#!/usr/bin/env node
/** Replay the accepted producer-independent run005 score cases through both applications. */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, dirname } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, values) => {
  if (index % 2 === 0) pairs.push([value.slice(2), values[index + 1]]);
  return pairs;
}, []));
for (const key of ['config', 'score-root', 'output']) if (!args[key]) throw Error(`--${key} required`);

const EXPECTED_CASE_IDS = [
  'score-0-no-questionnaire-provenance',
  'score-1-no-questionnaire-provenance',
  'score-2-no-questionnaire-provenance',
  'score-3-no-questionnaire-provenance',
  'missing-score',
  'missing-value',
  'string-value',
  'boolean-value',
  'negative-score',
  'above-range-score',
  'preliminary-score',
  'entered-in-error-score',
  'wrong-code',
  'wrong-system',
  'same-algorithm-code-without-version',
  'same-algorithm-code-different-version-metadata',
  'wrong-patient',
  'wrong-encounter',
  'missing-effective-time',
  'out-of-period-score',
  'duplicate-valid-score',
  'valid-with-unrelated-patient',
];
const EXPECTED_CASE_SET = new Set(EXPECTED_CASE_IDS);

const read = path => JSON.parse(readFileSync(path, 'utf8'));
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const write = (path, value) => writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
const expand = value => typeof value === 'string'
  ? value.replaceAll('${REPO_ROOT}', process.env.REPO_ROOT ?? '').replaceAll('${WORKBENCH_BASE_URL}', process.env.WORKBENCH_BASE_URL ?? '')
  : Array.isArray(value)
    ? value.map(expand)
    : value && typeof value === 'object'
      ? Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, expand(nested)]))
      : value;
const resources = bundle => (bundle?.entry ?? []).map(entry => entry?.resource).filter(Boolean);
const canonical = resource => typeof resource?.url === 'string' && typeof resource?.version === 'string'
  ? `${resource.url}|${resource.version}`
  : undefined;
const checksum = artifact => typeof artifact?.checksum === 'string' ? artifact.checksum.replace(/^sha256:/, '') : undefined;
const canonicalValues = value => Array.isArray(value) ? value : typeof value === 'string' ? [value] : [];

const configPath = resolve(args.config);
const config = expand(read(configPath));
const scoreRoot = resolve(args['score-root']);
const corePath = resolve(scoreRoot, 'score-contract.json');
const core = read(corePath);
const output = resolve(args.output);
const cookie = process.env.WORKBENCH_COOKIE;
if (!cookie) throw Error('WORKBENCH_COOKIE required; never written to evidence');
for (const key of ['contentPath', 'contentSha256', 'runtimePath', 'fixtureIndexPath', 'snapshotManifestPath', 'snapshotManifestSha256', 'projectId', 'snapshotId', 'baseUrl']) {
  if (typeof config[key] !== 'string' || !config[key]) throw Error(`config.${key} required`);
}
if (!config.measure?.artifactId || !config.measure?.canonical || !config.questionnaire?.artifactId || !config.questionnaire?.canonical || !Array.isArray(config.plans)) throw Error('config must define measure and plans');

const contentPath = resolve(config.contentPath);
const runtimePath = resolve(config.runtimePath);
const fixtureIndexPath = resolve(config.fixtureIndexPath);
const wasmPath = resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm');
const snapshotManifestPath = resolve(config.snapshotManifestPath);
if (sha(contentPath) !== config.contentSha256) throw Error('config.contentSha256 does not match contentPath');
if (sha(snapshotManifestPath) !== config.snapshotManifestSha256) throw Error('config.snapshotManifestSha256 does not match snapshotManifestPath');
if (
  core.runId !== 'run005'
  || core.passed !== true
  || core.inputs?.content?.sha256 !== sha(contentPath)
  || core.inputs?.runtime?.sha256 !== sha(runtimePath)
  || core.inputs?.wasm?.sha256 !== sha(wasmPath)
  || core.inputs?.fixtures?.sha256 !== sha(fixtureIndexPath)
) throw Error('Passing score contract must bind exact current package, fixtures, and public runtime');
if (!core.inputs?.scoreCoding || !['system', 'version', 'code'].every(key => typeof core.inputs.scoreCoding[key] === 'string' && core.inputs.scoreCoding[key])) {
  throw Error('Passing score contract lacks versioned score Coding provenance');
}

