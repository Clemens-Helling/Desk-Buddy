import bluetooth
import machine
import utime
try:
    import neopixel
except ImportError:
    neopixel = None

try:
    import ujson as json
except ImportError:
    import json

from micropython import const

UART = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1), timeout=10)
LED_PIN = const(2)
LED_COUNT = const(8)

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

_SERVICE_HID = bluetooth.UUID(0x1812)
_SERVICE_BATTERY = bluetooth.UUID(0x180F)
_SERVICE_DEVICE_INFO = bluetooth.UUID(0x180A)
_CHAR_HID_INFORMATION = bluetooth.UUID(0x2A4A)
_CHAR_REPORT_MAP = bluetooth.UUID(0x2A4B)
_CHAR_HID_CONTROL_POINT = bluetooth.UUID(0x2A4C)
_CHAR_REPORT = bluetooth.UUID(0x2A4D)
_CHAR_PROTOCOL_MODE = bluetooth.UUID(0x2A4E)
_CHAR_BOOT_KB_INPUT = bluetooth.UUID(0x2A22)
_CHAR_BOOT_KB_OUTPUT = bluetooth.UUID(0x2A32)
_CHAR_BATTERY_LEVEL = bluetooth.UUID(0x2A19)
_CHAR_MANUFACTURER_NAME = bluetooth.UUID(0x2A29)
_CHAR_MODEL_NUMBER = bluetooth.UUID(0x2A24)

_APPEARANCE_KEYBOARD = const(961)

_HID_REPORT_MAP = bytes(
    (
        0x05,
        0x01,
        0x09,
        0x06,
        0xA1,
        0x01,
        0x85,
        0x01,
        0x05,
        0x07,
        0x19,
        0xE0,
        0x29,
        0xE7,
        0x15,
        0x00,
        0x25,
        0x01,
        0x75,
        0x01,
        0x95,
        0x08,
        0x81,
        0x02,
        0x95,
        0x01,
        0x75,
        0x08,
        0x81,
        0x01,
        0x95,
        0x05,
        0x75,
        0x01,
        0x05,
        0x08,
        0x19,
        0x01,
        0x29,
        0x05,
        0x91,
        0x02,
        0x95,
        0x01,
        0x75,
        0x03,
        0x91,
        0x01,
        0x95,
        0x06,
        0x75,
        0x08,
        0x15,
        0x00,
        0x25,
        0x65,
        0x05,
        0x07,
        0x19,
        0x00,
        0x29,
        0x65,
        0x81,
        0x00,
        0xC0,
    )
)

MODIFIERS = {
    "CTRL": 0x01,
    "CONTROL": 0x01,
    "SHIFT": 0x02,
    "ALT": 0x04,
    "GUI": 0x08,
    "WIN": 0x08,
    "CMD": 0x08,
}

KEY_CODES = {
    "A": 0x04,
    "B": 0x05,
    "C": 0x06,
    "D": 0x07,
    "E": 0x08,
    "F": 0x09,
    "G": 0x0A,
    "H": 0x0B,
    "I": 0x0C,
    "J": 0x0D,
    "K": 0x0E,
    "L": 0x0F,
    "M": 0x10,
    "N": 0x11,
    "O": 0x12,
    "P": 0x13,
    "Q": 0x14,
    "R": 0x15,
    "S": 0x16,
    "T": 0x17,
    "U": 0x18,
    "V": 0x19,
    "W": 0x1A,
    "X": 0x1B,
    "Y": 0x1C,
    "Z": 0x1D,
    "1": 0x1E,
    "2": 0x1F,
    "3": 0x20,
    "4": 0x21,
    "5": 0x22,
    "6": 0x23,
    "7": 0x24,
    "8": 0x25,
    "9": 0x26,
    "0": 0x27,
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
    "DELETE": 0x4C,
    "RIGHT": 0x4F,
    "LEFT": 0x50,
    "DOWN": 0x51,
    "UP": 0x52,
}

for i in range(1, 13):
    KEY_CODES["F{}".format(i)] = 0x3A + (i - 1)

