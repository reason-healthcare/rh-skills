#!/usr/bin/env node
/**
 * Compare the standalone local-RH route with the public Node/WASM API.
 *
 * This intentionally leaves the source fixture tree untouched. It accepts a
 * content Bundle and a fixture manifest, captures each raw response, and
 * normalizes only output-resource generated IDs, references to those IDs, and
 * explicit generated timestamp metadata before comparing FHIR semantics.
 */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

function usage(message) {
  if (message) console.error(`Error: ${message}\n`);
  console.error(`Usage:
  node verify-standalone-api-parity.mjs \\
    --content /absolute/package-content-bundle.json \\
    --plan 'https://example/PlanDefinition/fall-screening|0.2.0' \\
    --fixtures /absolute/test-bundles/manifest.json \\
    --evaluation-date 2026-12-31T09:20:00Z \\
    --output /absolute/output-directory \\
    [--standalone http://127.0.0.1:9091] \\
    [--runtime /absolute/rh/packages/cpg/dist/node.js] \\
    [--assertion-root /absolute/source-fixture-cases] \\
    [--practitioner Practitioner/example] [--organization Organization/example] \\
    [--parameters-json '{"Some Parameter": true}'] \
    --guidance-json '{"mode":"communication-request"}'

--plan may be a PlanDefinition id, URL, or exact URL|version. The verifier
requires exactly one patient-bound Encounter in every fixture unless an
explicit --encounter is supplied. It does not infer among multiple Encounters.`);
  process.exit(2);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) return usage(`unexpected argument ${key}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) return usage(`missing value for ${key}`);
    args[key.slice(2)] = value;
    index += 1;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
for (const key of ['content', 'plan', 'fixtures', 'evaluation-date', 'output', 'guidance-json']) {
  if (!args[key]) usage(`--${key} is required`);
}

const contentPath = resolve(args.content);
const manifestPath = resolve(args.fixtures);
const outputDir = resolve(args.output);
const standaloneBase = (args.standalone ?? 'http://127.0.0.1:9091').replace(/\/$/, '');
const runtimePath = resolve(args.runtime ?? '/Users/bkaney/projects/reason-healthcare/rh/packages/cpg/dist/node.js');
const evaluationDate = args['evaluation-date'];
const explicitEncounter = args.encounter;
const practitioner = args.practitioner;
const organization = args.organization;
const assertionRoot = args['assertion-root'] ? resolve(args['assertion-root']) : undefined;
let parameters;
try {
  parameters = args['parameters-json'] ? JSON.parse(args['parameters-json']) : undefined;
} catch (error) {
  usage(`--parameters-json must be JSON: ${error instanceof Error ? error.message : String(error)}`);
}
let guidance;
try {
  guidance = JSON.parse(args['guidance-json']);
} catch (error) {
  usage(`--guidance-json must be JSON: ${error instanceof Error ? error.message : String(error)}`);
}
if (!guidance || !['communication-request', 'text-request-group-action', 'informational-guidance-notes'].includes(guidance.mode)) {
  usage('--guidance-json.mode must be communication-request, text-request-group-action, or informational-guidance-notes');
}
if (['text-request-group-action', 'informational-guidance-notes'].includes(guidance.mode) && (!Array.isArray(guidance.positiveActionIds) || guidance.positiveActionIds.length === 0 || !guidance.positiveActionIds.every((id) => typeof id === 'string' && id.length > 0))) {
  usage('text-request-group-action and informational-guidance-notes require nonempty positiveActionIds');
}

const sha256 = async (path) => createHash('sha256').update(await readFile(path)).digest('hex');
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));
const writeJson = async (path, value) => writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
const resources = (bundle) => bundle?.resourceType === 'Bundle'
  ? (bundle.entry ?? []).map((entry) => entry?.resource).filter(Boolean)
  : [bundle].filter(Boolean);

function canonical(resource) {
  return resource?.url
    ? `${resource.url}${resource.version ? `|${resource.version}` : ''}`
    : undefined;
}

function findPlan(content, selector) {
  const matches = resources(content).filter((resource) => {
    if (resource.resourceType !== 'PlanDefinition') return false;
    return resource.id === selector || resource.url === selector || canonical(resource) === selector;
  });
  if (matches.length !== 1) {
    throw new Error(`--plan ${selector} resolved ${matches.length} PlanDefinitions; supply an exact id or URL|version`);
  }
  return matches[0];
}

function findQuestionnaire(content, expectedCanonical) {
  const matches = resources(content).filter((resource) => resource.resourceType === 'Questionnaire' && canonical(resource) === expectedCanonical);
  if (matches.length > 1) throw new Error(`Questionnaire ${expectedCanonical} is ambiguous in the content Bundle`);
  return matches[0];
}

function explicitContext(bundle, patientId, suppliedEncounter) {
  const subject = `Patient/${patientId}`;
  if (suppliedEncounter) return { subject, encounter: suppliedEncounter, encounterSource: 'explicit --encounter' };
  const matches = resources(bundle).filter((resource) => resource.resourceType === 'Encounter' && resource.subject?.reference === subject);
  if (matches.length !== 1 || !matches[0].id) {
    throw new Error(`${subject} has ${matches.length} matching Encounter resources; use --encounter to avoid guessing`);
  }
  return { subject, encounter: `Encounter/${matches[0].id}`, encounterSource: 'single patient-bound Encounter in fixture Bundle' };
}

function expectedBoolean(assertions, name) {
  const match = (assertions.assertions ?? []).find((entry) => entry.expression === name);
  return match?.expected?.value ?? null;
}

function outputResources(result) {
  return resources(result?.resourceType === 'Bundle' ? result : { resourceType: 'Bundle', entry: [] });
}

/**
 * The only ignored values are generated resource identifiers in output Bundle
 * entries, references to those same identifiers, entry fullUrl values for the
 * generated resources, and FHIR metadata timestamps/version IDs. Canonicals,
 * subjects, encounters, action content, and clinical fields remain compared.
 */
function normalizeGeneratedOutput(bundle) {
  const copy = structuredClone(bundle);
  // `$apply` assigns the response Bundle id independently in each process.
  // It has no semantic reference target outside this generated response.
  if (copy?.resourceType === 'Bundle') delete copy.id;
  const generated = new Map();
  let sequence = 0;
  for (const resource of outputResources(copy)) {
    if (resource.resourceType && resource.id) {
      sequence += 1;
      generated.set(`${resource.resourceType}/${resource.id}`, `${resource.resourceType}/__generated_${sequence}`);
    }
  }
  const visit = (value, key, parent) => {
    if (Array.isArray(value)) return value.forEach((item) => visit(item, undefined, value));
    if (!value || typeof value !== 'object') return;
    for (const [childKey, childValue] of Object.entries(value)) {
      if (childKey === 'meta' && childValue && typeof childValue === 'object') {
        delete childValue.lastUpdated;
        delete childValue.versionId;
      }
      if (childKey === 'timestamp') {
        delete value[childKey];
        continue;
      }
      if (childKey === 'reference' && typeof childValue === 'string' && generated.has(childValue)) {
        value[childKey] = generated.get(childValue);
        continue;
      }
      visit(childValue, childKey, value);
    }
    if (value.resourceType && value.id) {
      const mapped = generated.get(`${value.resourceType}/${value.id}`);
      if (mapped) value.id = mapped.split('/')[1];
    }
    if (key === 'fullUrl' && typeof value === 'string' && generated.has(value.replace(/^https?:\/\/[^/]+\//, ''))) {
      parent[key] = `urn:generated:${generated.get(value.replace(/^https?:\/\/[^/]+\//, ''))}`;
    }
  };
  // fullUrl is on Bundle entries, so process it before descending resources.
  if (copy?.resourceType === 'Bundle') {
    for (const entry of copy.entry ?? []) {
      const reference = typeof entry.fullUrl === 'string' ? entry.fullUrl.replace(/^https?:\/\/[^/]+\//, '') : undefined;
      if (reference && generated.has(reference)) entry.fullUrl = `urn:generated:${generated.get(reference)}`;
      visit(entry.resource, 'resource', entry);
    }
  } else {
    visit(copy);
  }
  return copy;
}

function semanticChecks(result, context, expected, questionnaireCanonical, guidanceContract, fixtureId) {
  const output = outputResources(result);
  const tasks = output.filter((resource) => resource.resourceType === 'Task');
  const communications = output.filter((resource) => resource.resourceType === 'CommunicationRequest');
  const actions = output
    .filter((resource) => resource.resourceType === 'RequestGroup')
    .flatMap((resource) => resource.action ?? []);
  const guidanceNotes = output
    .filter((resource) => resource.resourceType === 'RequestGroup')
    .flatMap((resource) => resource.note ?? [])
    .map((note) => note.text)
    .filter((text) => typeof text === 'string' && text.trim().length > 0);
  const taskIssues = tasks.flatMap((task) => {
    const issues = [];
    const questionnaireValues = (task.input ?? []).map((input) => input.valueCanonical).filter(Boolean);
    if (!questionnaireValues.includes(questionnaireCanonical) || questionnaireValues.some((value) => value !== questionnaireCanonical)) issues.push('Task questionnaire canonical is missing or differs');
    const taskSubject = task.for?.reference ?? task.subject?.reference;
    if (taskSubject !== context.subject) issues.push(`Task subject is ${taskSubject ?? 'missing'}, expected ${context.subject}`);
    if (task.encounter?.reference !== context.encounter) issues.push(`Task encounter is ${task.encounter?.reference ?? 'missing'}, expected ${context.encounter}`);
    return issues.map((issue) => ({ taskId: task.id, issue }));
  });
  const population = expected['In Screening Population'] === true;
  const increasedRisk = expected['At Increased Fall Risk'] === true;
  const outsidePopulationActionFree = population || (tasks.length === 0 && communications.length === 0 && actions.length === 0);
  const matchingGuidance = guidanceContract.mode === 'communication-request'
    ? communications
    : guidanceContract.mode === 'informational-guidance-notes'
      ? guidanceNotes
        .filter((note) => note.startsWith('Source action:'))
        .map((note) => note.slice('Source action:'.length).trim().split(/\s/, 1)[0])
        .filter((id) => guidanceContract.positiveActionIds.includes(id))
      : actions.filter((action) => guidanceContract.positiveActionIds.includes(action.id));
  const requiredPositiveCount = guidanceContract.mode === 'communication-request'
    ? 1
    : guidanceContract.positiveActionIds.length;
  const positiveGuidanceOnlyExpected = increasedRisk
    ? matchingGuidance.length === requiredPositiveCount
    : matchingGuidance.length === 0;
  return {
    taskQuestionnaireSubjectEncounter: { passed: taskIssues.length === 0, issues: taskIssues },
    noActionOutsidePopulation: { expectedPopulation: population, taskCount: tasks.length, communicationCount: communications.length, requestGroupActionCount: actions.length, informationalGuidanceNoteCount: guidanceNotes.length, passed: outsidePopulationActionFree },
    positiveGuidanceOnlyExpected: { expectedIncreasedRisk: increasedRisk, guidanceContract, fixtureId, matchingGuidance, informationalGuidanceNoteCount: guidanceNotes.length, passed: positiveGuidanceOnlyExpected },
  };
}

async function postStandalone(payload) {
  const response = await fetch(`${standaloneBase}/api/apply`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload),
  });
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { unparsedBody: text }; }
  return { httpStatus: response.status, headers: Object.fromEntries(response.headers), body, rawBody: text };
}

