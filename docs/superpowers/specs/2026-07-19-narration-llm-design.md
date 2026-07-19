# VocNar v0.2 — Narration LLM

*Design validé le 19 juillet 2026.*

## Objectif

Remplacer les templates aléatoires par une vraie narration générée : le MJ écrit
chaque scène en tenant compte des choix des joueurs, juge la difficulté des
actions tentées, et conclut l'histoire. L'état du jeu migre côté backend ; le
front devient une couche d'affichage et d'audio.

## Décisions actées

| Sujet | Décision |
|---|---|
| Cerveau du MJ | API Claude, modèle `claude-haiku-4-5` ($1/$5 par MTok — une partie ≈ quelques centimes) |
| Structure narrative | Automate d'états backend : intro → scènes → climax → épilogue |
| Mécanique de jeu | d20 avec difficulté contextuelle fixée par le LLM, via tool use |
| Transport front↔back | `POST` simple (pas de streaming) ; WebSocket `/ws` supprimé |
| TTS | Inchangé (`speechSynthesis`) — item roadmap séparé |
| Persistance | Une seule partie en mémoire (dict Python), pas de BDD |

## Architecture

```
web/main.js ──POST /game/start──▶ backend/app.py ──▶ game/engine.py  (état, automate)
            ──POST /game/action─▶                ──▶ game/narrator.py (client Anthropic)
            ──POST /transcribe──▶ (Whisper, inchangé, chargement paresseux)
```

Le front ne contient plus aucune logique de jeu : `FRAG`, `BLUEPRINT`,
`render()` et le résolveur d20 disparaissent de `main.js`.

## Composants

### `backend/game/engine.py` — automate d'états

- `GameState` : config de partie (joueurs, noms, genre, durée), index de scène,
  nombre total de scènes, historique des messages (format API Anthropic).
- La durée choisie fixe le nombre de scènes : `max(2, durée // 5)` scènes
  puis épilogue (ex. 15 min → 3 scènes + épilogue).
- Phases : `intro` → `scene` (×N) → `climax` (dernière scène) → `epilogue`.
- **Aucun appel API dans ce module** — testable à sec.

### `backend/game/narrator.py` — client Anthropic

- Client `anthropic.Anthropic()`, clé lue depuis l'environnement.
- Construit le prompt système à partir de `scenes.json` : rôle de MJ, genre,
  personnages, directives de la phase courante, consignes de longueur
  (3 à 5 phrases par scène — c'est lu en TTS).
- Déclare l'outil `roll_d20` :

  ```json
  {
    "name": "roll_d20",
    "description": "Lance un d20 quand un joueur tente une action dont l'issue est incertaine. Ne pas l'utiliser pour un dialogue ou une question.",
    "input_schema": {
      "type": "object",
      "properties": {
        "difficulte": {"type": "integer", "description": "Seuil de réussite entre 5 (facile) et 19 (héroïque)"},
        "raison": {"type": "string", "description": "Pourquoi ce seuil, en une phrase"}
      },
      "required": ["difficulte", "raison"]
    }
  }
  ```

- Boucle manuelle : `messages.create(...)` ; si `stop_reason == "tool_use"`,
  le backend tire le d20, renvoie le `tool_result`
  (`"17 : réussite (seuil 14)"`), et récupère la narration finale. Un seul
  jet par action (l'outil est retiré au second tour pour garantir la
  terminaison).
- Retourne `{"texte": str, "jet": {"d20", "difficulte", "reussite", "raison"} | None}`.

### `backend/game/scenes.json` — données de prompt

Remplace les fragments aléatoires par :

- `genres` : une description d'ambiance par genre (fantastique, enquête,
  médiéval, policier), injectée dans le prompt système.
- `phases` : directives par phase (`intro`, `scene`, `climax`, `epilogue`),
  ex. pour `epilogue` : « conclus l'histoire, résous les fils ouverts,
  ne pose plus de question ».

### `backend/app.py` — routes

| Route | Rôle |
|---|---|
| `POST /game/start` | Crée la partie (remplace l'éventuelle partie en cours), retourne l'intro générée |
| `POST /game/action` | `{"text": ...}` → narration + jet éventuel + drapeau de fin |
| `POST /transcribe` | Inchangé, mais **chargement paresseux** de Whisper (premier appel) au lieu du chargement à l'import |
| `/ws` | **Supprimé** (code mort) |

Réponse de `/game/action` :

```json
{"texte": "...", "jet": {"d20": 17, "difficulte": 14, "reussite": true, "raison": "..."} , "fin": false}
```

(`jet` vaut `null` sans lancer ; `fin: true` quand l'épilogue est rendu.)

### `web/main.js` — front allégé

- `startBtn` → `POST /game/start`, affiche + lit l'intro.
- `sendBtn` → `POST /game/action` ; si `jet` non nul, affiche une ligne dé
  (`🎲 17 vs 14 — réussite !`) avant la narration ; si `fin`, désactive la saisie.
- Push-to-talk inchangé.
- Suppression de `FRAG`, `BLUEPRINT`, `render()`, `nextBeat()` et du résolveur d20.

## Configuration

- `ANTHROPIC_API_KEY` chargée via `python-dotenv` depuis `backend/.env`
  (déjà couvert par le `.gitignore`).
- Démarrage refusé avec message explicite si la clé est absente.
- Nouvelles dépendances : `anthropic`, `python-dotenv`.

## Gestion des erreurs

- Erreur ou timeout API → `503` avec message ; le front affiche
  « ⚠️ Le narrateur a une absence… réessayez. » L'action du joueur n'est pas
  consommée (l'historique n'est modifié qu'en cas de succès).
- `POST /game/action` sans partie démarrée → `409` avec message clair.
- Garde-fou : historique tronqué au-delà d'une limite large (~80 messages),
  improbable en une partie.

## Tests et CI

- `pytest` sur `engine.py` : calcul durée → nombre de scènes, progression des
  phases, détection de fin. Aucun réseau.
- Tests des routes avec le client Anthropic **mocké** (`unittest.mock`),
  y compris le chemin tool use (jet demandé → tool_result → narration).
- Le CI remplace l'« import check » par `pip install -r requirements.txt +
  pytest`. Le chargement paresseux de Whisper évite tout téléchargement de
  modèle en CI.
- Vérification manuelle finale : une mini-partie réelle avec la clé, micro
  inclus.

## Hors périmètre (roadmap ultérieure)

TTS réaliste (Piper/ElevenLabs), streaming/WebSocket, multi-joueurs distant,
cartes, effets sonores.
