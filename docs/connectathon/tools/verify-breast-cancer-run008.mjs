#!/usr/bin/env node
/** Actual public SDC extraction, native CQL assertions, and public CPG acceptance. */
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const args = Object.fromEntries(process.argv.slice(2).reduce((items, value, index, values) => {
  if (index % 2 === 0) items.push([value.replace(/^--/, ''), values[index + 1]])
  return items
}, []))
for (const key of ['workspace', 'runtime', 'cli']) assert(args[key], `--${key} is required`)
const read = (file) => JSON.parse(readFileSync(file, 'utf8'))
const write = (file, value) => writeFileSync(file, JSON.stringify(value, null, 2) + '\n')
const sha = (file) => createHash('sha256').update(readFileSync(file)).digest('hex')
const resources = (bundle) => (bundle.entry ?? []).map((entry) => entry.resource).filter(Boolean)
const workspace = path.resolve(args.workspace)
const topic = path.join(workspace, 'topics/breast-cancer-neoadjuvant-review')
const computable = path.join(topic, 'computable')
const executable = path.join(topic, 'process/package-workspace/executable')
const contentPath = path.join(executable, 'executable-bundle.json')
const content = read(contentPath)
const q = resources(content).find((item) => item.resourceType === 'Questionnaire')
const plan = resources(content).find((item) => item.id === 'neoadjuvant-tnbc-oncology-review-pathway-protocol')
const index = read(path.join(executable, 'fixtures/index.json')).fixtures.sort((left, right) => Number(right.id.startsWith('qr-')) - Number(left.id.startsWith('qr-')))
const expectedQr = read(path.join(workspace, 'evidence/questionnaire-fixture-contract.json')).fixtures
const output = path.join(workspace, 'evidence/runtime-run008')
mkdirSync(output, { recursive: true })
const runtime = await import(pathToFileURL(path.resolve(args.runtime)).href)
const reports = []

