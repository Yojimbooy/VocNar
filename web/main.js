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