const content = await readJson(contentPath);
const manifest = await readJson(manifestPath);
const fixtures = manifest.cases ?? manifest.fixtures;
if (!Array.isArray(fixtures) || fixtures.length !== 6) throw new Error(`Fixture manifest must list exactly six cases; found ${fixtures?.length ?? 'none'}`);
const planDefinition = findPlan(content, args.plan);
const questionnaireResources = resources(content).filter((resource) => resource.resourceType === 'Questionnaire');
const questionnaireCanonical = manifest.questionnaireCanonical
  ?? (questionnaireResources.length === 1 ? canonical(questionnaireResources[0]) : undefined);
if (!questionnaireCanonical) throw new Error('Fixture manifest has no questionnaireCanonical and content has no unique Questionnaire');
const questionnaire = findQuestionnaire(content, questionnaireCanonical);
if (!questionnaire) throw new Error(`Content Bundle lacks exact Questionnaire ${questionnaireCanonical}`);
const fixtureRoot = dirname(manifestPath);
// The legacy assertion manifest lives beside `bundle` files. The executable
// index lives under `fixtures/`, while its `dataBundlePath` is package-root
// relative (for example `fixtures/eligible-all-no.json`). Support both
// documented layouts without rewriting either source fixture set.
const bundlePath = (fixture) => {
  if (typeof fixture.bundle === 'string') return resolve(fixtureRoot, fixture.bundle);
  if (typeof fixture.dataBundlePath === 'string') return resolve(dirname(fixtureRoot), fixture.dataBundlePath);
  throw new Error(`${fixture.id ?? 'fixture'} has no bundle path`);
};
const sourcePaths = [manifestPath];
for (const fixture of fixtures) {
  sourcePaths.push(bundlePath(fixture));
  const assertions = fixture.assertions ?? (assertionRoot && resolve(assertionRoot, fixture.id, 'assertions.json'));
  if (assertions) sourcePaths.push(resolve(fixtureRoot, assertions));
}
const sourceHashesBefore = Object.fromEntries(await Promise.all(sourcePaths.map(async (path) => [path, await sha256(path)])));
const runtimeModule = await import(pathToFileURL(runtimePath).href);
if (typeof runtimeModule.applyPlanDefinition !== 'function') throw new Error(`${runtimePath} does not export applyPlanDefinition`);
await mkdir(outputDir, { recursive: true });
const cases = [];

