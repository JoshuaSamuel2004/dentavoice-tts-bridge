from fastapi import FastAPI, Request, Response
import httpx
import base64
import os
 
app = FastAPI()
 
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your-key-here")
SARVAM_SPEAKER = os.environ.get("SARVAM_SPEAKER", "ritu")
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
 
# Map Vapi sample rates to Sarvam supported rates
# Sarvam supports: 8000, 16000, 22050, 24000
SARVAM_SUPPORTED_RATES = {8000, 16000, 22050, 24000}
 
 
def get_closest_sarvam_rate(requested_rate):
    """Find the closest sample rate that Sarvam supports."""
    if requested_rate in SARVAM_SUPPORTED_RATES:
        return requested_rate
    # Find closest supported rate
    return min(SARVAM_SUPPORTED_RATES, key=lambda x: abs(x - requested_rate))
 
 
@app.post("/tts")
async def custom_tts(request: Request):
    try:
        body = await request.json()
        print(f"=== NEW TTS REQUEST ===")
        print(f"Keys: {list(body.keys())}")
 
        # --- EXTRACT TEXT AND SAMPLE RATE FROM VAPI ---
        # Vapi sends: { "message": { "type": "voice-request", "text": "...", "sampleRate": 24000 } }
        text = ""
        sample_rate = 24000  # Vapi default
 
        message = body.get("message", {})
        if isinstance(message, dict):
            text = message.get("text", "")
            sample_rate = message.get("sampleRate", 24000)
            msg_type = message.get("type", "unknown")
            print(f"Message type: {msg_type}")
            print(f"Requested sampleRate: {sample_rate}")
        elif isinstance(message, str):
            text = message
 
        # Fallback text extraction
        if not text:
            text = body.get("text", body.get("input", ""))
 
        print(f"Text: '{text[:100]}'" if text else "NO TEXT FOUND!")
 
        if not text:
            print(f"Full body for debug: {body}")
            return Response(content=b"", status_code=200)
 
        # --- CALL SARVAM TTS ---
        sarvam_rate = get_closest_sarvam_rate(sample_rate)
        print(f"Using Sarvam rate: {sarvam_rate} (Vapi requested: {sample_rate})")
 
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SARVAM_SPEAKER,
            "model": "bulbul:v3",
            "audio_format": "linear16",  # Raw PCM 16-bit
            "audio_sample_rate": sarvam_rate,
            "enable_preprocessing": True,
            "pace": 1.2,
        }
 
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        }
 
        print(f"Calling Sarvam: speaker={SARVAM_SPEAKER}, rate={sarvam_rate}, format=linear16")
 
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SARVAM_TTS_URL, json=payload, headers=headers
            )
 
        print(f"Sarvam status: {response.status_code}")
 
        if response.status_code != 200:
            print(f"Sarvam error: {response.text[:500]}")
            return Response(content=b"", status_code=200)
 
        result = response.json()
        audio_b64 = result.get("audios", [None])[0]
 
        if not audio_b64:
            print("No audio in response!")
            return Response(content=b"", status_code=200)
 
        # Decode base64 -> raw PCM bytes
        audio_bytes = base64.b64decode(audio_b64)
        print(f"Got {len(audio_bytes)} bytes of PCM audio at {sarvam_rate}Hz")
 
        # --- RETURN RAW PCM TO VAPI ---
        # Vapi docs say: return raw PCM with application/octet-stream
        # NO wav header, NO other encoding, just raw PCM bytes
        return Response(
            content=audio_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(audio_bytes)),
            },
        )
 
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b"", status_code=200)
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "speaker": SARVAM_SPEAKER}
 
 
@app.get("/")
async def root():
    return {"service": "DentaVoice TTS Bridge", "status": "running", "speaker": SARVAM_SPEAKER}
 
 
@app.get("/test")
async def test_voice(voice: str = "ritu"):
    test_text = "SmileCare Dental mein aapka swagat hai! Main Priya bol rahi hoon."
    payload = {
        "inputs": [test_text],
        "target_language_code": "hi-IN",
        "speaker": voice,
        "model": "bulbul:v3",
        "audio_format": "wav",
        "audio_sample_rate": 24000,
        "enable_preprocessing": True,
        "pace": 1.2,
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(SARVAM_TTS_URL, json=payload, headers=headers)
        if response.status_code != 200:
            return {"error": response.text[:300]}
        result = response.json()
        audio_b64 = result.get("audios", [None])[0]
        if not audio_b64:
            return {"error": "No audio"}
        audio_bytes = base64.b64decode(audio_b64)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        return {"error": str(e)}
 
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
