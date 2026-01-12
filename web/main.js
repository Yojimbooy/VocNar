// v0.1 : TTS via speechSynthesis + boucle de scènes côté front
const logEl = document.getElementById("log");
const startBtn = document.getElementById("start");
const sendBtn = document.getElementById("sendReply");
const replyInput = document.getElementById("replyText");
const pttBtn = document.getElementById("ptt");

// STT (Speech-to-Text) via Whisper (backend local)
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

      // Envoyer au backend pour transcription
      const formData = new FormData();
      formData.append("audio", audioBlob, "audio.webm");

      try {
        const resp = await fetch("/transcribe", { method: "POST", body: formData });
        const data = await resp.json();
        if (data.text) {
          replyInput.value = data.text;
          console.log("Transcription:", data.text);
          // Envoyer automatiquement
          setTimeout(() => sendBtn.click(), 200);
        }
      } catch (err) {
        console.error("Erreur transcription:", err);
        addMsg("⚠️ Erreur lors de la transcription.", "mj");
      }

      pttBtn.textContent = "🎤 Parler";
      pttBtn.style.background = "";
      isRecording = false;
    };

    console.log("Microphone initialisé");
    return true;
  } catch (err) {
    console.error("Erreur micro:", err);
    addMsg("⚠️ Impossible d'accéder au microphone.", "mj");
    return false;
  }
}

function toggleRecording() {
  if (!mediaRecorder) {
    initMicrophone().then(ok => { if (ok) toggleRecording(); });
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
    console.log("Enregistrement démarré");
  }
}

function say(text) {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";
  speechSynthesis.speak(u);
}

function addMsg(text, who="mj") {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = (who === "mj" ? "MJ: " : "Joueur: ") + text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function randomPick(arr){ return arr[Math.floor(Math.random()*arr.length)]; }

const FRAG = {
  lieu: ["au pied d'une tour en ruines", "dans une ruelle embrumée", "dans une taverne bondée"],
  accroche: ["Un murmure circule au sujet d'un artefact perdu.", "Une silhouette vous observe depuis l'ombre."],
  evenement: ["un cri retentit", "la lumière vacille", "un mécanisme claque"],
  consequence: ["un passage secret s'ouvre", "un piège se déclenche", "un allié se révèle hostile"]
};

const BLUEPRINT = [
  {id: "intro", prompt: "Vous arrivez {lieu}. {accroche} Que faites-vous ?"},
  {id: "scene1", prompt: "Alors que {evenement}, une opportunité se présente. Qui agit et comment ?"},
  {id: "scene2", prompt: "Une conséquence inattendue survient: {consequence}. Comment réagissez-vous ?"},
  {id: "final", prompt: "Le dénouement approche. Quelle est votre dernière action décisive ?"}
];

function render(tmpl) {
  return tmpl
    .replace("{lieu}", randomPick(FRAG.lieu))
    .replace("{accroche}", randomPick(FRAG.accroche))
    .replace("{evenement}", randomPick(FRAG.evenement))
    .replace("{consequence}", randomPick(FRAG.consequence));
}

let beats = [];
let idx = 0;

function nextBeat() {
  if (idx >= beats.length) {
    const end = "Épilogue: Votre aventure touche à sa fin. Un dernier regard en arrière… et le rideau tombe.";
    addMsg(end, "mj"); say(end); return;
  }
  const b = beats[idx++];
  addMsg(b, "mj"); say(b);
}

startBtn.addEventListener("click", () => {
  logEl.innerHTML = "";
  idx = 0;

  const players = document.getElementById("players").value;
  const names = document.getElementById("names").value || "Alice; Bob; Charly";
  const genre = document.getElementById("genre").value;
  const duration = document.getElementById("duration").value;

  const intro = `Bienvenue à tous (${players} joueurs): ${names}. Scénario ${genre}, durée cible ${duration} minutes.`;
  addMsg(intro, "mj"); say(intro);

  beats = BLUEPRINT.map(b => render(b.prompt));
  setTimeout(nextBeat, 1200);
});

sendBtn.addEventListener("click", () => {
  const txt = replyInput.value.trim();
  if (!txt) return;
  addMsg(txt, "player");
  replyInput.value = "";

  // v0.1 : mini "résolveur" (pseudo dé)
  const roll = Math.floor(Math.random()*20)+1;
  const outcome = roll >= 12 ? "Ça passe ! L'action réussit." : "Hmm… échec partiel, une complication surgit.";
  const bridge = `${outcome} (d20=${roll}).`;
  addMsg(bridge, "mj"); say(bridge);

  setTimeout(nextBeat, 800);
});

// Push-to-Talk : clic pour démarrer/arrêter l'enregistrement
pttBtn.addEventListener("click", toggleRecording);
