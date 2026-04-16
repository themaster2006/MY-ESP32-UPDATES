import network
import urequests
import ujson
import time
import machine
from machine import Pin

# ================================================================
# CREDENCIALES
# ================================================================

WIFI_SSID = "Flia novas p"
WIFI_PASSWORD = "novas1425"
TOKEN = "7104559959:AAFWsh7eViJtDucvb8hn-58oS8gx0i6anDk"
CHAT_ID = "6060134604"

# ================================================================
# WIFI
# ================================================================

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Conectando a WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)

    print("WiFi conectado:", wlan.ifconfig())
    return wlan

# ================================================================
# OTA
# ================================================================

FILE_URL = "https://raw.githubusercontent.com/themaster2006/MY-ESP32-UPDATES/refs/heads/main/main.py"
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
            try:
                r.close()
            except:
                pass

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
            try:
                r.close()
            except:
                pass

    except Exception as e:
        print("[OTA] Error:", e)

# ================================================================
# TELEGRAM
# ================================================================

def enviar(msg):
    try:
        msg = str(msg)[:4000]
        url = "https://api.telegram.org/bot{}/sendMessage".format(TOKEN)
        payload = "chat_id={}&text={}".format(CHAT_ID, msg)
        r = urequests.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            r.close()
        except:
            pass
    except:
        pass

# ================================================================
# PROXY IA
# ================================================================

PROXY_URL = "https://esp32s-proxy.onrender.com/ia"
PING_URL = "https://esp32s-proxy.onrender.com/ping"

proxy_activo = False
ultimo_check = time.ticks_ms()

def check_proxy():
    global proxy_activo

    try:
        r = urequests.get(PING_URL)
        try:
            r.close()
        except:
            pass

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
        payload = ujson.dumps({"prompt": prompt})
        r = urequests.post(PROXY_URL, data=payload, headers={"Content-Type": "application/json"})
        res = r.json()
        try:
            r.close()
        except:
            pass
        return res.get("respuesta", "Sin respuesta")
    except Exception as e:
        print("[IA ERROR]:", e)
        return None

# ================================================================
# TELEGRAM RECEIVE
# ================================================================

last_update_id = 0

def leer_comandos():
    global last_update_id

    url = "https://api.telegram.org/bot{}/getUpdates?offset={}".format(TOKEN, last_update_id + 1)

    try:
        r = urequests.get(url)
        data = r.json()
        try:
            r.close()
        except:
            pass

        for update in data.get("result", []):
            last_update_id = update.get("update_id", last_update_id)

            if "message" not in update:
                continue

            msg = update["message"].get("text", "")
            user_id = str(update["message"]["chat"]["id"])

            ejecutar_comando(msg, user_id)

    except:
        pass

# ================================================================
# LED
# ================================================================

led = Pin(2, Pin.OUT)
led.value(0)

_timer_end = 0

# ================================================================
# SESION PRO
# ================================================================

sesion_activa = False
sesion_inicio = 0
SESION_TIMEOUT = 300000

def ejecutar_comando(cmd, user_id):
    global _timer_end, sesion_activa, sesion_inicio

    cmd = cmd.strip()
    cmd_low = cmd.lower()
    print("[CMD]:", cmd_low, "| USER:", user_id)

    if str(user_id) != CHAT_ID:
        return

    if sesion_activa:
        if time.ticks_diff(time.ticks_ms(), sesion_inicio) > SESION_TIMEOUT:
            sesion_activa = False
            led.value(0)
            enviar("⏱️ Sesión expirada automáticamente")
            return

    if cmd_low == "eep":
        sesion_activa = True
        sesion_inicio = time.ticks_ms()
        enviar("🟢 Sesión iniciada (EEP)")
        return

    if cmd_low in ("ce", "adios", "adiós"):
        sesion_activa = False
        led.value(0)
        _timer_end = 0
        enviar("🔴 Sesión cerrada")
        return

    if not sesion_activa:
        return

    sesion_inicio = time.ticks_ms()

    if cmd_low.startswith("ia"):
        prompt = cmd[2:].strip()
        if not prompt:
            enviar("Usa: ia hola")
            return

        if not proxy_activo:
            enviar("⚠️ IA no disponible")
            return

        respuesta = preguntar_ia(prompt)

        if respuesta:
            enviar("🤖 {}".format(respuesta))
        else:
            enviar("⚠️ Error IA")

        return

    if cmd_low == "off":
        led.value(0)
        enviar("LED apagado ❌")
        return

    if cmd_low == "estado":
        estado = "ON" if led.value() else "OFF"
        enviar("LED: {}".format(estado))
        return

    try:
        segundos = float(cmd_low)
        if segundos <= 0:
            enviar("Número inválido")
            return

        led.value(1)
        _timer_end = time.ticks_add(time.ticks_ms(), int(segundos * 1000))
        enviar("LED ON {}s 💡".format(segundos))

    except:
        enviar("Comando inválido: {}".format(cmd))
# ================================================================
# INIT
# ================================================================

conectar_wifi()
check_update()
enviar("🚀 ESP32 listo")

# ================================================================
# LOOP
# ================================================================

while True:
    if time.ticks_diff(time.ticks_ms(), ultimo_check) > 10000:
        check_proxy()
        ultimo_check = time.ticks_ms()

    leer_comandos()

    if _timer_end and time.ticks_diff(time.ticks_ms(), _timer_end) >= 0:
        led.value(0)
        enviar("LED apagado automático ⏱️")
        _timer_end = 0

    time.sleep(2)
