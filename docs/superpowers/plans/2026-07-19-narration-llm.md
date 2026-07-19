# VocNar v0.2 — Narration LLM : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer les templates aléatoires par une narration générée par l'API Claude, avec état du jeu côté backend, automate de scènes et jet de d20 à difficulté contextuelle via tool use.

**Architecture:** Le backend FastAPI porte tout l'état (une partie en mémoire). `engine.py` est un automate d'états pur (sans réseau), `narrator.py` encapsule le client Anthropic et la boucle tool use, `app.py` expose `POST /game/start` et `POST /game/action`. Le front `main.js` ne fait plus qu'afficher, lire en TTS et envoyer les actions.

**Tech Stack:** Python 3.9+, FastAPI, SDK `anthropic` (modèle `claude-haiku-4-5`), pytest, JS vanilla côté front.

**Spec de référence:** `docs/superpowers/specs/2026-07-19-narration-llm-design.md`

## Global Constraints

- Python 3.9+ (pas de syntaxe `X | Y` dans les annotations ; `list[str]` est OK).
- Modèle API : `claude-haiku-4-5`, `max_tokens=1024`.
- Tout le texte visible (UI, prompts, messages d'erreur) est en français.
- Messages de commit : courts, en français, sans corps ni Co-Authored-By.
- Clé API : `ANTHROPIC_API_KEY` dans `backend/.env` (jamais committée ; `.env` est déjà dans le `.gitignore`).
- Les tests ne font **aucun** appel réseau : client Anthropic mocké partout.
- Simplicité avant tout : pas d'abstraction au-delà de ce que le spec demande.
- Toutes les commandes se lancent depuis la racine du dépôt (`~/Documents/Vocnar/VocNar`), venv activé (`source .venv/bin/activate`).

---

### Task 1: Automate d'états (`engine.py`) + dépendances de test

**Files:**
- Modify: `backend/requirements.txt`
- Create: `conftest.py` (racine du dépôt)
- Rewrite: `backend/game/engine.py` (l'ancien contenu — `render_prompt`, `generate_story_beats` — disparaît ; rien ne l'importe)
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: rien.
- Produces: `GameState(players: int, names: list[str], genre: str, duration: int)` avec attributs `players`, `names`, `genre`, `duration`, `total_scenes`, `scene_index`, `messages` (list), méthodes `phase() -> str` (`"intro" | "scene" | "climax" | "epilogue"`), `advance() -> None`, propriété `finished -> bool`. Utilisé par les tâches 2, 3 et 4.

- [ ] **Step 1: Ajouter les dépendances**

Remplacer le contenu de `backend/requirements.txt` par :

```
fastapi
uvicorn[standard]
openai-whisper
python-multipart
anthropic
python-dotenv
pytest
httpx
```

Puis : `pip install -r backend/requirements.txt`

- [ ] **Step 2: Créer `conftest.py` à la racine**

Ce fichier met la racine du dépôt dans `sys.path` pour pytest et fournit une clé factice pour que `backend/app.py` s'importe en test :

```python
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "cle-de-test")
```

- [ ] **Step 3: Écrire les tests qui échouent**

Créer `tests/test_engine.py` :

```python
from backend.game.engine import GameState


def make_state(duration=15):
    return GameState(players=2, names=["Alice", "Bob"], genre="fantastique", duration=duration)


def test_total_scenes_depend_de_la_duree():
    assert make_state(duration=15).total_scenes == 3
    assert make_state(duration=60).total_scenes == 12


def test_total_scenes_minimum_2():
    assert make_state(duration=5).total_scenes == 2


def test_progression_des_phases():
    s = make_state(duration=15)  # 3 scènes : intro, scene, scene, climax, epilogue
    phases = []
    for _ in range(5):
        phases.append(s.phase())
        s.advance()
    assert phases == ["intro", "scene", "scene", "climax", "epilogue"]


def test_finished_seulement_apres_epilogue():
    s = make_state(duration=15)
    for _ in range(4):  # intro + 2 scènes + climax générés
        s.advance()
    assert s.phase() == "epilogue"
    assert not s.finished
    s.advance()  # épilogue généré
    assert s.finished


def test_etat_initial():
    s = make_state()
    assert s.scene_index == 0
    assert s.messages == []
```

- [ ] **Step 4: Vérifier que les tests échouent**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL / ERROR — `ImportError: cannot import name 'GameState'`

- [ ] **Step 5: Réécrire `backend/game/engine.py`**

Remplacer tout le contenu par :

```python
class GameState:
    """État d'une partie : configuration, progression des scènes, historique des messages.

    Aucun appel réseau ici : l'automate est testable à sec.
    Phases : intro (index 0) -> scene (1..total-1) -> climax (total) -> epilogue (total+1).
    """

    def __init__(self, players: int, names: list, genre: str, duration: int):
        self.players = players
        self.names = names
        self.genre = genre
        self.duration = duration
        self.total_scenes = max(2, duration // 5)
        self.scene_index = 0
        self.messages: list = []

    def phase(self) -> str:
        if self.scene_index == 0:
            return "intro"
        if self.scene_index < self.total_scenes:
            return "scene"
        if self.scene_index == self.total_scenes:
            return "climax"
        return "epilogue"

    def advance(self) -> None:
        self.scene_index += 1

    @property
    def finished(self) -> bool:
        return self.scene_index > self.total_scenes + 1
```

- [ ] **Step 6: Vérifier que les tests passent**

Run: `pytest tests/test_engine.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt conftest.py backend/game/engine.py tests/test_engine.py
git commit -m "moteur de jeu : automate d'états GameState"
```

---

### Task 2: Données de prompt (`scenes.json`) + prompt système

**Files:**
- Rewrite: `backend/game/scenes.json`
- Create: `backend/game/narrator.py` (partie données + prompt seulement ; `generate()` arrive en tâche 3)
- Test: `tests/test_narrator.py`

**Interfaces:**
- Consumes: `GameState` (tâche 1) — lit `state.genre`, `state.names`, `state.players`, `state.phase()`.
- Produces: `narrator.DATA` (dict chargé depuis `scenes.json`, clés `"genres"` et `"phases"`), `narrator.build_system_prompt(state) -> str`. Utilisés par les tâches 3 et 4.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_narrator.py` :

```python
from backend.game import narrator
from backend.game.engine import GameState


def test_data_contient_les_4_genres_et_4_phases():
    assert set(narrator.DATA["genres"]) == {"fantastique", "enquete", "medieval", "policier"}
    assert set(narrator.DATA["phases"]) == {"intro", "scene", "climax", "epilogue"}


def test_prompt_systeme_contient_genre_phase_et_noms():
    state = GameState(players=2, names=["Alice", "Bob"], genre="enquete", duration=15)
    prompt = narrator.build_system_prompt(state)
    assert narrator.DATA["genres"]["enquete"] in prompt
    assert narrator.DATA["phases"]["intro"] in prompt
    assert "Alice, Bob" in prompt


def test_prompt_systeme_suit_la_phase_courante():
    state = GameState(players=1, names=["Zoé"], genre="medieval", duration=15)
    for _ in range(4):
        state.advance()  # phase epilogue
    prompt = narrator.build_system_prompt(state)
    assert narrator.DATA["phases"]["epilogue"] in prompt
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `pytest tests/test_narrator.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'backend.game.narrator'`

- [ ] **Step 3: Réécrire `backend/game/scenes.json`**

Remplacer tout le contenu par :

```json
{
  "genres": {
    "fantastique": "un monde de magie sombre, de créatures anciennes et de mystères surnaturels",
    "enquete": "une enquête à indices, témoins et fausses pistes, dans une ville pluvieuse",
    "medieval": "un royaume médiéval de châteaux, d'intrigues de cour et de batailles",
    "policier": "un polar urbain contemporain, entre commissariat, indics et courses-poursuites"
  },
  "phases": {
    "intro": "Pose le décor, présente la situation initiale et implique chaque personnage nommé. Termine par une question du type « Que faites-vous ? »",
    "scene": "Fais rebondir l'histoire selon la dernière action des joueurs : une complication, une rencontre ou une découverte. Termine par une question ou un choix.",
    "climax": "C'est la scène décisive : monte la tension au maximum et confronte les joueurs à l'enjeu principal de l'histoire. Termine par une question ou un choix.",
    "epilogue": "Conclus l'histoire en tenant compte de tout ce qui s'est passé. Résous les fils ouverts. Ne pose plus aucune question."
  }
}
```

(Les clés de `genres` correspondent exactement aux `<option>` du select `#genre` de `web/index.html` : `fantastique`, `enquete`, `medieval`, `policier`.)

- [ ] **Step 4: Créer `backend/game/narrator.py`**

```python
import json
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "scenes.json").read_text(encoding="utf-8"))


def build_system_prompt(state) -> str:
    genre_desc = DATA["genres"][state.genre]
    phase_dir = DATA["phases"][state.phase()]
    noms = ", ".join(state.names)
    return (
        "Tu es un maître du jeu (MJ) qui anime une partie de jeu de rôle en français.\n"
        f"Ambiance : {genre_desc}.\n"
        f"Personnages joueurs : {noms} ({state.players} joueur(s)).\n"
        f"Consigne pour cette scène : {phase_dir}\n"
        "Réponds en 3 à 5 phrases : ton texte est lu à voix haute par un narrateur vocal.\n"
        "Utilise l'outil roll_d20 seulement quand un joueur tente une action à l'issue incertaine."
    )
```

- [ ] **Step 5: Vérifier que les tests passent**

Run: `pytest tests/test_narrator.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/game/scenes.json backend/game/narrator.py tests/test_narrator.py
git commit -m "narrateur : données de prompt par genre et par phase"
```

---

### Task 3: Boucle tool use du narrateur (`generate()`)

**Files:**
- Modify: `backend/game/narrator.py`
- Test: `tests/test_narrator.py` (ajout de tests)

**Interfaces:**
- Consumes: `GameState` (tâche 1), `build_system_prompt` / `DATA` (tâche 2).
- Produces: `narrator.generate(state, player_text=None) -> dict` retournant `{"texte": str, "jet": dict | None}` avec `jet = {"d20": int, "difficulte": int, "reussite": bool, "raison": str}`. Modifie `state.messages` **uniquement en cas de succès**. `narrator.get_client()` (point de mock des tests). Utilisés par la tâche 4.

- [ ] **Step 1: Ajouter les tests qui échouent**

Ajouter à la fin de `tests/test_narrator.py` :

```python
from types import SimpleNamespace

import pytest


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(difficulte, raison="serrure complexe"):
    return SimpleNamespace(
        type="tool_use",
        id="toolu_01",
        name="roll_d20",
        input={"difficulte": difficulte, "raison": raison},
    )


class FakeClient:
    """Rejoue une liste de réponses préparées et enregistre les appels."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_generate_sans_jet(monkeypatch):
    fake = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[text_block("Vous arrivez au village.")]),
    ])
    monkeypatch.setattr(narrator, "get_client", lambda: fake)
    state = GameState(players=2, names=["Alice", "Bob"], genre="fantastique", duration=15)

    result = narrator.generate(state)

    assert result == {"texte": "Vous arrivez au village.", "jet": None}
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "claude-haiku-4-5"
    # l'historique est committé : question du joueur + réponse du MJ
    assert state.messages[0] == {"role": "user", "content": "Commence la partie."}
    assert state.messages[-1] == {"role": "assistant", "content": "Vous arrivez au village."}


def test_generate_avec_jet(monkeypatch):
    fake = FakeClient([
        SimpleNamespace(stop_reason="tool_use", content=[tool_block(14)]),
        SimpleNamespace(stop_reason="end_turn", content=[text_block("Le pêne cède dans un cliquetis.")]),
    ])
    monkeypatch.setattr(narrator, "get_client", lambda: fake)
    monkeypatch.setattr(narrator.random, "randint", lambda a, b: 17)
    state = GameState(players=2, names=["Alice", "Bob"], genre="fantastique", duration=15)
    state.advance()  # phase "scene"

    result = narrator.generate(state, "Je crochette la serrure")

    assert result["texte"] == "Le pêne cède dans un cliquetis."
    assert result["jet"] == {"d20": 17, "difficulte": 14, "reussite": True, "raison": "serrure complexe"}
    # le second appel interdit un nouveau jet et transmet le tool_result
    assert fake.calls[1]["tool_choice"] == {"type": "none"}
    dernier = fake.calls[1]["messages"][-1]
    assert dernier["role"] == "user"
    assert dernier["content"][0]["type"] == "tool_result"
    assert dernier["content"][0]["tool_use_id"] == "toolu_01"


def test_generate_echec_du_jet(monkeypatch):
    fake = FakeClient([
        SimpleNamespace(stop_reason="tool_use", content=[tool_block(15)]),
        SimpleNamespace(stop_reason="end_turn", content=[text_block("La serrure résiste.")]),
    ])
    monkeypatch.setattr(narrator, "get_client", lambda: fake)
    monkeypatch.setattr(narrator.random, "randint", lambda a, b: 3)
    state = GameState(players=1, names=["Zoé"], genre="policier", duration=15)
    state.advance()

    result = narrator.generate(state, "Je force la porte")

    assert result["jet"]["reussite"] is False
    assert "échec" in fake.calls[1]["messages"][-1]["content"][0]["content"]


def test_generate_erreur_ne_modifie_pas_l_historique(monkeypatch):
    class Boom(Exception):
        pass

    def failing_create(**kwargs):
        raise Boom()

    fake = SimpleNamespace(messages=SimpleNamespace(create=failing_create))
    monkeypatch.setattr(narrator, "get_client", lambda: fake)
    state = GameState(players=1, names=["Zoé"], genre="policier", duration=15)
    state.messages.append({"role": "user", "content": "tour précédent"})

    with pytest.raises(Boom):
        narrator.generate(state, "Je fonce")

    assert state.messages == [{"role": "user", "content": "tour précédent"}]
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `pytest tests/test_narrator.py -v`
Expected: les 3 tests de la tâche 2 passent, les 4 nouveaux FAIL — `AttributeError: module ... has no attribute 'generate'` (ou `get_client`)

- [ ] **Step 3: Implémenter `generate()`**

Dans `backend/game/narrator.py`, remplacer les imports du haut et ajouter à la suite de `build_system_prompt` :

```python
import json
import random
from pathlib import Path

import anthropic

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024
MAX_HISTORY = 80

ROLL_TOOL = {
    "name": "roll_d20",
    "description": (
        "Lance un d20 quand un joueur tente une action dont l'issue est incertaine. "
        "Ne pas l'utiliser pour un dialogue, une question ou une action triviale."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "difficulte": {
                "type": "integer",
                "description": "Seuil de réussite entre 5 (facile) et 19 (héroïque)",
            },
            "raison": {
                "type": "string",
                "description": "Pourquoi ce seuil, en une phrase",
            },
        },
        "required": ["difficulte", "raison"],
    },
}

