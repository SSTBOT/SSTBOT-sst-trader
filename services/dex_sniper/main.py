from fastapi import FastAPI
import aiohttp
app = FastAPI(title="DEX Sniper")

@app.get("/")
async def root():
    return {"service": "DEX Sniper"}

@app.get("/opportunities")
async def opps():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.dexscreener.com/latest/dex/tokens/trending", timeout=5) as r:
                tokens = (await r.json()).get("tokens", [])[:10]
                return [{"symbol": t.get("symbol","?"), "price": float(t.get("price",0))} for t in tokens]
    except:
        return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
