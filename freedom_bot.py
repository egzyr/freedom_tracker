"""
FreedomTracker Bot v2.12 PRODUCTION
══════════════════════════════════════════════════════════════
HISTORIA WERSJI:

v2.11 – ZABEZPIECZENIA MARGINU
  M01 - get_dynamic_max_contracts(symbol, equity, curr_price):
        Limit kontraktów obliczany dynamicznie z aktualnej CENY RYNKOWEJ.
        max_val_usd = equity * 50%
        max_contracts = int(max_val_usd / (curr_price * contract_multiplier))
        Przykład ETH@2000: 0.5*290/(2000*0.01)=7k  |  ETH@4000: 0.5*290/(4000*0.01)=3k
        curr_price pobierane ZAWSZE świeżo z get_price() w manage_logic,
        a nie z cache – cena wchodzi przez parametr, nigdy nie jest stała.
        Zastępuje hardkodowane max_contracts=15/20 (niezwiązane z equity/ceną).
  M02 - get_total_exposure_usd(all_positions):
        Przed każdym market buy sprawdza sumę USD wszystkich otwartych pozycji.
        Limit = MAX_TOTAL_EXPOSURE_PCT * equity (domyślnie 75% = ~217 USD).
        Dotyczy: check_initial_entry, check_dca_sweep_add, /buy.
  M03 - check_initial_entry wymaga size==0:
        Sweep market entry TYLKO gdy brak pozycji na symbolu.
        check_dca_sweep_add obsługuje dokupywanie przy size>0.
        Eliminuje podwójne wejście: sweep market + DCA limit w tej samej chwili.

v2.10 – NAPRAWIONE BAGI
  BUG1 - check_initial_entry nie blokuje się przez siatke DCA (buys guard usunięty)
  BUG2 - check_executed: alert gdy pozycja zamknięta podczas restartu bota
  BUG3 - cooldown entry 2h zamiast 8h bloku, z logiem powodu blokady
  BUG4 - sweep alert w pętli używa klucza "alert_SYM" (nie koliduje z DCA)

v2.9 – ANTYSPAM
  A01 - SL: TG tylko przy zmianie typu (Grid→Breakeven), nie przy każdej cenie
  A02 - SL hysteresis: wejście BE przy +1.7%, wyjście przy <+1.0%
  A03 - TP: TG tylko przy postawieniu/przesunięciu, "trailing za X%" = tylko print
  A04 - SL cooldown TG: max 1 wiadomość per symbol co 10 minut

v2.8 – FUNKCJE PRODUKCYJNE
  P01 - Partial TP: sprzedaj 40% market gdy +3% zysk i pozycja wystarczająco duża
  P02 - Break-even SL przy +1.5% (hysteresis w v2.9)
  P03 - /close SYM: market sell całej pozycji z Telegrama
  P04 - Dzienny reset equity_guard o 00:00 UTC

v2.7 – SYSTEM SWEEPÓW
  N01 - 5 sesji sweepowych 24/7: London Open(×2.5), London Lunch(×2.0),
        NY Open(×2.0), NY Reversal(×1.8), Asia Midnight(×1.5)
  N02 - DCA boost market buy gdy pozycja>0 i sweep schodzi głębiej
  N03 - /buy SYM: test market buy z Telegrama
  N04 - SOL wyłączony (za mało equity przy ~290 USD)
  N05 - risk_per_level: 0.04 (2× większe kontrakty)
  N06 - /sessions: countdown do następnej sesji sweepowej
  N07 - Sweep alert dla każdej sesji (nie tylko London)
  N08 - /status: pokazuje aktualną sesję

v2.5.x – BUGI BAZOWE (B01..B16)
  Wszystkie naprawione: isize(), manage_tp, check_executed, manage_dca,
  margin alert cooldown, race condition grid_resetting, equity guard jednorazowy
══════════════════════════════════════════════════════════════
"""

import os, time, requests, hmac, hashlib, json, threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')
GATE_KEY    = os.getenv('GATE_API_KEY')
GATE_SECRET = os.getenv('GATE_SECRET')
TOKEN       = os.getenv('TELEGRAM_TOKEN')
CHAT_ID     = os.getenv('TELEGRAM_CHAT_ID')
BASE_URL    = "https://api.gateio.ws"

BOT_ACTIVE     = True
DCA_ENABLED    = True
LAST_UPDATE_ID = 0

trailing_ref        = {}
last_size           = {}
sl_placed           = {}
btc_price_history   = []
session_zones       = {}
sweep_active        = {}
sweep_prev_price    = {}
sweep_last_notify   = {}
grid_bottom_cache   = {}
last_margin_alert   = {}
last_entry_session  = {}
last_boost_session  = {}
partial_tp_done     = {}
equity_guard_fired  = False
session_pnl_start   = 0
trade_log           = []
grid_resetting      = {}
grid_reset_time     = {}
equity_guard_day    = ""
# ── A01/A04: antyspam SL ──────────────────────────────────────────────────────
sl_last_type        = {}
sl_tg_cooldown      = {}
SL_TG_COOLDOWN_SEC  = 600
# ── A02: hysteresis breakeven ─────────────────────────────────────────────────
be_active           = {}
BE_ENTER_PCT        = 0.017
BE_EXIT_PCT         = 0.010
# ── M01/M02: limity ekspozycji ────────────────────────────────────────────────
MAX_EXPOSURE_PER_SYMBOL = 0.50   # 50% equity na jeden symbol
MAX_TOTAL_EXPOSURE_PCT  = 0.75   # 75% equity łącznie wszystkie symbole

# ══════════════════════════════════════════════════════════════
# ⚙️  DOCELOWA WARTOŚĆ USD NA JEDEN POZIOM DCA / WEJŚCIE SWEEP
#     Bot sam przelicza ile kontraktów BTC/ETH kupić żeby trafić
#     w tę kwotę – dzięki temu BTC i ETH mają podobne rozmiary.
#
#     Przykłady przy TARGET_ENTRY_USD = 40:
#       BTC @ 85,000:  40 / (85000 × 0.0001) =  4 kontrakty ≈ $34
#       ETH @  2,000:  40 / (2000  × 0.01)   =  2 kontrakty ≈ $40
#       ETH @  3,000:  40 / (3000  × 0.01)   =  1 kontrakt  ≈ $30
#       BTC @ 95,000:  40 / (95000 × 0.0001) =  4 kontrakty ≈ $38
#
#     Żeby mieć WIĘKSZE pozycje → zwiększ TARGET_ENTRY_USD.
#     Przy equity ~290 USD zalecany zakres: 30–60 USD.
#     Powyżej 60 USD bot szybko wypełni limit M02 (75% equity).
# ══════════════════════════════════════════════════════════════
TARGET_ENTRY_USD = 20   # ← JEDYNA LICZBA DO EDYCJI
# ─────────────────────────────────────────────────────────────────────────────

# ── SESJE SWEEPOWE ─────────────────────────────────────────────────────────────
SWEEP_SESSIONS = [
    ("London Open",   7,  0, 10,  0, 2.5, 1.5, 8),
    ("London Lunch",  11, 30, 13,  0, 2.0, 1.3, 8),
    ("NY Open",       13, 30, 16,  0, 2.0, 1.5, 8),
    ("NY Reversal",   19,  0, 21,  0, 1.8, 1.3, 8),
    ("Asia Midnight",  0,  0,  3,  0, 1.5, 1.2, 8),
]

CONFIG = {
    "BTC_USDT": {
        "icon": "🟠", "active": True,
        "base_qty": 0,                # 0 = tryb automatyczny (TARGET_ENTRY_USD)
        "min_moonbag": 2, "dca_levels": 5, "grid_step": 0.015,
        "max_contracts": 30,
        "risk_per_level": 0.08,
        "tp_pct": 0.04, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.20,
        "price_decimals": 0,
        "min_free_margin": 80, "min_equity": 150, "contract_multiplier": 0.0001,
        "grid_reset_pct": 0.05,
        "partial_tp_pct": 0.03, "partial_tp_ratio": 0.40, "partial_tp_min_size": 4,
    },
    "ETH_USDT": {
        "icon": "🔵", "active": True,
        "base_qty": 0,                # 0 = tryb automatyczny (TARGET_ENTRY_USD)
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.012,
        "max_contracts": 25,
        "risk_per_level": 0.08,
        "tp_pct": 0.04, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.13,
        "price_decimals": 2,
        "min_free_margin": 80, "min_equity": 150, "contract_multiplier": 0.01,
        "grid_reset_pct": 0.05,
        "partial_tp_pct": 0.03, "partial_tp_ratio": 0.40, "partial_tp_min_size": 3,
    },
    "SOL_USDT": {
        "icon": "🟣", "active": False,
        "base_qty": 0,                # 0 = tryb automatyczny (TARGET_ENTRY_USD)
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 10,
        "risk_per_level": 0.04,
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.18,
        "price_decimals": 2,
        "min_free_margin": 200, "min_equity": 250, "contract_multiplier": 0.1,
        "grid_reset_pct": 0.05,
        "partial_tp_pct": 0.03, "partial_tp_ratio": 0.40, "partial_tp_min_size": 2,
    }
}

