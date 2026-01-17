from fastapi import FastAPI
import asyncio

try:
    from radar import RadarV2
    radar = RadarV2()
except Exception as e:
    print(f"[ERROR] No se pudo inicializar RadarV2: {e}")
    radar = None

app = FastAPI(title="Hoole Cerebro Central API")

import time

# Memoria de caché global
CACHE = {
    "data": None,
    "timestamp": 0
}
CACHE_TTL = 300 # 5 minutos

@app.get("/")
def read_root():
    return {"status": "online", "message": "Hoole Cerebro Central arriba"}

@app.get("/test")
def test_connection():
    return {"status": "ok", "message": "Conexión exitosa desde n8n"}

async def process_fiat(fiat, url):
    """Procesador individual para cada moneda para ejecución en paralelo"""
    try:
        prices = await radar.get_fiat_prices(fiat, url)
        avg = radar.calculate_purified_average(prices)
        adjustment = 0.99 if fiat in ["COP", "VES"] else 1.0
        return fiat, avg * adjustment
    except Exception as e:
        print(f"[!] Error procesando {fiat}: {e}")
        return fiat, 0.0

@app.get("/radar")
async def get_market_rates():
    # 1. Verificar Caché
    now = time.time()
    if CACHE["data"] and (now - CACHE["timestamp"] < CACHE_TTL):
        print("[*] Sirviendo desde Caché (TTL: {}s)".format(int(CACHE_TTL - (now - CACHE["timestamp"]))))
        return {
            "success": True, 
            "cached": True, 
            "expires_in": int(CACHE_TTL - (now - CACHE["timestamp"])),
            **CACHE["data"]
        }

    try:
        from radar import BINANCE_URLS
        print(f"[*] Solicitud recibida en /radar. Iniciando escaneo PARALELO...")
        
        # 2. Ejecutar escaneos en PARALELO
        tasks = []
        for fiat, url in BINANCE_URLS.items():
            tasks.append(process_fiat(fiat, url))
        
        # Agregamos BRL y BCV a la lista de tareas paralelo
        # (Aunque BRL es API, lo metemos al saco para ahorrar tiempo)
        async def wrap_brl(): return "BRL", await radar.get_brl_price()
        async def wrap_bcv(): return "BCV", await radar.get_bcv_price()
        
        tasks.append(wrap_brl())
        tasks.append(wrap_bcv())
        
        # Lanzamos todo a la vez
        results = await asyncio.gather(*tasks)
        
        final_rates = dict(results)
        
        # Formateo final
        formatted_rates = {}
        for fiat, val in final_rates.items():
            if val >= 500:
                formatted_rates[fiat] = int(round(val, 0))
            else:
                formatted_rates[fiat] = round(val, 2)
        
        response_data = {
            "rates": formatted_rates,
            "raw_data": final_rates
        }

        # 3. Guardar en Caché
        CACHE["data"] = response_data
        CACHE["timestamp"] = now
            
        return {
            "success": True,
            "cached": False,
            **response_data
        }
    except Exception as e:
        print(f"[CRÍTICO] Fallo en /radar: {str(e)}")
        return {
            "success": False,
            "error_type": type(e).__name__,
            "message": str(e)
        }
