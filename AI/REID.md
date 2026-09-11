# BoT-SORT + OSNet

Both YOLO .pt and direct TensorRT .engine paths use BoT-SORT with sparse optical
flow camera motion compensation. Its internal appearance encoder is disabled;
OSNet handles selected-person long-term recovery separately. The short-term
buffer is 30 tracker updates, not a guaranteed number of wall-clock seconds.

OSNet runs only after selection: one target crop every 0.5 seconds while tracked,
and visible tracked candidates every 0.5 seconds while lost. Ten normalized
512D float32 vectors are kept (20 KiB of vector storage, excluding model/runtime).
No image gallery is retained. Candidate count and inference time still affect latency.
The TensorRT FP16 engine is preferred when present; OpenCV DNN CPU runs as the ONNX fallback.

Recovery requires cosine similarity >= 0.85, a >= 0.06 lead over the runner-up,
and the same candidate passing two consecutive comparison rounds. After 60 seconds
without the target, selection and gallery expire. New selection clears the gallery.
These thresholds are initial defaults requiring scene-specific validation; clothes
and pose similarity can still produce false matches, including short-track ID swaps.

## Prepare trained weights once

Use the official torchreid repository and its **ReID-trained osnet_x0_25** checkpoint:
https://github.com/KaiyangZhou/deep-person-reid/blob/master/docs/MODEL_ZOO.md
Do not substitute ImageNet-only initialization or an arbitrary OSNet architecture.
Weights are not bundled and are not downloaded at service startup.

On a development machine with torch, torchvision, onnx and the official torchreid
package installed, export the downloaded checkpoint:

```bash
cd AI
python tools/export_osnet.py --weights /path/to/osnet_x0_25_checkpoint.pth --output models/osnet_x0_25.onnx
```

Copy the exported model to Jetson's `AI/models/osnet_x0_25.onnx`. The model contract
is fixed input 1x3x256x128, RGB ImageNet normalization, output 1x512 embedding.
The runtime needs no torchreid installation. Missing weights produce an explicit
AI startup error; there is no silent HSV fallback.

Build an FP16 engine on the target Jetson (TensorRT engines are device/version specific):

```bash
/usr/src/tensorrt/bin/trtexec --onnx=models/osnet_x0_25.onnx \
  --saveEngine=models/osnet_x0_25.engine --fp16 --skipInference
```

If `models/osnet_x0_25.engine` exists it is selected automatically. Set
`VISION_REID_MODEL` only when an explicit engine or ONNX path is required.

Environment overrides: `VISION_REID_MODEL` (absolute TensorRT engine or ONNX path),
`VISION_REID_TIMEOUT` (seconds), `VISION_REID_THRESHOLD` (cosine threshold).
For autostart, set overrides in the service environment, not just an interactive shell.
Once the model is installed, restart the existing vision-tracker-web service.

Validate on Jetson by selecting a person, leaving the image for >3 seconds,
returning within 60 seconds, and checking `ReID 재연결`. Also test similar clothes,
two simultaneous candidates, expired recovery, and reselection. Inspect `reid_ms`
and video processing latency; no hardware performance claim is made by unit tests.