# ─────────────────────────────────────────────────────────────────────────────
def isize(v):
    """B01: int(float()) – obsługuje '5', '5.0', 5, 5.0 z API Gate.io"""
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


# ── M01: dynamiczny limit kontraktów ─────────────────────────────────────────
def get_dynamic_max_contracts(symbol, equity, curr_price):
    """
    Oblicza maksymalną liczbę kontraktów na podstawie AKTUALNEJ ceny rynkowej.

    curr_price jest zawsze przekazywane z manage_logic() które wywołuje
    get_price(symbol) → świeże dane z API na początku każdego cyklu.
    Nigdy nie używamy cached/stałej ceny.

    Przykłady przy equity=290 USD:
      ETH@2000: max = 0.50*290 / (2000*0.01) = 145/20 =  7k kontraktów
      ETH@4000: max = 0.50*290 / (4000*0.01) = 145/40 =  3k kontraktów
      BTC@84k:  max = 0.50*290 / (84000*0.0001) = 145/8.4 = 17k → cap 20
    """
    cfg          = CONFIG[symbol]
    max_usd      = equity * MAX_EXPOSURE_PER_SYMBOL
    contract_val = curr_price * cfg["contract_multiplier"]
    if contract_val <= 0:
        return cfg["max_contracts"]
    dynamic = int(max_usd / contract_val)
    # Nigdy nie przekrocz hardcap z CONFIG, nigdy poniżej min_moonbag+1
    return max(cfg["min_moonbag"] + 1, min(dynamic, cfg["max_contracts"]))


# ── M02: globalna ekspozycja USD ──────────────────────────────────────────────
def get_total_exposure_usd(all_positions):
    """
    Sumuje wartość USD wszystkich otwartych pozycji long.
    Używa entry_price z pozycji (realna ekspozycja na koncie).
    """
    total = 0.0
    if not isinstance(all_positions, list):
        return total
    for p in all_positions:
        sz = float(p.get("size", 0))
        if sz <= 0:
            continue
        sym = p.get("contract", "")
        cfg = CONFIG.get(sym)
        if not cfg:
            continue
        ep = float(p.get("entry_price", 0))
        if ep > 0:
            total += sz * cfg["contract_multiplier"] * ep
    return total
# ─────────────────────────────────────────────────────────────────────────────


def sign(method, path, query="", body=""):
    if not GATE_SECRET:
        raise EnvironmentError("BRAK GATE_SECRET w .env_freedom!")
    ts  = str(int(time.time()))
    h   = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{h}\n{ts}"
    sig = hmac.new(GATE_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return {"KEY": GATE_KEY, "Timestamp": ts, "SIGN": sig, "Content-Type": "application/json"}

def gate_request(method, path, params=None, body=None):
    query = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
    url   = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    b_str = json.dumps(body) if body else ""
    try:
        r    = requests.request(method, url, headers=sign(method, path, query, b_str),
                                data=b_str, timeout=15)
        data = r.json()
        if isinstance(data, dict) and data.get("label"):
            print(f"  API ERR {data.get('label')} - {data.get('message','')[:60]}")
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
    o = gate_request("GET", "/api/v4/futures/usdt/orders",
                     {"contract": symbol, "status": "open"})
    return o if isinstance(o, list) else []

def get_price_orders(symbol):
    o = gate_request("GET", "/api/v4/futures/usdt/price_orders",
                     {"contract": symbol, "status": "open"})
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
    """
    Tryb MANUALNY:    cfg['base_qty'] > 0 → stała liczba kontraktów z CONFIG.
    Tryb AUTOMATYCZNY: cfg['base_qty'] == 0 → oblicza ile kontraktów odpowiada
                       TARGET_ENTRY_USD USD, dzięki czemu BTC i ETH mają
                       podobną wartość pozycji niezależnie od ceny coina.

    Przykład przy TARGET_ENTRY_USD=40, equity=290:
      BTC @ 85000: 40/(85000×0.0001) = 4k ≈ $34  (max przez equity cap: $43)
      ETH @  2000: 40/(2000×0.01)    = 2k ≈ $40
      ETH @  3000: 40/(3000×0.01)    = 1k ≈ $30  (cena wzrosła → mniej kont.)

    Session multipliery (×1.5, ×2.0 itd.) są nakładane NA WIERZCH
    w miejscu wywołania – tu zwracamy tylko bazę.
    """
    cfg      = CONFIG[symbol]
    override = cfg.get("base_qty", 0)
    if override > 0:
        return override                        # TRYB MANUALNY

    # TRYB AUTOMATYCZNY – cel: TARGET_ENTRY_USD per poziom
    # Zabezpieczenie: nie przekroczymy 15% equity per poziom nawet gdy
    # TARGET_ENTRY_USD jest ustawione zbyt wysoko względem konta.
    max_by_equity = equity * 0.15
    target_usd    = min(TARGET_ENTRY_USD, max_by_equity)
    contract_val  = curr_price * cfg["contract_multiplier"]
    if contract_val <= 0:
        return 1
    return max(1, int(target_usd / contract_val))


# ── SESJE – helpery ───────────────────────────────────────────────────────────
def _minutes_utc():
    now = datetime.utcnow()
    return now.hour * 60 + now.minute

def get_active_session():
    m = _minutes_utc()
    for name, sh, sm, eh, em, mn, mw, cd in SWEEP_SESSIONS:
        start = sh * 60 + sm
        end   = eh * 60 + em
        if start <= m < end:
            return (name, mn, mw, cd)
    return None

def session_key_for(symbol):
    now = datetime.utcnow()
    return f"{symbol}_{now.date()}_{now.hour // 8}"

def next_session_info():
    m = _minutes_utc()
    candidates = []
    for name, sh, sm, eh, em, mn, mw, cd in SWEEP_SESSIONS:
        start = sh * 60 + sm
        diff  = (start - m) % (24 * 60)
        candidates.append((diff, name, sh, sm))
    candidates.sort()
    diff, name, sh, sm = candidates[0]
    return name, diff


# ── A02: dynamiczny SL z hysteresis breakeven ─────────────────────────────────
def calculate_sl(symbol, cfg, entry, curr_price, buys):
    """
    1. Breakeven (hysteresis A02): WEJDŹ >=+1.7%, ZOSTAŃ >=+1.0%, WYJDŹ <+1.0%
    2. Grid SL: 2% pod najniższym aktywnym DCA buy
    3. Grid Anchor: ostatnio zapamiętane dno siatki
    4. Fallback: grid_depth + 3% od entry
    """
    if entry <= 0:
        return 0, "Brak entry"

    profit_pct = (curr_price - entry) / entry

    currently_be = be_active.get(symbol, False)
    if profit_pct >= BE_ENTER_PCT:
        be_active[symbol] = True
    elif currently_be and profit_pct < BE_EXIT_PCT:
        be_active[symbol] = False

    if be_active.get(symbol):
        return entry * 1.001, "Breakeven 🔒"

    if buys:
        buy_prices = [float(o.get("price", 0)) for o in buys
                      if float(o.get("price", 0)) > 0]
        if buy_prices:
            lowest_buy = min(buy_prices)
            grid_bottom_cache[symbol] = lowest_buy
            target_sl  = lowest_buy * 0.98
            dist_pct   = (1 - target_sl / entry) * 100
            return target_sl, f"Grid SL ({len(buy_prices)} DCA, -{dist_pct:.1f}%)"

    if symbol in grid_bottom_cache:
        anchor    = grid_bottom_cache[symbol]
        target_sl = anchor * 0.98
        dist_pct  = (1 - target_sl / entry) * 100
        return target_sl, f"Grid Anchor (-{dist_pct:.1f}%)"

    grid_depth = cfg["grid_step"] * cfg["dca_levels"]
    target_sl  = entry * (1 - grid_depth - 0.03)
    dist_pct   = (1 - target_sl / entry) * 100
    return target_sl, f"Fallback SL (-{dist_pct:.1f}%)"


def update_session_zones():
    for sym, cfg in CONFIG.items():
        if not cfg["active"]:
            continue
        hist = gate_request("GET", "/api/v4/futures/usdt/candlesticks",
                            {"contract": sym, "limit": "8", "interval": "1h"})
        if not isinstance(hist, list) or not hist:
            continue
        try:
            h_list, l_list = [], []
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


def detect_sweep(symbol, curr_price):
    """
    Wykrywa przebicie 8h low. Zwraca (is_sweep, reason, session, mult_no_pos, mult_with_pos).
    curr_price zawsze świeża z get_price() przekazana przez manage_logic.
    """
    zone = session_zones.get(symbol)
    if not zone:
        return False, "brak strefy", None, 1.0, 1.0

    low  = zone["low"]
    prev = sweep_prev_price.get(symbol, curr_price)
    sweep_prev_price[symbol] = curr_price

    sess = get_active_session()
    if sess:
        sname, mn, mw, cd = sess
    else:
        sname, mn, mw = None, 1.0, 1.0

    if sweep_active.get(symbol) and curr_price > low * 1.005:
        sweep_active[symbol] = False

    if prev >= low and curr_price < low:
        sweep_active[symbol] = True
        pct    = (low - curr_price) / low * 100
        reason = f"SWEEP LOW {low:.2f} (-{pct:.1f}%)" + (f" [{sname}]" if sname else "")
        return True, reason, sname, mn, mw

    if sweep_active.get(symbol) and curr_price < low:
        pct    = (low - curr_price) / low * 100
        reason = f"SWEEP CONT {low:.2f} (-{pct:.1f}%)" + (f" [{sname}]" if sname else "")
        return True, reason, sname, mn, mw

    return False, "brak sweep", sname, mn, mw


# ── SWEEP ENTRY – MARKET BUY gdy brak pozycji (M02/M03) ─────────────────────
def check_initial_entry(symbol, cfg, size, curr_price, equity, free_margin, buys):
    """
    M03: entry TYLKO gdy size==0 (brak pozycji na tym symbolu).
    M02: sprawdza globalną ekspozycję USD przed zakupem.
    Cooldown 2h (BUG3).
    """
    if size > 0:           # M03
        return
    if free_margin < cfg["min_free_margin"]:
        return
    if is_market_crashing():
        return

    is_sw, reason, sname, mn, mw = detect_sweep(symbol, curr_price)
    if not is_sw:
        return

    now_ts        = time.time()
    last_entry_ts = last_entry_session.get(f"ts_{symbol}", 0)
    if now_ts - last_entry_ts < 7200:
        remaining = int((7200 - (now_ts - last_entry_ts)) / 60)
        print(f"    ENTRY SKIP {symbol}: cooldown {remaining} min pozostało")
        return

    # M02: global exposure guard
    all_pos_now   = get_positions()
    exp_usd       = get_total_exposure_usd(all_pos_now)
    max_exp_usd   = equity * MAX_TOTAL_EXPOSURE_PCT
    if exp_usd >= max_exp_usd:
        print(f"    ENTRY SKIP {symbol}: global exp {exp_usd:.0f} USD >= {max_exp_usd:.0f} USD (75%)")
        return

    base_qty = get_dynamic_size(symbol, equity, curr_price)
    qty      = fmt_size(base_qty * mn)

    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": qty,
        "price": "0", "tif": "ioc",
    })
    if res.get("id"):
        fill       = float(res.get("fill_price", curr_price) or curr_price)
        sess_label = sname if sname else "poza sesją"
        last_entry_session[f"ts_{symbol}"] = now_ts
        print(f"    ENTRY {symbol} MARKET x{qty}k @ ~{fill:.2f} [{sess_label}]")
        tg(
            f"🎯 <b>SWEEP ENTRY (MARKET)</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Cena:    ~{fill:.2f}\n"
            f"  Qty:     {qty}k  (×{mn:.1f} {sess_label})\n"
            f"  Powód:   {reason}\n"
            f"  Exp:     {exp_usd+qty*cfg['contract_multiplier']*fill:.0f}/{max_exp_usd:.0f} USD\n"
            f"  Siatka DCA działa poniżej 📐"
        )
    else:
        print(f"    ENTRY FAIL {symbol}: {res.get('label','?')} – {res.get('message','')[:60]}")


