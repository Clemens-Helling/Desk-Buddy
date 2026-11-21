"""DeskBuddy Pico W/WH - main.py (MicroPython, BLE-HID-Macropad)

Der Pico meldet sich per Bluetooth LE als HID-Gerät (Tastatur + Medientasten)
am PC an. Die Befehle kommen per UART vom Raspberry Pi 4, zusätzlich steuert
der Pico einen WS2812-/SK6812-LED-Streifen.

Verdrahtung:
    Pico GP0 (TX) -> Raspberry Pi GPIO15 (RX, Pin 10)
    Pico GP1 (RX) -> Raspberry Pi GPIO14 (TX, Pin 8)
    Pico GND      -> Raspberry Pi GND
    LED-Streifen: DIN an GP2, 5 V an VSYS, GND gemeinsam

Befehle (je eine JSON-Zeile, Antwort "ok ..." oder "error <grund>"):
    {"type": "shortcut", "keys": ["CTRL", "C"]}
    {"type": "shortcut", "keys": ["VOLUME_UP"]}
    {"type": "text", "text": "Hallo"}
    {"type": "led", "mode": "fill", "color": [62, 207, 142], "count": 8, "brightness": 0.25}
    {"type": "led", "mode": "pixels", "pixels": [[255, 0, 0], ...], "brightness": 0.5}
    {"type": "led", "mode": "off"}
    {"type": "status"}   -> "ok connected" | "ok disconnected"
    {"type": "unpair"}   -> löscht gespeicherte Kopplungen (danach neu koppeln)

Die Kopplung (Bonding) wird in ble_keys.json auf dem Pico gespeichert, damit der
PC den Pico nach einem Neustart ohne erneutes Koppeln wiedererkennt.
"""

import bluetooth
import machine
import utime

try:
    import ubinascii as binascii
except ImportError:
    import binascii

try:
    import neopixel
except ImportError:
    neopixel = None

try:
    import ujson as json
except ImportError:
    import json

from micropython import const

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

DEVICE_NAME = "DeskBuddy"
UART_BAUD = 115200
LED_PIN = const(2)
LED_COUNT = const(8)
SECRETS_FILE = "ble_keys.json"

MAX_LINE_BYTES = const(2048)
MAX_TEXT_CHARS = const(500)
KEY_PRESS_MS = const(10)
KEY_GAP_MS = const(6)

UART = machine.UART(
    0,
    baudrate=UART_BAUD,
    tx=machine.Pin(0),
    rx=machine.Pin(1),
    rxbuf=MAX_LINE_BYTES,
)

# --------------------------------------------------------------------------
# BLE-Konstanten
# --------------------------------------------------------------------------

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_ENCRYPTION_UPDATE = const(28)
_IRQ_GET_SECRET = const(29)
_IRQ_SET_SECRET = const(30)
_IRQ_PASSKEY_ACTION = const(31)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
_FLAG_READ_ENCRYPTED = const(0x0200)
_FLAG_WRITE_ENCRYPTED = const(0x1000)

_IO_CAPABILITY_NO_INPUT_OUTPUT = const(3)
_APPEARANCE_KEYBOARD = const(961)

_SERVICE_HID = bluetooth.UUID(0x1812)
_SERVICE_BATTERY = bluetooth.UUID(0x180F)
_SERVICE_DEVICE_INFO = bluetooth.UUID(0x180A)
_CHAR_HID_INFORMATION = bluetooth.UUID(0x2A4A)
_CHAR_REPORT_MAP = bluetooth.UUID(0x2A4B)
_CHAR_HID_CONTROL_POINT = bluetooth.UUID(0x2A4C)
_CHAR_REPORT = bluetooth.UUID(0x2A4D)
_CHAR_PROTOCOL_MODE = bluetooth.UUID(0x2A4E)
_CHAR_BATTERY_LEVEL = bluetooth.UUID(0x2A19)
_CHAR_MANUFACTURER_NAME = bluetooth.UUID(0x2A29)
_CHAR_MODEL_NUMBER = bluetooth.UUID(0x2A24)
_CHAR_PNP_ID = bluetooth.UUID(0x2A50)
_DESC_REPORT_REFERENCE = bluetooth.UUID(0x2908)

