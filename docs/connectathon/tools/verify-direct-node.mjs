#!/usr/bin/env node
/**
 * Execute every generated PlanDefinition and Measure with public Node/WASM,
 * using the immutable six-case oracle. Profiles express the distinct output
 * contracts; they never infer guidance expectations from generated text.
 */
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

function usage(message) {
  if (message) console.error(`Error: ${message}`)
  console.error('Usage: node verify-direct-node.mjs --content BUNDLE --runtime NODE_JS --oracle-root TEST_BUNDLES --profile run001|run002 --output REPORT_DIR')
  process.exit(2)
}

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, value, index, values) => {
    if (index % 2 === 0) pairs.push([value.replace(/^--/, ''), values[index + 1]])
    return pairs
  }, []),
)
for (const key of ['content', 'runtime', 'oracle-root', 'profile', 'output']) {
  if (!args[key]) usage(`--${key} is required`)
}

const profiles = {
  run001: {
    expectedChecks: 53,
    rootPlanIds: new Set(['fall-screening-and-guidance-recommendation', 'older-adult-fall-screening-protocol']),
    guidance: 'communication-request',
  },
  run002: {
    expectedChecks: 71,
    rootPlanIds: new Set(['fall-risk-screening-recommendation', 'steadi-fall-risk-screening-protocol']),
    guidance: 'informational-guidance-notes',
    positiveActionIds: ['refer-exercise-intervention', 'individualize-multifactorial-decision'],
    guidancePlanIds: {
      'refer-exercise-intervention': new Set([
        'fall-risk-screening-recommendation',
        'steadi-fall-risk-screening-protocol',
        'fall-risk-screening-recommendation-exercise-for-increased-risk',
        'steadi-fall-risk-screening-protocol-exercise-guidance',
      ]),
      'individualize-multifactorial-decision': new Set([
        'fall-risk-screening-recommendation',
        'steadi-fall-risk-screening-protocol',
        'fall-risk-screening-recommendation-individualize-mult-0cf8535f51',
        'steadi-fall-risk-screening-protocol-multifactorial-guidance',
      ]),
    },
    unresolvedActionId: 'await-complete-response',
  },
}
const profile = profiles[args.profile]
if (!profile) usage('--profile must be run001 or run002')

const contentPath = path.resolve(args.content)
const runtimePath = path.resolve(args.runtime)
const oracleRoot = path.resolve(args['oracle-root'])
const outputDir = path.resolve(args.output)
const read = (file) => JSON.parse(readFileSync(file, 'utf8'))
const save = (file, value) => writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
const sha = (file) => createHash('sha256').update(readFileSync(file)).digest('hex')
const canonical = (resource) => resource?.url ? `${resource.url}${resource.version ? `|${resource.version}` : ''}` : undefined
const resources = (bundle) => (bundle?.entry ?? []).map((entry) => entry?.resource).filter(Boolean)
const allActions = (actions) => (actions ?? []).flatMap((action) => [action, ...allActions(action.action)])
const noteActionIds = (notes) => notes
  .map((note) => note?.text)
  .filter((text) => typeof text === 'string' && text.startsWith('Source action:'))
  .map((text) => text.slice('Source action:'.length).trim().split(/\s/, 1)[0])

mkdirSync(outputDir, { recursive: true })
const bundleHash = sha(contentPath)
const content = read(contentPath)
const contentResources = resources(content)
const plans = contentResources.filter((resource) => resource.resourceType === 'PlanDefinition')
const measures = contentResources.filter((resource) => resource.resourceType === 'Measure')
const questionnaires = contentResources.filter((resource) => resource.resourceType === 'Questionnaire')
if (!plans.length || measures.length !== 1 || questionnaires.length !== 1) {
  throw new Error(`Expected generated Plans, exactly one Measure, and exactly one Questionnaire; got ${plans.length}/${measures.length}/${questionnaires.length}`)
}
const manifest = read(path.join(oracleRoot, 'manifest.json'))
if (!Array.isArray(manifest.cases) || manifest.cases.length !== 6) throw new Error('oracle manifest must contain exactly six cases')
const runtime = await import(pathToFileURL(runtimePath).href)
for (const fn of ['applyPlanDefinition', 'evaluateMeasure', 'validateQuestionnaireResponse']) {
  if (typeof runtime[fn] !== 'function') throw new Error(`${runtimePath} does not export ${fn}`)
}

