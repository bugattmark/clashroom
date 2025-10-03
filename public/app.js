// app.js — Streaming debate MVP with WebSocket relay.

const connectBtn = document.getElementById("connectBtn");
const startBtn = document.getElementById("startBtn");
const muteBtn = document.getElementById("muteBtn");
const statusEl = document.getElementById("status");
const youEl = document.getElementById("youStream");
const agentAEl = document.getElementById("agentAStream");
const agentBEl = document.getElementById("agentBStream");
const topicInput = document.getElementById("topic");

const VAD_THRESHOLD = 0.01;
const VAD_HANGOVER = 150;
const CHUNK_MS = 400;

let ws;
let mediaStream;
let mediaRecorder;
let audioContext;
let vadNode;
let vadActive = false;
let lastVoiceMs = 0;
let currentAgent = "A";
let speaking = false;
const agentBuffers = { A: "", B: "" };

async function setupAudio() {
  if (mediaStream) return;
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioContext = new AudioContext({ sampleRate: 16000 });
  const sourceNode = audioContext.createMediaStreamSource(mediaStream);
  const processor = audioContext.createScriptProcessor(1024, 1, 1);
  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    let rms = 0;
    for (let i = 0; i < input.length; i++) {
      rms += input[i] * input[i];
    }
    rms = Math.sqrt(rms / input.length);
    const now = performance.now();
    if (rms > VAD_THRESHOLD) {
      lastVoiceMs = now;
      if (!vadActive) {
        vadActive = true;
        sendInterrupt();
      }
    } else if (vadActive && now - lastVoiceMs > VAD_HANGOVER) {
      vadActive = false;
    }
  };
  sourceNode.connect(processor);
  processor.connect(audioContext.destination);
  vadNode = processor;
}

function startRecorder() {
  if (!mediaStream) return;
  mediaRecorder = new MediaRecorder(mediaStream, {
    mimeType: "audio/webm;codecs=opus",
    audioBitsPerSecond: 64000,
  });
  mediaRecorder.ondataavailable = async (evt) => {
    if (evt.data && evt.data.size > 0 && ws?.readyState === WebSocket.OPEN) {
      const arrayBuffer = await evt.data.arrayBuffer();
      ws.send(arrayBuffer);
    }
  };
  mediaRecorder.start(CHUNK_MS);
}

function stopRecorder() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  mediaRecorder = null;
}

function updateStatus(text) {
  statusEl.textContent = text;
}

let currentAudio = null;

function playAudioFromHex(hexString, format = 'wav') {
  try {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    
    // Convert hex string to bytes
    const bytes = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const mimeType = format === 'mp3' ? 'audio/mpeg' : 'audio/wav';
    const blob = new Blob([bytes], { type: mimeType });
    const url = URL.createObjectURL(blob);
    
    currentAudio = new Audio(url);
    currentAudio.onplay = () => { speaking = true; };
    currentAudio.onended = () => {
      speaking = false;
      URL.revokeObjectURL(url);
      currentAudio = null;
    };
    currentAudio.onerror = (e) => {
      console.error("Audio playback error:", e);
      speaking = false;
      URL.revokeObjectURL(url);
      currentAudio = null;
    };
    
    currentAudio.play().catch(err => console.error("Play failed:", err));
  } catch (err) {
    console.error("Failed to play audio:", err);
    speaking = false;
  }
}

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    updateStatus("connected");
    muteBtn.disabled = false;
    startBtn.disabled = false;
    startRecorder();
  };

  ws.onclose = () => {
    updateStatus("disconnected");
    muteBtn.disabled = true;
    startBtn.disabled = true;
    connectBtn.disabled = false;
    stopRecorder();
  };

  ws.onerror = (err) => {
    console.error("WebSocket error", err);
    updateStatus("error");
  };

  ws.onmessage = (evt) => {
    try {
      const payload = JSON.parse(evt.data);
      handleMessage(payload);
    } catch (err) {
      console.error("Invalid JSON message", err, evt.data);
    }
  };
}

function sendInterrupt() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  
  // Stop any playing audio
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  
  ws.send(JSON.stringify({ type: "interrupt" }));
}

function handleMessage(msg) {
  if (msg.type === "ready") {
    updateStatus("ready");
  } else if (msg.type === "llm_start") {
    const target = currentAgent === "A" ? agentAEl : agentBEl;
    agentBuffers[currentAgent] = "";
    target.textContent = "…";
  } else if (msg.type === "stt") {
    if (msg.final) {
      youEl.textContent = msg.text;
    } else if (msg.text) {
      youEl.textContent = msg.text + " …";
    }
  } else if (msg.type === "llm") {
    const target = currentAgent === "A" ? agentAEl : agentBEl;
    agentBuffers[currentAgent] += msg.text;
    target.textContent = agentBuffers[currentAgent] + " …";
  } else if (msg.type === "llm_final") {
    const target = currentAgent === "A" ? agentAEl : agentBEl;
    agentBuffers[currentAgent] = msg.text;
    target.textContent = msg.text;
    // Audio will come in separate tts_audio message
  } else if (msg.type === "tts_audio") {
    // Play Piper TTS audio
    if (msg.audio) {
      playAudioFromHex(msg.audio, msg.format || 'wav');
      currentAgent = currentAgent === "A" ? "B" : "A";
    }
  } else if (msg.type === "interrupt_ack") {
    updateStatus("interrupted");
  } else if (msg.type === "error") {
    console.error("Server error", msg);
    updateStatus("error: " + (msg.message || "unknown"));
  } else if (msg.type === "pong") {
    // keep-alive
  }
}

connectBtn.addEventListener("click", async () => {
  connectBtn.disabled = true;
  try {
    await setupAudio();
    connect();
    updateStatus("connecting...");
  } catch (err) {
    console.error("Audio setup failed", err);
    updateStatus("mic access denied");
    connectBtn.disabled = false;
  }
});

muteBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    stopRecorder();
    muteBtn.textContent = "Unmute mic";
    updateStatus("mic muted");
  } else {
    startRecorder();
    muteBtn.textContent = "Mute mic";
    updateStatus("mic active");
  }
});

startBtn.addEventListener("click", () => {
  const topic = topicInput.value.trim() || "Should AI have legal personhood?";
  currentAgent = "A";
  agentAEl.textContent = "";
  agentBEl.textContent = "";
  agentBuffers.A = "";
  agentBuffers.B = "";
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "prompt", text: topic }));
  }
});
