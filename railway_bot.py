import asyncio, logging, random, json, os, time, hashlib
from datetime import datetime, timedelta
from collections import defaultdict, deque
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from supabase import create_client
SUPABASE_URL = "https://throkijrjphuuevnofoi.supabase.co"
SUPABASE_KEY = "sb_publishable_5oukEO6ho0wCH0NV9zuvBw_RKRCvl4Z"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")
STABLECOINS = {"USDCUSDT","USDTUSDT","FDUSDUSDT","BUSDUSDT","DAIUSDT","TUSDUSDT","USDC","USDT"}

class TokenDiscovery:
    def __init__(self):
        self.known = set()
        self.stats = defaultdict(int)
    
    async def fetch_all(self):
        prices = {}
        sources = [self._bybit, self._coingecko, self._binance, self._mexc]
        for src in sources:
            try:
                data = await src()
                if data:
                    for k, v in data.items():
                        if k not in self.known: self.known.add(k); self.stats[src.__name__] += 1
                        prices[k] = v
            except: pass
        return prices if prices else self._fallback()
    
    async def _bybit(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=4) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('price24hPcnt',0))*100, 'vol': float(t.get('volume24h',0)), 'src': 'bybit'} for t in (await r.json())['result']['list'][:30] if t['symbol'] not in STABLECOINS}
        except: return {}
    
    async def _coingecko(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=50", timeout=4) as r:
                    return {c['symbol'].upper()+'/USDT': {'price': c['current_price'], 'chg': c.get('price_change_percentage_24h',0), 'vol': c.get('total_volume',0), 'src': 'coingecko'} for c in await r.json()}
        except: return {}
    
    async def _binance(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.binance.com/api/v3/ticker/24hr", timeout=4) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('priceChangePercent',0)), 'vol': float(t.get('quoteVolume',0)), 'src': 'binance'} for t in (await r.json())[:30] if t['symbol'].endswith('USDT')}
        except: return {}
    
    async def _mexc(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=3) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('priceChangePercent',0)), 'vol': float(t.get('quoteVolume',0)), 'src': 'mexc'} for t in (await r.json())[:20] if t['symbol'].endswith('USDT')}
        except: return {}
    
    def _fallback(self):
        return {s: {'price': p, 'chg': c, 'vol': v, 'src': 'fallback'} for s, p, c, v in [
            ('BTC/USDT', 80500, 2.5, 30e9), ('ETH/USDT', 4100, -1.2, 15e9),
            ('SOL/USDT', 155, 5.0, 3e9), ('BNB/USDT', 610, 1.0, 2e9),
            ('DOGE/USDT', 0.12, 8.0, 800e6), ('SUI/USDT', 1.80, 18.0, 600e6),
            ('SEI/USDT', 0.45, 22.0, 300e6), ('APT/USDT', 9.50, 12.0, 400e6),
        ]}

discovery = TokenDiscovery()

class DeepQLearning:
    def __init__(self):
        self.q = defaultdict(lambda: np.zeros(3))
        self.memory = deque(maxlen=10000)
        self.lr = 0.001; self.gamma = 0.95; self.eps = 0.1
    
    def state(self, price, chg, vol, risk):
        return f"{int(price//1000)}_{int(chg//3)}_{int(vol//1e6)}_{risk}"
    
    def predict(self, state):
        if random.random() < self.eps: return random.randint(0, 2)
        return int(np.argmax(self.q[state]))
    
    def learn(self, s, a, r, ns, done):
        target = r if done else r + self.gamma * np.max(self.q[ns])
        self.q[s][a] += self.lr * (target - self.q[s][a])

ai = DeepQLearning()

STRATEGIES = {
    "aggressive": {"name": "Агрессивная", "position": 20, "stop": 3, "target": 10},
    "moderate": {"name": "Умеренная", "position": 10, "stop": 5, "target": 15},
    "conservative": {"name": "Консервативная", "position": 5, "stop": 2, "target": 5},
    "scalping": {"name": "Скальпинг", "position": 5, "stop": 1, "target": 2},
    "trend": {"name": "Трендовая", "position": 15, "stop": 7, "target": 25},
    "ai": {"name": "AI Стратегия", "position": 15, "stop": 5, "target": 20},
}

