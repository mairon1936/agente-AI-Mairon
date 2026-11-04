const crypto = require("node:crypto");
const path = require("node:path");

require("dotenv").config({ path: path.resolve(__dirname, "..", ".env") });

const express = require("express");
const { rateLimit } = require("express-rate-limit");
const QRCode = require("qrcode");
const { DurableMessageQueue } = require("./durable-queue");

const app = express();
const publicDirectory = path.join(__dirname, "public");
const agentApiUrl = process.env.AGENT_API_URL || "http://127.0.0.1:8000/chat";
const bridgeDataDirectory =
  process.env.BRIDGE_DATA_DIR || path.resolve(__dirname, "..", "data", "bridge");
const messageQueue = new DurableMessageQueue(
  path.join(bridgeDataDirectory, "whatsapp-queue"),
);
const handledMessageIds = new Map();
const inFlightMessages = new Map();
const MAX_HANDLED_MESSAGES = 10000;
const MESSAGE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const MAX_MESSAGE_ATTEMPTS = 5;
let queueWorkerReady = false;
let stopping = false;

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

async function askAgent(clienteId, mensaje, accionId) {
  const headers = { "content-type": "application/json" };
  if (process.env.AGENT_BRIDGE_TOKEN) {
    headers["x-agent-bridge-token"] = process.env.AGENT_BRIDGE_TOKEN;
  }
  const body = { cliente_id: clienteId, mensaje };
  if (accionId) {
    body.accion_id = accionId;
  }
  const response = await fetch(agentApiUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(45000),
  });
  if (!response.ok) {
    throw new Error(`La API del agente respondió HTTP ${response.status}.`);
  }
  const result = await response.json();
  if (
    (typeof result.respuesta !== "string" || !result.respuesta.trim()) &&
    !result.interaccion &&
    !result.documento
  ) {
    throw new Error("La API del agente devolvió una respuesta vacía o inválida.");
  }
  return result;
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

async function sendWhatsAppButtons(recipient, message, draftId) {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const accessToken = process.env.WHATSAPP_ACCESS_TOKEN;
  const version = process.env.WHATSAPP_GRAPH_API_VERSION;
  if (!phoneNumberId || !accessToken || !version) {
    throw new Error("Falta configurar WhatsApp Cloud API para enviar botones.");
  }
  if (!/^v\d+\.\d+$/.test(version)) {
    throw new Error("WHATSAPP_GRAPH_API_VERSION debe tener el formato vNN.N.");
  }
  if (typeof draftId !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(draftId)) {
    throw new Error("El identificador del borrador es inválido.");
  }
  if (typeof message !== "string" || message.length > 1024) {
    throw new Error("El resumen excede el límite de botones de WhatsApp.");
  }
  const response = await fetch(
    `https://graph.facebook.com/${version}/${encodeURIComponent(phoneNumberId)}/messages`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${accessToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to: recipient,
        type: "interactive",
        interactive: {
          type: "button",
          body: { text: message },
          action: {
            buttons: [
              {
                type: "reply",
                reply: { id: `CONFIRMAR:${draftId}`, title: "Emitir" },
              },
              {
                type: "reply",
                reply: { id: `CANCELAR:${draftId}`, title: "Cancelar" },
              },
            ],
          },
        },
      }),
      signal: AbortSignal.timeout(20000),
    },
  );
  if (!response.ok) {
    throw new Error(`WhatsApp Cloud API respondió HTTP ${response.status}.`);
  }
}

