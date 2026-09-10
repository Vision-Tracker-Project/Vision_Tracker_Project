"""Pure input state machine; Linux button numbers are configuration, not guesses."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    speeds: tuple = (80, 90, 100)
    initial: int = 0
    inner_ratio: float = 0.8
    spin_limit: int = 80
    diagonal_outer: int = 100

    def __post_init__(self):
        if (not self.speeds or any(type(v) is not int or not 0 < v <= 100 for v in self.speeds)
                or tuple(sorted(set(self.speeds))) != tuple(self.speeds)
                or not 0 <= self.initial < len(self.speeds)
                or not 0 <= self.inner_ratio <= 1 or not 0 <= self.spin_limit <= 100
                or type(self.diagonal_outer) is not int or not 0 < self.diagonal_outer <= 100):
            raise ValueError("Invalid vehicle settings")


class Controller:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.level = self.settings.initial
        self.x = self.y = 0
        self.pending = [0, 0]
        self.buttons = set()
        self.connected = False
        self.dropped = False
        self.neutral_seen = False
        self.armed = False
        self.reason = "startup"
        self.actions = []

    def stop(self, reason):
        self.armed = False
        self.neutral_seen = False
        self.reason = reason
        self.actions.clear()

    def resync(self, x, y, buttons=()):
        self.stop("resync: neutral and fresh enable required")
        if x not in (-1, 0, 1) or y not in (-1, 0, 1):
            raise ValueError("Invalid HAT state during resync")
        self.connected = True
        self.dropped = False
        self.x, self.y = x, y
        self.pending = [x, y]
        self.buttons = set(buttons)
        self.neutral_seen = x == y == 0 and "enable" not in self.buttons

    def disconnect(self):
        self.stop("device disconnected")
        self.connected = False

    def event(self, kind, code=None, value=None):
        if kind == "dropped":
            self.stop("SYN_DROPPED")
            self.dropped = True
            return
        if self.dropped or not self.connected:
            return
        if kind == "axis":
            if value not in (-1, 0, 1):
                self.stop("invalid axis")
                self.dropped = True
                return
            self.pending[0 if code == "x" else 1] = value
        elif kind == "button" and value != 2:
            was_down = code in self.buttons
            if value:
                self.buttons.add(code)
            else:
                self.buttons.discard(code)
            if code == "stop" and value:
                self.stop("software stop lock")
            elif code == "enable" and not value:
                self.stop("enable released")
            elif value and not was_down:
                self.actions.append(code)
        elif kind == "report":
            self.x, self.y = self.pending
            neutral = self.x == self.y == 0
            if neutral and "enable" not in self.buttons and "stop" not in self.buttons:
                self.neutral_seen = True
            for action in self.actions:
                if action == "enable" and neutral and self.neutral_seen and "stop" not in self.buttons:
                    self.armed = True
                    self.reason = "enabled"
                elif action == "slower":
                    self.level = max(0, self.level - 1)
                elif action == "faster":
                    self.level = min(len(self.settings.speeds) - 1, self.level + 1)
            self.actions.clear()

    def output(self):
        if not self.connected or self.dropped or not self.armed or "enable" not in self.buttons:
            return (0, 0)
        speed = self.settings.speeds[self.level]
        if self.y:
            left = right = -self.y * (self.settings.diagonal_outer if self.x else speed)
            if self.x < 0:
                left = round(left * self.settings.inner_ratio)
            elif self.x > 0:
                right = round(right * self.settings.inner_ratio)
            return left, right
        spin = min(speed, self.settings.spin_limit)
        return self.x * spin, -self.x * spin