CHAR_TO_KEY = {
    " ": (0x00, 0x2C),
    "\n": (0x00, 0x28),
    "\t": (0x00, 0x2B),
    ".": (0x00, 0x37),
    ",": (0x00, 0x36),
    "-": (0x00, 0x2D),
    "_": (0x02, 0x2D),
    "=": (0x00, 0x2E),
    "+": (0x02, 0x2E),
    "/": (0x00, 0x38),
    "?": (0x02, 0x38),
    ";": (0x00, 0x33),
    ":": (0x02, 0x33),
    "'": (0x00, 0x34),
    '"': (0x02, 0x34),
    "[": (0x00, 0x2F),
    "{": (0x02, 0x2F),
    "]": (0x00, 0x30),
    "}": (0x02, 0x30),
    "\\": (0x00, 0x31),
    "|": (0x02, 0x31),
    "`": (0x00, 0x35),
    "~": (0x02, 0x35),
    "!": (0x02, 0x1E),
    "@": (0x02, 0x1F),
    "#": (0x02, 0x20),
    "$": (0x02, 0x21),
    "%": (0x02, 0x22),
    "^": (0x02, 0x23),
    "&": (0x02, 0x24),
    "*": (0x02, 0x25),
    "(": (0x02, 0x26),
    ")": (0x02, 0x27),
}

led_strip = neopixel.NeoPixel(machine.Pin(LED_PIN), LED_COUNT) if neopixel else None


def _clamp_channel(value):
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        return 0


def _parse_rgb(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) == 6:
            try:
                return (_clamp_channel(int(text[0:2], 16)), _clamp_channel(int(text[2:4], 16)), _clamp_channel(int(text[4:6], 16)))
            except ValueError:
                return None
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (_clamp_channel(value[0]), _clamp_channel(value[1]), _clamp_channel(value[2]))
    return None