const results = []
const outputResources = []
for (const scenario of manifest.cases) {
  const data = read(path.join(oracleRoot, scenario.bundle))
  const oracle = read(path.join(oracleRoot, scenario.assertions))
  const expected = Object.fromEntries((oracle.assertions ?? []).map((assertion) => [assertion.expression, assertion.expected?.value ?? null]))
  for (const expression of ['In Screening Population', 'Completed Three Question Screen', 'Exercise Intervention Applicable', 'Consider Multifactorial Intervention', 'Initial Population', 'Denominator', 'Numerator']) {
    if (!(expression in expected)) throw new Error(`${scenario.id}: oracle lacks ${expression}`)
  }
  const subject = `Patient/${oracle.evaluationContext?.patientId}`
  const encounter = resources(data).find((resource) => resource.resourceType === 'Encounter' && resource.subject?.reference === subject)
  if (!encounter?.id) throw new Error(`${scenario.id}: exactly one patient-bound Encounter is required`)
  const options = {
    data,
    encounter: `Encounter/${encounter.id}`,
    evaluationDate: '2026-06-15T09:20:00Z',
    measurementPeriod: oracle.evaluationContext.measurementPeriod,
  }

  for (const plan of plans) {
    const result = runtime.applyPlanDefinition(plan, subject, content, options)
    const output = resources(result.value)
    const tasks = output.filter((resource) => resource.resourceType === 'Task')
    const communications = output.filter((resource) => resource.resourceType === 'CommunicationRequest')
    const requestGroups = output.filter((resource) => resource.resourceType === 'RequestGroup')
    const actions = requestGroups.flatMap((requestGroup) => allActions(requestGroup.action))
    const notes = requestGroups.flatMap((requestGroup) => requestGroup.note ?? [])
    const outputActionIds = noteActionIds(notes)
    const checks = { succeeds: result.success === true }

    if (expected['In Screening Population'] === false) {
      checks.noScreeningOutsidePopulation = tasks.length === 0
    }
    if (expected['Exercise Intervention Applicable'] !== true) {
      checks.noInappropriatePositiveGuidance = communications.length === 0
    }
    if (profile.guidance === 'communication-request' && profile.rootPlanIds.has(plan.id)) {
      checks.oneScreeningWhenEligible = tasks.length === (expected['In Screening Population'] === true ? 1 : 0)
      checks.oneGuidanceWhenApplicable = communications.length === (expected['Exercise Intervention Applicable'] === true ? 1 : 0)
    }
    if (profile.guidance === 'informational-guidance-notes') {
      checks.textGuidanceDoesNotCreateOrders = output.every((resource) => !['ServiceRequest', 'MedicationRequest', 'CommunicationRequest'].includes(resource.resourceType))
      if (expected['In Screening Population'] === false) {
        checks.noGuidanceOutsidePopulation = actions.filter((action) => action.title).length === 0 && notes.length === 0
      }
      const positiveIds = profile.positiveActionIds
      const expectedPositive = {
        'refer-exercise-intervention': expected['Exercise Intervention Applicable'] === true,
        'individualize-multifactorial-decision': expected['Consider Multifactorial Intervention'] === true,
      }
      for (const actionId of positiveIds) {
        const actionCanBeReturned = profile.guidancePlanIds[actionId].has(plan.id)
        checks[`guidance-${actionId}`] = outputActionIds.includes(actionId) === (
          actionCanBeReturned && expectedPositive[actionId]
        )
      }
      if (profile.rootPlanIds.has(plan.id) && plan.id === 'steadi-fall-risk-screening-protocol') {
        checks.unresolvedResponseStep = outputActionIds.includes(profile.unresolvedActionId) === (expected['In Screening Population'] === true && expected['Completed Three Question Screen'] === false)
        checks.oneScreeningWhenEligible = tasks.length === (expected['In Screening Population'] === true ? 1 : 0)
      }
    }

    checks.validActionStructure = requestGroups.every((requestGroup) => allActions(requestGroup.action).every((action) => Boolean(action.resource) !== Boolean(action.action?.length)))
    checks.noDanglingActionLinks = requestGroups.every((requestGroup) => {
      const requestActions = allActions(requestGroup.action)
      const ids = new Set(requestActions.map((action) => action.id).filter(Boolean))
      return requestActions.every((action) => (action.relatedAction ?? []).every((related) => ids.has(related.actionId)))
    })
    const emitted = new Set(output.map((resource) => `${resource.resourceType}/${resource.id}`))
    checks.requestTargetsIncluded = requestGroups.every((requestGroup) => allActions(requestGroup.action).every((action) => !action.resource?.reference || emitted.has(action.resource.reference)))
    checks.nestedRequestsAreOptions = tasks.every((task) => task.intent === 'option') && requestGroups.slice(1).every((requestGroup) => requestGroup.intent === 'option')
    checks.rootIsProposal = requestGroups[0]?.intent === 'proposal'
    checks.correctTaskQuestionnaire = tasks.every((task) => task.input?.some((input) => input.valueCanonical === manifest.questionnaireCanonical))
    checks.correctSubject = requestGroups.every((requestGroup) => requestGroup.subject?.reference === subject) && tasks.every((task) => task.for?.reference === subject)
    checks.explicitEncounter = output.filter((resource) => ['RequestGroup', 'Task', 'CommunicationRequest'].includes(resource.resourceType)).every((resource) => resource.encounter?.reference === options.encounter)

    const filename = `${scenario.id}--${plan.id}.json`
    save(path.join(outputDir, filename), result.value ?? { error: result.error })
    results.push({ kind: 'apply', fixture: scenario.id, root: plan.id, checks, passed: Object.values(checks).every(Boolean), error: result.error, output: filename })
    if (result.success) outputResources.push(...output)
  }

  for (const measure of measures) {
    const result = runtime.evaluateMeasure(measure, subject, content, options)
    const report = result.value
    const populations = Object.fromEntries((report?.group ?? []).flatMap((group) => (group.population ?? []).map((population) => [population.code?.coding?.[0]?.code, population.count])))
    const checks = {
      succeeds: result.success === true,
      individualReport: report?.resourceType === 'MeasureReport' && report?.type === 'individual',
      correctSubject: report?.subject?.reference === subject,
      scoreMatchesPopulation: expected.Denominator === true ? report?.group?.[0]?.measureScore?.value === Number(expected.Numerator) : report?.group?.[0]?.measureScore === undefined,
      noMisScopedAbsentReason: !(report?.extension ?? []).some((extension) => extension.url === 'http://hl7.org/fhir/StructureDefinition/data-absent-reason'),
      correctMeasureCanonical: report?.measure === measure.url || report?.measure === canonical(measure),
      correctPeriod: report?.period?.start === options.measurementPeriod.start && report?.period?.end === options.measurementPeriod.end,
      initialPopulation: populations['initial-population'] === Number(expected['Initial Population']),
      denominator: populations.denominator === Number(expected.Denominator),
      numerator: populations.numerator === Number(expected.Numerator),
    }
    const filename = `${scenario.id}--MeasureReport-${measure.id}.json`
    save(path.join(outputDir, filename), report ?? { error: result.error })
    results.push({ kind: 'measure', fixture: scenario.id, root: measure.id, populations, checks, passed: Object.values(checks).every(Boolean), error: result.error, output: filename })
    if (result.success) outputResources.push(report)
  }

  const sourceResponse = resources(data).find((resource) => resource.resourceType === 'QuestionnaireResponse')
  if (sourceResponse) {
    for (const questionnaire of questionnaires) {
      const result = runtime.validateQuestionnaireResponse(questionnaire, sourceResponse)
      const valid = result.success === true && (result.value?.issues ?? []).length === 0
      const expectedValid = expected['Completed Three Question Screen']
      results.push({ kind: 'questionnaire-validation', fixture: scenario.id, root: questionnaire.id, expectedValid, valid, passed: valid === expectedValid })
    }
  }
}

