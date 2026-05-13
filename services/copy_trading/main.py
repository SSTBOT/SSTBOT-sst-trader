from fastapi import FastAPI
app = FastAPI(title="Copy Trading")
TRACKED = ["0x1234567890abcdef1234567890abcdef12345678"]

@app.get("/")
async def root():
    return {"service": "Copy Trading"}

@app.get("/wallets")
async def wallets():
    return {"wallets": TRACKED}

@app.get("/track/{wallet}")
async def track(wallet: str):
    if wallet not in TRACKED:
        TRACKED.append(wallet)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
