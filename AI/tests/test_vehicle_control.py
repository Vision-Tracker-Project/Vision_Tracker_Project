import ctypes as C
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.control.state import Controller, Settings
from src.control.service import ControlService
from src.communication.vehicle_protocol import build_vehicle_packet
from src.communication.protocol import build_servo_packet
from src.communication.uart_sender import UartSender
from tests.test_uart_protocol import FakeSerial


def button(c, name, value=1):
    c.event("button", name, value)
    c.event("report")


def axes(c, x, y):
    c.event("axis", "x", x)
    c.event("axis", "y", y)
    c.event("report")


def enabled():
    c = Controller(Settings(speeds=(40, 60, 100), spin_limit=30, inner_ratio=0.5, diagonal_outer=40))
    c.resync(0, 0)
    button(c, "enable")
    return c


class InputTest(unittest.TestCase):
    def test_default_vehicle_pwm_table(self):
        expected = {(0,-1):(80,80), (0,1):(-80,-80), (-1,0):(-80,80),
                    (1,0):(80,-80), (-1,-1):(80,100), (1,-1):(100,80),
                    (-1,1):(-80,-100), (1,1):(-100,-80), (0,0):(0,0)}
        c = Controller()
        c.resync(0, 0)
        button(c, "enable")
        for xy, pair in expected.items():
            with self.subTest(xy=xy):
                axes(c, *xy)
                self.assertEqual(c.output(), pair)
        button(c, "faster")
        axes(c, 0, -1)
        self.assertEqual(c.output(), (90,90))
        axes(c, -1, -1)
        self.assertEqual(c.output(), (80,100))
        axes(c, -1, 0)
        self.assertEqual(c.output(), (-80,80))
        c.event("button", "enable", 0)
        self.assertEqual(c.output(), (0,0))

    def test_eight_directions_and_neutral(self):
        expected = {(0,-1):(40,40), (0,1):(-40,-40), (-1,0):(-30,30),
                    (1,0):(30,-30), (-1,-1):(20,40), (1,-1):(40,20),
                    (-1,1):(-20,-40), (1,1):(-40,-20), (0,0):(0,0)}
        for xy, pair in expected.items():
            c = enabled(); axes(c, *xy)
            self.assertEqual(c.output(), pair)

    def test_report_atomic_and_no_events_maintains_hold(self):
        c = enabled()
        c.event("axis", "x", -1)
        self.assertEqual(c.output(), (0,0))
        c.event("axis", "y", -1)
        c.event("report")
        for _ in range(100):
            self.assertEqual(c.output(), (20,40))
        c.event("axis", "x", 0); c.event("report")
        self.assertEqual(c.output(), (40,40))
        axes(c, 0, 0); self.assertEqual(c.output(), (0,0))

    def test_speed_bounds_and_repeat(self):
        c = enabled(); axes(c,0,-1)
        for _ in range(10):
            button(c,"faster"); button(c,"faster",0)
        self.assertEqual(c.output(), (100,100))
        button(c,"slower")
        button(c,"slower",2)
        self.assertEqual(c.output(), (60,60))
        for _ in range(10):
            button(c,"slower",0); button(c,"slower")
        self.assertEqual(c.output(), (40,40))

    def test_release_is_immediate_and_requires_neutral(self):
        c=enabled(); axes(c,0,-1)
        c.event("button","enable",0)
        self.assertEqual(c.output(),(0,0))
        button(c,"enable"); self.assertEqual(c.output(),(0,0))
        button(c,"enable",0); axes(c,0,0); button(c,"enable"); axes(c,0,-1)
        self.assertEqual(c.output(),(40,40))

    def test_stop_lock_and_fresh_enable(self):
        c=enabled(); axes(c,0,-1); button(c,"stop")
        axes(c,0,0); button(c,"stop",0); axes(c,0,-1)
        self.assertEqual(c.output(),(0,0))
        button(c,"enable",0); axes(c,0,0); button(c,"enable"); axes(c,0,-1)
        self.assertEqual(c.output(),(40,40))

    def test_disconnect_reconnect_and_dropped(self):
        for cause in ("disconnect", "dropped"):
            c=enabled(); axes(c,0,-1)
            c.disconnect() if cause == "disconnect" else c.event("dropped")
            self.assertEqual(c.output(),(0,0))
            c.resync(0,-1,["enable"])
            axes(c,0,0); axes(c,0,-1)
            self.assertEqual(c.output(),(0,0))
            button(c,"enable",0); axes(c,0,0); button(c,"enable"); axes(c,0,-1)
            self.assertEqual(c.output(),(40,40))

    def test_invalid_config_and_axis(self):
        for kwargs in ({"speeds":(101,)},{"inner_ratio":2},{"initial":9}):
            with self.assertRaises(ValueError): Settings(**kwargs)
        c=enabled(); c.event("axis","x",5)
        self.assertEqual(c.output(),(0,0))

    def test_dry_run_never_opens_serial(self):
        with patch("src.communication.uart_sender.serial") as serial:
            service=ControlService(controller=enabled())
            service.tick(); service.stop(); service.run()
            serial.Serial.assert_not_called()

    def test_uart_reconnect_discards_motion_and_serializes_servo(self):
        fake=FakeSerial()
        sender=UartSender("fake",serial_factory=lambda **_:fake)
        c=enabled(); axes(c,0,-1)
        service=ControlService(controller=c,sender=sender,clock=lambda:2)
        service.tick()
        self.assertEqual(bytes(fake.written),build_vehicle_packet(0,0).data)
        service.mailbox.send((build_servo_packet(1,90),))
        service.tick()
        self.assertEqual(bytes(fake.written[-6:]),build_servo_packet(1,90).data)
        self.assertEqual(c.output(),(0,0))

    def test_exception_and_shutdown_send_zero(self):
        fake=FakeSerial(); sender=UartSender("fake",serial_factory=lambda **_:fake); sender.open()
        c=enabled(); axes(c,0,-1)
        class BrokenSource:
            def poll(self,*_): raise ValueError("injected")
            def close(self): pass
        service=ControlService(BrokenSource(),c,sender=sender)
        with self.assertLogs("src.control.service",level="ERROR"):
            with self.assertRaises(ValueError): service.run()
        self.assertEqual(bytes(fake.written),build_vehicle_packet(0,0).data)
        self.assertFalse(fake.is_open)

    def test_control_stall_stops_but_camera_stop_is_independent(self):
        c=enabled(); axes(c,0,-1)
        now=[0.0]; service=ControlService(controller=c,clock=lambda:now[0])
        service.tick(); now[0]=0.2; service.tick()
        self.assertEqual(c.output(),(0,0))
        c=enabled(); axes(c,0,-1); service.controller=c
        service.mailbox.close(); service.tick()
        self.assertEqual(c.output(),(40,40))

    def test_servo_mailbox_does_not_write_uart_from_camera_thread(self):
        fake=FakeSerial(); sender=UartSender("fake",serial_factory=lambda **_:fake); sender.open()
        service=ControlService(controller=enabled(),sender=sender)
        packet=build_servo_packet(1,90)
        service.mailbox.send((packet,))
        self.assertEqual(bytes(fake.written),b"")
        service.tick()
        self.assertTrue(bytes(fake.written).endswith(packet.data))

    def test_servo_mailbox_accepts_latest_target_while_uart_reconnects(self):
        fake=FakeSerial()
        sender=UartSender("fake",serial_factory=lambda **_:fake)
        service=ControlService(controller=enabled(),sender=sender,clock=lambda:2)
        packet=build_servo_packet(1,95)
        self.assertFalse(sender.is_open)
        self.assertTrue(service.mailbox.is_open)
        service.mailbox.send((packet,))
        service.tick()
        service.tick()
        self.assertTrue(bytes(fake.written).endswith(packet.data))

    def test_uart_failure_loop_closes_and_does_not_replay(self):
        c=enabled(); axes(c,0,-1)
        fake=FakeSerial()
        sender=UartSender("fake",serial_factory=lambda **_:fake); sender.open()
        service=ControlService(controller=c,sender=sender)
        def broken_write(data):
            service.stopping.set()
            raise OSError("injected write error")
        fake.write=broken_write
        with self.assertLogs("src.control.service",level="ERROR"): service.run()
        self.assertEqual(c.output(),(0,0))
        self.assertFalse(fake.is_open)

    def test_cli_default_and_explicit_uart_selection(self):
        from src.control.__main__ import create_service
        self.assertIsNone(create_service([]).sender)
        self.assertIsNone(create_service(["--gamepad", "--device", "auto"]).source.path)
        with patch("src.communication.uart_sender.serial") as serial:
            self.assertIsNotNone(create_service(["--uart","fake"]).sender)
            serial.Serial.assert_not_called()


