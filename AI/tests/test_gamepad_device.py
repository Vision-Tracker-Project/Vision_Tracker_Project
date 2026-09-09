"""Linux adapter tests with injected evdev and poll, including on Windows."""
import select
import types
import unittest
from unittest.mock import patch

from src.control.device import EvdevSource
from src.control.state import Controller


class Device:
    name = "Microsoft X-Box 360 pad"
    info = types.SimpleNamespace(vendor=123, product=456)
    phys = "fake USB"
    fd = 7

    def __init__(self, path):
        self.path=path; self.closed=False; self.events=[]
        self.axes={16:0,17:0}; self.keys=[]

    def capabilities(self): return {3:[(16,None),(17,None)],1:[10,11,12,13]}
    def absinfo(self,code): return types.SimpleNamespace(value=self.axes[code])
    def active_keys(self): return self.keys
    def read(self): return self.events
    def close(self): self.closed=True


class DeviceTest(unittest.TestCase):
    def setUp(self):
        self.devices={path:Device(path) for path in ("event11","event42")}
        self.evdev=types.SimpleNamespace(list_devices=lambda:list(self.devices),
                                        InputDevice=lambda path:self.devices[path],
                                        ecodes=types.SimpleNamespace(EV_ABS=3,EV_KEY=1))
        self.patch=patch.dict("sys.modules",evdev=self.evdev); self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_ambiguous_refuses_and_closes_all_candidates(self):
        with self.assertRaisesRegex(OSError,"Expected one"):
            EvdevSource().connect(Controller())
        self.assertTrue(all(d.closed for d in self.devices.values()))

    def test_explicit_path_and_identity_filter(self):
        source=EvdevSource(path="event42",vendor=123,product=456)
        c=Controller(); source.connect(c)
        self.assertEqual(source.device.path,"event42")
        self.assertTrue(c.connected)
        source.close(); self.assertTrue(self.devices["event42"].closed)
        with self.assertRaises(OSError): EvdevSource(vendor=999).connect(c)

    def test_missing_buttons_refused(self):
        with self.assertRaises(ValueError):
            EvdevSource({"enable":999},path="event11").connect(Controller())
        self.assertTrue(self.devices["event11"].closed)

    def poll(self,source,c,flags):
        fake=types.SimpleNamespace(register=lambda *_:None,poll=lambda _:[(7,flags)])
        # select.poll is absent on Windows, so inject its constants as well.
        with patch.multiple(select,create=True,poll=lambda:fake,POLLIN=1,POLLERR=8,POLLHUP=16,POLLNVAL=32):
            source.poll(c,0)

    def test_hangup_and_empty_read(self):
        source=EvdevSource(path="event11"); c=Controller(); source.connect(c)
        for flags in (16,8,32,1):
            with self.assertRaises(OSError): self.poll(source,c,flags)

    def test_dropped_resync_ignores_stale_batch(self):
        source=EvdevSource({"enable":10},path="event11"); c=Controller(); source.connect(c)
        event=lambda t,k,v:types.SimpleNamespace(type=t,code=k,value=v)
        source.device.events=[event(0,3,0),event(3,17,-1),event(0,0,0),
                              event(1,10,1),event(0,0,0),event(3,17,-1),event(0,0,0)]
        self.poll(source,c,1)
        self.assertFalse(c.armed)
        self.assertFalse(c.dropped)
        self.assertEqual(c.output(),(0,0))
        self.assertEqual(c.y,0)
