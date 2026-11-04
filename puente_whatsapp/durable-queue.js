const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");

class DurableMessageQueue {
  constructor(directory, { retentionMs = 7 * 24 * 60 * 60 * 1000 } = {}) {
    this.directory = directory;
    this.retentionMs = retentionMs;
    this.knownIds = new Set();
    this.ready = false;
  }

  _file(directory, id) {
    const key = crypto.createHash("sha256").update(id).digest("hex");
    return path.join(this.directory, directory, `${key}.json`);
  }

  async initialize() {
    for (const name of ["pending", "processing", "completed", "failed"]) {
      const directory = path.join(this.directory, name);
      await fs.mkdir(directory, { recursive: true, mode: 0o700 });
      if (process.platform !== "win32") {
        await fs.chmod(directory, 0o700);
      }
    }

    const processingDirectory = path.join(this.directory, "processing");
    for (const name of await fs.readdir(processingDirectory)) {
      await fs.rename(
        path.join(processingDirectory, name),
        path.join(this.directory, "pending", name),
      );
    }

    for (const name of ["pending", "processing", "completed", "failed"]) {
      const directory = path.join(this.directory, name);
      for (const file of await fs.readdir(directory)) {
        if (!file.endsWith(".json")) {
          continue;
        }
        try {
          const job = JSON.parse(await fs.readFile(path.join(directory, file), "utf8"));
          if (typeof job.id === "string") {
            this.knownIds.add(job.id);
          }
        } catch (error) {
          if (error.code !== "ENOENT") {
            throw new Error(`No se pudo leer un mensaje persistido (${file}).`, {
              cause: error,
            });
          }
        }
      }
    }

    await this.prune();
    this.ready = true;
  }

  async enqueue(message) {
    if (!this.ready) {
      throw new Error("La cola de mensajes aún no está inicializada.");
    }
    if (this.knownIds.has(message.id)) {
      return false;
    }

    this.knownIds.add(message.id);
    const finalPath = this._file("pending", message.id);
    const temporaryPath = `${finalPath}.${crypto.randomUUID()}.tmp`;
    const job = {
      ...message,
      attempts: 0,
      availableAt: Date.now(),
    };
    try {
      await fs.writeFile(temporaryPath, JSON.stringify(job), {
        flag: "wx",
        mode: 0o600,
      });
      await fs.rename(temporaryPath, finalPath);
      return true;
    } catch (error) {
      this.knownIds.delete(message.id);
      await fs.rm(temporaryPath, { force: true });
      throw error;
    }
  }

  async takeNext(now = Date.now()) {
    const directory = path.join(this.directory, "pending");
    const files = (await fs.readdir(directory)).filter((file) => file.endsWith(".json"));
    files.sort();
    for (const file of files) {
      const source = path.join(directory, file);
      let job;
      try {
        job = JSON.parse(await fs.readFile(source, "utf8"));
      } catch (error) {
        if (error.code === "ENOENT") {
          continue;
        }
        throw new Error(`No se pudo leer un mensaje pendiente (${file}).`, {
          cause: error,
        });
      }
      if (job.availableAt > now) {
        continue;
      }
      const processing = path.join(this.directory, "processing", file);
      try {
        await fs.rename(source, processing);
        return { job, processing };
      } catch (error) {
        if (error.code === "ENOENT") {
          continue;
        }
        throw error;
      }
    }
    return null;
  }

  async complete(processing) {
    const destination = path.join(
      this.directory,
      "completed",
      path.basename(processing),
    );
    await fs.rename(processing, destination);
  }

  async retry(job, processing, error, now = Date.now()) {
    job.attempts += 1;
    job.lastError = String(error.message || error).slice(0, 300);
    const delayMs = Math.min(300_000, 1000 * 2 ** (job.attempts - 1));
    job.availableAt = now + delayMs;
    const temporaryPath = `${processing}.${crypto.randomUUID()}.tmp`;
    const queuedPath = path.join(
      this.directory,
      "pending",
      path.basename(processing),
    );
    await fs.writeFile(temporaryPath, JSON.stringify(job), {
      flag: "wx",
      mode: 0o600,
    });
    try {
      await fs.link(temporaryPath, queuedPath);
      await fs.rm(temporaryPath, { force: true });
      await fs.rm(processing, { force: true });
    } catch (error) {
      await fs.rm(temporaryPath, { force: true });
      throw error;
    }
    return delayMs;
  }

  async fail(job, processing) {
    const failed = path.join(
      this.directory,
      "failed",
      path.basename(processing),
    );
    await fs.rename(processing, failed);
    return job;
  }

  async counts() {
    const result = {};
    for (const name of ["pending", "processing", "completed", "failed"]) {
      const files = await fs.readdir(path.join(this.directory, name));
      result[name] = files.filter((file) => file.endsWith(".json")).length;
    }
    return result;
  }

  async prune(now = Date.now()) {
    for (const name of ["completed", "failed"]) {
      const directory = path.join(this.directory, name);
      for (const file of await fs.readdir(directory)) {
        const filePath = path.join(directory, file);
        const info = await fs.stat(filePath);
        if (now - info.mtimeMs > this.retentionMs) {
          try {
            const job = JSON.parse(await fs.readFile(filePath, "utf8"));
            if (typeof job.id === "string") {
              this.knownIds.delete(job.id);
            }
          } catch (error) {
            if (error.code !== "ENOENT") {
              throw error;
            }
          }
          await fs.rm(filePath, { force: true });
        }
      }
    }
  }
}

module.exports = { DurableMessageQueue };