# Report-IDs. Über BLE enthalten die Report-Daten selbst KEINE Report-ID, sie
# wird nur im Report-Reference-Descriptor der jeweiligen Characteristic genannt.
_REPORT_ID_KEYBOARD = const(1)
_REPORT_ID_CONSUMER = const(2)

# HID-Report-Map: Tastatur (ID 1, 8 Byte Input, 1 Byte LED-Output) und
# Consumer Control (ID 2, ein 16-Bit-Usage).
_HID_REPORT_MAP = bytes(
    (
        # --- Keyboard ---
        0x05, 0x01,        # Usage Page (Generic Desktop)
        0x09, 0x06,        # Usage (Keyboard)
        0xA1, 0x01,        # Collection (Application)
        0x85, 0x01,        #   Report ID (1)
        0x05, 0x07,        #   Usage Page (Key Codes)
        0x19, 0xE0,        #   Usage Minimum (Left Control)
        0x29, 0xE7,        #   Usage Maximum (Right GUI)
        0x15, 0x00,        #   Logical Minimum (0)
        0x25, 0x01,        #   Logical Maximum (1)
        0x75, 0x01,        #   Report Size (1)
        0x95, 0x08,        #   Report Count (8)
        0x81, 0x02,        #   Input (Data, Variable, Absolute) - Modifier
        0x95, 0x01,        #   Report Count (1)
        0x75, 0x08,        #   Report Size (8)
        0x81, 0x01,        #   Input (Constant) - reserviert
        0x95, 0x05,        #   Report Count (5)
        0x75, 0x01,        #   Report Size (1)
        0x05, 0x08,        #   Usage Page (LEDs)
        0x19, 0x01,        #   Usage Minimum (Num Lock)
        0x29, 0x05,        #   Usage Maximum (Kana)
        0x91, 0x02,        #   Output (Data, Variable, Absolute) - LEDs
        0x95, 0x01,        #   Report Count (1)
        0x75, 0x03,        #   Report Size (3)
        0x91, 0x01,        #   Output (Constant) - Padding
        0x95, 0x06,        #   Report Count (6)
        0x75, 0x08,        #   Report Size (8)
        0x15, 0x00,        #   Logical Minimum (0)
        0x25, 0x65,        #   Logical Maximum (101)
        0x05, 0x07,        #   Usage Page (Key Codes)
        0x19, 0x00,        #   Usage Minimum (0)
        0x29, 0x65,        #   Usage Maximum (101)
        0x81, 0x00,        #   Input (Data, Array) - Tasten
        0xC0,              # End Collection
        # --- Consumer Control ---
        0x05, 0x0C,        # Usage Page (Consumer)
        0x09, 0x01,        # Usage (Consumer Control)
        0xA1, 0x01,        # Collection (Application)
        0x85, 0x02,        #   Report ID (2)
        0x15, 0x00,        #   Logical Minimum (0)
        0x26, 0xFF, 0x03,  #   Logical Maximum (0x03FF)
        0x19, 0x00,        #   Usage Minimum (0)
        0x2A, 0xFF, 0x03,  #   Usage Maximum (0x03FF)
        0x75, 0x10,        #   Report Size (16)
        0x95, 0x01,        #   Report Count (1)
        0x81, 0x00,        #   Input (Data, Array)
        0xC0,              # End Collection
    )
)

# --------------------------------------------------------------------------
# Tasten
# --------------------------------------------------------------------------

MOD_CTRL = const(0x01)
MOD_SHIFT = const(0x02)
MOD_ALT = const(0x04)
MOD_GUI = const(0x08)

