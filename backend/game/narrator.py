import json
import random
from pathlib import Path

import anthropic

DATA = json.loads((Path(__file__).parent / "scenes.json").read_text(encoding="utf-8"))

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
        messages=list(messages),
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
            messages=list(messages),
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
