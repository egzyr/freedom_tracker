import os, time, requests, hmac, hashlib, json, threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')

GATE_KEY       = os.getenv('GATE_API_KEY')
GATE_SECRET    = os.getenv('GATE_SECRET')
TOKEN          = os.getenv('TELEGRAM_TOKEN')
CHAT_ID        = os.getenv('TELEGRAM_CHAT_ID')
BASE_URL       = "https://api.gateio.ws"

BOT_ACTIVE     = True
DCA_ENABLED    = True
LAST_UPDATE_ID = 0

trailing_ref      = {}
last_size         = {}
sl_placed         = {}
btc_price_history = []
session_zones     = {}
sweep_active      = {}
sweep_prev_price  = {}
sweep_last_notify = {}

CONFIG = {
    "BTC_USDT": {
        "icon": "🟠", "active": True,
        "min_moonbag": 2, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 20, "risk_per_level": 0.02,
        "tp_pct": 0.05, "tp_pct_from_now": 0.05, "trailing_trigger": 0.03,
        "sl_pct": 0.08, "price_decimals": 0,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.0001,
        "grid_reset_pct": 0.05,
    },
    "ETH_USDT": {
        "icon": "🔵", "active": True,
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.02,
        "max_contracts": 15, "risk_per_level": 0.02,
        "tp_pct": 0.05, "tp_pct_from_now": 0.05, "trailing_trigger": 0.03,
        "sl_pct": 0.08, "price_decimals": 2,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.01,
        "grid_reset_pct": 0.05,
    },
    "SOL_USDT": {
        "icon": "🟣", "active": True,
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 10, "risk_per_level": 0.02,
        "tp_pct": 0.05, "tp_pct_from_now": 0.05, "trailing_trigger": 0.03,
        "sl_pct": 0.10, "price_decimals": 2,
        "min_free_margin": 200, "min_equity": 250, "contract_multiplier": 0.1,
        "grid_reset_pct": 0.05,
    }
}

