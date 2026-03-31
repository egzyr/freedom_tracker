                do_reset_grid(symbol, curr_price, equity, "auto grid reset w górę")
                return
            elif (distance_up > cfg["grid_step"]
                  and size == 0
                  and time_since_slide > 60):
                # Cena wyszła o 1 grid_step ponad siatkę, brak pozycji →
                # delikatne przesunięcie: usuń L_last, dodaj nowy L1 tuż pod ceną
                print(f"    GRID SLIDE {symbol}: {curr_price:.2f} ({distance_up*100:.1f}% > grid_step)")
                do_slide_grid(symbol, curr_price, equity, buys)
                return

    # Usuń nadmiarowe buy limity
    if len(buys) > cfg["dca_levels"]:
        buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)), reverse=True)
        to_remove   = buys_sorted[cfg["dca_levels"]:]
        for o in to_remove:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        print(f"    CLEANUP {symbol}: usunieto {len(to_remove)} nadmiarowych")
        buys = buys_sorted[:cfg["dca_levels"]]

    total_exp = size + sum(isize(o.get("size", 0)) for o in buys)  # B11
    if total_exp >= cfg["max_contracts"] or len(buys) >= cfg["dca_levels"]:
        return

    is_sweep, sweep_reason, sess_name = detect_sweep(symbol, curr_price)
    _, _, sess_cfg = get_session_info()
    now_ts    = time.time()
    scalp_key = symbol + "_scalp"  # B14: dedykowany klucz dla scalp cooldown
    scalp_ok  = (now_ts - sweep_last_notify.get(scalp_key, 0)) > 900

    if is_sweep and size == 0 and scalp_ok:
        # v2.7.0: size_mult per sesja zamiast hardkodowanego 2.5
        sweep_mult  = sess_cfg.get("size_mult", 2.5)
        sweep_label = f"SCALP {sess_name}"
        sweep_last_notify[scalp_key] = now_ts
    elif is_sweep and size > 0:
        sweep_mult  = 1.5
        sweep_label = f"BOOST {sess_name}"
    else:
        sweep_mult  = 1.0
        sweep_label = ""

    needed = cfg["dca_levels"] - len(buys)
    added  = 0
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
        remaining = cfg["max_contracts"] - total_exp - added
        if remaining <= 0:
            break
        if total_exp + added + qty > cfg["max_contracts"]:
            qty = remaining
        res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": qty,
            "price": fmt_price(target, symbol), "tif": "gtc",
        })
        if res.get("id"):
            lbl = f"L{i}" if i > 1 else f"L1({sweep_label or 'DCA'})"
            print(f"    DCA {symbol} {lbl} @ {fmt_price(target, symbol)} x{qty}k")
            added += 1
        time.sleep(0.5)


def do_slide_grid(symbol, curr_price, equity, buys):
    """
    Przesuwa siatkę DCA w górę o 1 poziom bez pełnego resetu.
    Usuwa najniższy (najdalszy) buy limit i stawia nowy L1 tuż pod bieżącą ceną.
    Uruchamiany gdy cena wychodzi powyżej siatki o co najmniej grid_step.
    Tylko gdy brak otwartej pozycji (gdy jest pozycja, DCA to siatka bezpieczeństwa).
    Cooldown 60 sekund – nie slajduje zbyt gwałtownie przy ostrych ruchach.
    """
    cfg = CONFIG[symbol]
    if not buys:
        return

    # Nowy L1 – jeden grid_step pod bieżącą ceną
    new_target = curr_price * (1 - cfg["grid_step"])

    # Nie slajduj jeśli nowy L1 za blisko (< 1.5%) istniejącego buy
    if any(abs(new_target - float(o.get("price", 0))) / new_target < 0.015 for o in buys):
        print(f"    SLIDE SKIP {symbol}: nowy L1 {new_target:.2f} zbyt blisko istniejącego")
        return

    # Usuń najniższy (najdalszy od ceny) buy limit
    buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)))
    lowest      = buys_sorted[0]
    low_price   = float(lowest.get("price", 0))
    low_sz      = isize(lowest.get("size", 0))
    gate_request("DELETE", f"/api/v4/futures/usdt/orders/{lowest['id']}")
    time.sleep(0.3)

    # Postaw nowy L1
    qty = fmt_size(get_dynamic_size(symbol, equity, curr_price))
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": qty,
        "price": fmt_price(new_target, symbol), "tif": "gtc",
    })
    grid_slide_time[symbol] = time.time()

    if res.get("id"):
        dist_old = (curr_price - low_price) / curr_price * 100
        dist_new = (curr_price - new_target) / curr_price * 100
        tg(
            f"🔼 <b>SIATKA PRZESUNIĘTA ↑</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🗑 Usunięto: {low_price:.2f} x{low_sz}k  (-{dist_old:.1f}%)\n"
            f"➕ Nowy L1:  <b>{fmt_price(new_target, symbol)}</b> x{qty}k  (-{dist_new:.1f}%)\n"
            f"📌 Cena:     {curr_price:.2f}"
        )
        print(f"  GRID SLIDE {symbol}: -{low_price:.2f} +L1@{new_target:.2f}")
    else:
        print(f"  GRID SLIDE FAIL {symbol}: {res.get('label','?')}")


def manage_logic(symbol, cfg, free_margin, equity, all_positions):
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
    buys   = [o for o in orders if isize(o.get("size", 0)) > 0]   # B01
    sells  = [o for o in orders if isize(o.get("size", 0)) < 0]   # B01

    pct_str = f"{(price-entry)/entry*100:+.1f}%" if entry > 0 else "---"
    print(f"  {cfg['icon']}  {symbol:<10} {price:>9.2f}  poz={size:.0f}k {pct_str}"
          f"  buy={len(buys)} sell={len(sells)}")

    if size > 0:
        check_executed(symbol, cfg, size, entry, price, sells)  # B03: przekazane sells
        # Scalp exit ma priorytet – jeśli zwróci True, pomijamy normalny SL/TP
        if not manage_scalp_exit(symbol, cfg, size, price, sells):
            manage_sl(symbol, cfg, size, entry, price, equity, buys)
            if size > cfg["min_moonbag"]:
                manage_tp(symbol, cfg, size, entry, price, sells)

    # S01: sprawdź czy potrzeba initial entry (gdy brak pozycji i brak grid)
    check_initial_entry(symbol, cfg, size, price, equity, free_margin, buys, all_positions)
    manage_dca(symbol, cfg, size, price, buys, free_margin, equity)


