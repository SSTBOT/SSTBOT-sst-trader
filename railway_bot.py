#!/usr/bin/env python3
"""
SST TRADER v9.1 — FIXED: position size, 8 strategies, reinvest, close notifications
"""
import asyncio, logging, random, json, os, time, secrets
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SST")

from supabase import create_client

# ===== BYBIT REAL API =====
from pybit.unified_trading import HTTP
BYBIT_KEY = "QtxrlcN1pPUPQFMpMW"
BYBIT_SECRET = "uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft"
bybit = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)

def place_real_order(symbol: str, side: str, amount_usd: float):
    try:
        sym = symbol.replace("/", "")
        ticker = bybit.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0: return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 4)
        if qty <= 0: return None
        order = bybit.place_order(category="spot", symbol=sym, side="Buy" if side=="BUY" else "Sell", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0:
            logger.info(f"REAL ORDER: {side} {symbol} ${amount_usd:.2f}")
            return {"price": price, "qty": qty, "order_id": order["result"]["orderId"]}
    except Exception as e: logger.error(f"Bybit error: {e}")
    return None
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
                "id": uid, "name": name, "balance": 36, "sub": "vip",
                "auto_trading": 0, "strategy": "conservative", "reinvest": 50,
                "risk": "low", "trades": [], "positions": [],
                "ai_stats": {"predictions":0,"correct":0,"accuracy":0},
                "notifications": {"new_trades":True,"close_trades":True,"daily_report":True}
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
        if u: self.update(uid, {"positions": u.get("positions", []) + [p]})
    def get_all(self):
        try:
            r = supabase.table("users").select("*").execute()
            return r.data or []
        except: return []

db = DB()

# ===== РЫНОК =====
class MarketData:
    async def fetch(self):
        prices = {}
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=5) as r:
                    for t in (await r.json())['result']['list'][:50]:
                        if t['symbol'] not in STABLECOINS:
                            prices[t['symbol']] = {'price': float(t['lastPrice']), 'chg': float(t.get('price24hPcnt',0))*100, 'vol': float(t.get('volume24h',0))}
        except: pass
        if not prices:
            prices = {'BTC/USDT':{'price':80500,'chg':2.5,'vol':30e9},'ETH/USDT':{'price':4100,'chg':-1.2,'vol':15e9},'SOL/USDT':{'price':155,'chg':5.0,'vol':3e9},'DOGE/USDT':{'price':0.113,'chg':2.8,'vol':800e6}}
        return prices

market = MarketData()

