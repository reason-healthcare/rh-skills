#!/usr/bin/env node
/**
 * Execute the run005 score-Observation package with public Node/WASM against
 * the fresh run005 extraction capture after reconciliation into QR-free data.
 * Raw extraction and score-only tests are separately verified by
 * verify-run005-score-contract.mjs. This replays all frozen clinical outcomes.
 */
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function usage(message) {
  if (message) console.error(`Error: ${message}`);
  console.error('Usage: node verify_run003_public_node_semantics.mjs --content BUNDLE --runtime NODE_JS --prepared-root DIR --oracle-root TEST_BUNDLES --output DIR [--run-id run003]');
  process.exit(2);
}
const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, values) => {
  if (index % 2 === 0) pairs.push([value.replace(/^--/, ''), values[index + 1]]);
  return pairs;
}, []));
for (const key of ['content', 'runtime', 'prepared-root', 'oracle-root', 'output']) if (!args[key]) usage(`--${key} is required`);
const read = (file) => JSON.parse(readFileSync(file, 'utf8'));
const write = (file, value) => writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
const sha = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');
const resources = (bundle) => (bundle?.entry ?? []).map((entry) => entry?.resource).filter(Boolean);
const allActions = (actions) => (actions ?? []).flatMap((action) => [action, ...allActions(action.action)]);
const actionIdsFromNotes = (notes) => notes.map((note) => note?.text)
  .filter((text) => typeof text === 'string' && text.startsWith('Source action:'))
  .map((text) => text.slice('Source action:'.length).trim().split(/\s/, 1)[0]);
