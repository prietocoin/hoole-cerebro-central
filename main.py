from fastapi import FastAPI
from radar import RadarV2
import asyncio

app = FastAPI(title="Hoole Cerebro Central API")
radar = RadarV2()

@app.get("/")
def read_root():
    return {"status": "online", "module": "Cerebro Central"}

@app.get("/radar")
async def get_market_rates():
    """
    Endpoint para obtener las tasas de mercado actualizadas.
    Llamado por n8n o el Dashboard.
    """
    from radar import BINANCE_URLS
    
    final_rates = {}
    all_currencies = list(BINANCE_URLS.keys())
    
    # Ejecutamos el radar
    for fiat in all_currencies:
        prices = await radar.get_fiat_prices(fiat, BINANCE_URLS[fiat])
        avg = radar.calculate_purified_average(prices)
        
        # Ajuste del -1% solo para COP y VES
        adjustment = 0.99 if fiat in ["COP", "VES"] else 1.0
        final_rates[fiat] = avg * adjustment
        await asyncio.sleep(1) # Delay corto en modo servidor

    # BRL y BCV
    final_rates["BRL"] = await radar.get_brl_price()
    
    bcv_raw = await radar.get_bcv_price()
    final_rates["BCV"] = bcv_raw # Sin ajuste según última instrucción
    
    # Formateo final para el cliente
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