class Vehicle(C.Structure):
    _fields_=[("target",C.c_int*2),("output",C.c_int*2),("last_sign",C.c_int*2),
              ("zero_since",C.c_uint32*2),("updated",C.c_uint32),("tick",C.c_uint32),
              ("credit",C.c_uint),("valid",C.c_int)]


class Parser(C.Structure):
    _fields_=[("bytes",C.c_uint8*8),("count",C.c_uint)]


class FirmwareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gcc=shutil.which("gcc")
        if not gcc: raise unittest.SkipTest("host gcc missing")
        cls.temp=tempfile.TemporaryDirectory()
        root=pathlib.Path(__file__).resolve().parents[2]/"STM32"
        lib=pathlib.Path(cls.temp.name)/"vehicle.dll"
        subprocess.run([gcc,"-shared","-std=c99","-Wall","-Wextra","-Werror","-O2",
                        "-fPIC",str(root/"vehicle.c"),"-o",str(lib)],check=True,timeout=30,
                       env={**os.environ,"PATH":str(pathlib.Path(gcc).parent)+os.pathsep+os.environ.get("PATH","")})
        cls.lib=C.CDLL(str(lib))
        cls.callback=C.CFUNCTYPE(None,C.c_uint,C.c_uint)
        cls.lib.Vehicle_Init.argtypes=[C.POINTER(Vehicle),C.c_uint32]
        cls.lib.Vehicle_Tick.argtypes=[C.POINTER(Vehicle),C.c_uint32]
        cls.lib.Vehicle_Command.argtypes=[C.POINTER(Vehicle),C.c_int,C.c_int,C.c_uint32]
        cls.lib.Packet_Feed.argtypes=[C.POINTER(Parser),C.POINTER(Vehicle),C.c_uint8,C.c_uint32,cls.callback]

    @classmethod
    def tearDownClass(cls):
        # Windows keeps loaded DLL files locked until FreeLibrary.
        if hasattr(C,"windll"): C.windll.kernel32.FreeLibrary(C.c_void_p(cls.lib._handle))
        cls.temp.cleanup()

    def setUp(self):
        self.v=Vehicle(); self.p=Parser(); self.servo=[]
        self.cb=self.callback(lambda t,a:self.servo.append((t,a)))
        self.lib.Vehicle_Init(C.byref(self.v),0)

    def feed(self,data,now=0):
        for b in data: self.lib.Packet_Feed(C.byref(self.p),C.byref(self.v),b,now,self.cb)

    def tick(self,now): self.lib.Vehicle_Tick(C.byref(self.v),now)

    def test_signed_serialization_split_atomic_and_consecutive(self):
        for left in (-100,-1,0,1,100):
            packet=build_vehicle_packet(left,-left).data
            old=tuple(self.v.target)
            self.feed(packet[:-1])
            self.assertEqual(tuple(self.v.target), old)
            self.feed(packet[-1:])
            self.assertEqual(tuple(self.v.target),(left,-left))
            self.assertEqual(len(packet),8)
        self.feed(build_vehicle_packet(30,60).data+build_vehicle_packet(-10,-20).data)
        self.assertEqual(tuple(self.v.target),(-10,-20))

    def test_noise_crc_length_range_and_resync(self):
        packet=build_vehicle_packet(45,-45).data
        bad=bytearray(packet); bad[6]^=1
        self.feed(b"noise\xaa\x10"+bad+packet,10)
        self.assertEqual(tuple(self.v.target),(45,-45))
        self.feed(bad,100)
        self.assertEqual(self.v.updated,10)
        from src.communication.vehicle_protocol import crc8
        for index,value in ((2,3),(3,3),(4,101),(5,155)):
            invalid=bytearray(packet); invalid[index]=value; invalid[6]=crc8(invalid[1:6])
            self.feed(invalid,150)
            self.assertEqual(self.v.updated,10)
        with self.assertRaises(ValueError): build_vehicle_packet(101,0)

    def test_servo_never_refreshes_watchdog(self):
        self.feed(build_vehicle_packet(100,100).data)
        self.tick(20); self.assertEqual(tuple(self.v.output),(2,2))
        self.feed(build_servo_packet(1,90).data,249)
        self.assertEqual(self.servo,[(1,90)])
        self.assertEqual(self.v.updated,0)
        self.tick(250); self.assertEqual(tuple(self.v.output),(0,0))

    def test_release_immediate_and_reversal_wait(self):
        self.feed(build_vehicle_packet(100,100).data)
        for t in range(10,101,10): self.tick(t)
        self.assertEqual(tuple(self.v.output),(10,10))
        self.feed(build_vehicle_packet(-50,-50).data,100)
        self.tick(110); self.assertEqual(tuple(self.v.output),(0,0))
        self.tick(209); self.assertEqual(tuple(self.v.output),(0,0))
        self.tick(210); self.tick(220)
        self.assertLess(self.v.output[0],0)
        self.feed(build_vehicle_packet(0,0).data,221)
        self.assertEqual(tuple(self.v.output),(0,0))
        self.feed(build_vehicle_packet(50,50).data,222)
        self.tick(250); self.assertEqual(tuple(self.v.output),(0,0))

    def test_watchdog_wrap_and_stale_restart(self):
        now=0xFFFFFFF0
        self.lib.Vehicle_Init(C.byref(self.v),now)
        self.feed(build_vehicle_packet(100,100).data,now)
        self.tick(4); self.assertEqual(tuple(self.v.output),(2,2))
        self.tick(234); self.assertEqual(tuple(self.v.output),(0,0))
        self.feed(build_vehicle_packet(100,100).data,300)
        self.tick(310); self.assertLessEqual(self.v.output[0],2)


if __name__ == "__main__": unittest.main()