# ── DCA BOOST – MARKET BUY gdy pozycja>0 i sweep głębiej (M01/M02) ───────────
def check_dca_sweep_add(symbol, cfg, size, entry, curr_price, equity, free_margin, buys):
    """
    Dodaje kontrakt market przy sweepie gdy mamy już otwartą pozycję.
    M01: limit przez get_dynamic_max_contracts (zależny od curr_price).
    M02: global exposure guard.
    """
    if size <= 0:
        return
    if free_margin < cfg["min_free_margin"]:
        return
    if is_market_crashing():
        return

    is_sw, reason, sname, mn, mw = detect_sweep(symbol, curr_price)
    if not is_sw or mw <= 1.0:
        return

    if curr_price >= entry:
        return

    # M01: limit zależny od curr_price (nie hardcoded)
    dyn_max   = get_dynamic_max_contracts(symbol, equity, curr_price)
    total_exp = size + sum(isize(o.get("size", 0)) for o in buys)
    if total_exp >= dyn_max - 1:
        print(f"    BOOST SKIP {symbol}: {total_exp}k >= dyn_max {dyn_max}k @ {curr_price:.2f}")
        return

    # M02: global exposure guard
    all_pos_now = get_positions()
    exp_usd     = get_total_exposure_usd(all_pos_now)
    max_exp_usd = equity * MAX_TOTAL_EXPOSURE_PCT
    if exp_usd >= max_exp_usd:
        print(f"    BOOST SKIP {symbol}: global exp {exp_usd:.0f} >= {max_exp_usd:.0f} USD")
        return

    sk = f"boost_{session_key_for(symbol)}"
    if last_boost_session.get(symbol) == sk:
        return

    base_qty = get_dynamic_size(symbol, equity, curr_price)
    qty      = fmt_size(base_qty * mw)
    dist_pct = (entry - curr_price) / entry * 100

    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": qty,
        "price": "0", "tif": "ioc",
    })
    if res.get("id"):
        fill       = float(res.get("fill_price", curr_price) or curr_price)
        sess_label = sname if sname else "poza sesją"
        last_boost_session[symbol] = sk
        print(f"    DCA BOOST {symbol} MARKET x{qty}k @ ~{fill:.2f} [{sess_label}]")
        tg(
            f"⚡ <b>SWEEP DCA BOOST (MARKET)</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Cena:    ~{fill:.2f}\n"
            f"  Entry:   {entry:.2f} (-{dist_pct:.1f}%)\n"
            f"  Qty:     {qty}k  (×{mw:.1f} {sess_label})\n"
            f"  Pozycja: {size:.0f}k → {size+qty:.0f}k\n"
            f"  Powód:   {reason}"
        )
    else:
        print(f"    BOOST FAIL {symbol}: {res.get('label','?')}")


