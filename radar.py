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
        """Extrae precios de Binance P2P usando Motor v3 (Evaluate & Anti-Risk)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency} (Motor v3)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(6) # Espera inicial para renderizado

                # --- SCRIPT DE LIMPIEZA DE AVISOS (Agresivo) ---
                await page.evaluate("""() => {
                    const selectors = [
                        'button:has-text("Confirm")', 'button:has-text("Confirmar")',
                        'button:has-text("I have read")', 'label:has-text("I have read")',
                        '.bn-checkbox', 'input[type="checkbox"]'
                    ];
                    selectors.forEach(sel => {
                        const els = document.querySelectorAll(sel);
                        els.forEach(el => el.click());
                    });
                }""")
                await asyncio.sleep(2)

                # --- EXTRACCIÓN DE PRECIOS VIA EVALUATE ---
                # Buscamos números que parezcan precios en la tabla principal
                prices = await page.evaluate("""() => {
                    const results = [];
                    // Los precios en Binance P2P suelen estar en divs con texto resaltado
                    const elements = document.querySelectorAll('div');
                    for (let el of elements) {
                        const text = el.innerText.trim().replace(/,/g, '');
                        if (/^\\d+\\.\\d+$/.test(text)) {
                            const val = parseFloat(text);
                            if (val > 0.01 && val < 5000000) results.push(val);
                        }
                    }
                    return results;
                }""")

                if not prices:
                    content = await page.content()
                    prices = [float(m) for m in re.findall(r'(\d+\.\d{2,})', content.replace(',', '')) if 0.1 < float(m) < 5000000]

                prices = sorted(list(set(prices)))[:15]
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
