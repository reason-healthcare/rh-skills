---
marp: true
theme: agentic-intro
size: 16:9
paginate: true
footer: HL7 FHIR Connectathon 43 · Agent-assisted knowledge engineering
title: Agent-Assisted Clinical Knowledge Engineering
description: Joint session introduction for Reason Healthcare and Smile Digital Health approaches to repeatable, auditable, and safe generation of computable healthcare knowledge.
author: Reason Healthcare and Smile Digital Health
---

<!--
Render from the repository root with Node 22 and Marp CLI 4.3.1:
npx --yes @marp-team/marp-cli@4.3.1 docs/connectathon/slides/agentic-knowledge-session-intro.md --theme-set docs/connectathon/slides/agentic-intro.css --pdf --allow-local-files
-->

<!-- _class: title -->

<div class="eyebrow">Joint session introduction</div>

# Agent-Assisted Clinical Knowledge Engineering

<p class="lede">Repeatable frameworks for producing computable healthcare knowledge with agents</p>

<p class="partners">Reason Healthcare <span>+</span> Smile Digital Health</p>

<!--
Speaker note: This is a shared framing for two different approaches. The session compares methods and evidence, not vendors.
-->

---

<div class="eyebrow">The software precedent</div>

## Agent workflows are changing how software gets built

<div class="comparison">
<div>
<p class="comparison-label">Earlier workflow</p>
<p class="comparison-main">A developer writes most implementation details directly.</p>
</div>
<div>
<p class="comparison-label">Emerging workflow</p>
<p class="comparison-main">A developer defines intent and constraints, then reviews generated code and test evidence.</p>
</div>
</div>

<p class="callout">The durable unit of work becomes the <strong>specification, agent loop, tests, and review record</strong>, not only the code that survives.</p>

<!--
Speaker note: Treat this as a directional observation about agent-based development, not a claim that a measured percentage of all code is already generated.
-->

---

<div class="eyebrow">The same shift in healthcare</div>

## Computable knowledge has the ingredients agents can work with

<div class="four-up">
<div>
<h3>Source material</h3>
<p>Evidence, guidelines, policy, and implementation guidance</p>
</div>
<div>
<h3>Formal languages</h3>
<p>FHIR, CQL, FHIRPath, and terminology expressions</p>
</div>
<div>
<h3>Executable checks</h3>
<p>Validators, translators, engines, fixtures, and package builds</p>
</div>
<div>
<h3>Human judgment</h3>
<p>Clinical meaning, scope choices, safety review, and approval</p>
</div>
</div>

<p class="horizon"><strong>Starting now:</strong> measures, guidelines, assessments, ValueSets, CDS, and prior authorization</p>
<p class="horizon secondary"><strong>Next:</strong> implementation guides and other workflows built with FHIR, CQL, or FHIRPath</p>

---

<div class="eyebrow">The risk</div>

## A convincing draft can still fail in consequential ways

<div class="risk-stack">
<div><strong>Source failure</strong><span>Outdated, incomplete, or misread evidence</span></div>
<div><strong>Semantic failure</strong><span>Valid syntax with the wrong clinical meaning</span></div>
<div><strong>Execution failure</strong><span>Different behavior across cases, engines, or repositories</span></div>
<div><strong>Governance failure</strong><span>No reproducible record of inputs, decisions, review, or change</span></div>
</div>

<p class="callout warning">A generic chat harness can produce a draft. It does not establish trust in the result.</p>

---

<div class="eyebrow">The framework</div>

## A guardrailed agent loop turns generation into an engineering process

<div class="loop">
<div><span>01</span><strong>Bound the work</strong><p>Versioned sources, artifact scope, acceptance criteria</p></div>
<div><span>02</span><strong>Generate and refine</strong><p>Structured intent, formal artifacts, explicit decisions</p></div>
<div><span>03</span><strong>Execute the evidence</strong><p>Validation, translation, fixtures, cross-engine behavior</p></div>
<div><span>04</span><strong>Review and release</strong><p>Clinical review, provenance, packaging, unresolved issues</p></div>
</div>

<div class="feedback">Failures and review findings return to the specification, prompts, tools, and evals</div>

---

<div class="eyebrow">The evidence</div>

## Trust requires more than a valid resource

