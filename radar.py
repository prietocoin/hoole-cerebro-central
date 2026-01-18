import asyncio
import random
import aiohttp
import re
from playwright.async_api import async_playwright

# Configuración de Monedas y URLs
# Hemos añadido BRL a la lista de P2P para evitar el bloqueo de API 451
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
        """Extrae precios de Binance P2P usando Motor v3.2 (Extracción Quirúrgica)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Motor v3.2)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # --- EXTRACCIÓN QUIRÚRGICA (Motor v3.2) ---
                await asyncio.sleep(6)
                
                # Buscamos específicamente los elementos que suelen contener el precio
                prices = await page.evaluate("""() => {
                    const results = [];
                    const divs = Array.from(document.querySelectorAll('div'));
                    
                    const seen = {};
                    divs.forEach(div => {
                        const text = div.innerText.trim().replace(/,/g, '');
                        // Buscamos números con exactamente 2 decimales
                        if (/^\\d+\\.\\d{2}$/.test(text)) {
                            const val = parseFloat(text);
                            // Descartamos porcentajes de completado (0.xx) y valores ínfimos
                            if (val > 0.05) {
                                seen[text] = (seen[text] || 0) + 1;
                                results.push(val);
                            }
                        }
                    });
                    return results;
                }""")

                # RANGE FILTERS (Seguridad máxima)
                ranges = {
                    "PEN": (3.0, 4.5), "COP": (3000, 4500), "CLP": (800, 1100),
                    "ARS": (800, 1400), "MXN": (15, 25), "VES": (30, 600),
                    "PYG": (6000, 8000), "DOP": (50, 75), "CRC": (450, 600),
                    "EUR": (0.8, 1.3), "CAD": (1.1, 1.7), "BRL": (4.5, 6.5)
                }
                
                low, high = ranges.get(currency, (0.01, 1000000))
                valid_prices = [p for p in prices if low <= p <= high]
                
                # Fallback: Regex si el evaluate falló
                if not valid_prices:
                    content = await page.content()
                    # Ignoramos números que empiecen por 0. si no es EUR
                    regex = r'(\d+\.\d{2})' if currency == "EUR" else r'([1-9]\d*\.\d{2})'
                    raw_matches = re.findall(regex, content.replace(',', ''))
                    valid_prices = [float(m) for m in raw_matches if low <= float(m) <= high]

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
        """Fallback por compatibilidad"""
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