const contentPath = path.resolve(args.content);
const runtimePath = path.resolve(args.runtime);
const preparedRoot = path.resolve(args['prepared-root']);
const oracleRoot = path.resolve(args['oracle-root']);
const outputDir = path.resolve(args.output);
const runId = args['run-id'] ?? 'run005';
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(runId)) usage('--run-id must be a simple report label');
const ROOT_PROTOCOL = 'steadi-fall-risk-screening-protocol';
const EXPECTED_PLAN_IDS = new Set([
  'fall-risk-screening-recommendation',
  'fall-risk-screening-recommendation-collect-screen',
  'fall-risk-screening-recommendation-exercise-for-increased-risk',
  'fall-risk-screening-recommendation-individualize-mult-0cf8535f51',
  'steadi-fall-risk-screening-protocol',
  'steadi-fall-risk-screening-protocol-await-complete-response',
  'steadi-fall-risk-screening-protocol-collect-screen',
  'steadi-fall-risk-screening-protocol-confirm-population',
  'steadi-fall-risk-screening-protocol-exercise-guidance',
  'steadi-fall-risk-screening-protocol-multifactorial-guidance',
]);
const POSITIVE_ACTION_IDS = ['refer-exercise-intervention', 'individualize-multifactorial-decision'];
const CHILD_NOTE_ACTIONS = {
  'fall-risk-screening-recommendation-exercise-for-increased-risk': 'refer-exercise-intervention',
  'fall-risk-screening-recommendation-individualize-mult-0cf8535f51': 'individualize-multifactorial-decision',
  'steadi-fall-risk-screening-protocol-confirm-population': 'confirm-population',
  'steadi-fall-risk-screening-protocol-await-complete-response': 'await-complete-response',
  'steadi-fall-risk-screening-protocol-exercise-guidance': 'refer-exercise-intervention',
  'steadi-fall-risk-screening-protocol-multifactorial-guidance': 'individualize-multifactorial-decision',
};
const CHILD_TASK_ROOTS = new Set([
  'fall-risk-screening-recommendation-collect-screen',
  'steadi-fall-risk-screening-protocol-collect-screen',
]);
mkdirSync(outputDir, { recursive: true });
const dataManifestPath = path.join(preparedRoot, 'manifest.json');
const dataManifest = read(dataManifestPath);
if (dataManifest.runId !== 'run005' || dataManifest.contentSha256 !== sha(contentPath) || dataManifest.runtimeSha256 !== sha(runtimePath)) {
  throw new Error('Prepared data must bind the exact run005 content and public runtime');
}
for (const entry of dataManifest.cases ?? []) {
  if (sha(path.join(preparedRoot, entry.preparedDataPath)) !== entry.sha256) throw new Error(`Prepared input hash differs: ${entry.fixtureId}`);
}
const scoreContractPath = path.resolve(preparedRoot, '../score-contract.json');
const scoreContract = read(scoreContractPath);
if (scoreContract.passed !== true || scoreContract.inputs?.content?.sha256 !== sha(contentPath) || scoreContract.inputs?.runtime?.sha256 !== sha(runtimePath)) {
  throw new Error('Actual extraction and score-contract acceptance must pass for this exact package/runtime before the full clinical replay');
}
const oracleManifestPath = path.join(oracleRoot, 'manifest.json');
const oracleManifest = read(oracleManifestPath);
if (!Array.isArray(oracleManifest.cases) || oracleManifest.cases.length !== 6) throw new Error('frozen oracle manifest must contain six cases');
const oracleCases = new Map(oracleManifest.cases.map((fixture) => [fixture.id, fixture]));
if (oracleCases.size !== 6 || [...oracleCases].some(([id, fixture]) => typeof id !== 'string' || !id || !fixture)) throw new Error('frozen oracle manifest case IDs must be six unique non-empty strings');
if (!Array.isArray(dataManifest.cases) || dataManifest.cases.length !== 6) throw new Error('prepared data manifest must contain exactly six cases');
const preparedFixtureIds = dataManifest.cases.map((scenario) => scenario?.fixtureId);
const preparedFixtureSet = new Set(preparedFixtureIds);
if (preparedFixtureSet.size !== 6 || preparedFixtureIds.some((id) => typeof id !== 'string' || !oracleCases.has(id)) || preparedFixtureSet.size !== oracleCases.size) {
  throw new Error('prepared data manifest fixture IDs must exactly match the six frozen oracle case IDs');
}
function expectedTruth(fixtureId) {
  const fixture = oracleCases.get(fixtureId);
  if (!fixture?.assertions) throw new Error(`frozen oracle has no assertions for ${fixtureId}`);
  const assertionFile = read(path.join(oracleRoot, fixture.assertions));
  const values = new Map((assertionFile.assertions ?? []).map((assertion) => [assertion.expression, assertion.expected?.value]));
  const required = ['In Screening Population', 'Completed Three Question Screen', 'At Increased Fall Risk', 'Numerator'];
  for (const expression of required) if (!values.has(expression)) throw new Error(`${fixtureId}: frozen oracle lacks ${expression}`);
  const truth = {
    population: values.get('In Screening Population'),
    completed: values.get('Completed Three Question Screen'),
    risk: values.get('At Increased Fall Risk'),
    numerator: values.get('Numerator'),
  };
  if (typeof truth.population !== 'boolean' || typeof truth.completed !== 'boolean' || typeof truth.numerator !== 'boolean' || !(typeof truth.risk === 'boolean' || truth.risk === null)) {
    throw new Error(`${fixtureId}: frozen oracle expected values must be Boolean, except risk may be null`);
  }
  return truth;
}
const content = read(contentPath);
const contentResources = resources(content);
const plans = contentResources.filter((resource) => resource.resourceType === 'PlanDefinition');
const measures = contentResources.filter((resource) => resource.resourceType === 'Measure');
const questionnaires = contentResources.filter((resource) => resource.resourceType === 'Questionnaire');
const planIds = plans.map((plan) => plan.id);
const planIdSet = new Set(planIds);
if (plans.length !== EXPECTED_PLAN_IDS.size || planIdSet.size !== EXPECTED_PLAN_IDS.size || planIds.some((id) => !EXPECTED_PLAN_IDS.has(id)) || measures.length !== 1 || questionnaires.length !== 1) {
  throw new Error(`Expected Plans, exactly one Measure, and exactly one Questionnaire; got ${plans.length}/${measures.length}/${questionnaires.length}`);
}
const questionnaireCanonical = questionnaires[0].url && `${questionnaires[0].url}${questionnaires[0].version ? `|${questionnaires[0].version}` : ''}`;
if (!questionnaireCanonical) throw new Error('Packaged Questionnaire lacks versioned canonical');
const runtime = await import(pathToFileURL(runtimePath).href);
for (const name of ['applyPlanDefinition', 'evaluateMeasure']) if (typeof runtime[name] !== 'function') throw new Error(`${runtimePath} does not export ${name}`);
const cases = [];
const outputs = [];
for (const scenario of dataManifest.cases) {
  const truth = expectedTruth(scenario.fixtureId);
  const dataPath = path.join(preparedRoot, scenario.preparedDataPath);
  const data = read(dataPath);
  const inputResources = resources(data);
  const patients = inputResources.filter((resource) => resource.resourceType === 'Patient');
  const patient = patients[0];
  const encounters = inputResources.filter((resource) => resource.resourceType === 'Encounter' && resource.subject?.reference === `Patient/${patient?.id}`);
  const encounter = encounters[0];
  if (patients.length !== 1 || encounters.length !== 1 || !patient?.id || !encounter?.id) throw new Error(`${scenario.fixtureId}: needs exactly one patient-bound encounter`);
  const subject = `Patient/${patient.id}`;
  const encounterRef = `Encounter/${encounter.id}`;
  const options = { data, encounter: encounterRef, evaluationDate: '2026-06-15T09:20:00Z', measurementPeriod: oracleManifest.measurementPeriod };
  for (const plan of plans) {
    const result = runtime.applyPlanDefinition(plan, subject, content, options);
    const output = resources(result.value);
    const requestGroups = output.filter((resource) => resource.resourceType === 'RequestGroup');
    const tasks = output.filter((resource) => resource.resourceType === 'Task');
    const notes = requestGroups.flatMap((group) => group.note ?? []);
    const noteActionIds = actionIdsFromNotes(notes);
    const actions = requestGroups.flatMap((group) => allActions(group.action));
    const inPopulation = truth.population === true;
    const expectedPositive = inPopulation && truth.risk === true;
    const expectedUnknown = inPopulation && truth.risk === null;
    const expectedChildNote = CHILD_NOTE_ACTIONS[plan.id];
    const childNoteShouldApply = expectedChildNote === 'confirm-population'
      ? inPopulation
      : expectedChildNote === 'await-complete-response'
        ? expectedUnknown
        : expectedPositive;
    const checks = {
      succeeds: result.success === true,
      qrFreeInput: !inputResources.some((resource) => ['Questionnaire', 'QuestionnaireResponse'].includes(resource.resourceType)),
      explicitSubject: output.filter((resource) => ['RequestGroup', 'Task', 'CommunicationRequest'].includes(resource.resourceType)).every((resource) => resource.subject?.reference === subject || resource.for?.reference === subject),
      explicitEncounter: output.filter((resource) => ['RequestGroup', 'Task', 'CommunicationRequest'].includes(resource.resourceType)).every((resource) => resource.encounter?.reference === encounterRef),
      validActionXor: requestGroups.every((group) => allActions(group.action).every((action) => Boolean(action.resource) !== Boolean(action.action?.length))),
      noDanglingRelatedAction: requestGroups.every((group) => { const ids = new Set(allActions(group.action).map((action) => action.id).filter(Boolean)); return allActions(group.action).every((action) => (action.relatedAction ?? []).every((related) => ids.has(related.actionId))); }),
      tasksUsePackagedQuestionnaire: tasks.every((task) => task.input?.some((input) => input.valueCanonical === questionnaireCanonical)),
      outsidePopulationHasNoClinicalOutput: inPopulation || (
        tasks.length === 0
        && notes.length === 0
        && actions.filter((action) => action.title).length === 0
      ),
      noPositiveGuidanceUnlessRisk: expectedPositive || !noteActionIds.some((id) => POSITIVE_ACTION_IDS.includes(id)),
      rootPositiveGuidance: plan.id !== ROOT_PROTOCOL || !expectedPositive || POSITIVE_ACTION_IDS.every((id) => noteActionIds.includes(id)),
      rootUnknownGuidance: plan.id !== ROOT_PROTOCOL || !expectedUnknown || (
        noteActionIds.includes('await-complete-response')
        && !noteActionIds.some((id) => POSITIVE_ACTION_IDS.includes(id))
      ),
      rootKnownResponseHasNoAwait: plan.id !== ROOT_PROTOCOL || truth.risk === null || !noteActionIds.includes('await-complete-response'),
      childNoteApplicability: !expectedChildNote || noteActionIds.includes(expectedChildNote) === childNoteShouldApply,
      childTaskApplicability: !CHILD_TASK_ROOTS.has(plan.id) || tasks.length === (inPopulation ? 1 : 0),
    };
    const outputName = `${scenario.fixtureId}--${plan.id}.json`;
    write(path.join(outputDir, outputName), result.value ?? { error: result.error });
    cases.push({ kind: 'apply', fixtureId: scenario.fixtureId, root: plan.id, checks, passed: Object.values(checks).every(Boolean), error: result.error, output: outputName, noteActionIds, taskCount: tasks.length });
    if (result.success) outputs.push(...output);
  }
  const measure = measures[0];
  const result = runtime.evaluateMeasure(measure, subject, content, options);
  const report = result.value;
  const populations = Object.fromEntries((report?.group ?? []).flatMap((group) => (group.population ?? []).map((population) => [population.code?.coding?.[0]?.code, population.count])));
  const score = report?.group?.[0]?.measureScore;
  const measureChecks = {
    succeeds: result.success === true,
    individualReport: report?.resourceType === 'MeasureReport' && report.type === 'individual',
    statusComplete: report?.status === 'complete',
    correctSubject: report?.subject?.reference === subject,
    correctPeriod: report?.period?.start === options.measurementPeriod.start && report?.period?.end === options.measurementPeriod.end,
    initialPopulation: populations['initial-population'] === Number(truth.population),
    denominator: populations.denominator === Number(truth.population),
    numerator: populations.numerator === Number(truth.numerator),
    score: truth.population ? score?.value === Number(truth.numerator) : score === undefined,
    noRootDataAbsentReason: !(report?.extension ?? []).some((extension) => extension.url === 'http://hl7.org/fhir/StructureDefinition/data-absent-reason'),
  };
  const outputName = `${scenario.fixtureId}--MeasureReport-${measure.id}.json`;
  write(path.join(outputDir, outputName), report ?? { error: result.error });
  cases.push({ kind: 'measure', fixtureId: scenario.fixtureId, root: measure.id, checks: measureChecks, passed: Object.values(measureChecks).every(Boolean), error: result.error, output: outputName, populations });
  if (result.success) outputs.push(report);
}
const wasmPath = path.resolve(path.dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm');
const report = {
  runId,
  scope: 'Direct public Node/WASM run005 evaluation using QR-free data from actual score extraction bound to this package/runtime. All ten Plans and the individual Measure are compared against unchanged six-case source expectations. Extraction and alternate-source score tests are separately recorded in score-contract.json. No browser or service claim.',
  passed: cases.every((entry) => entry.passed),
  expectedCounts: { planDefinitions: plans.length, cases: dataManifest.cases.length, applyCalls: plans.length * dataManifest.cases.length, measureCalls: dataManifest.cases.length },
  inputs: { content: { path: contentPath, sha256: sha(contentPath) }, preparedData: { path: preparedRoot, manifestSha256: sha(dataManifestPath) }, frozenOracle: { path: oracleRoot, manifestSha256: sha(oracleManifestPath) }, runtime: { path: runtimePath, sha256: sha(runtimePath) }, wasm: { path: wasmPath, sha256: sha(wasmPath) } },
  cases,
};
write(path.join(outputDir, 'results.json'), report);
write(path.join(outputDir, 'runtime-output-resources.json'), { resourceType: 'Bundle', type: 'collection', entry: outputs.map((resource) => ({ resource })) });
console.log(JSON.stringify({ passed: report.passed, expectedCounts: report.expectedCounts, failures: cases.filter((entry) => !entry.passed) }, null, 2));
if (!report.passed) process.exitCode = 1;
