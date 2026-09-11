"""One control loop owns UART; camera can only submit latest servo packets."""
import logging
import threading
import time

from src.communication.uart_sender import UartSender
from src.communication.protocol import build_servo_packet
from src.communication.vehicle_protocol import build_vehicle_packet
from src.config import PAN_INITIAL_ANGLE, PAN_TARGET_ID, TILT_INITIAL_ANGLE, TILT_TARGET_ID
from src.control.state import Controller

LOG = logging.getLogger(__name__)


class ServoMailbox:
    def __init__(self, service):
        self.service = service
        self.port = service.port or "dry-run"
        self.baud_rate = 115200

    @property
    def is_open(self):
        # The video worker writes to this in-memory mailbox, not to the serial
        # device. Keep accepting the latest servo target while UART reconnects;
        # the control loop will transmit it after the port is available again.
        return not self.service.stopping.is_set()

    def open(self):
        pass

    def send(self, packets):
        packets = tuple(packets)
        with self.service.lock:
            self.service.servo = packets
        return sum(len(p.data) for p in packets)

    def close(self):
        with self.service.lock:
            self.service.servo = ()


class ControlService:
    def __init__(self, source=None, controller=None, port=None, sender=None,
                 clock=time.monotonic, period=0.05):
        if not 0.01 <= period <= 0.1:
            raise ValueError("Control period must be 10..100 ms")
        self.source, self.controller, self.port = source, controller or Controller(), port
        self.sender = sender if sender is not None else (
            UartSender(port, write_timeout=0.05, flush_after_write=False) if port else None)
        self.clock, self.period = clock, period
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.servo = ()
        self.retry_uart = self.retry_input = 0
        self.last_input_error = None
        self.last_input_error_log = 0
        self.thread = None
        self.last_tick = None
        self.last_log_state = None
        self.mailbox = ServoMailbox(self)

    def status(self):
        """웹 표시용 게임패드와 실제 차량 출력의 최신 상태."""
        controller = self.controller
        left, right = controller.output()
        directions = {
            (0, 0): "정지", (0, -1): "전진", (0, 1): "후진",
            (-1, 0): "좌회전", (1, 0): "우회전",
            (-1, -1): "좌전진", (1, -1): "우전진",
            (-1, 1): "좌후진", (1, 1): "우후진",
        }
        return {
            "connected": controller.connected,
            "armed": controller.armed and "enable" in controller.buttons,
            "x": controller.x,
            "y": controller.y,
            "direction": directions.get((controller.x, controller.y), "알 수 없음"),
            "left_motor": left,
            "right_motor": right,
            "speed_level": controller.level + 1,
            "speed_level_count": len(controller.settings.speeds),
            "speed": controller.settings.speeds[controller.level],
            "enable_pressed": "enable" in controller.buttons,
            "stop_pressed": "stop" in controller.buttons,
            "reason": controller.reason,
        }

    def transmit(self, pair):
        packet = build_vehicle_packet(*pair)
        reason = (("direction neutral" if self.controller.armed and not any(pair)
                   else self.controller.reason) if pair == (0, 0) else "drive")
        log_state = (self.controller.x, self.controller.y, pair, reason)
        if log_state != self.last_log_state:
            LOG.info("axes=(%s,%s) wheels=%s packet=%s reason=%s",
                     self.controller.x, self.controller.y, pair,
                     packet.hex_string, reason)
            self.last_log_state = log_state
        else:
            LOG.debug("vehicle heartbeat packet=%s", packet.hex_string)
        if self.sender:
            self.sender.send((packet,))

    def initialize_servos(self):
        packets = (
            build_servo_packet(PAN_TARGET_ID, PAN_INITIAL_ANGLE),
            build_servo_packet(TILT_TARGET_ID, TILT_INITIAL_ANGLE),
        )
        self.sender.send(packets)
        LOG.info(
            "servo initialized pan=%d tilt=%d packets=%s / %s",
            PAN_INITIAL_ANGLE,
            TILT_INITIAL_ANGLE,
            packets[0].hex_string,
            packets[1].hex_string,
        )

    def tick(self):
        now = self.clock()
        if self.last_tick is not None and now - self.last_tick > 0.15:
            self.controller.stop("control loop deadline missed")
        self.last_tick = now
        if self.sender and not self.sender.is_open:
            self.controller.stop("UART reconnect: fresh enable required")
            if now < self.retry_uart:
                return
            self.retry_uart = now + 1
            self.sender.open()
            self.transmit((0, 0))
            self.initialize_servos()
            return
        self.transmit(self.controller.output())
        with self.lock:
            servo, self.servo = self.servo, ()
        if self.sender and servo:
            self.sender.send(servo)
            LOG.info("servo tx %s", " / ".join(packet.hex_string for packet in servo))

    def run(self):
        try:
            while not self.stopping.is_set():
                start = self.clock()
                if self.source:
                    try:
                        if not self.controller.connected and start >= self.retry_input:
                            self.source.connect(self.controller)
                            self.last_input_error = None
                        if self.controller.connected:
                            self.source.poll(self.controller, 0)
                    except OSError as error:
                        message = str(error)
                        if (message != self.last_input_error
                                or start - self.last_input_error_log >= 30):
                            LOG.warning("input: %s", error)
                            self.last_input_error = message
                            self.last_input_error_log = start
                        self.controller.disconnect()
                        self.source.close()
                        self.retry_input = start + 1
                try:
                    self.tick()
                except Exception as error:
                    LOG.error("UART: %s", error)
                    self.controller.stop("UART error")
                    if self.sender:
                        self.sender.close()
                self.stopping.wait(max(0, self.period - (self.clock() - start)))
        except Exception:
            LOG.exception("control loop error")
            raise
        finally:
            self.stopping.set()
            self.controller.stop("shutdown/error")
            try:
                if not self.sender or self.sender.is_open:
                    self.transmit((0, 0))
            finally:
                if self.sender:
                    self.sender.close()
                if self.source:
                    self.source.close()

    def start(self):
        self.thread = threading.Thread(target=self.run, name="vehicle-control", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(1)
