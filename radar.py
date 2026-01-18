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
        """Motor v5: Extracción Estructural (Sin Rangos)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Motor v5)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                await asyncio.sleep(8)
                try:
                    await page.locator('button:has-text("Confirm"), button:has-text("Confirmar"), button:has-text("Aceptar")').first.click(timeout=3000)
                except: pass

                # EXTRACCIÓN ESTRUCTURAL
                prices = await page.evaluate("""() => {
                    const results = [];
                    const rows = Array.from(document.querySelectorAll('.bn-web-table-row, [role="row"]'));
                    
                    rows.forEach(row => {
                        const text = row.innerText.replace(/,/g, '');
                        // Buscamos números con decimales (Precio)
                        const matches = text.match(/(\\d+\\.\\d{2,})/g);
                        if (matches) {
                            matches.forEach(m => {
                                const val = parseFloat(m);
                                // Filtro mínimo absoluto solo para evitar basura total (0.1)
                                if (val > 0.1) results.push(val);
                            });
                        }
                    });
                    return results;
                }""")

                if not prices:
                    content = await page.content()
                    raw_matches = re.findall(r'(\d+[.,]\d{2,})', content.replace(',', ''))
                    prices = [float(m) for m in raw_matches if float(m) > 0.1]

                if not prices and currency == "BRL":
                    return await self.get_brl_ticker_fallback()

                prices = sorted(list(set(prices)))[:15]
                print(f"   [+] {currency}: {len(prices)} precios capturados.")
                return prices

            except Exception as e:
                print(f"   [!] Error en {currency}: {e}")
                return []
            finally:
                await browser.close()

    async def get_brl_ticker_fallback(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://economia.awesomeapi.com.br/json/last/USDT-BRL", timeout=8) as resp:
                    data = await resp.json()
                    val = float(data["USDTBRL"]["bid"])
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
