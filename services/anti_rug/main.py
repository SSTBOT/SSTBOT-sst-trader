from fastapi import FastAPI
import aiohttp
app = FastAPI(title="Anti-Rug")

@app.get("/")
async def root():
    return {"service": "Anti-Rug Scanner"}

@app.get("/scan/{address}")
async def scan(address: str):
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses={address}"
            async with s.get(url, timeout=5) as r:
                t = (await r.json()).get("result", {}).get(address.lower(), {})
                return {
                    "is_honeypot": t.get("is_honeypot") == "1",
                    "sell_tax": float(t.get("sell_tax", 0)),
                    "risk_level": "CRITICAL" if t.get("is_honeypot") == "1" else "LOW"
                }
    except:
        return {"is_honeypot": False, "risk_level": "UNKNOWN"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
