#!/usr/bin/env python3
"""
SST TRADER v9.1 — FIXED: position size, 8 strategies, reinvest, close notifications
"""
import asyncio, logging, random, json, os, time, secrets
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger

# ===== BYBIT REAL TRADING =====
def place_real_order(symbol: str, side: str, amount_usd: float):
    """Реальный ордер на Bybit Spot"""
    try:
        from pybit.unified_trading import HTTP
        session = HTTP(testnet=False, api_key="QtxrlcN1pPUPQFMpMW", api_secret="uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft")
        sym = symbol.replace("/", "")
        ticker = session.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0:
            return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 0) if price > 1 else round(amount_usd / price, 0)
        if qty <= 0:
            return None
        order = session.place_order(category="spot", symbol=sym, side="Buy" if side=="BUY" else "Sell", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0:
            return {"price": price, "qty": qty, "order_id": order["result"]["orderId"]}
        from pybit.unified_trading import HTTP
        bybit = HTTP(
            testnet=False,
            api_key="QtxrlcN1pPUPQFMpMW",
            api_secret="uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft"
        )
        sym = symbol.replace("/", "")
        ticker = bybit.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0:
            return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 4)
        if qty <= 0:
            return None
        order = bybit.place_order(
            category="spot", symbol=sym,
            side="Buy" if side == "BUY" else "Sell",
            orderType="Market", qty=str(qty)
        )
        if order.get("retCode") == 0:
            return {"price": price, "qty": qty, "order_id": order["result"]["orderId"]}
    except Exception as e:
        print(f"Bybit error: {e}")
    return None
