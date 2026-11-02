const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const status = document.querySelector("#service-status");
const qrImage = document.querySelector("#qr-image");
const qrHelp = document.querySelector("#qr-help");
const whatsappLink = document.querySelector("#whatsapp-link");

function getClientId() {
  const storageKey = "ai-mairon-web-client-id";
  let clientId = localStorage.getItem(storageKey);
  if (!clientId) {
    clientId = `web:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, clientId);
  }
  return clientId;
}

function addMessage(text, role) {
  const bubble = document.createElement("p");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const result = await response.json();
    status.textContent = result.agente ? "Agente configurado" : "Agente no configurado";
    status.classList.toggle("status-error", !result.agente);
    if (!result.qr) {
      qrHelp.textContent =
        "Configura el número internacional de WhatsApp Business para mostrar el QR.";
    }
  } catch {
    status.textContent = "Servicio no disponible";
    status.classList.add("status-error");
  }
}

async function loadQr() {
  try {
    const response = await fetch("/api/qr");
    const result = await response.json();
    if (!response.ok) {
      qrHelp.textContent = result.error || "No se pudo cargar el código QR.";
      return;
    }
    qrImage.src = result.qr;
    qrImage.hidden = false;
    whatsappLink.href = result.url;
    whatsappLink.hidden = false;
    qrHelp.textContent = "El QR abre un chat con el negocio en WhatsApp.";
  } catch {
    qrHelp.textContent = "No se pudo cargar el código QR.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mensaje = input.value.trim();
  if (!mensaje) {
    return;
  }
  addMessage(mensaje, "user");
  input.value = "";
  input.disabled = true;
  form.querySelector("button").disabled = true;
  const pending = addMessage("Escribiendo…", "assistant");
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cliente_id: getClientId(), mensaje }),
    });
    const result = await response.json();
    pending.remove();
    if (!response.ok) {
      addMessage(result.error || "No se pudo enviar el mensaje.", "assistant");
      return;
    }
    addMessage(result.respuesta, "assistant");
  } catch {
    pending.remove();
    addMessage("No se pudo conectar con el servidor. Inténtalo de nuevo.", "assistant");
  } finally {
    input.disabled = false;
    form.querySelector("button").disabled = false;
    input.focus();
  }
});

loadStatus();
loadQr();