# ===== 8 СТРАТЕГИЙ =====
STRATEGIES = {
    "aggressive": {"name": "Агрессивная", "pos": 20, "stop": 3, "target": 10},
    "moderate": {"name": "Умеренная", "pos": 10, "stop": 5, "target": 15},
    "conservative": {"name": "Консервативная", "pos": 5, "stop": 2, "target": 5},
    "scalping": {"name": "Скальпинг", "pos": 3, "stop": 1, "target": 2},
    "trend": {"name": "Трендовая", "pos": 15, "stop": 7, "target": 25},
    "counter": {"name": "Контртренд", "pos": 10, "stop": 4, "target": 8},
    "arbitrage": {"name": "Арбитраж", "pos": 25, "stop": 0.5, "target": 1.5},
    "ai": {"name": "AI Стратегия", "pos": 10, "stop": 5, "target": 20},
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
    try:
        from aiogram import Bot
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(user_id, text, parse_mode="Markdown")
        await bot.session.close()
    except Exception as e:
        logger.error(f"Notify error: {e}")

# ===== АВТОТРЕЙДИНГ (ИСПРАВЛЕННЫЙ) =====
async def auto_trading_loop():
    while True:
        try:
            prices = await market.fetch()
            users = db.get_all()
            
            for user in users:
                if not user.get("auto_trading"): continue
                
                uid = user["id"]
                strategy = user.get("strategy", "conservative")
                risk = user.get("risk", "low")
                balance = user.get("balance", 36)
                positions = user.get("positions", [])
                notif = user.get("notifications", {})
                reinvest_pct = user.get("reinvest", 50)
                open_pos = [p for p in positions if p.get("status") == "open"]
                
                if len(open_pos) >= 3: continue
                open_tokens = {p["token"] for p in open_pos}  # Максимум 3 позиции
                
                cfg = STRATEGIES.get(strategy, STRATEGIES["conservative"])
                
                # Сбор кандидатов
                candidates = []
                if strategy in ["aggressive", "ai"]:
                    candidates += get_signals(prices, "pumps")[:3]
                    candidates += get_signals(prices, "sniper")
                if strategy in ["moderate", "ai"]:
                    candidates += get_signals(prices, "signals")[:3]
                if strategy == "conservative":
                    candidates += get_signals(prices, "vip")[:2]
                if strategy in ["scalping", "trend", "counter", "arbitrage"]:
                    candidates += get_signals(prices, "signals")[:2]
                
                # Дедубликация
                seen = set()
                uniq = []
                for k, v in candidates:
                    if k not in seen:
                        seen.add(k)
                        uniq.append((k, v))
                
                # Расчёт размера позиции (ИСПРАВЛЕНО!)
                pos_pct = cfg["pos"]
                amt = balance * pos_pct / 100
                
                # Открытие позиций
                for k, v in uniq[:2]:
                    if k in open_tokens: continue  # Максимум 2 новые за цикл
                    target = v["price"] * (1 + cfg["target"] / 100)
                    stop = v["price"] * (1 - cfg["stop"] / 100)
                    
                    pos = {
                        "token": k, "entry_price": v["price"],
                        "amount": round(amt, 2), "target": round(target, 4),
                        "stop_loss": round(stop, 4), "current_price": v["price"],
                        "pnl": 0, "status": "open", "source": "auto",
                        "strategy": strategy, "timestamp": datetime.now().isoformat()
                    }
                    db.add_position(uid, pos)
                    
                    # Уведомление о новой сделке
                    if notif.get("new_trades", True):
                        await send_notification(uid,
                            f"🟢 **НОВАЯ СДЕЛКА (Авто)**\n\n"
                            f"📛 {k}\n💰 Куплено: ${amt:.2f}\n"
                            f"💵 Цена: ${v['price']:.4f}\n"
                            f"🎯 Цель: ${target:.4f} (+{cfg['target']}%)\n"
                            f"🛑 Стоп: ${stop:.4f} (-{cfg['stop']}%)\n"
                            f"📊 {cfg['name']}\n🕐 {datetime.now().strftime('%H:%M')}"
                        )
                
                # Закрытие позиций
                updated = []
                for p in positions:
                    if p.get("status") != "open":
                        updated.append(p)
                        continue
                    
                    cp = prices.get(p["token"], {}).get("price", p["entry_price"])
                    p["current_price"] = cp
                    p["pnl"] = round((cp - p["entry_price"]) / p["entry_price"] * p["amount"], 2)
                    
                    # Проверка закрытия
                    if cp >= p["target"] or cp <= p["stop_loss"]:
                        p["status"] = "closed"
                        trade = {
                            "token": p["token"], "type": "SELL",
                            "amount": p["amount"], "price": cp,
                            "pnl": p["pnl"], "source": "auto",
                            "strategy": p.get("strategy", "conservative"),
                            "timestamp": datetime.now().isoformat()
                        }
                        db.add_trade(uid, trade)
                        
                        # Уведомление о закрытии
                        if notif.get("close_trades", True):
                            emoji = "🟢" if p["pnl"] > 0 else "🔴"
                            reason = "🎯 Цель" if cp >= p["target"] else "🛑 Стоп"
                            await send_notification(uid,
                                f"{emoji} **ЗАКРЫТИЕ (Авто)**\n\n"
                                f"📛 {p['token']}\n💰 ${p['amount']:.2f}\n"
                                f"💵 {p['entry_price']:.4f} → ${cp:.4f}\n"
                                f"📈 PnL: ${p['pnl']:+,.2f} ({p['pnl']/p['amount']*100:+.1f}%)\n"
                                f"{reason}\n🕐 {datetime.now().strftime('%H:%M')}"
                            )
                    
                    updated.append(p)
                
                db.update(uid, {"positions": updated})
                
                # Реинвестирование (ИСПРАВЛЕНО!)
                current_balance = (await supabase.table("users").select("balance").eq("id", uid).execute()).data[0]["balance"]
                if reinvest_pct > 0 and current_balance > 36:
                    profit = current_balance - 36
                    if profit > 0.01:
                        reinvest_amount = round(profit * reinvest_pct / 100, 2)
                        new_balance = round(current_balance + reinvest_amount, 2)
                        db.update(uid, {"balance": new_balance})
                        if reinvest_amount > 0.01:
                            await send_notification(uid,
                                f"💰 **РЕИНВЕСТ**\n\n"
                                f"Прибыль: ${profit:.2f}\n"
                                f"Реинвест ({reinvest_pct}%): ${reinvest_amount:.2f}\n"
                                f"Новый баланс: ${new_balance:.2f}"
                            )
        
        except Exception as e:
            logger.error(f"Auto-trading error: {e}")
        
        await asyncio.sleep(45)

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
        await msg.answer(f"👋 {u['name']}\n💰 ${u['balance']:.2f}\n🤖 Авто: {'🟢' if u.get('auto_trading') else '🔴'}\n📊 {STRATEGIES.get(u.get('strategy','conservative'),{}).get('name','?')}", reply_markup=main_kb())
    else:
        await msg.answer("🚀 SST TRADER v9.1\n\nВведите имя:"); await state.set_state(St.name)

@dp.message(St.name)
async def name(msg: types.Message, state: FSMContext):
    db.create(msg.from_user.id, msg.text.strip()); await state.clear()
    await msg.answer("✅ Готово! $36 на балансе\nВыбрана Консервативная стратегия", reply_markup=main_kb())

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
    await msg.answer(f"👤 {u['name']}\n💰 ${u['balance']:.2f}\n📈 PnL: ${pnl:+,.2f}\n📊 {STRATEGIES.get(u.get('strategy','conservative'),{}).get('name','?')}\n🔄 Реинвест: {u.get('reinvest',50)}%", reply_markup=main_kb())

@dp.message(F.text == "📡 Сигналы AI")
async def signals_ai(msg: types.Message):
    prices = await market.fetch()
    s = get_signals(prices, "signals")[:8]
    if not s: return await msg.answer("📡 Нет сигналов")
    text = "📡 СИГНАЛЫ AI\n\n"
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
    amt = round(u["balance"] * 0.05, 2)
    pnl = round(amt * random.uniform(-0.03, 0.05), 2)
    db.add_trade(cb.from_user.id, {"token": sym, "type": "BUY", "amount": amt, "price": float(price), "pnl": pnl, "source": "manual", "timestamp": datetime.now().isoformat()})
    await cb.answer(f"${amt:.2f}")
    await cb.message.answer(f"✅ {sym}\n${amt:.2f}\nPnL: ${pnl:+,.2f}")

@dp.message(F.text == "💼 Портфель")
async def portf(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    pos = [p for p in u.get("positions",[]) if p.get("status")=="open"]
    if not pos: return await msg.answer("💼 Нет открытых позиций")
    text = "💼 ПОРТФЕЛЬ\n\n"
    for p in pos[:5]: text += f"{'🟢' if p.get('pnl',0)>0 else '🔴'} {p['token']}: ${p.get('pnl',0):+,.2f}\n"
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
    if not s: return await msg.answer("👑 Нет VIP")
    text = "👑 VIP\n\n"
    for sym, data in s[:5]: text += f"👑 {sym}: {data['chg']:+.1f}%\n"
    await msg.answer(text)

@dp.message(F.text == "🔙 Назад")
async def back(msg: types.Message): await msg.answer("Меню", reply_markup=main_kb())

@dp.message(F.text == "⚙️ Настройки")
async def settings(msg: types.Message):
    u = db.get(msg.from_user.id)
    await msg.answer(f"⚙️ НАСТРОЙКИ\n\n📊 {STRATEGIES.get(u.get('strategy','conservative'),{}).get('name','?')}\n🔄 Реинвест: {u.get('reinvest',50)}%", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Стратегия (8)", callback_data="strat")],
        [InlineKeyboardButton(text="🔄 Реинвест", callback_data="reinv")],
        [InlineKeyboardButton(text="🛡️ Риск", callback_data="risk")],
    ]))

