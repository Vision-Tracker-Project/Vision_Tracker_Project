# SFace 얼굴 특징 추출

## 역할

SFace는 정렬된 얼굴을 128차원 특징 벡터로 변환하는 얼굴 인식 모델임. 현재 단계에서는 추출 결과 확인만 수행하며 저장·DB 연동·얼굴 비교는 수행하지 않음.

```text
YuNet 얼굴 검출 결과
    ↓
5개 랜드마크 기반 alignCrop
    ↓
SFace feature
    ↓
128차원 특징 벡터
    ↓
GUI 상태 표시 후 폐기
```

## 처리 과정

1. YuNet의 얼굴 박스와 5개 랜드마크 수신
2. `FaceRecognizerSF.alignCrop()`으로 얼굴 위치·크기·기울기 정렬
3. `FaceRecognizerSF.feature()`로 `(1, 128)` 특징 추출
4. 128차원 여부와 유한값 여부 검증
5. 벡터 차원, L2 norm, 처리 시간을 GUI에 표시
6. 다음 프레임 처리 후 기존 벡터 참조 폐기

벡터의 각 숫자는 눈·코·입처럼 개별 의미로 해석 불가. 얼굴 전체의 형태와 질감을 신경망이 압축한 값.

## 화면 표시

얼굴 검출 시 다음 형태로 표시.

```text
SFace: OK 1명 / 128D / Norm 2.34 / 6.8ms
```

- `1명`: 현재 특징을 추출한 얼굴 수
- `128D`: 특징 벡터 차원
- `Norm`: 첫 번째 얼굴 벡터의 L2 norm
- `ms`: 현재 프레임의 전체 SFace 추출 시간

## 저장 여부

이미지, 특징 벡터, 사용자 정보 모두 미저장. 파일 쓰기 및 DB 접근 코드 없음. 등록 얼굴 저장과 유사도 비교는 별도 단계로 분리 가능.

## 코드 위치

- `src/recognition/sface_extractor.py`: 얼굴 정렬과 특징 추출 담당
- `src/workers/video_worker.py`: 검출 얼굴별 특징 추출 실행
- `src/ui/main_window.py`: 추출 상태 표시

공식 자료 확인 가능.

- [OpenCV Zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
- [SFace 공식 예제](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/demo.cpp)