_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client
```

Puis, toujours dans `narrator.py`, après `build_system_prompt` :

```python
def _extract_text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def generate(state, player_text=None):
    """Génère la narration de la phase courante.

    Ne modifie state.messages qu'en cas de succès : en cas d'exception,
    l'action du joueur n'est pas consommée et il peut réessayer.
    """
    messages = list(state.messages)
    messages.append({"role": "user", "content": player_text or "Commence la partie."})

    client = get_client()
    system = build_system_prompt(state)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=[ROLL_TOOL],
        messages=messages,
    )

    jet = None
    if response.stop_reason == "tool_use":
        bloc = next(b for b in response.content if b.type == "tool_use")
        d20 = random.randint(1, 20)
        difficulte = int(bloc.input["difficulte"])
        reussite = d20 >= difficulte
        jet = {
            "d20": d20,
            "difficulte": difficulte,
            "reussite": reussite,
            "raison": bloc.input.get("raison", ""),
        }
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": bloc.id,
                "content": f"{d20} : {'réussite' if reussite else 'échec'} (seuil {difficulte})",
            }],
        })
        # tool_choice "none" garantit un seul jet par action (terminaison de la boucle)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[ROLL_TOOL],
            tool_choice={"type": "none"},
            messages=messages,
        )

    texte = _extract_text(response)
    messages.append({"role": "assistant", "content": texte})

    if len(messages) > MAX_HISTORY:
        # garde la fin, en retombant sur un tour utilisateur "simple"
        messages = messages[-MAX_HISTORY:]
        while messages and not (
            messages[0]["role"] == "user" and isinstance(messages[0]["content"], str)
        ):
            messages.pop(0)

    state.messages[:] = messages
    return {"texte": texte, "jet": jet}