def sign(method, path, query="", body=""):
    ts = str(int(time.time()))
    h = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{h}\n{ts}"
    sig = hmac.new(GATE_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return {"KEY": GATE_KEY, "Timestamp": ts, "SIGN": sig, "Content-Type": "application/json"}

def gate_request(method, path, params=None, body=None):
    query = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    b_str = json.dumps(body) if body else ""
    try:
        r = requests.request(method, url, headers=sign(method, path, query, b_str), data=b_str, timeout=15)
        data = r.json()
        if isinstance(data, dict) and data.get("label"):
            print(f"  API ERR {data.get('label')} - {data.get('message','')[:50]}")
        return data
    except Exception as e:
        print(f"  REQ ERR {e}")
        return {}

def get_account():
    return gate_request("GET", "/api/v4/futures/usdt/accounts")

def get_positions():
    return gate_request("GET", "/api/v4/futures/usdt/positions")

def get_price(symbol):
    t = gate_request("GET", "/api/v4/futures/usdt/tickers", {"contract": symbol})
    return float(t[0]["last"]) if isinstance(t, list) and t else 0.0

def get_orders(symbol):
    o = gate_request("GET", "/api/v4/futures/usdt/orders", {"contract": symbol, "status": "open"})
    return o if isinstance(o, list) else []

def get_price_orders(symbol):
    o = gate_request("GET", "/api/v4/futures/usdt/price_orders", {"contract": symbol, "status": "open"})
    return o if isinstance(o, list) else []

def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

def fmt_price(price, symbol):
    d = CONFIG[symbol]["price_decimals"]
    return str(int(round(price))) if d == 0 else f"{price:.{d}f}"

def fmt_size(size):
    return max(1, int(size))

def bar(pct, width=10):
    filled = int(width * min(max(pct, 0.0), 1.0))
    return "█" * filled + "░" * (width - filled)

def is_market_crashing():
    if len(btc_price_history) < 5:
        return False
    change = (btc_price_history[-1] - btc_price_history[0]) / btc_price_history[0]
    return change < -0.03

def get_dynamic_size(symbol, equity, curr_price):
    cfg = CONFIG[symbol]
    target_val = equity * cfg["risk_per_level"]
    mult = cfg["contract_multiplier"]
    return max(1, int(target_val / (curr_price * mult)))

def update_session_zones():
    for sym, cfg in CONFIG.items():
        if not cfg["active"]:
            continue
        hist = gate_request("GET", "/api/v4/futures/usdt/candlesticks",
                            {"contract": sym, "limit": "8", "interval": "1h"})
        if not isinstance(hist, list) or not hist:
            continue
        try:
            h_list = []
            l_list = []
            for c in hist:
                if isinstance(c, list):
                    h_list.append(float(c[2]))
                    l_list.append(float(c[3]))
                elif isinstance(c, dict):
                    h_list.append(float(c.get("h", 0)))
                    l_list.append(float(c.get("l", 0)))
            if h_list and l_list:
                session_zones[sym] = {"high": max(h_list), "low": min(l_list)}
                print(f"  Zone {sym}: L={min(l_list):.2f} H={max(h_list):.2f}")
        except Exception as e:
            print(f"  Zone ERR {sym}: {e}")

def is_london_session():
    return 7 <= datetime.utcnow().hour < 10

def detect_sweep(symbol, curr_price):
    if not is_london_session():
        sweep_active[symbol] = False
        sweep_prev_price[symbol] = curr_price
        return False, "poza sesja"
    zone = session_zones.get(symbol)
    if not zone:
        return False, "brak strefy"
    low = zone["low"]
    prev = sweep_prev_price.get(symbol, curr_price)
    sweep_prev_price[symbol] = curr_price
    if prev >= low and curr_price < low:
        sweep_active[symbol] = True
        pct = (low - curr_price) / low * 100
        return True, f"SWEEP LOW {low:.2f} (-{pct:.1f}%)"
    if sweep_active.get(symbol) and curr_price < low:
        pct = (low - curr_price) / low * 100
        return True, f"SWEEP CONT {low:.2f} (-{pct:.1f}%)"
    if sweep_active.get(symbol) and curr_price > low * 1.005:
        sweep_active[symbol] = False
    return False, "brak sweep"

def listen_telegram():
    global BOT_ACTIVE, DCA_ENABLED, LAST_UPDATE_ID
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": LAST_UPDATE_ID + 1, "timeout": 30},
                timeout=35
            ).json()
            if r.get("ok") and r.get("result"):
                for update in r["result"]:
                    LAST_UPDATE_ID = update["update_id"]
                    msg = update.get("message", {}).get("text", "")
                    chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                    if chat_id != CHAT_ID:
                        continue
                    if msg == "/stop":
                        BOT_ACTIVE = False
                        tg("🛑 <b>Bot zatrzymany</b>")
                    elif msg == "/start":
                        BOT_ACTIVE = True
                        tg("🚀 <b>Bot uruchomiony!</b>")
                    elif msg == "/dca_off":
                        DCA_ENABLED = False
                        tg("⏸ <b>DCA wylaczone</b>")
                    elif msg == "/dca_on":
                        DCA_ENABLED = True
                        tg("▶️ <b>DCA wlaczone</b>")
                    elif msg == "/status":
                        acc = get_account()
                        tot = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                        fr = float(acc.get("available", 0)) if isinstance(acc, dict) else 0
                        pnl = float(acc.get("unrealised_pnl", 0)) if isinstance(acc, dict) else 0
                        crash = is_market_crashing()
                        ords = ""
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            o = get_orders(sym)
                            if o:
                                b = len([x for x in o if int(x.get("size", 0)) > 0])
                                s = len([x for x in o if int(x.get("size", 0)) < 0])
                                ords += f"\n{cfg['icon']} {sym}: {b}x buy / {s}x sell"
                        margin_icon = "🟢" if fr > 150 else ("🟡" if fr > 80 else "🔴")
                        pnl_icon = "📈" if pnl >= 0 else "📉"
                        tg(
                            f"╔══ 📊 <b>STATUS</b> ══╗\n"
                            f"🤖 Bot: {'ON ✅' if BOT_ACTIVE else 'OFF 🛑'}  "
                            f"DCA: {'ON ✅' if DCA_ENABLED else 'OFF ⏸'}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"💰 Equity:  <b>{tot:.2f} USDT</b>\n"
                            f"{margin_icon} Margin:  <b>{fr:.2f} USDT</b>  {bar(fr/tot if tot > 0 else 0)}\n"
                            f"{pnl_icon} PnL:     <b>{pnl:+.2f} USDT</b>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🇬🇧 London: {'🟢 AKTYWNA' if is_london_session() else '⚫ Poza sesja'}\n"
                            f"🚨 Crash:  {'TAK ⚠️' if crash else 'NIE ✅'}\n"
                            f"📋 Zlecenia:{ords if ords else ' Brak'}\n"
                            f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝"
                        )
                    elif msg == "/pozycje":
                        p_data = get_positions()
                        lines = ["╔══ 📦 <b>POZYCJE</b> ══╗"]
                        found = False
                        if isinstance(p_data, list):
                            for p in p_data:
                                sz = float(p.get("size", 0))
                                if sz > 0:
                                    found = True
                                    sym = p["contract"]
                                    entry = float(p["entry_price"])
                                    ppnl = float(p.get("unrealised_pnl", 0))
                                    price = get_price(sym)
                                    pct = (price - entry) / entry * 100 if entry > 0 else 0
                                    cfg = CONFIG.get(sym, {})
                                    pnl_icon = "📈" if ppnl >= 0 else "📉"
                                    lines.append(
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{cfg.get('icon', '•')} <b>{sym}</b>\n"
                                        f"  Pozycja: {sz:.0f}k  Moonbag: {cfg.get('min_moonbag', 0)}k\n"
                                        f"  Entry:   {entry:.2f}\n"
                                        f"  Teraz:   {price:.2f} ({pct:+.1f}%) {bar(abs(pct)/20)}\n"
                                        f"  {pnl_icon} PnL: <b>{ppnl:+.2f} USDT</b>"
                                    )
                        if not found:
                            lines.append("━━━━━━━━━━━━━━━\nBrak otwartych pozycji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))
                    elif msg == "/sl":
                        p_data = get_positions()
                        lines = ["╔══ 🛡 <b>STOP LOSS</b> ══╗"]
                        found = False
                        if isinstance(p_data, list):
                            for p in p_data:
                                sz = float(p.get("size", 0))
                                if sz > 0:
                                    found = True
                                    sym = p["contract"]
                                    entry = float(p["entry_price"])
                                    price = get_price(sym)
                                    cfg = CONFIG.get(sym, {})
                                    profit_pct = (price - entry) / entry if entry > 0 else 0
                                    if profit_pct >= 0.03:
                                        sl = entry
                                        label = "Breakeven 🔒"
                                    else:
                                        sl = entry * (1 - cfg.get("sl_pct", 0.08))
                                        label = f"Standard -{cfg.get('sl_pct', 0.08)*100:.0f}%"
                                    dist = (price - sl) / price * 100
                                    placed = "TAK ✅" if sl_placed.get(sym) else "NIE ❌"
                                    lines.append(
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{cfg.get('icon', '•')} <b>{sym}</b>\n"
                                        f"  Typ:     {label}\n"
                                        f"  SL @     {sl:.2f}\n"
                                        f"  Dystans: {dist:.1f}% {bar(dist/15)}\n"
                                        f"  Placed:  {placed}"
                                    )
                        if not found:
                            lines.append("━━━━━━━━━━━━━━━\nBrak pozycji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))
                    elif msg == "/trailing":
                        lines = ["╔══ 📈 <b>TRAILING TP</b> ══╗"]
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            price = get_price(sym)
                            ref = trailing_ref.get(sym, 0)
                            sells = [o for o in get_orders(sym) if int(o.get("size", 0)) < 0]
                            tp_p = float(sells[0]["price"]) if sells else 0
                            if ref > 0 and price > 0:
                                rise = (price - ref) / ref * 100
                                trigger = cfg["trailing_trigger"] * 100
                                brakuje = max(0, trigger - rise)
                                progress = min(rise / trigger, 1.0) if trigger > 0 else 0
                                tp_str = fmt_price(tp_p, sym) if tp_p else "Brak"
                                lines.append(
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"{cfg['icon']} <b>{sym}</b>\n"
                                    f"  Cena:    {price:.2f}\n"
                                    f"  Ref:     {ref:.2f}\n"
                                    f"  Wzrost:  +{rise:.1f}% {bar(progress)}\n"
                                    f"  Trigger: +{trigger:.0f}% (brakuje {brakuje:.1f}%)\n"
                                    f"  TP @     {tp_str}"
                                )
                            else:
                                lines.append(f"━━━━━━━━━━━━━━━\n{cfg['icon']} {sym}: brak pozycji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))
                    elif msg == "/sweep":
                        lines = ["╔══ 🎯 <b>LONDON SWEEP</b> ══╗"]
                        lines.append(f"Sesja: {'🟢 AKTYWNA' if is_london_session() else '⚫ Poza sesja'}")
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            zone = session_zones.get(sym, {})
                            price = get_price(sym)
                            is_sw, reason = detect_sweep(sym, price)
                            lines.append(
                                f"━━━━━━━━━━━━━━━\n"
                                f"{cfg['icon']} <b>{sym}</b>\n"
                                f"  Cena:  {price:.2f}\n"
                                f"  Low:   {zone.get('low', 0):.2f}\n"
                                f"  High:  {zone.get('high', 0):.2f}\n"
                                f"  Status: {'🎯 SWEEP!' if is_sw else '⬜ Brak'}"
                            )
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))
                    elif msg.startswith("/reset_dca"):
                        parts = msg.split()
                        sym_arg = parts[1].upper() if len(parts) > 1 else ""
                        if not sym_arg:
                            tg("Uzycie: /reset_dca BTC, ETH, SOL lub ALL")
                        else:
                            if sym_arg == "ALL":
                                symbols = [s for s, c in CONFIG.items() if c["active"]]
                            else:
                                full = sym_arg if "_USDT" in sym_arg else sym_arg + "_USDT"
                                symbols = [full] if full in CONFIG else []
                            if not symbols:
                                tg(f"Nieznany symbol: {sym_arg}")
                            else:
                                acc2 = get_account()
                                eq2 = float(acc2.get("total", 300)) if isinstance(acc2, dict) else 300
                                for sym in symbols:
                                    price2 = get_price(sym)
                                    if price2 > 0:
                                        do_reset_grid(sym, price2, eq2, "reczny /reset_dca")

                    elif msg == "/help":
                        tg(
                            "╔══ 📖 <b>KOMENDY</b> ══╗\n"
                            "━━━━━━━━━━━━━━━\n"
                            "📊 /status    — equity, margin, PnL\n"
                            "📦 /pozycje   — otwarte pozycje\n"
                            "🛡 /sl        — stop lossy\n"
                            "📈 /trailing  — trailing TP\n"
                            "🎯 /sweep     — London Sweep\n"
                            "━━━━━━━━━━━━━━━\n"
                            "▶️ /start     — uruchom bota\n"
                            "🛑 /stop      — zatrzymaj bota\n"
                            "✅ /dca_on   — wlacz DCA\n"
                            "⏸ /dca_off   — wylacz DCA\n"
                            "🔄 /reset_dca BTC/ETH/SOL/ALL\n"
                            "╚══════════════╝"
                        )
        except Exception as e:
            print(f"  TG ERR {e}")
        time.sleep(2)

def do_reset_grid(symbol, curr_price, equity, reason="manual"):
    cfg = CONFIG[symbol]
    orders = get_orders(symbol)
    buys = [o for o in orders if int(o.get("size", 0)) > 0]
    for o in buys:
        gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
        time.sleep(0.2)
    added = 0
    levels = []
    for i in range(1, cfg["dca_levels"] + 1):
        target = curr_price * (1 - cfg["grid_step"] * i)
        qty = fmt_size(get_dynamic_size(symbol, equity, curr_price))
        res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": qty,
            "price": fmt_price(target, symbol), "tif": "gtc",
        })
        if res.get("id"):
            added += 1
            levels.append(f"  L{i}: {fmt_price(target, symbol)} x{qty}k")
        time.sleep(0.5)
    tg(
        f"🔄 <b>RESET SIATKI</b>\n"
        f"{cfg['icon']} {symbol}\n"
        f"Powod: {reason}\n"
        f"Nowa ref: {curr_price:.2f}\n"
        f"Usunieto: {len(buys)} | Dodano: {added}\n"
        + "\n".join(levels)
    )
    print(f"  GRID RESET {symbol} @ {curr_price:.2f} ({reason})")

