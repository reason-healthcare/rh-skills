---
marp: true
theme: rh-skills-systematic
size: 16:9
paginate: true
footer: rh-skills · Systematic clinical knowledge engineering
title: rh-skills: Systematic Clinical Knowledge Engineering
description: How rh-skills combines agent reasoning, terminology services, deterministic CLI operations, and FHIR tooling to create reviewed computable clinical knowledge.
author: Reason Healthcare
---

<!--
Render from the repository root with Node 22 and Marp CLI 4.3.1:
npx --yes @marp-team/marp-cli@4.3.1 docs/connectathon/slides/rh-skills-systematic-knowledge-engineering.md --theme-set docs/connectathon/slides/rh-skills-systematic.css --html --allow-local-files

Repository sources: README.md; docs/INTRODUCTION.md; docs/WORKFLOW.md;
docs/COMMANDS.md; docs/EXTRACT.md; docs/FORMALIZE.md; and the curated
rh-inf-extract and rh-inf-formalize skill instructions.
-->

<!-- _class: title -->

<div class="eyebrow">Reason Healthcare</div>

# rh-skills

<p class="lede">A systematic path from clinical evidence to reviewed, computable FHIR knowledge</p>

<p class="subtle">Agents reason about meaning. Scripts make the work repeatable. Terminology services keep clinical terms governed.</p>

---

<div class="eyebrow">The design premise</div>

## Clinical knowledge needs two kinds of work

<div class="two-col">
<div>
<h3>Human and agent judgment</h3>
<p>Interpret sources, expose uncertainty, select artifact types, and decide what a clinical statement means in context.</p>
</div>
<div>
<h3>Deterministic operations</h3>
<p>Scaffold files, preserve checksums, validate schemas, track lifecycle events, build packages, and report drift the same way every time.</p>
</div>
</div>

<p class="principle"><strong>rh-skills keeps these responsibilities separate.</strong> The skill supplies reasoning guidance. The CLI carries out controlled file and validation work.</p>

<!-- Speaker note: This separation comes directly from docs/INTRODUCTION.md and docs/WORKFLOW.md. Avoid describing the system as fully autonomous. -->

---

<div class="eyebrow">The artifact lifecycle</div>

## Evidence becomes progressively more computable

<div class="pipeline">
<div>
<div class="stage">L1</div>
<h3>Sources</h3>
<p>Guidelines, measures, assessments, policies, and terminology references. Raw material is normalized to Markdown.</p>
<div class="artifact-path">sources/</div>
</div>
<div>
<div class="stage">L2</div>
<h3>Structured knowledge</h3>
<p>Human-editable YAML for evidence, decisions, pathways, terminology, measures, assessments, and policy.</p>
<div class="artifact-path">topics/&lt;topic&gt;/structured/</div>
</div>
<div>
<div class="stage">L3</div>
<h3>Computable content</h3>
<p>FHIR R4 JSON and CQL: PlanDefinitions, ValueSets, Measures, Libraries, Questionnaires, and supporting resources.</p>
<div class="artifact-path">topics/&lt;topic&gt;/computable/</div>
</div>
</div>

<p class="loop-note">A source may inform several L2 artifacts. Several L2 artifacts may converge into one computable product.</p>

---

<div class="eyebrow">The control loop</div>

## Every transition has a reviewer gate

<div class="loop">
<div>
<span class="number">01</span>
<strong>Plan</strong>
<p>The agent proposes sources, artifact scope, terminology candidates, or a formalization strategy in a review packet.</p>
</div>
<div>
<span class="number">02</span>
<strong>Implement</strong>
<p>After approval, the agent calls the CLI to create the agreed artifacts and record their lifecycle event.</p>
</div>
<div>
<span class="number">03</span>
<strong>Verify</strong>
<p>Read-only checks surface schema errors, drift, missing required fields, and later stages that cannot yet run.</p>
</div>
</div>

<p class="loop-note">Review artifacts and tracking data make each decision inspectable after the agent session ends.</p>

---

<div class="eyebrow">The deterministic backbone</div>

## The rh-skills CLI owns the repeatable work

<pre class="command"><span class="prompt">$</span> rh-skills init diabetes-screening
<span class="prompt">$</span> rh-skills ingest plan diabetes-screening
<span class="prompt">$</span> rh-skills promote plan diabetes-screening
<span class="prompt">$</span> rh-skills validate diabetes-screening structured screening-criteria
<span class="prompt">$</span> rh-skills status check-changes diabetes-screening</pre>

