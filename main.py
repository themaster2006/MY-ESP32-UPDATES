"""
ble_led.py — MicroPython 1.27.0
================================
Enciende el LED integrado la cantidad de segundos indicada
por terminal Bluetooth (BLE UART) desde Thonny o cualquier
app de BLE serial (como "Serial Bluetooth Terminal" en Android).

Plataformas soportadas:
  • ESP32         → LED_PIN = 2
  • Pico W        → LED_PIN = "LED"
  • ESP32-S3      → LED_PIN = 8   (ajustar según board)
  • ESP32-C3      → LED_PIN = 8

Uso desde terminal BLE:
  Envía un número (segundos): "5"   → LED encendido 5 segundos
  Envía un float:             "2.5" → LED encendido 2.5 segundos
  Envía "off"                       → Apaga el LED inmediatamente
  Envía "estado"                    → Responde si el LED está ON/OFF
"""

import bluetooth
import time
from machine import Pin
from micropython import const
import struct

# ================================================================
#   CONFIGURACIÓN — ajusta según tu placa
# ================================================================
LED_PIN      = 2          # ESP32: 2 | Pico W: "LED" | ESP32-S3/C3: 8
LED_ACTIVE   = 1          # 1 = HIGH enciende | 0 = LOW enciende (ESP32 built-in = 1)
DEVICE_NAME  = "SALEM-LED"  # nombre visible en Bluetooth

# ================================================================
#   CONSTANTES BLE UART (Nordic UART Service — NUS)
#   Compatibles con Thonny BLE terminal y apps móviles estándar
# ================================================================
_IRQ_CENTRAL_CONNECT    = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE        = const(3)

_FLAG_READ   = const(0x0002)
_FLAG_WRITE  = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
_FLAG_WRITE_NO_RESP = const(0x0004)

# Nordic UART Service UUIDs
_NUS_UUID  = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_RX_UUID   = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")  # Central → Periferico
_TX_UUID   = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")  # Periferico → Central

_NUS_SERVICE = (
    _NUS_UUID,
    (
        (_TX_UUID, _FLAG_READ | _FLAG_NOTIFY),
        (_RX_UUID, _FLAG_WRITE | _FLAG_WRITE_NO_RESP),
    ),
)

# ================================================================
#   CLASE BLE UART
# ================================================================
class BLEUART:
    def __init__(self, ble, name=DEVICE_NAME):
        self._ble       = ble
        self._connected = False
        self._conn_handle = None
        self._rx_buf    = b""
        self._on_rx     = None

        ble.active(True)
        ble.irq(self._irq)

        # Registrar servicio GATT
        ((self._tx_handle, self._rx_handle),) = ble.gatts_register_services(
            (_NUS_SERVICE,)
        )

        # Aumentar el buffer de recepción
        ble.gatts_set_buffer(self._rx_handle, 256)

        # Iniciar advertising
        self._advertise(name)
        print(f"[BLE] Advertising como '{name}'")

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self._conn_handle, _, _ = data
            self._connected = True
            print("[BLE] Dispositivo conectado")
            self.send("SALEM-LED listo\r\nEnvia segundos (ej: 5) para encender el LED\r\n")

        elif event == _IRQ_CENTRAL_DISCONNECT:
            self._conn_handle = None
            self._connected   = False
            print("[BLE] Dispositivo desconectado — reiniciando advertising")
            self._advertise(DEVICE_NAME)

        elif event == _IRQ_GATTS_WRITE:
            _, value_handle = data
            if value_handle == self._rx_handle:
                chunk = self._ble.gatts_read(self._rx_handle)
                self._rx_buf += chunk
                # Procesar líneas completas
                while b"\n" in self._rx_buf or b"\r" in self._rx_buf:
                    for sep in (b"\r\n", b"\n", b"\r"):
                        if sep in self._rx_buf:
                            line, self._rx_buf = self._rx_buf.split(sep, 1)
                            line = line.strip()
                            if line and self._on_rx:
                                self._on_rx(line.decode("utf-8", "ignore"))
                            break
                    else:
                        break

    def _advertise(self, name):
        name_bytes = name.encode()
        adv_data = (
            bytes([0x02, 0x01, 0x06])                          # flags
            + bytes([len(name_bytes) + 1, 0x09])               # complete local name
            + name_bytes
        )
        self._ble.gap_advertise(100_000, adv_data=adv_data)   # intervalo 100 ms

    def send(self, text):
        """Envía texto al terminal BLE conectado."""
        if not self._connected or self._conn_handle is None:
            return
        try:
            data = text.encode() if isinstance(text, str) else text
            # Enviar en chunks de 20 bytes (límite BLE sin negociación MTU)
            for i in range(0, len(data), 20):
                self._ble.gatts_notify(self._conn_handle,
                                       self._tx_handle,
                                       data[i:i+20])
                time.sleep_ms(10)
        except Exception as e:
            print(f"[BLE] Error enviando: {e}")

    def on_rx(self, callback):
        """Registra callback para recibir datos."""
        self._on_rx = callback

    @property
    def connected(self):
        return self._connected


