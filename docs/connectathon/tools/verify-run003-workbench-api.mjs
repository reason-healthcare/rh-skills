#!/usr/bin/env node
/**
 * Authenticated Workbench preview API matrix for a final, already-imported
 * snapshot. It is read-only: it sends preview requests and writes evidence
 * beneath --output. It never imports, edits, or deletes snapshot content.
 */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

function die(message) { console.error(`Error: ${message}`); process.exit(2); }
const argv = process.argv.slice(2);
const flag = name => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
const configPath = flag('--config');
const outputDirArg = flag('--output');
if (!configPath || !outputDirArg) die('Usage: node verify-workbench-api-matrix.mjs --config matrix.json --output evidence-dir');
const rawConfig = JSON.parse(await readFile(resolve(configPath), 'utf8'));
const repoRoot = process.env.REPO_ROOT;
const workbenchBaseUrl = process.env.WORKBENCH_BASE_URL;
const expand = value => {
  if (typeof value === 'string') {
    if (value.includes('${REPO_ROOT}') && !repoRoot) die('Set REPO_ROOT to expand config paths');
    if (value.includes('${WORKBENCH_BASE_URL}') && !workbenchBaseUrl) die('Set WORKBENCH_BASE_URL to expand config baseUrl');
    return value.replaceAll('${REPO_ROOT}', repoRoot ?? '${REPO_ROOT}').replaceAll('${WORKBENCH_BASE_URL}', workbenchBaseUrl ?? '${WORKBENCH_BASE_URL}');
  }
  if (Array.isArray(value)) return value.map(expand);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, expand(item)]));
  return value;
};
const config = expand(rawConfig);
const outputDir = resolve(outputDirArg);
const readJson = async path => JSON.parse(await readFile(path, 'utf8'));
const writeJson = async (path, value) => writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
const hash = async path => createHash('sha256').update(await readFile(path)).digest('hex');
const canonical = resource => resource?.url ? `${resource.url}${resource.version ? `|${resource.version}` : ''}` : undefined;
const resources = bundle => bundle?.resourceType === 'Bundle' ? (bundle.entry ?? []).map(entry => entry?.resource).filter(Boolean) : [];
const expectString = (value, name) => { if (typeof value !== 'string' || !value) die(`config.${name} is required`); return value; };
const baseUrl = expectString(config.baseUrl, 'baseUrl').replace(/\/$/, '');
const projectId = expectString(config.projectId, 'projectId');
const snapshotId = expectString(config.snapshotId, 'snapshotId');
const cookie = config.cookie ?? process.env.WORKBENCH_COOKIE;
if (typeof cookie !== 'string' || !cookie) die('Provide config.cookie or WORKBENCH_COOKIE; the cookie is intentionally never written to evidence.');
const evaluationDate = expectString(config.evaluationDate, 'evaluationDate');
const period = config.measurementPeriod;
if (!period?.start || !period?.end) die('config.measurementPeriod.start and .end are required');
const contentPath = resolve(expectString(config.contentPath, 'contentPath'));
const fixtureIndexPath = resolve(expectString(config.fixtureIndexPath, 'fixtureIndexPath'));
const assertionRoot = resolve(expectString(config.assertionRoot, 'assertionRoot'));
const runtimePath = resolve(expectString(config.runtimePath, 'runtimePath'));
const runId = config.runId ?? 'run003';
if (typeof runId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(runId)) die('config.runId must be a simple report label');
const plans = config.plans;
if (!Array.isArray(plans) || plans.length < 1 || !plans.every(plan => plan?.artifactId && plan?.canonical)) die('config.plans must contain one or more { artifactId, canonical } entries; include every imported generated plan when available');
if (!config.measure?.artifactId || !config.measure?.canonical) die('config.measure requires artifactId and canonical');
if (!config.questionnaire?.artifactId || !config.questionnaire?.canonical) die('config.questionnaire requires artifactId and canonical');
const expectedCalls = config.expectedCalls;
if (!expectedCalls || !['fixtures', 'planApplies', 'measures', 'questionnaires', 'total'].every((key) => Number.isInteger(expectedCalls[key]) && expectedCalls[key] >= 0)) {
  die('config.expectedCalls must provide non-negative integer fixtures, planApplies, measures, questionnaires, and total');
}
const expectedArtifactPrefix = `${projectId}--`;
for (const artifact of [...plans, config.measure, config.questionnaire]) {
  if (!artifact.artifactId.startsWith(expectedArtifactPrefix)) {
    die(`artifactId ${artifact.artifactId} is not project-prefixed ${expectedArtifactPrefix}; refresh it from the imported snapshot manifest`);
  }
}

