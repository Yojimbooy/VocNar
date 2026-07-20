# VocNar v0.3 — Voix narrateur/PNJ : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner une voix distincte au narrateur et à chaque PNJ que le MJ fait parler, via des tags inline dans le texte du LLM et les voix système `speechSynthesis` du navigateur, sans nouvelle infrastructure serveur.

**Architecture:** Le LLM balise sa réponse (`[NARRATEUR]` / `[PNJ:Nom]`). `backend/game/narrator.py` parse ces tags en segments `{locuteur, texte}` avant de renvoyer la réponse ; le texte brut avec tags continue d'être stocké dans l'historique de conversation. Le front associe une voix fixe au narrateur et une voix dérivée d'un hash du nom à chaque PNJ, puis enchaîne les segments dans la file d'attente native de `speechSynthesis`.

**Tech Stack:** Python 3.9+ (`re` de la stdlib), FastAPI, `speechSynthesis` du navigateur (aucune nouvelle dépendance).

**Spec de référence:** `docs/superpowers/specs/2026-07-20-voix-narrateur-pnj-design.md`

## Global Constraints

- Python 3.9+ ; tout le texte visible en français.
- Messages de commit : courts, en français, une ligne, sans Co-Authored-By.
- Format de balisage exact : `[NARRATEUR]` et `[PNJ:Nom du PNJ]` — aucune variante.
- Si le LLM omet les tags, tout le texte devient un seul segment `narrateur` (jamais d'erreur, dégradation silencieuse).
- Le texte brut avec tags reste committé dans `state.messages` tel quel ; `parse_segments` n'agit qu'au moment de construire la valeur de retour.
- Un PNJ donné garde la même voix pendant toute la partie, dérivée d'un hash de son nom — aucun état supplémentaire à stocker côté backend.
- Aucune nouvelle dépendance ni infrastructure serveur pour la voix (pas de Piper, pas de moteur TTS local).
- Les tests Python ne font aucun appel réseau.
- Toutes les commandes se lancent depuis la racine du dépôt (`~/Documents/Vocnar/VocNar`), venv activé (`source .venv/bin/activate`).

---

### Task 1: `parse_segments()` + instructions de balisage dans le prompt système

**Files:**
- Modify: `backend/game/narrator.py` (ajout d'un import, d'une constante regex, d'une fonction, et extension de `build_system_prompt`)
- Test: `tests/test_narrator.py` (ajout de tests, aucun test existant modifié)

**Interfaces:**
- Consumes: rien de nouveau.
- Produces: `narrator.parse_segments(texte: str) -> list[dict]`, chaque élément `{"locuteur": str, "texte": str}`. `locuteur` vaut `"narrateur"` ou le nom du PNJ (tel qu'écrit après `[PNJ:...]`, sans les crochets). Utilisé par la tâche 2.

Ce module est entièrement additif : aucun test existant ne doit changer, `generate()` n'est pas encore touché.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_narrator.py` :

```python
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
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `pytest tests/test_narrator.py -v`
Expected: les tests existants passent, les 6 nouveaux FAIL — `AttributeError: module ... has no attribute 'parse_segments'` (et le dernier échoue faute des instructions de balisage dans le prompt)

- [ ] **Step 3: Ajouter l'import et la fonction `parse_segments`**

Dans `backend/game/narrator.py`, remplacer la ligne d'import :

```python
import json
import random
from pathlib import Path
```

par :

```python
import json
import random
import re
from pathlib import Path
```

Puis, juste après la définition de `ROLL_TOOL` (avant `_client = None`), ajouter :

```python
_TAG_RE = re.compile(r"\[(NARRATEUR)\]|\[PNJ:([^\]]+)\]")


def parse_segments(texte: str) -> list:
    """Découpe un texte balisé en segments {locuteur, texte}.

    Sans balise reconnue, tout le texte devient un seul segment narrateur
    (dégradation silencieuse si le LLM oublie le format).
    """
    matches = list(_TAG_RE.finditer(texte))
    if not matches:
        contenu = texte.strip()
        return [{"locuteur": "narrateur", "texte": contenu}] if contenu else []

    segments = []
    tete = texte[: matches[0].start()].strip()
    if tete:
        segments.append({"locuteur": "narrateur", "texte": tete})

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(texte)
        contenu = texte[start:end].strip()
        if not contenu:
            continue
        locuteur = "narrateur" if m.group(1) else m.group(2).strip()
        segments.append({"locuteur": locuteur, "texte": contenu})
    return segments
```

- [ ] **Step 4: Étendre `build_system_prompt` avec les instructions de balisage**

Dans `backend/game/narrator.py`, remplacer :

```python
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

par :

```python
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
        "Utilise l'outil roll_d20 seulement quand un joueur tente une action à l'issue incertaine.\n"
        "Structure ta réponse en balisant chaque segment : fais précéder chaque passage de "
        "narration par [NARRATEUR] et chaque réplique d'un PNJ par [PNJ:Nom du PNJ]. "
        "N'utilise jamais de guillemets pour les dialogues, seulement ce balisage. Exemple :\n"
        "[NARRATEUR] Le gardien surgit de l'ombre, son regard perçant les ténèbres.\n"
        "[PNJ:Le Gardien] Qui ose troubler mon repos ?\n"
        "[NARRATEUR] Alice recule d'un pas, la main sur son épée."
    )
```

- [ ] **Step 5: Vérifier que tous les tests passent**

Run: `pytest tests/ -v`
Expected: 26 passed (20 précédents + 6 nouveaux)

- [ ] **Step 6: Commit**

```bash
git add backend/game/narrator.py tests/test_narrator.py
git commit -m "narrateur : balisage locuteur et fonction parse_segments"
```

---

### Task 2: `generate()` renvoie des segments

**Files:**
- Modify: `backend/game/narrator.py:125` (une seule ligne)
- Test: `tests/test_narrator.py` (3 tests existants modifiés, 1 test ajouté)

**Interfaces:**
- Consumes: `narrator.parse_segments` (tâche 1).
- Produces: `narrator.generate(state, player_text=None) -> {"segments": list[dict], "jet": dict | None}` — remplace l'ancienne forme `{"texte": str, "jet": ...}`. Utilisé par la tâche 3.

- [ ] **Step 1: Modifier les tests existants pour la nouvelle forme de retour**

Dans `tests/test_narrator.py`, remplacer :

```python
    assert result == {"texte": "Vous arrivez au village.", "jet": None}
```

par :

```python
    assert result == {
        "segments": [{"locuteur": "narrateur", "texte": "Vous arrivez au village."}],
        "jet": None,
    }
```

(dans `test_generate_sans_jet`)

Remplacer :

```python
    assert result["texte"] == "Le pêne cède dans un cliquetis."
```

par :

```python
    assert result["segments"] == [
        {"locuteur": "narrateur", "texte": "Le pêne cède dans un cliquetis."}
    ]
```

(dans `test_generate_avec_jet` — le reste du test, y compris les assertions sur `fake.calls`, ne change pas)

`test_generate_echec_du_jet` et `test_generate_erreur_ne_modifie_pas_l_historique` ne référencent pas `result["texte"]` : aucun changement nécessaire pour ces deux tests.

- [ ] **Step 2: Ajouter un test d'intégration avec un PNJ**

Ajouter à la fin de `tests/test_narrator.py` :

```python
def test_generate_segments_avec_pnj(monkeypatch):
    texte_llm = "[NARRATEUR] Le vent siffle.\n[PNJ:Ombre] Approche...\n"
    fake = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[text_block(texte_llm)]),
    ])
    monkeypatch.setattr(narrator, "get_client", lambda: fake)
    state = GameState(players=1, names=["Zoé"], genre="fantastique", duration=15)

    result = narrator.generate(state)

    assert result["segments"] == [
        {"locuteur": "narrateur", "texte": "Le vent siffle."},
        {"locuteur": "Ombre", "texte": "Approche..."},
    ]
    # l'historique conserve le texte brut avec balises, pour la cohérence du LLM d'un tour à l'autre
    assert state.messages[-1] == {"role": "assistant", "content": texte_llm}
```

- [ ] **Step 3: Vérifier que les tests échouent**

Run: `pytest tests/test_narrator.py -v`
Expected: `test_generate_sans_jet`, `test_generate_avec_jet` et `test_generate_segments_avec_pnj` FAIL (la fonction renvoie encore `"texte"`)

- [ ] **Step 4: Modifier `generate()`**

Dans `backend/game/narrator.py`, remplacer la dernière ligne de `generate()` :

```python
    state.messages[:] = messages
    return {"texte": texte, "jet": jet}
```

par :

```python
    state.messages[:] = messages
    return {"segments": parse_segments(texte), "jet": jet}
```

- [ ] **Step 5: Vérifier que tous les tests passent**

Run: `pytest tests/ -v`
Expected: 27 passed

- [ ] **Step 6: Commit**

```bash
git add backend/game/narrator.py tests/test_narrator.py
git commit -m "narrateur : generate() renvoie des segments locuteur/texte"
```

---

### Task 3: Routes `/game/start` et `/game/action` renvoient des segments

**Files:**
- Modify: `backend/app.py:54,69`
- Test: `tests/test_app.py` (`fake_generate` et une assertion modifiées, tests restants inchangés)

**Interfaces:**
- Consumes: `narrator.generate()` (tâche 2) — clé `result["segments"]` au lieu de `result["texte"]`.
- Produces: réponse JSON `/game/start` et `/game/action` : `{"segments": [{"locuteur": str, "texte": str}], "jet": dict | None, "fin": bool}`. Utilisé par la tâche 4.

- [ ] **Step 1: Modifier `fake_generate` et l'assertion associée**

Dans `tests/test_app.py`, remplacer :

```python
def fake_generate(state, player_text=None):
    return {"texte": "Il était une fois.", "jet": None}
```

par :

```python
def fake_generate(state, player_text=None):
    return {
        "segments": [{"locuteur": "narrateur", "texte": "Il était une fois."}],
        "jet": None,
    }
```

Puis, dans `test_start_cree_une_partie`, remplacer :

```python
    assert resp.json() == {"texte": "Il était une fois.", "jet": None, "fin": False}
```

par :

```python
    assert resp.json() == {
        "segments": [{"locuteur": "narrateur", "texte": "Il était une fois."}],
        "jet": None,
        "fin": False,
    }
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `pytest tests/test_app.py -v`
Expected: `test_start_cree_une_partie` FAIL (la route renvoie encore `"texte"`) ; les autres tests de `test_app.py` passent déjà (ils ne vérifient pas ce champ)

- [ ] **Step 3: Modifier les deux routes**

Dans `backend/app.py`, dans `game_start`, remplacer :

```python
    return {"texte": result["texte"], "jet": None, "fin": False}
```

par :

```python
    return {"segments": result["segments"], "jet": None, "fin": False}
```

Dans `game_action`, remplacer :

```python
    return {"texte": result["texte"], "jet": result["jet"], "fin": state.finished}
```

par :

```python
    return {"segments": result["segments"], "jet": result["jet"], "fin": state.finished}
```

- [ ] **Step 4: Vérifier que tous les tests passent**

Run: `pytest tests/ -v`
Expected: 27 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app.py tests/test_app.py
git commit -m "routes : renvoient des segments locuteur/texte au lieu d'un bloc unique"
```

---

### Task 4: Front — voix par locuteur et lecture séquentielle

**Files:**
- Rewrite: `web/main.js`

**Interfaces:**
- Consumes: réponses `/game/start` et `/game/action` (tâche 3) — `data.segments`.
- Produces: rien (feuille de l'arbre). Pas de test automatisé (JS vanilla sans harnais, cohérent avec le reste du projet) : vérification manuelle en tâche 5.

- [ ] **Step 1: Réécrire `web/main.js`**

Remplacer tout le contenu par :

```javascript
// v0.3 : voix distinctes narrateur / PNJ via les voix système du navigateur
const logEl = document.getElementById("log");
const startBtn = document.getElementById("start");
const sendBtn = document.getElementById("sendReply");
const replyInput = document.getElementById("replyText");
const pttBtn = document.getElementById("ptt");

let frenchVoices = [];
let narratorVoice = null;

function loadVoices() {
  frenchVoices = speechSynthesis.getVoices().filter((v) => v.lang.startsWith("fr"));
  narratorVoice = frenchVoices.find((v) => v.name === "Thomas") || frenchVoices[0] || null;
}
loadVoices();
speechSynthesis.onvoiceschanged = loadVoices;

function hashString(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

function voiceFor(locuteur) {
  if (locuteur === "narrateur" || frenchVoices.length === 0) return narratorVoice;
  const pool = frenchVoices.filter((v) => v !== narratorVoice);
  if (pool.length === 0) return narratorVoice;
  return pool[hashString(locuteur) % pool.length];
}

function say(text, voice) {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";
  if (voice) u.voice = voice;
  speechSynthesis.speak(u);
}

function addMsg(text, who = "mj", label = null) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  const prefixe = label || (who === "mj" ? "MJ" : "Joueur");
  div.textContent = `${prefixe}: ${text}`;
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
  for (const segment of data.segments) {
    const label = segment.locuteur === "narrateur" ? null : segment.locuteur;
    addMsg(segment.texte, "mj", label);
    say(segment.texte, voiceFor(segment.locuteur));
  }
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

- [ ] **Step 2: Vérification rapide**

Run: `grep -c "data.texte" web/main.js`
Expected: `0` (plus aucune référence à l'ancien champ `texte`)

Run: `source .venv/bin/activate && pytest tests/ -q`
Expected: 27 passed (rien n'a cassé côté backend)

- [ ] **Step 3: Commit**

```bash
git add web/main.js
git commit -m "front : voix par locuteur, lecture séquentielle des segments"
```

---

### Task 5: Vérification manuelle

**Files:** aucun (vérification).

**Interfaces:**
- Consumes: tout ce qui précède + une vraie clé API dans `backend/.env` (déjà en place depuis la v0.2).

- [ ] **Step 1: Lancer le serveur**

Run: `source .venv/bin/activate && uvicorn backend.app:app --reload --port 8000`
Expected: démarrage sans erreur

- [ ] **Step 2: Partie réelle au navigateur**

Ouvrir http://127.0.0.1:8000, lancer une partie, jouer 2-3 actions en encourageant un PNJ à parler (ex. « Je m'adresse au gardien : qui es-tu ? »).

Vérifier :
- Le journal affiche les répliques préfixées par le nom du PNJ (pas juste « MJ: ») quand le LLM en fait parler un.
- Au moins deux voix différentes s'entendent pendant la partie (narrateur vs PNJ).
- Si un même PNJ reparle plus tard dans la partie, sa voix reste la même.
- Si le LLM ne fait parler aucun PNJ dans une réponse, tout s'affiche et se lit normalement en voix narrateur (pas de régression visible par rapport à la v0.2).

- [ ] **Step 3: Rapport**

Rapporter à Florian : les voix entendues (quelles voix macOS ont été choisies), si l'attribution PNJ→voix a semblé cohérente d'une réplique à l'autre, et toute bizarrerie (LLM qui oublie les tags, voix mal assorties, etc.).