MODIFIERS = {
    "CTRL": MOD_CTRL,
    "CONTROL": MOD_CTRL,
    "STRG": MOD_CTRL,
    "SHIFT": MOD_SHIFT,
    "ALT": MOD_ALT,
    "GUI": MOD_GUI,
    "WIN": MOD_GUI,
    "CMD": MOD_GUI,
    "SUPER": MOD_GUI,
}

KEY_CODES = {
    "ENTER": 0x28,
    "RETURN": 0x28,
    "ESC": 0x29,
    "ESCAPE": 0x29,
    "BACKSPACE": 0x2A,
    "TAB": 0x2B,
    "SPACE": 0x2C,
    "MINUS": 0x2D,
    "EQUAL": 0x2E,
    "LEFT_BRACKET": 0x2F,
    "RIGHT_BRACKET": 0x30,
    "BACKSLASH": 0x31,
    "SEMICOLON": 0x33,
    "QUOTE": 0x34,
    "GRAVE": 0x35,
    "COMMA": 0x36,
    "DOT": 0x37,
    "PERIOD": 0x37,
    "SLASH": 0x38,
    "CAPSLOCK": 0x39,
    "PRINTSCREEN": 0x46,
    "INSERT": 0x49,
    "HOME": 0x4A,
    "PAGEUP": 0x4B,
    "DELETE": 0x4C,
    "END": 0x4D,
    "PAGEDOWN": 0x4E,
    "RIGHT": 0x4F,
    "LEFT": 0x50,
    "DOWN": 0x51,
    "UP": 0x52,
}

for _i in range(26):
    KEY_CODES[chr(ord("A") + _i)] = 0x04 + _i
for _i in range(9):
    KEY_CODES[str(_i + 1)] = 0x1E + _i
KEY_CODES["0"] = 0x27
for _i in range(1, 13):
    KEY_CODES["F{}".format(_i)] = 0x3A + (_i - 1)
for _i in range(13, 25):
    KEY_CODES["F{}".format(_i)] = 0x68 + (_i - 13)

# Consumer-Usages (HID Usage Page 0x0C): Medientasten.
CONSUMER_CODES = {
    "PLAY_PAUSE": 0xCD,
    "STOP": 0xB7,
    "NEXT": 0xB5,
    "NEXT_TRACK": 0xB5,
    "PREV": 0xB6,
    "PREVIOUS": 0xB6,
    "PREV_TRACK": 0xB6,
    "MUTE": 0xE2,
    "VOLUME_UP": 0xE9,
    "VOL_UP": 0xE9,
    "VOLUME_DOWN": 0xEA,
    "VOL_DOWN": 0xEA,
    "BRIGHTNESS_UP": 0x6F,
    "BRIGHTNESS_DOWN": 0x70,
}

# Zeichen -> (Modifier, Keycode) für ein US-Tastaturlayout.
CHAR_TO_KEY = {
    " ": (0, 0x2C),
    "\n": (0, 0x28),
    "\t": (0, 0x2B),
    "-": (0, 0x2D),
    "_": (MOD_SHIFT, 0x2D),
    "=": (0, 0x2E),
    "+": (MOD_SHIFT, 0x2E),
    "[": (0, 0x2F),
    "{": (MOD_SHIFT, 0x2F),
    "]": (0, 0x30),
    "}": (MOD_SHIFT, 0x30),
    "\\": (0, 0x31),
    "|": (MOD_SHIFT, 0x31),
    ";": (0, 0x33),
    ":": (MOD_SHIFT, 0x33),
    "'": (0, 0x34),
    '"': (MOD_SHIFT, 0x34),
    "`": (0, 0x35),
    "~": (MOD_SHIFT, 0x35),
    ",": (0, 0x36),
    "<": (MOD_SHIFT, 0x36),
    ".": (0, 0x37),
    ">": (MOD_SHIFT, 0x37),
    "/": (0, 0x38),
    "?": (MOD_SHIFT, 0x38),
    "!": (MOD_SHIFT, 0x1E),
    "@": (MOD_SHIFT, 0x1F),
    "#": (MOD_SHIFT, 0x20),
    "$": (MOD_SHIFT, 0x21),
    "%": (MOD_SHIFT, 0x22),
    "^": (MOD_SHIFT, 0x23),
    "&": (MOD_SHIFT, 0x24),
    "*": (MOD_SHIFT, 0x25),
    "(": (MOD_SHIFT, 0x26),
    ")": (MOD_SHIFT, 0x27),
}