const content = await readJson(contentPath);
const index = await readJson(fixtureIndexPath);
const fixtures = index.fixtures;
if (!Array.isArray(fixtures) || fixtures.length !== 6) die('fixture index must contain exactly six fixtures');
const fixtureRoot = dirname(fixtureIndexPath);
const findOne = (resourceType, selector) => {
  const matches = resources(content).filter(resource => resource.resourceType === resourceType && (resource.id === selector || resource.url === selector || canonical(resource) === selector));
  if (matches.length !== 1) die(`${resourceType} ${selector} resolved ${matches.length} resources in final content`);
  return matches[0];
};
const planResources = plans.map(plan => ({ ...plan, resource: findOne('PlanDefinition', plan.canonical) }));
const packagedPlanCanonicals = new Set(resources(content).filter(resource => resource.resourceType === 'PlanDefinition').map(canonical));
const configuredPlanCanonicals = new Set(plans.map(plan => plan.canonical));
if (configuredPlanCanonicals.size !== plans.length || packagedPlanCanonicals.size !== configuredPlanCanonicals.size || [...configuredPlanCanonicals].some(value => !packagedPlanCanonicals.has(value))) {
  die('config.plans must contain each packaged PlanDefinition canonical exactly once');
}
if (expectedCalls.fixtures !== fixtures.length || expectedCalls.planApplies !== fixtures.length * planResources.length || expectedCalls.measures !== fixtures.length || expectedCalls.questionnaires !== fixtures.length || expectedCalls.total !== expectedCalls.planApplies + expectedCalls.measures + expectedCalls.questionnaires) {
  die('config.expectedCalls must exactly match the configured six-fixture full-package API matrix');
}
const measure = { ...config.measure, resource: findOne('Measure', config.measure.canonical) };
const questionnaire = { ...config.questionnaire, resource: findOne('Questionnaire', config.questionnaire.canonical) };
const runtime = await import(pathToFileURL(runtimePath).href);
for (const functionName of ['applyPlanDefinition', 'evaluateMeasure', 'assembleQuestionnaire', 'populateQuestionnaire', 'validateQuestionnaireResponse', 'extractQuestionnaireObservations', 'reconcileExtractedObservations']) if (typeof runtime[functionName] !== 'function') die(`${runtimePath} does not export ${functionName}`);