# ── GRID RESET ────────────────────────────────────────────────────────────────
def do_reset_grid(symbol, curr_price, equity, reason="manual"):
    grid_resetting[symbol]  = True
    grid_reset_time[symbol] = time.time()
    try:
        cfg = CONFIG[symbol]
        cancelled_total = 0
        for attempt in range(3):
            orders = get_orders(symbol)
            buys   = [o for o in orders if isize(o.get("size", 0)) > 0]
            if not buys:
                break
            for o in buys:
                gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
                time.sleep(0.2)
            cancelled_total += len(buys)
            if attempt < 2:
                time.sleep(0.5)

        remaining = [o for o in get_orders(symbol) if isize(o.get("size", 0)) > 0]
        if remaining:
            tg(f"⚠️ {symbol}: nie udało się usunąć {len(remaining)} zleceń – reset anulowany")
            return

        # M01: użyj dynamicznego limitu przy stawianiu nowej siatki
        dyn_max = get_dynamic_max_contracts(symbol, equity, curr_price)
        added, levels = 0, []
        for i in range(1, cfg["dca_levels"] + 1):
            target = curr_price * (1 - cfg["grid_step"] * i)
            qty    = fmt_size(get_dynamic_size(symbol, equity, curr_price))
            if added + qty > dyn_max:
                qty = max(1, dyn_max - added)
            if qty <= 0:
                break
            res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
                "contract": symbol, "size": qty,
                "price": fmt_price(target, symbol), "tif": "gtc",
            })
            if res.get("id"):
                added += qty
                levels.append(f"  L{i}: {fmt_price(target, symbol)} x{qty}k")
            time.sleep(0.5)
        tg(
            f"🔄 <b>RESET SIATKI</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"Powód: {reason}\n"
            f"Ref: {curr_price:.2f}\n"
            f"Usunięto: {cancelled_total} | Dodano: {len(levels)}\n"
            + "\n".join(levels)
        )
        print(f"  GRID RESET {symbol} @ {curr_price:.2f} ({reason})")
    finally:
        grid_resetting[symbol] = False


# ── MANAGE SL (A01/A04 antyspam) ─────────────────────────────────────────────
def manage_sl(symbol, cfg, size, entry, curr_price, equity, buys):
    if size <= 0 or entry <= 0:
        return
    target_sl, label = calculate_sl(symbol, cfg, entry, curr_price, buys)
    if target_sl <= 0:
        return

    existing  = get_price_orders(symbol)
    sl_orders = [o for o in existing
                 if float(o.get("trigger", {}).get("price", 0)) > 0]

    if sl_orders:
        current_sl = float(sl_orders[0].get("trigger", {}).get("price", 0))
        if abs(current_sl - target_sl) / target_sl < 0.01:
            sl_placed[symbol] = True
            return
        for o in sl_orders:
            gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{o['id']}")
            time.sleep(0.2)
    else:
        sl_placed[symbol] = False

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
    if not res.get("id"):
        print(f"    SL FAIL {symbol}: {res.get('label','?')}")
        return

    sl_placed[symbol] = True
    dist      = (curr_price - target_sl) / curr_price * 100
    now_ts    = time.time()
    sl_type   = label.split()[0]
    prev_type = sl_last_type.get(symbol, "")
    type_changed = sl_type != prev_type
    sl_last_type[symbol] = sl_type

    last_tg     = sl_tg_cooldown.get(symbol, 0)
    cooldown_ok = (now_ts - last_tg) > SL_TG_COOLDOWN_SEC

    if not prev_type or type_changed or cooldown_ok:
        sl_tg_cooldown[symbol] = now_ts
        tg(
            f"🛡 <b>SL {'ZMIENIONY' if type_changed and prev_type else 'USTAWIONY'}</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Typ:     {label}\n"
            f"  SL @     {fmt_price(target_sl, symbol)}\n"
            f"  Dystans: {dist:.1f}%"
            + (f"\n  ← poprzednio: {prev_type}" if type_changed and prev_type else "")
        )
    print(f"    SL {symbol} @ {target_sl:.2f} ({label})"
          + (" [TG]" if not prev_type or type_changed or cooldown_ok else " [cicho]"))


# ── CHECK EXECUTED ────────────────────────────────────────────────────────────
def check_executed(symbol, cfg, size, entry, price, sells):
    global trade_log
    prev = last_size.get(symbol, -1)

    if prev < 0:
        if size == 0:
            tg(
                f"⚠️ <b>UWAGA: pozycja zamknięta podczas restartu</b>\n"
                f"{cfg['icon']} {symbol}\n"
                f"  Bot nie widział zamknięcia – sprawdź historię na giełdzie!\n"
                f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
            )
        last_size[symbol] = size
        return

    if size > prev:
        added = size - prev
        val   = added * cfg["contract_multiplier"] * price
        for o in sells:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        if sells:
            print(f"    DCA fill {symbol}: anulowano {len(sells)} TP")
        trailing_ref[symbol] = price
        tg(
            f"📥 <b>DCA WYKONANY</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Kupiono:  +{added:.0f}k @ {price:.2f}\n"
            f"  Wartość:  ~{val:.2f} USDT\n"
            f"  Pozycja:  {prev:.0f}k → {size:.0f}k\n"
            f"  Entry:    {entry:.2f}\n"
            f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
        )
    elif prev > size >= 0:
        closed = prev - size
        if closed > 0:
            pnl  = closed * cfg["contract_multiplier"] * (price - entry) if entry > 0 else 0
            pct  = (price - entry) / entry * 100 if entry > 0 else 0
            existing_sl = get_price_orders(symbol)
            sl_price    = float(existing_sl[0].get("trigger", {}).get("price", 0)) if existing_sl else 0
            is_tp  = sl_price == 0 or price > sl_price * 1.01
            label  = "TP WYKONANY ✅" if is_tp else "SL WYKONANY 🔴"
            trade_log.append((symbol, pnl, datetime.now().strftime("%H:%M")))
            if len(trade_log) > 50:
                trade_log.pop(0)
            tg(
                f"{'╔══ ✅' if is_tp else '╔══ 🔴'} <b>{label}</b> ══╗\n"
                f"{cfg['icon']} {symbol}\n"
                f"  Zamknięto: {closed:.0f}k\n"
                f"  Cena:      {price:.2f}\n"
                f"  Entry:     {entry:.2f} ({pct:+.1f}%)\n"
                f"  PnL:       <b>{pnl:+.2f} USDT</b>\n"
                f"  Pozostaje: {size:.0f}k\n"
                f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
            )
            if size == 0:
                sl_placed[symbol]       = False
                partial_tp_done[symbol] = False
                trailing_ref.pop(symbol, None)
                grid_bottom_cache.pop(symbol, None)
                sl_last_type.pop(symbol, None)
                sl_tg_cooldown.pop(symbol, None)
                be_active[symbol] = False

    last_size[symbol] = size


# ── P01: PARTIAL TP ───────────────────────────────────────────────────────────
def check_partial_tp(symbol, cfg, size, entry, curr_price, sells):
    """Sprzedaj 40% market gdy zysk >= +3% i pozycja >= partial_tp_min_size."""
    if partial_tp_done.get(symbol):
        return
    if size < cfg.get("partial_tp_min_size", 3):
        return
    if entry <= 0:
        return

    profit_pct = (curr_price - entry) / entry
    if profit_pct < cfg.get("partial_tp_pct", 0.03):
        return

    partial_qty = fmt_size(size * cfg.get("partial_tp_ratio", 0.40))
    if size - partial_qty < cfg["min_moonbag"]:
        partial_qty = max(0, int(size) - cfg["min_moonbag"])
    if partial_qty <= 0:
        return

    for o in sells:
        gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
        time.sleep(0.2)

    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": -partial_qty,
        "price": "0", "tif": "ioc", "reduce_only": True,
    })
    if res.get("id"):
        fill    = float(res.get("fill_price", curr_price) or curr_price)
        pnl_est = partial_qty * cfg["contract_multiplier"] * (fill - entry)
        partial_tp_done[symbol] = True
        print(f"    PARTIAL TP {symbol} -{partial_qty}k @ ~{fill:.2f} (+{profit_pct*100:.1f}%)")
        tg(
            f"💰 <b>PARTIAL TP WYKONANY</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Sprzedano: {partial_qty}k ({cfg.get('partial_tp_ratio',0.4)*100:.0f}%)\n"
            f"  Fill:      ~{fill:.2f} (+{profit_pct*100:.1f}%)\n"
            f"  Entry:     {entry:.2f}\n"
            f"  PnL est:   <b>~{pnl_est:+.2f} USDT</b>\n"
            f"  Pozostaje: {int(size)-partial_qty:.0f}k (trailing TP aktywny)\n"
            f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
        )
    else:
        print(f"    PARTIAL TP FAIL {symbol}: {res.get('label','?')}")


# ── PLACE TP / MANAGE TP ──────────────────────────────────────────────────────
def place_tp(symbol, cfg, tradeable, curr_price, entry):
    tp_from_entry = entry * (1 + cfg["tp_pct"]) if entry > 0 else 0
    tp_from_now   = curr_price * (1 + cfg["tp_pct_from_now"])
    target_tp     = max(tp_from_entry, tp_from_now)
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": -fmt_size(tradeable),
        "price": fmt_price(target_tp, symbol), "tif": "gtc", "reduce_only": True,
    })
    if res.get("id"):
        pct = (target_tp - curr_price) / curr_price * 100
        trailing_ref[symbol] = curr_price
        return target_tp, pct
    print(f"    TP FAIL {symbol}: {res.get('label','?')}")
    return 0, 0


