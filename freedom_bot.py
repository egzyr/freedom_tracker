"""
FreedomTracker Bot v2.16 PRODUCTION [ODRZUTOWIEC WSS]
══════════════════════════════════════════════════════════════
HISTORIA WERSJI:

v2.13 – BUGFIXY Z AUDYTU
  K01 - check_partial_tp aktualizuje last_size → brak fałszywych TP/SL alertów
  K02 - datetime.utcnow() → datetime.now(timezone.utc) (fix deprecation Python 3.12+)
  H01 - /pozycje i /grid: equity pobierane z API (nie 0)
  H02 - guard na short pozycje w manage_logic
  H04 - CHAT_ID.strip() – odporność na spacje w .env
  S02 - check_initial_entry/check_dca_sweep_add: reuse all_positions (mniej API calls)
  S03 - session_key_for: klucz z nazwą sesji (nie hour//8)
  N01 - ujednolicone numery wersji v2.13

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

import os, time, requests, hmac, hashlib, json, threading, websocket
from datetime import datetime, timezone
from dotenv import load_dotenv

# ── CONFIG LOAD ──────────────────────────────────────────────────────────────
# Próba załadowania .env_freedom z bieżącej lokalizacji skryptu (lepsza kompatybilność Windows/Linux)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env_freedom')
if not os.path.exists(env_path):
    env_path = '.env_freedom' # Fallback na CWD
load_dotenv(env_path)
GATE_KEY    = os.getenv('GATE_API_KEY')
GATE_SECRET = os.getenv('GATE_SECRET')
TOKEN       = os.getenv('TELEGRAM_TOKEN')
CHAT_ID     = os.getenv('TELEGRAM_CHAT_ID', '').strip()
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
ibkr_withdrawn      = 0.0   # łączna suma wypłacona do IBKR (USDT), reset po restarcie
grid_resetting      = {}
grid_reset_time     = {}
equity_guard_day    = ""
starting_eq         = 0
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

# ── M04/M05: Market Intelligence Limits ───────────────────────────────────────
MAX_FUNDING_RATE = 0.0005      # >0.05% chroni przed Long Squeeze
SMA_PERIODS = 50               # 50 świec
SMA_INTERVAL = "4h"            # Okres 4H, czyli ~SMA z 8 dni
TREND_DIP_THRESHOLD_PCT = 0.04 # Zablokuj Sweep gdy Cena < SMA50 * 0.96

# ── SHARED STATE (thread-safe cache) ─────────────────────────────────────────
_cache_lock      = threading.Lock()
_state_lock      = threading.Lock()   # chroni BOT_ACTIVE / DCA_ENABLED / equity_guard_fired
_cached_account  = {}
_cached_positions = []
_market_regime   = {
    "funding_overheated": {},   # np. {"BTC_USDT": False}
    "downtrend_active": {}      # np. {"BTC_USDT": False}
}
_live_prices      = {}
_price_timestamps = {}   # sym -> czas ostatniej aktualizacji z WSS
_wss_reconnect_ts = 0    # czas ostatniego reconnectu WSS (global, dla data_feed)

PRICE_MAX_AGE      = 60  # sekundy – po tym czasie cena WSS uznawana za nieaktualną
WSS_GRACE_PERIOD   = 30  # sekundy grace po reconnect zanim stale alert może wylecieć

def get_cached_account():
    with _cache_lock: return dict(_cached_account) if isinstance(_cached_account, dict) else {}

def get_cached_positions():
    with _cache_lock: return list(_cached_positions) if isinstance(_cached_positions, list) else []

def is_market_safe(symbol):
    with _cache_lock:
        overheated = _market_regime["funding_overheated"].get(symbol, False)
        downtrend  = _market_regime["downtrend_active"].get(symbol, False)
        reasons = []
        if overheated: reasons.append("Overheated Funding (Squeeze Risk)")
        if downtrend:  reasons.append("SMA Downtrend (Falling Knife Risk)")
        return not bool(reasons), ", ".join(reasons)

# ══════════════════════════════════════════════════════════════
# ⚙️  DOCELOWA WARTOŚĆ USD NA JEDEN POZIOM DCA / WEJŚCIE SWEEP
#     Bot sam przelicza ile kontraktów BTC/ETH kupić żeby trafić
#     w tę kwotę – dzięki temu BTC i ETH mają podobne rozmiary.
#
#     Rozmiar wejścia skaluje się automatycznie z equity:
#       TARGET_ENTRY_PCT = 0.20  →  20% equity per poziom
#
#     Przykłady:
#       equity=290:  290×0.20 = 58 USD  (jak poprzednio ~60)
#       equity=400:  400×0.20 = 80 USD
#       equity=600:  600×0.20 = 120 USD
#       equity=1000: 1000×0.20 = 200 USD
#
#     Limit bezpieczeństwa: max 22% equity per poziom (cap w calc_qty).
# ══════════════════════════════════════════════════════════════
TARGET_ENTRY_PCT = 0.20   # ← JEDYNA LICZBA DO EDYCJI (% equity per wejście)
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
        "leverage": 7,                # ← dźwignia ustawiona na Gate.io
        "min_moonbag": 2, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 20,
        "risk_per_level": 0.04,
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.20,
        "price_decimals": 0,
        "min_free_margin": 80, "min_equity": 150, "contract_multiplier": 0.0001,
        "grid_reset_pct": 0.05,
        "partial_tp_pct": 0.03, "partial_tp_ratio": 0.40, "partial_tp_min_size": 4,
    },
    "ETH_USDT": {
        "icon": "🔵", "active": True,
        "base_qty": 0,                # 0 = tryb automatyczny (TARGET_ENTRY_USD)
        "leverage": 7,                # ← dźwignia ustawiona na Gate.io
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.02,
        "max_contracts": 20,
        "risk_per_level": 0.04,
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.13,
        "price_decimals": 2,
        "min_free_margin": 80, "min_equity": 150, "contract_multiplier": 0.01,
        "grid_reset_pct": 0.05,
        "partial_tp_pct": 0.03, "partial_tp_ratio": 0.40, "partial_tp_min_size": 3,
    },
    "SOL_USDT": {
        "icon": "🟣", "active": False,
        "base_qty": 0,                # 0 = tryb automatyczny (TARGET_ENTRY_USD)
        "leverage": 7,                # ← dźwignia ustawiona na Gate.io
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
    Oblicza max kontraktów bazując na RZECZYWISTYM MARGINIE (z dźwignią).

    max_margin_usd = equity × MAX_EXPOSURE_PER_SYMBOL  (50% = $145 przy $290)
    margin_per_contract = (curr_price × multiplier) / leverage
    max_contracts = int(max_margin_usd / margin_per_contract)

    Przykłady przy equity=290, leverage=7:
      ETH@2000: 145 / (2000×0.01/7) = 145/2.86 = 50k  → cap 15
      BTC@84k:  145 / (84000×0.0001/7) = 145/1.20 = 120k → cap 20
    """
    cfg              = CONFIG[symbol]
    leverage         = cfg.get("leverage", 1)
    max_margin_usd   = equity * MAX_EXPOSURE_PER_SYMBOL
    margin_per_contr = (curr_price * cfg["contract_multiplier"]) / leverage
    if margin_per_contr <= 0:
        return cfg["max_contracts"]
    dynamic = int(max_margin_usd / margin_per_contr)
    # Nigdy nie przekrocz hardcap z CONFIG, nigdy poniżej min_moonbag+1
    return max(cfg["min_moonbag"] + 1, min(dynamic, cfg["max_contracts"]))


