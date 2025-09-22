# Clashroom

Clashroom is a system where multiple AI agents can hold a live debate with each other and with a human participant. The agents should sound natural, respond quickly, and be able to interrupt or barge in just like people do in real conversations. The goal is to create the feel of a lively, fast-paced discussion where voices overlap, ideas clash, and turns shift fluidly, rather than a rigid back-and-forth. It’s essentially a small simulated society of debaters, designed to explore how multi-agent conversations unfold when spontaneity and real-time interaction are central.

---

## Frontend

* Hosted on **Cloudflare Pages** at your domain.
* Handles mic capture, audio playback, and the WebSocket client.
* Streams raw PCM audio to the backend and plays audio streamed back.
* No browser TTS or STT.

---

## Backend

Runs in an **AWS ECS GPU container** (Fargate or EC2).
Exposes a FastAPI WebSocket service that:

1. Receives mic audio chunks.
2. Runs **Whisper tiny.en (faster-whisper)** for low-latency streaming STT.
3. Applies an inline barge-in policy (rules + lightweight classifier).
4. Passes text to a floor arbiter to decide who speaks next.
5. Generates responses with **Qwen2.5-4B-instruct** (streaming).
6. Synthesizes speech via **Piper TTS** (fast, local).
7. Streams PCM16 audio back to the browser.

---

## Flow

* The browser simply records and plays audio.
* The domain routes:

  * `yourdomain.com` → Cloudflare Pages
  * `api.yourdomain.com` → AWS load balancer → backend

---

## Performance

This setup delivers \~600–800 ms latency to first audio, real-time barge-ins, and consistent voices, with all intelligence (STT, arbiter, LLM, TTS) running in AWS.

---