# ================================================================
#   CONTROL DEL LED
# ================================================================
led = Pin(LED_PIN, Pin.OUT)
led.value(0)   # apagado al inicio

def led_on():
    led.value(LED_ACTIVE)

def led_off():
    led.value(0 if LED_ACTIVE else 1)

def led_is_on():
    return led.value() == LED_ACTIVE


# ================================================================
#   LÓGICA PRINCIPAL
# ================================================================
ble  = bluetooth.BLE()
uart = BLEUART(ble)

# Estado del temporizador
_timer_end = 0   # timestamp en ms cuando debe apagarse (0 = no activo)

def handle_command(cmd):
    global _timer_end
    cmd = cmd.strip().lower()

    if not cmd:
        return

    # Comando "off" — apagar inmediatamente
    if cmd == "off":
        led_off()
        _timer_end = 0
        uart.send("LED apagado\r\n")
        print("[LED] Apagado por comando")
        return

    # Comando "estado" — consultar estado
    if cmd in ("estado", "status", "?"):
        estado = "ON" if led_is_on() else "OFF"
        restante = max(0, (_timer_end - time.ticks_ms()) // 1000) if _timer_end else 0
        uart.send(f"LED: {estado}")
        if led_is_on() and restante > 0:
            uart.send(f" ({restante}s restantes)")
        uart.send("\r\n")
        return

    # Comando numérico — segundos a encender
    try:
        segundos = float(cmd)
        if segundos <= 0:
            uart.send("Error: ingresa un numero positivo\r\n")
            return
        if segundos > 3600:
            uart.send("Error: maximo 3600 segundos (1 hora)\r\n")
            return

        led_on()
        _timer_end = time.ticks_add(time.ticks_ms(), int(segundos * 1000))

        if segundos == int(segundos):
            msg = f"LED ON por {int(segundos)} segundo{'s' if segundos != 1 else ''}\r\n"
        else:
            msg = f"LED ON por {segundos:.1f} segundos\r\n"

        uart.send(msg)
        print(f"[LED] Encendido por {segundos}s")

    except ValueError:
        uart.send(f"Comando no reconocido: '{cmd}'\r\n")
        uart.send("Comandos validos: <segundos> | off | estado\r\n")
        print(f"[BLE] Comando invalido: {cmd}")


uart.on_rx(handle_command)

# ================================================================
#   LOOP PRINCIPAL
# ================================================================
print("[MAIN] Sistema listo — esperando conexion BLE")

while True:
    # Verificar si el temporizador del LED expiró
    if _timer_end and time.ticks_diff(_timer_end, time.ticks_ms()) <= 0:
        led_off()
        _timer_end = 0
        uart.send("LED apagado (tiempo completado)\r\n")
        print("[LED] Apagado por temporizador")

    time.sleep_ms(50)   # revisar cada 50 ms — preciso a ±50 ms