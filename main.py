# ================================================================
# IMPORTS
# ================================================================
import network
import urequests
import time
import machine
from machine import Pin

# ================================================================
# OTA
# ================================================================
FILE_URL   = "https://raw.githubusercontent.com/themaster2006/MY-ESP32-UPDATES/refs/heads/main/main.py"
LOCAL_FILE = "main.py"

def check_update():
    wlan = network.WLAN(network.STA_IF)

    if not wlan.isconnected():
        print("[OTA] No WiFi — skipping update")
        return

    try:
        print("[OTA] Checking update...")
        r = urequests.get(FILE_URL)

        if r.status_code == 200:
            new_code = r.content
            r.close()

            try:
                with open(LOCAL_FILE, "rb") as f:
                    current = f.read()

                if current == new_code:
                    print("[OTA] Already up to date")
                    return

            except:
                pass

            with open(LOCAL_FILE, "wb") as f:
                f.write(new_code)

            print("[OTA] Updated! Rebooting...")
            time.sleep(1)
            machine.reset()

        else:
            print("[OTA] HTTP error:", r.status_code)
            r.close()

    except Exception as e:
        print("[OTA] Error:", e)


# ================================================================
# TELEGRAM
# ================================================================
TOKEN = "7104559959:AAFWsh7eViJtDucvb8hn-58oS8gx0i6anDk"
CHAT_ID = "6060134604"

def enviar(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        r = urequests.get(url)
        r.close()
    except:
        pass


# ================================================================
# INIT (AQUÍ PASA TODO)
# ================================================================
check_update()  # 👈 SOLO corre al arrancar (reset)

enviar("🚀 ESP32 listo")


# ================================================================
# RESTO DE TU CÓDIGO (igual que antes)
# ================================================================
PROXY_URL = "https://esp32s-proxy.onrender.com/ia"
PING_URL  = "https://esp32s-proxy.onrender.com/ping"

proxy_activo = False
ultimo_check = 0

def check_proxy():
    global proxy_activo

    try:
        r = urequests.get(PING_URL)
        r.close()

        if not proxy_activo:
            enviar("✅ Proxy IA conectado")

        proxy_activo = True

    except:
        if proxy_activo:
            enviar("❌ Proxy IA desconectado")

        proxy_activo = False


def preguntar_ia(prompt):
    if not proxy_activo:
        return None

    try:
        r = urequests.post(PROXY_URL, json={"prompt": prompt})
        res = r.json()
        r.close()
        return res.get("respuesta", "Sin respuesta")
    except:
        return None


last_update_id = 0

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

            if user_id != CHAT_ID:
                continue

            ejecutar_comando(msg)

    except:
        pass


led = Pin(2, Pin.OUT)
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
            enviar("Número inválido")
            return

        led.value(1)
        _timer_end = time.ticks_add(time.ticks_ms(), int(segundos * 1000))
        enviar(f"LED ON {segundos}s 💡")

    except:
        enviar(f"Comando inválido: {cmd}")


# ================================================================
# LOOP
# ================================================================
while True:

    if time.ticks_diff(time.ticks_ms(), ultimo_check) > 10000:
        check_proxy()
        ultimo_check = time.ticks_ms()

    leer_comandos()

    if _timer_end and time.ticks_diff(_timer_end, time.ticks_ms()) <= 0:
        led.value(0)
        enviar("LED apagado automático ⏱️")
        _timer_end = 0

    time.sleep(2)
