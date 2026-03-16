from fastapi import FastAPI, Request, Response
import httpx
import base64
import os
import struct

app = FastAPI()

# Your Sarvam API key (set this as environment variable on Render)
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "sk_hk4s4kw1_H1sWoJZNlHpN5ERB1xavYDHn")

# Change this to the voice you picked in Step B
SARVAM_SPEAKER = os.environ.get("SARVAM_SPEAKER", "riya")

# Sarvam API URL
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


def create_wav_header(audio_bytes: bytes, sample_rate: int = 8000) -> bytes:
    """Create WAV header for raw PCM audio."""
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(audio_bytes)
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,
        1,  # PCM format
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size,
    )
    return header


@app.post("/tts")
async def custom_tts(request: Request):
    """
    Vapi sends POST with JSON: { "message": { "text": "..." } }
    We send text to Sarvam, get audio back, return to Vapi.
    """
    try:
        body = await request.json()
        
        # Extract text from Vapi's request
        # Vapi custom TTS sends the text in message.text
        text = ""
        if "message" in body:
            msg = body["message"]
            if isinstance(msg, dict):
                text = msg.get("text", "")
            elif isinstance(msg, str):
                text = msg
        
        if not text:
            # Try alternative formats
            text = body.get("text", body.get("input", ""))
        
        if not text:
            return Response(content=b"", status_code=200)
        
        # Call Sarvam TTS API
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SARVAM_SPEAKER,
            "model": "bulbul:v3",
            "audio_format": "mulaw",
            "audio_sample_rate": 8000,
            "enable_preprocessing": True,
        }
        
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers,
            )
        
        if response.status_code != 200:
            print(f"Sarvam error: {response.status_code} - {response.text}")
            return Response(content=b"", status_code=200)
        
        result = response.json()
        
        # Sarvam returns base64-encoded audio
        audio_b64 = result.get("audios", [None])[0]
        if not audio_b64:
            return Response(content=b"", status_code=200)
        
        audio_bytes = base64.b64decode(audio_b64)
        
        # Add WAV header for mulaw audio
        wav_header = create_wav_header(audio_bytes, sample_rate=8000)
        wav_audio = wav_header + audio_bytes
        
        # Return audio to Vapi
        return Response(
            content=wav_audio,
            media_type="audio/wav",
            headers={
                "Content-Type": "audio/wav",
            }
        )
    
    except Exception as e:
        print(f"Error: {e}")
        return Response(content=b"", status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dentavoice-tts-bridge"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