def run():
    global BOT_ACTIVE, session_pnl_start, equity_guard_fired
    threading.Thread(target=listen_telegram, daemon=True).start()
    print("=" * 55)
    print("  FreedomTracker Bot v2.8.2")
    print("  BTC + ETH | DCA Grid | Multi-sesja Sweep Scalp")
    print("  /help /status /pozycje /sl /trailing /sweep /grid /pnl")
    print("=" * 55)
    tg(
        "╔══════════════════════╗\n"
        "🤖 <b>FreedomTracker v2.8.2</b>\n"
        "╚══════════════════════╝\n"
        "━━━━━━━━━━━━━━━\n"
        "🟠 BTC  |  🔵 ETH  aktywne\n"
        "━━━━━━━━━━━━━━━\n"
        "✅ DCA Grid 5 poziomów\n"
        "✅ Dynamic SL + Breakeven\n"
        "✅ Trailing TP (+3% trigger)\n"
        "✅ Multi-sesja: ASIA/LONDON/LUNCH/NY/REVERSAL/MIDNIGHT\n"
        "✅ Scalp exit: TP+1.5% / SL-1% / 25min\n"
        "✅ Crash detection BTC -3%\n"
        "✅ Equity Guard -25%\n"
        "━━━━━━━━━━━━━━━\n"
        "📖 /help — komendy\n"
        f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )

    cycle        = 0
    last_zone_h  = -1
    starting_eq  = 0
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

            # Gdy API zwróci pusty dict (timeout) eq=0 – pomijamy cykl, nie handlujemy
            if eq == 0:
                print(f"  [SKIP] eq=0 – brak odpowiedzi API, czekam 20s")
                time.sleep(20)
                continue

            if starting_eq == 0 and eq > 0:
                starting_eq       = eq
                session_pnl_start = eq   # S02: zapisz start equity dla /pnl
                print(f"  Equity startowe: {starting_eq:.2f} USDT")

            # B13: equity guard odpala tylko raz (nie w kółko po /start)
            # eq > 0: guard nie odpala gdy API zwróci błąd (eq=0 = brak odpowiedzi, nie strata)
            if (starting_eq > 0 and eq > 0 and eq < starting_eq * 0.75
                    and not equity_guard_fired):
                equity_guard_fired = True
                BOT_ACTIVE = False
                spadek = round((1 - eq / starting_eq) * 100, 1)
                tg(
                    f"🚨 <b>EQUITY GUARD!</b>\n"
                    f"Start:  {starting_eq:.2f} USDT\n"
                    f"Teraz:  {eq:.2f} USDT\n"
                    f"Spadek: -{spadek}%\n"
                    f"Bot zatrzymany. /start aby wznowić."
                )
                print(f"  EQUITY GUARD: bot zatrzymany (equity -{spadek}%)")

            # B06: margin alert z cooldownem 30 minut
            now_ts = time.time()
            if 0 < fr < 80:
                last_alert = last_margin_alert.get("warn", 0)
                if now_ts - last_alert > 1800:
                    tg(f"⚠️ <b>Uwaga!</b> Free margin: <b>{fr:.2f} USDT</b>")
                    last_margin_alert["warn"] = now_ts
            if 0 < fr < 50:
                last_alert = last_margin_alert.get("crit", 0)
                if now_ts - last_alert > 900:
                    tg(f"🚨 <b>ALARM!</b> Krytyczny margin: <b>{fr:.2f} USDT</b>")
                    last_margin_alert["crit"] = now_ts

            curr_hour = datetime.now().hour   # v2.7.0: czas lokalny Pi
            if curr_hour != last_zone_h:
                update_session_zones()
                last_zone_h = curr_hour

            # Sweep alert – wszystkie sesje (v2.7.0)
            is_sess, sess_name_now, sess_cfg_now = get_session_info()
            if is_sess:
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    p = get_price(sym)
                    if p <= 0:
                        continue
                    is_sw, reason, s_name = detect_sweep(sym, p)
                    if is_sw:
                        last_notif = sweep_last_notify.get(sym, 0)
                        if (time.time() - last_notif) > 900:
                            sweep_last_notify[sym] = time.time()
                            zone    = session_zones.get(sym, {})
                            all_pos = get_positions()
                            # B07: isinstance sprawdzony raz, poza generatorem
                            has_pos = False
                            if isinstance(all_pos, list):
                                pos_sw  = next((px for px in all_pos
                                                if px["contract"] == sym), None)
                                has_pos = pos_sw is not None and float(pos_sw.get("size", 0)) != 0
                            s_mult  = sess_cfg_now.get("size_mult", 1.0)
                            s_icon  = sess_cfg_now.get("icon", "🎯")
                            scalp_en = sess_cfg_now.get("scalp", True)
                            if scalp_en:
                                akcja = f"🎯 SCALP {s_mult:.1f}x" if not has_pos else "⚡ DCA BOOST 1.5x"
                            else:
                                akcja = "⚡ DCA BOOST" if has_pos else "⬜ Bez scalpa (ta sesja)"
                            tg(
                                f"{s_icon} <b>SWEEP! {s_name}</b>\n"
                                f"{cfg['icon']} <b>{sym}</b>\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"📍 Cena:    <b>{p:.2f}</b>\n"
                                f"📉 Low:     {zone.get('low', 0):.2f}\n"
                                f"⚡ Sygnał:  {reason}\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"🚀 Akcja:   <b>{akcja}</b>"
                            )
                        else:
                            remaining = int((900 - (time.time() - last_notif)) / 60)
                            print(f"    [SWEEP] {sym} {s_name} cooldown {remaining} min")

            crash_str = " [CRASH]" if is_market_crashing() else ""
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cykl {cycle} | "
                  f"Eq: {eq:.2f} | Free: {fr:.2f} | PnL: {pnl:+.2f}{crash_str}")
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
                        b = len([x for x in o if isize(x.get("size", 0)) > 0])   # B01
                        s = len([x for x in o if isize(x.get("size", 0)) < 0])   # B01
                        ords += f"\n{cfg['icon']} {sym}: {b}x buy / {s}x sell"
                gain = eq - session_pnl_start if session_pnl_start > 0 else 0
                tg(
                    f"╔══ 📊 <b>Raport godzinny</b> ══╗\n"
                    f"💰 Equity:  <b>{eq:.2f} USDT</b>\n"
                    f"💵 Wolne:   <b>{fr:.2f} USDT</b>\n"
                    f"📈 PnL:     <b>{pnl:+.2f} USDT</b>\n"
                    f"💹 Sesja:   <b>{gain:+.2f} USDT</b>\n"
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
EOF

sudo journalctl -u freedom_bot.service -f
sudo nano /etc/resolv.conf
sudo journalctl -u freedom_bot.service -f
sed -i 's/timeout=15/timeout=30/g' /home/barte/freedom_bot.py
sudo sh -c 'echo "nameserver 8.8.8.8\nnameserver 8.8.4.4" > /etc/resolv.conf'
pkill -9 -f python3 && sleep 2 && python3 /home/barte/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sudo nano /etc/dhcpcd.conf
sed -i 's/timeout=[0-9]*/timeout=7/g' /home/barte/freedom_bot.py
sed -i 's/time.sleep(1)/time.sleep(2)/g' /home/barte/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sed -i 's/time.sleep([0-9.]*)/time.sleep(3)/g' /home/barte/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sudo nano /etc/resolv.conf
sed -i 's/time.sleep([0-9.]*)/time.sleep(5)/g' /home/barte/freedom_bot.py
ping -c 10 google.com
sudo ifconfig wlan0 down && sleep 2 && sudo ifconfig wlan0 up
sudo journalctl -u freedom_bot.service -f
sed -i 's/api.telegram.org", timeout=[0-9]*/api.telegram.org", timeout=15/g' /home/barte/freedom_bot.py
sed -i 's/time.sleep([0-9.]*)/time.sleep(5)/g' /home/barte/freedom_bot.py
sudo pkill -9 -f python3 && sleep 5 && ps aux | grep python3
sudo pkill -9 -f python3 && sleep 3 && ps aux | grep python3
sudo nano /etc/dhcpcd.conf
sed -i 's/timeout=[0-9]*/timeout=10/g' /home/barte/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sed -i 's/time.sleep([0-9.]*)/time.sleep(10)/g' /home/barte/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
cat << 'EOF' > /home/barte/freedom_bot.py
"""
FreedomTracker Bot v2.8.0
─────────────────────────────
v2.8.2: KRYTYCZNY FIX sweepów – session_low nie aktualizowany tick-po-ticku
        Poprzednio: low = curr_price → trigger = curr_price*0.997 → niemożliwy przy płynnym spadku
        Teraz: low z zamkniętych świec 5m, odświeżany co 15 min → trigger jest stały i realny
v2.8.1: do_slide_grid() – siatka DCA sama przesuwa się w górę za ceną (bez pełnego resetu)
        Trigger: cena wychodzi o grid_step ponad najwyższy buy + brak pozycji + cooldown 60s
        Usuwa najniższy (najdalszy) buy limit i stawia nowy L1 tuż pod bieżącą ceną
        Pełny reset (grid_reset_pct=5%) nadal działa gdy cena ucieknie za daleko
v2.8.0: Pełny audit linijka po linijce – naprawione wszystkie znalezione bugi:
        B15 – manage_dca: cap na max_contracts przy zapełnianiu siatki (był off-by-one)
        B16 – check_executed: scalp_sl_id teraz czyszczony gdy pozycja w pełni zamknięta
        B17 – /help: "London Sweep" → "Multi-sesja Sweep" (odzwierciedla v2.7.x)
        B18 – /status: usunięta martwa zmienna total_exp_usdt (nigdy nieużywana)
        B19 – run() startup TG: dodane LONDON_LUNCH i NY_REVERSAL do listy sesji
        B20 – /sweep: next-session fallback na jutro gdy wszystkie sesje dnia minęły
v2.7.1: Per-session low tracking – każda sesja śledzi własne minimum (5m candles)
        /sweep pokazuje session_low, próg triggera i następną sesję
        /status pokazuje aktywną sesję z ikoną i trybem scalpa
v2.7.0: Multi-sesja – ASIA/LONDON/NY_OPEN/NY_REVERSAL/MIDNIGHT (czas lokalny Pi)
        Per-sesja: sweep_pct, size_mult, scalp on/off
        Max 2 pozycje jednocześnie – ochrona marginu
        SL scalpa jako price order na giełdzie (offline-safe)
v2.6.0: trailing_trigger 0.03 (było 0.02) – BTC/ETH nie resetuje TP przy małych ruchach
        Przepisane wiadomości Telegram – czytelniejsze, ładniejsze formatowanie
v2.5.5: CONFIG – konserwatywne parametry (risk 1%, max_contracts -50%, sl_pct 8%)
        SOL wyłączony (active=False) – BTC+ETH wystarczy, lepsza kontrola marginu
v2.5.4: S04 – dedykowany scalp exit (TP +1.5%, SL -1%, timeout 25 min)
        manage_scalp_exit() ma priorytet nad normalnym SL/TP gdy scalp aktywny
v2.5.3: B16 fix – scalp entry MARKET BUY zamiast limit
        Eliminuje: niewykonane scalpy gdy cena odbija zbyt szybko po sweepie
v2.5.2: B15 fix – do_reset_grid weryfikuje po kasowaniu (max 3 próby)
        Eliminuje: podwójną siatkę (1981/1979 obok siebie)
v2.5.1: Race condition fix – grid_resetting flag + 30s cooldown
        Eliminuje: podwójny reset ETH/SOL, 7 DCA na BTC

NAPRAWIONE BUGI (audit linijka po linijce):
  B01 - int(float()) wszędzie gdzie size pochodzi z API (było int() → crash na "5.0")
  B02 - manage_tp: sprawdza rozmiar zlecenia sell vs tradeable, aktualizuje gdy niezgodne
  B03 - check_executed: anuluje TP gdy DCA wchodzi → manage_tp postawi nowy z dobrym size
  B04 - Lepsze wykrywanie TP vs SL w check_executed (porównanie z ceną SL, nie entry)
  B05 - manage_dca: crash check PRZED kasowaniem grid (wcześniej kasował podczas crasha)
  B06 - Margin alert: cooldown 30 min (było: spam co 20 sekund)
  B07 - pos_sw detection: isinstance poza generatorem (optymalizacja + poprawność)
  B08 - place_tp: usunięty martwy kod (warunek nigdy nie był True)
  B09 - sign(): guard gdy GATE_SECRET=None → czytelny błąd zamiast cryptic crash
  B10 - reset_grid_if_stale + AUTO GRID RESET były duplikatem (scalono w jedno)
  B11 - manage_dca: total_exp liczył int() zamiast int(float()) → potencjalny crash
  B12 - sl_placed[symbol]=False tylko gdy brak jakichkolwiek price orders (było w else)
  B13 - Equity Guard: nie odpala wielokrotnie gdy bot ręcznie restartowany /start
  B14 - sweep cooldown: używał sweep_last_notify[sym] zamiast dedykowanej zmiennej

NOWE SYSTEMY (brakowało):
  S01 - check_initial_entry(): wejście L0 podczas London Sweep gdy brak pozycji
        → bot TERAZ aktywnie wchodzi, nie tylko czeka na DCA grid
        → cooldown: raz na sesję (8h okna), tylko gdy sweep potwierdzony
  S02 - /pnl komenda: P&L od startu bota (equity start vs teraz + historia trades)
  S03 - /grid komenda: pokazuje aktywne DCA levele na giełdzie dla każdego symbolu
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

trailing_ref       = {}
last_size          = {}
sl_placed          = {}
sl_last_label      = {}   # {symbol: str}  – ostatni typ SL (Breakeven/Grid SL/etc.)
sl_last_notify     = {}   # {symbol: float} – timestamp ostatniego powiadomienia SL
scalp_sl_id        = {}   # {symbol: int}   – ID price order SL scalpa na giełdzie
btc_price_history  = []
session_zones      = {}
sweep_active       = {}
sweep_prev_price   = {}
sweep_last_notify  = {}
grid_bottom_cache      = {}   # SL anchor po wejściu L5
last_margin_alert      = {}   # cooldown alertów marginu {symbol: timestamp}
last_entry_session     = {}   # cooldown initial entry {symbol: session_key}
# ── v2.7.1 / v2.8.2: PER-SESSION LOW TRACKING ───────────────────────────────
# session_low bazuje na ZAMKNIĘTYCH świecach 5m (nie tick realtime).
# Odświeżany co 15 min → low jest historyczny → sweep może realnie przebić poziom.
active_session_low     = {}   # {symbol: float} – minimum sesji z zamkniętych świec 5m
active_session_tracker = {}   # {symbol: str}   – która sesja jest śledzona
session_low_refresh    = {}   # {symbol: float} – timestamp ostatniego odświeżenia low
# ── SCALP EXIT TRACKING ───────────────────────────────────────────────────────
scalp_active       = {}   # {symbol: bool} – True gdy pozycja otwarta przez scalp
scalp_entry_price  = {}   # {symbol: float} – cena wejścia scalpa (do TP/SL)
scalp_entry_time   = {}   # {symbol: float} – timestamp wejścia (do timeoutu 25 min)
# ─────────────────────────────────────────────────────────────────────────────
equity_guard_fired = False
session_pnl_start  = 0
trade_log          = []   # [(symbol, pnl, time)]
# ── FIX RACE CONDITION: flagi blokujące manage_dca podczas resetu ────────────
grid_resetting     = {}   # {symbol: bool} – True gdy do_reset_grid jest w toku
grid_reset_time    = {}   # {symbol: timestamp} – czas ostatniego resetu (cooldown 30s)
grid_slide_time    = {}   # {symbol: timestamp} – czas ostatniego slide (cooldown 60s)
# ─────────────────────────────────────────────────────────────────────────────

# ── v2.7.0: MULTI-SESSION CONFIG ─────────────────────────────────────────────
# Wszystkie godziny w CZASIE LOKALNYM PI (CEST).
# sweep_pct  – o ile % cena musi przebić session_low żeby to był sweep
# size_mult  – mnożnik wielkości pozycji przy scalp entry
# scalp      – czy wchodzić w scalp gdy sweep wykryty
SESSIONS = {
    "ASIA_SWEEP":     {"h": (1.0,  4.0),  "icon": "🌏", "sweep_pct": 0.0010, "size_mult": 1.5, "scalp": True},
    "LONDON_SWEEP":   {"h": (8.0,  12.0), "icon": "🇬🇧", "sweep_pct": 0.0015, "size_mult": 2.5, "scalp": True},
    "LONDON_LUNCH":   {"h": (12.0, 14.0), "icon": "🍽️",  "sweep_pct": 0.004, "size_mult": 1.0, "scalp": False},
    "NY_OPEN":        {"h": (14.5, 17.0), "icon": "🗽", "sweep_pct": 0.0015, "size_mult": 2.0, "scalp": True},
    "NY_REVERSAL":    {"h": (18.0, 21.0), "icon": "🔄", "sweep_pct": 0.001, "size_mult": 1.5, "scalp": True},
    "MIDNIGHT_RESET": {"h": (0.0,  1.0),  "icon": "🌙", "sweep_pct": 0.001, "size_mult": 1.0, "scalp": True},
}
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    "BTC_USDT": {
        "icon": "🟠", "active": True,
        "min_moonbag": 2, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 18,           # SOL wyłączony → więcej marginu dla BTC
        "risk_per_level": 0.015,       # 1.5% equity per level (było 1%, SOL nieaktywny)
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.03,
        "sl_pct": 0.08,                # było 0.20 → 8% fallback (likwidacja przy 7x była za blisko)
        "price_decimals": 0,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.0001,
        "grid_reset_pct": 0.05,
    },
    "ETH_USDT": {
        "icon": "🔵", "active": True,
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.02,
        "max_contracts": 14,           # SOL wyłączony → więcej marginu dla ETH
        "risk_per_level": 0.015,       # 1.5% equity per level (było 1%, SOL nieaktywny)
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.03,
        "sl_pct": 0.08,                # było 0.13 → 8% fallback
        "price_decimals": 2,
        "min_free_margin": 100, "min_equity": 150, "contract_multiplier": 0.01,
        "grid_reset_pct": 0.05,
    },
    "SOL_USDT": {
        "icon": "🟣", "active": False,  # wyłączony – BTC+ETH wystarczy, SOL za bardzo koreluje
        "min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,
        "max_contracts": 5,            # było 10 → zmniejszone (SOL najbardziej volatile)
        "risk_per_level": 0.01,        # było 0.02 → 1% equity per level
        "tp_pct": 0.05, "tp_pct_from_now": 0.04, "trailing_trigger": 0.02,
        "sl_pct": 0.10,                # było 0.18 → 10% fallback
        "price_decimals": 2,
        "min_free_margin": 200, "min_equity": 250, "contract_multiplier": 0.1,
        "grid_reset_pct": 0.05,
    }
}

# ── B01: bezpieczna konwersja size z API ───────────────────────────────────────
def isize(v):
    """int(float(v)) – obsługuje '5', '5.0', 5, 5.0 z API Gate.io"""
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0
# ─────────────────────────────────────────────────────────────────────────────

def sign(method, path, query="", body=""):
    # B09: guard gdy zmienne środowiskowe nie są ustawione
    if not GATE_SECRET:
        raise EnvironmentError("BRAK GATE_SECRET w .env_freedom – bot nie może działać!")
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
        r = requests.request(method, url, headers=sign(method, path, query, b_str),
                             data=b_str, timeout=15)
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
    cfg = CONFIG[symbol]
    target_val = equity * cfg["risk_per_level"]
    mult = cfg["contract_multiplier"]
    return max(1, int(target_val / (curr_price * mult)))


# ── DYNAMICZNY SL ─────────────────────────────────────────────────────────────
def calculate_sl(symbol, cfg, entry, curr_price, buys):
    """
    Priorytety SL:
    1. Breakeven >= +2%: SL tuż nad entry
    2. Grid SL live: 2% pod najniższym aktywnym DCA buy limitem (zapisuje cache)
    3. Grid Anchor: gdy brak DCA (wszystkie weszły) → używa ostatnio zapamiętanego dna
    4. Fallback absolutny: grid_depth + 3% od entry (tylko start bota bez historii)
    """
    if entry <= 0:
        return 0, "Brak entry"
    profit_pct = (curr_price - entry) / entry

    if profit_pct >= 0.02:
        return entry * 1.001, "Breakeven 🔒"

    if buys:
        buy_prices = [float(o.get("price", 0)) for o in buys
                      if float(o.get("price", 0)) > 0]
        if buy_prices:
            lowest_buy = min(buy_prices)
            grid_bottom_cache[symbol] = lowest_buy
            target_sl = lowest_buy * 0.98
            dist_pct = (1 - target_sl / entry) * 100
            return target_sl, f"Grid SL ({len(buy_prices)} DCA, -{dist_pct:.1f}%)"

    if symbol in grid_bottom_cache:
        anchor = grid_bottom_cache[symbol]
        target_sl = anchor * 0.98
        dist_pct = (1 - target_sl / entry) * 100
        return target_sl, f"Grid Anchor (-{dist_pct:.1f}%)"

    grid_depth = cfg["grid_step"] * cfg["dca_levels"]
    target_sl = entry * (1 - grid_depth - 0.03)
    dist_pct = (1 - target_sl / entry) * 100
    return target_sl, f"Fallback SL (-{dist_pct:.1f}%)"
# ─────────────────────────────────────────────────────────────────────────────


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

def _fetch_session_low(symbol, sess_name, fallback):
    """
    Pobiera historyczne minimum od startu bieżącej sesji (świece 5m).
    Używane gdy bot startuje w środku sesji lub sesja się zmienia.
    """
    sess = SESSIONS.get(sess_name, {})
    if not sess:
        return fallback
    now = datetime.now()
    t   = now.hour + now.minute / 60.0
    lo, _ = sess["h"]
    elapsed_h = max(0.083, t - lo)           # min 5 min
    n_candles = min(int(elapsed_h * 12) + 1, 72)  # 5m candles, max 6h
    hist = gate_request("GET", "/api/v4/futures/usdt/candlesticks",
                        {"contract": symbol, "limit": str(n_candles), "interval": "5m"})
    if not isinstance(hist, list) or not hist:
        return fallback
    try:
        lows = []
        for c in hist:
            if isinstance(c, list):
                lows.append(float(c[3]))
            elif isinstance(c, dict):
                lows.append(float(c.get("l", fallback)))
        return min(lows) if lows else fallback
    except Exception:
        return fallback


def get_session_low(symbol, curr_price):
    """
    v2.8.2: Session low bazuje wyłącznie na ZAMKNIĘTYCH świecach 5m (nie tick realtime).
    Dzięki temu trigger sweep jest STAŁY — cena może go realnie przebić.
    Poprzednia wersja (real-time update) godziła low za ceną → trigger nigdy nie odpałał
    przy płynnych spadkach, bo low == curr_price → curr_price < low*0.997 niemożliwe.

    Odświeżanie:
      • przy zmianie sesji (reset)
      • co 15 minut (re-fetch 5m candles) — by uwzględnić nowe potwierdzone minima
    """
    is_active, sess_name, _ = get_session_info()
    if not is_active:
        # Poza sesją — fallback do globalnej strefy (session_zones)
        return session_zones.get(symbol, {}).get("low", curr_price)

    now_ts = time.time()
    sess_changed = active_session_tracker.get(symbol) != sess_name
    refresh_due  = (now_ts - session_low_refresh.get(symbol, 0)) > 900  # 15 minut

    if sess_changed or refresh_due:
        fetched = _fetch_session_low(symbol, sess_name, curr_price)
        if fetched > 0:
            active_session_low[symbol] = fetched
        active_session_tracker[symbol] = sess_name
        session_low_refresh[symbol]    = now_ts
        reason = "nowa sesja" if sess_changed else "odświeżenie 15min"
        print(f"  [SESSION LOW] {symbol} {sess_name} ({reason}): {fetched:.2f}")

    # BRAK real-time update curr_price → low jest historyczny, trigger jest stały
    return active_session_low.get(symbol, curr_price)


def get_session_info():
    """
    Zwraca (is_active, sess_name, sess_cfg) na podstawie czasu lokalnego Pi.
    Wszystkie godziny w CEST (czas lokalny).
    """
    t = datetime.now().hour + datetime.now().minute / 60.0
    for name, s in SESSIONS.items():
        lo, hi = s["h"]
        if lo <= t < hi:
            return True, name, s
    return False, "POZA_SESJA", {}

def is_london_session():
    """Kompatybilność — True gdy jakakolwiek sesja aktywna."""
    return get_session_info()[0]

def detect_sweep(symbol, curr_price):
    """
    Zwraca (is_sweep, reason, sess_name).
    Threshold sweep_pct per sesja — ASIA/MIDNIGHT niższy, LONDON/NY wyższy.
    """
    is_active, sess_name, sess_cfg = get_session_info()
    if not is_active:
        sweep_active[symbol] = False
        sweep_prev_price[symbol] = curr_price
        return False, "poza sesja", "POZA_SESJA"
    low       = get_session_low(symbol, curr_price)
    threshold = sess_cfg.get("sweep_pct", 0.003)
    prev      = sweep_prev_price.get(symbol, curr_price)
    sweep_prev_price[symbol] = curr_price
    if prev >= low and curr_price < low * (1 - threshold):
        sweep_active[symbol] = True
        pct = (low - curr_price) / low * 100
        return True, f"SWEEP LOW {low:.2f} (-{pct:.1f}%)", sess_name
    if sweep_active.get(symbol) and curr_price < low:
        pct = (low - curr_price) / low * 100
        return True, f"SWEEP CONT {low:.2f} (-{pct:.1f}%)", sess_name
    if sweep_active.get(symbol) and curr_price > low * 1.005:
        sweep_active[symbol] = False
    return False, "brak sweep", sess_name


# ── S01: NOWY SYSTEM – Initial Entry przy sesyjnym Sweep ─────────────────────
def check_initial_entry(symbol, cfg, size, curr_price, equity, free_margin, buys,
                        all_positions=None):
    """
    v2.7.0: Wchodzi w scalp podczas dowolnej aktywnej sesji (ASIA/LONDON/NY/etc.)
    Każda sesja ma własny threshold, size_mult i cooldown.
    Cooldown: raz na sesję (klucz = symbol + data + nazwa sesji).
    """
    if size > 0:                        # mamy już pozycję na tym symbolu
        return
    if buys:                            # siatka DCA jest już postawiona
        return
    if free_margin < cfg["min_free_margin"]:
        return

    # ── MAX POZYCJE: max 2 otwarte jednocześnie (BTC + ETH) ──────────────────
    if isinstance(all_positions, list):
        open_count = sum(1 for p in all_positions
                         if isinstance(p, dict) and float(p.get("size", 0)) != 0)
        if open_count >= 2:
            print(f"    [SKIP SCALP] {symbol}: limit 2 pozycji osiągnięty ({open_count})")
            return

    is_active, sess_name, sess_cfg = get_session_info()
    if not is_active:
        return
    if not sess_cfg.get("scalp", True):   # LONDON_LUNCH i inne bez scalpa
        return

    is_sweep, _, _ = detect_sweep(symbol, curr_price)
    if not is_sweep:
        return

    # Cooldown: raz na sesję per symbol per dzień
    now         = datetime.now()
    session_key = f"{symbol}_{now.date()}_{sess_name}"
    if last_entry_session.get(symbol) == session_key:
        return

    size_mult = sess_cfg.get("size_mult", 1.0)
    qty = fmt_size(get_dynamic_size(symbol, equity, curr_price) * size_mult)
    # B16: MARKET BUY zamiast limit – sweep trwa krótko, limit często nie zdążył wejść.
    # Gate.io: price="0" + tif="ioc" = natychmiastowy market order.
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": qty,
        "price": "0", "tif": "ioc",
    })
    if res.get("id"):
        fill_price = float(res.get("fill_price", curr_price) or curr_price)
        last_entry_session[symbol] = session_key
        # ── SCALP TRACKING: zapamiętaj wejście dla manage_scalp_exit ──────────
        scalp_active[symbol]      = True
        scalp_entry_price[symbol] = fill_price
        scalp_entry_time[symbol]  = time.time()
        # ─────────────────────────────────────────────────────────────────────
        tp_target  = fill_price * 1.015
        sl_target  = fill_price * 0.990
        print(f"    ENTRY {symbol} MARKET x{qty}k @ ~{fill_price:.2f} | TP {tp_target:.2f} SL {sl_target:.2f}")

        # ── Postaw TP limit na giełdzie od razu (działa nawet gdy Pi offline) ──
        tp_res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": -int(qty),
            "price": fmt_price(tp_target, symbol),
            "tif": "gtc", "reduce_only": True,
        })
        tp_ok = "✅" if tp_res.get("id") else "❌"

        # ── Postaw SL price order na giełdzie od razu (bezpieczeństwo offline) ─
        sl_res = gate_request("POST", "/api/v4/futures/usdt/price_orders", body={
            "initial": {
                "contract": symbol, "size": -int(qty),
                "price": "0", "tif": "ioc", "reduce_only": True,
            },
            "trigger": {
                "strategy_type": 0, "price_type": 0,
                "price": fmt_price(sl_target, symbol),
                "rule": 2, "expiration": 86400,   # wygasa po 24h
            }
        })
        if sl_res.get("id"):
            scalp_sl_id[symbol] = sl_res["id"]
            sl_ok = "✅"
        else:
            sl_ok = "❌"

        sess_icon = sess_cfg.get("icon", "🎯")
        tg(
            f"🎯 <b>SCALP ENTRY</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💥 Market buy ~{fill_price:.2f}\n"
            f"📦 Qty:     {qty}k  ({size_mult:.1f}x)\n"
            f"🎯 TP:      {fmt_price(tp_target, symbol)}  (+1.5%)  {tp_ok}\n"
            f"⛔ SL:      {fmt_price(sl_target, symbol)}  (-1.0%)  {sl_ok}\n"
            f"⌛ Timeout: 25 min → market close\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{sess_icon} {sess_name}"
        )
# ─────────────────────────────────────────────────────────────────────────────


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
                    msg = update.get("message", {}).get("text", "")
                    chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                    if chat_id != CHAT_ID:
                        continue

                    if msg == "/stop":
                        BOT_ACTIVE = False
                        tg("🛑 <b>Bot zatrzymany</b>")

                    elif msg == "/start":
                        BOT_ACTIVE = True
                        equity_guard_fired = False   # B13: reset flagi equity guard
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
                        fr  = float(acc.get("available", 0)) if isinstance(acc, dict) else 0
                        pnl = float(acc.get("unrealised_pnl", 0)) if isinstance(acc, dict) else 0
                        crash = is_market_crashing()
                        ords = ""
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            o = get_orders(sym)
                            if o:
                                b = len([x for x in o if isize(x.get("size", 0)) > 0])  # B01
                                s = len([x for x in o if isize(x.get("size", 0)) < 0])  # B01
                                ords += f"\n{cfg['icon']} {sym}: {b}x buy / {s}x sell"
                        margin_icon = "🟢" if fr > 150 else ("🟡" if fr > 80 else "🔴")
                        pnl_icon = "📈" if pnl >= 0 else "📉"
                        session_gain = tot - session_pnl_start if session_pnl_start > 0 else 0
                        _si, _sn, _sc = get_session_info()
                        sess_icon = _sc.get("icon", "⚫") if _si else "⚫"
                        scalp_lbl = f"scalp {_sc.get('size_mult',1):.1f}x" if (_si and _sc.get("scalp")) else ("bez scalpa" if _si else "—")
                        tg(
                            f"╔══ 📊 <b>STATUS</b> ══╗\n"
                            f"🤖 Bot: {'ON ✅' if BOT_ACTIVE else 'OFF 🛑'}  "
                            f"DCA: {'ON ✅' if DCA_ENABLED else 'OFF ⏸'}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"💰 Equity:  <b>{tot:.2f} USDT</b>\n"
                            f"{margin_icon} Margin:  <b>{fr:.2f} USDT</b>  {bar(fr/tot if tot > 0 else 0)}\n"
                            f"{pnl_icon} PnL:     <b>{pnl:+.2f} USDT</b>\n"
                            f"📊 Sesja:  <b>{session_gain:+.2f} USDT</b>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"{sess_icon} <b>{_sn}</b>  {scalp_lbl}\n"
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
                                    sym   = p["contract"]
                                    entry = float(p["entry_price"])
                                    ppnl  = float(p.get("unrealised_pnl", 0))
                                    price = get_price(sym)
                                    pct   = (price - entry) / entry * 100 if entry > 0 else 0
                                    cfg   = CONFIG.get(sym, {})
                                    pnl_icon = "📈" if ppnl >= 0 else "📉"
                                    lines.append(
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{cfg.get('icon','•')} <b>{sym}</b>\n"
                                        f"  Pozycja: {sz:.0f}k  Moonbag: {cfg.get('min_moonbag',0)}k\n"
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
                                    buys   = [o for o in orders if isize(o.get("size", 0)) > 0]  # B01
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
                            sells = [o for o in get_orders(sym) if isize(o.get("size", 0)) < 0]  # B01
                            tp_p  = float(sells[0]["price"]) if sells else 0
                            if ref > 0 and price > 0:
                                rise     = (price - ref) / ref * 100
                                trigger  = cfg["trailing_trigger"] * 100
                                brakuje  = max(0, trigger - rise)
                                progress = min(rise / trigger, 1.0) if trigger > 0 else 0
                                tp_str   = fmt_price(tp_p, sym) if tp_p else "Brak"
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
                        _si, _sn, _sc = get_session_info()
                        now_t = datetime.now().hour + datetime.now().minute / 60.0
                        # Znajdź następną sesję (jeśli nie znaleziono dziś, bierz pierwszą na jutro)
                        next_sess = "—"
                        next_time = "—"
                        for sn, sc in SESSIONS.items():
                            lo, hi = sc["h"]
                            if lo > now_t:
                                next_sess = f"{sc['icon']} {sn}"
                                next_time = f"{int(lo):02d}:{int((lo%1)*60):02d}"
                                break
                        if next_sess == "—":
                            # Po ostatniej sesji dnia – pierwsza sesja jutra (najwcześniejszy lo)
                            first_sn, first_sc = min(SESSIONS.items(), key=lambda x: x[1]["h"][0])
                            lo0 = first_sc["h"][0]
                            next_sess = f"{first_sc['icon']} {first_sn}"
                            next_time = f"jutro {int(lo0):02d}:{int((lo0%1)*60):02d}"
                        s_icon  = _sc.get("icon", "⚫") if _si else "⚫"
                        scalp_s = "✅" if _sc.get("scalp", False) else "❌"
                        mult_s  = f"{_sc.get('size_mult', 0):.1f}x" if _si else "—"
                        lines   = [
                            "╔══ 🎯 <b>SWEEP STATUS</b> ══╗",
                            f"{s_icon} <b>{_sn}</b>  scalp {scalp_s}  size {mult_s}",
                            f"Następna: {next_sess} o {next_time}",
                        ]
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            price    = get_price(sym)
                            sess_low = get_session_low(sym, price)
                            is_sw, reason, _ = detect_sweep(sym, price)
                            dist_to_low = (price - sess_low) / price * 100 if price > 0 else 0
                            threshold   = _sc.get("sweep_pct", 0.003) * 100 if _si else 0
                            sw_trigger  = sess_low * (1 - _sc.get("sweep_pct", 0.003)) if _si else 0
                            status = "🎯 SWEEP AKTYWNY!" if is_sw else (
                                f"⬜ Brak  (trigger @ {sw_trigger:.2f})" if sw_trigger else "⬜ Brak"
                            )
                            lines.append(
                                f"━━━━━━━━━━━━━━━\n"
                                f"{cfg['icon']} <b>{sym}</b>  {price:.2f}\n"
                                f"  Session low:  <b>{sess_low:.2f}</b>  ({dist_to_low:.1f}% nad)\n"
                                f"  Próg sweep:   -{threshold:.1f}%  → {sw_trigger:.2f}\n"
                                f"  {status}"
                            )
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))

                    # ── S03: NOWA KOMENDA /grid ───────────────────────────────────
                    elif msg == "/grid":
                        lines = ["╔══ 📐 <b>SIATKA DCA</b> ══╗"]
                        for sym, cfg in CONFIG.items():
                            if not cfg["active"]:
                                continue
                            price  = get_price(sym)
                            orders = get_orders(sym)
                            buys   = sorted(
                                [o for o in orders if isize(o.get("size", 0)) > 0],  # B01
                                key=lambda o: float(o.get("price", 0)), reverse=True
                            )
                            expected = cfg["dca_levels"]
                            # B15: ostrzeżenie gdy więcej zleceń niż oczekiwana liczba poziomów
                            warn = f" ⚠️ {len(buys)} zleceń!" if len(buys) > expected else ""
                            lines.append(f"━━━━━━━━━━━━━━━\n{cfg['icon']} <b>{sym}</b>  [{price:.2f}]{warn}")
                            if buys:
                                for i, o in enumerate(buys, 1):
                                    bp  = float(o.get("price", 0))
                                    bsz = isize(o.get("size", 0))  # B01
                                    dist = (price - bp) / price * 100
                                    lines.append(f"  L{i}: {bp:.2f} x{bsz}k ({dist:.1f}% niżej)")
                            else:
                                lines.append("  Brak aktywnych DCA buy limitów")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M')} ══╝")
                        tg("\n".join(lines))
                    # ─────────────────────────────────────────────────────────────

                    # ── S02: NOWA KOMENDA /pnl ────────────────────────────────────
                    elif msg == "/pnl":
                        acc  = get_account()
                        curr_eq = float(acc.get("total", 0)) if isinstance(acc, dict) else 0
                        gain = curr_eq - session_pnl_start if session_pnl_start > 0 else 0
                        gain_pct = gain / session_pnl_start * 100 if session_pnl_start > 0 else 0
                        lines = [
                            "╔══ 💹 <b>P&L SESJI</b> ══╗",
                            f"  Start:  {session_pnl_start:.2f} USDT",
                            f"  Teraz:  {curr_eq:.2f} USDT",
                            f"  Wynik:  <b>{gain:+.2f} USDT ({gain_pct:+.2f}%)</b>",
                            "━━━━━━━━━━━━━━━",
                        ]
                        if trade_log:
                            lines.append("📋 Ostatnie transakcje:")
                            for entry in trade_log[-5:]:   # ostatnie 5
                                sym_t, pnl_t, t_t = entry
                                icon = CONFIG.get(sym_t, {}).get("icon", "•")
                                lines.append(f"  {icon} {sym_t}: <b>{pnl_t:+.2f} USDT</b>  {t_t}")
                        else:
                            lines.append("  Brak zamkniętych transakcji")
                        lines.append(f"╚══ {datetime.now().strftime('%H:%M %d.%m')} ══╝")
                        tg("\n".join(lines))
                    # ─────────────────────────────────────────────────────────────

                    elif msg.startswith("/reset_dca"):
                        parts   = msg.split()
                        sym_arg = parts[1].upper() if len(parts) > 1 else ""
                        if not sym_arg:
                            tg("Uzycie: /reset_dca BTC, ETH, SOL lub ALL")
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
                                        do_reset_grid(sym, price2, eq2, "reczny /reset_dca")

                    elif msg == "/help":
                        tg(
                            "╔══ 📖 <b>KOMENDY</b> ══╗\n"
                            "━━━━━━━━━━━━━━━\n"
                            "📊 /status      equity, margin, PnL\n"
                            "📦 /pozycje     otwarte pozycje\n"
                            "🛡 /sl          stop lossy\n"
                            "📈 /trailing    trailing TP status\n"
                            "🎯 /sweep       Multi-sesja Sweep status\n"
                            "📐 /grid        aktywna siatka DCA\n"
                            "💹 /pnl         P&amp;L od startu bota\n"
                            "━━━━━━━━━━━━━━━\n"
                            "▶️ /start       uruchom bota\n"
                            "🛑 /stop        zatrzymaj bota\n"
                            "✅ /dca_on      włącz DCA\n"
                            "⏸ /dca_off     wyłącz DCA\n"
                            "🔄 /reset_dca   BTC / ETH / ALL\n"
                            "╚══════════════╝"
                        )
        except Exception as e:
            print(f"  TG ERR {e}")
        time.sleep(2)


def do_reset_grid(symbol, curr_price, equity, reason="manual"):
    """
    RACE CONDITION FIX: ustawia grid_resetting[symbol]=True na czas całej operacji.
    manage_dca widzi flagę i pomija cykl – nie może nakładać własnych zleceń
    podczas gdy reset jest w toku (eliminuje bug 7 DCA i podwójny reset).

    B15 FIX: po pierwszej pętli kasowania weryfikuje czy giełda rzeczywiście nie ma
    już żadnych buy limitów. Jeśli zostały (DELETE się nie powiodło / rate limit),
    próbuje jeszcze raz (max 3 rundy). Dopiero po potwierdzeniu czystego stanu stawia
    nową siatkę → eliminuje „podwójną siatkę" (1981/1979, 1941/1938 obok siebie).
    """
    grid_resetting[symbol] = True
    grid_reset_time[symbol] = time.time()
    try:
        cfg = CONFIG[symbol]

        # ── Krok 1: kasuj istniejące buy limity, max 3 próby ──────────────────
        cancelled_total = 0
        for attempt in range(3):
            orders = get_orders(symbol)
            buys   = [o for o in orders if isize(o.get("size", 0)) > 0]
            if not buys:
                break                         # siatka czysta – można stawiać nową
            for o in buys:
                gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
                time.sleep(0.2)
            cancelled_total += len(buys)
            if attempt < 2:
                time.sleep(0.5)               # chwila zanim API potwierdzi usunięcie

        # ── Krok 2: finalna weryfikacja ────────────────────────────────────────
        remaining = [o for o in get_orders(symbol) if isize(o.get("size", 0)) > 0]
        if remaining:
            # Nie udało się wyczyścić – przerywamy, żeby nie duplikować siatki
            tg(f"⚠️ {symbol}: nie udało się usunąć {len(remaining)} zleceń przed resetem – anulowano")
            print(f"  GRID RESET ABORTED {symbol}: {len(remaining)} orders still open")
            return

        # ── Krok 3: postaw nową siatkę ─────────────────────────────────────────
        added  = 0
        levels = []
        for i in range(1, cfg["dca_levels"] + 1):
            target = curr_price * (1 - cfg["grid_step"] * i)
            qty    = fmt_size(get_dynamic_size(symbol, equity, curr_price))
            res    = gate_request("POST", "/api/v4/futures/usdt/orders", body={
                "contract": symbol, "size": qty,
                "price": fmt_price(target, symbol), "tif": "gtc",
            })
            if res.get("id"):
                added += 1
                levels.append(f"  L{i}: {fmt_price(target, symbol)} x{qty}k")
            time.sleep(0.5)
        tg(
            f"🔄 <b>RESET SIATKI</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 Ref:      {curr_price:.2f}\n"
            f"🗑 Usunięto: {cancelled_total}  ➕ Dodano: {added}\n"
            f"📋 Powód:   {reason}\n"
            f"━━━━━━━━━━━━━━━\n"
            + "\n".join(levels)
        )
        print(f"  GRID RESET {symbol} @ {curr_price:.2f} ({reason})")
    finally:
        grid_resetting[symbol] = False   # zawsze odblokuj, nawet przy błędzie


def manage_scalp_exit(symbol, cfg, size, curr_price, sells):
    """
    Dedykowane wyjście dla pozycji otwartej przez London Sweep scalp.
    Parametry: TP +1.5%, SL -1% od ceny wejścia, timeout 25 min → market close.
    Zwraca True jeśli obsłużono (manage_logic pomija wtedy normalny SL/TP).
    Zwraca False gdy scalp nieaktywny → normalny manage_sl/manage_tp.
    """
    if not scalp_active.get(symbol):
        return False

    ep      = scalp_entry_price.get(symbol, curr_price)
    elapsed = time.time() - scalp_entry_time.get(symbol, time.time())

    tp_price = ep * 1.015   # +1.5%
    sl_price = ep * 0.990   # -1.0%

    def _scalp_cleanup(symbol, sells):
        """Anuluj TP limit + SL price order scalpa, wyczyść stan."""
        for o in sells:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        sl_id = scalp_sl_id.pop(symbol, None)
        if sl_id:
            gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{sl_id}")
        scalp_active.pop(symbol, None)
        scalp_entry_price.pop(symbol, None)
        scalp_entry_time.pop(symbol, None)

    # ── TIMEOUT: 25 minut bez wypełnienia → zamknij market ────────────────────
    if elapsed > 1500:
        tg(
            f"⏱ <b>SCALP TIMEOUT</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⌛ 25 min bez TP/SL\n"
            f"🔄 Zamykam market @ ~{curr_price:.2f}"
        )
        _scalp_cleanup(symbol, sells)
        gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": -int(size),
            "price": "0", "tif": "ioc", "reduce_only": True,
        })
        return True

    # ── SL: backup — giełda powinna zareagować pierwsza, ale bot też sprawdza ──
    if curr_price <= sl_price:
        tg(
            f"🔴 <b>SCALP SL HIT</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📉 Cena:   {curr_price:.2f}\n"
            f"⛔ SL był: {fmt_price(sl_price, symbol)}  (-1%)\n"
            f"🔄 Zamykam market"
        )
        _scalp_cleanup(symbol, sells)
        gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": -int(size),
            "price": "0", "tif": "ioc", "reduce_only": True,
        })
        return True

    # ── TP i SL już stoją na giełdzie od momentu wejścia — tylko loguj ────────
    remaining_min = max(0, int((1500 - elapsed) / 60))
    if sells:
        tp_on_ex = float(sells[0].get("price", 0))
        print(f"    SCALP {symbol} TP @ {tp_on_ex:.2f} | SL @ {sl_price:.2f} | timeout za {remaining_min} min")
    else:
        print(f"    SCALP {symbol} | SL @ {sl_price:.2f} | timeout za {remaining_min} min")

    return True   # obsłużono — nie uruchamiaj normalnego SL/TP


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
        current_sl_price = float(sl_orders[0].get("trigger", {}).get("price", 0))
        if abs(current_sl_price - target_sl) / target_sl < 0.01:
            sl_placed[symbol] = True
            return
        for o in sl_orders:
            gate_request("DELETE", f"/api/v4/futures/usdt/price_orders/{o['id']}")
            time.sleep(0.2)
    else:
        sl_placed[symbol] = False   # B12: tylko gdy naprawdę nie ma żadnego SL

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
        # Powiadomienie tylko gdy zmienił się TYP SL lub minęło 10 minut
        typ_changed  = sl_last_label.get(symbol) != label
        cooldown_ok  = (time.time() - sl_last_notify.get(symbol, 0)) > 600
        sl_last_label[symbol]  = label
        if not (typ_changed or cooldown_ok):
            print(f"    SL {symbol} @ {fmt_price(target_sl, symbol)} ({label}) – bez TG (cooldown)")
            return
        sl_last_notify[symbol] = time.time()
        tg(
            f"🛡 <b>SL USTAWIONY</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 Typ:      {label}\n"
            f"⛔ SL @      <b>{fmt_price(target_sl, symbol)}</b>\n"
            f"📏 Dystans:  {dist:.1f}%  {bar(dist/15)}"
        )
        print(f"    SL {symbol} @ {target_sl:.2f} ({label})")
    else:
        print(f"    SL FAIL {symbol}: {res.get('label','?')}")


def check_executed(symbol, cfg, size, entry, price, sells):
    """
    B03: sells przekazany z manage_logic – gdy DCA wchodzi, anuluj stary TP
         żeby manage_tp w tym samym cyklu postawił nowy z poprawnym size.
    B04: lepsze rozróżnienie TP vs SL – porównujemy cenę z poziomem SL.
    """
    global trade_log
    prev = last_size.get(symbol, -1)
    if prev < 0:
        last_size[symbol] = size
        return

    if size > prev:
        added = size - prev
        mult  = cfg["contract_multiplier"]
        val   = added * mult * price
        # B03: anuluj istniejący TP – manage_tp postawi nowy z właściwym size
        for o in sells:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        if sells:
            print(f"    DCA fill {symbol}: anulowano {len(sells)} TP → manage_tp postawi nowy")
        trailing_ref[symbol] = price   # reset trailing od nowej bazy
        tg(
            f"📥 <b>DCA WYPEŁNIONY</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Kupiono:  +{added:.0f}k @ {price:.2f}\n"
            f"💵 Wartość:  ~{val:.2f} USDT\n"
            f"📊 Pozycja:  {prev:.0f}k → <b>{size:.0f}k</b>\n"
            f"📌 Avg Entry: {entry:.2f}\n"
            f"🕐 {datetime.now().strftime('%H:%M')}"
        )

    elif prev > size >= 0:
        closed = prev - size
        if closed > 0:
            mult = cfg["contract_multiplier"]
            pnl  = closed * mult * (price - entry) if entry > 0 else 0
            pct  = (price - entry) / entry * 100 if entry > 0 else 0
            # B04: rozróżnienie TP vs SL przez porównanie z poziomem SL
            sl_price = 0
            existing_sl = get_price_orders(symbol)
            if existing_sl:
                sl_price = float(existing_sl[0].get("trigger", {}).get("price", 0))
            is_tp  = sl_price == 0 or price > sl_price * 1.01
            label  = "TP WYKONANY ✅" if is_tp else "SL WYKONANY 🔴"
            trade_log.append((symbol, pnl, datetime.now().strftime("%H:%M")))  # S02
            if len(trade_log) > 50:
                trade_log.pop(0)
            pnl_bar = bar(min(abs(pct) / 10, 1.0))
            tg(
                f"{'✅' if is_tp else '🔴'} <b>{label}</b>\n"
                f"{cfg['icon']} <b>{symbol}</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 Zamknięto: {closed:.0f}k @ {price:.2f}\n"
                f"📌 Entry:     {entry:.2f}  ({pct:+.1f}%)  {pnl_bar}\n"
                f"{'💚' if pnl >= 0 else '🔻'} PnL:      <b>{pnl:+.2f} USDT</b>\n"
                f"🌙 Moonbag:  {size:.0f}k pozostaje\n"
                f"🕐 {datetime.now().strftime('%H:%M')}"
            )
            if size == 0:
                sl_placed[symbol] = False
                trailing_ref.pop(symbol, None)
                grid_bottom_cache.pop(symbol, None)
                # Wyczyść scalp flags gdy pozycja całkowicie zamknięta
                scalp_active.pop(symbol, None)
                scalp_entry_price.pop(symbol, None)
                scalp_entry_time.pop(symbol, None)
                scalp_sl_id.pop(symbol, None)   # B16: czyść ID price-order SL scalpa

    last_size[symbol] = size


def place_tp(symbol, cfg, tradeable, curr_price, entry):
    # B08: usunięty martwy kod (warunek był zawsze False)
    tp_from_entry = entry * (1 + cfg["tp_pct"]) if entry > 0 else 0
    tp_from_now   = curr_price * (1 + cfg["tp_pct_from_now"])
    target_tp     = max(tp_from_entry, tp_from_now)
    tp_str = fmt_price(target_tp, symbol)
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": -fmt_size(tradeable),
        "price": tp_str, "tif": "gtc", "reduce_only": True,
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

    # B02: sprawdź czy rozmiar istniejącego TP zgadza się z tradeable
    if len(sells) == 1:
        existing_tp_size = abs(isize(sells[0].get("size", 0)))  # B01
        if existing_tp_size != tradeable:
            print(f"    TP size mismatch {symbol}: {existing_tp_size}k → {tradeable}k – aktualizacja")
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{sells[0]['id']}")
            time.sleep(0.2)
            sells = []   # wymuś postawienie nowego TP

    # Usuń duplikaty TP – zostaw tylko najwyższy
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
                f"{cfg['icon']} <b>{symbol}</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📤 Sell:    {tradeable}k kontraktów\n"
                f"🎯 TP @     <b>{fmt_price(tp_price, symbol)}</b>  (+{pct:.1f}%)\n"
                f"🌙 Moonbag: {cfg['min_moonbag']}k 🔒"
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
                    f"📈 <b>TRAILING TP ↑</b>\n"
                    f"{cfg['icon']} <b>{symbol}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🚀 Wzrost:   +{rise*100:.1f}% od {ref:.2f}\n"
                    f"🎯 Nowy TP:  <b>{fmt_price(tp_price, symbol)}</b>  (+{pct:.1f}%)\n"
                    f"🌙 Moonbag:  {cfg['min_moonbag']}k 🔒"
                )
        else:
            sell_p  = float(sells[0].get("price", 0))
            brakuje = (cfg["trailing_trigger"] - rise) * 100
            print(f"    TP {symbol} @ {sell_p:.2f} | trailing za {brakuje:.1f}%")
    else:
        trailing_ref[symbol] = curr_price


def manage_dca(symbol, cfg, size, curr_price, buys, free_margin, equity):
    # RACE CONDITION FIX: pomiń cykl gdy reset jest w toku (wątek Telegram)
    if grid_resetting.get(symbol):
        print(f"    SKIP {symbol}: grid reset w toku")
        return

    if not DCA_ENABLED:
        return

    # Crash check PRZED wszystkim
    if is_market_crashing():
        print(f"    CRASH DCA {symbol} wstrzymane")
        return

    if free_margin < cfg["min_free_margin"] or equity < cfg["min_equity"]:
        return

    # ── Auto-slide / auto-reset gdy cena ucieka w górę ────────────────────────
    # (cooldowny zapobiegają ciągłemu resetowaniu po /reset_dca lub przy szybkich ruchach)
    now_ts_r = time.time()
    time_since_reset = now_ts_r - grid_reset_time.get(symbol, 0)
    time_since_slide = now_ts_r - grid_slide_time.get(symbol, 0)
    if time_since_reset > 30 and buys:
        highest_buy = max(float(o.get("price", 0)) for o in buys)
        if highest_buy > 0:
            distance_up = (curr_price - highest_buy) / curr_price
            if distance_up > cfg["grid_reset_pct"]:
                # Cena uciekła za mocno (>grid_reset_pct) → pełny reset
                print(f"    GRID RESET UP {symbol}: {curr_price:.2f} ({distance_up*100:.1f}%)")
                do_reset_grid(symbol, curr_price, equity, "auto grid reset w górę")
                return
            elif (distance_up > cfg["grid_step"]
                  and size == 0
                  and time_since_slide > 60):
                # Cena wyszła o 1 grid_step ponad siatkę, brak pozycji →
                # delikatne przesunięcie: usuń L_last, dodaj nowy L1 tuż pod ceną
                print(f"    GRID SLIDE {symbol}: {curr_price:.2f} ({distance_up*100:.1f}% > grid_step)")
                do_slide_grid(symbol, curr_price, equity, buys)
                return

    # Usuń nadmiarowe buy limity
    if len(buys) > cfg["dca_levels"]:
        buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)), reverse=True)
        to_remove   = buys_sorted[cfg["dca_levels"]:]
        for o in to_remove:
            gate_request("DELETE", f"/api/v4/futures/usdt/orders/{o['id']}")
            time.sleep(0.2)
        print(f"    CLEANUP {symbol}: usunieto {len(to_remove)} nadmiarowych")
        buys = buys_sorted[:cfg["dca_levels"]]

    total_exp = size + sum(isize(o.get("size", 0)) for o in buys)  # B11
    if total_exp >= cfg["max_contracts"] or len(buys) >= cfg["dca_levels"]:
        return

    is_sweep, sweep_reason, sess_name = detect_sweep(symbol, curr_price)
    _, _, sess_cfg = get_session_info()
    now_ts    = time.time()
    scalp_key = symbol + "_scalp"  # B14: dedykowany klucz dla scalp cooldown
    scalp_ok  = (now_ts - sweep_last_notify.get(scalp_key, 0)) > 900

    if is_sweep and size == 0 and scalp_ok:
        # v2.7.0: size_mult per sesja zamiast hardkodowanego 2.5
        sweep_mult  = sess_cfg.get("size_mult", 2.5)
        sweep_label = f"SCALP {sess_name}"
        sweep_last_notify[scalp_key] = now_ts
    elif is_sweep and size > 0:
        sweep_mult  = 1.5
        sweep_label = f"BOOST {sess_name}"
    else:
        sweep_mult  = 1.0
        sweep_label = ""

    needed = cfg["dca_levels"] - len(buys)
    added  = 0
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
        remaining = cfg["max_contracts"] - total_exp - added
        if remaining <= 0:
            break
        if total_exp + added + qty > cfg["max_contracts"]:
            qty = remaining
        res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
            "contract": symbol, "size": qty,
            "price": fmt_price(target, symbol), "tif": "gtc",
        })
        if res.get("id"):
            lbl = f"L{i}" if i > 1 else f"L1({sweep_label or 'DCA'})"
            print(f"    DCA {symbol} {lbl} @ {fmt_price(target, symbol)} x{qty}k")
            added += 1
        time.sleep(0.5)


def do_slide_grid(symbol, curr_price, equity, buys):
    """
    Przesuwa siatkę DCA w górę o 1 poziom bez pełnego resetu.
    Usuwa najniższy (najdalszy) buy limit i stawia nowy L1 tuż pod bieżącą ceną.
    Uruchamiany gdy cena wychodzi powyżej siatki o co najmniej grid_step.
    Tylko gdy brak otwartej pozycji (gdy jest pozycja, DCA to siatka bezpieczeństwa).
    Cooldown 60 sekund – nie slajduje zbyt gwałtownie przy ostrych ruchach.
    """
    cfg = CONFIG[symbol]
    if not buys:
        return

    # Nowy L1 – jeden grid_step pod bieżącą ceną
    new_target = curr_price * (1 - cfg["grid_step"])

    # Nie slajduj jeśli nowy L1 za blisko (< 1.5%) istniejącego buy
    if any(abs(new_target - float(o.get("price", 0))) / new_target < 0.015 for o in buys):
        print(f"    SLIDE SKIP {symbol}: nowy L1 {new_target:.2f} zbyt blisko istniejącego")
        return

    # Usuń najniższy (najdalszy od ceny) buy limit
    buys_sorted = sorted(buys, key=lambda o: float(o.get("price", 0)))
    lowest      = buys_sorted[0]
    low_price   = float(lowest.get("price", 0))
    low_sz      = isize(lowest.get("size", 0))
    gate_request("DELETE", f"/api/v4/futures/usdt/orders/{lowest['id']}")
    time.sleep(0.3)

    # Postaw nowy L1
    qty = fmt_size(get_dynamic_size(symbol, equity, curr_price))
    res = gate_request("POST", "/api/v4/futures/usdt/orders", body={
        "contract": symbol, "size": qty,
        "price": fmt_price(new_target, symbol), "tif": "gtc",
    })
    grid_slide_time[symbol] = time.time()

    if res.get("id"):
        dist_old = (curr_price - low_price) / curr_price * 100
        dist_new = (curr_price - new_target) / curr_price * 100
        tg(
            f"🔼 <b>SIATKA PRZESUNIĘTA ↑</b>\n"
            f"{cfg['icon']} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🗑 Usunięto: {low_price:.2f} x{low_sz}k  (-{dist_old:.1f}%)\n"
            f"➕ Nowy L1:  <b>{fmt_price(new_target, symbol)}</b> x{qty}k  (-{dist_new:.1f}%)\n"
            f"📌 Cena:     {curr_price:.2f}"
        )
        print(f"  GRID SLIDE {symbol}: -{low_price:.2f} +L1@{new_target:.2f}")
    else:
        print(f"  GRID SLIDE FAIL {symbol}: {res.get('label','?')}")


def manage_logic(symbol, cfg, free_margin, equity, all_positions):
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
    buys   = [o for o in orders if isize(o.get("size", 0)) > 0]   # B01
    sells  = [o for o in orders if isize(o.get("size", 0)) < 0]   # B01

    pct_str = f"{(price-entry)/entry*100:+.1f}%" if entry > 0 else "---"
    print(f"  {cfg['icon']}  {symbol:<10} {price:>9.2f}  poz={size:.0f}k {pct_str}"
          f"  buy={len(buys)} sell={len(sells)}")

    if size > 0:
        check_executed(symbol, cfg, size, entry, price, sells)  # B03: przekazane sells
        # Scalp exit ma priorytet – jeśli zwróci True, pomijamy normalny SL/TP
        if not manage_scalp_exit(symbol, cfg, size, price, sells):
            manage_sl(symbol, cfg, size, entry, price, equity, buys)
            if size > cfg["min_moonbag"]:
                manage_tp(symbol, cfg, size, entry, price, sells)

    # S01: sprawdź czy potrzeba initial entry (gdy brak pozycji i brak grid)
    check_initial_entry(symbol, cfg, size, price, equity, free_margin, buys, all_positions)
    manage_dca(symbol, cfg, size, price, buys, free_margin, equity)


def run():
    global BOT_ACTIVE, session_pnl_start, equity_guard_fired
    threading.Thread(target=listen_telegram, daemon=True).start()
    print("=" * 55)
    print("  FreedomTracker Bot v2.8.2")
    print("  BTC + ETH | DCA Grid | Multi-sesja Sweep Scalp")
    print("  /help /status /pozycje /sl /trailing /sweep /grid /pnl")
    print("=" * 55)
    tg(
        "╔══════════════════════╗\n"
        "🤖 <b>FreedomTracker v2.8.2</b>\n"
        "╚══════════════════════╝\n"
        "━━━━━━━━━━━━━━━\n"
        "🟠 BTC  |  🔵 ETH  aktywne\n"
        "━━━━━━━━━━━━━━━\n"
        "✅ DCA Grid 5 poziomów\n"
        "✅ Dynamic SL + Breakeven\n"
        "✅ Trailing TP (+3% trigger)\n"
        "✅ Multi-sesja: ASIA/LONDON/LUNCH/NY/REVERSAL/MIDNIGHT\n"
        "✅ Scalp exit: TP+1.5% / SL-1% / 25min\n"
        "✅ Crash detection BTC -3%\n"
        "✅ Equity Guard -25%\n"
        "━━━━━━━━━━━━━━━\n"
        "📖 /help — komendy\n"
        f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )

    cycle        = 0
    last_zone_h  = -1
    starting_eq  = 0
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

            # Gdy API zwróci pusty dict (timeout) eq=0 – pomijamy cykl, nie handlujemy
            if eq == 0:
                print(f"  [SKIP] eq=0 – brak odpowiedzi API, czekam 20s")
                time.sleep(20)
                continue

            if starting_eq == 0 and eq > 0:
                starting_eq       = eq
                session_pnl_start = eq   # S02: zapisz start equity dla /pnl
                print(f"  Equity startowe: {starting_eq:.2f} USDT")

            # B13: equity guard odpala tylko raz (nie w kółko po /start)
            # eq > 0: guard nie odpala gdy API zwróci błąd (eq=0 = brak odpowiedzi, nie strata)
            if (starting_eq > 0 and eq > 0 and eq < starting_eq * 0.75
                    and not equity_guard_fired):
                equity_guard_fired = True
                BOT_ACTIVE = False
                spadek = round((1 - eq / starting_eq) * 100, 1)
                tg(
                    f"🚨 <b>EQUITY GUARD!</b>\n"
                    f"Start:  {starting_eq:.2f} USDT\n"
                    f"Teraz:  {eq:.2f} USDT\n"
                    f"Spadek: -{spadek}%\n"
                    f"Bot zatrzymany. /start aby wznowić."
                )
                print(f"  EQUITY GUARD: bot zatrzymany (equity -{spadek}%)")

            # B06: margin alert z cooldownem 30 minut
            now_ts = time.time()
            if 0 < fr < 80:
                last_alert = last_margin_alert.get("warn", 0)
                if now_ts - last_alert > 1800:
                    tg(f"⚠️ <b>Uwaga!</b> Free margin: <b>{fr:.2f} USDT</b>")
                    last_margin_alert["warn"] = now_ts
            if 0 < fr < 50:
                last_alert = last_margin_alert.get("crit", 0)
                if now_ts - last_alert > 900:
                    tg(f"🚨 <b>ALARM!</b> Krytyczny margin: <b>{fr:.2f} USDT</b>")
                    last_margin_alert["crit"] = now_ts

            curr_hour = datetime.now().hour   # v2.7.0: czas lokalny Pi
            if curr_hour != last_zone_h:
                update_session_zones()
                last_zone_h = curr_hour

            # Sweep alert – wszystkie sesje (v2.7.0)
            is_sess, sess_name_now, sess_cfg_now = get_session_info()
            if is_sess:
                for sym, cfg in CONFIG.items():
                    if not cfg["active"]:
                        continue
                    p = get_price(sym)
                    if p <= 0:
                        continue
                    is_sw, reason, s_name = detect_sweep(sym, p)
                    if is_sw:
                        last_notif = sweep_last_notify.get(sym, 0)
                        if (time.time() - last_notif) > 900:
                            sweep_last_notify[sym] = time.time()
                            zone    = session_zones.get(sym, {})
                            all_pos = get_positions()
                            # B07: isinstance sprawdzony raz, poza generatorem
                            has_pos = False
                            if isinstance(all_pos, list):
                                pos_sw  = next((px for px in all_pos
                                                if px["contract"] == sym), None)
                                has_pos = pos_sw is not None and float(pos_sw.get("size", 0)) != 0
                            s_mult  = sess_cfg_now.get("size_mult", 1.0)
                            s_icon  = sess_cfg_now.get("icon", "🎯")
                            scalp_en = sess_cfg_now.get("scalp", True)
                            if scalp_en:
                                akcja = f"🎯 SCALP {s_mult:.1f}x" if not has_pos else "⚡ DCA BOOST 1.5x"
                            else:
                                akcja = "⚡ DCA BOOST" if has_pos else "⬜ Bez scalpa (ta sesja)"
                            tg(
                                f"{s_icon} <b>SWEEP! {s_name}</b>\n"
                                f"{cfg['icon']} <b>{sym}</b>\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"📍 Cena:    <b>{p:.2f}</b>\n"
                                f"📉 Low:     {zone.get('low', 0):.2f}\n"
                                f"⚡ Sygnał:  {reason}\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"🚀 Akcja:   <b>{akcja}</b>"
                            )
                        else:
                            remaining = int((900 - (time.time() - last_notif)) / 60)
                            print(f"    [SWEEP] {sym} {s_name} cooldown {remaining} min")

            crash_str = " [CRASH]" if is_market_crashing() else ""
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cykl {cycle} | "
                  f"Eq: {eq:.2f} | Free: {fr:.2f} | PnL: {pnl:+.2f}{crash_str}")
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
                        b = len([x for x in o if isize(x.get("size", 0)) > 0])   # B01
                        s = len([x for x in o if isize(x.get("size", 0)) < 0])   # B01
                        ords += f"\n{cfg['icon']} {sym}: {b}x buy / {s}x sell"
                gain = eq - session_pnl_start if session_pnl_start > 0 else 0
                tg(
                    f"╔══ 📊 <b>Raport godzinny</b> ══╗\n"
                    f"💰 Equity:  <b>{eq:.2f} USDT</b>\n"
                    f"💵 Wolne:   <b>{fr:.2f} USDT</b>\n"
                    f"📈 PnL:     <b>{pnl:+.2f} USDT</b>\n"
                    f"💹 Sesja:   <b>{gain:+.2f} USDT</b>\n"
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
EOF

sudo journalctl -u freedom_bot.service -f
ping api.gateio.ws -c 5
tailscale status
sudo nano /etc/resolv.conf
sudo tailscale down
sudo tailscale up --accept-dns=false --reset
ping api.gateio.ws -c 5
ping 8.8.8.8 -c 5
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
ip route
ping 192.168.0.1 -c 5
ping 8.8.8.8 -c 5
[200~ping api.gateio.ws -c 5~
ping api.gateio.ws -c 5
curl -I https://api.gateio.ws/api/v4/spot/currencies
sudo nano /etc/dhcpcd.conf
sudo reboot
time curl -s https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT
sudo pkill -9 -f python3
sudo pkill -9 -f freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
ping 8.8.8.8
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl status freedom_bot.service
sudo journalctl -u freedom_bot.service -f
grep -i "error" /home/barte/logs/freedom_bot.log
sudo journalctl -u freedom_bot.service -f
curl ifconfig.me
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
curl ifconfig.me
sudo journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
time curl -I https://api.gateio.ws/api/v4/spot/currencies
sudo journalctl -u freedom_bot.service -f
time curl -I https://api.gateio.ws/api/v4/spot/currencies
time curl -s https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT
sudo nano /etc/resolv.conf
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
nslookup api.gateio.ws
sudo apt  update && sudo apt install dnsutils -y
nslookup api.gateio.ws
sudo nano /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf
sudo nano /etc/resolv.conf
sudo nano /etc/dhcpcd.conf
cat /etc/resolv.conf
nmcli connection show
sudo nmcli connection modify "Wired connection 1" ipv4.dns "8.8.8.8 1.1.1.1"
sudo nmcli connection modify "Wired connection 1" ipv6.method "disabled"
sudo nmcli connection up "Wired connection 1"
cat /etc/resolv.conf
sudo nmcli connection modify "Wired connection 1" ipv4.ignore-auto-dns yes
sudo nmcli connection up "Wired connection 1"
sudo nmcli connection modify "Wired connection 1" ipv4.ignore-auto-dns yes
sudo nmcli connection up "Wired connection 1"
nslookup api.gateio.ws
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
nslookup api.gateio.ws
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
