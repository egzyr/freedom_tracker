import time
import Adafruit_DHT
from RPLCD.i2c import CharLCD

# Ustawienia dla czujnika DHT22 (GPIO 17 to przykład, zmień, jeśli używasz innego pinu)
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 17  # Zmień pin, jeśli używasz innego

# Ustawienia LCD (podaj adres I2C swojego wyświetlacza)
lcd = CharLCD('PCF8574', 0x27)  # Używając domyślnego adresu I2C 0x27

while True:
    # Odczyt danych z czujnika DHT22
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)

    # Sprawdź, czy dane zostały poprawnie odczytane
    if humidity is not None and temperature is not None:
        # Wyświetl dane na ekranie LCD
        lcd.clear()
        lcd.write_string(f'Temperature: {temperature:.1f} C')
        lcd.cursor_pos = (1, 0)  # Druga linia LCD
        lcd.write_string(f'Humidity: {humidity:.1f} %')
    else:
        lcd.clear()
        lcd.write_string('Failed to get data')

    time.sleep(2)  # Poczekaj 2 sekundy przed kolejnym odczytem
