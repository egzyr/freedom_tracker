"""
FreedomTracker Dashboard v1.0
─────────────────────────────
Osobny monitor do bota — odpala się obok bota.
Instalacja: pip install rich
Uruchomienie: python3 dashboard.py
"""

import os, time, hmac, hashlib, json, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')
GATE_KEY    = os.getenv('GATE_API_KEY')
GATE_SECRET = os.getenv('GATE_SECRET')
BASE_URL    = "https://api.gateio.ws"

REFRESH = 5  # sekund między odświeżeniami

CONTRACT_MULT = {
    "BTC_USDT": 0.0001,
    "ETH_USDT": 0.01,
    "SOL_USDT": 0.1,
}
ICONS = {
    "BTC_USDT": "🟠",
    "ETH_USDT": "🔵",
    "SOL_USDT": "🟣",
}

# ── API ───────────────────────────────────────────────────────────────────────
def sign(method, path, query="", body=""):
    ts  = str(int(time.time()))
    h   = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{h}\n{ts}"
    sig = hmac.new(GATE_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return {"KEY": GATE_KEY, "Timestamp": ts, "SIGN": sig, "Content-Type": "application/json"}

def gate(method, path, params=None, body=None):
    query = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
    url   = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    b_str = json.dumps(body) if body else ""
    try:
        r = requests.request(method, url, headers=sign(method, path, query, b_str),
                             data=b_str, timeout=10)
        return r.json()
    except Exception as e:
        return {}

def get_account():   return gate("GET", "/api/v4/futures/usdt/accounts")
def get_positions(): return gate("GET", "/api/v4/futures/usdt/positions")
def get_orders(sym): return gate("GET", "/api/v4/futures/usdt/orders",
                                 {"contract": sym, "status": "open"})
def get_price(sym):
    t = gate("GET", "/api/v4/futures/usdt/tickers", {"contract": sym})
    return float(t[0]["last"]) if isinstance(t, list) and t else 0.0

# ── RICH DASHBOARD ────────────────────────────────────────────────────────────
try:
    from rich.live       import Live
    from rich.table      import Table
    from rich.panel      import Panel
    from rich.columns    import Columns
    from rich.text       import Text
    from rich.console    import Console
    from rich            import box
    RICH = True
except ImportError:
    RICH = False

def bar(pct, width=10):
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)

def pnl_color(val):
    if not RICH:
        return f"{val:+.2f}"
    if val > 0:  return f"[green]{val:+.2f}[/green]"
    if val < 0:  return f"[red]{val:+.2f}[/red]"
    return f"{val:+.2f}"

