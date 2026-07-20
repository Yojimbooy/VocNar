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


def test_parse_segments_sans_tag():
    texte = "Vous arrivez au village. Que faites-vous ?"
    assert narrator.parse_segments(texte) == [
        {"locuteur": "narrateur", "texte": texte}
    ]


def test_parse_segments_narrateur_et_pnj():
    texte = (
        "[NARRATEUR] Le gardien surgit de l'ombre.\n"
        "[PNJ:Le Gardien] Qui ose troubler mon repos ?\n"
        "[NARRATEUR] Alice recule d'un pas."
    )
    assert narrator.parse_segments(texte) == [
        {"locuteur": "narrateur", "texte": "Le gardien surgit de l'ombre."},
        {"locuteur": "Le Gardien", "texte": "Qui ose troubler mon repos ?"},
        {"locuteur": "narrateur", "texte": "Alice recule d'un pas."},
    ]


def test_parse_segments_contenu_avant_premier_tag():
    texte = "Une brume s'installe.\n[PNJ:Voix] Approchez..."
    assert narrator.parse_segments(texte) == [
        {"locuteur": "narrateur", "texte": "Une brume s'installe."},
        {"locuteur": "Voix", "texte": "Approchez..."},
    ]


def test_parse_segments_ignore_segments_vides():
    texte = "[NARRATEUR][PNJ:Echo] Un cri résonne."
    assert narrator.parse_segments(texte) == [
        {"locuteur": "Echo", "texte": "Un cri résonne."},
    ]


def test_parse_segments_texte_vide():
    assert narrator.parse_segments("") == []


def test_prompt_systeme_contient_les_instructions_de_balisage():
    state = GameState(players=1, names=["Zoé"], genre="policier", duration=15)
    prompt = narrator.build_system_prompt(state)
    assert "[NARRATEUR]" in prompt
    assert "[PNJ:" in prompt