class DB:
    def get(self, uid):
        try:
            r = supabase.table("users").select("*").eq("id", uid).execute()
            return r.data[0] if r.data else None
        except: return None
    def create(self, uid, name):
        try:
            supabase.table("users").insert({
                "id": uid, "name": name, "balance": 10000, "sub": "vip",
                "auto_trading": 0, "strategy": "ai", "reinvest": 50,
                "risk": "medium", "trades": [], "positions": [], "signals": 0
            }).execute()
        except: pass
        return self.get(uid)
    def update(self, uid, data):
        try: supabase.table("users").update(data).eq("id", uid).execute()
        except: pass
    def add_trade(self, uid, t):
        u = self.get(uid)
        if u:
            trades = u.get("trades", []) + [t]
            self.update(uid, {"trades": trades, "balance": u["balance"] + t.get("pnl", 0)})
    def add_position(self, uid, p):
        u = self.get(uid)
        if u:
            positions = u.get("positions", []) + [p]
            self.update(uid, {"positions": positions})
    def get_all(self):
        try:
            r = supabase.table("users").select("*").execute()
            return r.data or []
        except: return []

db = DB()

def get_signals(prices, sig_type="signals"):
    s = sorted(prices.items(), key=lambda x: x[1]["chg"], reverse=True)
    if sig_type == "signals": return [(k, v) for k, v in s if v["chg"] > 2][:10]
    if sig_type == "pumps": return [(k, v) for k, v in s if v["chg"] > 15][:10]
    if sig_type == "vip": return [(k, v) for k, v in s if v["chg"] > 3 and v["vol"] > 10e6][:5]
    if sig_type == "sniper":
        sc = [(k, v, v["chg"] * v["vol"]) for k, v in s[:30]]
        sc.sort(key=lambda x: x[2], reverse=True)
        return [(k, v) for k, v, _ in sc[:1]]
    if sig_type == "top20":
        return sorted(prices.items(), key=lambda x: x[1]["vol"], reverse=True)[:20]
    return []

async def auto_trading_loop():
    while True:
        try:
            prices = await discovery.fetch_all()
            for user in db.get_all():
                if not user.get("auto_trading"): continue
                strategy = user.get("strategy", "ai")
                risk = user.get("risk", "medium")
                balance = user.get("balance", 10000)
                positions = user.get("positions", [])
                open_pos = [p for p in positions if p.get("status") == "open"]
                if len(open_pos) >= 5: continue
                
                cfg = STRATEGIES.get(strategy, STRATEGIES["ai"])
                candidates = []
                if strategy in ["aggressive", "ai"]: candidates += get_signals(prices, "pumps")[:3] + get_signals(prices, "sniper")
                if strategy in ["moderate", "ai"]: candidates += get_signals(prices, "signals")[:2]
                if strategy == "conservative": candidates += get_signals(prices, "vip")[:2]
                
                seen = set(); uniq = []
                for k, v in candidates:
                    if k not in seen: seen.add(k); uniq.append((k, v))
                
                rp = {"low": cfg["position"]*0.5, "medium": cfg["position"], "high": cfg["position"]*1.5}[risk]
                amt = balance * rp / 100
                
                for k, v in uniq[:2]:
                    target = v["price"] * (1 + cfg["target"]/100)
                    stop = v["price"] * (1 - cfg["stop"]/100)
                    pos = {"token": k, "entry_price": v["price"], "amount": amt, "target": target, "stop_loss": stop, "current_price": v["price"], "pnl": 0, "status": "open", "source": "auto", "strategy": strategy, "timestamp": datetime.now().isoformat()}
                    db.add_position(user["id"], pos)
                
                updated = []
                for p in positions:
                    if p.get("status") != "open": updated.append(p); continue
                    cp = prices.get(p["token"], {}).get("price", p["entry_price"])
                    p["current_price"] = cp; p["pnl"] = (cp - p["entry_price"]) * p["amount"] / p["entry_price"]
                    if cp >= p["target"] or cp <= p["stop_loss"]:
                        p["status"] = "closed"
                        db.add_trade(user["id"], {"token": p["token"], "type": "SELL", "amount": p["amount"], "price": cp, "pnl": p["pnl"], "source": "auto", "strategy": p.get("strategy", "ai"), "timestamp": datetime.now().isoformat()})
                    updated.append(p)
                db.update(user["id"], {"positions": updated})
        except Exception as e:
            logging.error(f"Auto-trading: {e}")
        await asyncio.sleep(45)

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
        [KeyboardButton(text="📡 Торговля"), KeyboardButton(text="📊 Аналитика")],
        [KeyboardButton(text="🤖 Автотрейдинг"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="⚙️ Настройки")],
    ], resize_keyboard=True)