for (const fixture of index) {
  const bundlePath = path.join(executable, fixture.dataBundlePath)
  const input = read(bundlePath)
  let data = structuredClone(input)
  let extracted = null
  const qr = resources(input).find((item) => item.resourceType === 'QuestionnaireResponse')
  let expected
  if (qr) {
    const contract = expectedQr.find((item) => item.fixtureId === fixture.id)
    expected = contract.expectedExpressions
    assert(resources(input).filter((item) => item.resourceType === 'Observation').every((item) =>
      item.code.coding.some((coding) => coding.system === 'http://loinc.org' && coding.code === '21889-1')),
      `${fixture.id}: preexisting diagnostic Observation would mask extraction`)
    extracted = runtime.extractQuestionnaireObservations(q, qr, fixture.subject, {
      encounter: qr.encounter.reference, workflowGated: true, focus: fixture.parameters?.sdcObservationFocus,
    })
    write(path.join(output, fixture.id + '-extraction.json'), extracted)
    assert.equal(extracted.success, true, `${fixture.id}: ${JSON.stringify(extracted.error)}`)
    const observations = extracted.value.observations ?? []
    assert.equal(observations.length, contract.expectedExtractionCount, `${fixture.id}: extraction count`)
    for (const observation of observations) {
      const question = q.item.find((item) => item.code.some((coding) => coding.code === observation.code.coding[0].code))
      assert(question, 'extracted Observation must use question Coding')
      const answer = qr.item.find((item) => item.linkId === question.linkId).answer[0].valueCoding
      assert.deepEqual(observation.valueCodeableConcept.coding, [answer], 'coded answer must retain identity')
      assert.equal(observation.status, 'final')
      assert.equal(observation.subject.reference, fixture.subject)
      assert.equal(observation.effectiveDateTime, qr.authored)
      assert(observation.performer.some((ref) => ref.reference === qr.author.reference))
      assert(observation.derivedFrom.some((ref) => ref.reference === 'QuestionnaireResponse/' + qr.id))
      assert.deepEqual(observation.focus ?? [], contract.focus)
      const expectedCategory = question.linkId.startsWith('clinical-') ? 'exam' : 'laboratory'
      assert(observation.category.some((value) => value.coding.some((coding) => coding.code === expectedCategory)))
    }
    data = runtime.reconcileExtractedObservations(data, 'QuestionnaireResponse/' + qr.id, extracted.value.transaction)
    write(path.join(output, fixture.id + '-combined-bundle.json'), data)
    // CQL consumes clinical Observations only. Preserve QR linkage in extracted
    // provenance but remove the QR resource to prove it is not a logic dependency.
    data.entry = data.entry.filter((entry) => entry.resource.resourceType !== 'QuestionnaireResponse')
  } else {
    const source = read(path.join(workspace, 'process/fixtures/cases', fixture.id, 'assertions.json'))
    expected = Object.fromEntries(source.assertions.map((item) => [item.expression, item.expected.value]))
  }
  const stagedPath = path.join(output, fixture.id + '-clinical-input.json')
  write(stagedPath, data)
  const actual = {}
  for (const [expression, expectedValue] of Object.entries(expected)) {
    const value = execFileSync(path.resolve(args.cli), ['cql', 'eval', path.join(computable, 'NeoadjuvantTnbcOncologyReviewRecommendationLogic.cql'), expression,
      '--data', stagedPath, '--terminology', path.join(workspace, 'tests/cql/breast-cancer-terminology.json'),
      '--subject', fixture.subject, '--evaluation-date', fixture.evaluationDate, '--lib-path', computable], { encoding: 'utf8' })
    actual[expression] = JSON.parse(value)
    assert.deepEqual(actual[expression], expectedValue, fixture.id + ': ' + expression)
  }
  const applied = runtime.applyPlanDefinition(plan, fixture.subject, content, {
    data, evaluationDate: fixture.evaluationDate, measurementPeriod: fixture.measurementPeriod,
    encounter: qr?.encounter?.reference,
  })
  write(path.join(output, fixture.id + '-apply.json'), applied)
  assert.equal(applied.success, true, `${fixture.id}: ${JSON.stringify(applied.error)}`)
  const appliedResources = resources(applied.value)
  assert(!appliedResources.some((item) => item.resourceType === 'MedicationRequest'), 'guidance must not execute regimen')
  const notes = appliedResources.flatMap((item) => item.note ?? []).map((note) => note.text)
  const guidance = notes.some((note) => note.includes('surface-neoadjuvant-tnbc-guidance'))
  assert.equal(guidance, expected['Neoadjuvant TNBC Guidance Applicable'] === true, `${fixture.id}: actionable guidance`)
  reports.push({ fixtureId: fixture.id, inputSha256: sha(bundlePath), extractionStatus: extracted?.value.status,
    extractionCount: extracted ? extracted.value.observations?.length ?? 0 : undefined, assertions: actual, guidance, passed: true })
  console.log(`${fixture.id}: passed ${Object.keys(actual).length} expressions, ${extracted ? extracted.value.observations?.length ?? 0 : 'baseline'} extracted, guidance=${guidance}`)
}

// Complete positive QR without explicit cancer focus must not silently acquire it.
const positive = index.find((fixture) => fixture.id === 'qr-tnbc-t2-n0')
const positiveData = read(path.join(executable, positive.dataBundlePath))
const positiveQr = resources(positiveData).find((item) => item.resourceType === 'QuestionnaireResponse')
const noFocus = runtime.extractQuestionnaireObservations(q, positiveQr, positive.subject, { encounter: positiveQr.encounter.reference, workflowGated: true })
assert.equal(noFocus.success, true)
assert(noFocus.value.observations.every((observation) => !observation.focus?.length))
write(path.join(output, 'no-focus-extraction.json'), noFocus)

write(path.join(output, 'acceptance.json'), { passed: true, inputs: { contentSha256: sha(contentPath), runtimeSha256: sha(path.resolve(args.runtime)), questionnaire: q.url + '|' + q.version },
  cases: reports, assertions: reports.reduce((sum, report) => sum + Object.keys(report.assertions).length, 0),
  checks: ['source diagnostic Observations absent from QR inputs', 'actual public SDC extraction', 'typed coded values', 'clinical categories', 'explicit focus', 'response provenance', 'QR-free CQL', '208 clinical assertions', 'public CPG guidance', 'no automatic regimen execution', 'no inferred focus'] })
console.log(`Passed ${reports.length} scenarios; report ${path.join(output, 'acceptance.json')}`)