def manage_sl(symbol, cfg, size, entry, curr_price, equity):
    if size <= 0 or entry <= 0:
        return
    profit_pct = (curr_price - entry) / entry
    dynamic_base = get_dynamic_size(symbol, equity, curr_price)
    if profit_pct >= 0.03:
        target_sl = entry
        label = "Breakeven"
    else:
        target_sl = entry * (1 - cfg["sl_pct"])
        label = f"Standard -{cfg['sl_pct']*100:.0f}%"
    existing = get_price_orders(symbol)
    for o in existing:
        p = float(o.get("trigger", {}).get("price", 0))
        # Jesli istniejacy SL jest WYZSZY niz nowy (lepszy) - zostaw go
        if p > 0 and abs(p - target_sl) / target_sl < 0.005:
            sl_placed[symbol] = True
            return
    if not existing:
        sl_placed[symbol] = False
    for o in existing:
        gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{o['id']}")
        time.sleep(0.2)
    body = {
        "initial": {
            "contract": symbol, "size": -int(size),
            "price": "0", "tif": "ioc", "reduce_only": True,
        },
        "trigger": {
            "strategy_type": 0, "price_type": 0,
            "price": fmt_price(target_sl, symbol),
            "rule": 2, "expiration": 604800,
        }
    }
    res = gate_request("POST", "/api/v4/futures/usdt/price_orders", body=body)
    if res.get("id"):
        sl_placed[symbol] = True
        dist = (curr_price - target_sl) / curr_price * 100
        tg(
            f"🛡 <b>SL USTAWIONY</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Typ:     {label}\n"
            f"  SL @     {fmt_price(target_sl, symbol)}\n"
            f"  Dystans: {dist:.1f}%"
        )
        print(f"    SL {symbol} @ {target_sl:.2f} ({label})")
    else:
        print(f"    SL FAIL {symbol}: {res.get('label', '?')}")

