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

                # --- LIMPIEZA DE AVISOS (Motor v3.1 - Corregido) ---
                # Usamos el sistema nativo de Playwright para evitar el error de sintaxis anterior
                warning_selectors = [
                    'button:has-text("Confirm")', 
                    'button:has-text("Confirmar")',
                    'button:has-text("I have read")',
                    'label:has-text("I have read")'
                ]
                for selector in warning_selectors:
                    try:
                        locator = page.locator(selector)
                        if await locator.is_visible(timeout=3000):
                            await locator.click()
                            await asyncio.sleep(1)
                    except: pass

                # --- EXTRACCIÓN DE PRECIOS ---
                # Buscamos los precios reales que Binance renderiza en la tabla
                # Esperamos un poco más para asegurar que el DOM esté listo tras los clicks
                await asyncio.sleep(3)
                content = await page.content()
                
                # Extraemos números que tengan al menos 2 decimales
                # Usamos un regex que capture formatos 1.23, 1,234.56, etc.
                import re
                # Primero quitamos las comas que actúan como separador de miles
                clean_content = content.replace(',', '')
                raw_matches = re.findall(r'(\d+\.\d{2,})', clean_content)
                
                found_prices = []
                for m in raw_matches:
                    try:
                        val = float(m)
                        # Filtro de rango lógico para detectar precios P2P
                        if 0.1 < val < 5000000:
                            found_prices.append(val)
                    except: continue

                # Si no encontramos nada, usamos un selector CSS genérico como último recurso
                if not found_prices:
                    text_els = await page.locator('div').all_inner_texts()
                    for t in text_els:
                        t_clean = t.replace(',', '').strip()
                        if re.match(r'^\d+\.\d+$', t_clean):
                            try:
                                val = float(t_clean)
                                if 0.1 < val < 5000000: found_prices.append(val)
                            except: continue

                prices = sorted(list(set(found_prices)))[:15]
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
        # Eliminamos extremos si hay suficientes datos
        if len(p) > 5: p = p[1:-1]
        
        avg = sum(p) / len(p)
        purified = [x for x in p if avg * 0.98 <= x <= avg * 1.02]
        
        return sum(purified) / len(purified) if purified else avg

    async def get_brl_price(self):
        """Fallback BRL: Intentamos P2P si la API falló"""
        # Ya incluimos BRL en BINANCE_URLS, así que main.py lo procesará vía P2P automáticamente
        # Pero dejamos este método por compatibilidad con el código anterior de main.py
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
                    # Normalización de venezuela (mil.punto, decimal,coma o similar)
                    val = match.group(1).replace(',', '.')
                    if val.count('.') > 1:
                        parts = val.split('.')
                        val = "".join(parts[:-1]) + "." + parts[-1]
                    return float(val)
                return 0.0
            except: return 0.0
            finally: await browser.close()
