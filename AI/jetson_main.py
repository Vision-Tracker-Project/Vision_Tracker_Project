"""이전 실행 명령 호환용. 새 실행 진입점은 run_jetson.py이다."""

from run_jetson import main


if __name__ == "__main__":
    raise SystemExit(main())
