from fastapi import FastAPI
import secrets
app = FastAPI(title="Referral")

@app.get("/")
async def root():
    return {"service": "Referral System"}

@app.get("/generate/{user_id}")
async def gen(user_id: int):
    return {"code": f"SST{user_id}{secrets.token_hex(3).upper()}"}

@app.get("/stats/{user_id}")
async def stats(user_id: int):
    return {"invited_count": 0, "earnings": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