async function sendWhatsAppDocument(recipient, documento) {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const accessToken = process.env.WHATSAPP_ACCESS_TOKEN;
  const version = process.env.WHATSAPP_GRAPH_API_VERSION;
  if (!phoneNumberId || !accessToken || !version) {
    throw new Error("Falta configurar WhatsApp Cloud API para enviar documentos.");
  }
  if (!/^v\d+\.\d+$/.test(version)) {
    throw new Error("WHATSAPP_GRAPH_API_VERSION debe tener el formato vNN.N.");
  }
  if (
    typeof documento.contenido_base64 !== "string" ||
    documento.contenido_base64.length > 16 * 1024 * 1024 ||
    !/^[A-Za-z0-9+/]*={0,2}$/.test(documento.contenido_base64)
  ) {
    throw new Error("El PDF recibido del agente es inválido o demasiado grande.");
  }
  const contenido = Buffer.from(documento.contenido_base64, "base64");
  if (!contenido.subarray(0, 5).equals(Buffer.from("%PDF-"))) {
    throw new Error("El agente no devolvió un PDF válido.");
  }
  const nombre = path.basename(String(documento.nombre || "factura.pdf"))
    .replace(/[^A-Za-z0-9._-]/g, "_")
    .slice(0, 120);
  const form = new FormData();
  form.append("messaging_product", "whatsapp");
  form.append("type", "application/pdf");
  form.append(
    "file",
    new Blob([contenido], { type: "application/pdf" }),
    nombre,
  );
  const mediaResponse = await fetch(
    `https://graph.facebook.com/${version}/${encodeURIComponent(phoneNumberId)}/media`,
    {
      method: "POST",
      headers: { authorization: `Bearer ${accessToken}` },
      body: form,
      signal: AbortSignal.timeout(20000),
    },
  );
  if (!mediaResponse.ok) {
    throw new Error(`WhatsApp Cloud API respondió HTTP ${mediaResponse.status}.`);
  }
  const media = await mediaResponse.json();
  if (typeof media.id !== "string" || !media.id) {
    throw new Error("WhatsApp Cloud API no devolvió el identificador del PDF.");
  }
  const sendResponse = await fetch(
    `https://graph.facebook.com/${version}/${encodeURIComponent(phoneNumberId)}/messages`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${accessToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to: recipient,
        type: "document",
        document: {
          id: media.id,
          filename: nombre,
          caption: String(documento.caption || "").slice(0, 1024),
        },
      }),
      signal: AbortSignal.timeout(20000),
    },
  );
  if (!sendResponse.ok) {
    throw new Error(`WhatsApp Cloud API respondió HTTP ${sendResponse.status}.`);
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
      return messages.flatMap((message) => {
        if (
          typeof message?.id !== "string" ||
          typeof message?.from !== "string"
        ) {
          return [];
        }
        if (message.type === "text" && typeof message.text?.body === "string") {
          return [{ id: message.id, from: message.from, text: message.text.body }];
        }
        if (
          message.type === "interactive" &&
          typeof message.interactive?.button_reply?.id === "string"
        ) {
          return [
            {
              id: message.id,
              from: message.from,
              text: message.interactive.button_reply.title || "",
              accionId: message.interactive.button_reply.id,
            },
          ];
        }
        return [];
      });
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
    if (text.length > 2000) {
      await sendWhatsAppMessage(
        message.from,
        "Tu mensaje supera el límite de 2000 caracteres. Envíalo en varios mensajes más cortos.",
      );
    } else {
      const resultado = await askAgent(
        `whatsapp:${message.from}`,
        text || " ",
        message.accionId,
      );
      if (resultado.interaccion?.tipo === "confirmar_factura") {
        await sendWhatsAppButtons(
          message.from,
          resultado.interaccion.texto,
          resultado.interaccion.borrador_id,
        );
      } else if (resultado.documento) {
        await sendWhatsAppDocument(message.from, resultado.documento);
        const draftId = message.accionId?.split(":")[1];
        if (draftId) {
          await askAgent(
            `whatsapp:${message.from}`,
            "El documento fue enviado.",
            `ENTREGADA:${draftId}`,
          );
        }
      } else if (resultado.respuesta) {
        await sendWhatsAppMessage(message.from, resultado.respuesta);
      }
    }
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

app.get("/health/ready", async (request, response) => {
  try {
    if (!queueWorkerReady) {
      response.status(503).json({ estado: "iniciando" });
      return;
    }
    const healthUrl = new URL("/salud", agentApiUrl).toString();
    const agentHealth = await fetch(healthUrl, {
      signal: AbortSignal.timeout(3000),
    });
    const cola = await messageQueue.counts();
    if (!agentHealth.ok) {
      response.status(503).json({ estado: "agente_no_disponible", cola });
      return;
    }
    response.json({ estado: "listo", cola });
  } catch (error) {
    console.error("No se pudo comprobar la preparación del servicio:", error.message);
    response.status(503).json({ estado: "no_listo" });
  }
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
        error: "WhatsApp no está disponible en este momento.",
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
    const resultado = await askAgent(clienteId, mensaje.trim());
    response.json({ cliente_id: clienteId, ...resultado });
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
      await messageQueue.enqueue(message);
    }
    response.sendStatus(200);
  } catch (error) {
    console.error("No se pudo guardar el mensaje entrante:", error.message);
    response.status(503).json({ error: "No se pudo guardar el mensaje para procesarlo." });
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
  const port = Number(process.env.PORT || process.env.BRIDGE_PORT || 3000);
  const host = process.env.HOST || (process.env.PORT ? "0.0.0.0" : "127.0.0.1");
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("PORT o BRIDGE_PORT debe ser un puerto entre 1 y 65535.");
  }
  void (async () => {
    await messageQueue.initialize();
    queueWorkerReady = true;
    const server = app.listen(port, host, () => {
      console.log(`Chat web y puente listos en el puerto ${port}.`);
    });
    void processWebhookQueue();
    const stop = () => {
      stopping = true;
      server.close();
    };
    process.once("SIGINT", stop);
    process.once("SIGTERM", stop);
  })().catch((error) => {
    console.error("No se pudo iniciar el puente de WhatsApp:", error.message);
    process.exitCode = 1;
  });
}

async function processWebhookQueue() {
  let processedSincePrune = 0;
  let lastPrune = Date.now();
  while (!stopping) {
    try {
      const item = await messageQueue.takeNext();
      if (!item) {
        if (Date.now() - lastPrune >= 60 * 60 * 1000) {
          await messageQueue.prune();
          lastPrune = Date.now();
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
        continue;
      }
      try {
        await handleWhatsAppMessage(item.job);
        await messageQueue.complete(item.processing);
      } catch (error) {
        console.error("No se pudo procesar un mensaje entrante:", error.message);
        if (item.job.attempts + 1 >= MAX_MESSAGE_ATTEMPTS) {
          await messageQueue.fail(item.job, item.processing);
          try {
            await sendWhatsAppMessage(
              item.job.from,
              "No pude procesar tu mensaje después de varios intentos. Un operador debe revisarlo.",
            );
          } catch (sendError) {
            console.error(
              "No se pudo enviar el aviso de error de WhatsApp:",
              sendError.message,
            );
          }
        } else {
          const delay = await messageQueue.retry(
            item.job,
            item.processing,
            error,
          );
          console.error(`Se reintentará el mensaje en ${delay} ms.`);
        }
      }
      processedSincePrune += 1;
      if (processedSincePrune >= 100) {
        await messageQueue.prune();
        lastPrune = Date.now();
        processedSincePrune = 0;
      }
    } catch (error) {
      console.error("Falló el trabajador de la cola de WhatsApp:", error.message);
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }
  }
}

module.exports = {
  app,
  buildWhatsAppLink,
  extractTextMessages,
  isValidChatInput,
  messageQueue,
  processWebhookQueue,
  verifyMetaSignature,
};
