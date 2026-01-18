from fastapi import FastAPI
import asyncio
import time
import random

try:
    from radar import RadarV2
    radar = RadarV2()
except Exception as e:
    print(f"[ERROR] No se pudo inicializar RadarV2: {e}")
    radar = None

app = FastAPI(title="Hoole Cerebro Central API v4")

# Memoria de caché global
CACHE = {
    "data": {"rates": {}, "raw_data": {}},
    "timestamp": 0,
    "status": "initializing"
}

@app.on_event("startup")
async def startup_event():
    print("🚀 [Sistema] Motor v4 de Alta Precisión (Selectores CSS) Iniciado.")
    asyncio.create_task(background_radar_worker())

async def background_radar_worker():
    if not radar: return

    from radar import BINANCE_URLS
    
    while True:
        try:
            print(f"\n[*] [Worker v4] Iniciando ciclo de escaneo quirúrgico...")
            start_time = time.time()
            
            # Semáforo para cuidar la RAM del VPS (2 en 2)
            sem = asyncio.Semaphore(2)
            
            async def safe_process(fiat, url):
                async with sem:
                    try:
                        prices = await radar.get_fiat_prices(fiat, url)
                        avg = radar.calculate_purified_average(prices)
                        print(f"   -> {fiat} listo: {round(avg, 2)}")
                        return fiat, avg
                    except Exception as e:
                        print(f"   [!] Error en {fiat}: {e}")
                        return fiat, 0.0

            # Procesamos todas las monedas
            tasks = [safe_process(f, u) for f, u in BINANCE_URLS.items()]
            results = await asyncio.gather(*tasks)
            
            # BCV (Especial)
            bcv_val = await radar.get_bcv_price()
            results.append(("BCV", bcv_val))

            final_rates_raw = dict(results)
            
            # Formateo y Ajustes
            formatted_rates = {}
            final_rates_adjusted = {}
            
            for fiat, val in final_rates_raw.items():
                if val <= 0: continue
                # Ajuste -1% solo COP y VES
                adj = 0.99 if fiat in ["COP", "VES"] else 1.0
                val_adj = val * adj
                
                final_rates_adjusted[fiat] = val_adj
                if val_adj >= 100:
                    formatted_rates[fiat] = int(round(val_adj, 0))
                else:
                    formatted_rates[fiat] = round(val_adj, 2)

            # Actualizar Caché
            if formatted_rates:
                CACHE["data"] = {"rates": formatted_rates, "raw_data": final_rates_adjusted}
                CACHE["timestamp"] = time.time()
                CACHE["status"] = "ready"
            
            duration = int(time.time() - start_time)
            print(f"[+] [Worker v4] Ciclo completado en {duration}s. Datos listos en /radar.")
            
        except Exception as e:
            print(f"[CRÍTICO] Fallo en Cycle: {e}")
            CACHE["status"] = "error"
        
        # Actualización cada 2 minutos
        await asyncio.sleep(120)

@app.get("/")
def read_root():
    return {"status": "online", "version": "v4-final"}

@app.get("/radar")
async def get_market_rates():
    if not CACHE["data"]["rates"]:
        return {"success": False, "status": "initializing", "msg": "Motor v4 escaneando..."}
    
    return {
        "success": True,
        "age_seconds": int(time.time() - CACHE["timestamp"]),
        **CACHE["data"]
    }