def trade_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📡 Сигналы"), KeyboardButton(text="🎯 Снайпер")],
        [KeyboardButton(text="🚀 Пампы"), KeyboardButton(text="👑 VIP сигналы")],
        [KeyboardButton(text="💼 Портфель"), KeyboardButton(text="📋 Сделки")],
        [KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)

def analytics_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📈 Альфа"), KeyboardButton(text="📉 Бетта")],
        [KeyboardButton(text="📊 График"), KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    u = db.get(msg.from_user.id)
    if u: await msg.answer(f"👋 {u['name']}\n💰 {u['balance']:,.0f}\n🤖 Авто: {'🟢' if u.get('auto_trading') else '🔴'}", reply_markup=main_kb())
    else: await msg.answer("🚀 SST TRADER v9.0\n\nВведите имя:"); await state.set_state(St.name)

@dp.message(St.name)
async def name(msg: types.Message, state: FSMContext):
    db.create(msg.from_user.id, msg.text.strip()); await state.clear()
    await msg.answer("✅ Готово! VIP доступ\n$10,000 на балансе", reply_markup=main_kb())

@dp.message(F.text == "📡 Торговля")
async def trade(msg: types.Message): await msg.answer("📡 Торговля", reply_markup=trade_kb())
@dp.message(F.text == "📊 Аналитика")
async def analytics(msg: types.Message): await msg.answer("📊 Аналитика", reply_markup=analytics_kb())

@dp.message(F.text == "🤖 Автотрейдинг")
async def auto_toggle(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: db.create(msg.from_user.id, "Trader"); u = db.get(msg.from_user.id)
    new = 0 if u.get("auto_trading") else 1
    db.update(msg.from_user.id, {"auto_trading": new})
    await msg.answer(f"🤖 Автотрейдинг: {'🟢 ВКЛ' if new else '🔴 ВЫКЛ'}", reply_markup=main_kb())

@dp.message(F.text == "👤 Профиль")
async def profile(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: db.create(msg.from_user.id, "Trader"); u = db.get(msg.from_user.id)
    t = u.get("trades", [])
    pnl = sum(x.get("pnl",0) for x in t)
    w = sum(1 for x in t if x.get("pnl",0)>0)
    await msg.answer(f"👤 {u['name']}\n💰 {u['balance']:,.0f}\n📈 PnL: {pnl:+,.0f}\n✅ Win: {w}/{len(t)}\n📊 {u.get('strategy','ai')}\n🛡️ {u.get('risk','medium')}", reply_markup=main_kb())

@dp.message(F.text == "⚙️ Настройки")
async def settings(msg: types.Message):
    await msg.answer("⚙️ Настройки", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Стратегия", callback_data="strat")],
        [InlineKeyboardButton(text="🛡️ Риск", callback_data="risk")],
    ]))

@dp.callback_query(F.data == "strat")
async def strat_cb(cb: types.CallbackQuery):
    await cb.message.edit_text("Стратегия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s["name"], callback_data=f"s_{k}") for k, s in list(STRATEGIES.items())[:3]],
        [InlineKeyboardButton(text=s["name"], callback_data=f"s_{k}") for k, s in list(STRATEGIES.items())[3:]],
    ]))

@dp.callback_query(F.data.startswith("s_"))
async def strat_set(cb: types.CallbackQuery):
    s = cb.data.split("_")[1]
    db.update(cb.from_user.id, {"strategy": s})
    await cb.answer(f"✅ {STRATEGIES[s]['name']}")

@dp.callback_query(F.data == "risk")
async def risk_cb(cb: types.CallbackQuery):
    await cb.message.edit_text("Риск:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Низкий", callback_data="r_low")],
        [InlineKeyboardButton(text=f"Средний", callback_data="r_medium")],
        [InlineKeyboardButton(text=f"Высокий", callback_data="r_high")],
    ]))

@dp.callback_query(F.data.startswith("r_"))
async def risk_set(cb: types.CallbackQuery):
    r = cb.data.split("_")[1]
    db.update(cb.from_user.id, {"risk": r})
    await cb.answer(f"✅ {r}")

@dp.message(F.text == "🔙 Назад")
async def back(msg: types.Message): await msg.answer("Меню", reply_markup=main_kb())