```

- [ ] **Step 4: Vérifier que tous les tests passent**

Run: `pytest tests/ -v`
Expected: 12 passed (5 engine + 7 narrator)

- [ ] **Step 5: Commit**

```bash
git add backend/game/narrator.py tests/test_narrator.py
git commit -m "narrateur : génération Claude avec jet de d20 en tool use"
```

---

### Task 4: Routes de jeu (`app.py`), Whisper paresseux, suppression du WebSocket

**Files:**
- Rewrite: `backend/app.py`
- Create: `backend/.env.example`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `GameState` (tâche 1), `narrator.generate` / `narrator.DATA` (tâches 2-3).
- Produces: `POST /game/start` (body `{"players": int, "names": list[str], "genre": str, "duration": int}`) et `POST /game/action` (body `{"text": str}`), réponse commune `{"texte": str, "jet": dict | null, "fin": bool}`. Erreurs : 409 (pas de partie / partie finie), 422 (genre inconnu, validation), 503 (API indisponible). Consommé par la tâche 5 (front).

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_app.py` :

```python
import sys

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module

client = TestClient(app_module.app)

START_PAYLOAD = {"players": 2, "names": ["Alice", "Bob"], "genre": "fantastique", "duration": 10}


@pytest.fixture(autouse=True)
def partie_vierge():
    app_module.GAME["state"] = None
    yield


def fake_generate(state, player_text=None):
    return {"texte": "Il était une fois.", "jet": None}


def test_import_app_ne_charge_pas_whisper():
    assert "whisper" not in sys.modules


def test_start_cree_une_partie(monkeypatch):
    monkeypatch.setattr(app_module.narrator, "generate", fake_generate)
    resp = client.post("/game/start", json=START_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json() == {"texte": "Il était une fois.", "jet": None, "fin": False}
    assert app_module.GAME["state"].phase() == "scene"


def test_start_genre_inconnu():
    resp = client.post("/game/start", json={**START_PAYLOAD, "genre": "western"})
    assert resp.status_code == 422


def test_action_sans_partie():
    resp = client.post("/game/action", json={"text": "J'attaque"})
    assert resp.status_code == 409


def test_partie_complete_jusqu_a_la_fin(monkeypatch):
    monkeypatch.setattr(app_module.narrator, "generate", fake_generate)
    client.post("/game/start", json=START_PAYLOAD)  # durée 10 -> 2 scènes
    fins = [
        client.post("/game/action", json={"text": "On avance"}).json()["fin"]
        for _ in range(3)  # scène, climax, épilogue
    ]
    assert fins == [False, False, True]
    # la partie est finie : plus d'action possible
    assert client.post("/game/action", json={"text": "encore"}).status_code == 409


def test_erreur_api_renvoie_503_sans_consommer_l_action(monkeypatch):
    monkeypatch.setattr(app_module.narrator, "generate", fake_generate)
    client.post("/game/start", json=START_PAYLOAD)
    index_avant = app_module.GAME["state"].scene_index

    def failing(state, player_text=None):
        raise anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

    monkeypatch.setattr(app_module.narrator, "generate", failing)
    resp = client.post("/game/action", json={"text": "Je tente"})
    assert resp.status_code == 503
    assert app_module.GAME["state"].scene_index == index_avant


def test_le_websocket_a_disparu():
    with open("backend/app.py", encoding="utf-8") as f:
        source = f.read()
    assert "websocket" not in source.lower()


def test_le_front_est_servi():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "VocNar" in resp.text
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `pytest tests/test_app.py -v`
Expected: FAIL — `/game/start` renvoie 404 (route absente), `test_le_websocket_a_disparu` échoue, etc. (`test_import_app_ne_charge_pas_whisper` échoue aussi tant que l'ancien `app.py` charge Whisper à l'import — l'import peut d'ailleurs être long, c'est le symptôme).

- [ ] **Step 3: Réécrire `backend/app.py`**

Remplacer tout le contenu par :

```python
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
    return {"texte": result["texte"], "jet": None, "fin": False}


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
    return {"texte": result["texte"], "jet": result["jet"], "fin": state.finished}


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
```

- [ ] **Step 4: Créer `backend/.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Vérifier que tous les tests passent**

