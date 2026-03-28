sudo apt update
sudo apt install -y python3-smbus python3-pip i2c-tools
pip3 install RPLCD
python3 -m venv lcd_env
sudo i2cdetect -y 1
sudo raspi-config
sudo reboot
ls
source /home/barte/lcd_env/bin/activate
ls
cd
cd 
python3 telegramm11.py
source lcd_env/bin/activate
jak zrobic    
jak zrobic   
cd
cd 
cd ~/Adafruit_Python_DHT
ls
python3 telegramm11.py
pip install adafruit-blinka
python3 telegramm11.py
pip install adafruit-circuitpython-dht
python3 telegramm11.py
pip install pytz
python3 telegramm11.py
pip install apscheduler
python3 telegramm11.py
pip install python-telegram-bot
python3 telegramm11.py
nano telegramm111.py
python3 telegramm111.py
nano telegramm111.py
python3 telegramm111.py
from telegram import Update
[200~nano telegramm111.py
~
nano telegramm111.py
python3 telegramm111.py
source lcd_env/bin/activate
cd ~/Adafruit_Python_DHT
nohup python3 /home/barte/Adafruit_Python_DHT/telegramm111.py &
sudo apt-get install screen
screen
screen -r
cat nohup.out
vcgencmd measure_temp
ls
ls adafruit_python_shr
adafruit_python_dht
ls adafruit_python_dht
ls
cd ~/Adafruit_Python_DHT
ls
deactivate
ls
cd 
cd ~/Adafruit_Python_DHT
ls
nano telegramm111.py
y
exit
vcgencmd measure_temp
exit
top
quit
exit
vcgencmd measure_temp
[200~login as: barte
barte@192.168.0.57's password:
Linux raspberrypi 6.6.51+rpt-rpi-v8 #1 SMP PREEMPT Debian 1:6.6.51-1+rpt3 (2024-10-08) aarch64

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Last login: Thu Nov 28 20:17:31 2024
barte@raspberrypi:~ $

~python3 --version




python3 --version









[200~
>
~
>

>

>

[200~
>

python3 --version
pip3 --version
pip3 install requests python-telegram-bot --break-system-packages
nano ~/.env_freedom
\
chmod 600 ~/.env.freedom
nano ~/freedom_bot.py
pip3 install python-dotenv --break-system-packages
python3 ~/freedom_bot.py
nano ~/.env_freedom
GATE_API_KEY=twój_klucz_gate
GATE_SECRET=twój_secret_gate
TELEGRAM_TOKEN=twój_token_telegram
TELEGRAM_CHAT_ID=1091775044
rm ~/freedom_bot.py
cat > ~/freedom_bot.py << 'EOF'
import os, asyncio, requests, hmac, hashlib, time
from telegram import Bot
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')
GATE_KEY = os.getenv('GATE_API_KEY')
GATE_SECRET = os.getenv('GATE_SECRET')
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def gate_get(path):
    ts = str(int(time.time()))
    sign_str = f"GET\n{path}\n\n\n{ts}"
    sign = hmac.new(GATE_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
    headers = {"KEY": GATE_KEY, "Timestamp": ts, "SIGN": sign}
    return requests.get(f"https://fx.gate.io{path}", headers=headers).json()

async def main():
    bot = Bot(token=TOKEN)
    acc = gate_get("/api/v4/futures/usdt/accounts")
    if isinstance(acc, dict) and 'total' in acc:
        msg = f"FreedomTracker\nEquity: {float(acc['total']):.2f} USDT\nFree: {float(acc['available']):.2f} USDT\nPnL: {float(acc['unrealised_pnl']):.2f} USDT"
    else:
        msg = f"Blad Gate: {acc}"
    await bot.send_message(chat_id=CHAT_ID, text=msg)
    print("Wyslano!")

asyncio.run(main())
EOF

python3 ~/freedom_bot.py
ping google.com
ping -4 google.com
cat >> ~/.env_freedom << 'EOF'
PYTHONHTTPSVERIFY=1
EOF

sed -i 's/fx.gate.io/api.gateio.ws/g' ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/.env_freedom
python3 ~/freedom_bot.py
nano ~/.env_freedom
python3 ~/freedom_bot.py
crontab -e
nano ~/freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
nano ~/freedom_bot.py
[200~python3 ~/freedom_bot.py~
python3 ~/freedom_bot.py
ps aux | grep freedom_bot
pkill -f freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
sudo nano /etc/systemd/system/freedom.service
[200~sudo systemctl daemon-reload~
sudo systemctl daemon-reload
sudo systemctl enable freedom
sudo systemctl start freedom
sudo nano /etc/systemd/system/freedom.service
python3 ~/freedom_bot.py
sudo journalctl -u freedom -f
[200~
~
sudo journalctl -u freedom -f
[200~sudo journalctl -u freedom -f -n 50~
sudo journalctl -u freedom -f -n 50
sudo systemctl stop freedom
sudo systemctl disable freedom
sudo rm /etc/systemd/system/freedom.service
sudo systemctl daemon-reload
python3 ~/freedom_bot.py
sudo systemctl daemon-reload
nano ~/freedom_bot.py
python3 ~/freedom_bot.py
sudo apt update && sudo apt full-upgrade -y
ps aux | grep freedom_bot
tail -50 ~/freedom_bot.log
ps aux | grep freedom_bot
pkill -f freedom_bot.py
htop
ps aux | grep freedom_bot
tail -f ~/freedom_bot.log
python3 ~/freedom_bot.py
grep -n "trailing" ~/freedom_bot.py | head -20
ps aux | grep freedom_bot
cr
scr
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &+nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &+
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
ps aux | grep freedom_bot
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
ps aux | grep freedom_bot
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
> ~/freedom_bot.log
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py && sleep 2 && nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
ps aux | grep freedom_bot
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
pkill -f freedom_bot.py
nano ~/freedom_bot.py
nohup python3 -u ~/freedom_bot.py >> ~/freedom_bot.log 2>&1 &
nano ~/freedom_bot.py
nohup python3 -u ~/freedom_bot.py >> ~/freedom_bot.log 2>&1 &
sleep 2
nohup python3 -u ~/freedom_bot.py >> ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
ps aux | grep freedom_bot
python3 ~/freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
ps aux | grep freedom_bot
pkill -f freedom_bot.py
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
ps aux | grep freedom_bot
python3 ~/freedom_bot.py
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
cat ~/freedom_bot.log
pkill -f freedom_bot.py
nohup python3 -u ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
pkill -f freedom_bot.py
ls -l ~/freedom_bot.log
python3 ~/freedom_bot.py
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
pkill -f freedom_bot.py
pip install python-dotenv requests
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
ps aux | grep freedom_bot
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
pkill -f freedom_bot.py
ps aux | grep freedom_bot
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
nohup python3 -u ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
ps aux | grep freedom_bot
pkill -f freedom_bot.py
> ~/freedom_bot.log
nohup python3 -u ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
> ~/freedom_bot.py && nano ~/freedom_bot.py
pkill -f freedom_bot.py
> ~/freedom_bot.py && nano ~/freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
ps aux | grep freedom_bot
sed -i "s/\u2018/'/g; s/\u2019/'/g" ~/freedom_bot.py
pkill -f freedom_bot.py && sleep 2 && nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
grep -n "'" ~/freedom_bot.py | head -5
float(p.get('unrealised_pnl',
python3 ~/freedom_bot.py 2>&1 | head -20
python3 -c "
content = open('/home/barte/freedom_bot.py', 'rb').read()
content = content.replace(b'\xe2\x80\x98', b\"'\").replace(b'\xe2\x80\x99', b\"'\")
open('/home/barte/freedom_bot.py', 'wb').write(content)
print('Done')
"
python3 ~/freedom_bot.py 2>&1 | head -5
python3 -c "
content = open('/home/barte/freedom_bot.py', 'rb').read()
content = content.replace(b'\xe2\x80\x98', b\"'\")
content = content.replace(b'\xe2\x80\x99', b\"'\")
content = content.replace(b'\xe2\x80\x9c', b'\"')
content = content.replace(b'\xe2\x80\x9d', b'\"')
open('/home/barte/freedom_bot.py', 'wb').write(content)
print('Done')
"
python3 ~/freedom_bot.py 2>&1 | head -5
sed -n '80,87p' ~/freedom_bot.py
python3 << 'EOF'
c = open('/home/barte/freedom_bot.py').read()
# Fix indentation for fmt_price
c = c.replace('def fmt_price(price, symbol):\nd = CONFIG', 'def fmt_price(price, symbol):\n    d = CONFIG')
c = c.replace("d = CONFIG[symbol][\"price_decimals\"]\nreturn str", "    d = CONFIG[symbol][\"price_decimals\"]\n    return str")
c = c.replace('def fmt_size(size):\nreturn max', 'def fmt_size(size):\n    return max')
open('/home/barte/freedom_bot.py', 'w').write(c)
print('Done')
EOF

python3 ~/freedom_bot.py
cat -A ~/freedom_bot.py | sed -n '81,90p'
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
for i, line in enumerate(lines):
    # Fix fmt_price - 8 spaces -> 4 spaces
    if '        d = CONFIG[symbol]' in line:
        line = '    d = CONFIG[symbol]["price_decimals"]\n'
    # Fix is_market_crashing docstring
    if '"""Wykryj crash:' in line and not line.startswith('    '):
        line = '    ' + line.lstrip()
    fixed.append(line)
open('/home/barte/freedom_bot.py', 'w').writelines(fixed)
print('Done')
EOF

nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
python3 ~/freedom_bot.py
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
for i, line in enumerate(lines):
    # Fix fmt_price - 8 spaces -> 4 spaces
    if '        d = CONFIG[symbol]' in line:
        line = '    d = CONFIG[symbol]["price_decimals"]\n'
    # Fix is_market_crashing docstring
    if '"""Wykryj crash:' in line and not line.startswith('    '):
        line = '    ' + line.lstrip()
    fixed.append(line)
open('/home/barte/freedom_bot.py', 'w').writelines(fixed)
print('Done')
EOF

python3 ~/freedom_bot.py
cat -A ~/freedom_bot.py | sed -n '89,97p'
IndentationError: expected an indented block after 'if' statement on line 91
barte@raspberrypi:~ $ cat -A ~/freedom_bot.py | sed -n '89,97p'
def is_market_crashing():$
if len(btc_price_history) < 5:$
return False$
change = (btc_price_history[-1] - btc_price_history[0]) / btc_price_history[0]$
return change < -0.03   # 3% bardziej konserwatywny prog$
$
def get_dynamic_size(symbol, equity, curr_price):$
"""WielkoM-EM-^[M-DM-^G zlecenia = 2% equity / wartoM-EM-^[M-DM-^G kontraktu"""$
barte@raspberrypi:~ $ 
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    # Fix is_market_crashing body
    if line.strip() == 'if len(btc_price_history) < 5:':
        fixed.append('    if len(btc_price_history) < 5:\n')
    elif line.strip() == 'return False' and i > 0 and 'btc_price_history' in lines[i-1]:
        fixed.append('        return False\n')
    elif line.strip().startswith('change = (btc_price_history'):
        fixed.append('    ' + line.lstrip())
    elif line.strip().startswith('return change < -0.03'):
        fixed.append('    ' + line.lstrip())
    # Fix get_dynamic_size docstring
    elif '"""Wielkos' in line or 'zlecenia = 2%' in line:
        fixed.append('    ' + line.lstrip())
    else:
        fixed.append(line)
    i += 1
open('/home/barte/freedom_bot.py', 'w').writelines(fixed)
print('Done')
EOF

pkill -f freedom_bot.py
python3 ~/freedom_bot.py
barte@raspberrypi:~ $ python3 ~/freedom_bot.py
IndentationError: expected an indented block after function definition on line 105
python3 << 'PYEOF'
import urllib.request
url = "https://pastebin.com/raw/placeholder"
# Zamiast tego tworzymy plik bezposrednio
code = open('/home/barte/freedom_bot.py').read()
# Sprawdz ile bledow
import ast
try:
    ast.parse(code)
    print("OK - brak bledow skladni")
except SyntaxError as e:
    print(f"Blad linia {e.lineno}: {e.msg}")
    # Pokaz kontekst
    lines = code.split('\n')
    for i in range(max(0,e.lineno-3), min(len(lines),e.lineno+2)):
        print(f"{i+1}: {repr(lines[i])}")
PYEOF

python3 << 'PYEOF'
code = open('/home/barte/freedom_bot.py').read()
lines = code.split('\n')
fixed = []
inside_func = False
func_indent = 0

for line in lines:
    stripped = line.lstrip()
    
    # Linie definicji funkcji/klasy - zostaw jak jest
    if stripped.startswith('def ') or stripped.startswith('class '):
        inside_func = True
        fixed.append(line)
        continue
    
    # Pusta linia
    if not stripped:
        inside_func = False
        fixed.append(line)
        continue
    
    # Jesli linia nie ma wcięcia ale powinna (po def)
    if inside_func and line == stripped and not stripped.startswith('#'):
        fixed.append('    ' + stripped)
    else:
        fixed.append(line)

result = '\n'.join(fixed)
open('/home/barte/freedom_bot.py', 'w').write(result)

import ast
try:
    ast.parse(result)
    print("OK!")
except SyntaxError as e:
    print(f"Blad linia {e.lineno}: {e.msg}")
PYEOF

pkill -f freedom_bot.py
sed -i "s/\’/\'/g; s/\‘/\'/g; s/\”/\"/g; s/\“/\"/g" ~/freedom_bot.py
python3 - << 'EOF'
with open('/home/barte/freedom_bot.py', 'r') as f:
    lines = f.readlines()
with open('/home/barte/freedom_bot.py', 'w') as f:
    for line in lines:
        if "ts = str(int(time.time()))" in line:
            f.write("    ts = str(int(time.time()))\n")
        else:
            f.write(line)
EOF

python3 ~/freedom_bot.py
python3 - << 'EOF'
path = '/home/barte/freedom_bot.py'
with open(path, 'r') as f:
    lines = f.readlines()

fixed = []
for i, line in enumerate(lines):
    clean = line.strip()
    # Naprawa bloku requests po 'try'
    if 'r = requests.request(' in line:
        fixed.append('        r = requests.request(method, url,\n')
    elif 'headers=headers, params=params,' in line:
        fixed.append('                             headers=headers, params=params,\n')
    elif 'data=data, timeout=10)' in line:
        fixed.append('                             data=data, timeout=10)\n')
    # Naprawa bloku ts = str(int(time.time())) jeśli znowu uciekło
    elif 'ts = str(int(time.time()))' in line:
        fixed.append('    ts = str(int(time.time()))\n')
    else:
        fixed.append(line)

with open(path, 'w') as f:
    f.writelines(fixed)
print("--- NAPRAWA WCIĘĆ ZAKOŃCZONA ---")
EOF

python3 ~/freedom_bot.py
cat << 'EOF' > ~/freedom_bot.py
import os, time, hmac, hashlib, requests
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')

def gate_api(method, url, params=None, data=None):
    key = os.getenv('GATE_KEY')
    secret = os.getenv('GATE_SECRET')
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    
    ts = str(int(time.time()))
    query_string = requests.models.PreparedRequest()
    query_string.prepare_url("", params)
    query_string = query_string.url[1:]
    
    body_hash = hashlib.sha512((data or "").encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(secret.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    
    headers = {'KEY': key, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    
    try:
        r = requests.request(method, host + prefix + url, headers=headers, params=params, data=data, timeout=10)
        return r.json()
    except Exception as e:
        print(f"Błąd API: {e}")
        return None

print("--- KOD NAPRAWIONY (v7.3.1) ---")
print("Uruchamiam bota...")
EOF

python3 ~/freedom_bot.py
ps aux | grep freedom_bot
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
python3 - << 'EOF'
path = '/home/barte/freedom_bot.py'
with open(path, 'r') as f:
    lines = f.readlines()

fixed = []
indent = 0
for line in lines:
    stripped = line.strip()
    if not stripped:
        fixed.append('\n')
        continue
    
    # Usuwamy stare błędne wcięcia i nakładamy nowe
    if stripped.startswith(('def ', 'import ', 'from ', 'load_dotenv')):
        indent = 0
    
    # Logika automatycznego wcinania
    current_line = '    ' * indent + stripped + '\n'
    fixed.append(current_line)
    
    # Zwiększamy wcięcie po dwukropku
    if stripped.endswith(':'):
        indent += 1
    # Zmniejszamy wcięcie dla return/except/finally
    elif stripped.startswith(('return ', 'except ', 'finally ')):
        indent = max(0, indent - 1)

with open(path, 'w') as f:
    f.writelines(fixed)
print("--- TOTALNA NAPRAWA ZAKOŃCZONA ---")
EOF

python3 ~/freedom_bot.py
tail -f ~/freedom_bot.log
rm ~/freedom_bot.py
curl -s https://gist.githubusercontent.com/t-reals/7e868c2269a8e999c0d15e215438c823/raw/freedom_bot_v73.py -o ~/freedom_bot.py
python3 ~/freedom_bot.py
pkill -f freedom_bot.py
rm ~/freedom_bot.py && touch ~/freedom_bot.py
cat << 'EOF' >> ~/freedom_bot.py
import os, time, hmac, hashlib, requests
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')

def gate_api(method, url, params=None, data=None):
    key = os.getenv('GATE_KEY')
    secret = os.getenv('GATE_SECRET')
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    ts = str(int(time.time()))
    query_string = requests.models.PreparedRequest()
    query_string.prepare_url("", params if params else {})
    query_string = query_string.url[1:] if query_string.url else ""
    body_hash = hashlib.sha512((data or "").encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(secret.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    headers = {'KEY': key, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    try:
        r = requests.request(method, host + prefix + url, headers=headers, params=params, data=data, timeout=10)
        return r.json()
    except Exception as e:
        print(f"Błąd API: {e}")
        return None
EOF

cat << 'EOF' >> ~/freedom_bot.py
def start_bot():
    print("--- BOT STARTUJE (Wersja Ratunkowa) ---")
    while True:
        # Tu bot pobiera dane i sprawdza Trailing/DCA
        # Na razie uruchamiamy silnik komunikacji
        print(f"[{time.strftime('%H:%M:%S')}] Sprawdzam rynek...")
        time.sleep(30)

if __name__ == "__main__":
    start_bot()
EOF

python3 ~/freedom_bot.py
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
cat << 'EOF' >> ~/freedom_bot.py

def tg(msg):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except Exception as e:
        print(f"Błąd Telegram: {e}")

# Testujemy od razu czy wysyła
tg("<b>Bot v7.3.2 połączony!</b>\nSystemy obronne aktywne.")
EOF

nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
python3 ~/freedom_bot.py
cat ~/.env_freedom
cat << 'EOF' > ~/freedom_bot.py
import os, time, hmac, hashlib, requests
from dotenv import load_dotenv

# Wczytujemy klucze
load_dotenv('/home/barte/.env_freedom')

KEY = os.getenv('GATE_KEY')
SECRET = os.getenv('GATE_SECRET')
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def tg(msg):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)

def gate_api(method, url, params=None, data=None):
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    ts = str(int(time.time()))
    query_string = requests.models.PreparedRequest()
    query_string.prepare_url("", params if params else {})
    query_string = query_string.url[1:] if query_string.url else ""
    body_hash = hashlib.sha512((data or "").encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(SECRET.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    headers = {'KEY': KEY, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    r = requests.request(method, host + prefix + url, headers=headers, params=params, data=data, timeout=10)
    return r.json()

print("--- SYSTEMY OBRONNE v7.3.3 ---")
if not KEY or not SECRET:
    print("!!! KRYTYCZNY BŁĄD: Brak kluczy API w pliku .env_freedom !!!")
else:
    print("API Key: OK | Klucze wczytane.")
    tg("<b>Bot Reaktywacja!</b>\nUruchomiono po awarii zasilania.")

# Tu zaczyna się pętla sprawdzania DCA (uproszczona na start)
while True:
    print(f"[{time.strftime('%H:%M:%S')}] Sprawdzam pozycje i wystawiam limity DCA...")
    # Tutaj bot normalnie wykonuje Twoją logikę v7.3
    time.sleep(60)
EOF

python3 ~/freedom_bot.py
pkill -f freedom_bot.py
curl -L https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py -o ~/freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
ps aux | grep freedom_bot
pkill -f freedom_bot.py
python3 ~/freedom_bot.py
curl -L https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py -o ~/freedom_bot.py
python3 ~/freedom_bot.py
pkill -f freedom_bot.py
cat << 'EOF' > ~/freedom_bot.py
import os, time, hmac, hashlib, requests, json
from dotenv import load_dotenv

load_dotenv('/home/barte/.env_freedom')

KEY = os.getenv('GATE_KEY')
SECRET = os.getenv('GATE_SECRET')
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or os.getenv('CHAT_ID')
SYMBOL = "SOL_USDT"
DCA_LEVELS = [-0.02, -0.05, -0.08]
AMOUNT_USD = "10"

def tg(msg):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except: pass

def gate_api(method, url, params=None, data=None):
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    ts = str(int(time.time()))
    req = requests.models.PreparedRequest()
    req.prepare_url("", params if params else {})
    query_string = req.url[1:] if req.url else ""
    body = json.dumps(data) if data else ""
    body_hash = hashlib.sha512(body.encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(SECRET.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    headers = {'KEY': KEY, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    try:
        r = requests.request(method, host + prefix + url, headers=headers, params=params, data=body if data else None, timeout=10)
        return r.json()
    except: return None

def check_and_dca():
    ticker = gate_api("GET", "/tickers", params={"currency_pair": SYMBOL})
    if not ticker: 
        print("Błąd połączenia z API...")
        return
    price = float(ticker[0]['last'])
    orders = gate_api("GET", "/orders", params={"currency_pair": SYMBOL, "status": "open"})
    buys = [o for o in orders if o['side'] == 'buy'] if orders and isinstance(orders, list) else []
    
    if len(buys) == 0:
        print(f"[{time.strftime('%H:%M:%S')}] Brak zleceń. Wystawiam siatkę...")
        tg(f"<b>Bot Aktywny</b>\nCena SOL: {price}\nWystawiam DCA.")
    
    print(f"[{time.strftime('%H:%M:%S')}] Monitorowanie SOL: {price} | Zlecenia: {len(buys)}")

if __name__ == "__main__":
    print("--- FREEDOM BOT v7.3.7 START ---")
    while True:
        try: check_and_dca()
        except Exception as e: print(f"Błąd: {e}")
        time.sleep(45)
EOF

python3 ~/freedom_bot.py
cat ~/.env_freedom
cat << 'EOF' > ~/freedom_bot.py
import os, time, hmac, hashlib, requests

# --- TWOJE DANE (WPISZ JE TUTAJ) ---
KEY = "b9ce751d98a8478f376b78ed0357d27f"
SECRET = "18fd53d3867df132d4e1875a1b3551f2df7b97dfc089cc20423c062c3fae8493"
TOKEN = "7737813357:AAG3I858WYa-_S2IMmAfEFpTkkiSCebvku0"
CHAT_ID = "1091775044"

def tg(msg):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except: pass

def gate_api(method, url, params=None, data=None):
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    ts = str(int(time.time()))
    query_string = requests.models.PreparedRequest()
    query_string.prepare_url("", params if params else {})
    query_string = query_string.url[1:] if query_string.url else ""
    body_hash = hashlib.sha512((data or "").encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(SECRET.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    headers = {'KEY': KEY, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    try:
        r = requests.request(method, host + prefix + url, headers=headers, params=params, data=data, timeout=10)
        return r.json()
    except: return None

print("--- SYSTEMY BOJOWE v7.4.0 ---")
tg("<b>Bot v7.4.0 wstał!</b>\nKlucze wczytane bezpośrednio. Cel: Solana.")

while True:
    print(f"[{time.strftime('%H:%M:%S')}] Monitoring SOL/BTC aktywowany...")
    time.sleep(30)
EOF

python3 ~/freedom_bot.py
cat << 'EOF' >> ~/freedom_bot.py

def check_portfolio():
    # Pobieramy stan konta Cross Margin
    balance = gate_api("GET", "/accounts")
    if not balance: return
    
    msg = "<b>Stan Portfela:</b>\n"
    for b in balance.get('user', {}).get('currencies', []):
        curr = b.get('currency')
        amount = float(b.get('available', 0)) + float(b.get('locked', 0))
        if amount > 0 and curr in ['ETH', 'SOL', 'USDT']:
            msg += f"• {curr}: {amount:.4f}\n"
    
    tg(msg)
    print("[PORTFOLIO] Stan wysłany na TG.")

# Dodajemy wywołanie do pętli
EOF

python3 - << 'EOF'
path = '/home/barte/freedom_bot.py'
with open(path, 'r') as f:
    lines = f.readlines()

# Usuwamy starą, pustą pętlę while i wstawiamy nową, aktywną
new_lines = []
for line in lines:
    if "while True:" in line: break
    new_lines.append(line)

new_lines.append("\nif __name__ == '__main__':\n")
new_lines.append("    print('--- LOGIKA HANDLOWA AKTYWNA ---')\n")
new_lines.append("    check_portfolio()\n") # Sprawdź portfel od razu po starcie
new_lines.append("    while True:\n")
new_lines.append("        print(f'[{time.strftime(\"%H:%M:%S\ Kluczowe systemy aktywne...')\n")
new_lines.append("        # Tutaj wstawimy pełne DCA w kolejnym kroku\n")
new_lines.append("        time.sleep(300)\n")

with open(path, 'w') as f:
    f.writelines(new_lines)
EOF

python3 ~/freedom_bot.py
pkill -f freedom_bot.py
python3 - << 'EOF'
path = '/home/barte/freedom_bot.py'
with open(path, 'r') as f:
    lines = f.readlines()

fixed = []
for line in lines:
    # Usuwamy zepsutą linię z błędem backslash
    if 'Klucze wczytane bezpośrednio' in line or 'Kluczowe systemy aktywne' in line:
        continue
    fixed.append(line)

# Dodajemy czystą pętlę na końcu
if not fixed[-1].strip() == "while True:":
    fixed.append("if __name__ == '__main__':\n")
    fixed.append("    print('--- START SYSTEMU ---')\n")
    fixed.append("    check_portfolio()\n")
    fixed.append("    while True:\n")
    fixed.append("        print('Bot czuwa...')\n")
    fixed.append("        time.sleep(300)\n")

with open(path, 'w') as f:
    f.writelines(fixed)
EOF

python3 ~/freedom_bot.py
cat << 'EOF' > ~/freedom_bot.py
import os, time, hmac, hashlib, requests

# --- TWOJE DANE (WPISZ JE TUTAJ) ---
KEY = "b9ce751d98a8478f376b78ed0357d27f"
SECRET = "18fd53d3867df132d4e1875a1b3551f2df7b97dfc089cc20423c062c3fae8493"
TOKEN = "7737813357:AAG3I858WYa-_S2IMmAfEFpTkkiSCebvku0"
CHAT_ID = "1091775044"

def tg(msg):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except: pass

def gate_api(method, url, params=None, data=None):
    host = "https://api.gateio.ws/api/v4"
    prefix = "/margin"
    ts = str(int(time.time()))
    query_string = requests.models.PreparedRequest()
    query_string.prepare_url("", params if params else {})
    query_string = query_string.url[1:] if query_string.url else ""
    body_hash = hashlib.sha512((data or "").encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{prefix}{url}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(SECRET.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha512).hexdigest()
    headers = {'KEY': KEY, 'Timestamp': ts, 'SIGN': sign, 'Content-Type': 'application/json'}
    try:
        r = requests.request(method, host + prefix + url, headers=headers, params=params, data=data, timeout=10)
        return r.json()
    except: return None

def check_portfolio():
    print("Pobieram stan konta...")
    res = gate_api("GET", "/accounts")
    if not res:
        print("Błąd: Nie udało się pobrać danych z giełdy.")
        return
    
    msg = "<b>Aktywne środki:</b>\n"
    # Sprawdzamy czy struktura odpowiedzi jest poprawna
    currencies = res.get('user', {}).get('currencies', []) if isinstance(res, dict) else []
    
    if not currencies:
        msg += "Nie znaleziono środków na koncie Cross Margin."
    else:
        for b in currencies:
            amount = float(b.get('available', 0)) + float(b.get('locked', 0))
            if amount > 0.0001:
                msg += f"• {b['currency']}: {amount:.4f}\n"
    
    tg(msg)
    print("Stan wysłany na Telegram.")

if __name__ == "__main__":
    print("--- SYSTEMY BOJOWE v7.4.8 ---")
    tg("<b>Bot v7.4.8 Online!</b>\nSprawdzam Twoje ETH i SOL...")
    
    # 1. Sprawdź portfel od razu po starcie
    check_portfolio()
    
    # 2. Główna pętla
    while True:
        print(f"[{time.strftime('%H:%M:%S')}] Monitoring aktywny...")
        time.sleep(300)
EOF

nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
rm ~/freedom_bot.py
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py?token=GHSAT0AAAAAADY2BG7G5BYIOARKKE3YHTFW2OE6VIA" -o ~/freedom_bot.py
python3 ~/freedom_bot.py
pkill -f freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
pkill -f freedom_bot.py
cat << 'EOF' >> ~/freedom_bot.py

def get_dynamic_size(symbol, equity_pct=0.02):
    # 1. Pobierz cenę rynkową
    ticker = gate_api("GET", "/tickers", params={"currency_pair": symbol})
    if not ticker or len(ticker) == 0: return 0
    curr_price = float(ticker[0].get('last', 0))
    
    # 2. Pobierz Equity (całkowita wartość konta w USDT)
    acc = gate_api("GET", "/accounts")
    total_equity = 0
    if acc and 'user' in acc:
        total_equity = float(acc['user'].get('total_margin_balance', 0))
    
    if total_equity == 0 or curr_price == 0: return 0

    # 3. Oblicz wielkość: (Equity * 2%) / Cena
    size = (total_equity * equity_pct) / curr_price
    return round(size, 4)

def place_dca_orders(symbol):
    size = get_dynamic_size(symbol)
    if size == 0:
        print(f"Błąd obliczania wielkości dla {symbol}")
        return

    print(f"Planowane zlecenie DCA dla {symbol}: {size} sztuk")
    # Tutaj wstawilibyśmy gate_api("POST", "/orders", ...)
    tg(f"🤖 <b>DCA Ready:</b>\nPara: {symbol}\nWielkość: {size}\nStatus: Oczekiwanie na poziom wejścia.")

EOF

nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
pkill -f freedom_bot.py
sleep 2
nohup python3 -u ~/freedom_bot.py >> ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
rm ~/freedom_bot.py
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py?token=GHSAT0AAAAAADY2BG7HNN6D24DQESTTAER62OE7A7Q" -o ~/freedom_bot.py
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
curl -o ~/freedom_bot.py https://gist.githubusercontent.com/TWOJ_URL/raw/freedom_bot_final.txt
python3 ~/freedom_bot.py 2>&1 | head -5
pkill -f freedom_bot.py
> ~/freedom_bot.log
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &pkill -f freedom_bot.py
sleep 2
nohup python3 -u ~/freedom_bot.py >> ~/freedom_bot.log 2>&1 &
sleep 5
tail -f ~/freedom_bot.log
pkill -f freedom_bot.py
curl -L "https://gist.githubusercontent.com/TWOJ_USER/TWOJ_GIST_ID/raw/freedom_bot_final.txt" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:100])"
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py?token=GHSAT0AAAAAADY2BG7HNN6D24DQESTTAER62OE7A7Q" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:100])"
pkill -f freedom_bot.py
> ~/freedom_bot.log
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py?token=GHSAT0AAAAAADY2BG7HNN6D24DQESTTAER62OE7A7Q" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:100])"
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:50])"
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:50])"
nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
tail -f ~/freedom_bot.log
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
python3 ~/freedom_bot.py
> ~/freedom_bot.log
screen -S bot
python3 ~/freedom_bot.py
tail -50 ~/freedom_bot.log
tail -f ~/freedom_bot.log
screen -r bot
python3 ~/freedom_bot.py
pkill -f freedom_bot.py
python3 ~/freedom_bot.py
ps aux | grep freedom_bot
pkill -f freedom_bot.py
ps aux | grep freedom_bot
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py" -o ~/freedom_bot.py
python3 -c "print(open('/home/barte/freedom_bot.py').read()[:50])"
head -5 ~/freedom_bot.py
pkill -f freedom_bot.py
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py" -o ~/freedom_bot.py
head -5 ~/freedom_bot.py
screen -S bot
sudo journalctl -u freedom_bot.service -f
lsblk
tail -f ~/freedom_bot.log
sudo journalctl -u freedom_bot.service -f
vcgencmd get_throttled
journalctl -k | grep -i "voltage"
asudo journalctl -u freedom_bot.service -n 50 --no-pager
sudo journalctl -u freedom_bot.service -n 50 --no-pager
sudo systemctl status freedom_bot.service
sudo journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl restart freedom_bot.service
ps aux | grep freedom_bot.py
sudo systemctl status freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sed -i '2i BREAKEVEN_TRIGGER = 0.03  # 3% zysku aktywuje BE' ~/freedom_bot.py
sed -i '/profit_pct =/a \    if profit_pct >= BREAKEVEN_TRIGGER and current_sl < entry_price: current_sl = entry_price; print(f"🛡️ {symbol} BE Active")' ~/freedom_bot.py
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sed -i '/profit_pct =/a \    if profit_pct >= 0.03 and current_sl < entry_price:\n        current_sl = entry_price\n        print(f"🛡️ {symbol} BE Active")' ~/freedom_bot.py && sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sed -i '/profit_pct =/a \    if profit_pct >= 0.03 and current_sl < entry_price:\n        current_sl = entry_price\n        print(f"🛡️ {symbol} BE Active")' ~/freedom_bot.py && sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sed -i '/profit_pct =/a \    if profit_pct >= 0.03 and current_sl < entry_price:\n        current_sl = entry_price\n        print(f"🛡️ {symbol} BE Active")' ~/freedom_bot.py && sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
wget -O ~/freedom_bot.py https://raw.githubusercontent.com/barte-trading/core/main/v7_6_be.py
curl -o /home/barte/freedom_bot.py https://raw.githubusercontent.com/egzyr/freedom_tracker/main/freedom_bot.py
journalctl -u freedom_bot.service -f -n 50
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
> ~/freedom_bot.log
pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo systemctl disable freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl status freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl status freedom_bot.service
sudo journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo pkill -f freedom_bot.py
ps aux | grep freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f

iom DCA 1 dla SOL_USDT
Mar 26 18:25:50 raspberrypi python3[2795]: 🪜 Dodano 

sudo systemctl stop freedom_bot.service
sudo pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo pkill -f freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sudo pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
ps aux | grep freedom_bot
pkill -f freedom_bot.py
ps aux | grep freedom_bot
sudo systemctl stop freedom_bot.service
sudo systemctl status freedom_bot.service
sudo systemctl stop freedom_bot.service
sudo systemctl status freedom_bot.service
sudo systemctl stop freedom_bot.service
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 -c "
c = open('/home/barte/freedom_bot.py','rb').read()
c = c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"')
open('/home/barte/freedom_bot.py','wb').write(c)
print('OK')
"
python3 -c "import py_compile; py_compile.compile('/home/barte/freedom_bot.py', doraise=True)" && echo "Syntax OK"
sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service && python3 << 'PYEOF'
c = open('/home/barte/freedom_bot.py','rb').read()
c = c.replace(b'\xe2\x80\x98',b"'").replace(b'\xe2\x80\x99',b"'").replace(b'\xe2\x80\x9c',b'"').replace(b'\xe2\x80\x9d',b'"')
open('/home/barte/freedom_bot.py','wb').write(c)

# Napraw wcięcia
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
prev_def = False
for line in lines:
    stripped = line.lstrip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        prev_def = True
        fixed.append(line)
    elif prev_def and stripped and not stripped.startswith('#') and line == stripped:
        fixed.append('    ' + stripped)
    else:
        if stripped:
            prev_def = False
        fixed.append(line)
open('/home/barte/freedom_bot.py','w').writelines(fixed)
import ast
try:
    ast.parse(open('/home/barte/freedom_bot.py').read())
    print('OK - mozna uruchomic')
except SyntaxError as e:
    print(f'Blad linia {e.lineno}: {e.msg}')
PYEOF

sed -n '68,74p' ~/freedom_bot.py
python3 << 'PYEOF'
content = open('/home/barte/freedom_bot.py').read()
old = """    try:
    r    = requests.request(method, url, headers=sign(method, path, query, b_str),
    data=b_str, timeout=15)
    data = r.json()
    if isinstance(data, dict) and data.get('label'):
        print(f"  \033[91mAPI ERR\033[0m {data.get('label')} - {data.get('message','')[:50]}")
    return data
    except Exception as e:
    print(f"  \033[91mREQ ERR\033[0m {e}")
    return {}"""
new = """    try:
        r    = requests.request(method, url, headers=sign(method, path, query, b_str),
                                data=b_str, timeout=15)
        data = r.json()
        if isinstance(data, dict) and data.get('label'):
            print(f"  API ERR {data.get('label')} - {data.get('message','')[:50]}")
        return data
    except Exception as e:
        print(f"  REQ ERR {e}")
        return {}"""
content = content.replace(old, new)
open('/home/barte/freedom_bot.py','w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'Blad linia {e.lineno}: {e.msg}')
    lines = content.split('\n')
    for i in range(max(0,e.lineno-3), min(len(lines),e.lineno+2)):
        print(f'{i+1}: {repr(lines[i])}')
PYEOF

python3 << 'PYEOF'
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    # Znajdz zepsute try: i napraw nastepne linie
    if line.strip() == 'try:' and i+1 < len(lines) and not lines[i+1].startswith('        '):
        fixed.append(line)
        i += 1
        # Dodaj wcięcia do linii try bloku az do except
        while i < len(lines) and not lines[i].strip().startswith('except'):
            stripped = lines[i].lstrip()
            if stripped:
                fixed.append('        ' + stripped)
            else:
                fixed.append('\n')
            i += 1
        # Dodaj except
        if i < len(lines):
            fixed.append('    except Exception as e:\n')
            i += 1
            # Dodaj wcięcia do except bloku
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('    ') or (i < len(lines) and lines[i].strip().startswith('return {}')):
                stripped = lines[i].lstrip()
                fixed.append('        ' + stripped)
                i += 1
    else:
        fixed.append(line)
        i += 1

open('/home/barte/freedom_bot.py','w').writelines(fixed)
import ast
try:
    ast.parse(open('/home/barte/freedom_bot.py').read())
    print('OK')
except SyntaxError as e:
    print(f'Blad linia {e.lineno}: {e.msg}')
PYEOF

nano /home/barte/freedom_bot.py
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
journalctl -u freedom_bot.service -f
barte@raspberrypi:~ $ nano /home/barte/freedom_bot.py
nano /home/barte/freedom_bot.py
journalctl -u freedom_bot.service -f
python3 << 'PYEOF'
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    # Znajdz zepsute try: i napraw nastepne linie
    if line.strip() == 'try:' and i+1 < len(lines) and not lines[i+1].startswith('        '):
        fixed.append(line)
        i += 1
        # Dodaj wcięcia do linii try bloku az do except
        while i < len(lines) and not lines[i].strip().startswith('except'):
            stripped = lines[i].lstrip()
            if stripped:
                fixed.append('        ' + stripped)
            else:
                fixed.append('\n')
            i += 1
        # Dodaj except
        if i < len(lines):
            fixed.append('    except Exception as e:\n')
            i += 1
            # Dodaj wcięcia do except bloku
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('    ') or (i < len(lines) and lines[i].strip().startswith('return {}')):
                stripped = lines[i].lstrip()
                fixed.append('        ' + stripped)
                i += 1
    else:
        fixed.append(line)
        i += 1

open('/home/barte/freedom_bot.py','w').writelines(fixed)
import ast
try:
    ast.parse(open('/home/barte/freedom_bot.py').read())
    print('OK')
except SyntaxError as e:
    print(f'Blad linia {e.lineno}: {e.msg}')
PYEOF

pkill -f freedom_bot.py && sleep 2 && nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
ps aux | grep freedom
kill 5302
crontab -l
crontab -l | grep -v freedom_bot | crontab -
crontab -l
pkill -f freedom_bot.py
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
journalctl -u freedom_bot.service -n 50 --no-pager
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && sudo systemctl start freedom_bot.service
pkill -f freedom_bot.py
sudo journalctl -u freedom_bot.service -f
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service && python3 -c "
c=open('/home/barte/freedom_bot.py','rb').read()
c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"')
open('/home/barte/freedom_bot.py','wb').write(c)
print('OK')
" && sudo systemctl start freedom_bot.service
pkill -f freedom_bot.py && sleep 2 && nohup python3 ~/freedom_bot.py > ~/freedom_bot.log 2>&1 &
sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 -c "
lines = open('/home/barte/freedom_bot.py').readlines()
fixed = []
i = 0
while i < len(lines):
    fixed.append(lines[i])
    if lines[i].strip().startswith('def ') and lines[i].strip().endswith(':'):
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(' ') and not lines[i].startswith('\t'):
            fixed.append('    ' + lines[i].lstrip())
            i += 1
        continue
    i += 1
open('/home/barte/freedom_bot.py','w').writelines(fixed)
import ast
try:
    ast.parse(open('/home/barte/freedom_bot.py').read())
    print('OK')
except SyntaxError as e:
    print(f'Blad {e.lineno}: {e.msg}')
" && sudo systemctl start freedom_bot.service && sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
pkill -f freedom_bot.py
curl -sSL https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py -o /home/barte/freedom_bot.py
chmod +x /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
sudo journalctl -u freedom_bot.service -f
curl -sSL https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py -o /home/barte/freedom_bot.py
chmod +x /home/barte/freedom_bot.py
sudo systemctl daemon-reload
sudo systemctl restart freedom_bot.service
sudo journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && python3 -c "c=open('/home/barte/freedom_bot.py','rb').read();c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"');open('/home/barte/freedom_bot.py','wb').write(c)" && sudo systemctl start freedom_bot.service
sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && python3 -c "c=open('/home/barte/freedom_bot.py','rb').read();c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"');open('/home/barte/freedom_bot.py','wb').write(c)" && sudo systemctl start freedom_bot.service && sudo journalctl -u freedom_bot.service -f
sudo journalctl -u freedom_bot.service -f
sudo journalctl -u freedom_bot.service --since "13:50" --until "14:00"
sudo journalctl -u freedom_bot.service --since "13:20" --until "13:50" | grep ETH
grep -n "DCA WYKONANY" ~/freedom_bot.py
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && python3 -c "c=open('/home/barte/freedom_bot.py','rb').read();c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"');open('/home/barte/freedom_bot.py','wb').write(c)" && sudo systemctl start freedom_bot.service
grep -n "DCA WYKONANY" ~/freedom_bot.py
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && python3 -c "c=open('/home/barte/freedom_bot.py','rb').read();c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"');open('/home/barte/freedom_bot.py','wb').write(c)" && sudo systemctl start freedom_bot.service && grep -n "DCA WYKONANY" ~/freedom_bot.py
sudo systemctl stop freedom_bot.service
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service && curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py && python3 -c "c=open('/home/barte/freedom_bot.py','rb').read();c=c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"');open('/home/barte/freedom_bot.py','wb').write(c)" && sudo systemctl start freedom_bot.service
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
pkill -f freedom_bot.py
curl -sSL https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py -o /home/barte/freedom_bot.py
sudo systemctl daemon-reload
sudo systemctl start freedom_bot.service
sudo journalctl -u freedom_bot.service -f
grep -n "DCA WYKONANY" ~/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
grep -n "DCA WYKONANY" ~/freedom_bot.py
sudo journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
curl -sSL https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py -o /home/barte/freedom_bot.py
sudo systemctl daemon-reload
sudo systemctl start freedom_bot.service
sudo journalctl -u freedom_bot.service -f
[200~journalctl -u freedom_bot.service -f
~
journalctl -u freedom_bot.service -f
grep -n "starting_equity" ~/freedom_bot.py | head -5
journalctl -u freedom_bot.service --since "today" | grep -i "equity startowe"
sed -n '645,660p' ~/freedom_bot.py
barte@raspberrypi:~ $ ^C
barte@raspberrypi:~ $ journalctl -u freedom_bot.service --since "today" | grep -i "equity startowe"
barte@raspberrypi:~ $ sed -n '645,660p' ~/freedom_bot.py
barte@raspberrypi:~ $
barte@raspberrypi:~ $ ^C
barte@raspberrypi:~ $ journalctl -u freedom_bot.service --since "today" | grep -i "equity startowe"
barte@raspberrypi:~ $ sed -n '645,660p' ~/freedom_bot.py
barte@raspberrypi:~ $
ccc
barte@raspberrypi:~ $ ^C
barte@raspberrypi:~ $ journalctl -u freedom_bot.service --since "today" | grep -i "equity startowe"
barte@raspberrypi:~ $ sed -n '645,660p' ~/freedom_bot.py
barte@raspberrypi:~ $
barte@raspberrypi:~ $ ^C
barte@raspberrypi:~ $ journalctl -u freedom_bot.service --since "today" | grep -i "equity startowe"
barte@raspberrypi:~ $ sed -n '645,660p' ~/freedom_bot.py
barte@raspberrypi:~ $
sudo systemctl stop freedom_bot.service
sed -i 's/    last_zone_h = -1/    last_zone_h = -1\n    starting_equity = 0/' ~/freedom_bot.py
sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
sed -i 's/                BOT_ACTIVE = False/                global BOT_ACTIVE\n                BOT_ACTIVE = False/' ~/freedom_bot.py
sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
curl -L "https://raw.githubusercontent.com/egzyr/freedom_tracker/refs/heads/main/freedom_bot.py" -o ~/freedom_bot.py
python3 -c "
c = open('/home/barte/freedom_bot.py','rb').read()
c = c.replace(b'\xe2\x80\x98',b\"'\").replace(b'\xe2\x80\x99',b\"'\").replace(b'\xe2\x80\x9c',b'\"').replace(b'\xe2\x80\x9d',b'\"')
open('/home/barte/freedom_bot.py','wb').write(c)
print('OK')
"
sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
content = content.replace(
    '                global BOT_ACTIVE\n                BOT_ACTIVE = False',
    '                BOT_ACTIVE = False'
)
content = content.replace(
    'BOT_ACTIVE = False\n                spadek',
    'global BOT_ACTIVE\n                BOT_ACTIVE = False\n                spadek'
)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl start freedom_bot.service
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
# Usun wszystkie global BOT_ACTIVE z run()
content = content.replace('                global BOT_ACTIVE\n                BOT_ACTIVE = False\n                spadek', '                BOT_ACTIVE = False\n                spadek')
# Dodaj global na poczatku run()
content = content.replace('    cycle = 0\n    last_zone_h = -1\n    starting_equity = 0', '    global BOT_ACTIVE\n    cycle = 0\n    last_zone_h = -1\n    starting_equity = 0')
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
nano /home/barte/freedom.py
sudo systemctl stop freedom_bot.service
pkill -f freedom_bot.py
sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
nano /home/barte/freedom_bot.py
pkill -f freedom_bot.pypkill -f freedom_bot.py\
pkill -f freedom_bot.py
journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
# Usun wszystkie poprzednie proby dodania global
import re
content = re.sub(r'\s*global BOT_ACTIVE\n', '\n', content)
# Dodaj global BOT_ACTIVE na samym poczatku funkcji run()
content = content.replace('def run():\n    threading.Thread', 'def run():\n    global BOT_ACTIVE\n    threading.Thread')
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
content = content.replace(
    '    cycle = 0\n    last_zone_h = -1',
    '    cycle = 0\n    last_zone_h = -1\n    starting_equity = 0'
)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
echo "=== CPU ===" && top -bn1 | grep "Cpu(s)" && echo "=== RAM ===" && free -h && echo "=== TEMP ===" && vcgencmd measure_temp && echo "=== DYSK ===" && df -h / && echo "=== BOT ===" && systemctl is-active freedom_bot.service+
journalctl -u freedom_bot.service -f
++
sudo systemctl start freedom_bot.service
sudo systemctl status freedom_bot.service
journalctl -u freedom_bot.service -f
USDT       82.37  poz=0k ---  buy=5 sell=0
Mar 27 19:52:21 raspberrypi python3[7018]: ------------++++
sudo systemctl enable freedom_bot.service
journalctl -u freedom_bot.service -f
nano /home/barte/freedom_bot.py
sudo systemctl restart freedom_bot.service
journalctl -u freedom_bot.service -f
pkill -f freedom_bot.py
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
for i, line in enumerate(lines):
    if 'def run():' in line:
        print(f"Linia {i+1}: {line.strip()}")
        print(f"Linia {i+2}: {lines[i+1].strip()}")
        break
EOF

python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
lines.insert(677, '    global BOT_ACTIVE\n')
open('/home/barte/freedom_bot.py', 'w').writelines(lines)
import ast
try:
    ast.parse(open('/home/barte/freedom_bot.py').read())
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo journalctl -u freedom_bot.service -n 50 --no-pager
sudo journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
for i, line in enumerate(lines):
    if 'sl_placed[symbol] = True' in line and 'return' in lines[i+1]:
        print(f"Linia {i+1}: {line.strip()}")
EOF

sudo systemctl stop freedom_bot.service
python3 << 'EOF'
lines = open('/home/barte/freedom_bot.py').readlines()
for i, line in enumerate(lines):
    if 'sl_placed[symbol] = True' in line and 'return' in lines[i+1]:
        print(f"Linia {i+1}: {line.strip()}")
EOF

sed -n '430,445p' ~/freedom_bot.py
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()

old = '''    existing = get_price_orders(symbol)
    for o in existing:
        p = float(o.get("trigger", {}).get("price", 0))
        if p > 0 and abs(p - target_sl) / target_sl < 0.001:
            sl_placed[symbol] = True
            return'''

new = '''    existing = get_price_orders(symbol)
    for o in existing:
        p = float(o.get("trigger", {}).get("price", 0))
        if p > 0 and abs(p - target_sl) / target_sl < 0.005:
            sl_placed[symbol] = True
            return
    if not existing:
        sl_placed[symbol] = False'''

content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
# Upewnij sie ze breakeven ma priorytet - usuń tight scalp gdy profit >= 3%
# Aktualnie kod sprawdza profit_pct >= 0.03 jako pierwsze - to jest poprawne
# Problem: po restarcie sl_placed = {} wiec bot stawia SL od nowa
# Fix: sprawdz istniejacy SL na Gate i jesli jest wyzszy niz nowy - zostaw go
old = '''    existing = get_price_orders(symbol)
    for o in existing:
        p = float(o.get("trigger", {}).get("price", 0))
        if p > 0 and abs(p - target_sl) / target_sl < 0.005:
            sl_placed[symbol] = True
            return
    if not existing:
        sl_placed[symbol] = False'''

new = '''    existing = get_price_orders(symbol)
    for o in existing:
        p = float(o.get("trigger", {}).get("price", 0))
        # Jesli istniejacy SL jest WYZSZY niz nowy (lepszy) - zostaw go
        if p > 0 and p >= target_sl * 0.995:
            sl_placed[symbol] = True
            return
    if not existing:
        sl_placed[symbol] = False'''

content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
old = '        if p > 0 and p >= target_sl * 0.995:'
new = '        if p > 0 and abs(p - target_sl) / target_sl < 0.005:'
content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
ast.parse(content)
print('OK')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
old = '''    elif size > dynamic_base * 1.5:
        tight_pct = cfg["sl_pct"] * 0.5
        target_sl = entry * (1 - tight_pct)
        label = f"Tight Scalp -{tight_pct*100:.1f}%"
    else:'''
new = '''    else:'''
content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
ast.parse(content)
print('OK')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo journalctl -u freedom_bot.service -f
192.168.0.57
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()

old = '''    total_exp = size + sum(int(o.get("size", 0)) for o in buys)
    if total_exp >= cfg["max_contracts"] or len(buys) >= cfg["dca_levels"]:
        return'''

new = '''    # Usun nadmiarowe buy limity jesli jest ich wiecej niz dca_levels
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
        return'''

content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()

old = '''def manage_tp(symbol, cfg, size, entry, curr_price, sells):
    tradeable = int(size) - cfg["min_moonbag"]
    if tradeable <= 0:
        return
    ref = trailing_ref.get(symbol, 0)
    if not sells:'''

new = '''def manage_tp(symbol, cfg, size, entry, curr_price, sells):
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

    if not sells:'''

content = content.replace(old, new)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
try:
    ast.parse(content)
    print('OK')
except SyntaxError as e:
    print(f'ERR {e.lineno}: {e.msg}')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()
content = content.replace(
    '"min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,\n        "max_contracts": 20',
    '"min_moonbag": 3, "dca_levels": 5, "grid_step": 0.03,\n        "max_contracts": 20'
)
open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
ast.parse(content)
print('OK')
EOF

sudo systemctl start freedom_bot.service
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()

# BTC grid 2%
content = content.replace(
    '"min_moonbag": 3, "dca_levels": 5, "grid_step": 0.03,\n        "max_contracts": 20',
    '"min_moonbag": 3, "dca_levels": 5, "grid_step": 0.02,\n        "max_contracts": 20'
)

# ETH grid 2%
content = content.replace(
    '"min_moonbag": 1, "dca_levels": 5, "grid_step": 0.03,\n        "max_contracts": 15',
    '"min_moonbag": 1, "dca_levels": 5, "grid_step": 0.02,\n        "max_contracts": 15'
)

open('/home/barte/freedom_bot.py', 'w').write(content)
import ast
ast.parse(content)
print('OK')
EOF

sudo systemctl start freedom_bot.service
```

Potem zresetuj siatki:
```
/reset_dca BTC
/reset_dca ETH
```

**Nowa siatka BTC @ 66k:**
```
L1 @ 64 871
L2 @ 63 574
L3 @ 62 303
L4 @ 61 057
L5 @ 59 836
journalctl -u freedom_bot.service -f
sudo systemctl stop freedom_bot.service
python3 << 'EOF'
content = open('/home/barte/freedom_bot.py').read()

# SL liczy sie od entry ktore Gate zwraca - to jest juz avg entry po DCA
# Problem byl w /sl komendzie ktora pokazywala zly entry
# manage_sl uzywa 'entry' z pozycji Gate - to jest avg entry - wiec jest OK
# Sprawdzmy czy to prawda

# Szukamy manage_sl
idx = content.find('def manage_sl(')
print(content[idx:idx+300])
EOF

