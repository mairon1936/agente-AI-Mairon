const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const test = require("node:test");

const {
  buildWhatsAppLink,
  extractTextMessages,
  isValidChatInput,
  verifyMetaSignature,
} = require("../server");

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

test("extracts only text messages from webhook payloads", () => {
  const messages = extractTextMessages({
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { id: "m1", from: "18095550101", type: "text", text: { body: "Hola" } },
                { id: "m2", from: "18095550101", type: "image" },
              ],
            },
          },
        ],
      },
    ],
  });
  assert.deepEqual(messages, [
    { id: "m1", from: "18095550101", text: "Hola" },
  ]);
});