def check_executed(symbol, cfg, size, entry, price):
    prev = last_size.get(symbol, -1)
    if prev < 0:
        last_size[symbol] = size
        return

    # Pozycja WZROSLA – weszlo zlecenie DCA
    if size > prev:
        added = size - prev
        mult = cfg["contract_multiplier"]
        val = added * mult * price
        tg(
            f"📥 <b>DCA WYKONANY</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Kupiono:  +{added:.0f}k @ {price:.2f}\n"
            f"  Wartosc:  ~{val:.2f} USDT\n"
            f"  Pozycja:  {prev:.0f}k → {size:.0f}k\n"
            f"  Entry:    {entry:.2f}\n"
            f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
        )

    # Pozycja ZMNIEJSZYLA SIE – TP lub SL
    elif prev > size >= 0:
        closed = prev - size
        if closed > 0:
            mult = cfg["contract_multiplier"]
            pnl = closed * mult * (price - entry) if entry > 0 else 0
            pct = (price - entry) / entry * 100 if entry > 0 else 0
            is_tp = price >= entry * 0.99
            label = "TP WYKONANY" if is_tp else "SL WYKONANY"
            tg(
                f"{'╔══ ✅' if is_tp else '╔══ 🔴'} <b>{label}</b> ══╗\n"
                f"{cfg['icon']} {symbol}\n"
                f"  Zamknieto: {closed:.0f}k\n"
                f"  Cena:      {price:.2f}\n"
                f"  Entry:     {entry:.2f} ({pct:+.1f}%)\n"
                f"  PnL:       <b>{pnl:+.2f} USDT</b>\n"
                f"  Pozostaje: {size:.0f}k\n"
                f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
            )
            if size == 0:
                sl_placed[symbol] = False
                trailing_ref.pop(symbol, None)

    last_size[symbol] = size

