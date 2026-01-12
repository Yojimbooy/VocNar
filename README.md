![CI](https://github.com/Yojimbooy/VocNar/actions/workflows/ci.yml/badge.svg)

# VocNar

*Vocal Narrator — un maître du jeu qui parle !*

VocNar est un prototype d'interface narrative interactive :

- Les joueurs et joueuses définissent leurs personnages, le type de scénario et la durée de la partie.
- Un narrateur vocal (MJ) conte l'aventure à voix haute.
- Les joueurs et joueuses répondent via texte ou **reconnaissance vocale** (Whisper en local).
- À chaque choix, le scénario évolue et le MJ rebondit.

---

##  Installation

### Prérequis

- Python **3.9+**
- **ffmpeg** (requis par Whisper pour le traitement audio)
  ```bash
  # macOS
  brew install ffmpeg
  # Ubuntu/Debian
  sudo apt install ffmpeg
  ```
- [Uvicorn](https://www.uvicorn.org/) & [FastAPI](https://fastapi.tiangolo.com/) (dans `backend/requirements.txt`)

### Étapes

1. **Cloner le dépôt**

   ```bash
   git clone https://github.com/<ton-user>/VocaNar.git
   cd VocaNar
   ```

2. **Créer un environnement virtuel**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   *(désactiver : `deactivate`)*

3. **Installer les dépendances**

   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Lancer le serveur**

   ```bash
   uvicorn backend.app:app --reload --port 8000
   ```

5. **Ouvrir le navigateur**
    [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Utilisation

1. Choisis :
   - Nombre de joueurs
   - Noms des personnages
   - Type de scénario (fantastique / enquête / médiéval / policier)
   - Durée de la partie

2. Clique sur **Lancer la partie**.
3. Le narrateur vocal (`speechSynthesis` du navigateur) raconte l'histoire.
4. Les joueurs répondent :
   - Via la zone de texte, ou
   - En cliquant sur **Parler** (reconnaissance vocale via Whisper)
5. Le MJ réagit et propose la scène suivante.  

---

## Prévisions (MVP -> futur)

- [x] Jets de dés (d20 basique)
- [x] Push-to-talk (micro)
- [x] Reconnaissance vocale (Whisper STT en local)
- [ ] Narration TTS plus réaliste (Piper / ElevenLabs)
- [ ] Système de jeu amélioré (difficulté contextuelle)
- [ ] Automate d'états (intro -> dilemme -> climax -> épilogue)
- [ ] Cartes (SVG/Canvas, PNJ, lieux)
- [ ] Effets sonores et musiques d'ambiance
- [ ] Mode multi-joueurs

---

##  Contributions

Les PR (pull requests) sont bienvenues !  
Idées, issues et retours sont aussi appréciés.  

---

##  Licence

[MIT](https://github.com/Yojimbooy/VocNar/blob/main/LICENSE.md) — libre utilisation et partage.
