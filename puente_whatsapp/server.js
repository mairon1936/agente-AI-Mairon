const crypto = require("node:crypto");
const path = require("node:path");

require("dotenv").config({ path: path.resolve(__dirname, "..", ".env") });

const express = require("express");
const { rateLimit } = require("express-rate-limit");
const QRCode = require("qrcode");

const app = express();
const publicDirectory = path.join(__dirname, "public");
const agentApiUrl = process.env.AGENT_API_URL || "http://127.0.0.1:8000/chat";
const handledMessageIds = new Map();
const inFlightMessages = new Map();
const MAX_HANDLED_MESSAGES = 10000;
const MESSAGE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

app.use(
  express.json({
    limit: "64kb",
    verify: (request, response, buffer) => {
      request.rawBody = Buffer.from(buffer);
    },
  }),
);
app.use(express.static(publicDirectory));

function isValidChatInput(clienteId, mensaje) {
  return (
    typeof clienteId === "string" &&
    /^web:[A-Za-z0-9-]{1,123}$/.test(clienteId) &&
    typeof mensaje === "string" &&
    mensaje.trim().length > 0 &&
    mensaje.length <= 2000
  );
}

function buildWhatsAppLink(phoneNumber, message = "Hola, quiero información.") {
  const number = String(phoneNumber || "").replace(/\D/g, "");
  if (!/^[1-9]\d{6,14}$/.test(number)) {
    throw new TypeError("El número público de WhatsApp no es válido.");
  }
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}

function verifyMetaSignature(rawBody, signature, appSecret) {
  if (!Buffer.isBuffer(rawBody) || !signature || !appSecret) {
    return false;
  }
  const expected = `sha256=${crypto
    .createHmac("sha256", appSecret)
    .update(rawBody)
    .digest("hex")}`;
  const expectedBuffer = Buffer.from(expected);
  const actualBuffer = Buffer.from(signature);
  return (
    expectedBuffer.length === actualBuffer.length &&
    crypto.timingSafeEqual(expectedBuffer, actualBuffer)
  );
}

function constantTimeStringMatch(actual, expected) {
  if (typeof actual !== "string" || typeof expected !== "string") {
    return false;
  }
  const actualBuffer = Buffer.from(actual);
  const expectedBuffer = Buffer.from(expected);
  return (
    actualBuffer.length === expectedBuffer.length &&
    crypto.timingSafeEqual(actualBuffer, expectedBuffer)
  );
}

async function askAgent(clienteId, mensaje) {
  const response = await fetch(agentApiUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ cliente_id: clienteId, mensaje }),
    signal: AbortSignal.timeout(45000),
  });
  if (!response.ok) {
    throw new Error(`La API del agente respondió HTTP ${response.status}.`);
  }
  const result = await response.json();
  if (typeof result.respuesta !== "string" || !result.respuesta.trim()) {
    throw new Error("La API del agente devolvió una respuesta vacía o inválida.");
  }
  return result.respuesta;
}

