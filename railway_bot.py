import asyncio, logging, random, json, os
from datetime import datetime
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")
SUPABASE_URL = "https://5oukEO6ho0wCH0NV9zuvBw.supabase.co"
SUPABASE_KEY = "sb_publishable_5oukEO6ho0wCH0NV9zuvBw_RKRCvl4Z"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class DB:
    def get(self, uid):
        try:
            r = supabase.table("users").select("*").eq("id", uid).execute()
            return r.data[0] if r.data else None
        except: return None
    def create(self, uid, name):
        supabase.table("users").insert({"id": uid, "name": name, "balance": 10000, "trades": [], "signals": 0}).execute()
        return self.get(uid)
    def add_trade(self, uid, trade):
        u = self.get(uid)
        if u:
            trades = u.get("trades", []) + [trade]
            supabase.table("users").update({"trades": trades, "balance": u["balance"] + trade.get("pnl", 0)}).eq("id", uid).execute()

db = DB()

# Мульти-источник данных
async def fetch_prices():
    # Пробуем Bybit
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=3) as r:
                data = await r.json()
                prices = {}
                for t in data['result']['list'][:15]:
                    prices[t['symbol']] = {'price': float(t['lastPrice']), 'chg': float(t.get('price24hPcnt',0))*100}
                return prices
    except: pass
    
    # Пробуем CoinGecko
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,ripple&vs_currencies=usd&include_24hr_change=true", timeout=3) as r:
                data = await r.json()
                mapping = {'bitcoin': 'BTC/USDT', 'ethereum': 'ETH/USDT', 'solana': 'SOL/USDT', 'binancecoin': 'BNB/USDT', 'ripple': 'XRP/USDT'}
                prices = {}
                for coin, sym in mapping.items():
                    if coin in data:
                        prices[sym] = {'price': data[coin]['usd'], 'chg': data[coin].get('usd_24h_change', 0)}
                return prices
    except: pass
    
    # Fallback
    return {
        'BTC/USDT': {'price': 80000, 'chg': 2.5},
        'ETH/USDT': {'price': 4000, 'chg': -1.2},
        'SOL/USDT': {'price': 150, 'chg': 5.0},
        'BNB/USDT': {'price': 600, 'chg': 1.0},
        'XRP/USDT': {'price': 0.50, 'chg': -0.5},
    }

def get_signal(prices):
    if not prices: return None
    sym, d = random.choice(list(prices.items()))
    return {"s": sym, "p": d['price'], "c": d['chg'], "sg": "BUY" if d['chg']<-2 else ("SELL" if d['chg']>2 else "HOLD"), "cf": min(95, 50+abs(d['chg'])*5)}

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class St(StatesGroup): name = State()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Дашборд"), KeyboardButton(text="Сигналы")],
        [KeyboardButton(text="Портфель"), KeyboardButton(text="Рынок")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    u = db.get(msg.from_user.id)
    if u: await msg.answer(f"{u['name']} | Баланс: {u['balance']:,.0f}", reply_markup=menu())
    else: await msg.answer("Имя:"); await state.set_state(St.name)

@dp.message(St.name)
async def name(msg: types.Message, state: FSMContext):
    db.create(msg.from_user.id, msg.text.strip()); await state.clear()
    await msg.answer("Готово", reply_markup=menu())

@dp.message(F.text == "Дашборд")
async def dash(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    await msg.answer(f"{u['name']} | {u['balance']:,.0f} | Сделок: {len(u.get('trades',[]))}", reply_markup=menu())

@dp.message(F.text == "Сигналы")
async def signals(msg: types.Message):
    m = await msg.answer("Загрузка...")
    prices = await fetch_prices()
    s = get_signal(prices)
    if not s: return await m.edit_text("Нет данных")
    text = f"{s['s']} | {s['p']:.2f} | {s['c']:+.1f}% | {s['sg']} | {s['cf']:.0f}%"
    try: supabase.table("users").update({"signals": supabase.table("users").select("signals").eq("id", msg.from_user.id).execute().data[0].get("signals",0)+1}).eq("id", msg.from_user.id).execute()
    except: pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить", callback_data=f"b_{s['s']}_{s['p']}")],
        [InlineKeyboardButton(text="Обновить", callback_data="ref")],
    ])
    await m.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("b_"))
async def buy(cb: types.CallbackQuery):
    _, sym, price = cb.data.split("_")
    u = db.get(cb.from_user.id)
    if not u: return await cb.answer("/start")
    amt = min(u["balance"]*0.1, 500)
    pnl = amt * random.uniform(-0.05, 0.08)
    db.add_trade(cb.from_user.id, {"s": sym, "a": amt, "pnl": pnl})
    u2 = db.get(cb.from_user.id)
    await cb.answer(f"{amt:.0f}")
    await cb.message.answer(f"{sym} | {amt:.0f} | PnL: {pnl:+.0f} | {u2['balance']:,.0f}")

@dp.callback_query(F.data=="ref")
async def ref(cb: types.CallbackQuery): await signals(cb.message)

@dp.message(F.text == "Портфель")
async def portf(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u or not u.get("trades"): return await msg.answer("Нет сделок")
    text = "\n".join([f"{x['s']}: {x.get('pnl',0):+.0f}" for x in u["trades"][-5:]])
    await msg.answer(f"Портфель\n{text}\n{u['balance']:,.0f}", reply_markup=menu())

@dp.message(F.text == "Рынок")
async def market(msg: types.Message):
    prices = await fetch_prices()
    text = "\n".join([f"{s}: {d['price']:.2f} ({d['chg']:+.1f}%)" for s,d in list(prices.items())[:10]])
    await msg.answer(f"Рынок\n{text}", reply_markup=menu())

async def main():
    print("SST TRADER | Multi-source")
    await dp.start_polling(bot)

asyncio.run(main())
