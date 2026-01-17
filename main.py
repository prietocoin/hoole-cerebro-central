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
    "data": {
        "rates": {},
        "raw_data": {}
    },
    "timestamp": 0,
    "status": "initializing"
}

@app.on_event("startup")
async def startup_event():
    """Al arrancar el servidor, lanzamos el trabajador de fondo"""
    asyncio.create_task(background_radar_worker())

async def background_radar_worker():
    """Trabajador que actualiza las tasas cada 10 minutos perpetuamente"""
    from radar import BINANCE_URLS
    
    while True:
        try:
            print(f"[*] [Worker] Iniciando actualización proactiva de tasas...")
            start_time = time.time()
            
            # Procesamos de 2 en 2 para no saturar la RAM del VPS (Semaphore)
            sem = asyncio.Semaphore(2)
            
            async def safe_process(fiat, url):
                async with sem:
                    try:
                        prices = await radar.get_fiat_prices(fiat, url)
                        avg = radar.calculate_purified_average(prices)
                        return fiat, avg
                    except Exception as e:
                        print(f"[!] Error worker en {fiat}: {e}")
                        return fiat, 0.0

            tasks = [safe_process(f, u) for f, u in BINANCE_URLS.items()]
            
            # Agregamos BRL y BCV (rápido)
            async def get_extras():
                brl = await radar.get_brl_price()
                bcv = await radar.get_bcv_price()
                return [("BRL", brl), ("BCV", bcv)]

            results = await asyncio.gather(*tasks)
            extras = await get_extras()
            
            final_rates = dict(results + extras)
            
            # Aplicamos ajustes y formateo
            formatted_rates = {}
            for fiat, val in final_rates.items():
                # Ajuste -1% COP y VES
                adj = 0.99 if fiat in ["COP", "VES"] else 1.0
                val_adj = val * adj
                
                if val_adj >= 500:
                    formatted_rates[fiat] = int(round(val_adj, 0))
                else:
                    formatted_rates[fiat] = round(val_adj, 2)
                
                final_rates[fiat] = val_adj # Guardamos el ajustado en raw también

            # Actualizamos CACHE
            CACHE["data"] = {
                "rates": formatted_rates,
                "raw_data": final_rates
            }
            CACHE["timestamp"] = time.time()
            CACHE["status"] = "ready"
            
            duration = int(time.time() - start_time)
            print(f"[+] [Worker] Tasas actualizadas con éxito en {duration}s. Próxima actualización en 10min.")
            
        except Exception as e:
            print(f"[CRÍTICO] Error en worker: {e}")
            CACHE["status"] = "error"
        
        # Esperamos 10 minutos antes de la siguiente vuelta
        await asyncio.sleep(600)

@app.get("/radar")
async def get_market_rates():
    """
    Endpoint instantáneo: responde con lo que haya en la CACHE.
    """
    if CACHE["status"] == "initializing" and not CACHE["data"]["rates"]:
        return {
            "success": False,
            "status": "initializing",
            "message": "El Cerebro se está despertando. Por favor, espera 30 segundos y recarga."
        }
    
    now = time.time()
    age = int(now - CACHE["timestamp"])
    
    return {
        "success": True,
        "status": CACHE["status"],
        "age_seconds": age,
        "updated_at": time.ctime(CACHE["timestamp"]),
        **CACHE["data"]
    }
