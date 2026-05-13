import logging, os
from fastapi import FastAPI
import aiohttp
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AI Predictor")

@app.get("/")
async def root():
    return {"service": "AI Predictor"}

@app.get("/predict/{symbol}")
async def predict(symbol: str):
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol.replace('/','')}"
            async with s.get(url, timeout=5) as r:
                d = await r.json()
                if d.get("retCode") == 0 and d["result"]["list"]:
                    t = d["result"]["list"][0]
                    p = float(t["lastPrice"])
                    c = float(t.get("price24hPcnt", 0)) * 100
                    return {
                        "symbol": symbol,
                        "current_price": p,
                        "predictions": {"1h": p*(1+c/200), "4h": p*(1+c/100)},
                        "confidence": min(95, 50+abs(c)*3),
                        "trend": "BULLISH" if c > 2 else ("BEARISH" if c < -2 else "NEUTRAL")
                    }
    except:
        pass
    return {"symbol": symbol, "current_price": 0, "predictions": {}, "confidence": 50, "trend": "NEUTRAL"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
