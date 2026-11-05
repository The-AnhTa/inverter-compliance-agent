import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { runAssessment } from "../src/runtime.js";
import { inputSchema, outputSchema } from "../src/schemas.js";


const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const PYTHON = process.env.TASK_E_PYTHON_PATH;
if (!PYTHON) throw new Error("TASK_E_PYTHON_PATH is required for deterministic plugin tests");

const manifestPath = path.join(ROOT, "integration", "openclaw", "integrity_manifest.json");
const manifestHash = createHash("sha256").update(await readFile(manifestPath)).digest("hex").toUpperCase();
const baseConfig = Object.freeze({
  pythonPath: PYTHON,
  runnerPath: path.join(ROOT, "integration", "openclaw", "assessment_runner.py"),
  workingDirectory: ROOT,
  integrityManifestPath: manifestPath,
  integrityManifestSha256: manifestHash,
  runnerArguments: Object.freeze(["-I"]),
  timeoutMs: 5_000,
  maxInputBytes: 32_768,
  maxOutputBytes: 262_144,
  maxStderrBytes: 8_192,
});
const request = JSON.parse(await readFile(path.join(ROOT, "tests", "fixtures", "task_e_synthetic_request.json"), "utf8"));

test("schemas reject unknown root fields and publish structured classifications", () => {
  assert.equal(inputSchema.additionalProperties, false);
  assert.equal(inputSchema.properties.metadata.additionalProperties, false);
  assert.equal(inputSchema.properties.observations.items.additionalProperties, false);
  assert.equal(outputSchema.additionalProperties, false);
  assert.ok(outputSchema.properties.results.items.properties.classification);
});

test("plugin-to-Python integration returns the deterministic assessment", async () => {
  const result = await runAssessment(request, baseConfig);
  assert.equal(result.dataset_id, "SYNTHETIC-TASK-E-E2E-001");
  assert.equal(result.synthetic, true);
  assert.equal(result.results.find((item) => item.parameter === "volt_var_vv1").classification, "compliant_with_approved_variation");
});

test("plugin enforces its pre-spawn input byte limit", async () => {
  await assert.rejects(
    runAssessment({ value: "x".repeat(33_000) }, baseConfig),
    /input exceeds/u,
  );
});

test("Python execution failure is surfaced without a shell", async () => {
  const config = {
    ...baseConfig,
    runnerPath: path.join(ROOT, "tests", "fixtures", "task_e_failure_runner.py"),
  };
  await assert.rejects(runAssessment(request, config), /SYNTHETIC_TEST_FAILURE/u);
});

test("Python execution timeout terminates the child", async () => {
  const config = {
    ...baseConfig,
    runnerPath: path.join(ROOT, "tests", "fixtures", "task_e_timeout_runner.py"),
    timeoutMs: 50,
  };
  await assert.rejects(runAssessment(request, config), /timed out/u);
});
