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

def enviar(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        r = urequests.get(url)
        r.close()
    except:
        pass

# ================================================================
# PROXY IA
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

# ================================================================
# TELEGRAM RECEIVE
# ================================================================
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

# ================================================================
# LED
# ================================================================
led = Pin(2, Pin.OUT)
led.value(0)

_timer_end = 0

def ejecutar_comando(cmd):
    global _timer_end

    cmd = cmd.strip().lower()

    # =========================
    # IA
    # =========================
    if cmd.startswith("ia "):
        prompt = cmd[3:]

        if not proxy_activo:
            enviar("⚠️ IA no disponible (proxy caído)")
            return

        respuesta = preguntar_ia(prompt)

        if respuesta:
            enviar(f"🤖 {respuesta}")
        else:
            enviar("⚠️ Error con IA")

        return

    # =========================
    # NORMAL
    # =========================
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
enviar("ESP32 iniciado 🚀")

while True:
    # 🔍 Revisar proxy cada 10 segundos
    if time.ticks_diff(time.ticks_ms(), ultimo_check) > 10000:
        check_proxy()
        ultimo_check = time.ticks_ms()

    leer_comandos()

    # ⏱️ Timer LED
    if _timer_end and time.ticks_diff(_timer_end, time.ticks_ms()) <= 0:
        led.value(0)
        enviar("LED apagado automático ⏱️")
        _timer_end = 0

    time.sleep(2)