def _char_to_key(ch):
    if "a" <= ch <= "z":
        return (0, 0x04 + (ord(ch) - ord("a")))
    if "A" <= ch <= "Z":
        return (MOD_SHIFT, 0x04 + (ord(ch) - ord("A")))
    if "1" <= ch <= "9":
        return (0, 0x1E + (ord(ch) - ord("1")))
    if ch == "0":
        return (0, 0x27)
    return CHAR_TO_KEY.get(ch)


# --------------------------------------------------------------------------
# BLE-HID
# --------------------------------------------------------------------------


def advertising_payload(name, service_uuid16, appearance):
    """Baut die Advertising-Daten (Flags, HID-Service, Appearance, Name)."""
    payload = bytearray()

    def _append(ad_type, value):
        payload.extend(bytes((len(value) + 1, ad_type)) + value)

    _append(0x01, b"\x06")  # LE General Discoverable, kein BR/EDR
    _append(0x03, bytes((service_uuid16 & 0xFF, (service_uuid16 >> 8) & 0xFF)))
    _append(0x19, bytes((appearance & 0xFF, (appearance >> 8) & 0xFF)))
    _append(0x09, name.encode("utf-8"))
    return payload


def _gatt_services(secure):
    """GATT-Tabelle. secure=True verlangt verschlüsselte Verbindung (Pairing)."""
    enc_r = _FLAG_READ_ENCRYPTED if secure else 0
    enc_w = _FLAG_WRITE_ENCRYPTED if secure else 0
    report_ref = (_DESC_REPORT_REFERENCE, _FLAG_READ)
    return (
        (
            _SERVICE_HID,
            (
                (_CHAR_HID_INFORMATION, _FLAG_READ),
                (_CHAR_REPORT_MAP, _FLAG_READ | enc_r),
                (_CHAR_HID_CONTROL_POINT, _FLAG_WRITE_NO_RESPONSE),
                (_CHAR_PROTOCOL_MODE, _FLAG_READ | _FLAG_WRITE_NO_RESPONSE),
                # Input: Tastatur
                (_CHAR_REPORT, _FLAG_READ | _FLAG_NOTIFY | enc_r, (report_ref,)),
                # Input: Consumer Control
                (_CHAR_REPORT, _FLAG_READ | _FLAG_NOTIFY | enc_r, (report_ref,)),
                # Output: Tastatur-LEDs (Caps Lock usw.)
                (
                    _CHAR_REPORT,
                    _FLAG_READ | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE | enc_r | enc_w,
                    (report_ref,),
                ),
            ),
        ),
        (
            _SERVICE_BATTERY,
            ((_CHAR_BATTERY_LEVEL, _FLAG_READ | _FLAG_NOTIFY),),
        ),
        (
            _SERVICE_DEVICE_INFO,
            (
                (_CHAR_MANUFACTURER_NAME, _FLAG_READ),
                (_CHAR_MODEL_NUMBER, _FLAG_READ),
                (_CHAR_PNP_ID, _FLAG_READ),
            ),
        ),
    )