Run: `pytest tests/ -v`
Expected: 20 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app.py backend/.env.example tests/test_app.py
git commit -m "routes de jeu, whisper paresseux, suppression du websocket"
```

---

### Task 5: Front allégé (`main.js`)

**Files:**
- Rewrite: `web/main.js`
- Modify: `web/index.html:41` (placeholder du champ réponse)

**Interfaces:**
- Consumes: `POST /game/start` et `POST /game/action` (tâche 4), `POST /transcribe` (inchangé).
- Produces: rien (feuille de l'arbre). Pas de test automatisé (JS vanilla sans harnais) : vérification manuelle en tâche 7.

- [ ] **Step 1: Réécrire `web/main.js`**

Remplacer tout le contenu par :

```javascript
// v0.2 : narration générée côté backend (API Claude) ; le front affiche, lit en TTS et envoie les actions
const logEl = document.getElementById("log");
const startBtn = document.getElementById("start");
const sendBtn = document.getElementById("sendReply");
const replyInput = document.getElementById("replyText");
const pttBtn = document.getElementById("ptt");

function say(text) {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";
  speechSynthesis.speak(u);
}

function addMsg(text, who = "mj") {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = (who === "mj" ? "MJ: " : "Joueur: ") + text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function setBusy(busy) {
  startBtn.disabled = busy;
  sendBtn.disabled = busy;
}

function endGame() {
  sendBtn.disabled = true;
  replyInput.disabled = true;
  pttBtn.disabled = true;
}

async function callGame(url, payload) {
  setBusy(true);
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      addMsg(`⚠️ ${err.detail || "Erreur serveur."}`, "mj");
      return null;
    }
    return await resp.json();
  } catch (e) {
    addMsg("⚠️ Impossible de joindre le serveur.", "mj");
    return null;
  } finally {
    setBusy(false);
  }
}