<table class="evidence-table">
<thead>
<tr><th>Question</th><th>Evidence</th></tr>
</thead>
<tbody>
<tr><td>Can another team reproduce it?</td><td>Frozen inputs, versions, instructions, environment, and outputs</td></tr>
<tr><td>Does it behave as intended?</td><td>Typed assertions, boundary cases, missing-data cases, and regression evals</td></tr>
<tr><td>Can we audit the reasoning?</td><td>Source locators, derived decisions, provenance, and review findings</td></tr>
<tr><td>Can it move between implementations?</td><td>FHIR round trips and equivalent CQL results across independent stacks</td></tr>
<tr><td>Is it ready for its claimed use?</td><td>Explicit scope, safety limits, accountable human approval, and release status</td></tr>
</tbody>
</table>

<!--
[Sources]
- https://github.com/reason-healthcare/hl7-agentic-knowledge-connectathon#interoperability-test
[/Sources]
-->

---

<div class="eyebrow">The Connectathon experiment</div>

## Two approaches, tested against common questions

<div class="approaches">
<div>
<h3>Reason Healthcare</h3>
<p>A source-to-artifact lifecycle with typed intermediate knowledge, formalization, execution, and packaged verification evidence.</p>
</div>
<div>
<h3>Smile Digital Health</h3>
<p>A human-readable clinical Domain Specific Language and integrated toolchain bridging FHIR and CQL to turn clinical knowledge into validated, executable standards—and manage it throughout its lifecycle.</p>
</div>
</div>

<div class="common-line">
<strong>We will compare:</strong> inputs and specifications · agent control · eval design · review points · reproducibility · failure handling
</div>

<!--
Speaker note: Keep the Smile description intentionally neutral until their presenters supply their preferred wording.
-->

---

<div class="eyebrow">The use cases</div>

## STEADI and breast cancer stress different parts of the process

<div class="cases">
<div>
<h3>STEADI fall-risk screening</h3>
<p class="case-question">Can the workflow preserve assessment completeness, Boolean and unknown semantics, and evidence-linked next steps?</p>
<p><strong>Artifacts:</strong> Questionnaire, Measure, PlanDefinition, Library, CQL, terminology, and package</p>
<p><strong>Evaluation focus:</strong> extraction, eligibility, missing responses, execution parity, and repeatable rebuilds</p>
</div>
<div>
<h3>Breast cancer review</h3>
<p class="case-question">Can the workflow keep receptor, staging, tumor context, source updates, and clinical uncertainty aligned?</p>
<p><strong>Artifacts:</strong> evidence and recommendation structures, PlanDefinition, Library, CQL, terminology, and package</p>
<p><strong>Evaluation focus:</strong> linked observations, three-valued logic, boundary cases, and oncology review</p>
</div>
</div>

<!--
[Sources]
- https://github.com/reason-healthcare/hl7-agentic-knowledge-connectathon/tree/main/use-cases/steadi
- https://github.com/reason-healthcare/hl7-agentic-knowledge-connectathon/tree/main/use-cases/breast-cancer
[/Sources]
-->

---

<div class="eyebrow">The session</div>

## What we will examine together

<ol class="agenda">
<li><span>1</span><div><strong>Approach walkthroughs</strong><p>How each framework represents intent, controls the agent loop, and records the work</p></div></li>
<li><span>2</span><div><strong>Use-case evidence</strong><p>What worked for STEADI and breast cancer, including failed checks and revisions</p></div></li>
<li><span>3</span><div><strong>Comparison</strong><p>Where the approaches agree, where they differ, and what each still needs</p></div></li>
<li><span>4</span><div><strong>Next iteration</strong><p>Shared evals, interoperability tests, governance patterns, and future artifact classes</p></div></li>
</ol>

---

<!-- _class: closing -->

<div class="eyebrow">A continuing track</div>

# The goal is dependable knowledge engineering at agent scale

<p class="closing-lede">This Connectathon gives us a place to test the frameworks, expose their limits, and improve the shared evaluation model.</p>

<p class="closing-question">Which guardrails and evidence should become reusable across tools, artifact types, and future Connectathons?</p>

<!--
Speaker note: Close by inviting participants to compare methods and contribute failing cases. The immediate output is learning and a stronger test harness, not a claim of production clinical approval.
-->
