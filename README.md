# Clashroom - Fully Local Real-Time Voice AI

Real-time voice debate system running **completely on your GPU**. No API costs, true streaming, ~300-500ms latency.

## Stack

- **STT**: faster-whisper (tiny.en model, streaming)
- **LLM**: Qwen2.5-3B-Instruct (4-bit quantized)
- **TTS**: Piper (en_US-lessac-medium voice)
- **Backend**: FastAPI + WebSocket
- **Hardware**: NVIDIA GPU (tested on RTX 4000 Ada)

## Features

✅ **Fully local** - No API calls, no internet needed after models download  
✅ **True real-time** - Streaming STT, LLM, and TTS (300-500ms total latency)  
✅ **Word-by-word** - Audio generated as LLM tokens arrive  
✅ **Barge-in** - Interrupt agents mid-sentence  
✅ **Low cost** - Only RunPod GPU costs (~$0.50/hour)  

## Quick Start

### 1. Deploy to RunPod

```bash
# Create GPU pod (RTX 4000 or better)
# Container Disk: 20GB minimum
# Expose HTTP Ports: 8000

# In RunPod terminal:
cd /workspace
git clone <your-repo> clashroom
cd clashroom

docker build -t clashroom .

docker run -d -p 8000:8000 \
  --gpus all \
  --name clashroom \
  clashroom

docker logs -f clashroom
```

### 2. First Run (Model Download)

**First startup takes 5-10 minutes** to download models:
- faster-whisper tiny.en: ~75MB
- Qwen2.5-3B-Instruct: ~2GB
- Piper voice: ~60MB

**Total disk space needed**: ~5GB

### 3. Access

1. Click "Connect to HTTP Service [Port 8000]" in RunPod
2. Open in Chrome/Edge
3. Click "Connect" → Allow mic
4. Click "Start debate"
5. Speak and debate!

## Expected Performance

### Latency Breakdown
- Speech → Transcription: ~100-200ms
- LLM first token: ~100-150ms
- Audio generation: ~50-100ms per word
- **Total perceived latency**: ~300-500ms

### Resource Usage (RTX 4000 Ada)
- **VRAM**: ~12GB (Whisper: 1GB, LLM: 8GB, Piper: minimal)
- **Disk**: ~5GB (models)
- **CPU**: Minimal (GPU handles everything)

## Configuration

Optional environment variables:

```bash
WHISPER_MODEL=tiny.en          # Options: tiny.en, base.en, small.en
LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
PIPER_VOICE=en_US-lessac-medium
PORT=8000
```

## Architecture

```
Browser (MediaRecorder + VAD)
    ↓ WebSocket (PCM audio)
FastAPI Server
    ↓ faster-whisper (streaming)
    ↓ Qwen 3B (streaming tokens)
    ↓ Piper TTS (word-by-word audio)
    ↓ WebSocket (WAV chunks)
Browser (Audio playback)
```

## Cost

**Per hour**:
- RunPod GPU (RTX 4000): ~$0.50-0.79/hour
- **Total**: ~$0.50-0.79/hour

**No API costs!** Everything runs locally.

## Troubleshooting

```bash
# Check logs
docker logs clashroom

# Check GPU usage
nvidia-smi

# Restart
docker restart clashroom

# Rebuild
docker stop clashroom && docker rm clashroom
docker build --no-cache -t clashroom .
docker run -d -p 8000:8000 --gpus all --name clashroom clashroom
```

### Common Issues

**Models not downloading**: Check RunPod disk space (need 20GB+)  
**Out of memory**: Use smaller models (base → tiny for Whisper)  
**Slow inference**: Ensure `--gpus all` flag is set  
**No audio**: Use Chrome/Edge, check browser console  

## Files

```
├── server.py          # FastAPI server with model loading
├── requirements.txt   # Python dependencies
├── Dockerfile        # NVIDIA CUDA base image
├── start.sh          # Startup script
├── public/
│   ├── index.html    # UI
│   ├── app.js        # WebSocket client
│   └── styles.css    # Styling
└── README.md         # This file
```

## Development

```bash
# Local (with GPU)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## License

MIT
