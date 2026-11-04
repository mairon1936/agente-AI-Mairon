const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const status = document.querySelector("#service-status");
const qrImage = document.querySelector("#qr-image");
const qrHelp = document.querySelector("#qr-help");
const whatsappLink = document.querySelector("#whatsapp-link");
const installButton = document.querySelector("#install-button");
const installHelp = document.querySelector("#install-help");
const publicUrl = document.querySelector("#public-url");
const publicUrlHelp = document.querySelector("#public-url-help");
const copyUrlButton = document.querySelector("#copy-url-button");
let installPrompt;

if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
  installHelp.textContent =
    "En Safari, pulsa Compartir y selecciona Agregar a pantalla de inicio.";
}

if (
  window.location.protocol === "https:" &&
  !["localhost", "127.0.0.1", "::1"].includes(window.location.hostname)
) {
  publicUrl.textContent = window.location.origin;
  publicUrl.hidden = false;
  copyUrlButton.hidden = false;
  publicUrlHelp.textContent = "Comparte esta dirección segura para abrir el sitio.";
}

copyUrlButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(publicUrl.textContent);
    publicUrlHelp.textContent = "Enlace copiado.";
  } catch (error) {
    console.error("No se pudo copiar el enlace público:", error);
    publicUrlHelp.textContent = "No se pudo copiar. Selecciona la dirección para copiarla.";
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  installButton.hidden = false;
  installHelp.textContent = "Instala la aplicación para abrirla desde tu pantalla de inicio.";
});

window.addEventListener("appinstalled", () => {
  installPrompt = null;
  installButton.hidden = true;
  installHelp.textContent = "La aplicación quedó instalada en este dispositivo.";
});

installButton.addEventListener("click", async () => {
  if (!installPrompt) {
    return;
  }
  await installPrompt.prompt();
  installPrompt = null;
  installButton.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.error("No se pudo habilitar la instalación sin conexión:", error);
    });
  });
}

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
  if (role !== "assistant") {
    bubble.textContent = text;
  } else {
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    for (const part of parts) {
      if (/^\*\*[^*]+\*\*$|^\*[^*]+\*$/.test(part)) {
        const bold = document.createElement("strong");
        bold.textContent = part.replace(/^\*\*?|\*\*?$/g, "");
        bubble.append(bold);
      } else {
        bubble.append(document.createTextNode(part));
      }
    }
  }
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
      qrHelp.textContent = "WhatsApp no está disponible en este momento.";
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
