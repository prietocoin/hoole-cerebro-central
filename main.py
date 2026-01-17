from fastapi import FastAPI
import asyncio

try:
    from radar import RadarV2
    radar = RadarV2()
except Exception as e:
    print(f"[ERROR] No se pudo inicializar RadarV2: {e}")
    radar = None

app = FastAPI(title="Hoole Cerebro Central API")

@app.get("/")
def read_root():
    return {"status": "online", "message": "Hoole Cerebro Central arriba"}

@app.get("/test")
def test_connection():
    """Endpoint instantáneo para probar si n8n llega al servidor"""
    return {"status": "ok", "message": "Conexión exitosa desde n8n"}

@app.get("/radar")
async def get_market_rates():
    """
    Endpoint para obtener las tasas de mercado actualizadas.
    Llamado por n8n o el Dashboard.
    """
    try:
        from radar import BINANCE_URLS
        print(f"[*] Solicitud recibida en /radar. Iniciando escaneo...")
        
        final_rates = {}
        all_currencies = list(BINANCE_URLS.keys())
        
        # Ejecutamos el radar
        for fiat in all_currencies:
            try:
                prices = await radar.get_fiat_prices(fiat, BINANCE_URLS[fiat])
                avg = radar.calculate_purified_average(prices)
                
                # Ajuste del -1% solo para COP y VES
                adjustment = 0.99 if fiat in ["COP", "VES"] else 1.0
                final_rates[fiat] = avg * adjustment
                # Delay mínimo en entorno servidor
                await asyncio.sleep(0.3) 
            except Exception as e_inner:
                print(f"[!] Error procesando {fiat}: {e_inner}")
                final_rates[fiat] = 0.0

        # BRL y BCV
        try:
            final_rates["BRL"] = await radar.get_brl_price()
            final_rates["BCV"] = await radar.get_bcv_price()
        except Exception as e_extra:
            print(f"[!] Error extras: {e_extra}")
        
        # Formateo final
        formatted_rates = {}
        for fiat, val in final_rates.items():
            if val >= 500:
                formatted_rates[fiat] = int(round(val, 0))
            else:
                formatted_rates[fiat] = round(val, 2)
            
        return {
            "success": True,
            "rates": formatted_rates,
            "raw_data": final_rates
        }
    except Exception as e:
        print(f"[CRÍTICO] Fallo general en /radar: {str(e)}")
        return {
            "success": False,
            "error_type": type(e).__name__,
            "message": str(e)
        }
