import asyncio, logging, random, json, os
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")

class DB:
    def __init__(self):
        self.f = Path("data/users.json")
        self.f.parent.mkdir(exist_ok=True)
        self.users = json.loads(self.f.read_text()) if self.f.exists() else {}
    def save(self): self.f.write_text(json.dumps(self.users, indent=2))
    def get(self, uid): return self.users.get(str(uid))
    def create(self, uid, name):
        u = {"name": name, "balance": 10000, "trades": [], "signals": 0}
        self.users[str(uid)] = u; self.save(); return u
    def add(self, uid, t):
        u = self.users.get(str(uid))
        if u: u["trades"].append(t); u["balance"] += t.get("pnl",0); self.save()

db = DB()

class BybitLive:
    def __init__(self): self.prices = {}
    async def fetch(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=5) as r:
                    for t in (await r.json())["result"]["list"][:20]:
                        self.prices[t["symbol"]] = {"price": float(t["lastPrice"]), "chg": float(t.get("price24hPcnt",0))*100}
                    return True
        except: return False
    def sig(self):
        if not self.prices: return None
        sym, d = random.choice(list(self.prices.items()))
        return {"s": sym, "p": d["price"], "c": d["chg"], "sg": "BUY" if d["chg"]<-2 else ("SELL" if d["chg"]>2 else "HOLD"), "cf": min(95, 50+abs(d["chg"])*5)}

bybit = BybitLive()

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
    t = u.get("trades",[]); w = sum(1 for x in t if x.get("pnl",0)>0)
    await msg.answer(f"{u['name']} | {u['balance']:,.0f} | Сделок: {len(t)}", reply_markup=menu())

@dp.message(F.text == "Сигналы")
async def signals(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    m = await msg.answer("Загрузка...")
    await bybit.fetch()
    s = bybit.sig()
    if not s: return await m.edit_text("Нет данных")
    text = f"{s['s']} | {s['p']:.4f} | {s['c']:+.1f}% | {s['sg']} | {s['cf']:.0f}%"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить", callback_data=f"b_{s['s']}_{s['p']}")],
        [InlineKeyboardButton(text="Обновить", callback_data="ref")],
    ])
    u["signals"] = u.get("signals",0)+1; db.save()
    await m.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("b_"))
async def buy(cb: types.CallbackQuery):
    _, sym, price = cb.data.split("_")
    u = db.get(cb.from_user.id)
    if not u: return await cb.answer("/start")
    amt = min(u["balance"]*0.1, 500)
    pnl = amt * random.uniform(-0.05, 0.08)
    db.add(cb.from_user.id, {"s": sym, "a": amt, "pnl": pnl})
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
    await bybit.fetch()
    text = "\n".join([f"{s}: {d['price']:.2f} ({d['chg']:+.1f}%)" for s,d in list(bybit.prices.items())[:10]])
    await msg.answer(f"Рынок Bybit\n{text}", reply_markup=menu())

async def main():
    print("SST TRADER | Railway Ready")
    await dp.start_polling(bot)

asyncio.run(main())