function showTurn(data) {
  if (data.jet) {
    const j = data.jet;
    addMsg(`🎲 d20 = ${j.d20} vs ${j.difficulte} — ${j.reussite ? "réussite !" : "échec…"} (${j.raison})`, "mj");
  }
  addMsg(data.texte, "mj");
  say(data.texte);
  if (data.fin) {
    addMsg("🏁 La partie est terminée. Relance une partie pour rejouer.", "mj");
    endGame();
  }
}

startBtn.addEventListener("click", async () => {
  logEl.innerHTML = "";
  sendBtn.disabled = false;
  replyInput.disabled = false;
  pttBtn.disabled = false;

  const names = (document.getElementById("names").value || "Alice; Bob; Charly")
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
  const payload = {
    players: parseInt(document.getElementById("players").value, 10),
    names,
    genre: document.getElementById("genre").value,
    duration: parseInt(document.getElementById("duration").value, 10),
  };
  addMsg("Le MJ prépare la partie…", "mj");
  const data = await callGame("/game/start", payload);
  if (data) showTurn(data);
});

sendBtn.addEventListener("click", async () => {
  const txt = replyInput.value.trim();
  if (!txt) return;
  addMsg(txt, "player");
  replyInput.value = "";
  const data = await callGame("/game/action", { text: txt });
  if (data) showTurn(data);
});

