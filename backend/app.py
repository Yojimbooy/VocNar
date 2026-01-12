from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import json
import tempfile
import whisper

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Charger le modèle Whisper (base = bon compromis vitesse/qualité)
print("Chargement du modèle Whisper...")
whisper_model = whisper.load_model("base")
print("Modèle Whisper prêt.")

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Reçoit un fichier audio et retourne la transcription."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp.flush()
        result = whisper_model.transcribe(tmp.name, language="fr")
    return JSONResponse({"text": result["text"].strip()})

# Servir le front (doit être après les autres routes)
web_dir = Path(__file__).parent.parent / "web"
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    # Echo/dummy pour v0.1 : on peut déjà tester la boucle
    try:
        while True:
            msg = await ws.receive_text()
            # Ici, plus tard: router STT/intent/état → narration
            reply = json.dumps({"type": "server-echo", "text": f"Reçu: {msg}"})
            await ws.send_text(reply)
    except Exception:
        pass
