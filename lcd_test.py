from RPLCD.i2c import CharLCD
import time

# Zamień '0x27' na adres twojego ekranu LCD, jeśli jest inny
lcd_address = 0x27  # lub 0x3F

# Inicjalizacja ekranu LCD: ustawienia mogą się różnić
lcd = CharLCD(i2c_expander='PCF8574', address=lcd_address, port=1,
              cols=16, rows=2, charmap='A00', auto_linebreaks=True)

# Funkcja testowa do wyświetlania tekstu na ekranie
def lcd_test():
    lcd.clear()
    lcd.write_string("Hello, Raspberry!")
    time.sleep(2)
    lcd.clear()
    lcd.write_string("LCD Test OK!")
    time.sleep(2)
    lcd.clear()

# Uruchomienie testu
lcd_test()