// --- Push-to-talk (Whisper) : inchangé depuis la v0.1 ---
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function initMicrophone() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      pttBtn.textContent = "⏳ Transcription...";
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];

      const formData = new FormData();
      formData.append("audio", audioBlob, "audio.webm");

      try {
        const resp = await fetch("/transcribe", { method: "POST", body: formData });
        const data = await resp.json();
        if (data.text) {
          replyInput.value = data.text;
          setTimeout(() => sendBtn.click(), 200);
        }
      } catch (err) {
        addMsg("⚠️ Erreur lors de la transcription.", "mj");
      }

      pttBtn.textContent = "🎤 Parler";
      pttBtn.style.background = "";
      isRecording = false;
    };

    return true;
  } catch (err) {
    addMsg("⚠️ Impossible d'accéder au microphone.", "mj");
    return false;
  }
}

function toggleRecording() {
  if (!mediaRecorder) {
    initMicrophone().then((ok) => {
      if (ok) toggleRecording();
    });
    return;
  }

  if (isRecording) {
    mediaRecorder.stop();
    isRecording = false;
  } else {
    audioChunks = [];
    mediaRecorder.start();
    isRecording = true;
    pttBtn.textContent = "🔴 Écoute...";
    pttBtn.style.background = "#5a2a2a";
  }
}

