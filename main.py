from fastapi import FastAPI, Request, Response
import httpx
import base64
import os
 
app = FastAPI()
 
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "your-key-here")
SARVAM_SPEAKER = os.environ.get("SARVAM_SPEAKER", "ritu")
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
 
 
@app.post("/tts")
async def custom_tts(request: Request):
    try:
        body = await request.json()
        print(f"Received from Vapi: {list(body.keys())}")
        print(f"Full body: {body}")
 
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
            print(f"WARNING: No text in payload.")
            return Response(content=b"", status_code=200)
 
        # Sarvam TTS - using mulaw at 8kHz (telephony standard)
        # This is what voice pipelines like Vapi typically expect
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SARVAM_SPEAKER,
            "model": "bulbul:v3",
            "audio_format": "mulaw",
            "audio_sample_rate": 8000,
            "enable_preprocessing": True,
            "pace": 1.2,
        }
 
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        }
 
        print(f"Calling Sarvam: speaker={SARVAM_SPEAKER}, format=mulaw, rate=8000, pace=1.2")
 
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers,
            )
 
        print(f"Sarvam status: {response.status_code}")
 
        if response.status_code != 200:
            print(f"Sarvam error: {response.status_code} - {response.text[:500]}")
            return Response(content=b"", status_code=200)
 
        result = response.json()
        audio_b64 = result.get("audios", [None])[0]
 
        if not audio_b64:
            print("No audio in Sarvam response!")
            return Response(content=b"", status_code=200)
 
        audio_bytes = base64.b64decode(audio_b64)
        print(f"Got {len(audio_bytes)} bytes of mulaw audio")
 
        # Return raw mulaw audio - no headers, no wrapper
        # Content-Type audio/basic is the standard for mulaw
        return Response(
            content=audio_bytes,
            media_type="audio/basic",
        )
 
    except Exception as e:
        print(f"Error in /tts: {e}")
        import traceback
        traceback.print_exc()
        return Response(content=b"", status_code=200)
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "dentavoice-tts-bridge", "speaker": SARVAM_SPEAKER}
 
 
@app.get("/")
async def root():
    return {
        "service": "DentaVoice TTS Bridge",
        "status": "running",
        "speaker": SARVAM_SPEAKER,
    }
 
 
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
            return {"error": f"Sarvam returned {response.status_code}", "detail": response.text[:300]}
 
        result = response.json()
        audio_b64 = result.get("audios", [None])[0]
        if not audio_b64:
            return {"error": "No audio returned"}
 
        audio_bytes = base64.b64decode(audio_b64)
        return Response(content=audio_bytes, media_type="audio/wav")
 
    except Exception as e:
        return {"error": str(e)}
 
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
