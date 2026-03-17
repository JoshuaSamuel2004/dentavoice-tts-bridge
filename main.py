from fastapi import FastAPI, Request, Response
import httpx
import base64
import os
 
app = FastAPI()
 
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your-key-here")
SARVAM_SPEAKER = os.environ.get("SARVAM_SPEAKER", "priya")
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
 
 
@app.post("/tts")
async def custom_tts(request: Request):
    try:
        body = await request.json()
        print(f"Received from Vapi: {list(body.keys())}")
 
        # Extract text from Vapi's request
        text = ""
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
        if not text and "data" in body:
            data = body["data"]
            if isinstance(data, dict):
                text = data.get("text", data.get("message", ""))
 
        print(f"Text to speak: '{text[:100]}'" if text else "No text found!")
 
        if not text:
            print(f"WARNING: No text in payload. Body: {body}")
            return Response(content=b'\x00' * 320, media_type="audio/pcm")
 
        # Call Sarvam TTS API
        # Using linear16 (raw PCM) at 16kHz - exactly what Vapi needs
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SARVAM_SPEAKER,
            "model": "bulbul:v3",
            "audio_format": "linear16",
            "audio_sample_rate": 16000,
            "enable_preprocessing": True,
            "pace": 1.25,
        }
 
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        }
 
        print(f"Calling Sarvam with speaker={SARVAM_SPEAKER}, pace=1.25...")
 
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers,
            )
 
        print(f"Sarvam status: {response.status_code}")
 
        if response.status_code != 200:
            print(f"Sarvam error: {response.status_code} - {response.text[:500]}")
            return Response(content=b'\x00' * 320, media_type="audio/pcm")
 
        result = response.json()
        audio_b64 = result.get("audios", [None])[0]
 
        if not audio_b64:
            print("No audio in Sarvam response!")
            return Response(content=b'\x00' * 320, media_type="audio/pcm")
 
        # Decode the base64 audio - this is raw PCM 16-bit 16kHz mono
        audio_bytes = base64.b64decode(audio_b64)
        print(f"Got {len(audio_bytes)} bytes of audio")
 
        # Return RAW PCM audio to Vapi - NO WAV header
        # The WAV header was causing the "thud" sound
        # Vapi expects raw PCM: 16-bit, 16kHz, mono
        return Response(
            content=audio_bytes,
            media_type="audio/pcm",
            headers={
                "Content-Type": "audio/pcm",
                "X-Audio-Sample-Rate": "16000",
                "X-Audio-Channels": "1",
                "X-Audio-Bit-Depth": "16",
            }
        )
 
    except Exception as e:
        print(f"Error in /tts: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b'\x00' * 320, media_type="audio/pcm")
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "dentavoice-tts-bridge"}
 
 
@app.get("/")
async def root():
    return {
        "service": "DentaVoice TTS Bridge",
        "status": "running",
        "speaker": SARVAM_SPEAKER,
        "endpoints": {"/tts": "POST - Vapi custom TTS", "/health": "GET - Health check"}
    }
 
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
