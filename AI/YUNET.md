# YuNet 얼굴 검출

## 역할

YuNet은 프레임에서 얼굴 위치를 찾는 경량 검출 모델임. 얼굴 신원 판단은 수행하지 않음.

```text
카메라 BGR 프레임
    ↓
YuNet 얼굴 검출
    ↓
얼굴 박스 + 5개 랜드마크 + 신뢰도
```

## 출력

얼굴 한 건마다 15개 값 반환.

| 범위 | 내용 |
|---|---|
| `0–3` | 얼굴 박스 `x, y, width, height` |
| `4–13` | 두 눈, 코, 양쪽 입꼬리 좌표 |
| `14` | 얼굴 검출 신뢰도 |

원본 15개 값은 `FaceDetection.raw`에 보존. SFace 정렬 단계에서는 신뢰도를 제외한 앞 14개 값 사용.

## 설정

`src/config.py`에서 관리.

- 모델: `models/face_detection_yunet_2023mar.onnx`
- 신뢰도 임계값: `0.8`
- NMS 임계값: `0.3`
- NMS 전 후보 수: `5000`

신뢰도 임계값을 낮추면 검출 수와 오검출 가능성이 함께 증가. NMS는 겹치는 박스 중 신뢰도가 높은 결과를 유지.

## 코드 위치

- `src/detection/yunet_detector.py`: 모델 로드, 검출 결과 변환, 시각화 담당
- `src/workers/video_worker.py`: 최신 카메라 프레임에 검출 실행
- `src/ui/main_window.py`: 검출 영상과 얼굴 수 표시

공식 자료 확인 가능.

- [OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [YuNet ONNX 모델](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx)
