"use strict";

const $ = (id) => document.getElementById(id);
let requestNumber = 0;
let pending = 0;
let polling = false;
let pollAgain = false;
let pollTimer;
let snapshotKey = "";

function connection(online) {
  $("connection").textContent = online ? "Jetson 연결됨" : "Jetson 연결 확인 실패";
  $("connection").className = `badge ${online ? "online" : "offline"}`;
}

function timeText(value) {
  return new Date(value).toLocaleTimeString("ko-KR", { hour12: false });
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(path, { ...options, cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: 명령 또는 서버 응답 확인 필요`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function renderSnapshot(data) {
  const key = `${data.instance_id}:${data.total_received}`;
  if (snapshotKey === key) return;
  snapshotKey = key;
  const latest = data.latest_command;
  $("history-count").textContent = `최근 ${data.history.length}건 / 총 ${data.total_received}건`;
  $("server-latest").textContent = latest
    ? `서버 마지막 수신 #${latest.sequence}: ${latest.command} → ${latest.action}`
    : "서버 명령 대기";
  const fragment = document.createDocumentFragment();
  for (const record of data.history) {
    const row = document.createElement("li");
    const sequence = document.createElement("span");
    sequence.className = "sequence";
    sequence.textContent = `#${record.sequence}`;
    const detail = document.createElement("div");
    detail.textContent = `${record.action} · ${record.command}`;
    const client = document.createElement("small");
    client.textContent = record.client_ip || "IP 정보 없음";
    detail.append(client);
    const time = document.createElement("time");
    time.dateTime = record.received_at;
    time.textContent = timeText(record.received_at);
    row.append(sequence, detail, time);
    fragment.append(row);
  }
  if (!data.history.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "아직 받은 명령이 없음";
    fragment.append(empty);
  }
  $("history").replaceChildren(fragment);
}

async function refreshStatus() {
  if (document.hidden) return;
  if (polling) { pollAgain = true; return; }
  clearTimeout(pollTimer);
  polling = true;
  try {
    const data = await api("/api/status");
    connection(data.status === "ok");
    renderSnapshot(data);
    $("history-status").textContent = `서버 확인 ${timeText(Date.now())} · 최대 ${data.history_capacity}건 보관`;
  } catch (error) {
    connection(false);
    $("history-status").textContent = "연결 확인 실패 · 아래 기록은 마지막으로 확인한 내용";
  } finally {
    polling = false;
    const delay = pollAgain ? 0 : 1000;
    pollAgain = false;
    if (!document.hidden) pollTimer = setTimeout(refreshStatus, delay);
  }
}

async function sendCommand(command) {
  const number = ++requestNumber;
  pending += 1;
  $("pending").textContent = `전송 대기 ${pending}건`;
  $("request-number").textContent = `요청 ${number}`;
  $("last-sent").textContent = command;
  $("action").textContent = "응답 대기";
  $("received-at").textContent = "—";
  $("client-ip").textContent = "—";
  $("result").className = "result";
  $("result").textContent = "Jetson 수신 확인 중…";
  try {
    // 클릭 한 번에 POST 한 번. 타이머·재시도·touchstart 중복 전송 없음.
    const receipt = await api("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    });
    // 빠른 입력에서 오래된 응답이 마지막 요청의 결과를 덮어쓰지 않도록 제한.
    if (number === requestNumber) {
      $("action").textContent = receipt.action;
      $("received-at").textContent = timeText(receipt.received_at);
      $("client-ip").textContent = receipt.client_ip || "IP 정보 없음";
      $("result").className = "result success";
      $("result").textContent = `수신·해석 성공 #${receipt.sequence} · 하드웨어 전송 없음`;
    }
  } catch (error) {
    if (number === requestNumber) {
      $("action").textContent = "확인 불가";
      $("result").className = "result error";
      $("result").textContent = error.name === "AbortError"
        ? "응답 시간 초과 · 이미 수신됐을 수 있으므로 서버 기록 확인. 자동 재전송 없음."
        : `응답 확인 실패 · ${error.message}. 서버 기록과 Wi-Fi 연결 확인.`;
    }
  } finally {
    pending -= 1;
    $("pending").textContent = `전송 대기 ${pending}건`;
    refreshStatus();
  }
}

document.querySelectorAll("button[data-command]").forEach((button) => {
  button.addEventListener("click", () => sendCommand(button.dataset.command));
});
document.addEventListener("visibilitychange", () => {
  clearTimeout(pollTimer);
  if (!document.hidden) refreshStatus();
});
window.addEventListener("online", refreshStatus);
window.addEventListener("offline", () => connection(false));
refreshStatus();
