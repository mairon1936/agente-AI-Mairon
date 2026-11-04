const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { DurableMessageQueue } = require("../durable-queue");

test("persists messages across restart and deduplicates Meta retries", async (t) => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "agent-queue-"));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));

  const first = new DurableMessageQueue(directory);
  await first.initialize();
  const message = { id: "wamid-test-1", from: "18095550101", text: "Hola" };
  assert.equal(await first.enqueue(message), true);
  assert.equal(await first.enqueue(message), false);

  const restarted = new DurableMessageQueue(directory);
  await restarted.initialize();
  assert.equal(await restarted.enqueue(message), false);
  assert.deepEqual(await restarted.counts(), {
    pending: 1,
    processing: 0,
    completed: 0,
    failed: 0,
  });
  const item = await restarted.takeNext();
  assert.deepEqual(item.job, {
    ...message,
    attempts: 0,
    availableAt: item.job.availableAt,
  });
  await restarted.complete(item.processing);
  assert.equal(await restarted.enqueue(message), false);
});

test("moves interrupted processing jobs back to pending on restart", async (t) => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "agent-queue-"));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));

  const first = new DurableMessageQueue(directory);
  await first.initialize();
  await first.enqueue({ id: "wamid-test-2", from: "18095550101", text: "Hola" });
  const interrupted = await first.takeNext();
  assert.ok(interrupted);

  const restarted = new DurableMessageQueue(directory);
  await restarted.initialize();
  assert.deepEqual(await restarted.counts(), {
    pending: 1,
    processing: 0,
    completed: 0,
    failed: 0,
  });
  assert.equal((await restarted.takeNext()).job.id, "wamid-test-2");
});

test("retries failed jobs with bounded exponential delay", async (t) => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "agent-queue-"));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));

  const queue = new DurableMessageQueue(directory);
  await queue.initialize();
  await queue.enqueue({ id: "wamid-test-3", from: "18095550101", text: "Hola" });
  const item = await queue.takeNext();
  const delay = await queue.retry(
    item.job,
    item.processing,
    new Error("temporary error"),
    1000,
  );

  assert.equal(delay, 1000);
  assert.equal(await queue.takeNext(1500), null);
  const retry = await queue.takeNext(2001);
  assert.equal(retry.job.attempts, 1);
  assert.equal(retry.job.lastError, "temporary error");
});
