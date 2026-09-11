# BoT-SORT + OSNet x0.25 TensorRT ReID

YOLO TensorRT 검출 결과를 BoT-SORT가 짧게 이어가고, 사용자가 선택한 사람이
화면에서 사라진 경우 OSNet x0.25 TensorRT 임베딩으로 다시 찾습니다.
BoT-SORT 내부 ReID는 끄고 OSNet만 장기 재식별에 사용합니다.

- 엔진: `models/osnet_x0_25.engine` (TensorRT FP16, 입력 1×3×256×128, 출력 512D)
- 추출 주기: 선택 대상을 추적하거나 잃어버린 후보를 비교할 때 0.5초 간격
- 갤러리: 정규화된 특징 최대 10개, 이미지 저장 없음
- 재연결: 코사인 유사도 0.85 이상, 차순위보다 0.06 이상 높고 2회 연속 일치
- 유효 시간: 대상 유실 후 60초

ONNX CPU 또는 다른 OSNet 모델로 자동 폴백하지 않습니다. 엔진 누락이나 형식
불일치는 시작 오류로 처리합니다. 임계값은 `VISION_REID_THRESHOLD`, 유효 시간은
`VISION_REID_TIMEOUT` 환경 변수로 조정할 수 있습니다.
