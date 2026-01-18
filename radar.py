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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

class RadarV2:
    async def get_fiat_prices(self, currency, url):
        """Motor v4.1: Extracción por Fuerza Bruta (Inmune a cambios de CSS)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Fuerza Bruta v4.1)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # 1. ESPERA DE RENDERIZADO
                await asyncio.sleep(10)

                # 2. LIMPIEZA AGRESIVA DE MODALES (Multidioma)
                try:
                    modal_buttons = page.locator('button:has-text("Confirm"), button:has-text("Confirmar"), button:has-text("Aceptar"), button:has-text("I have read"), .bn-modal-footer button')
                    count = await modal_buttons.count()
                    for i in range(count):
                        await modal_buttons.nth(i).click(timeout=1000)
                        await asyncio.sleep(0.5)
                except: pass

                # 3. EXTRACCIÓN POR FUERZA BRUTA
                body_text = await page.evaluate("() => document.body.innerText")
                
                # Rangos lógicos para filtrar basura
                ranges = {
                    "PEN": (3.2, 4.3), "COP": (3200, 4800), "CLP": (800, 1200),
                    "ARS": (800, 1500), "MXN": (15, 23), "VES": (35, 550),
                    "PYG": (6000, 8500), "DOP": (55, 75), "CRC": (450, 650),
                    "EUR": (0.8, 1.3), "CAD": (1.2, 1.8), "BRL": (4.5, 6.5)
                }
                
                low, high = ranges.get(currency, (0.01, 1000000))
                
                clean_text = body_text.replace(',', '')
                raw_numbers = re.findall(r'(\d+\.\d{2,})', clean_text)
                
                found_prices = []
                for n in raw_numbers:
                    try:
                        val = float(n)
                        if low <= val <= high:
                            found_prices.append(val)
                    except: continue

                if not found_prices:
                    if currency == "BRL":
                        return await self.get_brl_ticker_fallback()
                    return []

                prices = sorted(list(set(found_prices)))[:15]
                print(f"   [+] {currency}: {len(prices)} precios extraídos.")
                return prices

            except Exception as e:
                print(f"   [!] Error en {currency}: {e}")
                return []
            finally:
                await browser.close()

    async def get_brl_ticker_fallback(self):
        """API Externa para BRL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://economia.awesomeapi.com.br/json/last/USDT-BRL", timeout=8) as resp:
                    data = await resp.json()
                    val = float(data["USDTBRL"]["bid"])
                    print(f"   [+] BRL (API Fallback): {val}")
                    return [val]
        except: return []

    def calculate_purified_average(self, prices):
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
        url = "https://www.tcambio.app/"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(5)
                text = await page.evaluate("() => document.body.innerText")
                import re
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
