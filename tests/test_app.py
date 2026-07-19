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