def manage_tp(symbol, cfg, size, entry, curr_price, sells):
    tradeable = int(size) - cfg["min_moonbag"]
    if tradeable <= 0:
        return
    ref = trailing_ref.get(symbol, 0)

    if len(sells) == 1:
        existing_tp_size = abs(isize(sells[0].get("size", 0)))
        if existing_tp_size != tradeable:
            print(f"    TP size mismatch {symbol}: {existing_tp_size}k→{tradeable}k")
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{sells[0]['id']}")
            time.sleep(0.2)
            sells = []

    if len(sells) > 1:
        sells_sorted = sorted(sells, key=lambda o: float(o.get("price", 0)), reverse=True)
        for o in sells_sorted[1:]:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
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
                    f"📈 <b>TRAILING TP PRZESUNIĘTY</b>\n"
                    f"{cfg['icon']} {symbol}\n"
                    f"  Wzrost:  +{rise*100:.1f}% od {ref:.2f}\n"
                    f"  Nowy TP: {fmt_price(tp_price, symbol)} (+{pct:.1f}%)\n"
                    f"  Moonbag: {cfg['min_moonbag']}k 🔒"
                )
        else:
            sell_p  = float(sells[0].get("price", 0)) if sells else 0
            brakuje = (cfg["trailing_trigger"] - rise) * 100
            print(f"    TP {symbol} @ {sell_p:.2f} | trailing za {brakuje:.1f}%")
    else:
        trailing_ref[symbol] = curr_price


# ── MANAGE DCA (M01) ──────────────────────────────────────────────────────────
def manage_dca(symbol, cfg, size, curr_price, buys, free_margin, equity):
    if grid_resetting.get(symbol):
        print(f"    SKIP {symbol}: grid reset w toku")
        return
    if not DCA_ENABLED:
        return
    if is_market_crashing():
        print(f"    CRASH DCA {symbol} wstrzymane")
        return
    if free_margin < cfg["min_free_margin"] or equity < cfg["min_equity"]:
        return

    time_since_reset = time.time() - grid_reset_time.get(symbol, 0)
    if time_since_reset > 30 and buys:
        highest_buy = max(float(o.get("price", 0)) for o in buys)
        if highest_buy > 0 and (curr_price - highest_buy) / curr_price > cfg["grid_reset_pct"]:
            print(f"    GRID RESET UP {symbol}: {curr_price:.2f}")
            do_reset_grid(symbol, curr_price, equity, "auto grid reset w górę")
            return

    if len(buys) > cfg["dca_levels"]:
        buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)), reverse=True)
        for o in buys_sorted[cfg["dca_levels"]:]:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        buys = buys_sorted[:cfg["dca_levels"]]

    # M01: dynamiczny limit oparty o curr_price (świeże z get_price w manage_logic)
    dyn_max   = get_dynamic_max_contracts(symbol, equity, curr_price)
    total_exp = size + sum(isize(o.get("size", 0)) for o in buys)
    if total_exp >= dyn_max or len(buys) >= cfg["dca_levels"]:
        return

    is_sw, sweep_reason, sname, mn, mw = detect_sweep(symbol, curr_price)
    now_ts    = time.time()
    scalp_key = f"{symbol}_scalp_dca"
    scalp_ok  = (now_ts - sweep_last_notify.get(scalp_key, 0)) > 900

    if is_sw and size == 0 and scalp_ok:
        sweep_mult, sweep_label = mn, f"SCALP×{mn:.1f}"
        sweep_last_notify[scalp_key] = now_ts
    elif is_sw and size > 0:
        sweep_mult, sweep_label = mw, f"BOOST×{mw:.1f}"
    else:
        sweep_mult, sweep_label = 1.0, ""

    needed = cfg["dca_levels"] - len(buys)
    added  = 0
    for i in range(1, cfg["dca_levels"] + 1):
        if added >= needed:
            break
        target = curr_price * (1 - cfg["grid_step"] * i)
        if any(abs(target - float(o.get("price", 0))) / target < 0.015 for o in buys):
            continue
        qty = fmt_size(get_dynamic_size(symbol, equity, curr_price) *
                       (sweep_mult if i == 1 else 1.0))
        if total_exp + added + qty > dyn_max:
            qty = max(1, dyn_max - total_exp - added)
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


# ── MANAGE LOGIC ──────────────────────────────────────────────────────────────
def manage_logic(symbol, cfg, free_margin, equity, all_positions):
    # KLUCZOWE: get_price() wywołane tu → świeża cena z API
    # Ta sama cena przekazywana przez WSZYSTKIE funkcje – nigdy cached.
    price = get_price(symbol)
    if price <= 0:
        return

    if symbol == "BTC_USDT":
        btc_price_history.append(price)
        if len(btc_price_history) > 10:
            btc_price_history.pop(0)

    pos   = (next((p for p in all_positions if p["contract"] == symbol), None)
             if isinstance(all_positions, list) else None)
    size  = abs(float(pos["size"])) if pos and float(pos.get("size", 0)) != 0 else 0
    entry = float(pos["entry_price"]) if size > 0 else 0

    orders = get_orders(symbol)
    buys   = [o for o in orders if isize(o.get("size", 0)) > 0]
    sells  = [o for o in orders if isize(o.get("size", 0)) < 0]

    # M01: pokaż dynamiczny limit w konsoli
    dyn_max = get_dynamic_max_contracts(symbol, equity, price)
    pct_str = f"{(price-entry)/entry*100:+.1f}%" if entry > 0 else "---"
    print(f"  {cfg['icon']}  {symbol:<10} {price:>9.2f}  poz={size:.0f}k {pct_str}"
          f"  buy={len(buys)} sell={len(sells)}  maxC={dyn_max}k")

    if size > 0:
        check_executed(symbol, cfg, size, entry, price, sells)
        check_partial_tp(symbol, cfg, size, entry, price, sells)
        sells = [o for o in get_orders(symbol) if isize(o.get("size", 0)) < 0]
        manage_sl(symbol, cfg, size, entry, price, equity, buys)
        if size > cfg["min_moonbag"]:
            manage_tp(symbol, cfg, size, entry, price, sells)

    check_initial_entry(symbol, cfg, size, price, equity, free_margin, buys)
    check_dca_sweep_add(symbol, cfg, size, entry, price, equity, free_margin, buys)
    manage_dca(symbol, cfg, size, price, buys, free_margin, equity)


