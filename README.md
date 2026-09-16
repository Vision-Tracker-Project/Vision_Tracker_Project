# Vision Tracking

## 프로젝트 소개

선택한 인물을 카메라가 자동으로 추적하고, 차량을 수동으로 제어하여 위치를 이동할 수 있는 Vision Tracking 프로젝트입니다.

![Vision Tracking 프로젝트 실물](docs/images/presentation/slide-04.png)

## 팀 소개 — 수화

저희 팀은 처음에는 MediaPipe를 활용한 **수화 인식 프로젝트**를 기획했습니다. 손의 랜드마크를 인식하고, 이를 Ollama와 연계해 수화를 해석하는 방향이었습니다.

기획 과정에서 AI 디바이스의 인식 결과를 실제 하드웨어의 움직임으로 연결하는 시스템을 만들어 보자는 의견이 나왔습니다. 당시 팀원 모두 카메라 기반 객체 추적 시스템을 깊게 다뤄 본 경험이 없었기에, 새로운 분야에 직접 도전하자는 의미로 프로젝트 주제를 변경했습니다.

![수화 인식 기획과 프로젝트 주제 전환](docs/images/presentation/slide-05.png)

![팀원 및 역할 분담](docs/images/presentation/slide-03.png)

## Why this Project?

출입 시스템처럼 고정된 카메라를 활용한 인식 시스템은 비교적 쉽게 접할 수 있지만, 움직이는 대상을 인식하고 카메라가 그 대상을 따라 움직이는 시스템을 직접 다뤄 볼 기회는 많지 않았습니다.

인식한 대상을 계속해서 따라가는 프로젝트를 진행하며 객체 추적과 카메라 제어의 원리를 배우고, 실제 하드웨어에 적용해 보고자 했습니다.

![객체 추적과 카메라 제어 프로젝트의 기획 배경](docs/images/presentation/slide-06.png)

## 프로젝트 목표

![프로젝트 목표와 구현 범위](docs/images/presentation/slide-07.png)

## 시스템 구성

![전체 시스템 처리 흐름도](docs/images/presentation/slide-08.png)

![실물 하드웨어 구성](docs/images/presentation/slide-09.png)

![시스템 아키텍처](docs/images/presentation/slide-10.png)

![시스템 블록 다이어그램](docs/images/presentation/slide-11.png)

## 하드웨어

![주요 부품 목록](docs/images/presentation/slide-13.png)

![STM32 핀맵](docs/images/presentation/slide-15.png)

![회로 구성](docs/images/presentation/slide-16.png)

## AI 인물 추적

![AI 모델과 알고리즘의 역할](docs/images/presentation/slide-17.png)

![인물 추적 상태 머신](docs/images/presentation/slide-12.png)

![최신 프레임 처리 구조](docs/images/presentation/slide-18.png)

![최근 세 박스의 중앙값 필터링](docs/images/presentation/slide-19.png)

![OSNet 특징 저장 및 재연결 조건](docs/images/presentation/slide-20.png)

## 팬틸트 및 차량 제어

![팬틸트 이중 경계 제어](docs/images/presentation/slide-21.png)

![evdev 게임패드 입력 동기화](docs/images/presentation/slide-22.png)

![좌우 바퀴 출력과 속도 매핑](docs/images/presentation/slide-23.png)

## UART 통신

![UART 패킷 구조와 무결성 검증](docs/images/presentation/slide-24.png)

## 트러블슈팅 및 구현 결과

![구동부와 웹 영상 지연 문제 해결](docs/images/presentation/slide-25.png)

![AI 추론 지연과 인물 ID 변경 문제 해결](docs/images/presentation/slide-26.png)

## 향후 과제

![향후 연구 과제](docs/images/presentation/slide-27.png)

## 시연영상

약 51초 분량의 실제 동작 영상입니다. 아래 이미지를 클릭하면 영상을 열 수 있습니다.

[![Vision Tracking 실제 동작 시연영상](docs/images/demo-preview.jpg)](https://raw.githubusercontent.com/Vision-Tracker-Project/Vision_Tracker_Project/main/docs/videos/vision-tracking-demo.mp4)

[▶ 시연영상 재생](https://raw.githubusercontent.com/Vision-Tracker-Project/Vision_Tracker_Project/main/docs/videos/vision-tracking-demo.mp4) · [MP4 원본 파일](docs/videos/vision-tracking-demo.mp4)
