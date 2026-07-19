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