pttBtn.addEventListener("click", toggleRecording);
```

- [ ] **Step 2: Mettre à jour le placeholder**

Dans `web/index.html`, ligne 41, remplacer :

```html
        <input id="replyText" type="text" placeholder="Répondez ici (v0.1)">
```

par :

```html
        <input id="replyText" type="text" placeholder="Que faites-vous ?">
```

- [ ] **Step 3: Vérification rapide sans clé réelle**

Run: `grep -c "BLUEPRINT\|FRAG\|nextBeat\|randomPick" web/main.js`
Expected: `0` (toute la logique de jeu locale a disparu)

Run: `pytest tests/ -q`
Expected: 20 passed (rien n'a cassé côté backend)

- [ ] **Step 4: Commit**

```bash
git add web/main.js web/index.html
git commit -m "front : affichage et TTS seulement, logique de jeu côté backend"
```

---

### Task 6: CI et README

**Files:**
- Modify: `.github/workflows/ci.yml` (étape "Lint (import check)")
- Modify: `README.md`

**Interfaces:**
- Consumes: la suite pytest (tâches 1-4).
- Produces: rien.

- [ ] **Step 1: Remplacer l'import check par pytest dans le CI**

Dans `.github/workflows/ci.yml`, remplacer l'étape :

```yaml
    - name: Lint (import check)
      run: |
        source .venv/bin/activate
        python -c "import fastapi, uvicorn; print('✅ FastAPI et Uvicorn sont installés')"
```

par :

```yaml
    - name: Tests
      run: |
        source .venv/bin/activate
        pytest -q
