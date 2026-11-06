"""COS Gamepad Driver: a controller as keyboard and pointer.

COS runs Driver(api, device).run() on its own thread. Everything goes
through `api`: api.key() types into COS, api.pointer_move()/click() drive
the pointer, api.evdev() reads the controller.
"""
import os
import time

# evdev codes (linux/input-event-codes.h)
ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y = 0x00, 0x01, 0x10, 0x11
BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST = 0x130, 0x131, 0x133, 0x134
BTN_TL, BTN_TR, BTN_SELECT, BTN_START = 0x136, 0x137, 0x13a, 0x13b
BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT = (
    0x220, 0x221, 0x222, 0x223)

DEADZONE = 0.22          # fraction of the stick's travel that does nothing
MAX_SPEED = 45.0         # pointer cells per second at full deflection
REPEAT_DELAY, REPEAT_EVERY = 0.40, 0.09
TICK = 0.02


class Driver:
    def __init__(self, api, device):
        self.api = api
        self.dev = device
        c = api.curses
        self.buttons = {
            BTN_SOUTH: ('key', 10),             # Enter
            BTN_EAST: ('key', 27),              # Esc
            BTN_NORTH: ('key', ord(' ')),
            BTN_WEST: ('click', 1),
            BTN_TR: ('click', 3),
            BTN_TL: ('scroll', -1),
            BTN_START: ('key', 6),              # Ctrl+F opens the menus
            BTN_SELECT: ('key', 9),             # Tab: next window
        }
        self.dpad_keys = {
            BTN_DPAD_UP: c.KEY_UP, BTN_DPAD_DOWN: c.KEY_DOWN,
            BTN_DPAD_LEFT: c.KEY_LEFT, BTN_DPAD_RIGHT: c.KEY_RIGHT,
        }
        self.hat_keys = {(ABS_HAT0X, -1): c.KEY_LEFT, (ABS_HAT0X, 1): c.KEY_RIGHT,
                         (ABS_HAT0Y, -1): c.KEY_UP, (ABS_HAT0Y, 1): c.KEY_DOWN}
        self.held = {}          # key code -> time of next repeat
        self.stick = [0.0, 0.0]
        self.ranges = {}

    # -- input --------------------------------------------------------------
    def _norm(self, code, value):
        lo, hi = self.ranges.get(code) or (-32768, 32767)
        mid = (lo + hi) / 2.0
        half = max(1.0, (hi - lo) / 2.0)
        v = max(-1.0, min(1.0, (value - mid) / half))
        if abs(v) < DEADZONE:
            return 0.0
        # rescale past the deadzone so speed starts from zero, not a jump
        return (abs(v) - DEADZONE) / (1 - DEADZONE) * (1 if v > 0 else -1)

    def _press(self, key):
        self.api.key(key)
        self.held[key] = time.monotonic() + REPEAT_DELAY

    def _release(self, key):
        self.held.pop(key, None)

    def on_event(self, etype, code, value):
        api = self.api
        if etype == api.EV_KEY:
            if code in self.dpad_keys:
                (self._press if value else self._release)(self.dpad_keys[code])
                return
            act = self.buttons.get(code)
            if not act or value == 2:        # 2 is the kernel's autorepeat
                return
            what, arg = act
            if what == 'key' and value == 1:
                api.key(arg)
            elif what == 'click':
                api.pointer_button(arg, bool(value))
            elif what == 'scroll' and value == 1:
                api.scroll(arg)
        elif etype == api.EV_ABS:
            if code in (ABS_HAT0X, ABS_HAT0Y):
                for direction in (-1, 1):
                    k = self.hat_keys[(code, direction)]
                    if value == direction:
                        if k not in self.held:
                            self._press(k)
                    else:
                        self._release(k)
            elif code == ABS_X:
                self.stick[0] = self._norm(code, value)
            elif code == ABS_Y:
                self.stick[1] = self._norm(code, value)

    # -- timed work: key repeat and the stick --------------------------------
    def tick(self, dt):
        now = time.monotonic()
        for key, due in list(self.held.items()):
            if now >= due:
                self.api.key(key)
                self.held[key] = now + REPEAT_EVERY
        dx, dy = self.stick
        if dx or dy:
            # square the deflection: fine control near the centre, fast at
            # the edge. Cells are about twice as tall as wide, so y is halved.
            sx = dx * abs(dx) * MAX_SPEED * dt
            sy = dy * abs(dy) * MAX_SPEED * dt * 0.5
            self.api.pointer_move(sx, sy)

    def run(self):
        api = self.api
        path = self.dev.get('path')
        if not path or not os.access(path, os.R_OK):
            api.set_status('no permission to read ' + str(path))
            api.notify('[Gamepad] cannot read %s -- run cos.py --grant-input'
                       % path, 'warn')
            return
        for code in (ABS_X, ABS_Y):
            self.ranges[code] = api.absinfo(code)
        api.set_status('running')
        api.notify('[Gamepad] %s ready: D-pad + A/B, stick moves the pointer'
                   % self.dev.get('name', 'controller'))
        last = time.monotonic()
        for ev in api.evdev(tick=TICK):
            if ev is not None:
                self.on_event(*ev)
            now = time.monotonic()
            if now - last >= TICK:
                self.tick(now - last)
                last = now
        api.set_status('stopped')
