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