```

(Le `conftest.py` fournit une clé factice et le chargement paresseux de Whisper évite tout téléchargement de modèle : les tests ne font aucun appel réseau.)

- [ ] **Step 2: Mettre à jour le README**

Dans `README.md` :

1. Dans la section **Étapes**, après l'étape 3 (« Installer les dépendances »), insérer une nouvelle étape :

```markdown
4. **Configurer la clé API Anthropic**

   La narration est générée par l'API Claude (modèle Haiku). Crée `backend/.env` :

   ```bash
   cp backend/.env.example backend/.env
   # puis édite backend/.env et colle ta clé ANTHROPIC_API_KEY
   ```

   Une partie coûte quelques centimes.
```

(et renuméroter les étapes suivantes : « Lancer le serveur » devient 5, « Ouvrir le navigateur » devient 6).

2. Dans la section **Prévisions (MVP -> futur)**, cocher les deux items livrés :

```markdown
- [x] Système de jeu amélioré (difficulté contextuelle)
- [x] Automate d'états (intro -> dilemme -> climax -> épilogue)
```

3. Dans la section **Utilisation**, remplacer la phrase finale « Le MJ réagit et propose la scène suivante. » par :

```markdown
5. Le MJ (API Claude) écrit chaque scène selon vos choix, juge la difficulté
   des actions tentées (jet de d20 visible) et conclut l'histoire à la fin
   de la durée choisie.
```

- [ ] **Step 3: Vérifier la syntaxe du workflow**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"`
Expected: `OK` (si `yaml` n'est pas installé : `pip install pyyaml` ou vérification visuelle de l'indentation)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci : pytest à la place de l'import check, maj README"
```

---

### Task 7: Vérification manuelle de bout en bout

**Files:** aucun (vérification).

**Interfaces:**
- Consumes: tout ce qui précède + une vraie clé API dans `backend/.env`.

- [ ] **Step 1: Vérifier la présence de la clé**

Run: `test -f backend/.env && grep -q "ANTHROPIC_API_KEY=sk-" backend/.env && echo "clé présente" || echo "MANQUANTE"`
Expected: `clé présente` — sinon, demander à Florian de créer `backend/.env` à partir de `backend/.env.example`.

- [ ] **Step 2: Lancer le serveur**

Run: `uvicorn backend.app:app --reload --port 8000`
Expected: démarrage sans erreur, **sans** le message « Chargement du modèle Whisper » (chargement paresseux).

- [ ] **Step 3: Mini-partie réelle au curl (10 minutes de jeu → 2 scènes)**

```bash
curl -s -X POST http://127.0.0.1:8000/game/start \
  -H "Content-Type: application/json" \
  -d '{"players": 2, "names": ["Alice", "Bob"], "genre": "fantastique", "duration": 10}'
```

Expected: JSON `{"texte": "...", "jet": null, "fin": false}` avec une intro en français qui nomme Alice et Bob et se termine par une question.

```bash
curl -s -X POST http://127.0.0.1:8000/game/action \
  -H "Content-Type: application/json" \
  -d '{"text": "Alice escalade la muraille pendant que Bob fait le guet"}'
```

Expected: réponse cohérente avec l'action ; `jet` non nul attendu (action risquée) avec `difficulte` entre 5 et 19.

Enchaîner 2 actions de plus : la dernière réponse doit avoir `"fin": true` et un texte de conclusion sans question. Une action supplémentaire doit renvoyer un 409.

- [ ] **Step 4: Vérification navigateur, micro inclus**

Ouvrir http://127.0.0.1:8000 : lancer une partie, vérifier l'affichage de la ligne 🎲 lors d'un jet, la lecture TTS, le push-to-talk (🎤 → parler → transcription → envoi auto), et la désactivation de la saisie à la fin.

- [ ] **Step 5: Rapport**

Rapporter à Florian : coût observé de la partie (visible sur la console Anthropic), qualité de la narration Haiku en français, et toute bizarrerie (jets trop fréquents/rares, longueurs de scène).
