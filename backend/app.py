from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Servir le front
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