def _clamp_brightness(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def _apply_brightness(rgb, brightness):
    factor = _clamp_brightness(brightness)
    return (int(rgb[0] * factor), int(rgb[1] * factor), int(rgb[2] * factor))


def _render_leds(color_by_index):
    if led_strip is None:
        return False
    for i in range(LED_COUNT):
        led_strip[i] = color_by_index[i] if i < len(color_by_index) else (0, 0, 0)
    led_strip.write()
    return True


def send_led(command):
    if led_strip is None:
        return False, "led-unavailable"

    mode = str(command.get("mode", "fill")).strip().lower()
    if mode == "off":
        return (_render_leds([(0, 0, 0)] * LED_COUNT), "send-failed")

    brightness = _clamp_brightness(command.get("brightness", 1.0))

    if mode == "pixels":
        pixels = command.get("pixels", [])
        if not isinstance(pixels, list):
            return False, "invalid-pixels"
        rgb_values = []
        for item in pixels[:LED_COUNT]:
            rgb = _parse_rgb(item)
            if rgb is None:
                rgb_values.append((0, 0, 0))
            else:
                rgb_values.append(_apply_brightness(rgb, brightness))
        return (_render_leds(rgb_values), "send-failed")

    rgb = _parse_rgb(command.get("color", [255, 255, 255]))
    if rgb is None:
        return False, "invalid-color"
    rgb = _apply_brightness(rgb, brightness)
    try:
        count = max(0, min(LED_COUNT, int(command.get("count", LED_COUNT))))
    except (TypeError, ValueError):
        count = LED_COUNT
    colors = [rgb if i < count else (0, 0, 0) for i in range(LED_COUNT)]
    return (_render_leds(colors), "send-failed")


def advertising_payload(name, services, appearance):
    payload = bytearray()

    def _append(ad_type, value):
        payload.extend(bytes((len(value) + 1, ad_type)) + value)

    _append(0x01, b"\x06")
    for service in services:
        service_bytes = bytes(service)
        if len(service_bytes) == 2:
            _append(0x03, service_bytes)
        elif len(service_bytes) == 16:
            _append(0x07, service_bytes)
    if appearance is not None:
        _append(0x19, bytes((appearance & 0xFF, (appearance >> 8) & 0xFF)))
    if name:
        _append(0x09, name.encode("utf-8"))
    return payload


def configure_ble_security(ble):
    # Newer MicroPython builds support these keys; older builds may not.
    options = (
        {"bond": True},
        {"mitm": False},
        {"io": 0},
    )
    for option in options:
        try:
            ble.config(**option)
        except (TypeError, ValueError, OSError):
            continue


class DeskBuddyBLEKeyboard:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.config(gap_name="DeskBuddy")
        configure_ble_security(self._ble)
        self._ble.irq(self._irq)
        self._conn_handle = None
        self._last_led_state = 0
        self._report_output_handle = None
        self._boot_output_handle = None

        try:
            services = (
                (
                    _SERVICE_HID,
                    (
                        (_CHAR_HID_INFORMATION, _FLAG_READ),
                        (_CHAR_REPORT_MAP, _FLAG_READ),
                        (_CHAR_HID_CONTROL_POINT, _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                        (_CHAR_REPORT, _FLAG_READ | _FLAG_NOTIFY),  # input report
                        (_CHAR_REPORT, _FLAG_READ | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),  # output report
                        (_CHAR_PROTOCOL_MODE, _FLAG_READ | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                        (_CHAR_BOOT_KB_INPUT, _FLAG_READ | _FLAG_NOTIFY),
                        (_CHAR_BOOT_KB_OUTPUT, _FLAG_READ | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                    ),
                ),
                (
                    _SERVICE_BATTERY,
                    (
                        (_CHAR_BATTERY_LEVEL, _FLAG_READ | _FLAG_NOTIFY),
                    ),
                ),
                (
                    _SERVICE_DEVICE_INFO,
                    (
                        (_CHAR_MANUFACTURER_NAME, _FLAG_READ),
                        (_CHAR_MODEL_NUMBER, _FLAG_READ),
                    ),
                ),
            )
            (
                (
                    self._hid_info_handle,
                    self._report_map_handle,
                    self._control_handle,
                    self._report_input_handle,
                    self._report_output_handle,
                    self._protocol_handle,
                    self._boot_input_handle,
                    self._boot_output_handle,
                ),
                (self._battery_level_handle,),
                (self._manufacturer_handle, self._model_handle),
            ) = self._ble.gatts_register_services(services)

            self._ble.gatts_write(self._hid_info_handle, b"\x11\x01\x00\x03")
            self._ble.gatts_write(self._report_map_handle, _HID_REPORT_MAP)
            self._ble.gatts_write(self._protocol_handle, b"\x01")
            self._ble.gatts_write(self._report_input_handle, b"\x01" + b"\x00" * 8)
            self._ble.gatts_write(self._report_output_handle, b"\x01\x00")
            self._ble.gatts_write(self._boot_input_handle, b"\x00" * 8)
            self._ble.gatts_write(self._boot_output_handle, b"\x00")
            self._ble.gatts_write(self._battery_level_handle, b"\x64")
            self._ble.gatts_write(self._manufacturer_handle, b"DeskBuddy")
            self._ble.gatts_write(self._model_handle, b"PicoWH-HID")
            self._payload = advertising_payload("DeskBuddy", [_SERVICE_HID], None)
        except Exception:
            # Fallback for firmware builds that reject the full HID profile.
            minimal = (
                (
                    _SERVICE_HID,
                    (
                        (_CHAR_HID_INFORMATION, _FLAG_READ),
                        (_CHAR_REPORT_MAP, _FLAG_READ),
                        (_CHAR_HID_CONTROL_POINT, _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                        (_CHAR_REPORT, _FLAG_READ | _FLAG_NOTIFY),
                        (_CHAR_PROTOCOL_MODE, _FLAG_READ | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                    ),
                ),
            )
            (
                (
                    self._hid_info_handle,
                    self._report_map_handle,
                    self._control_handle,
                    self._report_input_handle,
                    self._protocol_handle,
                ),
            ) = self._ble.gatts_register_services(minimal)
            self._ble.gatts_write(self._hid_info_handle, b"\x11\x01\x00\x03")
            self._ble.gatts_write(self._report_map_handle, _HID_REPORT_MAP)
            self._ble.gatts_write(self._protocol_handle, b"\x01")
            self._ble.gatts_write(self._report_input_handle, b"\x01" + b"\x00" * 8)
            self._payload = advertising_payload("DeskBuddy", [_SERVICE_HID], None)

        self._advertise()

    def _advertise(self):
        self._ble.gap_advertise(500_000, adv_data=self._payload)

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self._conn_handle, _, _ = data
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self._conn_handle = None
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, attr_handle = data
            if conn_handle != self._conn_handle:
                return
            if attr_handle in (self._report_output_handle, self._boot_output_handle):
                value = self._ble.gatts_read(attr_handle)
                if value:
                    self._last_led_state = value[-1]

    @property
    def connected(self):
        return self._conn_handle is not None

    def _notify_report(self, report):
        if not self.connected:
            return False
        self._ble.gatts_write(self._report_input_handle, report)
        self._ble.gatts_notify(self._conn_handle, self._report_input_handle, report)
        return True

    def send_keys(self, modifier, keycodes):
        keycodes = keycodes[:6]
        report = bytes((0x01, modifier & 0xFF, 0x00)) + bytes(keycodes) + b"\x00" * (6 - len(keycodes))
        if not self._notify_report(report):
            return False
        utime.sleep_ms(10)
        self._notify_report(b"\x01" + b"\x00" * 8)
        return True


ble_keyboard = DeskBuddyBLEKeyboard()


def _char_to_key(ch):
    if "a" <= ch <= "z":
        return (0x00, 0x04 + (ord(ch) - ord("a")))
    if "A" <= ch <= "Z":
        return (0x02, 0x04 + (ord(ch) - ord("A")))
    if "1" <= ch <= "9":
        return (0x00, 0x1E + (ord(ch) - ord("1")))
    if ch == "0":
        return (0x00, 0x27)
    return CHAR_TO_KEY.get(ch)


def send_shortcut(keys):
    modifier = 0
    keycodes = []
    for raw_name in keys:
        name = str(raw_name).strip().upper()
        if not name:
            continue
        if name in MODIFIERS:
            modifier |= MODIFIERS[name]
            continue
        keycode = KEY_CODES.get(name)
        if keycode is not None and keycode not in keycodes:
            keycodes.append(keycode)
    if modifier == 0 and not keycodes:
        return False
    return ble_keyboard.send_keys(modifier, keycodes)


def send_text(text):
    for ch in text:
        combo = _char_to_key(ch)
        if combo is None:
            continue
        modifier, keycode = combo
        if not ble_keyboard.send_keys(modifier, [keycode]):
            return False
        utime.sleep_ms(5)
    return True


while True:
    line = UART.readline()
    if line is None:
        utime.sleep_ms(10)
        continue

    try:
        command = json.loads(line.decode("utf-8").strip())
    except (ValueError, UnicodeError):
        UART.write(b"error invalid-json\n")
        continue

    if not isinstance(command, dict):
        UART.write(b"error invalid-command\n")
        continue

    command_type = command.get("type")
    if command_type == "led":
        sent, reason = send_led(command)
        if sent:
            UART.write(b"ok\n")
        else:
            UART.write(("error %s\n" % reason).encode("utf-8"))
    elif command_type == "text":
        if not ble_keyboard.connected:
            UART.write(b"error not-connected\n")
            continue
        text = str(command.get("text", ""))[:500]
        if send_text(text):
            UART.write(b"ok\n")
        else:
            UART.write(b"error send-failed\n")
    elif command_type == "shortcut":
        if not ble_keyboard.connected:
            UART.write(b"error not-connected\n")
            continue
        keys = command.get("keys", [])
        if not isinstance(keys, list):
            UART.write(b"error invalid-keys\n")
            continue
        if send_shortcut(keys):
            UART.write(b"ok\n")
        else:
            UART.write(b"error send-failed\n")
    else:
        UART.write(b"error unknown-command\n")
