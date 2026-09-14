"""Optional python-evdev adapter. No input device or serial access at import."""
import select


class EvdevSource:
    def __init__(self, mapping=None, name="Microsoft X-Box 360 pad", vendor=None,
                 product=None, path=None, diagnostic=False):
        self.mapping = mapping or {}
        self.name, self.vendor, self.product, self.path = name, vendor, product, path
        self.diagnostic = diagnostic
        self.device = None

    def connect(self, controller):
        import evdev
        candidates = []
        try:
            for path in ([self.path] if self.path else evdev.list_devices()):
                dev = evdev.InputDevice(path)
                axes = dev.capabilities().get(evdev.ecodes.EV_ABS, [])
                axes = {a[0] if isinstance(a, tuple) else a for a in axes}
                if (dev.name == self.name and {16, 17} <= axes
                        and (self.vendor is None or dev.info.vendor == self.vendor)
                        and (self.product is None or dev.info.product == self.product)):
                    candidates.append(dev)
                else:
                    dev.close()
            if len(candidates) != 1:
                raise OSError("Expected one gamepad; candidates=" + str([
                    (d.path, d.name, d.info.vendor, d.info.product, d.phys) for d in candidates]))
            self.device = candidates.pop()
            if not self.diagnostic:
                supported = set(self.device.capabilities().get(evdev.ecodes.EV_KEY, []))
                if not set(self.mapping.values()) <= supported:
                    self.close()
                    raise ValueError("Configured buttons not supported by selected device")
            self.resync(controller)
        finally:
            for dev in candidates:
                dev.close()

    def resync(self, controller):
        keys = set(self.device.active_keys())
        controller.resync(self.device.absinfo(16).value, self.device.absinfo(17).value,
                          [name for name, code in self.mapping.items() if code in keys])

    def poll(self, controller, timeout):
        poller = select.poll()
        poller.register(self.device.fd, select.POLLIN | select.POLLERR | select.POLLHUP)
        for _, flags in poller.poll(round(timeout * 1000)):
            if flags & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                raise OSError("gamepad hangup")
            try:
                events = list(self.device.read())
            except BlockingIOError:
                return
            if not events:
                raise OSError("gamepad EOF")
            for event in events:
                if self.diagnostic:
                    print(f"type={event.type} code={event.code} value={event.value}", flush=True)
                if event.type == 0 and event.code == 3:
                    controller.event("dropped")
                elif event.type == 0 and event.code == 0:
                    if controller.dropped:
                        self.resync(controller)
                        # ioctl is newer than this read batch; discard queued stale events.
                        return
                    else:
                        controller.event("report")
                elif event.type == 3 and event.code in (16, 17):
                    controller.event("axis", "x" if event.code == 16 else "y", event.value)
                elif event.type == 1:
                    for name, code in self.mapping.items():
                        if code == event.code:
                            controller.event("button", name, event.value)

    def close(self):
        if self.device:
            self.device.close()
            self.device = None
