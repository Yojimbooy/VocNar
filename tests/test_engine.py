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
