import asyncio
import random
import aiohttp
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Configuración de Monedas y URLs (Inspirado en Promedios.json)
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
    "EUR": "https://p2p.binance.com/trade/SEPAinstant/USDT?fiat=EUR",
    "CAD": "https://p2p.binance.com/trade/all-payments/USDT?fiat=CAD"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

class RadarV2:
    def __init__(self):
        self.results = {}

    async def get_fiat_prices(self, currency, url):
        """Extrae los precios de Binance P2P usando Playwright (Stealth mode)"""
        async with async_playwright() as p:
            # Lanzamos el navegador con configuración compatible para Docker
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu"
                ]
            ) 
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"}
            )
            
            page = await context.new_page()
            
            try:
                print(f"[*] Escaneando {currency}...")
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # REGLA ANTI-AVISOS: Si aparece el botón de "Confirmar" o "I have read", lo pulsamos
                try:
                    # Buscamos botones de confirmación que suelen bloquear la vista
                    warning_buttons = [
                        'button:has-text("Confirm")', 
                        'button:has-text("I have read")',
                        'button:has-text("Confirmar")'
                    ]
                    for btn in warning_buttons:
                        if await page.is_visible(btn):
                            await page.click(btn)
                            await asyncio.sleep(1)
                except:
                    pass
                
                # Esperar a los precios reales
                await asyncio.sleep(5)
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                found_prices = []
                # Buscamos elementos que contengan números con decimales (formato precio)
                # Binance suele renderizar los precios en divs con la clase 'bn-flex' o similar
                potential_divs = soup.find_all(['div', 'span'], string=re.compile(r'\d+\.\d+'))
                
                # Fallback: Extraer todo texto que parezca un precio significativo
                if not potential_divs:
                    divs = soup.find_all('div')
                    for div in divs:
                        t = div.get_text(strip=True).replace(',', '')
                        if t and re.match(r'^\d+(\.\d+)?$', t):
                            val = float(t)
                            if 0.1 < val < 2000000:
                                found_prices.append(val)
                else:
                    for item in potential_divs:
                        try:
                            val = float(item.get_text(strip=True).replace(',', ''))
                            if 0.1 < val < 2000000:
                                found_prices.append(val)
                        except: continue

                # Si seguimos sin precios, intentamos un último escaneo agresivo
                if not found_prices:
                    text = soup.get_text()
                    # Regex para números con 2 o más decimales
                    matches = re.findall(r'(\d+\.\d{2,})', text)
                    found_prices = [float(m) for m in matches if 0.1 < float(m) < 2000000]

                prices = sorted(list(set(found_prices)))[:15]
                print(f"[+] {currency}: {len(prices)} precios encontrados.")
                return prices

            except Exception as e:
                print(f"[!] Error en {currency}: {str(e)}")
                return []
            finally:
                await browser.close()

    def calculate_purified_average(self, prices):
        """Implementa el algoritmo de exclusión iterativa +/- 1% (Lógica Anti-Outliers)"""
        if not prices or len(prices) < 2:
            return prices[0] if prices else 0.0
        
        current_prices = sorted(prices)
        original_count = len(current_prices)
        
        # Eliminamos el 20% más alto y más bajo antes de empezar para ser más robustos
        if len(current_prices) >= 5:
            current_prices = current_prices[1:-1]

        while len(current_prices) > 2:
            avg = sum(current_prices) / len(current_prices)
            lower_bound = avg * 0.98 # Un poco más permisivo para evitar quedarnos sin datos
            upper_bound = avg * 1.02
            
            to_remove = None
            max_dist = -1
            
            for p in current_prices:
                if p < lower_bound or p > upper_bound:
                    dist = abs(p - avg)
                    if dist > max_dist:
                        max_dist = dist
                        to_remove = p
            
            if to_remove is None:
                break
            current_prices.remove(to_remove)
            
        return sum(current_prices) / len(current_prices) if current_prices else 0.0

    async def get_brl_price(self):
        """Obtiene BRL usando una ruta alternativa para evitar el error 451"""
        # Intentamos con varias APIs para saltar bloqueos geográficos
        urls = [
            "https://api.binance.com/api/v3/ticker/price?symbol=USDTBRL",
            "https://api1.binance.com/api/v3/ticker/price?symbol=USDTBRL",
            "https://api3.binance.com/api/v3/ticker/price?symbol=USDTBRL"
        ]
        
        for url in urls:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            async with aiohttp.ClientSession(headers=headers) as session:
                try:
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            val = float(data['price'])
                            print(f"[+] BRL obtenido: {val}")
                            return val
                except: continue
        print("[!] No se pudo obtener BRL de ninguna API.")
        return 0.0

    async def get_bcv_price(self):
        """Obtiene la tasa BCV desde tcambio.app con selector más robusto"""
        url = "https://www.tcambio.app/"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(5)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                text = soup.get_text()
                match = re.search(r'(?:BCV|Central).*?([\d,.]+)', text, re.IGNORECASE | re.DOTALL)
                if match:
                    val_str = match.group(1).replace(',', '.')
                    if val_str.count('.') > 1:
                        parts = val_str.split('.')
                        val_str = "".join(parts[:-1]) + "." + parts[-1]
                    val = float(val_str)
                    print(f"[+] BCV obtenido: {val}")
                    return val
                return 0.0
            except: return 0.0
            finally: await browser.close()