class DeskBuddyBLEKeyboard:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._conn_handle = None
        self._encrypted = False
        self._led_state = 0
        self._secrets = {}
        self._secrets_dirty = False
        self._load_secrets()

        self._ble.irq(self._irq)
        self._ble.config(gap_name=DEVICE_NAME)
        secure = self._configure_security()

        try:
            handles = self._ble.gatts_register_services(_gatt_services(secure))
        except OSError:
            # Falls der Stack die Security-Flags ablehnt: ohne Verschlüsselungspflicht.
            handles = self._ble.gatts_register_services(_gatt_services(False))
        (
            (
                h_info,
                h_map,
                _h_control,
                h_protocol,
                self._h_keyboard,
                h_keyboard_ref,
                self._h_consumer,
                h_consumer_ref,
                self._h_led,
                h_led_ref,
            ),
            (h_battery,),
            (h_manufacturer, h_model, h_pnp),
        ) = handles

        # Wichtig: Standard-Puffer einer Characteristic sind nur 20 Byte. Die
        # Report-Map ist länger und würde sonst abgeschnitten -> PC verwirft das
        # HID-Gerät oder zeigt es als "unbekannt" an.
        self._ble.gatts_set_buffer(h_map, len(_HID_REPORT_MAP))
        self._ble.gatts_write(h_info, b"\x11\x01\x00\x02")  # HID 1.11, normally connectable
        self._ble.gatts_write(h_map, _HID_REPORT_MAP)
        self._ble.gatts_write(h_protocol, b"\x01")  # Report Protocol Mode
        self._ble.gatts_write(h_keyboard_ref, bytes((_REPORT_ID_KEYBOARD, 0x01)))  # Input
        self._ble.gatts_write(h_consumer_ref, bytes((_REPORT_ID_CONSUMER, 0x01)))  # Input
        self._ble.gatts_write(h_led_ref, bytes((_REPORT_ID_KEYBOARD, 0x02)))  # Output
        self._ble.gatts_write(self._h_keyboard, b"\x00" * 8)
        self._ble.gatts_write(self._h_consumer, b"\x00" * 2)
        self._ble.gatts_write(self._h_led, b"\x00")
        self._ble.gatts_write(h_battery, b"\x64")
        self._ble.gatts_write(h_manufacturer, b"DeskBuddy")
        self._ble.gatts_write(h_model, b"Macropad")
        # PnP-ID: Quelle USB, Vendor 0x2E8A (Raspberry Pi), Produkt 0x000A, Version 1.0
        self._ble.gatts_write(h_pnp, b"\x02\x8a\x2e\x0a\x00\x00\x01")

        self._payload = advertising_payload(DEVICE_NAME, 0x1812, _APPEARANCE_KEYBOARD)
        self._advertise()

    def _configure_security(self):
        """Aktiviert Pairing/Bonding ("Just Works"). Gibt zurück, ob es verfügbar ist."""
        ok = True
        for option in ({"bond": True}, {"mitm": False}, {"io": _IO_CAPABILITY_NO_INPUT_OUTPUT}):
            try:
                self._ble.config(**option)
            except (TypeError, ValueError, OSError):
                ok = False
        return ok

    # -- Bonding-Schlüssel ---------------------------------------------------

    def _load_secrets(self):
        try:
            with open(SECRETS_FILE, "r") as f:
                for sec_type, key, value in json.load(f):
                    self._secrets[(sec_type, binascii.unhexlify(key))] = binascii.unhexlify(value)
        except (OSError, ValueError):
            self._secrets = {}

    def save_secrets_if_needed(self):
        """Schreibt geänderte Schlüssel ins Flash. Nicht aus dem IRQ aufrufen."""
        if not self._secrets_dirty:
            return
        self._secrets_dirty = False
        entries = [
            [sec_type, binascii.hexlify(key).decode(), binascii.hexlify(value).decode()]
            for (sec_type, key), value in self._secrets.items()
        ]
        try:
            with open(SECRETS_FILE, "w") as f:
                json.dump(entries, f)
        except OSError:
            pass

    def unpair(self):
        """Löscht alle gespeicherten Kopplungen und trennt die Verbindung."""
        self._secrets = {}
        self._secrets_dirty = True
        if self._conn_handle is not None:
            try:
                self._ble.gap_disconnect(self._conn_handle)
            except OSError:
                pass

    # -- Verbindung ----------------------------------------------------------

    def _advertise(self):
        self._ble.gap_advertise(100_000, adv_data=self._payload)

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self._conn_handle = data[0]
            self._encrypted = False
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self._conn_handle = None
            self._encrypted = False
            self._advertise()
        elif event == _IRQ_ENCRYPTION_UPDATE:
            conn_handle, encrypted, _authenticated, _bonded, _key_size = data
            if conn_handle == self._conn_handle:
                self._encrypted = bool(encrypted)
        elif event == _IRQ_PASSKEY_ACTION:
            pass  # "Just Works": keine Eingabe nötig
        elif event == _IRQ_SET_SECRET:
            sec_type, key, value = data
            key = (sec_type, bytes(key))
            if value is None:
                self._secrets.pop(key, None)
            else:
                self._secrets[key] = bytes(value)
            self._secrets_dirty = True
            return True
        elif event == _IRQ_GET_SECRET:
            sec_type, index, key = data
            if key is None:
                position = 0
                for (stored_type, _stored_key), value in self._secrets.items():
                    if stored_type == sec_type:
                        if position == index:
                            return value
                        position += 1
                return None
            return self._secrets.get((sec_type, bytes(key)))
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, attr_handle = data
            if conn_handle == self._conn_handle and attr_handle == self._h_led:
                value = self._ble.gatts_read(attr_handle)
                if value:
                    self._led_state = value[0]

    @property
    def connected(self):
        return self._conn_handle is not None

    # -- Reports -------------------------------------------------------------

    def _notify(self, handle, report):
        if self._conn_handle is None:
            return False
        try:
            self._ble.gatts_write(handle, report)
            self._ble.gatts_notify(self._conn_handle, handle, report)
        except OSError:
            return False
        return True

    def send_keys(self, modifier, keycodes):
        """Drückt Modifier + bis zu 6 Tasten und lässt sie wieder los."""
        keycodes = keycodes[:6]
        report = bytes((modifier & 0xFF, 0x00)) + bytes(keycodes) + b"\x00" * (6 - len(keycodes))
        if not self._notify(self._h_keyboard, report):
            return False
        utime.sleep_ms(KEY_PRESS_MS)
        return self._notify(self._h_keyboard, b"\x00" * 8)

    def send_consumer(self, usage):
        """Sendet eine Medientaste (Lautstärke, Play/Pause, ...)."""
        if not self._notify(self._h_consumer, bytes((usage & 0xFF, (usage >> 8) & 0xFF))):
            return False
        utime.sleep_ms(KEY_PRESS_MS)
        return self._notify(self._h_consumer, b"\x00\x00")


