import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.game import narrator
from backend.game.engine import GameState

load_dotenv(Path(__file__).parent / ".env")
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "ANTHROPIC_API_KEY manquante : crée backend/.env avec ANTHROPIC_API_KEY=sk-ant-..."
    )

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Une seule partie en mémoire (prototype mono-table)
GAME: dict = {"state": None}


class StartRequest(BaseModel):
    players: int = Field(ge=1, le=6)
    names: list
    genre: str
    duration: int = Field(ge=5, le=120)


class ActionRequest(BaseModel):
    text: str


@app.post("/game/start")
def game_start(req: StartRequest):
    if req.genre not in narrator.DATA["genres"]:
        raise HTTPException(status_code=422, detail=f"Genre inconnu : {req.genre}")
    state = GameState(players=req.players, names=req.names, genre=req.genre, duration=req.duration)
    try:
        result = narrator.generate(state)
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="Le narrateur est indisponible, réessayez.")
    GAME["state"] = state
    state.advance()
    return {"segments": result["segments"], "jet": result["jet"], "fin": False}


@app.post("/game/action")
def game_action(req: ActionRequest):
    state = GAME["state"]
    if state is None:
        raise HTTPException(status_code=409, detail="Aucune partie en cours.")
    if state.finished:
        raise HTTPException(status_code=409, detail="La partie est terminée, relance une partie.")
    try:
        result = narrator.generate(state, req.text)
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="Le narrateur est indisponible, réessayez.")
    state.advance()
    return {"segments": result["segments"], "jet": result["jet"], "fin": state.finished}


# --- Transcription Whisper (chargement paresseux : rien à l'import) ---
_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("base")
    return _whisper_model


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp.flush()
        result = get_whisper_model().transcribe(tmp.name, language="fr")
    return JSONResponse({"text": result["text"].strip()})


# Le mount attrape toutes les routes restantes : il doit rester déclaré en DERNIER
web_dir = Path(__file__).parent.parent / "web"
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
