#!/usr/bin/env python3
import os, time, requests, hmac, hashlib, json, threading
from datetime import datetime
from dotenv import load_dotenv

# --- ŁADOWANIE ZMIENNYCH ---
load_dotenv('/home/barte/.env_freedom')

GATE_KEY       = os.getenv('GATE_API_KEY')
GATE_SECRET    = os.getenv('GATE_SECRET')
TOKEN          = os.getenv('TELEGRAM_TOKEN')
CHAT_ID        = os.getenv('TELEGRAM_CHAT_ID')
BASE_URL       = "https://api.gateio.ws"

# --- ZMIENNE GLOBALNE ---
BOT_ACTIVE      = True
DCA_ENABLED     = True
LAST_UPDATE_ID  = 0
STARTING_EQUITY = 0.0

# Pamięć bota (cache)
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
        "icon": "🟠", "active": True, "min_moonbag": 2, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 20, "risk_per_level": 0.02, "tp_pct": 0.05, "tp_pct_from_now": 0.05,
        "trailing_trigger": 0.03, "sl_pct": 0.08, "price_decimals": 0,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.0001,
    },
    "ETH_USDT": {
        "icon": "🔵", "active": True, "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 15, "risk_per_level": 0.02, "tp_pct": 0.05, "tp_pct_from_now": 0.05,
        "trailing_trigger": 0.03, "sl_pct": 0.08, "price_decimals": 2,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.01,
    },
    "SOL_USDT": {
        "icon": "🟣", "active": True, "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 10, "risk_per_level": 0.02, "tp_pct": 0.05, "tp_pct_from_now": 0.05,
        "trailing_trigger": 0.03, "sl_pct": 0.10, "price_decimals": 2,
        "min_free_margin": 200, "min_equity": 250, "contract_multiplier": 0.1,
    }
}

# --- FUNKCJE POMOCNICZE API ---
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
        return r.json()
    except Exception as e:
        print(f"  REQ ERR {e}")
        return {}

def get_account(): return gate_request("GET", "/api/v4/futures/usdt/accounts")
def get_positions(): return gate_request("GET", "/api/v4/futures/usdt/positions")
def get_price(symbol):
    t = gate_request("GET", "/api/v4/futures/usdt/tickers", {"contract": symbol})
    return float(t[0]["last"]) if isinstance(t, list) and t else 0.0

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

def fmt_price(price, symbol):
    d = CONFIG[symbol]["price_decimals"]
    return str(int(round(price))) if d == 0 else f"{price:.{d}f}"

# --- LOGIKA STEROWANIA ---
def listen_telegram():
    global BOT_ACTIVE, LAST_UPDATE_ID
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", 
                             params={"offset": LAST_UPDATE_ID + 1, "timeout": 30}, timeout=35).json()
            if r.get("ok") and r.get("result"):
                for update in r["result"]:
                    LAST_UPDATE_ID = update["update_id"]
                    msg = update.get("message", {}).get("text", "")
                    if msg == "/stop":
                        BOT_ACTIVE = False
                        tg("🛑 Bot zatrzymany manualnie.")
                    elif msg == "/start":
                        BOT_ACTIVE = True
                        tg("🚀 Bot uruchomiony!")
        except: pass
        time.sleep(2)

def run():
    global BOT_ACTIVE, STARTING_EQUITY
    threading.Thread(target=listen_telegram, daemon=True).start()
    
    print("=== FreedomTracker v2.3 ACTIVE ===")
    tg("✅ <b>Bot wystartował poprawnie!</b>")

    while True:
        if BOT_ACTIVE:
            try:
                acc = get_account()
                if not isinstance(acc, dict): continue
                
                eq = float(acc.get("total", 0))
                fr = float(acc.get("available", 0))
                
                if STARTING_EQUITY == 0 and eq > 0:
                    STARTING_EQUITY = eq
                    print(f"Ustawiono equity startowe: {eq}")

                # BEZPIECZNIK: Spadek o 15% wyłącza bota
                if STARTING_EQUITY > 0 and eq < (STARTING_EQUITY * 0.85):
                    BOT_ACTIVE = False
                    tg(f"🚨 <b>KRYTYCZNY STOP!</b>\nEquity spadło poniżej 85% ({eq:.2f} USDT). Bot zostaje wyłączony!")
                    continue

                # Tutaj miejsce na resztę Twojej logiki (get_positions, manage_sl itd.)
                # Dla oszczędności miejsca wklejam tylko szkielet działania:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: {eq:.2f} | Margin: {fr:.2f}")

            except Exception as e:
                print(f"Błąd pętli: {e}")
        
        time.sleep(20)

if __name__ == "__main__":
    run()