def place_tp(symbol, cfg, tradeable, curr_price, entry):
    tp_from_entry = entry * (1 + cfg["tp_pct"]) if entry > 0 else 0
    tp_from_now = curr_price * (1 + cfg["tp_pct_from_now"])
    target_tp = max(tp_from_entry, tp_from_now)
    if target_tp <= curr_price * (1 + cfg["tp_pct_from_now"] * 0.5):
        target_tp = curr_price * (1 + cfg["tp_pct_from_now"])
    tp_str = fmt_price(target_tp, symbol)
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": -fmt_size(tradeable),
        "price": tp_str, "tif": "gtc", "reduce_only": True,
    })
    if res.get("id"):
        pct = (target_tp - curr_price) / curr_price * 100
        trailing_ref[symbol] = curr_price
        return target_tp, pct
    print(f"    TP FAIL {symbol}: {res.get('label', '?')}")
    return 0, 0

def manage_tp(symbol, cfg, size, entry, curr_price, sells):
    tradeable = int(size) - cfg["min_moonbag"]
    if tradeable <= 0:
        return
    ref = trailing_ref.get(symbol, 0)

    # Usun duplikaty TP – zostaw tylko najwyzszy (najlepszy)
    if len(sells) > 1:
        sells_sorted = sorted(sells, key=lambda o: float(o.get("price", 0)), reverse=True)
        for o in sells_sorted[1:]:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        print(f"    CLEANUP TP {symbol}: usunieto {len(sells_sorted)-1} duplikatow")
        sells = sells_sorted[:1]

    if not sells:
        tp_price, pct = place_tp(symbol, cfg, tradeable, curr_price, entry)
        if tp_price > 0:
            tg(
                f"🎯 <b>TP USTAWIONY</b>\n"
                f"{cfg['icon']} {symbol}\n"
                f"  Sell:    {tradeable}k\n"
                f"  TP @     {fmt_price(tp_price, symbol)} (+{pct:.1f}%)\n"
                f"  Moonbag: {cfg['min_moonbag']}k 🔒"
            )
    elif ref > 0:
        rise = (curr_price - ref) / ref
        if rise >= cfg["trailing_trigger"]:
            for o in sells:
                gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
                time.sleep(0.2)
            tp_price, pct = place_tp(symbol, cfg, tradeable, curr_price, entry)
            if tp_price > 0:
                tg(
                    f"📈 <b>TRAILING TP</b>\n"
                    f"{cfg['icon']} {symbol}\n"
                    f"  Wzrost:  +{rise*100:.1f}% od {ref:.2f}\n"
                    f"  Nowy TP: {fmt_price(tp_price, symbol)} (+{pct:.1f}%)\n"
                    f"  Moonbag: {cfg['min_moonbag']}k 🔒"
                )
        else:
            sell_p = float(sells[0].get("price", 0))
            brakuje = (cfg["trailing_trigger"] - rise) * 100
            print(f"    TP {symbol} @ {sell_p:.2f} | trailing za {brakuje:.1f}%")
    else:
        trailing_ref[symbol] = curr_price