<div class="checklist">
<div><strong>Input control</strong> Register sources, normalize them, and retain SHA-256 checksums.</div>
<div><strong>Artifact control</strong> Apply schemas, canonical locations, and type-specific validation.</div>
<div><strong>Lifecycle control</strong> Record named events in <code>tracking.yaml</code> and report deterministic next steps.</div>
</div>

<!-- Speaker note: The CLI supports both CLI-first and agent-native operation. The agent-native mode calls this same CLI. -->

---

<div class="eyebrow">Control files and tracking</div>

## The control files make workflow state inspectable

<table class="mapping">
<thead><tr><th>File</th><th>What it controls</th><th>What reviewers can see</th></tr></thead>
<tbody>
<tr><td><code>tracking.yaml</code></td><td>Topic registry, source checksums, generated artifacts, and named lifecycle events.</td><td>What exists, what changed, and which downstream artifacts may be stale.</td></tr>
<tr><td><code>extract-plan.yaml</code></td><td>Proposed L2 artifacts, source links, required sections, concerns, and approval decisions.</td><td>Why the work has this scope before structured content is written.</td></tr>
<tr><td><code>concepts/</code> and <code>concepts-review-meta.yaml</code></td><td>Candidate codes, reviewer decisions, expansion records, final reviewer, timestamp, and review checksums.</td><td>How a source concept became an approved terminology pivot.</td></tr>
<tr><td><code>formalize-plan.yaml</code></td><td>Approved L2 inputs, FHIR strategy, expected targets, and overlap concerns.</td><td>What the formalizer is allowed to generate.</td></tr>
</tbody>
</table>

<p class="loop-note">The agent can reason over the files. The files remain the durable record of state, approval, and provenance.</p>

<!-- Speaker note: Use the diabetes-screening example project to show tracking.yaml and the extract-plan.yaml / concept review files together. -->

---

<div class="eyebrow">Annotated source to terminology artifact</div>

## Source annotations lead to an extensional ValueSet

<div class="two-col">
<div>
<h3>Normalized source frontmatter</h3>
<pre class="command compact">concepts:
- name: Prediabetes
  type: condition
  role: [inclusion-criterion]
  context: "Screening for prediabetes..."</pre>
<p class="subtle">The annotation preserves the source wording, clinical role, and a locator for review.</p>
</div>
<div>
<h3>Terminology materialization</h3>
<pre class="command compact">reviewed pivot: SNOMED CT 714628002 | Prediabetes
expansion intent: is-a descendants
FHIR output: ValueSet.compose.include.concept[]</pre>
<p class="subtle">A complete, version-pinned expansion writes explicit membership for an extensional ValueSet.</p>
</div>
</div>

<p class="loop-note">Sequence: annotate the source, review the pivot, preserve the expansion rule, validate the complete result, then write explicit ValueSet members.</p>

<!-- Speaker note: The example source frontmatter and concepts.yaml live under example-project/. Keep search as discovery; an approved pivot and complete pinned expansion establish membership. -->

---

<div class="eyebrow">Terminology as a controlled input</div>

## Pivot terms turn clinical language into reviewable terminology work

<div class="terminology-flow">
<div><strong>Clinical term</strong><span>“Hypertension,” “blood pressure,” or a named medication appears in a source or structured artifact.</span></div>
<div><strong>Pivot term</strong><span>ReasonHub search proposes code candidates in the appropriate system. A reviewer chooses the usable anchor and excludes alternatives.</span></div>
<div><strong>Computable identity</strong><span>The approved system, code, display, and review decision carry into terminology artifacts and executable FHIR resources.</span></div>
</div>

<pre class="command compact"><span class="comment"># Record candidates returned by terminology search</span>
<span class="prompt">$</span> rh-skills promote concept enrich &lt;topic&gt; "Hypertension" \
  --candidate "http://snomed.info/sct|38341003|Hypertensive disorder"

<span class="comment"># A reviewer records the clinical decision</span>
<span class="prompt">$</span> rh-skills promote concept review &lt;topic&gt; "Hypertension" --approve-code 38341003</pre>

---

<div class="eyebrow">Terminology expansion</div>

## Expansions preserve the rule that produced membership

<table class="mapping">
<thead><tr><th>Step</th><th>What happens</th><th>Why it matters</th></tr></thead>
<tbody>
<tr><td>Anchor</td><td>An approved SNOMED concept acts as the clinical pivot for a hierarchy or relationship query.</td><td>The expansion begins with a reviewed meaning, not a broad text search.</td></tr>
<tr><td>Expansion</td><td>ReasonHub expands the intended hierarchy, such as descendants of a concept, using a specified filter.</td><td>A complete, pinned expansion supplies membership rather than a hand-maintained code list.</td></tr>
<tr><td>Review</td><td>Related codes and the expansion rule remain identifiable in the concept review record.</td><td>Clinical reviewers can accept, exclude, or defer the result before it becomes content.</td></tr>
<tr><td>Formalize</td><td>The terminology strategy emits FHIR ValueSet and ConceptMap resources, with expansion provenance retained where supplied.</td><td>Downstream CQL and FHIR artifacts retain a testable terminology boundary.</td></tr>
</tbody>
</table>