for (const fixture of fixtures) {
  const data = await readJson(bundlePath(fixture));
  const assertionPath = fixture.assertions ?? (assertionRoot && resolve(assertionRoot, fixture.id, 'assertions.json'));
  if (!assertionPath) throw new Error(`${fixture.id} has no assertions path; provide --assertion-root for executable fixture indexes`);
  const assertions = await readJson(resolve(fixtureRoot, assertionPath));
  const patientId = assertions.evaluationContext?.patientId ?? fixture.subject?.replace(/^Patient\//, '');
  if (!patientId) throw new Error(`${fixture.id} has no evaluationContext.patientId or Patient subject`);
  if (fixture.evaluationDate && fixture.evaluationDate !== evaluationDate) {
    throw new Error(`${fixture.id} evaluationDate ${fixture.evaluationDate} does not match required --evaluation-date ${evaluationDate}`);
  }
  const period = fixture.measurementPeriod ?? assertions.evaluationContext?.measurementPeriod ?? manifest.measurementPeriod;
  if (!period?.start || !period?.end) throw new Error(`${fixture.id} has no measurement period`);
  const context = explicitContext(data, patientId, explicitEncounter);
  const expected = Object.fromEntries(['In Screening Population', 'At Increased Fall Risk'].map((name) => [name, expectedBoolean(assertions, name)]));
  const options = { data, encounter: context.encounter, practitioner, organization, evaluationDate, measurementPeriod: period, parameters };
  const payload = { dataPayload: data, subjectPayload: context.subject, planDefinition, questionnaire, runtimeMode: 'local-rh-cpg', contentPayload: content, evaluationDate, measurementPeriod: period, encounter: context.encounter, practitioner, organization, parameters };
  const standalone = await postStandalone(payload);
  const direct = runtimeModule.applyPlanDefinition(planDefinition, context.subject, content, options);
  const standalonePath = resolve(outputDir, `${fixture.id}.standalone-response.json`);
  const directPath = resolve(outputDir, `${fixture.id}.direct-response.json`);
  await writeJson(standalonePath, standalone);
  await writeJson(directPath, direct);
  const standaloneValue = standalone.httpStatus === 200 ? standalone.body : undefined;
  const directValue = direct.success ? direct.value : undefined;
  const normalizedStandalone = standaloneValue ? normalizeGeneratedOutput(standaloneValue) : undefined;
  const normalizedDirect = directValue ? normalizeGeneratedOutput(directValue) : undefined;
  await writeJson(resolve(outputDir, `${fixture.id}.standalone-normalized.json`), normalizedStandalone);
  await writeJson(resolve(outputDir, `${fixture.id}.direct-normalized.json`), normalizedDirect);
  const parity = standalone.httpStatus === 200 && direct.success === true && JSON.stringify(normalizedStandalone) === JSON.stringify(normalizedDirect);
  const semantic = {
    standalone: standaloneValue ? semanticChecks(standaloneValue, context, expected, questionnaireCanonical, guidance, fixture.id) : { passed: false, error: `HTTP ${standalone.httpStatus}` },
    direct: directValue ? semanticChecks(directValue, context, expected, questionnaireCanonical, guidance, fixture.id) : { passed: false, error: direct.error ?? 'direct Node/WASM apply failed' },
  };
  const semanticPassed = Object.values(semantic).every((side) => side.taskQuestionnaireSubjectEncounter?.passed === true && side.noActionOutsidePopulation?.passed === true && side.positiveGuidanceOnlyExpected?.passed === true);
  cases.push({ fixtureId: fixture.id, context, expected, standalone: { httpStatus: standalone.httpStatus, rawResponse: standalonePath }, direct: { success: direct.success, rawResponse: directPath }, parity, semantic, semanticPassed });
}

const sourceHashesAfter = Object.fromEntries(await Promise.all(sourcePaths.map(async (path) => [path, await sha256(path)])));
const wasmPath = resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm');
let wasmHash;
try { wasmHash = await sha256(wasmPath); } catch { wasmHash = undefined; }
const report = {
  checkedAt: new Date().toISOString(),
  scope: 'Actual standalone API versus direct public Node/WASM PlanDefinition $apply parity. Guidance expectations are supplied explicitly in --guidance-json; source fixture manifest and case files are read-only.',
  inputs: { contentPath, contentSha256: await sha256(contentPath), planSelector: args.plan, resolvedPlanCanonical: canonical(planDefinition), fixtureManifestPath: manifestPath, fixtureManifestSha256: await sha256(manifestPath), evaluationDate, standaloneBase, runtimePath, runtimeSha256: await sha256(runtimePath), guidanceContract: guidance, wasmPath, wasmSha256: wasmHash, ignoredForParity: ['generated response Bundle id', 'output Bundle entry resource id', 'references to those generated entry resources', 'entry fullUrl for those generated resources', 'meta.lastUpdated', 'meta.versionId', 'Bundle.timestamp'] },
  sourceFixturesUnchanged: JSON.stringify(sourceHashesBefore) === JSON.stringify(sourceHashesAfter),
  cases,
  counts: { total: cases.length, parityPassed: cases.filter((item) => item.parity).length, semanticPassed: cases.filter((item) => item.semanticPassed).length },
};
await writeJson(resolve(outputDir, 'standalone-api-parity-report.json'), report);
console.log(JSON.stringify({ output: resolve(outputDir, 'standalone-api-parity-report.json'), counts: report.counts, sourceFixturesUnchanged: report.sourceFixturesUnchanged }, null, 2));
if (!report.sourceFixturesUnchanged || report.counts.parityPassed !== cases.length || report.counts.semanticPassed !== cases.length) process.exitCode = 1;