# ── M02: globalna ekspozycja USD ──────────────────────────────────────────────
def get_total_exposure_usd(all_positions):
    """
    Sumuje RZECZYWISTY MARGIN wszystkich otwartych pozycji long.
    Dzieli przez dźwignię z CONFIG żeby porównywać z equity uczciwie.

    Przykład przy ×7:
      ETH: 7 kont × 0.01 × 2057 / 7 = $20.57 rzeczywistego marginu
      BTC: 13 kont × 0.0001 × 66800 / 7 = $12.40 rzeczywistego marginu
      Razem: ~$33 (nie $231 notional)

    Limit M02 = MAX_TOTAL_EXPOSURE_PCT × equity = 75% × 290 = $217 marginu
    → możesz otworzyć dużo więcej zanim limit zostanie osiągnięty.
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
        ep       = float(p.get("entry_price", 0))
        leverage = cfg.get("leverage", 1)
        if ep > 0:
            total += sz * cfg["contract_multiplier"] * ep / leverage
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
    
    for attempt in range(3): # S04: retry logic dla transient errors
        try:
            r = requests.request(method, url, headers=sign(method, path, query, b_str),
                                data=b_str, timeout=12)
            data = r.json()
            if isinstance(data, dict) and data.get("label"):
                # Specyficzne błędy API (np. brak kasy) nie powinny być ponawiane
                print(f"  API ERR {data.get('label')} - {data.get('message','')[:60]}")
                return data
            return data
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  REQ ERR (Final Attempt) {e}")
            return {}

def get_account():
    return gate_request("GET", "/api/v4/futures/usdt/accounts")

def get_positions():
    return gate_request("GET", "/api/v4/futures/usdt/positions")

def get_price(symbol):
    with _cache_lock:
        ts = _price_timestamps.get(symbol, 0)
        if ts > 0 and time.time() - ts > PRICE_MAX_AGE:
            # Cena WSS nieaktualna – nie handluj na przeterminowanych danych
            return 0.0
        return _live_prices.get(symbol, 0.0)

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

    # TRYB AUTOMATYCZNY – cel: equity × TARGET_ENTRY_PCT per poziom
    # Zabezpieczenie: cap na 22% equity per poziom.
    max_by_equity = equity * 0.22
    target_usd    = min(equity * TARGET_ENTRY_PCT, max_by_equity)
    contract_val  = curr_price * cfg["contract_multiplier"]
    if contract_val <= 0:
        return 1
    return max(1, int(target_usd / contract_val))


# ── SESJE – helpery ───────────────────────────────────────────────────────────
def _minutes_utc():
    now = datetime.now(timezone.utc)
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
    sess = get_active_session()
    sname = sess[0] if sess else "none"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{symbol}_{today}_{sname}"

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
                    h_list.append(float(c[3]))  # index 3 = high  ([t, v, c, h, l, o])
                    l_list.append(float(c[4]))  # index 4 = low
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
def check_initial_entry(symbol, cfg, size, curr_price, equity, free_margin, buys, all_positions=None):
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

    # M04/M05: Intelligence Market Guard
    safe, mkt_reason = is_market_safe(symbol)
    if not safe:
        print(f"    ENTRY SKIP {symbol}: Zablokowane przez Inteligencje Rynku → {mkt_reason}")
        return

    now_ts        = time.time()
    last_entry_ts = last_entry_session.get(f"ts_{symbol}", 0)
    if now_ts - last_entry_ts < 7200:
        remaining = int((7200 - (now_ts - last_entry_ts)) / 60)
        print(f"    ENTRY SKIP {symbol}: cooldown {remaining} min pozostało")
        return

    # M02: global exposure guard (S02: reuse all_positions zamiast re-fetch)
    if all_positions is None:
        all_positions = get_positions()
    exp_usd       = get_total_exposure_usd(all_positions)
    max_exp_usd   = equity * MAX_TOTAL_EXPOSURE_PCT
    if exp_usd >= max_exp_usd:
        print(f"    ENTRY SKIP {symbol}: global exp {exp_usd:.0f} USD >= {max_exp_usd:.0f} USD (75%)")
        return

    base_qty = get_dynamic_size(symbol, equity, curr_price)
    dyn_max  = get_dynamic_max_contracts(symbol, equity, curr_price)
    qty      = fmt_size(min(int(base_qty * mn), dyn_max))

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
def check_dca_sweep_add(symbol, cfg, size, entry, curr_price, equity, free_margin, buys, all_positions=None):
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

    # M04/M05: Intelligence Market Guard (Ochrona DCA przy mocnym bessie i squeezie na spadkach)
    safe, mkt_reason = is_market_safe(symbol)
    if not safe:
        print(f"    BOOST SKIP {symbol}: Zablokowane przez Inteligencje Rynku → {mkt_reason}")
        return

    if curr_price >= entry:
        return

    # M01: sweep boost patrzy tylko na ROZMIAR POZYCJI (nie pending DCA orderów).
    # Pending ordery limitują siatkę DCA w manage_dca, ale nie blokują aktywnego
    # boostu podczas sweepla – M02 global exposure guard chroni rzeczywisty margin.
    dyn_max = get_dynamic_max_contracts(symbol, equity, curr_price)
    if size >= dyn_max - 1:
        print(f"    BOOST SKIP {symbol}: pozycja {size:.0f}k >= dyn_max {dyn_max}k @ {curr_price:.2f}")
        return

    # M02: global exposure guard (S02: reuse all_positions zamiast re-fetch)
    if all_positions is None:
        all_positions = get_positions()
    exp_usd     = get_total_exposure_usd(all_positions)
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
                time.sleep(0.15)
            cancelled_total += len(buys)
            if attempt < 2:
                time.sleep(0.3)

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
            time.sleep(0.3)
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
    else:
        sl_placed[symbol] = False

    # Postaw nowy SL ZANIM usuniesz stary – jeśli fail, stary zostaje aktywny
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

    # Usuń stare SL dopiero po potwierdzeniu nowego
    for o in sl_orders:
        gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{o['id']}")
        time.sleep(0.15)

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
                f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝"
            )
        last_size[symbol] = size
        return

    if size > prev:
        added = size - prev
        val   = added * cfg["contract_multiplier"] * price
        for o in sells:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.15)
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
            f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝"
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
            trade_log.append((symbol, pnl, datetime.now(timezone.utc).strftime("%H:%M")))
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
                f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝"
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
        time.sleep(0.15)

    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": -partial_qty,
        "price": "0", "tif": "ioc", "reduce_only": True,
    })
    if res.get("id"):
        fill    = float(res.get("fill_price", curr_price) or curr_price)
        pnl_est = partial_qty * cfg["contract_multiplier"] * (fill - entry)
        partial_tp_done[symbol] = True
        # K01: aktualizuj last_size żeby check_executed nie wysłał fałszywego TP/SL alertu
        last_size[symbol] = size - partial_qty
        print(f"    PARTIAL TP {symbol} -{partial_qty}k @ ~{fill:.2f} (+{profit_pct*100:.1f}%)")
        tg(
            f"💰 <b>PARTIAL TP WYKONANY</b>\n"
            f"{cfg['icon']} {symbol}\n"
            f"  Sprzedano: {partial_qty}k ({cfg.get('partial_tp_ratio',0.4)*100:.0f}%)\n"
            f"  Fill:      ~{fill:.2f} (+{profit_pct*100:.1f}%)\n"
            f"  Entry:     {entry:.2f}\n"
            f"  PnL est:   <b>~{pnl_est:+.2f} USDT</b>\n"
            f"  Pozostaje: {int(size)-partial_qty:.0f}k (trailing TP aktywny)\n"
            f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝"
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
            time.sleep(0.15)
            sells = []

    if len(sells) > 1:
        sells_sorted = sorted(sells, key=lambda o: float(o.get("price", 0)), reverse=True)
        for o in sells_sorted[1:]:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.15)
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
                time.sleep(0.15)
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
            # Guard: resetuj siatkę tylko gdy brak otwartej pozycji.
            # Przy otwartej pozycji DCA orders powinny zostać tam gdzie są –
            # jeśli cena zawróci, mamy ochronę poniżej. Reset w górę usunąłby tę siatkę.
            if size > 0:
                print(f"    GRID RESET SKIP {symbol}: otwarta pozycja – siatka DCA zostaje")
            else:
                print(f"    GRID RESET UP {symbol}: {curr_price:.2f}")
                do_reset_grid(symbol, curr_price, equity, "auto grid reset w górę")
                return

    if len(buys) > cfg["dca_levels"]:
        buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)), reverse=True)
        for o in buys_sorted[cfg["dca_levels"]:]:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.15)
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
        return 0

    if symbol == "BTC_USDT":
        btc_price_history.append(price)
        if len(btc_price_history) > 10:
            btc_price_history.pop(0)

    pos   = (next((p for p in all_positions if p["contract"] == symbol), None)
             if isinstance(all_positions, list) else None)

    # H02: guard – ignoruj short pozycje (unikaj zarządzania SL/TP/DCA w złym kierunku)
    if pos and float(pos.get("size", 0)) < 0:
        print(f"  ⚠️  {symbol} SHORT wykryta ({pos.get('size')}k) – pomijam")
        return 0

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
        _ptp_before = partial_tp_done.get(symbol, False)
        check_partial_tp(symbol, cfg, size, entry, price, sells)
        if not _ptp_before and partial_tp_done.get(symbol, False):
            # Partial TP właśnie się wykonał – odśwież zlecenia sprzedaży
            sells = [o for o in get_orders(symbol) if isize(o.get("size", 0)) < 0]
        manage_sl(symbol, cfg, size, entry, price, equity, buys)
        if size > cfg["min_moonbag"]:
            manage_tp(symbol, cfg, size, entry, price, sells)

    check_initial_entry(symbol, cfg, size, price, equity, free_margin, buys, all_positions)
    check_dca_sweep_add(symbol, cfg, size, entry, price, equity, free_margin, buys, all_positions)
    manage_dca(symbol, cfg, size, price, buys, free_margin, equity)
    return price


# ── TELEGRAM LISTENER ─────────────────────────────────────────────────────────
def listen_telegram():
    global BOT_ACTIVE, DCA_ENABLED, LAST_UPDATE_ID, equity_guard_fired, ibkr_withdrawn
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
                        with _state_lock:
                            BOT_ACTIVE = False
                        tg("🛑 <b>Bot zatrzymany</b>")

                    elif msg == "/start":
                        with _state_lock:
                            BOT_ACTIVE = True
                            equity_guard_fired = False
                        tg("🚀 <b>Bot uruchomiony!</b>")

                    elif msg == "/dca_off":
                        with _state_lock:
                            DCA_ENABLED = False
                        tg("⏸ <b>DCA wyłączone</b>")

                    elif msg == "/dca_on":
                        with _state_lock:
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
                                            f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝"
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
                        
                        btc_safe, btc_r = is_market_safe("BTC_USDT")
                        if btc_safe:
                            regime_str = "🟢 ZDROWY (Brak barier)"
                        else:
                            regime_str = f"🔴 ZABLOKOWANY ({btc_r.split('(')[0].strip()})"
                            
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
                            f"╚══ {datetime.now(timezone.utc).strftime('%H:%M %d.%m')} ══╝"
                        )

                    elif msg == "/pozycje":
                        acc_poz = get_account()
                        eq_poz  = float(acc_poz.get("total", 0)) if isinstance(acc_poz, dict) else 0
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
                                    dyn_m  = get_dynamic_max_contracts(sym, eq_poz, price) if price > 0 else "?"
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/grid":
                        acc_grid = get_account()
                        eq_grid  = float(acc_grid.get("total", 0)) if isinstance(acc_grid, dict) else 0
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
                            dyn_m = get_dynamic_max_contracts(sym, eq_grid, price) if price > 0 else "?"
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M')} ══╝")
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
                        lines.append(f"╚══ {datetime.now(timezone.utc).strftime('%H:%M %d.%m')} ══╝")
                        tg("\n".join(lines))

                    elif msg == "/withdraw_calc":
                        global ibkr_withdrawn
                        acc_w    = get_account()
                        eq_w     = float(acc_w.get("total", 0)) if isinstance(acc_w, dict) else 0
                        base     = starting_eq if starting_eq > 0 else eq_w
                        surplus  = max(0.0, eq_w - base)
                        safe_w   = surplus * 0.5
                        after_w  = eq_w - safe_w
                        GOAL_EUR = 125000
                        progress = (ibkr_withdrawn / (GOAL_EUR * 1.08) * 100) if GOAL_EUR > 0 else 0
                        # 1.08 = przybliżony kurs EUR/USD
                        tg(
                            f"╔══ 💸 <b>KALKULATOR WYPŁATY IBKR</b> ══╗\n"
                            f"  Baza startowa:    <b>{base:.2f} USDT</b>\n"
                            f"  Aktualne equity:  <b>{eq_w:.2f} USDT</b>\n"
                            f"  Nadwyżka:         <b>{surplus:.2f} USDT</b>\n"
                            f"  ━━━━━━━━━━━━━━━\n"
                            f"  💰 Bezpieczna wypłata (50%):\n"
                            f"     <b>{safe_w:.2f} USDT</b>\n"
                            f"  Po wypłacie equity: {after_w:.2f} USDT\n"
                            f"  ━━━━━━━━━━━━━━━\n"
                            f"  💼 IBKR łącznie: <b>{ibkr_withdrawn:.2f} USDT</b>\n"
                            f"  🎯 Cel: 125 000 EUR\n"
                            f"  📊 Postęp: <b>{progress:.3f}%</b>\n"
                            f"  ━━━━━━━━━━━━━━━\n"
                            f"  ℹ️ Użyj /ibkr_add [kwota] aby\n"
                            f"     zarejestrować wypłatę\n"
                            f"╚══ {datetime.now(timezone.utc).strftime('%H:%M %d.%m')} ══╝"
                        )

                    elif msg.startswith("/ibkr_add"):
                        parts_i = msg.split()
                        if len(parts_i) < 2:
                            tg("💼 <b>Użycie: /ibkr_add 125.50</b>\n"
                               "Rejestruje wypłatę do IBKR/IWDA.\n"
                               "Kwota w USDT.")
                        else:
                            try:
                                amount = float(parts_i[1].replace(",", "."))
                                if amount <= 0:
                                    raise ValueError
                                ibkr_withdrawn += amount
                                GOAL_USD = 125000 * 1.08
                                progress = ibkr_withdrawn / GOAL_USD * 100
                                tg(
                                    f"✅ <b>Wypłata zarejestrowana</b>\n"
                                    f"  Kwota:          +{amount:.2f} USDT\n"
                                    f"  IBKR łącznie:   <b>{ibkr_withdrawn:.2f} USDT</b>\n"
                                    f"  Postęp do celu: <b>{progress:.3f}%</b>\n"
                                    f"  ━━━━━━━━━━━━━━━\n"
                                    f"  ℹ️ Kwota resertuje się po restarcie bota.\n"
                                    f"     Zapisz ją ręcznie!"
                                )
                            except ValueError:
                                tg("❌ Nieprawidłowa kwota. Użyj: /ibkr_add 125.50")

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
                            "╔══ 📖 <b>KOMENDY v2.16</b> ══╗\n"
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
                            "💸 /withdraw_calc     — kalkulator wypłaty IBKR\n"
                            "💼 /ibkr_add [kwota]  — rejestruj wypłatę\n"
                            "━━━━━━━━━━━━━━━\n"
                            "▶️ /start  🛑 /stop\n"
                            "✅ /dca_on  ⏸ /dca_off\n"
                            "🔄 /reset_dca BTC/ETH/SOL/ALL\n"
                            "╚══════════════════╝"
                        )

        except Exception as e:
            print(f"  TG ERR {e}")
        time.sleep(2)



# ── DATA FEED WORKER ──────────────────────────────────────────────────────────
def data_feed_worker():
    """Wątek odświeżania danych: konto, pozycje, guardy, raporty co 10s."""
    global _cached_account, _cached_positions
    global session_pnl_start, equity_guard_fired, equity_guard_day, BOT_ACTIVE
    global starting_eq

    _last_zone_h  = -1
    _last_report  = time.time()

    while True:
        if not BOT_ACTIVE:
            time.sleep(5)
            continue

        try:
            acc = get_account()
            pos = get_positions()

            # Zabezpieczenie przed timeoutami: jeśli API nie zwróciło słownika (acc) 
            # lub listy (pos) – nie dotykaj cache i nie sprawdzaj guardów.
            if not isinstance(acc, dict) or not isinstance(pos, list):
                time.sleep(10)
                continue

            # Jeśli konto jest puste (np. błąd API który zwrócił {}) – skacz dalej
            if "total" not in acc:
                time.sleep(10)
                continue

            # Aktualizuj cache (thread-safe)
            with _cache_lock:
                _cached_account  = acc
                _cached_positions = pos

            eq  = float(acc.get("total", 0))
            fr  = float(acc.get("available", 0))
            pnl = float(acc.get("unrealised_pnl", 0))

            # Starting equity
            if starting_eq == 0 and eq > 0:
                starting_eq       = eq
                session_pnl_start = eq
                print(f"  Equity startowe: {starting_eq:.2f} USDT")

            # P04: daily equity guard reset
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if equity_guard_day != today_str and eq > 0:
                if equity_guard_day != "":
                    prev_base          = starting_eq
                    starting_eq        = eq
                    session_pnl_start  = eq
                    equity_guard_fired = False
                    equity_guard_day   = today_str
                    print(f"  [P04] Dzienny reset: {prev_base:.2f}→{eq:.2f} USDT")
                    tg(
                        f"🌅 <b>Dzienny reset equity guard</b>\n"
                        f"  Nowa baza: <b>{eq:.2f} USDT</b>\n"
                        f"  Guard przy: <b>{eq*0.75:.2f} USDT</b> (-25%)\n"
                        f"╚══ {datetime.now(timezone.utc).strftime('%H:%M %d.%m')} ══╝"
                    )
                else:
                    equity_guard_day = today_str

            # Equity guard
            if starting_eq > 0 and eq < starting_eq * 0.75 and not equity_guard_fired:
                with _state_lock:
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

            # Margin alerts
            now_ts = time.time()
            if 0 < fr < 80:
                if now_ts - last_margin_alert.get("warn", 0) > 1800:
                    tg(f"⚠️ <b>Free margin:</b> <b>{fr:.2f} USDT</b>")
                    last_margin_alert["warn"] = now_ts
            if 0 < fr < 50:
                if now_ts - last_margin_alert.get("crit", 0) > 900:
                    tg(f"🚨 <b>ALARM! Krytyczny margin: {fr:.2f} USDT</b>")
                    last_margin_alert["crit"] = now_ts

            # Session zones (hourly)
            curr_hour = datetime.now(timezone.utc).hour
            if curr_hour != _last_zone_h:
                update_session_zones()
                _last_zone_h = curr_hour

            # WSS health check – alert gdy ceny nieaktualne
            # Grace period po reconnect: czekaj WSS_GRACE_PERIOD sekund zanim
            # wyślesz stale alert (WSS potrzebuje chwili na pierwsze tickery).
            if now_ts - _wss_reconnect_ts > WSS_GRACE_PERIOD:
                for sym in (s for s, c in CONFIG.items() if c["active"]):
                    with _cache_lock:
                        wss_ts = _price_timestamps.get(sym, 0)
                    if wss_ts > 0 and now_ts - wss_ts > PRICE_MAX_AGE:
                        wss_key = f"wss_{sym}"
                        if now_ts - last_margin_alert.get(wss_key, 0) > 1800:
                            down_sec = int(now_ts - wss_ts)
                            tg(f"⚠️ <b>WSS STALE:</b> {sym}\n"
                               f"  Brak ceny od {down_sec}s — trading wstrzymany dla {sym}")
                            last_margin_alert[wss_key] = now_ts

            # Status log
            crash_str = " [CRASH]" if is_market_crashing() else ""
            sess = get_active_session()
            sess_str = f" [{sess[0]}]" if sess else ""
            print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] DataFeed | "
                  f"Eq: {eq:.2f} | Free: {fr:.2f} | PnL: {pnl:+.2f}{crash_str}{sess_str}")

            # Hourly report (co ~60 min)
            if now_ts - _last_report >= 3600:
                _last_report = now_ts
                all_pos_r = get_cached_positions()
                exp_r     = get_total_exposure_usd(all_pos_r)
                ords = ""
                for sym, cfg_r in CONFIG.items():
                    if not cfg_r["active"]:
                        continue
                    o = get_orders(sym)
                    if o:
                        b = len([x for x in o if isize(x.get("size", 0)) > 0])
                        s = len([x for x in o if isize(x.get("size", 0)) < 0])
                        ords += f"\n{cfg_r['icon']} {sym}: {b}× buy / {s}× sell"
                gain = eq - session_pnl_start if session_pnl_start > 0 else 0
                
                btc_safe, btc_r = is_market_safe("BTC_USDT")
                if btc_safe:
                    regime_str = "🟢 ZDROWY (Brak barier)"
                else:
                    regime_str = f"🔴 ZABLOKOWANY ({btc_r.split('(')[0].strip()})"

                tg(
                    f"╔══ 📊 <b>Raport godzinny</b> ══╗\n"
                    f"💰 Equity:  <b>{eq:.2f} USDT</b>\n"
                    f"💵 Wolne:   <b>{fr:.2f} USDT</b>\n"
                    f"📈 PnL:     <b>{pnl:+.2f} USDT</b>\n"
                    f"💹 Sesja:   <b>{gain:+.2f} USDT</b>\n"
                    f"📦 Exp:     <b>{exp_r:.0f}/{eq*MAX_TOTAL_EXPOSURE_PCT:.0f} USD</b>\n"
                    f"🤖 Rynek:   <b>{regime_str}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📋 Zlecenia:{ords if ords else ' Brak'}\n"
                    f"╚══ {datetime.now(timezone.utc).strftime('%H:%M %d.%m')} ══╝"
                )

        except Exception as e:
            print(f"  DataFeed ERR: {e}")

        time.sleep(10)


# ── SYMBOL WORKER ─────────────────────────────────────────────────────────────
def symbol_worker(symbol):
    """Niezależny wątek per symbol: cena → sweep → SL/TP/DCA co 8s."""
    cfg = CONFIG[symbol]
    print(f"  [{symbol}] Worker uruchomiony")

    while True:
        if not BOT_ACTIVE:
            time.sleep(3)
            continue

        try:
            # Pobierz dane z cache (odświeżane przez data_feed_worker)
            acc     = get_cached_account()
            eq      = float(acc.get("total", 0)) if acc else 0
            fr      = float(acc.get("available", 0)) if acc else 0
            all_pos = get_cached_positions()

            if eq <= 0:
                time.sleep(3)
                continue

            # Główna logika tradingowa (get_price wywoływane wewnątrz)
            price = manage_logic(symbol, cfg, fr, eq, all_pos)



        except Exception as e:
            print(f"  [{symbol}] ERR: {e}")

        time.sleep(2)  # Cena pochodzi z WSS (0ms latency). REST API (get_orders itp.)
                       # wywoływane co 2s – wystarczy do zarządzania DCA/SL/TP
                       # i nie przeciąża limitu zapytań Gate.io (~120 req/min dla 2 symboli).


# ── WEBSOCKET PRICE FEED (0ms Latency) ───────────────────────────────────────
def websocket_price_worker():
    """Wątek utrzymujący asynchroniczny strumień WSS z serwerami Gate.io."""
    print("  [WebSocket] Inicjowanie superszybkiego silnika cenowego...")
    _wss_state = {"was_disconnected": False, "disconnect_ts": 0}

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("event") == "update" and data.get("channel") == "futures.tickers":
                now = time.time()
                for item in data.get("result", []):
                    sym = item.get("contract")
                    price = float(item.get("last", 0))
                    if sym and price > 0:
                        with _cache_lock:
                            _live_prices[sym] = price
                            _price_timestamps[sym] = now
        except Exception:
            pass

    def on_error(ws, error):
        # Ciche ignorowanie błędów sieciowych - auto-reconnect zadba o resztę
        pass

    def on_close(ws, close_status_code, close_msg):
        _wss_state["was_disconnected"] = True
        _wss_state["disconnect_ts"]    = time.time()
        print("  [WebSocket] Rozłączono strumień WSS, auto-wznawiam...")
        time.sleep(2)

    def on_open(ws):
        global _wss_reconnect_ts
        print("  [WebSocket] Połączono! Zaczynam pobierać Strumień Cen LIVE...")
        if _wss_state["was_disconnected"]:
            down_sec = int(time.time() - _wss_state["disconnect_ts"])
            tg(f"🔄 <b>WSS reconnected</b> — strumień cen przywrócony\n"
               f"  Przerwa: ~{down_sec}s")
        _wss_reconnect_ts = time.time()
        _wss_state["was_disconnected"] = False
        symbols = [s for s, cfg in CONFIG.items() if cfg["active"]]
        if symbols:
            subs = {
                "time": int(time.time()),
                "channel": "futures.tickers",
                "event": "subscribe",
                "payload": symbols
            }
            ws.send(json.dumps(subs))

    while True:
        if not BOT_ACTIVE:
            time.sleep(5)
            continue
            
        symbols = [s for s, cfg in CONFIG.items() if cfg["active"]]
        if not symbols:
            time.sleep(5)
            continue

        try:
            ws = websocket.WebSocketApp(
                "wss://fx-ws.gateio.ws/v4/ws/usdt",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(ping_interval=15, ping_timeout=10)
        except Exception as e:
            print(f"  [WebSocket] Wątek Główny WSS padł: {e}")
        time.sleep(5)

# ── MARKET INTELLIGENCE WORKER ────────────────────────────────────────────────
def market_intelligence_worker():
    """Wątek sprawdzający Funding Rate oraz giełdowe uderzenia w SMA."""
    global _market_regime
    print("  [Intel] Wątek nałożony — analizuję trendy rynku...")
    while True:
        if not BOT_ACTIVE:
            time.sleep(10)
            continue
            
        try:
            for sym, cfg in CONFIG.items():
                if not cfg["active"]: continue
                
                # 1. Funding Rate (Sentyment Rynku / Dźwigniomierz)
                try:
                    res_fund = gate_request("GET", f"/api/v4/futures/usdt/contracts/{sym}")
                    if isinstance(res_fund, dict) and 'funding_rate' in res_fund:
                        frate = float(res_fund.get('funding_rate', 0))
                        overheated = frate > MAX_FUNDING_RATE
                        with _cache_lock:
                            _market_regime["funding_overheated"][sym] = overheated
                except Exception as e:
                    pass
                    
                # 2. SMA Guard (Trend / Death Cross protector)
                try:
                    res_k = gate_request("GET", "/api/v4/futures/usdt/candlesticks",
                                         {"contract": sym, "interval": SMA_INTERVAL, "limit": str(SMA_PERIODS)})
                    if isinstance(res_k, list) and len(res_k) == SMA_PERIODS:
                        # Close to indeks numer 2 w zapytaniu Gateio ([t, v, c, h, l, o])
                        closes = [float(k[2]) for k in res_k]
                        sma = sum(closes) / len(closes)
                        current_price = closes[-1]
                        
                        downtrend = current_price < (sma * (1.0 - TREND_DIP_THRESHOLD_PCT))
                        with _cache_lock:
                            _market_regime["downtrend_active"][sym] = downtrend
                except Exception as e:
                    pass
                    
        except Exception as e:
            print(f"  [Intel] Błąd Główny: {e}")
            
        time.sleep(180) # Sprawdza w tle co 3 minuty

# ── GŁÓWNA PĘTLA (THREADED) ──────────────────────────────────────────────────
def run():
    global BOT_ACTIVE, equity_guard_fired

    print("=" * 62)
    print("  FreedomTracker Bot v2.16 PRODUCTION [ODRZUTOWIEC WSS]")
    print("  Architektura: WSS(0ms) + Intel(180s) + Workers(2s)")
    print("  /help /status /pozycje /sl /sweep /sessions /grid /pnl /buy /close")
    print("=" * 62)
    tg(
        "╔══ 🤖 <b>FreedomTracker v2.16 PRODUCTION</b> ══╗\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🧵 Architektura Odrzutowiec WSS:\n"
        "   • WSSBot: Live Price 0ms Streamer\n"
        "   • IntelBot: SMA50 4h + FundingRate\n"
        "   • Market Workers: cykl 2s (REST ~120 req/min)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔧 <b>v2.16 — poprawki:</b>\n"
        "   ✅ WSS staleness guard (cena >60s → skip)\n"
        "   ✅ Czasy UTC w całym bocie\n"
        "   ✅ Grid reset guard (blok gdy pozycja na stracie)\n"
        "   ✅ Thread-safe: BOT_ACTIVE / DCA / guard\n"
        "   ✅ Rate limit fix: Workers 0.5s → 2s\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🛡 M01..M05 | Antyspam | Partial TP | 5 sesji\n"
        "📖 /help — lista komend\n"
        "╚══════════════════════╝"
    )

    equity_guard_fired = False

    # 1. Data feed thread (konto + pozycje + guardy + raporty)
    threading.Thread(target=data_feed_worker, daemon=True, name="DataFeed").start()
    print("  [DataFeed] Wątek uruchomiony — czekam na dane...")
    time.sleep(4)

    # 2. Telegram listener
    threading.Thread(target=listen_telegram, daemon=True, name="Telegram").start()
    print("  [Telegram] Wątek uruchomiony")

    # 3. Symbol workers — jeden wątek per aktywny symbol
    active_symbols = []
    for sym, cfg in CONFIG.items():
        if cfg["active"]:
            threading.Thread(
                target=symbol_worker, args=(sym,),
                daemon=True, name=f"Worker-{sym}"
            ).start()
            active_symbols.append(sym)

    print(f"  [Workers] Uruchomiono: {', '.join(active_symbols)}")
    
    # 4. Market Intelligence Thread (Strażnik Rynku)
    threading.Thread(target=market_intelligence_worker, daemon=True, name="Intel").start()
    print("  [Intel] Moduł Inteligencji dołączony.")
    
    # 5. WebSocket Live Price Feed (0ms Latency)
    threading.Thread(target=websocket_price_worker, daemon=True, name="WSS").start()
    
    print("=" * 62)

    # Main thread: keep alive (wątki daemon zamkną się same przy Ctrl+C)
    while True:
        time.sleep(60)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nBot zatrzymany (CTRL+C)")
        tg("🛑 <b>Bot zatrzymany ręcznie</b>")
    except Exception as e:
        print(f"\nKRYTYCZNY BŁĄD: {e}")
        tg(f"🚨 <b>KRYTYCZNY BŁĄD!</b>\n<code>{str(e)[:200]}</code>")

