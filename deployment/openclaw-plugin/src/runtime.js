import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";


export const MAX_INPUT_BYTES = 32_768;
export const MAX_OUTPUT_BYTES = 262_144;
export const MAX_STDERR_BYTES = 8_192;
export const EXECUTION_TIMEOUT_MS = 5_000;

export const LIVE_CONFIG = Object.freeze({
  pythonPath: "C:\\Users\\anh001\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
  runnerPath: "C:\\Users\\anh001\\.openclaw\\workspace-inverter-audit\\integration\\openclaw\\assessment_runner.py",
  workingDirectory: "C:\\Users\\anh001\\.openclaw\\workspace-inverter-audit",
  integrityManifestPath: "C:\\Users\\anh001\\.openclaw\\workspace-inverter-audit\\integration\\openclaw\\integrity_manifest.json",
  integrityManifestSha256: "25B1A4A042D7DB2DAA4F0B3DE294376D8979625C8713DE9A656588E60631BC24",
  runnerArguments: Object.freeze(["-I"]),
  timeoutMs: EXECUTION_TIMEOUT_MS,
  maxInputBytes: MAX_INPUT_BYTES,
  maxOutputBytes: MAX_OUTPUT_BYTES,
  maxStderrBytes: MAX_STDERR_BYTES,
});

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex").toUpperCase();
}

function safeEnvironment() {
  const result = {
    PYTHONIOENCODING: "utf-8",
    PYTHONUTF8: "1",
  };
  for (const key of ["SYSTEMROOT", "WINDIR", "TEMP", "TMP"]) {
    const value = process.env[key];
    if (typeof value === "string" && value) {
      result[key] = value;
    }
  }
  return result;
}

export async function verifyIntegrity(config = LIVE_CONFIG) {
  const [manifestBuffer, pythonInfo, runnerInfo] = await Promise.all([
    readFile(config.integrityManifestPath),
    stat(config.pythonPath),
    stat(config.runnerPath),
  ]);
  if (!pythonInfo.isFile() || !runnerInfo.isFile()) {
    throw new Error("Fixed Python executable or assessment runner is unavailable");
  }
  if (sha256(manifestBuffer) !== config.integrityManifestSha256.toUpperCase()) {
    throw new Error("Assessment integrity manifest hash mismatch");
  }
  const manifest = JSON.parse(manifestBuffer.toString("utf8"));
  if (!manifest.files || typeof manifest.files !== "object" || Array.isArray(manifest.files)) {
    throw new Error("Assessment integrity manifest is invalid");
  }
  const root = path.resolve(config.workingDirectory);
  for (const [relativeName, expectedHash] of Object.entries(manifest.files)) {
    if (
      typeof relativeName !== "string" ||
      typeof expectedHash !== "string" ||
      path.isAbsolute(relativeName) ||
      relativeName.split(/[\\/]+/u).includes("..")
    ) {
      throw new Error("Assessment integrity manifest contains an unsafe entry");
    }
    const target = path.resolve(root, relativeName);
    const relative = path.relative(root, target);
    if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
      throw new Error("Assessment integrity target escapes the fixed workspace");
    }
    const contents = await readFile(target);
    if (sha256(contents) !== expectedHash.toUpperCase()) {
      throw new Error(`Assessment integrity check failed for ${relativeName}`);
    }
  }
}

function appendBounded(chunks, chunk, state, maximum, streamName, child) {
  state.bytes += chunk.length;
  if (state.bytes > maximum) {
    child.kill();
    throw new Error(`${streamName} exceeded its fixed size limit`);
  }
  chunks.push(chunk);
}

export async function runAssessment(params, config = LIVE_CONFIG, spawnImpl = spawn, signal) {
  if (signal?.aborted) {
    throw new Error("Assessment engine call was cancelled");
  }
  const encodedInput = Buffer.from(JSON.stringify(params), "utf8");
  if (encodedInput.length > config.maxInputBytes) {
    throw new Error(`Assessment input exceeds ${config.maxInputBytes} bytes`);
  }
  await verifyIntegrity(config);

  return await new Promise((resolve, reject) => {
    const child = spawnImpl(
      config.pythonPath,
      [...config.runnerArguments, config.runnerPath],
      {
        cwd: config.workingDirectory,
        env: safeEnvironment(),
        shell: false,
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    const stdout = [];
    const stderr = [];
    const stdoutState = { bytes: 0 };
    const stderrState = { bytes: 0 };
    let settled = false;
    const abortHandler = () => {
      child.kill();
      finish(() => reject(new Error("Assessment engine call was cancelled")));
    };
    const finish = (action) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", abortHandler);
      action();
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(() => reject(new Error("Assessment engine timed out")));
    }, config.timeoutMs);
    signal?.addEventListener("abort", abortHandler, { once: true });

    child.on("error", (error) => finish(() => reject(new Error(`Assessment engine failed to start: ${error.message}`))));
    child.stdout.on("data", (chunk) => {
      try {
        appendBounded(stdout, chunk, stdoutState, config.maxOutputBytes, "Assessment output", child);
      } catch (error) {
        finish(() => reject(error));
      }
    });
    child.stderr.on("data", (chunk) => {
      try {
        appendBounded(stderr, chunk, stderrState, config.maxStderrBytes, "Assessment error output", child);
      } catch (error) {
        finish(() => reject(error));
      }
    });
    child.on("close", (code) => {
      if (settled) return;
      if (code !== 0) {
        const message = Buffer.concat(stderr).toString("utf8").trim();
        finish(() => reject(new Error(message || `Assessment engine exited with code ${code}`)));
        return;
      }
      try {
        const result = JSON.parse(Buffer.concat(stdout).toString("utf8"));
        finish(() => resolve(result));
      } catch {
        finish(() => reject(new Error("Assessment engine returned invalid JSON")));
      }
    });
    child.stdin.on("error", (error) => finish(() => reject(new Error(`Assessment input write failed: ${error.message}`))));
    child.stdin.end(encodedInput);
  });
}