const scoreCases = Array.isArray(core.cases) ? core.cases : [];
const coreCasesById = new Map();
for (const test of scoreCases) {
  if (!test || typeof test.id !== 'string' || coreCasesById.has(test.id)) throw Error('score contract case IDs must be unique non-empty strings');
  coreCasesById.set(test.id, test);
}
if (scoreCases.length !== EXPECTED_CASE_IDS.length || coreCasesById.size !== EXPECTED_CASE_IDS.length || EXPECTED_CASE_IDS.some(id => !coreCasesById.has(id)) || [...coreCasesById].some(([id]) => !EXPECTED_CASE_SET.has(id))) {
  throw Error('score contract must contain exactly the accepted 22 alternate-source case IDs');
}
for (const id of EXPECTED_CASE_IDS) {
  const test = coreCasesById.get(id);
  if (typeof test.inputSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(test.inputSha256)) throw Error(`${id}: score contract lacks inputSha256`);
  if (typeof test.expected?.completed !== 'boolean' || !(typeof test.expected?.risk === 'boolean' || test.expected?.risk === null)) throw Error(`${id}: score contract lacks typed expected outcome`);
}

const content = read(contentPath);
const contentResources = resources(content);
const rootPlans = contentResources.filter(resource => resource.resourceType === 'PlanDefinition' && resource.id === 'steadi-fall-risk-screening-protocol');
const measures = contentResources.filter(resource => resource.resourceType === 'Measure');
const questionnaires = contentResources.filter(resource => resource.resourceType === 'Questionnaire');
if (rootPlans.length !== 1 || measures.length !== 1 || questionnaires.length !== 1) throw Error('content must contain exactly one root PlanDefinition, Measure, and Questionnaire');
const plan = rootPlans[0];
const measure = measures[0];
const questionnaire = questionnaires[0];
const planCanonical = canonical(plan);
const measureCanonical = canonical(measure);
const questionnaireCanonical = canonical(questionnaire);
if (!planCanonical || !measureCanonical || !questionnaireCanonical) throw Error('selected package resources require versioned canonicals');
const planConfig = config.plans.filter(item => item?.canonical === planCanonical);
if (planConfig.length !== 1 || !planConfig[0].artifactId) throw Error('root PlanDefinition must resolve to exactly one configured artifact');
if (config.measure.canonical !== measureCanonical) throw Error('configured Measure canonical does not match package Measure');
if (config.questionnaire.canonical !== questionnaireCanonical) throw Error('configured Questionnaire canonical does not match package Questionnaire');

const snapshotManifest = read(snapshotManifestPath);
if (snapshotManifest?.project?.id !== config.projectId) throw Error('snapshot manifest project does not match config.projectId');
const snapshotRoot = dirname(snapshotManifestPath);
function verifySnapshotArtifact(artifactId, expectedType, expectedCanonical) {
  const matches = (snapshotManifest.artifacts ?? []).filter(artifact => artifact?.id === artifactId);
  if (matches.length !== 1) throw Error(`snapshot manifest must contain exactly one ${artifactId}`);
  const artifact = matches[0];
  if (artifact.type !== expectedType || typeof artifact.path !== 'string' || !checksum(artifact)) throw Error(`${artifactId}: invalid manifest artifact identity`);
  const artifactPath = resolve(snapshotRoot, artifact.path);
  if (sha(artifactPath) !== checksum(artifact)) throw Error(`${artifactId}: artifact file differs from manifest checksum`);
  const artifactResource = read(artifactPath);
  if (artifactResource.resourceType !== expectedType || canonical(artifactResource) !== expectedCanonical) {
    throw Error(`${artifactId}: artifact canonical does not match selected package resource`);
  }
  return { artifactId, type: expectedType, canonical: expectedCanonical, path: artifactPath, sha256: checksum(artifact) };
}
const snapshotArtifacts = {
  rootPlan: verifySnapshotArtifact(planConfig[0].artifactId, 'PlanDefinition', planCanonical),
  measure: verifySnapshotArtifact(config.measure.artifactId, 'Measure', measureCanonical),
  questionnaire: verifySnapshotArtifact(config.questionnaire.artifactId, 'Questionnaire', questionnaireCanonical),
};

