import os, random, time, json, logging, secrets
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template_string, request, jsonify, redirect, make_response
from flask_cors import CORS
from functools import wraps

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SST")

BYBIT_KEY = os.getenv("BYBIT_API_KEY", "QtxrlcN1pPUPQFMpMW")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "uxwWmOC7CFs85iMQHRq5gRpINDxkAsihxfft")
APP_PASSWORD = os.getenv("APP_PASSWORD", "sst2026")

app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_hex(16)

STABLECOINS = {"USDCUSDT","USDTUSDT","FDUSDUSDT","BUSDUSDT","DAIUSDT","TUSDUSDT"}
STRATEGIES = {
    "aggressive": {"name": "Агрессивная", "pos": 20, "stop": 3, "target": 10},
    "moderate": {"name": "Умеренная", "pos": 10, "stop": 5, "target": 15},
    "conservative": {"name": "Консервативная", "pos": 5, "stop": 2, "target": 5},
    "scalping": {"name": "Скальпинг", "pos": 3, "stop": 1, "target": 2},
    "trend": {"name": "Трендовая", "pos": 15, "stop": 7, "target": 25},
    "ai": {"name": "AI МаксПрибыль", "pos": 10, "stop": 3, "target": 20},
}

state = {
    "auto_trading": False, "strategy": "conservative", "reinvest": 50,
    "trades": [], "bought_tokens": set()
}

def check_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.cookies.get('sst_auth')
        if auth != APP_PASSWORD:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def get_bybit_balance():
    try:
        from pybit.unified_trading import HTTP
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        bal = session.get_wallet_balance(accountType="UNIFIED")
        coins = bal["result"]["list"][0]["coin"]
        total = float(bal["result"]["list"][0]["totalWalletBalance"])
        return {"total": round(total, 2), "coins": [{"coin": c["coin"], "amount": float(c["walletBalance"])} for c in coins if float(c["walletBalance"]) > 0]}
    except: return {"total": 0, "coins": []}

def get_prices():
    prices = {}
    try:
        import requests
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=5)
        for t in r.json()['result']['list'][:80]:
            if t['symbol'] not in STABLECOINS:
                prices[t['symbol']] = {'price': float(t['lastPrice']), 'chg': round(float(t.get('price24hPcnt',0))*100, 2), 'vol': float(t.get('volume24h',0))}
    except:
        prices = {'BTCUSDT':{'price':80500,'chg':2.5,'vol':30e9},'ETHUSDT':{'price':4100,'chg':-1.2,'vol':15e9},'SOLUSDT':{'price':155,'chg':5.0,'vol':3e9},'DOGEUSDT':{'price':0.113,'chg':2.8,'vol':800e6}}
    return prices

def real_buy(symbol, amount_usd):
    try:
        from pybit.unified_trading import HTTP
        session = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)
        sym = symbol.replace("/", "")
        ticker = session.get_tickers(category="spot", symbol=sym)
        if ticker.get("retCode") != 0: return None
        price = float(ticker["result"]["list"][0]["lastPrice"])
        qty = round(amount_usd / price, 4)
        if qty <= 0: return None
        order = session.place_order(category="spot", symbol=sym, side="Buy", orderType="Market", qty=str(qty))
        if order.get("retCode") == 0: return price
    except Exception as e: logger.error(f"Buy error: {e}")
    return None

def get_signals(prices, sig_type="signals"):
    s = sorted(prices.items(), key=lambda x: x[1]["chg"], reverse=True)
    if sig_type == "pumps": return [(k, v) for k, v in s if v["chg"] > 15][:10]
    if sig_type == "vip": return [(k, v) for k, v in s if v["chg"] > 3 and v["vol"] > 10e6][:5]
    if sig_type == "sniper":
        sc = [(k, v, v["chg"] * v["vol"]) for k, v in s[:50]]
        sc.sort(key=lambda x: x[2], reverse=True)
        return [(k, v) for k, v, _ in sc[:5]]
    return []