ble_keyboard = DeskBuddyBLEKeyboard()


def send_shortcut(keys):
    """Führt eine Tastenkombination aus. Gibt (ok, grund) zurück."""
    modifier = 0
    keycodes = []
    consumer = None
    for raw_name in keys:
        name = str(raw_name).strip().upper()
        if not name:
            continue
        if name in MODIFIERS:
            modifier |= MODIFIERS[name]
        elif name in KEY_CODES:
            code = KEY_CODES[name]
            if code not in keycodes:
                keycodes.append(code)
        elif name in CONSUMER_CODES:
            consumer = CONSUMER_CODES[name]
        else:
            return False, "unknown-key"
    if consumer is not None:
        return ble_keyboard.send_consumer(consumer), "send-failed"
    if modifier == 0 and not keycodes:
        return False, "no-keys"
    return ble_keyboard.send_keys(modifier, keycodes), "send-failed"


def send_text(text):
    """Tippt Text (US-Layout). Nicht abbildbare Zeichen werden übersprungen."""
    for ch in text:
        combo = _char_to_key(ch)
        if combo is None:
            continue
        if not ble_keyboard.send_keys(combo[0], [combo[1]]):
            return False
        utime.sleep_ms(KEY_GAP_MS)
    return True


# --------------------------------------------------------------------------
# LED-Streifen
# --------------------------------------------------------------------------