const fixtures = read(fixtureIndexPath);
const fixtureMatches = (fixtures.fixtures ?? []).filter(item => item?.id === 'eligible-unsteady-yes');
if (fixtureMatches.length !== 1 || !fixtureMatches[0].subject || !fixtureMatches[0].encounter || !fixtureMatches[0].evaluationDate || !fixtureMatches[0].measurementPeriod) {
  throw Error('fixture index must contain one complete eligible-unsteady-yes context');
}
const fixture = fixtureMatches[0];
const base = config.baseUrl.replace(/\/$/, '');
const standalone = (args.standalone ?? 'http://127.0.0.1:9091').replace(/\/$/, '');
const apiPath = (artifact, operation) => `${base}/api/projects/${encodeURIComponent(config.projectId)}/snapshots/${encodeURIComponent(config.snapshotId)}/artifacts/${encodeURIComponent(artifact)}/preview/${operation}`;

async function post(url, body, authenticated = false) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...(authenticated ? { cookie } : {}) },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let value;
  try { value = JSON.parse(text); } catch { value = { unparsed: text }; }
  return { status: response.status, body: value };
}
function sourceActionIds(bundle) {
  return resources(bundle)
    .filter(resource => resource.resourceType === 'RequestGroup')
    .flatMap(resource => resource.note ?? [])
    .map(note => note?.text)
    .filter(text => typeof text === 'string')
    .map(text => text.match(/^Source action:\s+(\S+)/)?.[1])
    .filter(Boolean);
}
function applyChecks(bundle, expected, subject, encounter) {
  const groups = resources(bundle).filter(resource => resource.resourceType === 'RequestGroup');
  const rootGroups = groups.filter(group => canonicalValues(group.instantiatesCanonical).includes(planCanonical));
  const root = rootGroups[0];
  const nonempty = root && (
    (root.action ?? []).length > 0
    || (root.note ?? []).some(note => typeof note?.text === 'string' && note.text.trim().length > 0)
  );
  const actionIds = sourceActionIds(bundle);
  const has = id => actionIds.includes(id);
  return {
    bundle: bundle?.resourceType === 'Bundle',
    rootRequestGroup: rootGroups.length === 1,
    rootCanonical: canonicalValues(root?.instantiatesCanonical).includes(planCanonical),
    rootSubject: root?.subject?.reference === subject,
    rootEncounter: root?.encounter?.reference === encounter,
    rootNonempty: Boolean(nonempty),
    exercise: has('refer-exercise-intervention') === (expected.risk === true),
    multifactorial: has('individualize-multifactorial-decision') === (expected.risk === true),
    unknown: has('await-complete-response') === (expected.risk === null),
  };
}