def reset_grid_if_stale(symbol, cfg, curr_price, buys):
    """Resetuj siatke gdy cena odeszla >5% powyzej najwyzszego buy limitu"""
    if not buys:
        return False
    highest_buy = max(float(o.get("price", 0)) for o in buys)
    if highest_buy <= 0:
        return False
    distance = (curr_price - highest_buy) / curr_price
    if distance > 0.05:
        print(f"    GRID RESET {symbol}: cena {curr_price:.2f} odeszla {distance*100:.1f}% od siatki @ {highest_buy:.2f}")
        for o in buys:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        tg(
            f"🔄 <b>RESET SIATKI</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Cena:      {curr_price:.2f}\n"
            f"  Stara siatka: {highest_buy:.2f} ({distance*100:.1f}% nizej)\n"
            f"  Nowa siatka zostanie postawiona ponizej aktualnej ceny"
        )
        return True
    return False

def manage_dca(symbol, cfg, size, curr_price, buys, free_margin, equity):
    if not DCA_ENABLED:
        return
    # Reset siatki gdy cena odeszla za daleko w gore
    if buys and reset_grid_if_stale(symbol, cfg, curr_price, buys):
        buys = []  # siatka wyczyszczona – postaw nowa ponizej
    if is_market_crashing():
        print(f"    CRASH DCA {symbol} wstrzymane")
        return
    if free_margin < cfg["min_free_margin"] or equity < cfg["min_equity"]:
        return
    # AUTO GRID RESET W GORE
    # Gdy cena jest 5% powyzej najwyzszego buy limitu -> reset siatki wyzej
    if buys:
        highest_buy = max(float(o.get("price", 0)) for o in buys)
        if highest_buy > 0 and curr_price > highest_buy * (1 + cfg["grid_reset_pct"]):
            print(f"    AUTO GRID RESET {symbol}: {curr_price:.2f} > {highest_buy:.2f} +5%")
            do_reset_grid(symbol, curr_price, equity, "auto +5% powyzej siatki")
            return

    # Usun nadmiarowe buy limity jesli jest ich wiecej niz dca_levels
    if len(buys) > cfg["dca_levels"]:
        # Zostaw 5 najblizszych cenie, usun reszte
        buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)), reverse=True)
        to_remove = buys_sorted[cfg["dca_levels"]:]
        for o in to_remove:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        print(f"    CLEANUP {symbol}: usunieto {len(to_remove)} nadmiarowych buy limitow")
        buys = buys_sorted[:cfg["dca_levels"]]

    total_exp = size + sum(int(o.get("size", 0)) for o in buys)
    if total_exp >= cfg["max_contracts"] or len(buys) >= cfg["dca_levels"]:
        return
    is_sweep, sweep_reason = detect_sweep(symbol, curr_price)
    now_ts = time.time()
    scalp_last = sweep_last_notify.get(symbol + "_scalp", 0)
    scalp_ok = (now_ts - scalp_last) > 900
    if is_sweep and size == 0 and scalp_ok:
        sweep_mult = 2.5
        sweep_label = "SCALP"
        sweep_last_notify[symbol + "_scalp"] = now_ts
    elif is_sweep and size > 0:
        sweep_mult = 1.5
        sweep_label = "BOOST"
    else:
        sweep_mult = 1.0
        sweep_label = ""
    needed = cfg["dca_levels"] - len(buys)
    added = 0
    for i in range(1, cfg["dca_levels"] + 1):
        if added >= needed:
            break
        target = curr_price * (1 - cfg["grid_step"] * i)
        if any(abs(target - float(o.get("price", 0))) / target < 0.015 for o in buys):
            continue
        if i == 1 and sweep_mult > 1.0:
            qty = fmt_size(get_dynamic_size(symbol, equity, curr_price) * sweep_mult)
        else:
            qty = fmt_size(get_dynamic_size(symbol, equity, curr_price))
        if total_exp + added + qty > cfg["max_contracts"]:
            qty = max(1, cfg["max_contracts"] - total_exp - added)
            if qty <= 0:
                break
        res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": qty,
            "price": fmt_price(target, symbol), "tif": "gtc",
        })
        if res.get("id"):
            lbl = f"L{i}" if i > 1 else f"L1({sweep_label or 'DCA'})"
            print(f"    DCA {symbol} {lbl} @ {fmt_price(target, symbol)} x{qty}k")
            added += 1
        time.sleep(0.5)

