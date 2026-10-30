(() => {
  "use strict";
  const CHAT_KEY = "jarvis_web_chat_v1";
  const MEMORY_KEY = "jarvis_web_memory_v1";
  const BUILD = "web-20261030-1";
  const byId = (id) => document.getElementById(id);
  const messagesEl = byId("messages");
  const welcome = byId("welcome");
  const chat = byId("chat");
  const input = byId("messageInput");
  const sendButton = byId("sendButton");
  const toastEl = byId("toast");
  let toastTimer = 0;
  let transcript = loadJson(CHAT_KEY, []);
  let memory = loadJson(MEMORY_KEY, {});
  let lastTopic = [...transcript].reverse().find((item) => item.role === "user")?.text || "";

  function loadJson(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      return value == null ? fallback : value;
    } catch (_) { return fallback; }
  }
  function save() {
    try {
      localStorage.setItem(CHAT_KEY, JSON.stringify(transcript.slice(-80)));
      localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
    } catch (_) { showToast("No pude guardar el historial local."); }
  }
  function normalize(value) {
    return String(value || "").toLocaleLowerCase("es").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").replace(/[¿?¡!.,;:()[\]{}]/g, " ")
      .replace(/\s+/g, " ").trim();
  }
  function showToast(text) {
    toastEl.textContent = text;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }
  function timeLabel() {
    return new Intl.DateTimeFormat("es-CO", {hour:"2-digit", minute:"2-digit"}).format(new Date());
  }
  function addMessage(role, text, persist = true) {
    const item = {role, text:String(text), time:timeLabel()};
    transcript.push(item);
    renderMessage(item);
    welcome.style.display = "none";
    chat.classList.add("visible");
    if (persist) save();
    chat.scrollTop = chat.scrollHeight;
  }
  function renderMessage(item) {
    const row = document.createElement("div");
    row.className = "message " + (item.role === "user" ? "user" : "assistant");
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = item.role === "user" ? "TÚ" : "J";
    const body = document.createElement("div");
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = item.text;
    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = item.time || "";
    body.appendChild(bubble);
    body.appendChild(time);
    row.appendChild(avatar);
    row.appendChild(body);
    messagesEl.appendChild(row);
  }
  function hydrate() {
    transcript.slice(-80).forEach((item) => renderMessage(item));
    if (transcript.length) {
      welcome.style.display = "none";
      chat.classList.add("visible");
      chat.scrollTop = chat.scrollHeight;
    }
  }

  function native(action, value = "") {
    try {
      if (window.JarvisNative && typeof window.JarvisNative.perform === "function") {
        return window.JarvisNative.perform(action, String(value));
      }
      return "Esa acción del teléfono está disponible al abrir Jarvis desde la aplicación Android.";
    } catch (error) {
      return "Android no pudo ejecutar esa acción: " + String(error);
    }
  }

  function remember(text) {
    const match = text.match(/^(?:recuerda|guarda|anota)(?: que)?\s+(.+)$/i);
    if (!match) return null;
    const detail = match[1].trim();
    const name = detail.match(/^(?:me llamo|mi nombre es)\s+(.+)$/i);
    if (name) memory.nombre = name[1].trim();
    else {
      memory.notas = Array.isArray(memory.notas) ? memory.notas : [];
      memory.notas.push(detail);
      memory.notas = memory.notas.slice(-30);
    }
    save();
    return "Lo guardé en la memoria privada de este dispositivo. No se envió a ningún servidor.";
  }

  function answerMemory(q) {
    const nameMatch = q.match(/^(?:me llamo|mi nombre es)\s+(.+)$/i);
    if (nameMatch) {
      memory.nombre = nameMatch[1].trim();
      save();
      return "Mucho gusto, " + memory.nombre + ". Guardé tu nombre en este dispositivo.";
    }
    if (/^(?:que recuerdas|que sabes de mi|muestrame mi memoria|que tienes guardado)$/.test(q)) {
      const parts = [];
      if (memory.nombre) parts.push("Tu nombre: " + memory.nombre);
      if (memory.notas && memory.notas.length) parts.push("Notas: " + memory.notas.join("; "));
      return parts.length ? "Esto es lo que tengo guardado en este dispositivo:\n" + parts.join("\n") : "Todavía no has guardado recuerdos. Puedes decirme «recuerda que…».";
    }
    if (/^(?:olvida todo|borra mi memoria|elimina mis recuerdos)$/.test(q)) {
      memory = {};
      save();
      return "He borrado la memoria local de Jarvis.";
    }
    if (/^(?:olvida la conversacion|borra el chat|limpia el chat)$/.test(q)) {
      transcript = [];
      save();
      messagesEl.replaceChildren();
      welcome.style.display = "flex";
      chat.classList.remove("visible");
      return "Conversación borrada. La memoria que guardaste permanece.";
    }
    return null;
  }

  function safeMath(expression) {
    const tokens = String(expression).replace(/,/g, ".").match(/\d+(?:\.\d+)?|[()+\-*/%]/g);
    if (!tokens || tokens.join("") !== String(expression).replace(/\s+/g, "").replace(/,/g, ".")) return null;
    let position = 0;
    function primary() {
      const token = tokens[position++];
      if (token === "+" || token === "-") {
        const value = primary();
        return token === "-" ? -value : value;
      }
      if (token === "(") {
        const value = sum();
        if (tokens[position++] !== ")") throw new Error("Paréntesis incompleto");
        return value;
      }
      const number = Number(token);
      if (!Number.isFinite(number)) throw new Error("Número inválido");
      return number;
    }
    function product() {
      let value = primary();
      while (["*", "/", "%"].includes(tokens[position])) {
        const op = tokens[position++];
        const right = primary();
        if ((op === "/" || op === "%") && right === 0) throw new Error("No se puede dividir por cero");
        value = op === "*" ? value * right : op === "/" ? value / right : value % right;
      }
      return value;
    }
    function sum() {
      let value = product();
      while (tokens[position] === "+" || tokens[position] === "-") {
        const op = tokens[position++];
        const right = product();
        value = op === "+" ? value + right : value - right;
      }
      return value;
    }
    try {
      const result = sum();
      if (position !== tokens.length || !Number.isFinite(result)) return null;
      return Number(result.toFixed(8)).toLocaleString("es-CO");
    } catch (_) { return null; }
  }

  function localConversation(raw) {
    const q = normalize(raw);
    if (!q) return "Aquí estoy. Escríbeme lo que necesitas.";
    const saved = remember(raw);
    if (saved) return saved;
    const memoryAnswer = answerMemory(q);
    if (memoryAnswer !== null) return memoryAnswer;

    if (/^(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|ey)$/.test(q)) {
      return memory.nombre ? "Hola, " + memory.nombre + ". Aquí estoy. ¿Qué tienes en mente?" : "Hola. Aquí estoy, listo para ayudarte. ¿Qué tienes en mente?";
    }
    if (/\b(como estas|que tal|todo bien)\b/.test(q)) return "Estoy funcionando localmente y listo para ayudarte. ¿Qué vamos a resolver?";
    if (/\b(como te llamas|quien eres|que eres)\b/.test(q)) return "Soy Jarvis. Esta versión funciona sin reconocimiento de voz y sin conectarse a servicios de IA. Mi núcleo conversacional está escrito para este proyecto y se ejecuta en el dispositivo.";
    if (/\b(que puedes hacer|ayuda|tus funciones|que sabes hacer)\b/.test(q)) {
      return "Puedo conversar y mantener recuerdos locales, resolver operaciones, abrir aplicaciones, buscar en la web, leer la pantalla y, si activas Accesibilidad, pulsar controles, escribir y desplazarte. Mis respuestas no dependen de una IA remota.";
    }
    if (/\b(hora|que hora es)\b/.test(q)) return "Son las " + new Intl.DateTimeFormat("es-CO", {hour:"2-digit", minute:"2-digit"}).format(new Date()) + ".";
    if (/\b(fecha|que dia es|que fecha es|hoy)\b/.test(q)) return "Hoy es " + new Intl.DateTimeFormat("es-CO", {weekday:"long", day:"numeric", month:"long", year:"numeric"}).format(new Date()) + ".";
    if (/\b(estas conectado|usas internet|nube|otra ia|gemini|chatgpt|qwen|modelo externo)\b/.test(q)) {
      return "No envío tus mensajes a otra IA ni uso una API conversacional. El chat se resuelve aquí mismo. La conexión se utiliza para descargar la interfaz y sus mejoras web; el núcleo local sigue funcionando sin conexión una vez cargado.";
    }
    if (/\b(que es la inteligencia artificial|que significa inteligencia artificial|explicame la ia)\b/.test(q)) {
      return "La inteligencia artificial es un conjunto de métodos que permite a un sistema reconocer patrones, resolver tareas o producir respuestas. Jarvis, en esta etapa, usa lógica y habilidades programadas para este proyecto; todavía no tiene un modelo generativo entrenado desde cero.";
    }
    if (/\b(que es jarvis|que es este proyecto)\b/.test(q)) {
      return "Jarvis es tu asistente Android. Estamos separando su interfaz web actualizable de las funciones nativas del teléfono. La conversación básica corre localmente, conserva memoria en este dispositivo y no llama a servicios de IA.";
    }
    if (/\b(que significa sin conexion|funciona sin internet|funciona offline)\b/.test(q)) {
      return "Cuando la interfaz ya está cargada, el chat local y la memoria funcionan sin conexión. Internet solo hace falta para recibir mejoras de la interfaz web y para abrir búsquedas externas que tú pidas.";
    }
    if (/\b(gracias|te agradezco)\b/.test(q)) return "Con gusto. Seguimos.";
    if (/\b(no entiendes|no me entiendes|estas equivocado)\b/.test(q)) return "Dime qué parte interpreté mal. Puedo corregir el contexto de esta conversación y guardar una preferencia local para no repetir el error.";

    const mathMatch = raw.match(/(?:cuanto es|calcula|resuelve|resultado de)\s+(.+)$/i);
    if (mathMatch) {
      const value = safeMath(mathMatch[1].replace(/x/gi, "*"));
      if (value !== null) return "El resultado es " + value + ".";
    }

    const openMatch = raw.match(/^(?:abre|abrir|inicia|lanza)\s+(?:la\s+)?(?:aplicacion\s+)?(?:app\s+)?(.+)$/i);
    if (openMatch) return native("open_app", openMatch[1].trim());
    if (/\b(lee la pantalla|que dice la pantalla|lee lo que aparece|que hay en pantalla)\b/.test(q)) return native("read_screen");
    if (/^(?:toca|pulsa|presiona|selecciona)\s+(.+)$/i.test(raw)) return native("click_text", raw.replace(/^(?:toca|pulsa|presiona|selecciona)\s+/i, "").trim());
    if (/^(?:escribe|teclea|introduce|ingresa)\s+(.+)$/i.test(raw)) return native("type_text", raw.replace(/^(?:escribe|teclea|introduce|ingresa)\s+/i, "").trim());
    if (/^(?:vuelve atras|atras|retrocede|regresa)$/.test(q)) return native("back");
    if (/^(?:ir al inicio|pantalla principal|vuelve al inicio)$/.test(q)) return native("home");
    if (/\b(desplaza hacia abajo|baja la pantalla|desliza hacia abajo|scroll abajo)\b/.test(q)) return native("scroll_down");
    if (/\b(desplaza hacia arriba|sube la pantalla|desliza hacia arriba|scroll arriba)\b/.test(q)) return native("scroll_up");
    if (/\b(activar accesibilidad|activa accesibilidad|control de pantalla|activar control de pantalla)\b/.test(q)) return native("accessibility_settings");

    const video = raw.match(/^(?:busca|buscar)\s+(.+)\s+en\s+youtube$/i);
    if (video) return native("youtube_search", video[1].trim());
    const search = raw.match(/^(?:busca|buscar|investiga|consulta)\s+(.+)$/i);
    if (search) return native("web_search", search[1].trim());

    const call = raw.match(/^(?:llama|llamar|marca)\s+(?:al\s+)?([+\d][+\d\s-]{6,})$/i);
    if (call) {
      if (window.confirm("Jarvis abrirá el marcador con " + call[1] + ". ¿Continuar?")) return native("dial", call[1].replace(/[^\d+]/g, ""));
      return "De acuerdo. No abrí el marcador.";
    }

    if (/^(si|sí|claro|de acuerdo|hazlo)$/.test(q) && lastTopic) {
      return "Tengo presente que estábamos hablando de: " + lastTopic + ". Dime qué parte quieres que continúe.";
    }

    lastTopic = raw.slice(0, 140);
    return "Te sigo. Puedo conversar sobre lo que me cuentas, conservar el contexto de este chat y ejecutar las funciones locales que tengo instaladas. No voy a inventar datos: todavía no tengo un modelo generativo entrenado desde cero ni conocimiento general comparable al de una IA grande. ¿Qué quieres que hagamos con esto?";
  }

  async function send(raw) {
    const text = String(raw || "").trim();
    if (!text) return;
    sendButton.disabled = true;
    addMessage("user", text);
    input.value = "";
    input.style.height = "auto";
    await new Promise((resolve) => setTimeout(resolve, 140));
    const response = localConversation(text);
    addMessage("assistant", response);
    sendButton.disabled = false;
    input.focus();
  }

  function setBuildLabel() {
    byId("buildLabel").textContent = BUILD.toUpperCase();
  }
  async function checkWebUpdate() {
    try {
      const response = await fetch("./version.json?check=" + Date.now(), {cache:"no-store"});
      if (!response.ok) return;
      const data = await response.json();
      if (data.build && data.build !== BUILD) {
        showToast("Jarvis se está actualizando…");
        setTimeout(() => location.reload(), 700);
      }
    } catch (_) {
      // Offline: the local conversation engine continues to work.
    }
  }

  sendButton.addEventListener("click", () => send(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send(input.value);
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => send(button.getAttribute("data-prompt")));
  });
  byId("menuButton").addEventListener("click", () => byId("menuPanel").classList.toggle("hidden"));
  byId("newChatButton").addEventListener("click", () => {
    transcript = [];
    save();
    messagesEl.replaceChildren();
    chat.classList.remove("visible");
    welcome.style.display = "flex";
    byId("menuPanel").classList.add("hidden");
    showToast("Conversación nueva. Tu memoria sigue guardada.");
  });
  byId("memoryButton").addEventListener("click", () => {
    byId("menuPanel").classList.add("hidden");
    send("¿Qué recuerdas?");
  });
  byId("accessibilityButton").addEventListener("click", () => {
    byId("menuPanel").classList.add("hidden");
    showToast(native("accessibility_settings"));
  });

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  hydrate();
  setBuildLabel();
  checkWebUpdate();
  setInterval(checkWebUpdate, 60000);
})();
