import asyncio
import random
import aiohttp
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
                # Usamos domcontentloaded + espera manual para evitar bloqueos de red infinitos
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Esperamos a que aparezca al menos un elemento que parezca un precio.
                # Binance suele usar clases como 'bn-flex' o divs con texto de moneda.
                try:
                    await page.wait_for_selector('div:has-text(".")', timeout=10000)
                except:
                    pass # Seguimos si el selector falla pero la página cargó
                
                await asyncio.sleep(4) # Tiempo para que el JS renderice los números
                
                # Obtenemos el contenido
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Buscamos los precios (Clase detectada por inspección)
                # Nota: Los selectores de Binance cambian, este es el punto que requiere mantenimiento
                price_elements = soup.find_all('div', class_='bn-flex') # Placeholder, ajustaremos según realidad
                
                # Alternativa: Buscar por texto numérico con formato de precio
                found_prices = []
                divs = soup.find_all('div')
                for div in divs:
                    text = div.get_text(strip=True).replace(' ', '')
                    if text and any(c.isdigit() for c in text):
                        try:
                            # CRÍTICO: No confundir 3 decimales con millares.
                            # Si detectamos algo como "1.234" o "12.345", y el usuario dice
                            # que la ingesta tiene 3 decimales, el punto es SIEMPRE decimal.
                            
                            # Normalizar: eliminar comas si actúan como millares (ej: 3,689.432)
                            # O si la coma es el decimal (formato latino), convertir a punto.
                            if ',' in text and '.' in text:
                                # Formato 1,234.567 -> 1234.567
                                clean_text = text.replace(',', '')
                            elif ',' in text:
                                # Formato 1234,567 -> 1234.567
                                clean_text = text.replace(',', '.')
                            else:
                                clean_text = text
                            
                            val = float(clean_text)
                            if 0.1 < val < 2000000:
                                found_prices.append(val)
                        except:
                            continue
                
                prices = found_prices[:15]
                print(f"[+] {currency}: {len(prices)} precios encontrados.")
                return prices

            except Exception as e:
                print(f"[!] Error en {currency}: {str(e)}")
                return []
            finally:
                await browser.close()

    def calculate_purified_average(self, prices):
        """Implementa el algoritmo de exclusión iterativa +/- 1% (Lógica Anti-Outliers)"""
        if not prices:
            return 0.0
        
        current_prices = sorted(prices)
        original_count = len(current_prices)
        
        while len(current_prices) > 1:
            avg = sum(current_prices) / len(current_prices)
            lower_bound = avg * 0.99
            upper_bound = avg * 1.01
            
            # Buscamos el valor más extremo fuera del rango
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
            
        purified_avg = sum(current_prices) / len(current_prices) if current_prices else 0.0
        removed_count = original_count - len(current_prices)
        
        if removed_count > 0:
            # Guardamos info de depuración (interna)
            pass 
            
        return purified_avg

    async def get_brl_price(self):
        """Obtiene el precio de USDTBRL directamente de la API de Binance"""
        url = "https://api.binance.com/api/v3/ticker/price?symbol=USDTBRL"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                print(f"[*] Solicitando BRL a Binance API...")
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        val = float(data['price'])
                        print(f"[+] BRL obtenido: {val}")
                        return val
                    else:
                        print(f"[!] API BRL error: Status {response.status}")
                        return 0.0
            except Exception as e:
                print(f"[!] Error de red en BRL: {e}")
                return 0.0

    async def get_bcv_price(self):
        """Obtiene la tasa BCV desde tcambio.app"""
        url = "https://www.tcambio.app/"
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            try:
                print("[*] Escaneando BCV...")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(8)
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                text_content = soup.get_text()
                
                import re
                # Mejoramos el regex para buscar bajo el encabezado de "Dólar" en las tasas de BCV
                # O simplemente buscar el primer "Bs.S" que suele ser el dólar oficial
                match = re.search(r'Dólar.*?\nBs\.S\s*([\d,.]+)', text_content, re.IGNORECASE | re.DOTALL)
                if not match:
                    # Fallback al primer Bs.S encontrado
                    match = re.search(r'Bs\.S\s*([\d,.]+)', text_content)
                
                if match:
                    val_str = match.group(1).replace(',', '') # tcambio usa coma para miles a veces, o punto.
                    # Si el valor tiene coma y punto, asumimos formato americano (milla,decimal)
                    # Pero en Venezuela el BCV usa coma para decimales. 
                    # tcambio.app segun el log parece usar punto: Bs.S 344.50
                    if ',' in val_str and '.' in val_str:
                        val_str = val_str.replace(',', '')
                    elif ',' in val_str:
                        val_str = val_str.replace(',', '.')
                    
                    return float(val_str)
                return 0.0
            except Exception as e:
                print(f"[!] Error en BCV: {str(e)}")
                return 0.0
            finally:
                await browser.close()

async def main():
    radar = RadarV2()
    final_rates = {}
    
    # Procesamos TODAS las monedas
    all_currencies = list(BINANCE_URLS.keys())
    
    print("🚀 Iniciando Radar v2 (Stealth Mode) - Todas las Monedas")
    
    # 1. Binance P2P
    for fiat in all_currencies:
        prices = await radar.get_fiat_prices(fiat, BINANCE_URLS[fiat])
        avg = radar.calculate_purified_average(prices)
        
        # NUEVO AJUSTE: -1% SOLO para COP y VES
        adjustment = 0.99 if fiat in ["COP", "VES"] else 1.0
        final_rates[fiat] = avg * adjustment
        await asyncio.sleep(random.uniform(3, 6)) 

    # 2. BRL (Ticker)
    print("[*] Obteniendo BRL...")
    brl_avg = await radar.get_brl_price()
    final_rates["BRL"] = brl_avg # BRL no es COP/VES, ajuste 1.0

    # 3. BCV
    print("[*] Obteniendo BCV...")
    bcv_avg = await radar.get_bcv_price()
    # BCV es una tasa de intercambio oficial, NO aplica ajuste.
    final_rates["BCV"] = bcv_avg

    print("\n" + "="*40)
    print("✅ REPORTE TASA DEFINITIVA (Radar v2)")
    print("="*40)
    # Orden deseado completo
    order = ["PEN", "COP", "CLP", "ARS", "MXN", "BRL", "VES", "PYG", "DOP", "CRC", "EUR", "CAD", "BCV"]
    for fiat in order:
        if fiat in final_rates:
            val = final_rates[fiat]
            # REGLA DE VISUALIZACIÓN:
            # >= 500: Sin decimales
            # < 500: Dos decimales
            if val >= 500:
                print(f"{fiat:4}: {int(round(val, 0)):>10}")
            else:
                print(f"{fiat:4}: {val:>10.2f}")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())