def manage_logic(symbol, cfg, free_margin, equity, all_positions):
    price = get_price(symbol)
    if price <= 0:
        return
    if symbol == "BTC_USDT":
        btc_price_history.append(price)
        if len(btc_price_history) > 10:
            btc_price_history.pop(0)
    pos = next((p for p in all_positions if p["contract"] == symbol), None) if isinstance(all_positions, list) else None
    size = abs(float(pos["size"])) if pos and float(pos.get("size", 0)) != 0 else 0
    entry = float(pos["entry_price"]) if size > 0 else 0
    orders = get_orders(symbol)
    buys = [o for o in orders if int(o.get("size", 0)) > 0]
    sells = [o for o in orders if int(o.get("size", 0)) < 0]
    pct_str = f"{(price-entry)/entry*100:+.1f}%" if entry > 0 else "---"
    print(f"  {cfg['icon']}  {symbol:<10} {price:>9.2f}  poz={size:.0f}k {pct_str}  buy={len(buys)} sell={len(sells)}")
    if size > 0:
        check_executed(symbol, cfg, size, entry, price)
        manage_sl(symbol, cfg, size, entry, price, equity)
        if size > cfg["min_moonbag"]:
            manage_tp(symbol, cfg, size, entry, price, sells)
    manage_dca(symbol, cfg, size, price, buys, free_margin, equity)

