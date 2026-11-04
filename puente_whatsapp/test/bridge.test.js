const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { once } = require("node:events");
const test = require("node:test");

const {
  app,
  buildWhatsAppLink,
  extractTextMessages,
  isValidChatInput,
  verifyMetaSignature,
} = require("../server");

test("serves the installable web app resources", async (t) => {
  const server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const { port } = server.address();
  const origin = `http://127.0.0.1:${port}`;
  for (const [path, contentType] of [
    ["/", "text/html"],
    ["/manifest.webmanifest", "application/manifest+json"],
    ["/service-worker.js", "javascript"],
    ["/icons/icon.svg", "image/svg+xml"],
    ["/icons/icon-192.png", "image/png"],
    ["/icons/icon-512.png", "image/png"],
    ["/icons/apple-touch-icon.png", "image/png"],
  ]) {
    const response = await fetch(`${origin}${path}`);
    assert.equal(response.status, 200, path);
    assert.ok(response.headers.get("content-type").includes(contentType), path);
    if (path === "/") {
      const html = await response.text();
      assert.match(html, /<nav class="quick-menu" aria-label="Menú principal">/);
      assert.match(html, /<ol>/);
      assert.match(html, /<title>Asistente de Facturación Electrónica<\/title>/);
      assert.match(
        html,
        /<strong>Bienvenido al Sistema de Facturación Electrónica RD\. ¡Gracias por preferirnos!<\/strong>/,
      );
    }
    if (path === "/manifest.webmanifest") {
      const manifest = await response.json();
      assert.equal(manifest.name, "Asistente de Facturación Electrónica");
      assert.deepEqual(
        manifest.icons.map((icon) => icon.sizes),
        ["192x192", "512x512"],
      );
    }
  }
});

test("builds a WhatsApp link and encodes its opening message", () => {
  assert.equal(
    buildWhatsAppLink("+1 (809) 555-0101", "Hola, ¿cómo estás?"),
    "https://wa.me/18095550101?text=Hola%2C%20%C2%BFc%C3%B3mo%20est%C3%A1s%3F",
  );
});

test("rejects malformed WhatsApp phone numbers", () => {
  assert.throws(() => buildWhatsAppLink("123"), TypeError);
});

test("checks message input size and identifier format", () => {
  assert.equal(isValidChatInput("web:client-1", "Hola"), true);
  assert.equal(isValidChatInput("bad client id", "Hola"), false);
  assert.equal(isValidChatInput("whatsapp:18095550101", "Hola"), false);
  assert.equal(isValidChatInput("web:client-1", " "), false);
  assert.equal(isValidChatInput("web:client-1", "x".repeat(2001)), false);
});

test("verifies Meta webhook signatures and rejects altered payloads", () => {
  const rawBody = Buffer.from('{"object":"whatsapp_business_account"}');
  const secret = "test-app-secret";
  const signature = `sha256=${crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex")}`;

  assert.equal(verifyMetaSignature(rawBody, signature, secret), true);
  assert.equal(verifyMetaSignature(Buffer.from("{}"), signature, secret), false);
  assert.equal(verifyMetaSignature(rawBody, signature, ""), false);
});

test("accepts a signed webhook quickly and rejects an invalid signature", async (t) => {
  const secret = "test-webhook-secret";
  const previousSecret = process.env.META_APP_SECRET;
  process.env.META_APP_SECRET = secret;
  t.after(() => {
    if (previousSecret === undefined) {
      delete process.env.META_APP_SECRET;
    } else {
      process.env.META_APP_SECRET = previousSecret;
    }
  });

  const server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const { port } = server.address();
  const rawBody = Buffer.from('{"object":"whatsapp_business_account","entry":[]}');
  const signature = `sha256=${crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex")}`;
  const response = await fetch(`http://127.0.0.1:${port}/webhook`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hub-signature-256": signature,
    },
    body: rawBody,
  });
  assert.equal(response.status, 200);

  const rejected = await fetch(`http://127.0.0.1:${port}/webhook`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hub-signature-256": "sha256=invalid",
    },
    body: rawBody,
  });
  assert.equal(rejected.status, 401);
});

test("extracts text messages and signed interactive button replies", () => {
  const messages = extractTextMessages({
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { id: "m1", from: "18095550101", type: "text", text: { body: "Hola" } },
                { id: "m2", from: "18095550101", type: "image" },
                {
                  id: "m3",
                  from: "18095550101",
                  type: "interactive",
                  interactive: {
                    button_reply: { id: "CONFIRMAR:B00001", title: "Emitir" },
                  },
                },
              ],
            },
          },
        ],
      },
    ],
  });
  assert.deepEqual(messages, [
    { id: "m1", from: "18095550101", text: "Hola" },
    {
      id: "m3",
      from: "18095550101",
      text: "Emitir",
      accionId: "CONFIRMAR:B00001",
    },
  ]);
});