async function sendWhatsAppMessage(recipient, message) {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const accessToken = process.env.WHATSAPP_ACCESS_TOKEN;
  if (!phoneNumberId || !accessToken) {
    throw new Error(
      "Falta configurar WHATSAPP_PHONE_NUMBER_ID o WHATSAPP_ACCESS_TOKEN.",
    );
  }

  const version = process.env.WHATSAPP_GRAPH_API_VERSION;
  if (!version) {
    throw new Error("Falta configurar WHATSAPP_GRAPH_API_VERSION.");
  }
  if (!/^v\d+\.\d+$/.test(version)) {
    throw new Error("WHATSAPP_GRAPH_API_VERSION debe tener el formato vNN.N.");
  }
  const url = `https://graph.facebook.com/${version}/${encodeURIComponent(
    phoneNumberId,
  )}/messages`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      authorization: `Bearer ${accessToken}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      recipient_type: "individual",
      to: recipient,
      type: "text",
      text: { body: message.slice(0, 4096) },
    }),
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error(`WhatsApp Cloud API respondió HTTP ${response.status}.`);
  }
}

function extractTextMessages(body) {
  const entries = Array.isArray(body?.entry) ? body.entry : [];
  return entries.flatMap((entry) => {
    const changes = Array.isArray(entry?.changes) ? entry.changes : [];
    return changes.flatMap((change) => {
      const messages = Array.isArray(change?.value?.messages)
        ? change.value.messages
        : [];
      return messages
        .filter(
          (message) =>
            message?.type === "text" &&
            typeof message?.from === "string" &&
            typeof message?.text?.body === "string",
        )
        .map((message) => ({
          id: message.id,
          from: message.from,
          text: message.text.body,
        }));
    });
  });
}

function pruneMessageCache(now = Date.now()) {
  for (const [messageId, timestamp] of handledMessageIds) {
    if (now - timestamp > MESSAGE_CACHE_TTL_MS) {
      handledMessageIds.delete(messageId);
    }
  }
  while (handledMessageIds.size > MAX_HANDLED_MESSAGES) {
    const oldestMessageId = handledMessageIds.keys().next().value;
    handledMessageIds.delete(oldestMessageId);
  }
}

async function handleWhatsAppMessage(message) {
  if (typeof message.id === "string" && handledMessageIds.has(message.id)) {
    return;
  }
  if (typeof message.id === "string" && inFlightMessages.has(message.id)) {
    await inFlightMessages.get(message.id);
    return;
  }

  const operation = (async () => {
    const text = message.text.trim();
    if (!text || !/^[1-9]\d{6,19}$/.test(message.from)) {
      return;
    }
    const answer =
      text.length > 2000
        ? "Tu mensaje supera el límite de 2000 caracteres. Envíalo en varios mensajes más cortos."
        : await askAgent(`whatsapp:${message.from}`, text);
    await sendWhatsAppMessage(message.from, answer);
    if (typeof message.id === "string") {
      handledMessageIds.set(message.id, Date.now());
      pruneMessageCache();
    }
  })();

  if (typeof message.id === "string") {
    inFlightMessages.set(message.id, operation);
  }
  try {
    await operation;
  } finally {
    if (
      typeof message.id === "string" &&
      inFlightMessages.get(message.id) === operation
    ) {
      inFlightMessages.delete(message.id);
    }
  }
}

const chatLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 30,
  standardHeaders: "draft-7",
  legacyHeaders: false,
});

app.get("/health", (request, response) => {
  response.json({ estado: "ok" });
});

app.get("/api/status", (request, response) => {
  const publicNumber = process.env.WHATSAPP_PUBLIC_NUMBER || "";
  response.json({
    agente: Boolean(agentApiUrl),
    qr: /^[1-9]\d{6,14}$/.test(publicNumber.replace(/\D/g, "")),
    whatsapp:
      Boolean(process.env.WHATSAPP_PHONE_NUMBER_ID) &&
      Boolean(process.env.WHATSAPP_ACCESS_TOKEN) &&
      Boolean(process.env.WHATSAPP_VERIFY_TOKEN) &&
      Boolean(process.env.META_APP_SECRET),
  });
});

app.get("/api/qr", async (request, response, next) => {
  const phoneNumber = process.env.WHATSAPP_PUBLIC_NUMBER || "";
  try {
    const url = buildWhatsAppLink(phoneNumber);
    const qr = await QRCode.toDataURL(url, {
      errorCorrectionLevel: "M",
      margin: 2,
      width: 280,
    });
    response.json({ qr, url });
  } catch (error) {
    if (error instanceof TypeError) {
      response.status(503).json({
        error: "Configura WHATSAPP_PUBLIC_NUMBER en el archivo .env.",
      });
      return;
    }
    next(error);
  }
});

app.post("/api/chat", chatLimiter, async (request, response) => {
  const { cliente_id: clienteId, mensaje } = request.body || {};
  if (!isValidChatInput(clienteId, mensaje)) {
    response.status(400).json({
      error: "Envía un cliente_id válido y un mensaje de hasta 2000 caracteres.",
    });
    return;
  }
  try {
    const respuesta = await askAgent(clienteId, mensaje.trim());
    response.json({ cliente_id: clienteId, respuesta });
  } catch (error) {
    console.error("No se pudo completar el mensaje web:", error.message);
    response.status(502).json({
      error:
        "No se pudo conectar con el agente. Comprueba que la API de Python esté iniciada.",
    });
  }
});

app.get("/webhook", (request, response) => {
  const verifyToken = process.env.WHATSAPP_VERIFY_TOKEN;
  const mode = request.query["hub.mode"];
  const token = request.query["hub.verify_token"];
  const challenge = request.query["hub.challenge"];
  if (
    mode === "subscribe" &&
    verifyToken &&
    constantTimeStringMatch(token, verifyToken) &&
    typeof challenge === "string"
  ) {
    response.status(200).send(challenge);
    return;
  }
  response.sendStatus(403);
});

app.post("/webhook", async (request, response) => {
  const appSecret = process.env.META_APP_SECRET;
  if (
    !verifyMetaSignature(
      request.rawBody,
      request.get("x-hub-signature-256"),
      appSecret,
    )
  ) {
    response.status(401).json({ error: "Firma de webhook inválida." });
    return;
  }
  const messages = extractTextMessages(request.body);
  try {
    for (const message of messages) {
      await handleWhatsAppMessage(message);
    }
    response.sendStatus(200);
  } catch (error) {
    console.error("No se pudo procesar el webhook de WhatsApp:", error.message);
    response.status(502).json({
      error: "No se pudo procesar el mensaje entrante; WhatsApp puede reintentar.",
    });
  }
});

app.use((error, request, response, next) => {
  console.error("Error no controlado en el puente:", error.message);
  if (response.headersSent) {
    next(error);
    return;
  }
  response.status(500).json({ error: "Error interno del puente de WhatsApp." });
});

if (require.main === module) {
  const port = Number(process.env.BRIDGE_PORT || 3000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("BRIDGE_PORT debe ser un puerto entre 1 y 65535.");
  }
  app.listen(port, "127.0.0.1", () => {
    console.log(`Chat web y puente listos en http://localhost:${port}`);
  });
}

module.exports = {
  app,
  buildWhatsAppLink,
  extractTextMessages,
  isValidChatInput,
  verifyMetaSignature,
};