async def send_signals(msg, prices, stype, title):
    s = get_signals(prices, stype)
    if not s: return await msg.answer(f"{title}: нет сигналов")
    text = f"{title}\n\n"
    kb = []
    for sym, data in s[:5]:
        text += f"{'🟢' if data['chg']>0 else '🔴'} {sym}: ${data['price']:.4f} ({data['chg']:+.1f}%)\n"
        kb.append([InlineKeyboardButton(text=f"BUY {sym}", callback_data=f"buy_{sym}_{data['price']}")])
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.message(F.text == "📡 Сигналы")
async def sig(msg: types.Message): await send_signals(msg, await discovery.fetch_all(), "signals", "📡 Сигналы")
@dp.message(F.text == "🎯 Снайпер")
async def snipe(msg: types.Message): await send_signals(msg, await discovery.fetch_all(), "sniper", "🎯 Снайпер")
@dp.message(F.text == "🚀 Пампы")
async def pump(msg: types.Message): await send_signals(msg, await discovery.fetch_all(), "pumps", "🚀 Пампы")
@dp.message(F.text == "👑 VIP сигналы")
async def vip(msg: types.Message): await send_signals(msg, await discovery.fetch_all(), "vip", "👑 VIP сигналы")

@dp.message(F.text == "💼 Портфель")
async def portf(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: db.create(msg.from_user.id, "Trader"); u = db.get(msg.from_user.id)
    pos = [p for p in u.get("positions", []) if p.get("status") == "open"]
    if not pos: return await msg.answer("💼 Нет открытых позиций")
    text = "💼 Портфель\n\n"
    for p in pos[:5]:
        text += f"{'🟢' if p.get('pnl',0)>0 else '🔴'} {p['token']}: {p.get('pnl',0):+.2f}\n"
    await msg.answer(text)

@dp.message(F.text == "📋 Сделки")
async def trades(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: db.create(msg.from_user.id, "Trader"); u = db.get(msg.from_user.id)
    t = u.get("trades", [])
    if not t: return await msg.answer("📋 Нет сделок")
    text = f"📋 Сделки ({len(t)})\n\n"
    for x in t[-10:]:
        text += f"{'🤖' if x.get('source')=='auto' else '👤'} {x['token']}: ${x.get('pnl',0):+,.2f}\n"
    await msg.answer(text)

@dp.message(F.text == "📈 Альфа")
async def alpha(msg: types.Message):
    prices = await discovery.fetch_all()
    avg = sum(d["chg"] for d in prices.values()) / max(1, len(prices))
    sentiment = "Бычий 🟢" if avg > 1 else ("Медвежий 🔴" if avg < -1 else "Нейтральный ⚪")
    await msg.answer(f"📈 Альфа\n{sentiment}\nСреднее: {avg:+.1f}%\nПар: {len(prices)}")

@dp.message(F.text == "📉 Бетта")
async def beta(msg: types.Message):
    prices = await discovery.fetch_all()
    s = get_signals(prices, "signals")[:5]
    text = "📉 Бетта\n\n"
    for sym, data in s:
        text += f"{sym}: BUY → TP: {data['price']*1.05:.4f}\n"
    await msg.answer(text)

@dp.message(F.text == "📊 График")
async def chart(msg: types.Message):
    prices = await discovery.fetch_all()
    top5 = sorted(prices.items(), key=lambda x: x[1]["vol"], reverse=True)[:5]
    text = "📊 Топ-5\n\n"
    for sym, data in top5:
        bar = "█" * int(abs(data["chg"]))
        text += f"{sym}: ${data['price']:.2f} {bar} {data['chg']:+.1f}%\n"
    await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def buy(cb: types.CallbackQuery):
    _, sym, price = cb.data.split("_")
    u = db.get(cb.from_user.id)
    if not u: return await cb.answer("/start")
    amt = min(u["balance"] * 0.1, 500)
    pnl = amt * random.uniform(-0.05, 0.08)
    db.add_trade(cb.from_user.id, {"token": sym, "type": "BUY", "amount": amt, "price": float(price), "pnl": pnl, "source": "manual", "timestamp": datetime.now().isoformat()})
    await cb.answer(f"${amt:.0f}")
    await cb.message.answer(f"✅ {sym}\nPnL: {pnl:+.0f}")

async def main():
    print("🚀 SST TRADER v9.0")
    asyncio.create_task(auto_trading_loop())
    await dp.start_polling(bot)

asyncio.run(main())


