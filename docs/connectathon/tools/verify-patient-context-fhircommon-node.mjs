#!/usr/bin/env node
// Exercise the public CPG runtime with the pinned reference-translated probe.
// Individual Measure counts are Boolean membership, not returned-list sizes.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, arg, index, all) => {
  if (index % 2 === 0) pairs.push([arg, all[index + 1]]);
  return pairs;
}, []));
for (const key of ['--runtime', '--dependency-dir', '--output']) {
  assert(args[key], `required argument: ${key}`);
}
const runtime = path.resolve(args['--runtime']);
// The public @reasonhealth/cpg dist/node.js wrapper requires this sibling.
const wasmDir = path.resolve(path.dirname(runtime), '../wasm-node');
const dependencyDir = path.resolve(args['--dependency-dir']);
const output = path.resolve(args['--output']);
const { evaluateMeasure } = await import(pathToFileURL(runtime).href);
const read = (name) => JSON.parse(fs.readFileSync(path.join(dependencyDir, name), 'utf8'));
const sha = (filename) => createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
const probe = read('FHIRCommonReferencesProbe.elm.json');
const probeCanonical = 'https://example.org/Library/FHIRCommonReferencesProbe';
const content = {
  resourceType: 'Bundle', type: 'collection', entry: [
    { resource: {
      resourceType: 'Library', id: 'context-probe', name: 'FHIRCommonReferencesProbe',
      url: probeCanonical, version: '1.0.0',
      content: [{ contentType: 'application/elm+json', data: Buffer.from(JSON.stringify(probe)).toString('base64') }],
    } },
    { resource: read('Library-FHIRCommon.pinned-fhirhelpers.json') },
    { resource: read('Library-FHIRHelpers.pinned.json') },
  ],
};
const measure = {
  resourceType: 'Measure', id: 'context-probe',
  library: [`${probeCanonical}|1.0.0`],
  group: [{ population: [{
    code: { coding: [{ system: 'http://terminology.hl7.org/CodeSystem/measure-population', code: 'initial-population' }] },
    criteria: { language: 'text/cql-identifier', expression: 'Encounter Bound Observations', reference: `${probeCanonical}|1.0.0` },
  }] }],
};
const base = [
  { resourceType: 'Patient', id: 'p1' },
  { resourceType: 'Patient', id: 'p2' },
  { resourceType: 'Encounter', id: 'e1', subject: { reference: 'Patient/p1' } },
  { resourceType: 'Encounter', id: 'e2', subject: { reference: 'Patient/p2' } },
];
const observations = {
  correct: { resourceType: 'Observation', id: 'o1', subject: { reference: 'Patient/p1' }, encounter: { reference: 'Encounter/e1' } },
  wrongEncounter: { resourceType: 'Observation', id: 'o2', subject: { reference: 'Patient/p1' }, encounter: { reference: 'Encounter/e2' } },
  wrongPatient: { resourceType: 'Observation', id: 'o3', subject: { reference: 'Patient/p2' }, encounter: { reference: 'Encounter/e1' } },
};
const cases = [
  { name: 'correct-only', observations: ['correct'], expected: 1 },
  { name: 'mixed-valid-and-invalid', observations: ['correct', 'wrongEncounter', 'wrongPatient'], expected: 1 },
  { name: 'wrong-encounter-only', observations: ['wrongEncounter'], expected: 0 },
  { name: 'wrong-patient-only', observations: ['wrongPatient'], expected: 0 },
  { name: 'both-invalid-only', observations: ['wrongEncounter', 'wrongPatient'], expected: 0 },
  { name: 'no-observations', observations: [], expected: 0 },
];
const results = cases.map((test) => {
  const data = {
    resourceType: 'Bundle', type: 'collection',
    entry: [...base, ...test.observations.map((key) => observations[key])].map((resource) => ({ resource })),
  };
  const result = evaluateMeasure(measure, 'Patient/p1', content, {
    data, evaluationDate: '2026-06-15T00:00:00Z',
    measurementPeriod: { start: '2026-01-01T00:00:00Z', end: '2026-12-31T23:59:59Z' },
  });
  assert.equal(result.success, true, `${test.name}: runtime failed: ${result.error}`);
  assert.equal(result.value.status, 'complete', `${test.name}: runtime error must not count as clinical false`);
  const count = result.value.group?.[0]?.population?.[0]?.count;
  assert.equal(count, test.expected, `${test.name}: unexpected membership`);
  return { name: test.name, expectedMembership: test.expected, actualMembership: count, reportStatus: result.value.status, passed: true };
});
const report = {
  checkedAt: new Date().toISOString(), status: 'pass',
  scope: 'Public Node/WASM Patient and Encounter isolation using official reference-translated FHIRCommon ELM',
  assertionMeaning: 'Measure counts are Boolean membership. Separate invalid-only cases prove exclusions; a positive mixed-case count alone does not prove exact returned IDs.',
  runtime: { path: runtime, sha256: sha(runtime) },
  wasm: Object.fromEntries(['rh_cpg.js', 'rh_cpg_bg.wasm'].map((name) => [name, {
    path: path.join(wasmDir, name), sha256: sha(path.join(wasmDir, name)),
  }])),
  dependencies: Object.fromEntries([
    'FHIRCommonReferencesProbe.elm.json', 'Library-FHIRCommon.pinned-fhirhelpers.json', 'Library-FHIRHelpers.pinned.json',
  ].map((name) => [name, sha(path.join(dependencyDir, name))])),
  passed: results.length, failed: 0, cases: results,
};
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ status: report.status, passed: results.length, output }));
