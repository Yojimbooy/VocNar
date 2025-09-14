![CI](https://github.com/<ton-user>/VocaNar/actions/workflows/ci.yml/badge.svg)

# ️ VocNar

*Vocal Narrator — un maître du jeu qui parle !*

VocaNar est un prototype d’interface narrative interactive :  

- Les joueurs et joueuses définissent leurs personnages, le type de scénario et la durée de la partie.  
- Un narrateur vocal (MJ) conte l’aventure à voix haute.  
- Les joueurs et joueuses répondent via une zone de texte (micro et reconnaissance vocale arrivent bientôt).  
- À chaque choix, le scénario évolue et le MJ rebondit.

---

##  Installation

### Prérequis

- Python **3.9+**
- [Uvicorn](https://www.uvicorn.org/) & [FastAPI](https://fastapi.tiangolo.com/) (normalement déjà listés dans `backend/requirements.txt`)

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

##  Utilisation

1. Choisis :
   - Nombre de joueurs  
   - Noms des personnages  
   - Type de scénario (fantastique / enquête / médiéval / policier)  
   - Durée de la partie  

2. Clique sur **Lancer la partie**.  
3. Le narrateur vocal (`speechSynthesis` du navigateur) raconte l’histoire.  
4. Les joueurs répondent dans la zone de texte.  
5. Le MJ réagit et propose la scène suivante.  

---

##  Prévisions  (MVP → futur)

- [ ] Jets de dés 
- [ ] Push-to-talk (micro)
- [ ] Reconnaissance vocale (Whisper STT)
- [ ] Narration TTS plus réaliste (Piper / ElevenLabs)
- [ ] Automate d’états (intro → dilemme → climax → épilogue)
- [ ] Cartes (SVG/Canvas, PNJ, lieux)
- [ ] Effets sonores et musiques d’ambiance
- [ ] Mode multi-joueurs

---

##  Contributions

Les PR (pull requests) sont bienvenues !  
Idées, issues et retours sont aussi appréciés.  

---

##  Licence

[MIT](LICENSE) — libre utilisation et partage.