# ── TELEGRAM LISTENER ─────────────────────────────────────────────────────────
def listen_telegram():
    global BOT_ACTIVE, DCA_ENABLED, LAST_UPDATE_ID, equity_guard_fired
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
                    msg     = update.get("message", {}).get("text", "")
                    chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                    if chat_id != CHAT_ID:
                        continue

                    if msg == "/stop":
                        BOT_ACTIVE = False
                        tg("🛑 <b>Bot zatrzymany</b>")

                    elif msg == "/start":
                        BOT_ACTIVE = True
                        equity_guard_fired = False
                        tg("🚀 <b>Bot uruchomiony!</b>")

                    elif msg == "/dca_off":
                        DCA_ENABLED = False
                        tg("⏸ <b>DCA wyłączone</b>")

                    elif msg == "/dca_on":
                        DCA_ENABLED = True
                        tg("▶️ <b>DCA włączone</b>")
                      

                    elif msg.startswith("/buy"):
                        parts   = msg.split()
                        sym_arg = parts[1].upper() if len(parts) > 1 else ""
                        if not sym_arg:
                            tg("🛒 <b>Użycie: /buy ETH / /buy BTC</b>\n"
                               "Market buy 1× dynamic size.\n"
                               "Blokowany przez M02 global exposure guard.")
                        else:
                            sym_full = sym_arg if "_USDT" in sym_arg else sym_arg + "_USDT"
                            if sym_full not in CONFIG:
                                tg(f"❌ Nieznany symbol: {sym_arg}")
                            else:
                                cfg_b = CONFIG[sym_full]
                                acc_b = get_account()
                                eq_b  = float(acc_b.get("total", 0)) if isinstance(acc_b, dict) else 0
                                fr_b  = float(acc_b.get("available", 0)) if isinstance(acc_b, dict) else 0
                                if fr_b < cfg_b["min_free_margin"]:
                                    tg(f"❌ Za mało free margin: {fr_b:.2f} USDT")
                                else:
                                    p_b       = get_price(sym_full)
                                    all_p_b   = get_positions()
                                    exp_usd_b = get_total_exposure_usd(all_p_b)
                                    max_exp_b = eq_b * MAX_TOTAL_EXPOSURE_PCT
                                    dyn_b     = get_dynamic_max_contracts(sym_full, eq_b, p_b)
                                    if exp_usd_b >= max_exp_b:
                                        tg(
                                            f"❌ /buy ZABLOKOWANY – M02 global exposure:\n"
                                            f"  Otwarte: {exp_usd_b:.0f} USD / max {max_exp_b:.0f} USD\n"
                                            f"  Zamknij część pozycji przed ręcznym wejściem."
                                        )
                                    else:
                                        qty_b = fmt_size(get_dynamic_size(sym_full, eq_b, p_b))
                                        # M01: upewnij się że nie przekraczamy dynamicznego limitu
                                        qty_b = min(qty_b, dyn_b)
                                        tg(f"🛒 Wysyłam MARKET BUY {sym_full} x{qty_b}k @ ~{p_b:.2f}\n"
                                           f"  Exp: {exp_usd_b:.0f}/{max_exp_b:.0f} USD  maxC={dyn_b}k @ {p_b:.2f}")
                                        res_b = gate_request("POST", "/api/v4/futures/usdt/orders",
                                                             body={"contract": sym_full, "size": qty_b,
                                                                   "price": "0", "tif": "ioc"})
                                        if res_b.get("id"):
                                            fill = float(res_b.get("fill_price", p_b) or p_b)
                                            tg(f"✅ <b>MARKET BUY WYKONANY</b>\n"
                                               f"{cfg_b['icon']} {sym_full}\n"
                                               f"  Qty:   {qty_b}k\n"
                                               f"  Fill:  ~{fill:.2f}\n"
                                               f"  ID:    {res_b['id']}")
                                        else:
                                            tg(f"❌ FAILED: {res_b.get('label','?')} – "
                                               f"{res_b.get('message','')[:80]}")

                    elif msg.startswith("/close"):
                        parts   = msg.split()
                        sym_arg = parts[1].upper() if len(parts) > 1 else ""
                        if not sym_arg:
                            tg("🔴 <b>Użycie: /close ETH / /close BTC</b>\n"
                               "Zamyka całą pozycję market. Anuluje TP i SL.")
                        else:
                            sym_full = sym_arg if "_USDT" in sym_arg else sym_arg + "_USDT"
                            if sym_full not in CONFIG:
                                tg(f"❌ Nieznany symbol: {sym_arg}")
                            else:
                                cfg_c   = CONFIG[sym_full]
                                all_p   = get_positions()
                                pos_c   = next((p for p in all_p if p["contract"] == sym_full), None) \
                                          if isinstance(all_p, list) else None
                                sz_c    = float(pos_c["size"]) if pos_c else 0
                                if sz_c <= 0:
                                    tg(f"ℹ️ {sym_full}: brak otwartej pozycji long")
                                else:
                                    entry_c = float(pos_c.get("entry_price", 0))
                                    p_c     = get_price(sym_full)
                                    tg(f"🔴 Zamykam {sym_full} {sz_c:.0f}k @ ~{p_c:.2f}…")
                                    for o in get_orders(sym_full):
                                        gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
                                        time.sleep(0.15)
                                    for o in get_price_orders(sym_full):
                                        gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{o['id']}")
                                        time.sleep(0.15)
                                    res_c = gate_request("POST", "/api/v4/futures/usdt/orders",
                                                         body={"contract": sym_full, "size": -int(sz_c),
                                                               "price": "0", "tif": "ioc",
                                                               "reduce_only": True})
                                    if res_c.get("id"):
                                        fill_c = float(res_c.get("fill_price", p_c) or p_c)
                                        pnl_c  = sz_c * cfg_c["contract_multiplier"] * (fill_c - entry_c)
                                        pct_c  = (fill_c - entry_c) / entry_c * 100 if entry_c > 0 else 0
                                        sl_placed[sym_full]       = False
                                        partial_tp_done[sym_full] = False
                                        trailing_ref.pop(sym_full, None)
                                        grid_bottom_cache.pop(sym_full, None)
                                        be_active[sym_full] = False
                                        tg(
                                            f"{'✅' if pnl_c >= 0 else '🔴'} <b>ZAMKNIĘTO POZYCJĘ</b>\n"
                                            f"{cfg_c['icon']} {sym_full}\n"
                                            f"  Qty:    {sz_c:.0f}k\n"
                                            f"  Fill:   ~{fill_c:.2f} ({pct_c:+.1f}%)\n"
                                            f"  Entry:  {entry_c:.2f}\n"
                                            f"  PnL:    <b>{pnl_c:+.2f} USDT</b>\n"
                                            f"╚══ {datetime.now().strftime('%H:%M')} ══╝"
                                        )
                                    else:
                                        tg(f"❌ Close FAILED: {res_c.get('label','?')}")

                    elif msg == "/status":
                        acc   = get_account()
                        tot   = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                        fr    = float(acc.get("available", 0)) if isinstance(acc, dict) else 0
                        pnl   = float(acc.get("unrealised_pnl", 0)) if isinstance(acc, dict) else 0
                        crash = is_market_crashing()
                        sess  = get_active_session()
                        sess_str = f"🟢 {sess[0]}" if sess else "⚫ brak sesji"
                        next_s, next_m = next_session_info()
                        all_p_s   = get_positions()
                        exp_usd_s = get_total_exposure_usd(all_p_s)
                        max_exp_s = tot * MAX_TOTAL_EXPOSURE_PCT
                        exp_bar   = bar(exp_usd_s / max_exp_s if max_exp_s > 0 else 0)
                        ords = ""
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            o = get_orders(sym)
                            if o:
                                b = len([x for x in o if isize(x.get("size", 0)) > 0])
                                s = len([x for x in o if isize(x.get("size", 0)) < 0])
                                ords += f"\n{cfg['icon']} {sym}: {b}× buy / {s}× sell"
                        margin_icon  = "🟢" if fr > 150 else ("🟡" if fr > 80 else "🔴")
                        pnl_icon     = "📈" if pnl >= 0 else "📉"
                        session_gain = tot - session_pnl_start if session_pnl_start > 0 else 0
                        tg(
                            f"╔══ 📊 <b>STATUS</b> ══╗\n"
                            f"🤖 Bot: {'ON ✅' if BOT_ACTIVE else 'OFF 🛑'}  "
                            f"DCA: {'ON ✅' if DCA_ENABLED else 'OFF ⏸'}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"💰 Equity:  <b>{tot:.2f} USDT</b>\n"
                            f"{margin_icon} Margin:  <b>{fr:.2f} USDT</b>\n"
                            f"{pnl_icon} PnL:     <b>{pnl:+.2f} USDT</b>\n"
                            f"📊 Sesja:  <b>{session_gain:+.2f} USDT</b>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📦 Ekspozycja: <b>{exp_usd_s:.0f}/{max_exp_s:.0f} USD</b> {exp_bar}\n"
                            f"⏰ Sesja:  {sess_str}\n"
                            f"⏭ Następna: {next_s} za {next_m//60}h{next_m%60:02d}m\n"
                            f"🚨 Crash:  {'TAK ⚠️' if crash else 'NIE ✅'}\n"
                            f"📋 Zlecenia:{ords if ords else ' Brak'}\n"
                            f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝"
                        )

                    elif msg == "/pozycje":
                        p_data = get_positions()
                        lines  = ["╔══ 📦 <b>POZYCJE</b> ══╗"]
                        found  = False
                        if isinstance(p_data, list):
                            for p in p_data:
                                sz = float(p.get("size", 0))
                                if sz > 0:
                                    found  = True
                                    sym    = p["contract"]
                                    entry  = float(p["entry_price"])
                                    ppnl   = float(p.get("unrealised_pnl", 0))
                                    price  = get_price(sym)
                                    pct    = (price - entry) / entry * 100 if entry > 0 else 0
                                    cfg    = CONFIG.get(sym, {})
                                    dyn_m  = get_dynamic_max_contracts(sym, 0, price) if price > 0 else "?"
                                    pnl_ic = "📈" if ppnl >= 0 else "📉"
                                    lines.append(
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{cfg.get('icon','•')} <b>{sym}</b>\n"
                                        f"  Pozycja: {sz:.0f}k  Moonbag: {cfg.get('min_moonbag',0)}k\n"
                                        f"  Entry:   {entry:.2f}\n"
                                        f"  Teraz:   {price:.2f} ({pct:+.1f}%) {bar(abs(pct)/20)}\n"
                                        f"  {pnl_ic} PnL: <b>{ppnl:+.2f} USDT</b>"
                                    )
                        if not found:
                            lines.append("━━━━━━━━━━━━━━━\nBrak otwartych pozycji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/sl":
                        p_data = get_positions()
                        lines  = ["╔══ 🛡 <b>STOP LOSS</b> ══╗"]
                        found  = False
                        if isinstance(p_data, list):
                            for p in p_data:
                                sz = float(p.get("size", 0))
                                if sz > 0:
                                    found  = True
                                    sym    = p["contract"]
                                    entry  = float(p["entry_price"])
                                    price  = get_price(sym)
                                    cfg    = CONFIG.get(sym, {})
                                    orders = get_orders(sym)
                                    buys   = [o for o in orders if isize(o.get("size", 0)) > 0]
                                    sl, label = calculate_sl(sym, cfg, entry, price, buys)
                                    dist   = (price - sl) / price * 100 if sl > 0 and price > 0 else 0
                                    placed = "TAK ✅" if sl_placed.get(sym) else "NIE ❌"
                                    lines.append(
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{cfg.get('icon','•')} <b>{sym}</b>\n"
                                        f"  Typ:     {label}\n"
                                        f"  SL @     {sl:.2f}\n"
                                        f"  Dystans: {dist:.1f}% {bar(dist/20)}\n"
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
                            ref   = trailing_ref.get(sym, 0)
                            sells = [o for o in get_orders(sym) if isize(o.get("size", 0)) < 0]
                            tp_p  = float(sells[0]["price"]) if sells else 0
                            if ref > 0 and price > 0:
                                rise     = (price - ref) / ref * 100
                                trigger  = cfg["trailing_trigger"] * 100
                                brakuje  = max(0, trigger - rise)
                                progress = min(rise / trigger, 1.0) if trigger > 0 else 0
                                lines.append(
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"{cfg['icon']} <b>{sym}</b>\n"
                                    f"  Cena:    {price:.2f}\n"
                                    f"  Ref:     {ref:.2f}\n"
                                    f"  Wzrost:  +{rise:.1f}% {bar(progress)}\n"
                                    f"  Trigger: +{trigger:.0f}% (brakuje {brakuje:.1f}%)\n"
                                    f"  TP @     {fmt_price(tp_p, sym) if tp_p else 'Brak'}"
                                )
                            else:
                                lines.append(f"━━━━━━━━━━━━━━━\n{cfg['icon']} {sym}: brak pozycji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/sweep":
                        sess     = get_active_session()
                        sess_str = f"🟢 {sess[0]}" if sess else "⚫ brak aktywnej sesji"
                        next_s, next_m = next_session_info()
                        lines = [
                            "╔══ 🎯 <b>SWEEP STATUS</b> ══╗",
                            f"Sesja:     {sess_str}",
                            f"Następna:  {next_s} za {next_m//60}h{next_m%60:02d}m",
                        ]
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            zone  = session_zones.get(sym, {})
                            price = get_price(sym)
                            is_sw, reason, sname, mn, mw = detect_sweep(sym, price)
                            lines.append(
                                f"━━━━━━━━━━━━━━━\n"
                                f"{cfg['icon']} <b>{sym}</b>\n"
                                f"  Cena:   {price:.2f}\n"
                                f"  Low:    {zone.get('low', 0):.2f}\n"
                                f"  High:   {zone.get('high', 0):.2f}\n"
                                f"  Status: {'🎯 ' + reason if is_sw else '⬜ Brak'}"
                            )
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/sessions":
                        m_now = _minutes_utc()
                        lines = ["╔══ ⏰ <b>SESJE SWEEPOWE</b> ══╗"]
                        for name, sh, sm, eh, em, mn, mw, cd in SWEEP_SESSIONS:
                            start  = sh * 60 + sm
                            end    = eh * 60 + em
                            active = start <= m_now < end
                            diff   = (start - m_now) % (24 * 60)
                            if active:
                                remain = end - m_now
                                status = f"🟢 AKTYWNA (jeszcze {remain//60}h{remain%60:02d}m)"
                            else:
                                status = f"⚫ za {diff//60}h{diff%60:02d}m"
                            lines.append(
                                f"━━━━━━━━━━━━━━━\n"
                                f"<b>{name}</b>  {sh:02d}:{sm:02d}–{eh:02d}:{em:02d} UTC\n"
                                f"  entry ×{mn}  boost ×{mw}\n"
                                f"  {status}"
                            )
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/grid":
                        lines = ["╔══ 📐 <b>SIATKA DCA</b> ══╗"]
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            price  = get_price(sym)
                            orders = get_orders(sym)
                            buys   = sorted(
                                [o for o in orders if isize(o.get("size", 0)) > 0],
                                key=lambda o: float(o.get("price", 0)), reverse=True
                            )
                            dyn_m = get_dynamic_max_contracts(sym, 0, price) if price > 0 else "?"
                            warn  = f" ⚠️ {len(buys)} zleceń!" if len(buys) > cfg["dca_levels"] else ""
                            lines.append(f"━━━━━━━━━━━━━━━\n"
                                         f"{cfg['icon']} <b>{sym}</b>  [{price:.2f}]  maxC={dyn_m}k{warn}")
                            if buys:
                                for i, o in enumerate(buys, 1):
                                    bp   = float(o.get("price", 0))
                                    bsz  = isize(o.get("size", 0))
                                    dist = (price - bp) / price * 100
                                    lines.append(f"  L{i}: {bp:.2f} x{bsz}k ({dist:.1f}% niżej)")
                            else:
                                lines.append("  Brak aktywnych DCA buy limitów")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/pnl":
                        acc      = get_account()
                        curr_eq  = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                        gain     = curr_eq - session_pnl_start if session_pnl_start > 0 else 0
                        gain_pct = gain / session_pnl_start * 100 if session_pnl_start > 0 else 0
                        lines    = [
                            "╔══ 💹 <b>P&L SESJI</b> ══╗",
                            f"  Start:  {session_pnl_start:.2f} USDT",
                            f"  Teraz:  {curr_eq:.2f} USDT",
                            f"  Wynik:  <b>{gain:+.2f} USDT ({gain_pct:+.2f}%)</b>",
                            "━━━━━━━━━━━━━━━",
                        ]
                        if trade_log:
                            lines.append("📋 Ostatnie transakcje:")
                            for entry_t in trade_log[-5:]:
                                sym_t, pnl_t, t_t = entry_t
                                icon = CONFIG.get(sym_t, {}).get("icon", "•")
                                lines.append(f"  {icon} {sym_t}: <b>{pnl_t:+.2f} USDT</b>  {t_t}")
                        else:
                            lines.append("  Brak zamkniętych transakcji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝")
                        tg("\n".join(lines))

                    elif msg.startswith("/reset_dca"):
                        parts   = msg.split()
                        sym_arg = parts[1].upper() if len(parts) > 1 else ""
                        if not sym_arg:
                            tg("Użycie: /reset_dca BTC / ETH / SOL / ALL")
                        else:
                            symbols = ([s for s, c in CONFIG.items() if c["active"]]
                                       if sym_arg == "ALL"
                                       else [(sym_arg if "_USDT" in sym_arg
                                              else sym_arg + "_USDT")])
                            symbols = [s for s in symbols if s in CONFIG]
                            if not symbols:
                                tg(f"Nieznany symbol: {sym_arg}")
                            else:
                                acc2 = get_account()
                                eq2  = float(acc2.get("total", 300)) if isinstance(acc2, dict) else 300
                                for sym in symbols:
                                    price2 = get_price(sym)
                                    if price2 > 0:
                                        do_reset_grid(sym, price2, eq2, "ręczny /reset_dca")

                    elif msg == "/help":
                        tg(
                            "╔══ 📖 <b>KOMENDY v2.11</b> ══╗\n"
                            "━━━━━━━━━━━━━━━\n"
                            "📊 /status      — equity + ekspozycja USD\n"
                            "📦 /pozycje     — otwarte pozycje\n"
                            "🛡 /sl          — stop lossy\n"
                            "📈 /trailing    — trailing TP\n"
                            "🎯 /sweep       — sweep status\n"
                            "⏰ /sessions    — sesje + countdown\n"
                            "📐 /grid        — siatka DCA + maxC\n"
                            "💹 /pnl         — P&L od startu\n"
                            "🛒 /buy ETH/BTC — test market buy\n"
                            "🔴 /close ETH/BTC — zamknij pozycję\n"
                            "━━━━━━━━━━━━━━━\n"
                            "▶️ /start  🛑 /stop\n"
                            "✅ /dca_on  ⏸ /dca_off\n"
                            "🔄 /reset_dca BTC/ETH/SOL/ALL\n"
                            "╚══════════════════╝"
                        )

        except Exception as e:
            print(f"  TG ERR {e}")
        time.sleep(2)


# ── GŁÓWNA PĘTLA ──────────────────────────────────────────────────────────────
def run():
    global BOT_ACTIVE, session_pnl_start, equity_guard_fired, equity_guard_day
    threading.Thread(target=listen_telegram, daemon=True).start()
    print("=" * 62)
    print("  FreedomTracker Bot v2.11 PRODUCTION")
    print("  M01: dyn max_contracts | M02: global exp guard | M03: size==0")
    print("  /help /status /pozycje /sl /sweep /sessions /grid /pnl /buy /close")
    print("=" * 62)
    tg(
        "╔══ 🤖 <b>FreedomTracker v2.11 PRODUCTION</b> ══╗\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🛡 M01: max kontraktów = f(equity, cena rynkowa)\n"
        "   ETH@2000: max ~7k  |  ETH@4000: max ~3k\n"
        "🛡 M02: global exposure guard 75% equity (~217 USD)\n"
        "🛡 M03: sweep entry tylko gdy brak pozycji\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Antyspam SL/TP (v2.9)\n"
        "✅ Partial TP 40% przy +3%\n"
        "✅ 5 sesji sweepowych 24/7\n"
        "✅ /close | /buy | /sessions\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📖 /help — lista komend\n"
        "╚══════════════════════╝"
    )

    cycle           = 0
    last_zone_h     = -1
    starting_eq     = 0
    equity_guard_fired = False

    while True:
        cycle += 1
        if BOT_ACTIVE:
            try:
                acc = get_account()
                fr  = float(acc.get("available", 0)) if isinstance(acc, dict) else 0
                eq  = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                pnl = float(acc.get("unrealised_pnl", 0)) if isinstance(acc, dict) else 0
            except Exception as e:
                print(f"  ERR get_account: {e}")
                time.sleep(20)
                continue

            if starting_eq == 0 and eq > 0:
                starting_eq       = eq
                session_pnl_start = eq
                print(f"  Equity startowe: {starting_eq:.2f} USDT")

            # P04: reset equity guard każdego nowego dnia UTC
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            if equity_guard_day != today_str and eq > 0:
                if equity_guard_day != "":
                    prev_base          = starting_eq
                    starting_eq        = eq
                    session_pnl_start  = eq
                    equity_guard_fired = False
                    equity_guard_day   = today_str
                    print(f"  [P04] Dzienny reset equity guard: {prev_base:.2f}→{eq:.2f} USDT")
                    tg(
                        f"🌅 <b>Dzienny reset equity guard</b>\n"
                        f"  Nowa baza: <b>{eq:.2f} USDT</b>\n"
                        f"  Guard przy: <b>{eq*0.75:.2f} USDT</b> (-25%)\n"
                        f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝"
                    )
                else:
                    equity_guard_day = today_str

            if starting_eq > 0 and eq < starting_eq * 0.75 and not equity_guard_fired:
                equity_guard_fired = True
                BOT_ACTIVE = False
                spadek = round((1 - eq / starting_eq) * 100, 1)
                tg(
                    f"🚨 <b>EQUITY GUARD!</b>\n"
                    f"Start:  {starting_eq:.2f} USDT\n"
                    f"Teraz:  {eq:.2f} USDT  (-{spadek}%)\n"
                    f"Bot zatrzymany. /start aby wznowić."
                )
                print(f"  EQUITY GUARD: bot zatrzymany (-{spadek}%)")

            now_ts = time.time()
            if 0 < fr < 80:
                if now_ts - last_margin_alert.get("warn", 0) > 1800:
                    tg(f"⚠️ <b>Free margin:</b> <b>{fr:.2f} USDT</b>")
                    last_margin_alert["warn"] = now_ts
            if 0 < fr < 50:
                if now_ts - last_margin_alert.get("crit", 0) > 900:
                    tg(f"🚨 <b>ALARM! Krytyczny margin: {fr:.2f} USDT</b>")
                    last_margin_alert["crit"] = now_ts

            curr_hour = datetime.utcnow().hour
            if curr_hour != last_zone_h:
                update_session_zones()
                last_zone_h = curr_hour

            # Sweep alert dla aktywnej sesji
            sess = get_active_session()
            if sess:
                sname, mn, mw, cd = sess
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    p = get_price(sym)
                    if p <= 0:
                        continue
                    is_sw, reason, _, _, _ = detect_sweep(sym, p)
                    if is_sw:
                        alert_key  = f"alert_{sym}"
                        last_notif = sweep_last_notify.get(alert_key, 0)
                        if (time.time() - last_notif) > 900:
                            sweep_last_notify[alert_key] = time.time()
                            zone    = session_zones.get(sym, {})
                            all_pos = get_positions()
                            has_pos = False
                            if isinstance(all_pos, list):
                                pos_sw  = next((px for px in all_pos if px["contract"] == sym), None)
                                has_pos = pos_sw is not None and float(pos_sw.get("size", 0)) != 0
                            akcja = f"🎯 ENTRY ×{mn:.1f}" if not has_pos else f"⚡ BOOST ×{mw:.1f}"
                            tg(
                                f"🎯 <b>{sname.upper()} SWEEP!</b>\n"
                                f"{cfg['icon']} {sym}\n"
                                f"  Cena:   {p:.2f}\n"
                                f"  Low:    {zone.get('low', 0):.2f}\n"
                                f"  Sygnał: {reason}\n"
                                f"  Akcja:  {akcja} 🚀"
                            )
                        else:
                            rem = int((900 - (time.time() - last_notif)) / 60)
                            print(f"    [SWEEP] {sym} alert cooldown {rem} min")

            crash_str = " [CRASH]" if is_market_crashing() else ""
            sess_str  = f" [{sess[0]}]" if sess else ""
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cykl {cycle} | "
                  f"Eq: {eq:.2f} | Free: {fr:.2f} | PnL: {pnl:+.2f}{crash_str}{sess_str}")
            print("-" * 62)

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

            print("-" * 62)

            if cycle % 180 == 0:
                all_pos_r = get_positions()
                exp_r     = get_total_exposure_usd(all_pos_r)
                ords = ""
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    o = get_orders(sym)
                    if o:
                        b = len([x for x in o if isize(x.get("size", 0)) > 0])
                        s = len([x for x in o if isize(x.get("size", 0)) < 0])
                        ords += f"\n{cfg['icon']} {sym}: {b}× buy / {s}× sell"
                gain = eq - session_pnl_start if session_pnl_start > 0 else 0
                tg(
                    f"╔══ 📊 <b>Raport godzinny</b> ══╗\n"
                    f"💰 Equity:  <b>{eq:.2f} USDT</b>\n"
                    f"💵 Wolne:   <b>{fr:.2f} USDT</b>\n"
                    f"📈 PnL:     <b>{pnl:+.2f} USDT</b>\n"
                    f"💹 Sesja:   <b>{gain:+.2f} USDT</b>\n"
                    f"📦 Exp:     <b>{exp_r:.0f}/{eq*MAX_TOTAL_EXPOSURE_PCT:.0f} USD</b>\n"
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
        tg("🛑 <b>Bot zatrzymany ręcznie</b>")
    except Exception as e:
        print(f"\nKRYTYCZNY BŁĄD: {e}")
        tg(f"🚨 <b>KRYTYCZNY BŁĄD!</b>\n<code>{str(e)[:200]}</code>")
