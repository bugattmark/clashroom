# RunPod Setup Guide

## Requirements

- **GPU**: NVIDIA GPU with 16GB+ VRAM (RTX 4000 Ada or better)
- **Disk**: 20GB minimum
- **RunPod account**: https://runpod.io

## Step-by-Step

### 1. Create RunPod Pod

1. Go to https://www.runpod.io/console/pods
2. Click **"Deploy"** → **GPU Pod**
3. Select GPU: **RTX 4000 Ada** or **RTX A5000**
4. Configure:
   - **Container Disk**: `20 GB` minimum
   - **Expose HTTP Ports**: `8000`
   - **Volume**: Not needed
5. Click **"Deploy On-Demand"**
6. Wait ~30 seconds for provisioning

### 2. Upload Code

Option A - Git (recommended):
```bash
cd /workspace
git clone https://github.com/your-username/clashroom.git
cd clashroom
```

Option B - Manual upload:
1. Click "Connect" → "Start Jupyter Lab"
2. Upload all files via file browser

### 3. Build & Run

```bash
cd /workspace/clashroom

# Build Docker image (takes ~5 minutes)
docker build -t clashroom .

# Run container with GPU access
docker run -d -p 8000:8000 \
  --gpus all \
  --name clashroom \
  clashroom

# Monitor logs
docker logs -f clashroom
```

### 4. First Run (Model Download)

**Expected logs:**
```
=== Clashroom Local AI Startup ===
✅ NVIDIA GPU detected
NVIDIA GeForce RTX 4000 Ada, 20480 MiB
🚀 Starting uvicorn on port 8000...
📦 Models will download on first run (may take 5-10 minutes)
INFO: Loading Whisper model: tiny.en
INFO: Loading LLM model: Qwen/Qwen2.5-3B-Instruct
```

**This takes 5-10 minutes on first run!** Models download from HuggingFace:
- faster-whisper: ~75MB
- Qwen2.5-3B: ~2GB
- Piper voice: ~60MB

**Subsequent startups**: ~30 seconds (models cached)

### 5. Access Your App

1. In RunPod console, find your pod
2. Click **"Connect to HTTP Service [Port 8000]"**
3. URL format: `https://xxx-8000.proxy.runpod.net`
4. Open in **Chrome or Edge**

### 6. Test

1. Click **"Connect"** → Allow microphone
2. Status shows "connected"
3. Click **"Start debate"**
4. Wait ~2 seconds for LLM to generate
5. **Speak into microphone**
6. You should see:
   - Your words transcribed (STT)
   - Agent response text streaming
   - Agent voice playing

## Expected Behavior

### Latency Timeline
```
[0ms]    You start speaking
[200ms]  First words transcribed (partial)
[800ms]  You finish speaking
[900ms]  Full transcript ready
[1000ms] LLM first token arrives
[1100ms] First audio chunk plays
[2500ms] LLM completes, full audio plays
```

**Total: ~2.5 seconds from end of speech to start of response**

This is **much faster** than API-based solutions (which take 5-7 seconds).

### What You'll Hear/See

1. **Your speech** appears in "You" section as you speak
2. **Agent response** streams word-by-word in "Agent A/B" section
3. **Audio plays** in chunks as words are generated
4. **Barge-in works**: Speak while agent talks → agent stops

## Troubleshooting

### "Out of memory" error
```bash
# Use smaller Whisper model
export WHISPER_MODEL=tiny.en

# Or reduce LLM context
# Edit server.py line 172: max_new_tokens=100 (from 150)
```

### Slow inference (>5 seconds)
```bash
# Check GPU is actually being used
docker exec clashroom nvidia-smi

# Should show processes using GPU
# If not, rebuild with --gpus all flag
```

### Models not downloading
```bash
# Check disk space
df -h

# Need 20GB+ free space
# If low, increase Container Disk size in RunPod
```

### No transcription appearing
```bash
# Check logs for errors
docker logs clashroom | grep -i error

# Common: Whisper model download failed
# Fix: Restart container, wait for download
docker restart clashroom
```

### No audio playback
```bash
# Browser issue (not server)
# 1. Use Chrome or Edge (not Firefox/Safari)
# 2. Check browser console (F12) for errors
# 3. Check system volume not muted
```

### Port already in use
```bash
docker stop clashroom
docker rm clashroom
# Then re-run docker run command
```

## Commands Reference

```bash
# View logs
docker logs clashroom

# Live log stream
docker logs -f clashroom

# Check if running
docker ps

# Stop
docker stop clashroom

# Start
docker start clashroom

# Restart
docker restart clashroom

# Remove (to rebuild)
docker rm clashroom

# Full rebuild
docker stop clashroom && docker rm clashroom
docker build --no-cache -t clashroom .
docker run -d -p 8000:8000 --gpus all --name clashroom clashroom

# Check GPU usage
nvidia-smi

# Check disk space
df -h

# Enter container shell (for debugging)
docker exec -it clashroom bash
```

## Model Configuration

### To use smaller models (less VRAM):

Edit `server.py` or set environment:
```bash
docker run -d -p 8000:8000 \
  --gpus all \
  -e WHISPER_MODEL=tiny.en \
  -e LLM_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
  --name clashroom \
  clashroom
```

### Model sizes:

**Whisper**:
- `tiny.en`: 39M params, ~1GB VRAM
- `base.en`: 74M params, ~1.5GB VRAM
- `small.en`: 244M params, ~2GB VRAM

**LLM**:
- `Qwen2.5-1.5B`: ~3GB VRAM (4-bit)
- `Qwen2.5-3B`: ~6GB VRAM (4-bit)
- `Qwen2.5-7B`: ~12GB VRAM (4-bit)

**Recommended for RTX 4000 Ada (20GB)**:
- Whisper: `tiny.en` or `base.en`
- LLM: `Qwen2.5-3B` (leaves headroom)

## Cost

### RunPod Pricing (On-Demand)
- **RTX 4000 Ada**: $0.79/hour
- **RTX A5000**: $0.89/hour

### Tips to Save Money
1. **Stop pod when not using** (most important!)
2. Use Spot instances (cheaper but can be interrupted)
3. Choose regions with lower pricing
4. Test locally first before RunPod deployment

### Cost Comparison

**This setup (fully local)**:
- $0.79/hour (RunPod GPU only)
- Unlimited conversations

**Previous setup (APIs)**:
- OpenAI Whisper: $0.36/hour
- OpenAI Chat: $0.10/hour
- ElevenLabs: $0.30/hour
- RunPod: $0.50/hour
- **Total**: $1.26/hour

**Savings**: 37% cheaper + better latency!

## Next Steps

After it's working:

1. **Adjust agent personality**: Edit system prompt in `server.py` line 168
2. **Try different voices**: Change `PIPER_VOICE` environment variable
3. **Add more agents**: Extend the multi-agent logic
4. **Fine-tune latency**: Adjust VAD settings, buffer sizes
5. **Deploy permanently**: Create RunPod template for easy restart

---

**Questions?** Check logs first: `docker logs clashroom`

