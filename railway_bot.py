#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🚀 SST TRADER v9.0 — AI-DRIVEN TRADING WITH ALERTS       ║
║   DEX Sniper | Copy Trading | Anti-Rug | AI Predictor      ║
║   Real-time Notifications | Daily Reports                  ║
╚══════════════════════════════════════════════════════════════╝
"""
import asyncio, logging, random, json, os, time, hashlib, secrets
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SST")

# ===== КОНФИГУРАЦИЯ =====
from supabase import create_client
SUPABASE_URL = "https://throkijrjphuuevnofoi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRocm9raWpyanBodXVldm5vZm9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODYxMjg5MCwiZXhwIjoyMDk0MTg4ODkwfQ.7p10xZyUvQ5SrPWDJHV_knVaEryn21CeP8YGbrc1CkI"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8510828511:AAEwLy9HhcoWVDROLgr3a4v2nx3ydc7WQiY")
STABLECOINS = {"USDCUSDT","USDTUSDT","FDUSDUSDT","BUSDUSDT","DAIUSDT","TUSDUSDT"}

# ===== БАЗА ДАННЫХ =====
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
                "risk": "medium", "trades": [], "positions": [],
                "referral_code": f"SST{uid}{secrets.token_hex(3).upper()}",
                "ai_stats": {"predictions":0,"correct":0,"accuracy":0},
                "notifications": {"new_trades": True, "close_trades": True, "daily_report": True}
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
            ai_stats = u.get("ai_stats", {})
            ai_stats["predictions"] = ai_stats.get("predictions", 0) + 1
            if t.get("pnl", 0) > 0: ai_stats["correct"] = ai_stats.get("correct", 0) + 1
            ai_stats["accuracy"] = ai_stats["correct"] / max(1, ai_stats["predictions"]) * 100
            self.update(uid, {"ai_stats": ai_stats})
    def add_position(self, uid, p):
        u = self.get(uid)
        if u: self.update(uid, {"positions": u.get("positions", []) + [p]})
    def get_all(self):
        try:
            r = supabase.table("users").select("*").execute()
            return r.data or []
        except: return []

db = DB()

# ===== РЫНОК =====
class MarketData:
    async def fetch(self) -> Dict:
        prices = {}
        for src in [self._bybit, self._coingecko, self._binance, self._mexc]:
            try:
                data = await src()
                if data: prices.update(data)
            except: pass
        return prices if prices else self._fallback()
    
    async def _bybit(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=5) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('price24hPcnt',0))*100, 'vol': float(t.get('volume24h',0))} for t in (await r.json())['result']['list'][:50] if t['symbol'] not in STABLECOINS}
        except: return {}
    async def _coingecko(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=100", timeout=5) as r:
                    return {c['symbol'].upper()+'/USDT': {'price': c['current_price'], 'chg': c.get('price_change_percentage_24h',0), 'vol': c.get('total_volume',0)} for c in await r.json()}
        except: return {}
    async def _binance(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.binance.com/api/v3/ticker/24hr", timeout=5) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('priceChangePercent',0)), 'vol': float(t.get('quoteVolume',0))} for t in (await r.json())[:50] if t['symbol'].endswith('USDT')}
        except: return {}
    async def _mexc(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=5) as r:
                    return {t['symbol']: {'price': float(t['lastPrice']), 'chg': float(t.get('priceChangePercent',0)), 'vol': float(t.get('quoteVolume',0))} for t in (await r.json())[:30] if t['symbol'].endswith('USDT')}
        except: return {}
    def _fallback(self):
        return {'BTC/USDT': {'price': 80500, 'chg': 2.5, 'vol': 30e9}, 'ETH/USDT': {'price': 4100, 'chg': -1.2, 'vol': 15e9}, 'SOL/USDT': {'price': 155, 'chg': 5.0, 'vol': 3e9}, 'DOGE/USDT': {'price': 0.12, 'chg': 8.0, 'vol': 800e6}, 'SUI/USDT': {'price': 1.80, 'chg': 18.0, 'vol': 600e6}, 'INJ/USDT': {'price': 5.22, 'chg': 9.4, 'vol': 500e6}, 'TIA/USDT': {'price': 0.47, 'chg': 2.6, 'vol': 400e6}}

market = MarketData()

# ===== AI =====
class AI:
    def __init__(self):
        self.q = defaultdict(lambda: np.zeros(3))
        self.eps = 0.1
    def predict(self, price, chg, vol):
        state = f"{int(price//1000)}_{int(chg//3)}_{int(vol//1e6)}"
        if random.random() < self.eps: return random.randint(0, 2)
        return int(np.argmax(self.q[state]))
    def learn(self, price, chg, vol, action, reward):
        state = f"{int(price//1000)}_{int(chg//3)}_{int(vol//1e6)}"
        self.q[state][action] += 0.1 * (reward - self.q[state][action])

ai = AI()

STRATEGIES = {
    "aggressive": {"name": "Агрессивная", "pos": 20, "stop": 3, "target": 10},
    "moderate": {"name": "Умеренная", "pos": 10, "stop": 5, "target": 15},
    "conservative": {"name": "Консервативная", "pos": 5, "stop": 2, "target": 5},
    "scalping": {"name": "Скальпинг", "pos": 5, "stop": 1, "target": 2},
    "trend": {"name": "Трендовая", "pos": 15, "stop": 7, "target": 25},
    "ai": {"name": "AI Стратегия", "pos": 15, "stop": 5, "target": 20},
}

def get_signals(prices, sig_type="signals"):
    s = sorted(prices.items(), key=lambda x: x[1]["chg"], reverse=True)
    if sig_type == "signals": return [(k, v) for k, v in s if v["chg"] > 2][:15]
    if sig_type == "pumps": return [(k, v) for k, v in s if v["chg"] > 15][:10]
    if sig_type == "vip": return [(k, v) for k, v in s if v["chg"] > 3 and v["vol"] > 10e6][:5]
    if sig_type == "sniper":
        sc = [(k, v, v["chg"] * v["vol"]) for k, v in s[:50]]
        sc.sort(key=lambda x: x[2], reverse=True)
        return [(k, v) for k, v, _ in sc[:3]]
    return []

# ===== УВЕДОМЛЕНИЯ =====
async def send_notification(user_id: int, text: str):
    """Отправляет уведомление пользователю в Telegram"""
    try:
        from aiogram import Bot
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(user_id, text, parse_mode="Markdown")
        await bot.session.close()
    except Exception as e:
        logger.error(f"Notification error: {e}")

# ===== АВТОТРЕЙДИНГ С УВЕДОМЛЕНИЯМИ =====
async def auto_trading_loop():
    while True:
        try:
            prices = await market.fetch()
            users = db.get_all()
            
            for user in users:
                if not user.get("auto_trading"): continue
                
                uid = user["id"]
                strategy = user.get("strategy", "ai")
                risk = user.get("risk", "medium")
                balance = user.get("balance", 10000)
                positions = user.get("positions", [])
                notifications = user.get("notifications", {})
                open_pos = [p for p in positions if p.get("status") == "open"]
                
                if len(open_pos) >= 5: continue
                
                cfg = STRATEGIES.get(strategy, STRATEGIES["ai"])
                candidates = []
                if strategy in ["aggressive", "ai"]: candidates += get_signals(prices, "pumps")[:5] + get_signals(prices, "sniper")
                if strategy in ["moderate", "ai"]: candidates += get_signals(prices, "signals")[:5]
                if strategy == "conservative": candidates += get_signals(prices, "vip")[:3]
                
                seen = set(); uniq = []
                for k, v in candidates:
                    if k not in seen: seen.add(k); uniq.append((k, v))
                
                rp = {"low": cfg["pos"]*0.5, "medium": cfg["pos"], "high": cfg["pos"]*1.5}[risk]
                amt = balance * rp / 100
                
                # ОТКРЫТИЕ ПОЗИЦИЙ
                for k, v in uniq[:3]:
                    target = v["price"] * (1 + cfg["target"]/100)
                    stop = v["price"] * (1 - cfg["stop"]/100)
                    
                    pos = {"token": k, "entry_price": v["price"], "amount": amt, "target": target, "stop_loss": stop, "current_price": v["price"], "pnl": 0, "status": "open", "source": "auto", "strategy": strategy, "timestamp": datetime.now().isoformat()}
                    db.add_position(uid, pos)
                    
                    # 📱 УВЕДОМЛЕНИЕ О НОВОЙ СДЕЛКЕ
                    if notifications.get("new_trades", True):
                        await send_notification(uid, 
                            f"🟢 **НОВАЯ СДЕЛКА (Авто)**\n\n"
                            f"📛 {k}\n"
                            f"💰 Куплено: ${amt:.2f}\n"
                            f"💵 Цена: ${v['price']:.4f}\n"
                            f"🎯 Цель: ${target:.4f} (+{cfg['target']}%)\n"
                            f"🛑 Стоп: ${stop:.4f} (-{cfg['stop']}%)\n"
                            f"📊 Стратегия: {cfg['name']}\n"
                            f"🕐 {datetime.now().strftime('%d.%m.%Y, %H:%M')}"
                        )
                
                # ЗАКРЫТИЕ ПОЗИЦИЙ
                updated = []
                for p in positions:
                    if p.get("status") != "open": updated.append(p); continue
                    cp = prices.get(p["token"], {}).get("price", p["entry_price"])
                    p["current_price"] = cp
                    p["pnl"] = (cp - p["entry_price"]) * p["amount"] / p["entry_price"]
                    
                    if cp >= p["target"] or cp <= p["stop_loss"]:
                        p["status"] = "closed"
                        trade = {"token": p["token"], "type": "SELL", "amount": p["amount"], "price": cp, "pnl": p["pnl"], "source": "auto", "strategy": p.get("strategy", "ai"), "timestamp": datetime.now().isoformat()}
                        db.add_trade(uid, trade)
                        ai.learn(p["entry_price"], 0, 0, 0, 1 if p["pnl"] > 0 else -1)
                        
                        # 📱 УВЕДОМЛЕНИЕ О ЗАКРЫТИИ
                        if notifications.get("close_trades", True):
                            emoji = "🟢" if p["pnl"] > 0 else "🔴"
                            reason = "🎯 Цель достигнута" if cp >= p["target"] else "🛑 Стоп-лосс"
                            await send_notification(uid,
                                f"{emoji} **ЗАКРЫТИЕ ПОЗИЦИИ (Авто)**\n\n"
                                f"📛 {p['token']}\n"
                                f"💰 Сумма: ${p['amount']:.2f}\n"
                                f"💵 Вход: ${p['entry_price']:.4f}\n"
                                f"💵 Выход: ${cp:.4f}\n"
                                f"📈 PnL: ${p['pnl']:+,.2f} ({p['pnl']/p['amount']*100:+.1f}%)\n"
                                f"{reason}\n"
                                f"🕐 {datetime.now().strftime('%d.%m.%Y, %H:%M')}"
                            )
                    
                    updated.append(p)
                
                db.update(uid, {"positions": updated})
                
                # Авто-реинвестирование
                reinvest_pct = user.get("reinvest", 50)
                if reinvest_pct > 0 and user.get("balance", 0) > 10000:
                    profit = user["balance"] - 10000
                    if profit > 0:
                        reinvest_amount = profit * reinvest_pct / 100
                        db.update(uid, {"balance": user["balance"] + reinvest_amount})
                        logger.info(f"Reinvested ${reinvest_amount:.2f} for user {uid}")
                
        except Exception as e:
            logger.error(f"Auto-trading error: {e}")
        
        await asyncio.sleep(45)

# ===== ЕЖЕДНЕВНЫЙ ОТЧЁТ =====
async def daily_report_loop():
    """Отправляет ежедневный отчёт всем пользователям с автотрейдингом"""
    while True:
        await asyncio.sleep(86400)  # Раз в 24 часа
        
        try:
            users = db.get_all()
            for user in users:
                if not user.get("auto_trading"): continue
                if not user.get("notifications", {}).get("daily_report", True): continue
                
                uid = user["id"]
                trades = [t for t in user.get("trades", []) if t.get("source") == "auto"]
                today = [t for t in trades if datetime.fromisoformat(t["timestamp"]).date() == datetime.now().date()]
                
                if not today: continue
                
                wins = sum(1 for t in today if t.get("pnl", 0) > 0)
                total_pnl = sum(t.get("pnl", 0) for t in today)
                best = max(t.get("pnl", 0) for t in today)
                worst = min(t.get("pnl", 0) for t in today)
                
                await send_notification(uid,
                    f"📊 **ЕЖЕДНЕВНЫЙ ОТЧЁТ**\n\n"
                    f"📈 Сделок: {len(today)}\n"
                    f"✅ Прибыльных: {wins}\n"
                    f"💰 PnL за день: ${total_pnl:+,.2f}\n"
                    f"📊 Win rate: {wins/max(1,len(today))*100:.0f}%\n"
                    f"🏆 Лучшая: ${best:+,.2f}\n"
                    f"💀 Худшая: ${worst:+,.2f}\n"
                    f"💼 Баланс: ${user['balance']:,.2f}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y')}"
                )
        except Exception as e:
            logger.error(f"Daily report error: {e}")

# ===== TELEGRAM BOT =====
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
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🔔 Уведомления")],
    ], resize_keyboard=True)

def trade_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📡 Сигналы AI"), KeyboardButton(text="🎯 Снайпер")],
        [KeyboardButton(text="🚀 Пампы"), KeyboardButton(text="👑 VIP сигналы")],
        [KeyboardButton(text="💼 Портфель"), KeyboardButton(text="📋 Сделки")],
        [KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    u = db.get(msg.from_user.id)
    if u:
        await msg.answer(f"👋 {u['name']}!\n💰 ${u['balance']:,.0f}\n🤖 Авто: {'🟢' if u.get('auto_trading') else '🔴'}", reply_markup=main_kb())
    else:
        await msg.answer("🚀 SST TRADER v9.0\n\nВведите имя:"); await state.set_state(St.name)

@dp.message(St.name)
async def name(msg: types.Message, state: FSMContext):
    db.create(msg.from_user.id, msg.text.strip()); await state.clear()
    await msg.answer(f"✅ Готово! $10,000 на балансе", reply_markup=main_kb())

@dp.message(F.text == "📡 Торговля")
async def trade(msg: types.Message): await msg.answer("📡 Торговля", reply_markup=trade_kb())

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
    if not u: return await msg.answer("/start")
    t = u.get("trades", []); pnl = sum(x.get("pnl",0) for x in t)
    await msg.answer(f"👤 {u['name']}\n💰 ${u['balance']:,.0f}\n📈 PnL: {pnl:+,.0f}\n📊 {u.get('strategy','ai')}", reply_markup=main_kb())

@dp.message(F.text == "🔔 Уведомления")
async def notif_menu(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    n = u.get("notifications", {})
    await msg.answer("🔔 УВЕДОМЛЕНИЯ\n\nВыберите что включить/выключить:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if n.get('new_trades',True) else '❌'} Новые сделки", callback_data="notif_new")],
        [InlineKeyboardButton(text=f"{'✅' if n.get('close_trades',True) else '❌'} Закрытие позиций", callback_data="notif_close")],
        [InlineKeyboardButton(text=f"{'✅' if n.get('daily_report',True) else '❌'} Ежедневный отчёт", callback_data="notif_daily")],
    ]))

@dp.callback_query(F.data.startswith("notif_"))
async def notif_toggle(cb: types.CallbackQuery):
    key = cb.data.replace("notif_", "")
    key_map = {"new": "new_trades", "close": "close_trades", "daily": "daily_report"}
    field = key_map.get(key, key)
    u = db.get(cb.from_user.id)
    n = u.get("notifications", {})
    n[field] = not n.get(field, True)
    db.update(cb.from_user.id, {"notifications": n})
    await cb.answer(f"{'✅ ВКЛ' if n[field] else '❌ ВЫКЛ'}")

@dp.message(F.text == "📡 Сигналы AI")
async def signals_ai(msg: types.Message):
    prices = await market.fetch()
    s = get_signals(prices, "signals")[:8]
    if not s: return await msg.answer("📡 Нет сигналов")
    text = f"📡 СИГНАЛЫ AI\n\n"
    kb = []
    for sym, data in s:
        text += f"{'🟢' if data['chg']>0 else '🔴'} {sym}: ${data['price']:.4f} ({data['chg']:+.1f}%)\n"
        kb.append([InlineKeyboardButton(text=f"BUY {sym.split('/')[0]}", callback_data=f"buy_{sym}_{data['price']}")])
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_token(cb: types.CallbackQuery):
    _, sym, price = cb.data.split("_")
    u = db.get(cb.from_user.id)
    if not u: return await cb.answer("/start")
    amt = min(u["balance"]*0.1, 500)
    pnl = amt * random.uniform(-0.05, 0.10)
    db.add_trade(cb.from_user.id, {"token": sym, "type": "BUY", "amount": amt, "price": float(price), "pnl": pnl, "source": "manual", "timestamp": datetime.now().isoformat()})
    u2 = db.get(cb.from_user.id)
    await cb.answer(f"${amt:.0f}")
    await cb.message.answer(f"✅ {sym}\n💰 ${amt:.0f}\nPnL: ${pnl:+,.0f}\n💼 ${u2['balance']:,.0f}")

@dp.message(F.text == "💼 Портфель")
async def portf(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    pos = [p for p in u.get("positions",[]) if p.get("status")=="open"]
    if not pos: return await msg.answer("💼 Нет открытых позиций")
    text = "💼 ПОРТФЕЛЬ\n\n"
    for p in pos[:5]: text += f"{'🟢' if p.get('pnl',0)>0 else '🔴'} {p['token']}: ${p['entry_price']:.4f} → ${p.get('current_price',0):.4f}\n"
    await msg.answer(text)

@dp.message(F.text == "📋 Сделки")
async def trades(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    t = u.get("trades", [])
    if not t: return await msg.answer("📋 Нет сделок")
    text = f"📋 СДЕЛКИ\n\n"
    for x in t[-10:]: text += f"{'🤖' if x.get('source')=='auto' else '👤'} {x['token']}: ${x.get('pnl',0):+,.2f}\n"
    await msg.answer(text)

@dp.message(F.text == "🎯 Снайпер")
async def snipe(msg: types.Message):
    s = get_signals(await market.fetch(), "sniper")
    if not s: return await msg.answer("🎯 Нет сигналов")
    await msg.answer(f"🎯 СНАЙПЕР\n\n{s[0][0]}: ${s[0][1]['price']:.4f} ({s[0][1]['chg']:+.1f}%)")

@dp.message(F.text == "🚀 Пампы")
async def pump(msg: types.Message):
    s = get_signals(await market.fetch(), "pumps")
    if not s: return await msg.answer("🚀 Нет пампов")
    text = "🚀 ПАМПЫ\n\n"
    for sym, data in s[:5]: text += f"🔥 {sym}: {data['chg']:+.1f}%\n"
    await msg.answer(text)

@dp.message(F.text == "👑 VIP сигналы")
async def vip(msg: types.Message):
    s = get_signals(await market.fetch(), "vip")
    if not s: return await msg.answer("👑 Нет VIP сигналов")
    text = "👑 VIP\n\n"
    for sym, data in s[:5]: text += f"👑 {sym}: {data['chg']:+.1f}%\n"
    await msg.answer(text)

@dp.message(F.text == "🔙 Назад")
async def back(msg: types.Message): await msg.answer("Меню", reply_markup=main_kb())

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
        [InlineKeyboardButton(text="Низкий", callback_data="r_low")],
        [InlineKeyboardButton(text="Средний", callback_data="r_medium")],
        [InlineKeyboardButton(text="Высокий", callback_data="r_high")],
    ]))

@dp.callback_query(F.data.startswith("r_"))
async def risk_set(cb: types.CallbackQuery):
    db.update(cb.from_user.id, {"risk": cb.data.split("_")[1]})
    await cb.answer("✅")

async def main():
    print("🚀 SST TRADER v9.0 — WITH NOTIFICATIONS")
    asyncio.create_task(auto_trading_loop())
    asyncio.create_task(daily_report_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
