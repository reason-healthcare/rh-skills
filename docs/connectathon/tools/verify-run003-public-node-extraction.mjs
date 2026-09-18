#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

function usage(message) {
  if (message) console.error(`Error: ${message}`);
  console.error('Usage: node verify-run003-public-node-extraction.mjs --capture-root DIR --runtime NODE_JS --output REPORT [--run-id run003]');
  process.exit(2);
}
const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, values) => {
  if (index % 2 === 0) pairs.push([value.replace(/^--/, ''), values[index + 1]]);
  return pairs;
}, []));
for (const key of ['capture-root', 'runtime', 'output']) if (!args[key]) usage(`--${key} is required`);
const captureRoot = resolve(args['capture-root']);
const runtimePath = resolve(args.runtime);
const outputPath = resolve(args.output);
const runId = args['run-id'] ?? 'run003';
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(runId)) usage('--run-id must be a simple report label');
const { extractQuestionnaireObservations } = await import(new URL(`file://${runtimePath}`).href);
const manifest = JSON.parse(readFileSync(resolve(captureRoot, 'manifest.json'), 'utf8'));
const questionnaire = JSON.parse(readFileSync(resolve(captureRoot, 'questionnaire-input.json'), 'utf8'));
const sha256 = (value) => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');
const fileSha256 = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');
const resourcesOnly = (transaction) => ({
  resourceType: transaction.resourceType,
  type: transaction.type,
  entry: transaction.entry.map((entry) => entry.resource),
});
const cases = [];
for (const expected of manifest.cases) {
  const result = { fixtureId: expected.fixtureId, expectedStatus: expected.status, invoked: expected.invoked };
  if (!expected.invoked && !expected.rawPath) {
    result.actualStatus = 'not-invoked';
    result.reason = expected.reason;
    result.passed = true;
    cases.push(result);
    continue;
  }
  const responsePath = resolve(captureRoot, `${expected.fixtureId}--response.json`);
  const response = JSON.parse(readFileSync(responsePath, 'utf8'));
  const subject = response.subject.reference;
  const encounter = response.encounter.reference;
  const call = extractQuestionnaireObservations(questionnaire, response, subject, { encounter });
  if (!call.success) {
    result.actualStatus = 'error';
    result.error = call.error;
    result.passed = false;
    cases.push(result);
    continue;
  }
  result.actualStatus = call.value.status;
  result.reason = call.value.reason;
  if (call.value.status === 'extracted') {
    const expectedTransactionPath = resolve(captureRoot, expected.resultPath);
    const expectedTransaction = JSON.parse(readFileSync(expectedTransactionPath, 'utf8'));
    result.expectedTransactionSha256 = fileSha256(expectedTransactionPath);
    result.actualTransactionResourcesSha256 = sha256(resourcesOnly(call.value.transaction));
    result.expectedTransactionResourcesSha256 = sha256(resourcesOnly(expectedTransaction));
    result.observationCount = call.value.observations.length;
    result.passed = result.expectedStatus === result.actualStatus
      && result.actualTransactionResourcesSha256 === result.expectedTransactionResourcesSha256;
  } else {
    result.passed = result.expectedStatus === result.actualStatus;
  }
  cases.push(result);
}
const runtimeWasm = resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm');
const output = {
  runId,
  scope: 'Public Node/WASM SDC wrapper extraction against a frozen v2 QuestionnaireResponse capture. Compares semantic transaction Observation resources only; UUID entry fullUrls are generated values. This is not CQL/package/app execution.',
  passed: cases.every((entry) => entry.passed),
  wrapper: { module: runtimePath, moduleSha256: fileSha256(runtimePath), wasm: runtimeWasm, wasmSha256: fileSha256(runtimeWasm) },
  capture: { manifest: resolve(captureRoot, 'manifest.json'), manifestSha256: fileSha256(resolve(captureRoot, 'manifest.json')), questionnaireSha256: fileSha256(resolve(captureRoot, 'questionnaire-input.json')) },
  cases,
};
writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`);
console.log(outputPath);
if (!output.passed) process.exitCode = 1;
