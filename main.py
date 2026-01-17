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

app = FastAPI(title="Hoole Cerebro Central API")

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
    """Trabajador que actualiza las tasas cada 10 minutos proactivamente"""
    if not radar:
        print("[!] Radar no inicializado. El worker no arrancará.")
        return

    from radar import BINANCE_URLS
    
    while True:
        try:
            print(f"[*] [Worker] Iniciando actualización de tasas...")
            start_time = time.time()
            
            # Semáforo para no saturar el VPS (procesar de 2 en 2)
            sem = asyncio.Semaphore(2)
            
            async def safe_process(fiat, url):
                async with sem:
                    try:
                        print(f"   [Worker] Procesando {fiat}...")
                        prices = await radar.get_fiat_prices(fiat, url)
                        avg = radar.calculate_purified_average(prices)
                        print(f"   [Worker] ✅ {fiat} listo: {round(avg, 2)}")
                        return fiat, avg
                    except Exception as e:
                        print(f"   [Worker] ❌ Error en {fiat}: {e}")
                        return fiat, 0.0

            # Crear tareas para Binance P2P
            tasks = [safe_process(f, u) for f, u in BINANCE_URLS.items()]
            
            # Ejecutar P2P en paralelo (respetando el semáforo)
            results = await asyncio.gather(*tasks)
            
            # Obtener BRL y BCV por separado
            try:
                brl = await radar.get_brl_price()
                bcv = await radar.get_bcv_price()
            except Exception as e_extra:
                print(f"[!] Error en extras (BRL/BCV): {e_extra}")
                brl, bcv = 0.0, 0.0

            final_rates_raw = dict(results)
            final_rates_raw["BRL"] = brl
            final_rates_raw["BCV"] = bcv
            
            # Aplicar ajustes y formateo
            formatted_rates = {}
            final_rates_adjusted = {}
            
            for fiat, val in final_rates_raw.items():
                # Ajuste -1% solo para COP y VES (Binance P2P)
                # BCV y BRL tienen 0% ajuste (val * 1.0)
                adjustment = 0.99 if fiat in ["COP", "VES"] else 1.0
                val_adj = val * adjustment
                
                # Guardar valor ajustado para el cliente
                final_rates_adjusted[fiat] = val_adj
                
                # Formateo visual
                if val_adj >= 500:
                    formatted_rates[fiat] = int(round(val_adj, 0))
                else:
                    formatted_rates[fiat] = round(val_adj, 2)

            # Actualizar Caché Global
            CACHE["data"] = {
                "rates": formatted_rates,
                "raw_data": final_rates_adjusted
            }
            CACHE["timestamp"] = time.time()
            CACHE["status"] = "ready"
            
            duration = int(time.time() - start_time)
            print(f"[+] [Worker] Éxito. Tasas listas en {duration}s. Siguiente ciclo en 10m.")
            
        except Exception as e:
            print(f"[CRÍTICO] Error general en Worker: {e}")
            CACHE["status"] = "error"
        
        # Esperar 10 minutos (600s)
        await asyncio.sleep(600)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Hoole Cerebro Central arriba"}

@app.get("/test")
def test_connection():
    return {"status": "ok", "message": "Conexión exitosa"}

@app.get("/radar")
async def get_market_rates():
    """Retorna las tasas almacenadas en caché instantáneamente"""
    if CACHE["status"] == "initializing" and not CACHE["data"]["rates"]:
        return {
            "success": False,
            "status": "initializing",
            "message": "El Cerebro se está despertando. Reintenta en 30 segundos."
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