# ===== СТРАНИЦА ВХОДА =====
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SST Trader - Вход</title>
    <style>
        :root { --bg:#0b0e11; --card:#1e2329; --border:#2b3139; --text:#eaecef; --gold:#f0b90b; --green:#0ecb81; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:-apple-system,sans-serif; background:var(--bg); color:var(--text); display:flex; align-items:center; justify-content:center; min-height:100vh; }
        .login-box { background:var(--card); padding:30px; border-radius:16px; border:1px solid var(--border); width:90%; max-width:360px; text-align:center; }
        .logo { font-size:24px; font-weight:700; margin-bottom:20px; }
        .logo span { color:var(--gold); }
        input { width:100%; padding:14px; border-radius:8px; border:1px solid var(--border); background:var(--bg); color:var(--text); font-size:16px; margin:8px 0; text-align:center; }
        button { width:100%; padding:14px; border-radius:8px; border:none; background:var(--gold); color:#000; font-size:16px; font-weight:700; cursor:pointer; margin-top:8px; }
        .error { color:#f6465d; font-size:13px; margin-top:8px; }
    </style>
</head>
<body>
    <div class="login-box">
        <div class="logo">🚀 SST<span>Trader</span></div>
        <p style="color:#848e9c;margin-bottom:16px;">Введите пароль для доступа</p>
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="Пароль" required autofocus>
            <button type="submit">ВОЙТИ</button>
            <div class="error">{{ error }}</div>
        </form>
    </div>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == APP_PASSWORD:
            resp = make_response(redirect('/'))
            resp.set_cookie('sst_auth', APP_PASSWORD, max_age=60*60*24*30, httponly=True)
            return resp
        error = "Неверный пароль"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    resp = make_response(redirect('/login'))
    resp.delete_cookie('sst_auth')
    return resp

# ===== ЗАЩИЩЁННЫЕ РОУТЫ =====
@app.route('/')
@check_auth
def index():
    return render_template_string(MAIN_HTML, password=APP_PASSWORD)

@app.route('/api/all')
@check_auth
def api_all():
    prices = get_prices()
    balance = get_bybit_balance()
    return jsonify({
        'balance': balance,
        'tokens': {k: v for k, v in sorted(prices.items(), key=lambda x: x[1]['chg'], reverse=True)[:50]},
        'pumps': {k: v for k, v in get_signals(prices, "pumps")},
        'vip': {k: v for k, v in get_signals(prices, "vip")},
        'sniper': {k: v for k, v in get_signals(prices, "sniper")},
        'trades': state['trades'][-15:],
        'auto': state['auto_trading'],
        'strategy': STRATEGIES[state['strategy']]['name'],
        'reinvest': state['reinvest'],
        'pnl': sum(t.get('pnl', 0) for t in state['trades']),
        'wins': sum(1 for t in state['trades'] if t.get('pnl', 0) > 0),
        'losses': sum(1 for t in state['trades'] if t.get('pnl', 0) <= 0),
        'token_list': [k for k in prices.keys()][:60]
    })

@app.route('/api/buy', methods=['POST'])
@check_auth
def api_buy():
    data = request.json
    token = data.get('token', 'SOLUSDT')
    amount = float(data.get('amount', 5))
    price = real_buy(token, amount)
    if price:
        trade = {"token": token, "type": "BUY", "amount": amount, "price": price, "pnl": 0, "source": "manual", "timestamp": datetime.now().isoformat()}
        state['trades'].append(trade)
        return jsonify({'ok': True, 'price': round(price, 4), 'token': token, 'amount': amount})
    return jsonify({'ok': False, 'error': 'Order failed'})

@app.route('/api/auto', methods=['POST'])
@check_auth
def api_auto():
    state['auto_trading'] = not state['auto_trading']
    return jsonify({'auto': state['auto_trading']})

@app.route('/api/strategy', methods=['POST'])
@check_auth
def api_strategy():
    data = request.json
    s = data.get('strategy', 'conservative')
    if s in STRATEGIES: state['strategy'] = s
    return jsonify({'ok': True})

@app.route('/api/reinvest', methods=['POST'])
@check_auth
def api_reinvest():
    data = request.json
    state['reinvest'] = int(data.get('reinvest', 50))
    return jsonify({'ok': True})

# ===== ОСНОВНОЙ HTML =====
MAIN_HTML = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>SST Trader v10</title>
    <style>
        :root { --bg:#0b0e11; --card:#1e2329; --border:#2b3139; --text:#eaecef; --sub:#848e9c; --green:#0ecb81; --red:#f6465d; --gold:#f0b90b; --blue:#3772ff; --purple:#8b5cf6; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:-apple-system,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; padding-bottom:90px; -webkit-tap-highlight-color:transparent; }
        .header { background:var(--card); padding:12px 16px; display:flex; justify-content:space-between; border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100; }
        .logo { font-size:20px; font-weight:700; } .logo span { color:var(--gold); }
        .logout { color:var(--red); font-size:12px; cursor:pointer; text-decoration:none; }
        .content { padding:8px 12px; }
        .card { background:var(--card); border-radius:12px; padding:12px; margin:8px 0; border:1px solid var(--border); }
        .card-title { font-size:14px; font-weight:600; color:var(--sub); margin-bottom:8px; }
        .row { display:flex; gap:6px; margin:6px 0; }
        .btn { flex:1; padding:12px; border-radius:8px; border:none; font-size:12px; font-weight:600; cursor:pointer; text-align:center; }
        .btn:active { transform:scale(0.97); }
        .btn-gold { background:var(--gold); color:#000; font-size:14px; }
        .btn-blue { background:var(--blue); color:#fff; }
        .btn-outline { background:transparent; border:1px solid var(--border); color:var(--text); }
        .btn-red { background:var(--red); color:#fff; }
        .token-row { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border); cursor:pointer; }
        .token-row:active { opacity:0.7; }
        .token-sym { font-weight:600; font-size:13px; }
        .token-src { font-size:9px; padding:1px 5px; border-radius:3px; margin-left:4px; }
        .src-pump { background:rgba(14,203,129,0.2); color:var(--green); }
        .src-vip { background:rgba(240,185,11,0.2); color:var(--gold); }
        .src-sniper { background:rgba(139,92,246,0.2); color:var(--purple); }
        .green { color:var(--green); } .red { color:var(--red); }
        .big { font-size:24px; font-weight:700; text-align:center; }
        .small { font-size:11px; color:var(--sub); }
        .bottom-nav { position:fixed; bottom:0; left:0; right:0; background:var(--card); border-top:1px solid var(--border); display:flex; padding:6px 0; z-index:150; }
        .nav-item { flex:1; text-align:center; color:var(--sub); font-size:10px; cursor:pointer; padding:4px; }
        .nav-icon { font-size:16px; }
        .modal { position:fixed; bottom:0; left:0; right:0; background:var(--card); border-radius:16px 16px 0 0; padding:20px; z-index:200; transform:translateY(100%); transition:.3s; max-height:80vh; overflow-y:auto; }
        .modal.open { transform:translateY(0); }
        .overlay { position:fixed; top:0;left:0;right:0;bottom:0; background:rgba(0,0,0,0.5); z-index:199; display:none; }
        .overlay.open { display:block; }
        select, input { width:100%; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--bg); color:var(--text); font-size:14px; margin:4px 0; }
        .slider { width:100%; margin:8px 0; -webkit-appearance:none; height:4px; background:var(--border); border-radius:2px; outline:none; }
        .slider::-webkit-slider-thumb { -webkit-appearance:none; width:22px; height:22px; background:var(--gold); border-radius:50%; cursor:pointer; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🚀 SST<span>Trader</span></div>
        <div><span class="small" id="time"></span> <a href="/logout" class="logout">Выйти</a></div>
    </div>
    
    <div class="content">
        <div class="card" style="text-align:center;">
            <div class="small">💼 БАЛАНС BYBIT</div>
            <div class="big" id="bal">--</div>
            <div class="small" id="coins">--</div>
            <div style="margin-top:4px;">📈 PnL: <span id="pnl" class="big">--</span></div>
            <div class="small">✅ <span id="wins">0</span> ❌ <span id="losses">0</span></div>
        </div>
        
        <div class="row">
            <button class="btn btn-gold" onclick="openBuy()">💵 КУПИТЬ ТОКЕН</button>
        </div>
        <div class="row">
            <button class="btn btn-blue" id="autoBtn" onclick="toggleAuto()">🤖 АВТО ВКЛ</button>
            <button class="btn btn-outline" onclick="showSettings()">⚙️ НАСТРОЙКИ</button>
        </div>
        
        <div class="card"><div class="card-title">🎯 СНАЙПЕР</div><div id="sniper"></div></div>
        <div class="card"><div class="card-title">🚀 ПАМПЫ</div><div id="pumps"></div></div>
        <div class="card"><div class="card-title">👑 VIP</div><div id="vip"></div></div>
        <div class="card"><div class="card-title">📡 ВСЕ ТОКЕНЫ (50+)</div><div id="allTokens"></div></div>
        <div class="card"><div class="card-title">📋 СДЕЛКИ</div><div id="history"></div></div>
    </div>
    
    <div class="overlay" id="overlay" onclick="closeBuy()"></div>
    <div class="modal" id="modal">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="font-weight:700;">💵 ПОКУПКА ТОКЕНА</span>
            <span style="cursor:pointer;font-size:20px;" onclick="closeBuy()">✕</span>
        </div>
        <select id="modalToken"></select>
        <div style="text-align:center;font-size:28px;font-weight:700;margin:8px 0;" id="amountDisplay">$10</div>
        <input type="range" class="slider" id="amountSlider" min="1" max="100" value="10" oninput="updateAmount()">
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--sub);"><span>$1</span><span>$25</span><span>$50</span><span>$75</span><span>$100</span></div>
        <button class="btn btn-gold" style="width:100%;padding:14px;font-size:16px;margin-top:12px;" onclick="confirmBuy()">💰 КУПИТЬ</button>
    </div>
    
    <div class="bottom-nav">
        <div class="nav-item" onclick="refreshAll()"><div class="nav-icon">📊</div>Рынок</div>
        <div class="nav-item" onclick="openBuy()"><div class="nav-icon">💰</div>Купить</div>
        <div class="nav-item" onclick="toggleAuto()"><div class="nav-icon" id="autoIcon">⏸️</div>Авто</div>
        <div class="nav-item" onclick="showSettings()"><div class="nav-icon">⚙️</div>Настр.</div>
    </div>

    <script>
        let autoTrading = false;
        let tokenList = [];
        
        async function refreshAll() {
            try {
                const r = await fetch('/api/all');
                if (r.status === 401) { window.location.href = '/login'; return; }
                const d = await r.json();
                
                document.getElementById('bal').textContent = '$' + (d.balance?.total?.toFixed(2) || '0.00');
                const coins = d.balance?.coins || [];
                document.getElementById('coins').textContent = coins.map(c => c.coin + ':' + c.amount?.toFixed(4)).join(' | ') || 'Нет активов';
                
                const pnl = d.pnl || 0;
                document.getElementById('pnl').textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                document.getElementById('pnl').className = 'big ' + (pnl >= 0 ? 'green' : 'red');
                document.getElementById('wins').textContent = d.wins || 0;
                document.getElementById('losses').textContent = d.losses || 0;
                
                autoTrading = d.auto;
                document.getElementById('autoBtn').textContent = d.auto ? '🤖 АВТО ВЫКЛ' : '🤖 АВТО ВКЛ';
                document.getElementById('autoIcon').textContent = d.auto ? '▶️' : '⏸️';
                document.getElementById('time').textContent = new Date().toLocaleTimeString();
                
                tokenList = d.token_list || [];
                let opts = '';
                for (const t of tokenList.slice(0, 60)) opts += '<option value="' + t + '">' + t.replace('USDT','') + '</option>';
                document.getElementById('modalToken').innerHTML = opts;
                
                function renderTokens(data, containerId, srcClass, srcLabel) {
                    let html = '';
                    for (const [sym, v] of Object.entries(data || {}).slice(0, 5)) {
                        html += '<div class="token-row" onclick="quickBuy(\'' + sym + '\')"><div><span class="token-sym">' + sym.replace('USDT','') + '</span><span class="token-src ' + srcClass + '">' + srcLabel + '</span></div><div style="text-align:right;"><div>$' + (v.price?.toFixed(4) || '--') + '</div><div class="' + (v.chg >= 0 ? 'green' : 'red') + '">' + (v.chg >= 0 ? '+' : '') + (v.chg?.toFixed(1) || '0') + '%</div></div></div>';
                    }
                    document.getElementById(containerId).innerHTML = html || '<div class="small">Нет сигналов</div>';
                }
                
                renderTokens(d.sniper, 'sniper', 'src-sniper', 'SNIPER');
                renderTokens(d.pumps, 'pumps', 'src-pump', 'PUMP');
                renderTokens(d.vip, 'vip', 'src-vip', 'VIP');
                renderTokens(d.tokens, 'allTokens', '', '');
                
                let histHtml = '';
                for (const t of (d.trades || []).slice(-8).reverse()) {
                    histHtml += '<div class="token-row"><span>' + (t.source === 'auto' ? '🤖' : '👤') + ' ' + t.token?.replace('USDT','') + '</span><span>$' + (t.amount?.toFixed(2) || '0') + '</span><span class="' + ((t.pnl || 0) >= 0 ? 'green' : 'red') + '">' + ((t.pnl || 0) >= 0 ? '+' : '') + '$' + (t.pnl?.toFixed(2) || '0') + '</span></div>';
                }
                document.getElementById('history').innerHTML = histHtml || '<div class="small">Нет сделок</div>';
            } catch(e) { console.error(e); }
        }
        
        function openBuy() { document.getElementById('modal').classList.add('open'); document.getElementById('overlay').classList.add('open'); }
        function closeBuy() { document.getElementById('modal').classList.remove('open'); document.getElementById('overlay').classList.remove('open'); }
        function updateAmount() { document.getElementById('amountDisplay').textContent = '$' + document.getElementById('amountSlider').value; }
        function quickBuy(symbol) { document.getElementById('modalToken').value = symbol; openBuy(); }
        
        function confirmBuy() {
            const token = document.getElementById('modalToken').value;
            const amount = parseFloat(document.getElementById('amountSlider').value);
            closeBuy();
            fetch('/api/buy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token, amount})})
            .then(r => { if (r.status === 401) window.location.href = '/login'; return r.json(); })
            .then(d => { alert(d.ok ? '✅ ' + d.token + '\\n$' + d.amount + ' @ $' + d.price : '❌ ' + (d.error || 'Ошибка')); refreshAll(); });
        }
        
        async function toggleAuto() {
            const r = await fetch('/api/auto', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
            refreshAll();
        }
        
        function showSettings() {
            const strat = prompt('Стратегия:\n1.Агрессивная (20%)\n2.Умеренная (10%)\n3.Консервативная (5%)\n4.Скальпинг (3%)\n5.Трендовая (15%)\n6.AI (10%)', '3');
            if (strat) {
                const strats = ['aggressive','moderate','conservative','scalping','trend','ai'];
                fetch('/api/strategy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({strategy: strats[parseInt(strat)-1] || 'conservative'})});
            }
            const reinvest = prompt('Реинвест %:', '50');
            if (reinvest) fetch('/api/reinvest', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({reinvest: parseInt(reinvest)})});
        }
        
        setInterval(refreshAll, 15000);
        refreshAll();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🚀 SST TRADER v10 — ЗАЩИЩЁННЫЙ ДОСТУП")
    print("   Пароль по умолчанию: sst2026")
    print("   http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
