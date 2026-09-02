# YuNet 얼굴 검출

## YuNet이 하는 일

YuNet은 영상에서 얼굴의 위치를 찾는 경량 얼굴 검출 모델이다. 현재 단계에서는 OpenCV의 `FaceDetectorYN` API와 공식 ONNX 모델을 사용한다. 얼굴이 누구인지는 판단하지 않으며, 그 작업은 다음 단계의 SFace가 담당한다.

```text
카메라 BGR 프레임
    ↓
YuNet 입력 크기를 현재 프레임 크기로 설정
    ↓
FaceDetectorYN.detect()
    ↓
얼굴 박스 + 5개 랜드마크 + 신뢰도
    ↓
화면에 검출 결과 표시
```

## 검출 결과

YuNet은 얼굴마다 15개 값을 반환한다.

| 범위 | 내용 |
|---|---|
| `0–3` | 얼굴 박스 `x, y, width, height` |
| `4–13` | 오른쪽 눈, 왼쪽 눈, 코, 오른쪽 입꼬리, 왼쪽 입꼬리 좌표 |
| `14` | 얼굴 검출 신뢰도 |

현재 `FaceDetection.raw`에 15개 원본 값을 보존한다. 다음 SFace 단계에서 얼굴 정렬에 이 값을 사용할 수 있다.

## 설정값

설정은 `src/config.py`에 있다.

- 모델: `models/face_detection_yunet_2023mar.onnx`
- 신뢰도 임계값: `0.8`
- NMS 임계값: `0.3`
- NMS 전 후보 수: `5000`

신뢰도 임계값을 낮추면 더 많은 얼굴을 찾지만 오검출도 늘어날 수 있다. NMS는 겹치는 얼굴 박스 중 신뢰도가 높은 박스를 남긴다.

## 현재 코드 위치

- `src/detection/yunet_detector.py`: 모델 초기화, 검출 결과 변환, 박스 표시
- `src/workers/video_worker.py`: 카메라 프레임에 YuNet 실행
- `src/ui/main_window.py`: 검출 영상과 얼굴 수 표시

공식 자료:

- [OpenCV Zoo YuNet 설명](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [OpenCV 공식 YuNet 모델](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx)