@dp.callback_query(F.data == "strat")
async def strat_cb(cb: types.CallbackQuery):
    await cb.message.edit_text("📊 СТРАТЕГИИ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{s['name']} ({s['pos']}%)", callback_data=f"s_{k}") for k, s in list(STRATEGIES.items())[:4]],
        [InlineKeyboardButton(text=f"{s['name']} ({s['pos']}%)", callback_data=f"s_{k}") for k, s in list(STRATEGIES.items())[4:]],
    ]))

@dp.callback_query(F.data.startswith("s_"))
async def strat_set(cb: types.CallbackQuery):
    s = cb.data.split("_")[1]
    db.update(cb.from_user.id, {"strategy": s})
    await cb.answer(f"✅ {STRATEGIES[s]['name']}")

@dp.callback_query(F.data == "reinv")
async def reinv_cb(cb: types.CallbackQuery):
    await cb.message.edit_text("🔄 РЕИНВЕСТ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{x}%", callback_data=f"ri_{x}") for x in [0, 25, 50, 75, 100]],
    ]))

@dp.callback_query(F.data.startswith("ri_"))
async def reinv_set(cb: types.CallbackQuery):
    r = int(cb.data.split("_")[1])
    db.update(cb.from_user.id, {"reinvest": r})
    await cb.answer(f"✅ {r}%")

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

@dp.message(F.text == "🔔 Уведомления")
async def notif_menu(msg: types.Message):
    u = db.get(msg.from_user.id)
    if not u: return await msg.answer("/start")
    n = u.get("notifications", {})
    await msg.answer("🔔 УВЕДОМЛЕНИЯ", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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
    await cb.answer(f"{'✅' if n[field] else '❌'}")

async def main():
    print("🚀 SST TRADER v9.1 — FIXED")
    asyncio.create_task(auto_trading_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

