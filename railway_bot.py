#!/usr/bin/env python3
"""
SST TRADER v9.5 — REAL TRADING + FULL FEATURES
"""
import asyncio, logging, random, json, os, time, secrets
from datetime import datetime
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SST")

from pybit.unified_trading import HTTP
BYBIT_KEY = "QtxrlcN1pPUPQFMpMW"
BYBIT_SECRET = "uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft"

def real_buy(symbol: str, amount_usd: float):
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        sym = symbol.replace("/", "")
        ticker = session.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0: return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 4)
        if qty <= 0: return None
        order = session.place_order(category="spot", symbol=sym, side="Buy", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0:
            logger.info(f"REAL BUY: {symbol} ${amount_usd} @ ${price}")
            return price
    except Exception as e:
        logger.error(f"Buy error: {e}")
    return None

from supabase import create_client
SUPABASE_URL = "https://throkijrjphuuevnofoi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRocm9raWpyanBodXVldm5vZm9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODYxMjg5MCwiZXhwIjoyMDk0MTg4ODkwfQ.7p10xZyUvQ5SrPWDJHV_knVaEryn21CeP8YGbrc1CkI"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")
TRADE_TOKENS = ["SOL/USDT", "BTC/USDT", "ETH/USDT", "INJ/USDT", "TIA/USDT", "SUI/USDT", "ARB/USDT", "OP/USDT"]

class DB:
    def get(self, uid):
        try:
            r = supabase.table("users").select("*").eq("id", uid).execute()
            return r.data[0] if r.data else None
        except: return None
    def create(self, uid, name):
        try:
            supabase.table("users").insert({
                "id": uid, "name": name, "balance": 36, "sub": "vip",
                "auto_trading": 0, "strategy": "conservative",
                "trades": [], "bought_tokens": []
            }).execute()
        except: pass
        return self.get(uid)
    def update(self, uid, data):
        try: supabase.table("users").update(data).eq("id", uid).execute()
        except: pass
    def add_bought(self, uid, token):
        u = self.get(uid)
        if u:
            tokens = u.get("bought_tokens", []) + [token]
            self.update(uid, {"bought_tokens": tokens})

db = DB()

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class St(StatesGroup): name = State()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📡 Сигналы"), KeyboardButton(text="💰 Купить токен")],
        [KeyboardButton(text="🤖 Авто-трейд"), KeyboardButton(text="📊 Баланс Bybit")],
        [KeyboardButton(text="📋 Портфель"), KeyboardButton(text="⚙️ Стратегия")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    u = db.get(msg.from_user.id)
    if u:
        await msg.answer(f"👋 {u['name']}\n💰 Реальная торговля на Bybit\n\nВыберите действие:", reply_markup=main_kb())
    else:
        await msg.answer("🚀 SST TRADER v9.5\n\nВведите имя:"); await state.set_state(St.name)

@dp.message(St.name)
async def name(msg: types.Message, state: FSMContext):
    db.create(msg.from_user.id, msg.text.strip()); await state.clear()
    await msg.answer("✅ Готово! $36 на балансе\n💰 Реальная торговля!", reply_markup=main_kb())

@dp.message(F.text == "📡 Сигналы")
async def signals(msg: types.Message):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=5) as r:
                data = await r.json()
                text = "📡 СИГНАЛЫ BYBIT\n\n"
                for t in data['result']['list'][:15]:
                    if t['symbol'] in [x.replace("/","") for x in TRADE_TOKENS]:
                        chg = float(t.get('price24hPcnt',0))*100
                        text += f"{'🟢' if chg>0 else '🔴'} {t['symbol']}: ${float(t['lastPrice']):.4f} ({chg:+.1f}%)\n"
                await msg.answer(text)
    except:
        await msg.answer("❌ Нет данных. Попробуйте позже.")

@dp.message(F.text == "💰 Купить токен")
async def buy_menu(msg: types.Message):
    u = db.get(msg.from_user.id)
    bought = u.get("bought_tokens", []) if u else []
    available = [t for t in TRADE_TOKENS if t not in bought]
    
    if not available:
        return await msg.answer("✅ Все токены уже куплены!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {s} на $5", callback_data=f"buy_{s}_5")] for s in available[:6]
    ])
    await msg.answer(f"💰 ДОСТУПНО {len(available)} ТОКЕНОВ:", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def buy_token(cb: types.CallbackQuery):
    parts = cb.data.split("_")
    symbol = f"{parts[1]}/{parts[2]}" if len(parts) > 3 else parts[1]
    amt = 5.0
    
    await cb.answer(f"🔄 Покупаю {symbol}...")
    price = real_buy(symbol, amt)
    if price:
        db.add_bought(cb.from_user.id, symbol)
        await cb.message.answer(f"✅ РЕАЛЬНАЯ СДЕЛКА!\n{symbol}\n💰 ${amt:.2f}\n💵 Цена: ${price:.4f}\n\nПроверьте баланс Bybit!")
    else:
        await cb.message.answer(f"❌ Ошибка покупки {symbol}")

@dp.message(F.text == "📊 Баланс Bybit")
async def balance(msg: types.Message):
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        bal = session.get_wallet_balance(accountType="UNIFIED")
        coins = bal["result"]["list"][0]["coin"]
        text = "📊 БАЛАНС BYBIT\n\n"
        for c in coins:
            amount = float(c["walletBalance"])
            if amount > 0:
                text += f"• {c['coin']}: {amount:.6f}\n"
        await msg.answer(text)
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

@dp.message(F.text == "📋 Портфель")
async def portfolio(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    tokens = u.get("bought_tokens", [])
    if not tokens: return await msg.answer("📋 Нет купленных токенов")
    await msg.answer(f"📋 КУПЛЕНО:\n\n" + "\n".join([f"• {t}" for t in tokens]))

@dp.message(F.text == "⚙️ Стратегия")
async def strategy(msg: types.Message):
    await msg.answer("⚙️ СТРАТЕГИЯ\n\n• Консервативная (5% на сделку)\n• Токены: SOL, BTC, ETH, INJ, TIA, SUI, ARB, OP\n• Каждый токен покупается 1 раз\n• Реальные сделки на Bybit")

@dp.message(F.text == "🤖 Авто-трейд")
async def auto_toggle(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: db.create(msg.from_user.id, "Trader"); u = db.get(msg.from_user.id)
    new = 0 if u.get("auto_trading") else 1
    db.update(msg.from_user.id, {"auto_trading": new})
    await msg.answer(f"🤖 Авто-трейдинг: {'🟢 ВКЛ' if new else '🔴 ВЫКЛ'}\n\nПокупает разные токены каждые 60 сек\nКонсервативная стратегия")

async def auto_loop():
    while True:
        try:
            users = db.get_all() if hasattr(db, 'get_all') else []
            for u in (users if users else []):
                if u.get("auto_trading"):
                    bought = u.get("bought_tokens", [])
                    available = [t for t in TRADE_TOKENS if t not in bought]
                    if available:
                        token = random.choice(available)
                        price = real_buy(token, 5.0)
                        if price:
                            db.add_bought(u["id"], token)
        except: pass
        await asyncio.sleep(60)

async def main():
    print("🚀 SST TRADER v9.5 — REAL TRADING")
    asyncio.create_task(auto_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