mkdirSync(output, { recursive: true });
const cases = [];
for (const id of EXPECTED_CASE_IDS) {
  const test = coreCasesById.get(id);
  const inputPath = resolve(scoreRoot, `${id}.json`);
  const inputSha256 = sha(inputPath);
  if (inputSha256 !== test.inputSha256) throw Error(`${id}: input differs from accepted score contract`);
  const data = read(inputPath);
  const dataResources = resources(data);
  if (
    data?.resourceType !== 'Bundle'
    || dataResources.some(resource => ['Questionnaire', 'QuestionnaireResponse'].includes(resource.resourceType))
    || dataResources.filter(resource => resource.resourceType === 'Observation').some(resource => resource.derivedFrom !== undefined)
  ) throw Error(`${id}: patientData is not producer-independent`);
  const body = { subject: fixture.subject, encounter: fixture.encounter, patientData: data, evaluationDate: fixture.evaluationDate, measurementPeriod: fixture.measurementPeriod };
  const [measureResponse, workbenchResponse, standaloneResponse] = await Promise.all([
    post(apiPath(config.measure.artifactId, 'evaluate-measure'), body, true),
    post(apiPath(planConfig[0].artifactId, 'apply'), body, true),
    post(`${standalone}/api/apply`, {
      dataPayload: data,
      subjectPayload: fixture.subject,
      planDefinition: plan,
      questionnaire,
      runtimeMode: 'local-rh-cpg',
      contentPayload: content,
      evaluationDate: fixture.evaluationDate,
      measurementPeriod: fixture.measurementPeriod,
      encounter: fixture.encounter,
    }),
  ]);
  const report = measureResponse.body?.measureReport;
  const populations = Object.fromEntries((report?.group?.[0]?.population ?? []).map(item => [item.code?.coding?.[0]?.code, item.count]));
  const checks = {
    measure: {
      http: measureResponse.status === 200,
      complete: report?.status === 'complete',
      population: populations['initial-population'] === 1 && populations.denominator === 1,
      numerator: populations.numerator === Number(test.expected.completed),
      proportion: report?.group?.[0]?.measureScore?.value === Number(test.expected.completed),
    },
    workbench: { http: workbenchResponse.status === 200, ...applyChecks(workbenchResponse.body?.requestGroupBundle, test.expected, fixture.subject, fixture.encounter) },
    standalone: { http: standaloneResponse.status === 200, ...applyChecks(standaloneResponse.body, test.expected, fixture.subject, fixture.encounter) },
  };
  const passed = Object.values(checks).every(group => Object.values(group).every(Boolean));
  write(resolve(output, `${id}.json`), {
    id,
    input: { path: inputPath, sha256: inputSha256 },
    expected: test.expected,
    checks,
    measure: measureResponse,
    workbench: workbenchResponse,
    standalone: standaloneResponse,
  });
  cases.push({ id, inputSha256, expected: test.expected, checks, passed });
}
const report = {
  checkedAt: new Date().toISOString(),
  runId: 'run005',
  scope: 'Replays exactly the 22 accepted producer-independent score Observation inputs through Workbench Measure/CPG and standalone CPG. patientData contains no Questionnaire, QuestionnaireResponse, or Observation.derivedFrom; the package knowledge content may contain a Questionnaire. This proves endpoint behavior for the configured immutable snapshot/artifact IDs and supplied standalone package, not browser behavior or deployed binary identity.',
  inputs: {
    config: configPath,
    content: { path: contentPath, sha256: sha(contentPath) },
    runtime: { path: runtimePath, sha256: sha(runtimePath) },
    wasm: { path: wasmPath, sha256: sha(wasmPath) },
    fixtureIndex: { path: fixtureIndexPath, sha256: sha(fixtureIndexPath) },
    scoreContract: { path: corePath, sha256: sha(corePath), scoreCoding: core.inputs.scoreCoding, inputCodingVersionSelection: 'Input Coding.version is recorded provenance, not a score-selection predicate; stable system plus code select the algorithm.' },
    workbenchSnapshot: { manifest: snapshotManifestPath, sha256: sha(snapshotManifestPath), projectId: config.projectId, snapshotId: config.snapshotId, artifacts: snapshotArtifacts },
  },
  expectedCaseIds: EXPECTED_CASE_IDS,
  counts: { cases: cases.length, httpCalls: cases.length * 3, passedCases: cases.filter(item => item.passed).length },
  cases,
  passed: cases.length === EXPECTED_CASE_IDS.length && cases.every(item => item.passed),
};
write(resolve(output, 'score-apps-report.json'), report);
console.log(JSON.stringify({ passed: report.passed, counts: report.counts, failures: cases.filter(item => !item.passed) }, null, 2));
if (!report.passed) process.exitCode = 1;
