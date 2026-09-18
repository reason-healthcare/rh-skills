#!/usr/bin/env node
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

function usage(message) {
  if (message) console.error(`Error: ${message}`)
  console.error('Usage: node verify-direct-node.mjs --content BUNDLE --fixtures INDEX --runtime NODE_JS --plan CANONICAL --measure CANONICAL --questionnaire CANONICAL --output REPORT')
  process.exit(2)
}

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, value, index, values) => {
    if (index % 2 === 0) pairs.push([value.replace(/^--/, ''), values[index + 1]])
    return pairs
  }, []),
)
for (const key of ['content', 'fixtures', 'runtime', 'plan', 'measure', 'questionnaire', 'output']) {
  if (!args[key]) usage(`--${key} is required`)
}

const sha256 = async (path) => createHash('sha256').update(await readFile(path)).digest('hex')
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'))
const contentPath = resolve(args.content)
const fixturesPath = resolve(args.fixtures)
const runtimePath = resolve(args.runtime)
const content = await readJson(contentPath)
const fixtureIndex = await readJson(fixturesPath)
const runtime = await import(pathToFileURL(runtimePath).href)
const wasmPath = resolve(dirname(runtimePath), '../wasm-node/rh_cpg_bg.wasm')

for (const functionName of ['applyPlanDefinition', 'evaluateMeasure', 'assembleQuestionnaire', 'populateQuestionnaire', 'validateQuestionnaireResponse']) {
  if (typeof runtime[functionName] !== 'function') throw new Error(`${runtimePath} does not export ${functionName}`)
}

const resources = (bundle) => (bundle?.resourceType === 'Bundle' ? bundle.entry ?? [] : [])
  .map((entry) => entry?.resource)
  .filter(Boolean)
const canonical = (resource) => resource?.url ? `${resource.url}${resource.version ? `|${resource.version}` : ''}` : undefined
function findOne(resourceType, reference) {
  const matches = resources(content).filter((resource) => resource.resourceType === resourceType && canonical(resource) === reference)
  if (matches.length !== 1) throw new Error(`${resourceType} ${reference} resolved ${matches.length} resources`)
  return matches[0]
}

const plan = findOne('PlanDefinition', args.plan)
const measure = findOne('Measure', args.measure)
const questionnaire = findOne('Questionnaire', args.questionnaire)
if (!Array.isArray(fixtureIndex.fixtures) || fixtureIndex.fixtures.length !== 6) throw new Error('fixture index must contain exactly six fixtures')
const executableRoot = dirname(dirname(fixturesPath))
const cases = []
for (const fixture of fixtureIndex.fixtures) {
  const data = await readJson(resolve(executableRoot, fixture.dataBundlePath))
  const options = { data, encounter: fixture.encounter, practitioner: fixture.practitioner, organization: fixture.organization, evaluationDate: fixture.evaluationDate, measurementPeriod: fixture.measurementPeriod, parameters: fixture.parameters }
  const apply = runtime.applyPlanDefinition(plan, fixture.subject, content, options)
  const evaluate = runtime.evaluateMeasure(measure, fixture.subject, content, options)
  const assembled = runtime.assembleQuestionnaire(questionnaire, content)
  const populated = assembled.success ? runtime.populateQuestionnaire(assembled.value, fixture.subject, content, options) : assembled
  const validated = populated.success ? runtime.validateQuestionnaireResponse(assembled.value, populated.value) : populated
  const questionnaireCanonicalPreserved = populated.success && populated.value?.questionnaire === args.questionnaire
  const passed = apply.success === true && evaluate.success === true && assembled.success === true && populated.success === true && validated.success === true && questionnaireCanonicalPreserved
  cases.push({ id: fixture.id, passed, applySuccess: apply.success === true, measureSuccess: evaluate.success === true, questionnaireSuccess: populated.success === true, questionnaireCanonicalPreserved })
}
const report = {
  checkedAt: new Date().toISOString(),
  scope: 'Direct public Node/WASM execution against the durable executable bundle and its six fixture inputs.',
  inputs: { contentPath, contentSha256: await sha256(contentPath), fixturesPath, fixturesSha256: await sha256(fixturesPath), runtimePath, runtimeSha256: await sha256(runtimePath), wasmPath, wasmSha256: await sha256(wasmPath), plan: args.plan, measure: args.measure, questionnaire: args.questionnaire },
  counts: { total: cases.length, passed: cases.filter((item) => item.passed).length, failed: cases.filter((item) => !item.passed).length },
  cases,
}
await mkdir(dirname(resolve(args.output)), { recursive: true })
await writeFile(resolve(args.output), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.counts.failed > 0) process.exitCode = 1