def build_dashboard():
    acc  = get_account()
    eq   = float(acc.get("total",          0)) if acc else 0
    fr   = float(acc.get("available",      0)) if acc else 0
    pnl  = float(acc.get("unrealised_pnl", 0)) if acc else 0

    positions = get_positions()
    pos_map   = {}
    if isinstance(positions, list):
        for p in positions:
            sz = float(p.get("size", 0))
            if sz != 0:
                pos_map[p["contract"]] = p

    now = datetime.now().strftime("%H:%M:%S  %d.%m.%Y")
    margin_pct = fr / eq if eq > 0 else 0

    if not RICH:
        # ── FALLBACK: czysty terminal ─────────────────────────────────────────
        os.system("clear")
        print("=" * 58)
        print(f"  🤖 FreedomTracker Dashboard       {now}")
        print("=" * 58)
        print(f"  💰 Equity:  {eq:>10.2f} USDT")
        print(f"  💵 Wolne:   {fr:>10.2f} USDT  {bar(margin_pct)}")
        pnl_sign = "+" if pnl >= 0 else ""
        print(f"  📈 PnL:     {pnl_sign}{pnl:.2f} USDT")
        print("-" * 58)
        for sym in ["BTC_USDT", "ETH_USDT"]:
            icon  = ICONS.get(sym, "•")
            price = get_price(sym)
            p     = pos_map.get(sym)
            if p:
                entry  = float(p.get("entry_price", 0))
                sz     = float(p.get("size", 0))
                ppnl   = float(p.get("unrealised_pnl", 0))
                pct    = (price - entry) / entry * 100 if entry > 0 else 0
                pnl_s  = f"{ppnl:+.2f}"
                print(f"\n  {icon} {sym}")
                print(f"    Pozycja:  {sz:.0f}k kontraktów")
                print(f"    Entry:    {entry:.2f}")
                print(f"    Teraz:    {price:.2f}  ({pct:+.1f}%)")
                print(f"    PnL:      {pnl_s} USDT")
            else:
                print(f"\n  {icon} {sym}   {price:.2f}   Brak pozycji")
            orders = get_orders(sym)
            if isinstance(orders, list):
                buys  = sorted([o for o in orders if int(float(o.get("size",0))) > 0],
                               key=lambda o: float(o.get("price",0)), reverse=True)
                sells = [o for o in orders if int(float(o.get("size",0))) < 0]
                for i, o in enumerate(buys, 1):
                    op    = float(o.get("price", 0))
                    dist  = (price - op) / price * 100 if price > 0 else 0
                    print(f"    L{i} BUY   {op:.2f}   ({dist:.1f}% niżej)")
                for o in sells:
                    op   = float(o.get("price", 0))
                    dist = (op - price) / price * 100 if price > 0 else 0
                    print(f"    TP  SELL  {op:.2f}   ({dist:.1f}% wyżej)")
        print("\n" + "=" * 58)
        print(f"  Odświeżanie co {REFRESH}s  |  Ctrl+C aby wyjść")
        return

    # ── RICH: ładny dashboard ─────────────────────────────────────────────────
    console = Console()

    # Nagłówek
    header = Text(f"🤖 FreedomTracker Dashboard   {now}", style="bold cyan")

    # Konto
    acc_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    acc_table.add_column(style="dim")
    acc_table.add_column(justify="right", style="bold")
    acc_table.add_column()
    mg_color = "green" if margin_pct > 0.4 else ("yellow" if margin_pct > 0.2 else "red")
    acc_table.add_row("💰 Equity",  f"{eq:.2f} USDT", "")
    acc_table.add_row("💵 Wolne",   f"[{mg_color}]{fr:.2f} USDT[/{mg_color}]",
                      f"[{mg_color}]{bar(margin_pct)}[/{mg_color}]")
    pnl_c = "green" if pnl >= 0 else "red"
    acc_table.add_row("📈 PnL",     f"[{pnl_c}]{pnl:+.2f} USDT[/{pnl_c}]", "")

    panels = [Panel(acc_table, title="[bold]💼 KONTO[/bold]", border_style="cyan")]

    # Per symbol
    for sym in ["BTC_USDT", "ETH_USDT"]:
        icon  = ICONS.get(sym, "•")
        price = get_price(sym)
        p     = pos_map.get(sym)

        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column(style="dim", width=12)
        t.add_column(justify="right", style="bold", width=14)
        t.add_column(width=14)

        t.add_row("Cena", f"{price:.2f}", "")

        if p:
            entry = float(p.get("entry_price", 0))
            sz    = float(p.get("size", 0))
            ppnl  = float(p.get("unrealised_pnl", 0))
            pct   = (price - entry) / entry * 100 if entry > 0 else 0
            pc    = "green" if pct >= 0 else "red"
            lc    = "green" if ppnl >= 0 else "red"
            t.add_row("Pozycja",  f"{sz:.0f}k", "kontraktów")
            t.add_row("Entry",    f"{entry:.2f}", "")
            t.add_row("Zmiana",   f"[{pc}]{pct:+.1f}%[/{pc}]",
                      f"[{pc}]{bar(abs(pct)/10, 8)}[/{pc}]")
            t.add_row("PnL",      f"[{lc}]{ppnl:+.2f}[/{lc}]", "USDT")
        else:
            t.add_row("Pozycja", "[dim]Brak[/dim]", "")

        # Zlecenia
        orders = get_orders(sym)
        if isinstance(orders, list) and orders:
            t.add_row("", "", "")
            buys  = sorted([o for o in orders if int(float(o.get("size",0))) > 0],
                           key=lambda o: float(o.get("price",0)), reverse=True)
            sells = [o for o in orders if int(float(o.get("size",0))) < 0]
            for i, o in enumerate(buys, 1):
                op   = float(o.get("price", 0))
                dist = (price - op) / price * 100 if price > 0 else 0
                t.add_row(f"[cyan]L{i} BUY[/cyan]",
                          f"[cyan]{op:.2f}[/cyan]",
                          f"[dim]↓{dist:.1f}%[/dim]")
            for o in sells:
                op   = float(o.get("price", 0))
                dist = (op - price) / price * 100 if price > 0 else 0
                t.add_row("[green]TP SELL[/green]",
                          f"[green]{op:.2f}[/green]",
                          f"[dim]↑{dist:.1f}%[/dim]")
        else:
            t.add_row("[dim]Zlecenia[/dim]", "[dim]Brak[/dim]", "")

        panels.append(Panel(t, title=f"[bold]{icon} {sym}[/bold]",
                            border_style="yellow" if p else "dim"))

    return Panel(
        Columns(panels, equal=True, expand=True),
        title=str(header),
        subtitle=f"[dim]odświeżanie co {REFRESH}s  |  Ctrl+C aby wyjść[/dim]",
        border_style="bright_blue",
        padding=(1, 2),
    )


def main():
    if not RICH:
        print("⚠️  Biblioteka 'rich' niedostępna — używam trybu tekstowego")
        print("   Instalacja: pip install rich")
        print()
        try:
            while True:
                build_dashboard()
                time.sleep(REFRESH)
        except KeyboardInterrupt:
            print("\nDashboard zamknięty.")
        return

    console = Console()
    with Live(console=console, refresh_per_second=1, screen=True) as live:
        try:
            while True:
                panel = build_dashboard()
                if panel:
                    live.update(panel)
                time.sleep(REFRESH)
        except KeyboardInterrupt:
            pass
    print("Dashboard zamknięty.")


if __name__ == "__main__":
    main()
