#!/bin/bash
set -e

echo "=== Clashroom Local AI Startup ==="

# Check CUDA availability
if command -v nvidia-smi &> /dev/null; then
    echo "✅ NVIDIA GPU detected"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "⚠️  No NVIDIA GPU detected, will use CPU (slower)"
fi

# Set HuggingFace cache
export HF_HOME=/workspace/hf_cache
mkdir -p $HF_HOME

echo "🚀 Starting uvicorn on port ${PORT:-8000}..."
echo "📦 Models will download on first run (may take 5-10 minutes)"

# Start server
exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
