# BoT-SORT + OSNet x0.25 TensorRT ReID

YOLO TensorRT 검출 결과를 BoT-SORT가 칼만 필터와 내부 외형 ReID(색상·질감)로
짧게 이어가고, 사용자가 선택한 사람이 BoT-SORT 버퍼를 벗어난 경우에만 OSNet
x0.25 TensorRT 임베딩으로 다시 찾습니다.

BoT-SORT 원본 ID와 외부에 표시하는 영구 ID는 분리합니다. OSNet이 장기 재연결을
확정하면 새 BoT-SORT ID를 기존 영구 ID에 일대일로 재바인딩합니다. 새 트랙에 이미
발급됐던 영구 ID는 재사용하지 않으므로 한 프레임에 같은 ID가 중복 표시되지 않습니다.

선택한 BoT-SORT ID가 계속 보이더라도 OSNet 유사도를 주기적으로 검증합니다. 유사도가
기본 0.75 미만으로 2회 연속 떨어지면 해당 Crop은 갤러리에 저장하지 않고 모든 사람을
다시 비교합니다. 다른 BoT-SORT ID가 기존 갤러리와 임계값·차순위 마진을 모두 만족하면
영구 ID를 그 사람에게 옮겨 ID 교환을 자동 교정합니다. 일치 후보가 없으면 잘못된 사람을
따라가지 않도록 팬틸트 추적을 멈추고 재검색합니다.

- 엔진: `models/osnet_x0_25.engine` (TensorRT FP16, 입력 1×3×256×128, 출력 512D)
- 추출 주기: 선택 대상을 추적하거나 잃어버린 후보를 비교할 때 0.5초 간격
- 역할 전환: BoT-SORT ID 유실 후 기본 1초 동안은 단기 재연결을 기다린 뒤 OSNet 검색
- 갤러리: 정규화된 특징 최대 10개, 이미지 저장 없음
- 재연결: 코사인 유사도 0.85 이상, 차순위보다 0.06 이상 높고 2회 연속 일치
- 유효 시간: 대상 유실 후 60초

ONNX CPU 또는 다른 OSNet 모델로 자동 폴백하지 않습니다. 엔진 누락이나 형식
불일치는 시작 오류로 처리합니다. 임계값은 `VISION_REID_THRESHOLD`, 유효 시간은
`VISION_REID_TIMEOUT`, 역할 전환 지연은 `VISION_REID_LONG_TERM_DELAY` 환경 변수로
조정할 수 있습니다. 실시간 ID 검증 임계값과 연속 횟수는 각각
`VISION_REID_GUARD_THRESHOLD`, `VISION_REID_MISMATCH_SAMPLES`로 조정합니다.
