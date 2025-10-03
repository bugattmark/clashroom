import asyncio
import io
import json
import logging
import os
import struct
import wave
from collections import deque
from contextlib import suppress
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import numpy as np
import soundfile as sf
import torch
import webrtcvad
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
from piper import PiperVoice
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clashroom")

BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny.en")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct")
PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-lessac-medium")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

# Global model instances
_whisper_model: Optional[WhisperModel] = None
_llm_model: Optional[Any] = None
_llm_tokenizer: Optional[Any] = None
_piper_voice: Optional[PiperVoice] = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device="cuda" if torch.cuda.is_available() else "cpu",
            compute_type="float16" if torch.cuda.is_available() else "int8"
        )
    return _whisper_model


def get_llm_model():
    global _llm_model, _llm_tokenizer
    if _llm_model is None or _llm_tokenizer is None:
        logger.info(f"Loading LLM model: {LLM_MODEL}")
        _llm_tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            LLM_MODEL,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            load_in_4bit=True if torch.cuda.is_available() else False,
        )
    return _llm_model, _llm_tokenizer


def get_piper_voice() -> PiperVoice:
    global _piper_voice
    if _piper_voice is None:
        logger.info(f"Loading Piper voice: {PIPER_VOICE}")
        voice_path = MODELS_DIR / f"{PIPER_VOICE}.onnx"
        if not voice_path.exists():
            logger.warning(f"Piper voice not found at {voice_path}, downloading...")
            # In production, download from Piper voices repo
        _piper_voice = PiperVoice.load(str(voice_path))
    return _piper_voice


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


class AudioProcessor:
    def __init__(self):
        self.vad = webrtcvad.Vad(3)  # Aggressiveness 0-3
        self.sample_rate = 16000
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.buffer = bytearray()
        
    def add_audio(self, audio_bytes: bytes) -> Optional[bytes]:
        """Add audio and return complete utterance when silence detected"""
        self.buffer.extend(audio_bytes)
        
        # Process in frames
        if len(self.buffer) < self.frame_size * 2:
            return None
            
        # Simple VAD: check if we have speech
        frame = bytes(self.buffer[:self.frame_size * 2])
        try:
            is_speech = self.vad.is_speech(frame, self.sample_rate)
            if not is_speech and len(self.buffer) > self.sample_rate * 2:  # 1 sec of audio
                result = bytes(self.buffer)
                self.buffer.clear()
                return result
        except Exception as e:
            logger.error(f"VAD error: {e}")
        
        return None


async def transcribe_audio(audio_data: bytes) -> Optional[str]:
    """Transcribe audio using faster-whisper"""
    try:
        model = get_whisper_model()
        
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Transcribe
        segments, info = model.transcribe(
            audio_np,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
            vad_filter=True,
        )
        
        text = " ".join(segment.text for segment in segments).strip()
        return text if text else None
    
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None


async def generate_llm_response(
    prompt: str,
    interrupt_event: asyncio.Event
) -> AsyncIterator[str]:
    """Generate streaming LLM response"""
    try:
        model, tokenizer = get_llm_model()
        
        messages = [
            {"role": "system", "content": "You are a concise debating agent. Respond in 1-2 short sentences."},
            {"role": "user", "content": prompt}
        ]
        
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            inputs,
            streamer=streamer,
            max_new_tokens=150,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )
        
        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        
        for text in streamer:
            if interrupt_event.is_set():
                break
            yield text
        
        thread.join()
    
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        yield f"Error: {str(e)}"


async def synthesize_speech(text: str) -> Optional[bytes]:
    """Synthesize speech using Piper TTS"""
    try:
        voice = get_piper_voice()
        
        # Generate audio
        audio_chunks = []
        for audio_bytes in voice.synthesize_stream_raw(text):
            audio_chunks.append(audio_bytes)
        
        if not audio_chunks:
            return None
            
        # Combine and convert to WAV
        audio_data = b"".join(audio_chunks)
        
        # Create WAV file in memory
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(audio_data)
        
        return wav_io.getvalue()
    
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "ready"})
    
    processor = AudioProcessor()
    llm_interrupt: Optional[asyncio.Event] = None
    llm_task: Optional[asyncio.Task] = None
    
    async def run_llm_pipeline(transcript: str) -> None:
        nonlocal llm_interrupt, llm_task
        
        if llm_task and not llm_task.done():
            if llm_interrupt:
                llm_interrupt.set()
            with suppress(asyncio.CancelledError):
                await llm_task
        
        llm_interrupt = asyncio.Event()
        await websocket.send_json({"type": "llm_start"})
        
        async def _worker() -> None:
            nonlocal llm_interrupt
            try:
                full_text = []
                async for token in generate_llm_response(transcript, llm_interrupt):
                    full_text.append(token)
                    await websocket.send_json({"type": "llm", "text": token})
                
                if full_text and not llm_interrupt.is_set():
                    complete_text = "".join(full_text)
                    await websocket.send_json({"type": "llm_final", "text": complete_text})
                    
                    # Generate speech
                    audio_data = await synthesize_speech(complete_text)
                    if audio_data:
                        await websocket.send_json({
                            "type": "tts_audio",
                            "audio": audio_data.hex(),
                            "format": "wav"
                        })
            
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"LLM pipeline error: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
            finally:
                if llm_interrupt:
                    llm_interrupt.set()
                    llm_interrupt = None
        
        llm_task = asyncio.create_task(_worker())
    
    try:
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                break
            
            if message.get("bytes"):
                audio_chunk = message["bytes"]
                
                # Process audio
                complete_audio = processor.add_audio(audio_chunk)
                if complete_audio:
                    transcript = await transcribe_audio(complete_audio)
                    if transcript:
                        await websocket.send_json({
                            "type": "stt",
                            "text": transcript,
                            "final": True
                        })
                        await run_llm_pipeline(transcript)
            
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                
                kind = data.get("type")
                
                if kind == "interrupt":
                    if llm_interrupt and not llm_interrupt.is_set():
                        llm_interrupt.set()
                        await websocket.send_json({"type": "interrupt_ack"})
                    processor.buffer.clear()
                
                elif kind == "prompt":
                    text = (data.get("text") or "").strip()
                    if text:
                        await websocket.send_json({"type": "stt", "text": text, "final": True})
                        await run_llm_pipeline(text)
                
                elif kind == "ping":
                    await websocket.send_json({"type": "pong", "id": data.get("id")})
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    finally:
        if llm_task and not llm_task.done():
            if llm_interrupt:
                llm_interrupt.set()
            llm_task.cancel()
            with suppress(asyncio.CancelledError):
                await llm_task
        await websocket.close()


@app.on_event("startup")
async def startup_event():
    logger.info("Loading models on startup...")
    # Preload models
    get_whisper_model()
    get_llm_model()
    # Piper voice loads on first use
    logger.info("Models loaded successfully")
