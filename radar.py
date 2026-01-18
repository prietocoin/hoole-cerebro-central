import asyncio
import random
import aiohttp
import re
from playwright.async_api import async_playwright

# Configuración de Monedas y URLs
BINANCE_URLS = {
    "PEN": "https://p2p.binance.com/trade/all-payments/USDT?fiat=PEN",
    "COP": "https://p2p.binance.com/trade/all-payments/USDT?fiat=COP",
    "CLP": "https://p2p.binance.com/trade/all-payments/USDT?fiat=CLP",
    "ARS": "https://p2p.binance.com/trade/all-payments/USDT?fiat=ARS",
    "MXN": "https://p2p.binance.com/trade/all-payments/USDT?fiat=MXN",
    "VES": "https://p2p.binance.com/trade/all-payments/USDT?fiat=VES",
    "PYG": "https://p2p.binance.com/trade/all-payments/USDT?fiat=PYG",
    "DOP": "https://p2p.binance.com/trade/all-payments/USDT?fiat=DOP",
    "CRC": "https://p2p.binance.com/trade/all-payments/USDT?fiat=CRC",
    "EUR": "https://p2p.binance.com/trade/all-payments/USDT?fiat=EUR",
    "CAD": "https://p2p.binance.com/trade/all-payments/USDT?fiat=CAD",
    "BRL": "https://p2p.binance.com/trade/all-payments/USDT?fiat=BRL"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

class RadarV2:
    async def get_fiat_prices(self, currency, url):
        """Motor v4: Extracción Profesional por Selectores CSS Reales"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Motor v4)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Esperar a que los anuncios carguen (selector real de Binance)
                try:
                    await page.wait_for_selector(".bn-web-table-row", timeout=15000)
                except:
                    if currency == "BRL":
                        print(f"   [!] BRL P2P bloqueado. Usando fallback de API...")
                        return await self.get_brl_ticker_fallback()
                    return []

                # --- EXTRACCIÓN QUIRÚRGICA ---
                # Extraemos el texto de la columna Headline5 (donde está el precio real)
                await asyncio.sleep(2)
                price_texts = await page.locator(".bn-web-table-row .headline5.text-primaryText").all_inner_texts()
                
                found_prices = []
                for pt in price_texts:
                    try:
                        # Limpiar: "S/. 3.553" -> "3.553"
                        clean = "".join(c for c in pt if c.isdigit() or c in ".,")
                        if "," in clean and "." in clean: clean = clean.replace(",", "")
                        elif "," in clean:
                            if len(clean.split(",")[-1]) == 2: clean = clean.replace(",", ".")
                            else: clean = clean.replace(",", "")
                            
                        val = float(clean)
                        if val > 0.1: found_prices.append(val)
                    except: continue

                if not found_prices and currency == "BRL":
                    return await self.get_brl_ticker_fallback()

                prices = sorted(list(set(found_prices)))[:15]
                print(f"   [+] {currency}: {len(prices)} precios capturados.")
                return prices

            except Exception as e:
                print(f"   [!] Error en {currency}: {e}")
                return []
            finally:
                await browser.close()

    async def get_brl_ticker_fallback(self):
        """Recurso de emergencia para BRL (AwesomeAPI)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://economia.awesomeapi.com.br/json/last/USDT-BRL", timeout=8) as resp:
                    data = await resp.json()
                    val = float(data["USDTBRL"]["bid"])
                    print(f"   [+] BRL (Fallback): {val}")
                    return [val]
        except: return []

    def calculate_purified_average(self, prices):
        """Algoritmo de Purificación +/- 1%"""
        if not prices: return 0.0
        if len(prices) == 1: return prices[0]
        p = sorted(prices)
        if len(p) > 5: p = p[1:-1]
        avg = sum(p) / len(p)
        purified = [x for x in p if avg * 0.98 <= x <= avg * 1.02]
        return sum(purified) / len(purified) if purified else avg

    async def get_brl_price(self):
        p = await self.get_fiat_prices("BRL", BINANCE_URLS["BRL"])
        return self.calculate_purified_average(p)

    async def get_bcv_price(self):
        """BCV estable vía tcambio.app"""
        url = "https://www.tcambio.app/"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(5)
                text = await page.evaluate("() => document.body.innerText")
                match = re.search(r'(?:BCV|Central|Dólar).*?([\d,.]+)', text, re.I | re.S)
                if match:
                    val = match.group(1).replace(',', '.')
                    if val.count('.') > 1:
                        parts = val.split('.')
                        val = "".join(parts[:-1]) + "." + parts[-1]
                    return float(val)
                return 0.0
            except: return 0.0
            finally: await browser.close()
