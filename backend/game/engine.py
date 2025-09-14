import json, random
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "scenes.json").read_text(encoding="utf-8"))

def render_prompt(tmpl: str) -> str:
    def pick(key):
        return random.choice(DATA["fragments"][key])
    return (tmpl
            .replace("{lieu}", pick("lieu"))
            .replace("{accroche}", pick("accroche"))
            .replace("{evenement}", pick("evenement"))
            .replace("{consequence}", pick("consequence")))

def generate_story_beats():
    beats = []
    for step in DATA["blueprint"]:
        beats.append({"id": step["id"], "text": render_prompt(step["prompt"])})
    return beats