def run():
    global BOT_ACTIVE
    threading.Thread(target=listen_telegram, daemon=True).start()
    print("=" * 55)
    print("  FreedomTracker Bot v2.2 Final")
    print("  /help /status /pozycje /sl /trailing /sweep")
    print("=" * 55)
    tg(
        "╔══ 🤖 <b>FreedomTracker v2.2</b> ══╗\n"
        "━━━━━━━━━━━━━━━\n"
        "✅ Stop Loss + Breakeven + Tight Scalp SL\n"
        "✅ Trailing TP (+5% / +3% trigger)\n"
        "✅ DCA siatka 5 poziomow\n"
        "✅ London Sweep (Scalp 2.5x / Boost 1.5x)\n"
        "✅ Crash detection BTC -3%\n"
        "━━━━━━━━━━━━━━━\n"
        "📖 /help — lista komend\n"
        "╚══════════════════╝"
    )
    cycle = 0
    last_zone_h = -1
    starting_equity = 0

    while True:
        cycle += 1
        if BOT_ACTIVE:
            try:
                acc = get_account()
                fr = float(acc.get("available", 0)) if isinstance(acc, dict) else 0
                eq = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                pnl = float(acc.get("unrealised_pnl", 0)) if isinstance(acc, dict) else 0
            except Exception as e:
                print(f"  ERR get_account: {e}")
                time.sleep(20)
                continue




            # Zapamietaj equity startowe


            if starting_equity == 0 and eq > 0:
                starting_equity = eq
                print(f"  Equity startowe: {starting_equity:.2f} USDT")

            if starting_equity > 0 and eq < starting_equity * 0.75:
                BOT_ACTIVE = False
                spadek = round((1 - eq / starting_equity) * 100, 1)
                msg = "🚨 EQUITY GUARD!\n"
                msg += f"Start:  {starting_equity:.2f} USDT\n"
                msg += f"Teraz:  {eq:.2f} USDT\n"
                msg += f"Spadek: -{spadek}%\n"
                msg += "Bot zatrzymany. Wpisz /start aby wznowic."
                tg(msg)
                print(f"  EQUITY GUARD: bot zatrzymany (equity -{spadek}%)")

            if 0 < fr < 80:
                tg(f"⚠️ <b>Uwaga!</b> Free margin: <b>{fr:.2f} USDT</b>")
            if 0 < fr < 50:
                tg(f"🚨 <b>ALARM!</b> Krytyczny margin: <b>{fr:.2f} USDT</b>")
            curr_hour = datetime.utcnow().hour
            if curr_hour != last_zone_h:
                update_session_zones()
                last_zone_h = curr_hour
            if is_london_session():
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    p = get_price(sym)
                    if p <= 0:
                        continue
                    is_sw, reason = detect_sweep(sym, p)
                    if is_sw:
                        last_notif = sweep_last_notify.get(sym, 0)
                        if (time.time() - last_notif) > 900:
                            sweep_last_notify[sym] = time.time()
                            zone = session_zones.get(sym, {})
                            all_pos = get_positions()
                            pos_sw = next((px for px in all_pos if isinstance(all_pos, list) and px["contract"] == sym), None)
                            has_pos = pos_sw and float(pos_sw.get("size", 0)) != 0
                            akcja = "🎯 SCALP 2.5x" if not has_pos else "⚡ DCA BOOST 1.5x"
                            tg(
                                f"🎯 <b>LONDON SWEEP!</b>\n"
                                f"{cfg['icon']} {sym}\n"
                                f"  Cena:   {p:.2f}\n"
                                f"  Low:    {zone.get('low', 0):.2f}\n"
                                f"  Sygnał: {reason}\n"
                                f"  Akcja:  {akcja} 🚀"
                            )
                        else:
                            remaining = int((900 - (time.time() - last_notif)) / 60)
                            print(f"    [SWEEP] {sym} cooldown {remaining} min")
            crash_str = " [CRASH]" if is_market_crashing() else ""
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cykl {cycle} | Eq: {eq:.2f} | Free: {fr:.2f} | PnL: {pnl:+.2f}{crash_str}")
            print("-" * 55)
            try:
                all_pos = get_positions()
            except Exception as e:
                print(f"  ERR get_positions: {e}")
                all_pos = []
            for sym, cfg in CONFIG.items():
                if cfg["active"]:
                    try:
                        manage_logic(sym, cfg, fr, eq, all_pos)
                    except Exception as e:
                        print(f"  ERR manage_logic {sym}: {e}")
            print("-" * 55)
            if cycle % 180 == 0:
                ords = ""
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    o = get_orders(sym)
                    if o:
                        b = len([x for x in o if int(x.get("size", 0)) > 0])
                        s = len([x for x in o if int(x.get("size", 0)) < 0])
                        ords += f"\n{cfg['icon']} {sym}: {b}x buy / {s}x sell"
                tg(
                    f"╔══ 📊 <b>Raport godzinny</b> ══╗\n"
                    f"💰 Equity:  <b>{eq:.2f} USDT</b>\n"
                    f"💵 Wolne:   <b>{fr:.2f} USDT</b>\n"
                    f"📈 PnL:     <b>{pnl:+.2f} USDT</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📋 Zlecenia:{ords if ords else ' Brak'}\n"
                    f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝"
                )
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Pauza...")
        time.sleep(20)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nBot zatrzymany (CTRL+C)")
        tg("🛑 <b>Bot zatrzymany recznie</b>")
    except Exception as e:
        print(f"\nKRYTYCZNY BLAD: {e}")
        tg(f"🚨 <b>KRYTYCZNY BLAD!</b>\n<code>{str(e)[:200]}</code>")