const wasmPath = path.resolve(path.dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm')
const report = {
  checkedAt: new Date().toISOString(),
  scope: 'Independent public Node/WASM execution of all generated PlanDefinition roots, six individual MeasureReports, and supplied QuestionnaireResponses against the immutable six-case oracle. No aggregate, SDC, browser, or second-engine claim.',
  inputs: { contentPath, contentSha256: bundleHash, oracleRoot, oracleManifestSha256: sha(path.join(oracleRoot, 'manifest.json')), runtimePath, runtimeSha256: sha(runtimePath), wasmPath, wasmSha256: sha(wasmPath), profile: args.profile },
  stableInput: sha(contentPath) === bundleHash,
  expectedChecks: profile.expectedChecks,
  counts: { total: results.length, passed: results.filter((item) => item.passed).length, failed: results.filter((item) => !item.passed).length },
  results,
}
save(path.join(outputDir, 'results.json'), report)
save(path.join(outputDir, 'runtime-output-resources.json'), { resourceType: 'Bundle', type: 'collection', entry: outputResources.map((resource) => ({ resource })) })
console.log(JSON.stringify({ ...report, results: report.results.filter((item) => !item.passed) }, null, 2))
if (!report.stableInput || report.counts.total !== profile.expectedChecks || report.counts.failed !== 0) process.exitCode = 1