led_strip = neopixel.NeoPixel(machine.Pin(LED_PIN), LED_COUNT) if neopixel else None


def _clamp_channel(value):
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        return 0


def _clamp_brightness(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def _parse_rgb(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) == 6:
            try:
                return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
            except ValueError:
                return None
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (_clamp_channel(value[0]), _clamp_channel(value[1]), _clamp_channel(value[2]))
    return None


def _scale(rgb, brightness):
    return (int(rgb[0] * brightness), int(rgb[1] * brightness), int(rgb[2] * brightness))


def _render_leds(colors):
    for i in range(LED_COUNT):
        led_strip[i] = colors[i] if i < len(colors) else (0, 0, 0)
    led_strip.write()


def send_led(command):
    """Verarbeitet einen LED-Befehl. Gibt (ok, grund) zurück."""
    if led_strip is None:
        return False, "led-unavailable"

    mode = str(command.get("mode", "fill")).strip().lower()
    if mode == "off":
        _render_leds([])
        return True, ""

    brightness = _clamp_brightness(command.get("brightness", 1.0))

    if mode == "pixels":
        pixels = command.get("pixels", [])
        if not isinstance(pixels, list):
            return False, "invalid-pixels"
        colors = []
        for item in pixels[:LED_COUNT]:
            rgb = _parse_rgb(item)
            colors.append(_scale(rgb, brightness) if rgb else (0, 0, 0))
        _render_leds(colors)
        return True, ""

    rgb = _parse_rgb(command.get("color", [255, 255, 255]))
    if rgb is None:
        return False, "invalid-color"
    try:
        count = max(0, min(LED_COUNT, int(command.get("count", LED_COUNT))))
    except (TypeError, ValueError):
        count = LED_COUNT
    _render_leds([_scale(rgb, brightness)] * count)
    return True, ""


# --------------------------------------------------------------------------
# UART-Befehle
# --------------------------------------------------------------------------


def reply(message):
    UART.write((message + "\n").encode("utf-8"))


def handle_command(line):
    try:
        command = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeError):
        reply("error invalid-json")
        return
    if not isinstance(command, dict):
        reply("error invalid-command")
        return

    kind = command.get("type")

    if kind == "led":
        ok, reason = send_led(command)
        reply("ok" if ok else "error " + reason)
    elif kind == "text":
        if not ble_keyboard.connected:
            reply("error not-connected")
        elif send_text(str(command.get("text", ""))[:MAX_TEXT_CHARS]):
            reply("ok")
        else:
            reply("error send-failed")
    elif kind == "shortcut":
        keys = command.get("keys", [])
        if not isinstance(keys, list):
            reply("error invalid-keys")
        elif not ble_keyboard.connected:
            reply("error not-connected")
        else:
            ok, reason = send_shortcut(keys)
            reply("ok" if ok else "error " + reason)
    elif kind in ("status", "ping"):
        reply("ok connected" if ble_keyboard.connected else "ok disconnected")
    elif kind == "unpair":
        ble_keyboard.unpair()
        reply("ok")
    else:
        reply("error unknown-command")


def main():
    buffer = bytearray()
    while True:
        ble_keyboard.save_secrets_if_needed()

        waiting = UART.any()
        if not waiting:
            utime.sleep_ms(5)
            continue

        buffer.extend(UART.read(waiting) or b"")

        while True:
            end = buffer.find(b"\n")
            if end < 0:
                break
            line = bytes(buffer[:end]).strip()
            buffer = buffer[end + 1:]
            if not line:
                continue
            try:
                handle_command(line)
            except Exception:  # Firmware darf durch einen Befehl nie abstürzen
                reply("error internal")

        if len(buffer) > MAX_LINE_BYTES:
            buffer = bytearray()
            reply("error line-too-long")


main()
