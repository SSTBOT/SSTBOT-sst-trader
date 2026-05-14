import asyncio, logging, random, json, os, time
from datetime import datetime
import numpy as np
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SST")

BYBIT_KEY = "QtxrlcN1pPUPQFMpMW"
BYBIT_SECRET = "uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft"

def real_buy(symbol: str, amount_usd: float):
    """Реальная покупка на Bybit"""
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        sym = symbol.replace("/", "")
        ticker = session.get_tickers(category="spot", symbol=sym)
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 0)
        order = session.place_order(category="spot", symbol=sym, side="Buy", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0:
            logger.info(f"REAL BUY: {symbol} ${amount_usd} @ ${price}")
            return price
    except Exception as e:
        logger.error(f"Buy error: {e}")
    return None

def real_sell(symbol: str):
    """Реальная продажа всего объёма на Bybit"""
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        sym = symbol.replace("/", "")
        # Получаем баланс токена
        balance = session.get_wallet_balance(accountType="UNIFIED")
        for coin in balance["result"]["list"][0]["coin"]:
            if coin["coin"] == sym.replace("USDT", ""):
                qty = float(coin["walletBalance"])
                if qty > 0:
                    order = session.place_order(category="spot", symbol=sym, side="Sell", orderType="Market", qty=str(qty))
                    logger.info(f"REAL SELL: {symbol} qty={qty}")
                    return True
    except Exception as e:
        logger.error(f"Sell error: {e}")
    return False

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class St(StatesGroup): name = State()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 BUY DOGE $1"), KeyboardButton(text="💰 BUY SOL $5")],
        [KeyboardButton(text="📊 Баланс"), KeyboardButton(text="🤖 Авто-торговля")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🚀 SST REAL TRADING\n\n💰 BUY DOGE $1 — купить DOGE на $1\n💰 BUY SOL $5 — купить SOL на $5\n📊 Баланс — проверить баланс Bybit\n🤖 Авто-торговля — включить авто", reply_markup=main_kb())

@dp.message(F.text == "💰 BUY DOGE $1")
async def buy_doge(msg: types.Message):
    await msg.answer("🔄 Покупаю DOGE на $1...")
    price = real_buy("DOGE/USDT", 1.0)
    if price:
        await msg.answer(f"✅ Куплено DOGE на $1 по цене ${price:.4f}\nПроверь баланс Bybit!")
    else:
        await msg.answer("❌ Ошибка покупки")

@dp.message(F.text == "💰 BUY SOL $5")
async def buy_sol(msg: types.Message):
    await msg.answer("🔄 Покупаю SOL на $5...")
    price = real_buy("SOL/USDT", 5.0)
    if price:
        await msg.answer(f"✅ Куплено SOL на $5 по цене ${price:.2f}\nПроверь баланс Bybit!")
    else:
        await msg.answer("❌ Ошибка покупки")

@dp.message(F.text == "📊 Баланс")
async def balance(msg: types.Message):
    try:
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        bal = session.get_wallet_balance(accountType="UNIFIED")
        coins = bal["result"]["list"][0]["coin"]
        text = "📊 БАЛАНС BYBIT\n\n"
        total = 0
        for c in coins:
            amount = float(c["walletBalance"])
            if amount > 0:
                text += f"{c['coin']}: {amount:.4f}\n"
        text += f"\n💰 USDT: ~${float(bal['result']['list'][0]['totalWalletBalance']):.2f}"
        await msg.answer(text)
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

auto_trading = False

@dp.message(F.text == "🤖 Авто-торговля")
async def auto_toggle(msg: types.Message):
    global auto_trading
    auto_trading = not auto_trading
    await msg.answer(f"🤖 Авто-торговля: {'🟢 ВКЛ' if auto_trading else '🔴 ВЫКЛ'}")

async def auto_loop():
    while True:
        if auto_trading:
            # Каждые 60 сек покупаем DOGE на $1 и SOL на $5
            real_buy("DOGE/USDT", 1.0)
            await asyncio.sleep(2)
            real_buy("SOL/USDT", 5.0)
        await asyncio.sleep(60)

async def main():
    print("🚀 SST REAL TRADING")
    asyncio.create_task(auto_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
