from fastapi import FastAPI, Request, Response
import httpx
import base64
import os
import struct
 
app = FastAPI()
 
# Your Sarvam API key (set as environment variable on Render)
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "sk_hk4s4kw1_H1sWoJZNlHpN5ERB1xavYDHn")
 
# Your chosen Sarvam voice
SARVAM_SPEAKER = os.environ.get("SARVAM_SPEAKER", "priya")
 
# Sarvam API URL
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
 
 
@app.post("/tts")
async def custom_tts(request: Request):
    """
    Bridge between Vapi Custom TTS and Sarvam AI.
    Vapi sends text -> we send to Sarvam -> return PCM audio to Vapi.
    """
    try:
        body = await request.json()
        
        # Log what Vapi sends (helps with debugging)
        print(f"Received from Vapi: {list(body.keys())}")
        
        # Extract text - Vapi can send it in different formats
        text = ""
        
        # Try all known Vapi payload formats
        if "message" in body:
            msg = body["message"]
            if isinstance(msg, dict):
                text = msg.get("text", msg.get("content", ""))
            elif isinstance(msg, str):
                text = msg
        
        if not text and "text" in body:
            text = body["text"]
            
        if not text and "input" in body:
            text = body["input"]
        
        # Try nested structures
        if not text and "data" in body:
            data = body["data"]
            if isinstance(data, dict):
                text = data.get("text", data.get("message", ""))
        
        print(f"Text to speak: '{text[:100]}'" if text else "No text found!")
        
        if not text:
            # Return silent audio instead of empty response
            print(f"WARNING: No text found in payload. Full body: {body}")
            # Return minimal valid WAV (silence)
            silent_audio = create_wav_header(b'\x00' * 3200, 16000) + b'\x00' * 3200
            return Response(content=silent_audio, media_type="audio/wav")
        
        # Call Sarvam TTS API
        # Using linear16 format at 16kHz - this is what Vapi expects
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SARVAM_SPEAKER,
            "model": "bulbul:v3",
            "audio_format": "linear16",
            "audio_sample_rate": 16000,
            "enable_preprocessing": True,
        }
        
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        }
        
        print(f"Calling Sarvam API with speaker={SARVAM_SPEAKER}...")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers,
            )
        
        print(f"Sarvam response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Sarvam error: {response.status_code} - {response.text[:500]}")
            return Response(content=b"", status_code=200)
        
        result = response.json()
        
        # Sarvam returns base64-encoded audio
        audio_b64 = result.get("audios", [None])[0]
        if not audio_b64:
            print("No audio in Sarvam response!")
            return Response(content=b"", status_code=200)
        
        audio_bytes = base64.b64decode(audio_b64)
        print(f"Got {len(audio_bytes)} bytes of audio from Sarvam")
        
        # Create WAV with proper header for Vapi
        # Vapi expects: PCM 16-bit, 16kHz, mono
        wav_header = create_wav_header(audio_bytes, sample_rate=16000)
        wav_audio = wav_header + audio_bytes
        
        return Response(
            content=wav_audio,
            media_type="audio/wav",
            headers={
                "Content-Type": "audio/wav",
            }
        )
    
    except Exception as e:
        print(f"Error in /tts: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b"", status_code=200)
 
 
def create_wav_header(audio_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Create a proper WAV header for PCM 16-bit mono audio."""
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
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "dentavoice-tts-bridge"}
 
 
@app.get("/")
async def root():
    return {"service": "DentaVoice TTS Bridge", "status": "running", "endpoints": {"/tts": "POST - Vapi custom TTS", "/health": "GET - Health check"}}
 
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
 






