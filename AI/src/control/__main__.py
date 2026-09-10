"""python -m src.control defaults to dry-run. Buttons must be measured."""
import argparse
import json
import logging
import signal

from src.control.device import EvdevSource
from src.control.service import ControlService
from src.control.state import Controller, Settings


def create_service(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uart", help="Explicit opt-in UART path; omitted = dry-run")
    parser.add_argument("--gamepad", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--config", help="JSON settings and measured button codes")
    parser.add_argument("--device", help="Explicit disambiguation path, never a default event number")
    args = parser.parse_args(argv)
    config = {}
    if args.config:
        with open(args.config, encoding="utf-8") as stream:
            config = json.load(stream)
    mapping = config.get("buttons", {})
    if mapping and (set(mapping) != {"enable", "stop", "slower", "faster"}
                    or any(type(v) is not int or v < 0 for v in mapping.values())
                    or len(set(mapping.values())) != 4):
        parser.error("buttons requires four distinct measured numeric codes")
    if args.uart and args.diagnose:
        parser.error("diagnosis cannot open UART")
    if args.uart and args.gamepad and not mapping:
        parser.error("real driving requires measured --config button mapping")
    source = None
    if args.gamepad or args.diagnose:
        source = EvdevSource(mapping, path=args.device, diagnostic=args.diagnose,
                             **config.get("device", {}))
    return ControlService(source, Controller(Settings(**config.get("settings", {}))), args.uart)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    service = create_service()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: service.stop())
    service.run()


if __name__ == "__main__":
    main()
