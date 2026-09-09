/* Latest-frame JPEG polling; stale camera and inference frames are discarded server-side. */
(() => {
  const $ = id => document.getElementById(id);
  const canvas = $('video'), context = canvas.getContext('2d');
  let state = {}, sequence = 0, session = '', generation = 0;
  let displayed = 0, skipped = 0, requests = 0, requestMs = 0;
  let epoch = performance.now(), measurement = null, hasFrame = false;
  const number = value => Number.isFinite(value) ? value : 0;
  const reusableImage = new Image();

  async function decodeFrame(blob) {
    if ('createImageBitmap' in window) {
      return await createImageBitmap(blob);
    }
    const url = URL.createObjectURL(blob);
    try {
      reusableImage.src = url;
      await reusableImage.decode();
      return reusableImage;
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  function reset() {
    displayed = skipped = requests = requestMs = 0;
    epoch = performance.now();
  }

  async function api(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/api/vision/' + path, {
        cache: 'no-store', signal: controller.signal,
        ...(body === undefined ? {} : {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body),
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  async function action(path, body) {
    try { state = await api(path, body); }
    catch (error) { $('vision-status').textContent = error.message; }
  }

  $('camera-on').onclick = () => action('start', {mode: $('vision-mode').value});
  $('camera-off').onclick = () => action('stop', {});
  $('tracking-toggle').onclick = () => action('tracking', {enabled: !state.tracking_enabled});
  $('target-clear').onclick = () => action('target/clear', {});
  canvas.addEventListener('click', event => {
    if (!hasFrame || state.mode !== 'ai' || !state.running) return;
    const bounds = canvas.getBoundingClientRect();
    action('target', {
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    });
  });
  $('capture-frame').onclick = () => {
    if (!hasFrame) return;
    canvas.toBlob(blob => {
      if (!blob) return;
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url;
      link.download = `capture_${Date.now()}_live.png`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }, 'image/png');
  };
  $('benchmark').onclick = () => {
    if (!state.running || state.mode === 'camera' || document.hidden) {
      $('benchmark-result').textContent = '실시간 영상 전송 중에 측정하세요.';
      return;
    }
    measurement = {start: performance.now(), displayed, skipped, requests, requestMs, session};
    $('benchmark-result').textContent = '30초 측정 중 — 이 화면을 유지하세요.';
  };

  async function statusLoop() {
    try {
      state = await api('status');
      if (session !== state.session) {
        session = state.session;
        sequence = 0;
        generation++;
        reset();
        measurement = null;
      }
      $('tracking-toggle').textContent = state.tracking_enabled ? '팬·틸트 중지' : '팬·틸트 시작';
      $('vision-status').textContent = state.error ||
        `${state.running ? '실행 중' : '정지'} · ${state.mode} · 인물 ${(state.people || []).length}명 · UART ${state.uart}`;
      const seconds = Math.max(0.001, (performance.now() - epoch) / 1000);
      $('vision-metrics').textContent =
        `캡처 ${number(state.capture_fps).toFixed(1)} FPS · AI ${number(state.ai_fps).toFixed(1)} FPS · ` +
        `브라우저 ${(displayed / seconds).toFixed(1)} FPS · 처리 ${number(state.processing_ms).toFixed(1)}ms · ` +
        `프레임 나이 ${number(state.frame_age_ms).toFixed(1)}ms · AI 건너뜀 ${number(state.inference_frames_skipped)}장 · ` +
        `JPEG ${number(state.jpeg_ms).toFixed(1)}ms`;
      if (state.tracking)
        $('vision-status').textContent += ` · 팬 ${state.tracking.pan_angle}° / 틸트 ${state.tracking.tilt_angle}°`;
      const target = state.target || {};
      const detector = state.detector || {};
      $('target-id').textContent = target.selected_id == null ? '선택 안 됨' : `ID ${target.selected_id}`;
      $('target-state').textContent = target.state || '선택 대기';
      $('detector-detail').textContent = `${detector.model || 'YOLO Person'} · ${number(detector.inference_ms).toFixed(1)}ms`;
      $('people-list').textContent = (state.people || []).length ? '검출: ' + state.people.map(person =>
        `ID ${person.track_id} (${(person.confidence * 100).toFixed(0)}%)`).join(' · ') :
        '검출 인물 없음';
      $('reid-similarity').textContent = target.reid_similarity == null ? '수집 중' :
        `${(target.reid_similarity * 100).toFixed(1)}%` +
        (target.reid_candidate_id == null ? '' : ` · 후보 ID ${target.reid_candidate_id}`);
      $('reid-profile').textContent = `${number(target.reid_profile_samples)}장 · 판정 ${(number(target.reid_threshold) * 100).toFixed(0)}%`;
      $('reid-method').textContent = target.reid_method || '—';
      if (measurement && (!state.running || session !== measurement.session)) {
        measurement = null;
        $('benchmark-result').textContent = '카메라 상태가 바뀌어 측정을 취소했습니다.';
      }
      if (measurement && performance.now() - measurement.start >= 30000) {
        const m = measurement;
        measurement = null;
        const seconds = (performance.now() - m.start) / 1000;
        const report = {
          session, seconds, displayed: displayed - m.displayed, skipped: skipped - m.skipped,
          fps: (displayed - m.displayed) / seconds,
          request_ms: (requestMs - m.requestMs) / Math.max(1, requests - m.requests),
        };
        const loss = report.skipped / Math.max(1, report.displayed + report.skipped) * 100;
        $('benchmark-result').textContent =
          `${seconds.toFixed(1)}초: 표시 ${report.fps.toFixed(2)} FPS / ${report.displayed}장\n` +
          `출력 프레임 건너뜀 ${report.skipped}장 (${loss.toFixed(1)}%)\n` +
          `요청→디코딩·그리기 평균 ${report.request_ms.toFixed(1)}ms\n` +
          `AI 프레임 나이 ${number(state.frame_age_ms).toFixed(1)}ms · AI 건너뜀 ${number(state.inference_frames_skipped)}장`;
        await api('report', report);
      }
    } catch (error) { $('vision-status').textContent = `연결 오류: ${error.message}`; }
    setTimeout(statusLoop, 1000);
  }

  async function videoLoop() {
    let failed = false;
    if (!document.hidden && state.running && state.mode !== 'camera') {
      const version = generation, started = performance.now();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      try {
        const response = await fetch(`/api/vision/frame?after=${sequence}`, {cache: 'no-store', signal: controller.signal});
        if (response.status === 200) {
          const decoded = await decodeFrame(await response.blob());
          try {
            if (version === generation && !document.hidden && response.headers.get('X-Session') === session) {
              const width = decoded.width || decoded.naturalWidth;
              const height = decoded.height || decoded.naturalHeight;
              if (canvas.width !== width || canvas.height !== height) {
                canvas.width = width;
                canvas.height = height;
              }
              context.drawImage(decoded, 0, 0);
              hasFrame = true;
              const next = Number(response.headers.get('X-Sequence'));
              if (sequence) skipped += Math.max(0, next - sequence - 1);
              sequence = next;
              displayed++;
              requests++;
              requestMs += performance.now() - started;
            }
          } finally {
            if (typeof decoded.close === 'function') decoded.close();
          }
        } else if (response.status !== 204) throw new Error(`영상 HTTP ${response.status}`);
      } catch (error) {
        failed = true;
        $('vision-status').textContent = error.message;
      } finally { clearTimeout(timer); }
    }
    setTimeout(videoLoop,
      failed ? 1000 : !state.running || document.hidden || state.mode === 'camera' ? 200 : 0);
  }

  document.addEventListener('visibilitychange', () => {
    generation++;
    sequence = 0;
    reset();
    if (measurement) {
      measurement = null;
      $('benchmark-result').textContent = '화면이 숨겨져 측정을 취소했습니다.';
    }
  });
  statusLoop();
  videoLoop();
})();
