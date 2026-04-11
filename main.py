import network
import urequests
import time
from machine import Pin

# ================================================================
# WIFI
# ================================================================
SSID = "Flia novas p"
PASSWORD = "novas1425"

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Conectando WiFi...")
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
    print("WiFi OK:", wlan.ifconfig())

# ================================================================
# TELEGRAM
# ================================================================
TOKEN = "7104559959:AAFWsh7eViJtDucvb8hn-58oS8gx0i6anDk"
CHAT_ID = "6060134604"

last_update_id = 0

def enviar(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        r = urequests.get(url)
        r.close()
    except Exception as e:
        print("Error enviando:", e)

def leer_comandos():
    global last_update_id

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update_id+1}"

    try:
        r = urequests.get(url)
        data = r.json()
        r.close()

        for update in data["result"]:
            last_update_id = update["update_id"]

            if "message" not in update:
                continue

            msg = update["message"].get("text", "")
            user_id = str(update["message"]["chat"]["id"])

            # Seguridad: solo tú controlas
            if user_id != CHAT_ID:
                continue

            ejecutar_comando(msg)

    except Exception as e:
        print("Error leyendo comandos:", e)

# ================================================================
# LED
# ================================================================
LED_PIN = 2
led = Pin(LED_PIN, Pin.OUT)
led.value(0)

_timer_end = 0

def ejecutar_comando(cmd):
    global _timer_end

    cmd = cmd.strip().lower()

    if cmd == "off":
        led.value(0)
        enviar("LED apagado ❌")
        return

    if cmd == "estado":
        estado = "ON" if led.value() else "OFF"
        enviar(f"LED: {estado}")
        return

    try:
        segundos = float(cmd)

        if segundos <= 0:
            enviar("Error: número inválido")
            return

        led.value(1)
        _timer_end = time.ticks_add(time.ticks_ms(), int(segundos * 1000))

        enviar(f"LED ON {segundos}s 💡")

    except:
        enviar(f"Comando inválido: {cmd}")

# ================================================================
# MAIN
# ================================================================
conectar_wifi()
enviar("ESP32 listo para comandos 🚀")

while True:
    leer_comandos()

    if _timer_end and time.ticks_diff(_timer_end, time.ticks_ms()) <= 0:
        led.value(0)
        enviar("LED apagado automático ⏱️")
        _timer_end = 0

    time.sleep(2)