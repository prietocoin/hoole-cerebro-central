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
        """Extrae precios de Binance P2P usando Motor v3.3 (Anti-Inflación & Consenso)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Motor v3.3)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # --- EXTRACCIÓN POR CONSENSO (v3.3) ---
                await asyncio.sleep(7)
                
                prices = await page.evaluate("""() => {
                    const results = [];
                    const elements = Array.from(document.querySelectorAll('div, span'));
                    const seen = {};
                    
                    elements.forEach(el => {
                        const text = el.innerText.trim().replace(/,/g, '');
                        // Buscamos números con decimales
                        if (/^\\d+\\.\\d{2}$/.test(text)) {
                            const val = parseFloat(text);
                            if (val > 0.05) {
                                seen[text] = (seen[text] || 0) + 1;
                                results.push(val);
                            }
                        }
                    });
                    
                    // Solo aceptamos números que se repiten (Precios de anuncios)
                    // Los metadatos de éxito suelen ser variados y únicos.
                    return results.filter(v => seen[v.toFixed(2)] >= 2);
                }""")

                # BANDAS EXTRA ANCHAS (Protección contra inflación extrema)
                ranges = {
                    "PEN": (1.0, 10.0), "COP": (1000, 10000), "CLP": (100, 3000),
                    "ARS": (100, 8000), "MXN": (5, 100), "VES": (5, 5000),
                    "PYG": (1000, 20000), "DOP": (20, 200), "CRC": (100, 2000),
                    "EUR": (0.1, 5.0), "CAD": (0.1, 5.0), "BRL": (1.0, 20.0)
                }
                
                low, high = ranges.get(currency, (0.01, 1000000))
                valid_prices = [p for p in prices if low <= p <= high]
                
                # Fallback Regex
                if not valid_prices:
                    content = await page.content()
                    regex = r'(\d+\.\d{2})'
                    raw_matches = re.findall(regex, content.replace(',', ''))
                    # En fallback también aplicamos consenso manual
                    counts = {}
                    for m in raw_matches: counts[m] = counts.get(m, 0) + 1
                    valid_prices = [float(m) for m, c in counts.items() if c >= 2 and low <= float(m) <= high]

                prices = sorted(list(set(valid_prices)))[:15]
                print(f"   [+] {currency}: {len(prices)} precios capturados.")
                return prices

            except Exception as e:
                print(f"   [!] Error en {currency}: {e}")
                return []
            finally:
                await browser.close()

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