function normalize(value) {
  const copy = structuredClone(value);
  const generated = new Map(); let sequence = 0;
  const addResource = resource => { if (resource?.resourceType && resource.id) { sequence += 1; generated.set(`${resource.resourceType}/${resource.id}`, `${resource.resourceType}/__generated_${sequence}`); } };
  if (copy?.resourceType === 'Bundle') { delete copy.id; for (const resource of resources(copy)) addResource(resource); }
  // MeasureReport and a populated QuestionnaireResponse are generated by each
  // invocation but do not act as package identity. Keep the assembled
  // Questionnaire identifier intact while removing only the response id.
  if (copy?.resourceType === 'MeasureReport') delete copy.id;
  if (copy?.response?.resourceType === 'QuestionnaireResponse') delete copy.response.id;
  const visit = current => {
    if (Array.isArray(current)) return current.forEach(visit);
    if (!current || typeof current !== 'object') return;
    for (const [key, child] of Object.entries(current)) {
      if (key === 'timestamp') { delete current[key]; continue; }
      if (key === 'meta' && child && typeof child === 'object') { delete child.lastUpdated; delete child.versionId; }
      if (key === 'reference' && typeof child === 'string' && generated.has(child)) { current[key] = generated.get(child); continue; }
      visit(child);
    }
    if (current.resourceType && current.id) { const mapped = generated.get(`${current.resourceType}/${current.id}`); if (mapped) current.id = mapped.split('/')[1]; }
  };
  if (copy?.resourceType === 'Bundle') {
    for (const entry of copy.entry ?? []) {
      const reference = typeof entry.fullUrl === 'string' ? entry.fullUrl.replace(/^https?:\/\/[^/]+\//, '') : undefined;
      if (reference && generated.has(reference)) entry.fullUrl = `urn:generated:${generated.get(reference)}`;
    }
  }
  visit(copy); return copy;
}
async function post(path, body) {
  const response = await fetch(`${baseUrl}${path}`, { method: 'POST', headers: { 'content-type': 'application/json', cookie }, body: JSON.stringify(body) });
  const raw = await response.text(); let value;
  try { value = JSON.parse(raw); } catch { value = { unparsed: raw }; }
  return { status: response.status, body: value, raw };
}
const apiPath = (artifactId, operation) => `/api/projects/${encodeURIComponent(projectId)}/snapshots/${encodeURIComponent(snapshotId)}/artifacts/${encodeURIComponent(artifactId)}/preview/${operation}`;
const directQuestionnaire = (subject, data, options) => {
  const assembled = runtime.assembleQuestionnaire(questionnaire.resource, content);
  if (!assembled.success) return assembled;
  const populated = runtime.populateQuestionnaire(assembled.value, subject, content, options);
  if (!populated.success) return populated;
  const validated = runtime.validateQuestionnaireResponse(assembled.value, populated.value);
  if (!validated.success) return validated;
  return { success: true, value: { questionnaire: assembled.value, response: populated.value, issues: validated.value?.issues ?? [] } };
};
await mkdir(outputDir, { recursive: true });
const allSourcePaths = [fixtureIndexPath];
for (const fixture of fixtures) { allSourcePaths.push(resolve(dirname(fixtureRoot), fixture.dataBundlePath), resolve(assertionRoot, fixture.id, 'assertions.json')); }
const before = Object.fromEntries(await Promise.all(allSourcePaths.map(async path => [path, await hash(path)])));
const cases = [];
for (const fixture of fixtures) {
  if (fixture.evaluationDate !== evaluationDate) die(`${fixture.id}: fixture evaluation date differs from config`);
  if (JSON.stringify(fixture.measurementPeriod) !== JSON.stringify(period)) die(`${fixture.id}: fixture measurement period differs from config`);
  const rawData = await readJson(resolve(dirname(fixtureRoot), fixture.dataBundlePath));
  const assertions = await readJson(resolve(assertionRoot, fixture.id, 'assertions.json'));
  const subject = fixture.subject;
  const encounter = fixture.encounter;
  if (!subject || !encounter) die(`${fixture.id}: fixture must declare subject and encounter`);
  // The service receives raw QuestionnaireResponse input. Mirror its shared RH
  // extraction/reconciliation path for direct CPG and Measure parity only.
  const sourceResponse = resources(rawData).find(resource => resource.resourceType === 'QuestionnaireResponse');
  let data = rawData;
  let extraction = { status: 'not-invoked', reason: 'No QuestionnaireResponse' };
  if (sourceResponse) {
    const extracted = runtime.extractQuestionnaireObservations(questionnaire.resource, sourceResponse, subject, { encounter });
    if (!extracted.success) die(`${fixture.id}: direct extraction failed: ${extracted.error}`);
    extraction = extracted.value;
    data = runtime.reconcileExtractedObservations(rawData, `QuestionnaireResponse/${sourceResponse.id}`, extraction.status === 'extracted' ? extraction.transaction : undefined);
  }
  const body = { subject, encounter, patientData: rawData, evaluationDate, measurementPeriod: period };
  const options = { data, encounter, evaluationDate, measurementPeriod: period };
  const artifactResults = [];
  for (const plan of planResources) {
    const actual = await post(apiPath(plan.artifactId, 'apply'), body);
    const direct = runtime.applyPlanDefinition(plan.resource, subject, content, options);
    const value = actual.body?.requestGroupBundle;
    const equal = actual.status === 200 && direct.success === true && JSON.stringify(normalize(value)) === JSON.stringify(normalize(direct.value));
    artifactResults.push({ kind: 'apply', artifactId: plan.artifactId, canonical: plan.canonical, httpStatus: actual.status, directSuccess: direct.success === true, parity: equal, responsePath: `${fixture.id}.${plan.artifactId}.apply.json` });
    await writeJson(resolve(outputDir, `${fixture.id}.${plan.artifactId}.apply.json`), { api: actual, direct });
  }
  const measureActual = await post(apiPath(measure.artifactId, 'evaluate-measure'), body);
  const measureDirect = runtime.evaluateMeasure(measure.resource, subject, content, options);
  const measureParity = measureActual.status === 200 && measureDirect.success === true && JSON.stringify(normalize(measureActual.body?.measureReport)) === JSON.stringify(normalize(measureDirect.value));
  artifactResults.push({ kind: 'measure', artifactId: measure.artifactId, canonical: measure.canonical, httpStatus: measureActual.status, directSuccess: measureDirect.success === true, parity: measureParity, responsePath: `${fixture.id}.${measure.artifactId}.measure.json` });
  await writeJson(resolve(outputDir, `${fixture.id}.${measure.artifactId}.measure.json`), { api: measureActual, direct: measureDirect });
  const questionnaireActual = await post(apiPath(questionnaire.artifactId, 'questionnaire'), body);
  const questionnaireOptions = { data: rawData, encounter, evaluationDate, measurementPeriod: period };
  const questionnaireDirect = directQuestionnaire(subject, rawData, questionnaireOptions);
  const questionnaireCanonicalPreserved = questionnaireActual.body?.response?.questionnaire === questionnaire.canonical
    && questionnaireDirect.value?.response?.questionnaire === questionnaire.canonical;
  const questionnaireParity = questionnaireActual.status === 200 && questionnaireDirect.success === true && questionnaireCanonicalPreserved && JSON.stringify(normalize(questionnaireActual.body)) === JSON.stringify(normalize(questionnaireDirect.value));
  artifactResults.push({ kind: 'questionnaire', artifactId: questionnaire.artifactId, canonical: questionnaire.canonical, httpStatus: questionnaireActual.status, directSuccess: questionnaireDirect.success === true, canonicalPreserved: questionnaireCanonicalPreserved, parity: questionnaireParity, responsePath: `${fixture.id}.${questionnaire.artifactId}.questionnaire.json` });
  await writeJson(resolve(outputDir, `${fixture.id}.${questionnaire.artifactId}.questionnaire.json`), { api: questionnaireActual, direct: questionnaireDirect, fixtureAssertions: assertions.assertions });
  cases.push({ fixtureId: fixture.id, subject, encounter, evaluationDate, measurementPeriod: period, extraction: { status: extraction.status, observationCount: extraction.observations?.length ?? 0 }, artifactResults });
}
const negative = config.negative;
let negativeResult;
if (negative) {
  if (negative.confirmIsolated !== true || !negative.artifactId) die('negative test requires confirmIsolated: true and artifactId');
  const fixture = fixtures[0];
  const data = await readJson(resolve(dirname(fixtureRoot), fixture.dataBundlePath));
  const result = await post(apiPath(negative.artifactId, 'apply'), { subject: fixture.subject, encounter: fixture.encounter, patientData: data, evaluationDate, measurementPeriod: period });
  negativeResult = { artifactId: negative.artifactId, httpStatus: result.status, error: result.body?.error, passed: result.status === 409 && typeof result.body?.error === 'string' && result.body.error.startsWith('Preview unavailable — package incomplete:') };
  await writeJson(resolve(outputDir, 'isolated-missing-dependency-negative.json'), result);
}
const after = Object.fromEntries(await Promise.all(allSourcePaths.map(async path => [path, await hash(path)])));
const results = cases.flatMap(item => item.artifactResults);
const report = {
  checkedAt: new Date().toISOString(), runId, scope: 'Authenticated Workbench API replay versus direct public Node/WASM. Apply and Measure APIs receive raw QuestionnaireResponse fixture Bundles; their direct parity path uses the same shared SDC extraction and reconciliation. This verifier does not import or mutate the snapshot.',
  inputs: { baseUrl, projectId, snapshotId, contentPath, contentSha256: await hash(contentPath), fixtureIndexPath, fixtureIndexSha256: await hash(fixtureIndexPath), runtimePath, runtimeSha256: await hash(runtimePath), wasmPath: resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm'), wasmSha256: await hash(resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm')), cookieProvided: true, plans: plans.map(({ artifactId, canonical }) => ({ artifactId, canonical })), measure: { artifactId: measure.artifactId, canonical: measure.canonical }, questionnaire: { artifactId: questionnaire.artifactId, canonical: questionnaire.canonical }, evaluationDate, measurementPeriod: period },
  sourceFixturesUnchanged: JSON.stringify(before) === JSON.stringify(after), cases, counts: { fixtures: cases.length, artifactCalls: results.length, parityPassed: results.filter(result => result.parity).length, parityFailed: results.filter(result => !result.parity).length }, negative: negativeResult ?? { status: 'not-run', reason: 'No explicitly confirmed isolated incomplete snapshot supplied.' },
};
await writeJson(resolve(outputDir, 'workbench-api-matrix-report.json'), report);
console.log(JSON.stringify({ output: resolve(outputDir, 'workbench-api-matrix-report.json'), counts: report.counts, sourceFixturesUnchanged: report.sourceFixturesUnchanged, negative: report.negative }, null, 2));
if (!report.sourceFixturesUnchanged || report.counts.fixtures !== expectedCalls.fixtures || report.counts.artifactCalls !== expectedCalls.total || report.counts.parityPassed !== expectedCalls.total || report.counts.parityFailed || (negativeResult && !negativeResult.passed)) process.exitCode = 1;