<p class="loop-note">Search discovers candidates. An approved pivot plus a pinned expansion defines computable membership.</p>

<!-- Speaker note: The extraction skill makes SNOMED anchor expansion optional and reviewer-directed. The formalization skill uses ReasonHub ValueSet expansion for hierarchical sets. -->

---

<div class="eyebrow">Formalization</div>

## Artifact type selects the FHIR strategy

<table class="mapping">
<thead><tr><th>L2 artifact</th><th>Primary FHIR output</th><th>Supporting content</th></tr></thead>
<tbody>
<tr><td>Terminology</td><td>ValueSet</td><td>ConceptMap</td></tr>
<tr><td>Decision table or policy</td><td>PlanDefinition + ActivityDefinition</td><td>Library, CQL, DTR Questionnaire where applicable</td></tr>
<tr><td>Care pathway</td><td>PlanDefinition + ActivityDefinition</td><td>Coded actions and protocol steps</td></tr>
<tr><td>Measure</td><td>Measure</td><td>Library and CQL</td></tr>
<tr><td>Assessment</td><td>Questionnaire</td><td>Scoring library where needed</td></tr>
<tr><td>Evidence summary</td><td>Evidence</td><td>EvidenceVariable</td></tr>
</tbody>
</table>

<p class="principle">PlanDefinition coordinates workflow. ActivityDefinition carries reusable, coded actions. The plan names both before the CLI writes them.</p>

---

<div class="eyebrow">The runtime toolchain</div>

## The rh-skills and rh toolchain

<pre class="command"><span class="comment"># Create FHIR JSON and CQL from approved L2 content</span>
<span class="prompt">$</span> rh-skills formalize &lt;topic&gt; &lt;artifact&gt;

<span class="comment"># Delegate CQL syntax and translation to the rh CLI</span>
<span class="prompt">$</span> rh-skills cql validate &lt;topic&gt; &lt;Library&gt;
<span class="prompt">$</span> rh-skills cql translate &lt;topic&gt; &lt;Library&gt;

<span class="comment"># Stage and build the FHIR distribution package with rh</span>
<span class="prompt">$</span> rh-skills package &lt;topic&gt; --pack</pre>

<div class="two-col">
<div><h3>rh-skills</h3><p>Lifecycle, plans, review gates, structured artifacts, FHIR scaffolding, and package orchestration.</p></div>
<div><h3>rh</h3><p>CQL validation and compilation, then FHIR package checking, building, and packing.</p></div>
</div>

---

<div class="eyebrow">System evidence</div>

## The deliverable includes the proof trail

<div class="checklist">
<div><strong>Provenance</strong> Registered source files, checksums, normalized text, and artifact-level evidence traceability.</div>
<div><strong>Review record</strong> Extract and formalize plans, concept coding decisions, conflicts, and reviewer finalization metadata.</div>
<div><strong>Build evidence</strong> Schema validation, CQL validation and ELM translation, package checks, and fixture-oriented tests.</div>
<div><strong>Drift detection</strong> Source checksums identify changes and name downstream structured or computable artifacts that may be stale.</div>
</div>

<p class="loop-note">The output is more than a FHIR resource. It includes enough context to rebuild, review, and challenge the result.</p>

---

<!-- _class: closing -->

<div class="eyebrow">The operating model</div>

# rh-skills makes knowledge engineering systematic

<p class="closing-lede">Clinical experts and agents work where judgment matters. Terminology services resolve and expand meaning. Deterministic commands preserve the record and carry the content into executable FHIR artifacts.</p>

<div class="closing-grid">
<div><strong>Reasoned</strong><p>Source interpretation and clinical choices remain visible and reviewable.</p></div>
<div><strong>Governed</strong><p>Pivot terms, expansions, and ValueSet membership follow explicit terminology decisions.</p></div>
<div><strong>Repeatable</strong><p>Scripts, validation, packaging, and drift checks turn the workflow into a toolchain.</p></div>
</div>

<!-- Speaker note: Documentation sources are listed in the opening comment. This closing makes no claim that the tools replace clinical governance or production clinical approval. -->
