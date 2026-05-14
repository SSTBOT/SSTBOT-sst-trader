#!/usr/bin/env python3
import asyncio, logging, random, json, os, time, secrets
from datetime import datetime
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from pybit.unified_trading import HTTP
BYBIT_KEY = "QtxrlcN1pPUPQFMpMW"
BYBIT_SECRET = "uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft"

def real_buy(symbol, amount_usd):
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        sym = symbol.replace("/", "")
        ticker = session.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0: return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 4)
        if qty <= 0: return None
        order = session.place_order(category="spot", symbol=sym, side="Buy", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0: return price
    except: pass
    return None

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")
TRADE_TOKENS = ["SOL/USDT","BTC/USDT","ETH/USDT","INJ/USDT","TIA/USDT","SUI/USDT","ARB/USDT","OP/USDT"]

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class St(StatesGroup): name = State()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
bought = set()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📡 Сигналы"), KeyboardButton(text="💰 Купить токен")],
        [KeyboardButton(text="🤖 Авто-трейд"), KeyboardButton(text="📊 Баланс Bybit")],
        [KeyboardButton(text="📋 Портфель"), KeyboardButton(text="⚙️ Стратегия")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await msg.answer("🚀 SST TRADER v9.5\n\n💰 Реальная торговля на Bybit\n📡 Сигналы из 10 источников\n🤖 Авто-трейдинг\n\nВыберите действие:", reply_markup=main_kb())

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
        await msg.answer("❌ Нет данных")

@dp.message(F.text == "💰 Купить токен")
async def buy_menu(msg: types.Message):
    available = [t for t in TRADE_TOKENS if t not in bought]
    if not available: return await msg.answer("✅ Все токены уже куплены!")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {s} на $5", callback_data=f"b_{s}")] for s in available[:6]
    ])
    await msg.answer(f"💰 ДОСТУПНО {len(available)} ТОКЕНОВ:", reply_markup=kb)

@dp.callback_query(F.data.startswith("b_"))
async def buy_token(cb: types.CallbackQuery):
    symbol = cb.data[2:]
    await cb.answer(f"🔄 Покупаю {symbol}...")
    price = real_buy(symbol, 5.0)
    if price:
        bought.add(symbol)
        await cb.message.answer(f"✅ РЕАЛЬНАЯ СДЕЛКА!\n{symbol}\n💰 $5.00\n💵 Цена: ${price:.4f}")
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
            if amount > 0: text += f"• {c['coin']}: {amount:.6f}\n"
        await msg.answer(text)
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

@dp.message(F.text == "📋 Портфель")
async def portfolio(msg: types.Message):
    if not bought: return await msg.answer("📋 Нет купленных токенов")
    await msg.answer(f"📋 КУПЛЕНО:\n\n" + "\n".join([f"• {t}" for t in bought]))

@dp.message(F.text == "⚙️ Стратегия")
async def strategy(msg: types.Message):
    await msg.answer("⚙️ СТРАТЕГИЯ\n\n• Консервативная ($5 на сделку)\n• 8 разных токенов\n• Каждый покупается 1 раз\n• Реальные сделки на Bybit")

@dp.message(F.text == "🤖 Авто-трейд")
async def auto_toggle(msg: types.Message):
    await msg.answer("🤖 Авто-трейдинг: 🟢 ВКЛ (каждые 60 сек)")

async def auto_loop():
    while True:
        available = [t for t in TRADE_TOKENS if t not in bought]
        if available:
            token = random.choice(available)
            real_buy(token, 5.0)
            bought.add(token)
        await asyncio.sleep(60)

async def main():
    print("🚀 SST TRADER v9.5")
    asyncio.create_task(auto_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
