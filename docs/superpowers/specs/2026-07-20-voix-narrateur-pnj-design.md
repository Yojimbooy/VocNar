# VocNar v0.3 — Voix distinctes narrateur / PNJ

*Design validé le 20 juillet 2026.*

## Objectif

Rendre la narration plus immersive (effet « livre audio ») en donnant une voix
différente au narrateur et à chaque PNJ que le MJ fait parler, sans nouvelle
infrastructure serveur.

## Décisions actées

| Sujet | Décision |
|---|---|
| Cohérence des voix | Un PNJ récurrent garde la même voix toute la partie, dérivée d'un hash de son nom (pas d'état supplémentaire à stocker) |
| Attribution du locuteur | Tags inline dans le texte du LLM (`[NARRATEUR]` / `[PNJ:Nom]`), parsés côté backend par regex |
| Moteur TTS | `speechSynthesis` du navigateur (déjà en place depuis la v0.1) — macOS expose 18 voix françaises système, aucun moteur serveur (Piper, MeloTTS...) n'est nécessaire |
| Robustesse | Si le LLM omet les tags, tout le texte devient un seul segment `narrateur` — dégradation silencieuse, jamais d'erreur |

## Format de balisage attendu du LLM

Le prompt système instruit le narrateur de structurer sa réponse ainsi :

```
[NARRATEUR] Le gardien surgit de l'ombre, son regard perçant les ténèbres.
[PNJ:Le Gardien] Qui ose troubler mon repos ?
[NARRATEUR] Alice recule d'un pas, la main sur son épée.
```

Un exemple de ce type est inclus dans le prompt système pour fiabiliser le
respect du format par `claude-haiku-4-5`.

## Backend

### `backend/game/narrator.py`

- Nouvelle fonction pure `parse_segments(texte: str) -> list[dict]` :
  - Découpe le texte sur les marqueurs `[NARRATEUR]` et `[PNJ:Nom]` (regex,
    insensible à la position — pas besoin d'être en début de ligne).
  - Un segment sans tag identifié (ex. contenu avant le premier marqueur)
    est traité comme `narrateur`.
  - Segments vides (deux marqueurs consécutifs) ignorés.
  - **Aucun marqueur trouvé dans tout le texte** → un seul segment
    `{"locuteur": "narrateur", "texte": <texte entier>}` (comportement
    identique à la v0.2, pas de régression si le LLM ignore l'instruction).
  - Testable entièrement à sec (pas d'appel réseau).
- `build_system_prompt` intègre les instructions de balisage et l'exemple
  ci-dessus.
- `generate()` change de forme de retour : `{"segments": [...], "jet": ...}`
  au lieu de `{"texte": ..., "jet": ...}`. Le texte **brut avec tags** continue
  d'être committé dans `state.messages` (l'historique envoyé à l'API à chaque
  tour reste inchangé) ; `parse_segments` n'est appliqué qu'au moment de
  construire la valeur de retour, pas avant.

### `backend/app.py`

- `/game/start` et `/game/action` renvoient `"segments"` à la place de
  `"texte"` dans leur réponse JSON : `{"segments": [{"locuteur", "texte"}],
  "jet": ..., "fin": bool}`.
- Aucun autre changement de comportement (validation, erreurs 409/422/503
  inchangées).

## Front (`web/main.js`)

- **Sélection des voix** : au chargement (et à l'événement
  `voiceschanged`, nécessaire sur certains navigateurs où la liste des
  voix arrive de façon asynchrone), on filtre
  `speechSynthesis.getVoices()` sur les voix dont `lang` commence par
  `fr`. Une voix fixe est choisie pour le narrateur (préférence pour
  `Thomas` si présente, sinon la première voix française disponible) ;
  les voix restantes forment le pool des voix PNJ.
- **Attribution PNJ** : hash simple et stable du nom du PNJ, modulo la
  taille du pool → indice de voix. Même nom PNJ = même voix pendant
  toute la partie, sans état à synchroniser avec le backend.
- **Repli** : si aucune voix française n'est disponible (cas rare hors
  macOS), le narrateur et les PNJ utilisent la voix par défaut du
  navigateur (`voice` non renseigné sur l'utterance) — pas d'erreur.
- **Affichage et lecture** : `showTurn()` boucle sur `data.segments`.
  Chaque segment est ajouté au journal préfixé par son locuteur (« MJ: »
  pour le narrateur, « Le Gardien: » pour un PNJ — effet script) et lu
  via `speechSynthesis.speak()` avec la voix correspondante. Les appels
  `.speak()` s'enchaînent naturellement dans l'ordre de la file
  d'attente du navigateur — aucune synchronisation manuelle nécessaire.

## Tests

- `parse_segments` couvert en pur : aucun tag, tags mêlés narrateur/PNJ,
  contenu avant le premier tag, segments vides ignorés.
- Les tests existants de `generate()` (`test_generate_sans_jet`,
  `test_generate_avec_jet`, `test_generate_echec_du_jet`) mis à jour pour
  asserter sur `result["segments"]` au lieu de `result["texte"]` ; les
  assertions sur `state.messages` (texte brut avec tags) ne changent pas.
- `tests/test_app.py` : `fake_generate` et les assertions de réponse
  mises à jour pour la forme `segments`.
- Front : pas de nouveau harnais de test JS (cohérent avec le reste du
  projet) — vérification par grep (`data.texte` a disparu, `data.segments`
  est utilisé) et écoute réelle au navigateur (plusieurs voix distinctes
  audibles pendant une partie).

## Hors périmètre

Voix par personnage joueur (Alice, Bob...) — explicitement écarté au
profit du seul narrateur/PNJ. Moteur TTS serveur (Piper, XTTS) — resterait
une option si les voix système s'avèrent insuffisantes à l'usage.
