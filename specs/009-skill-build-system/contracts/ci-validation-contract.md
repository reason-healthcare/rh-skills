# Contract: CI Validation and Installability

## Purpose

Define what repository CI must prove before generated bundles are treated as
distribution-ready for bundled platforms.

## CI Responsibilities

- run the build workflow for the relevant bundled platforms
- run structural validation against each platform profile
- run platform-oriented installability smoke checks
- fail the workflow on blocking validation or installability errors

## Installability Scope for 009

Installability checks confirm that a generated bundle can be loaded or consumed
in the expected distribution flow for a bundled platform.

For 009, this does **not** include:

- model-quality scoring
- transcript ranking
- scenario replay through Ollama or other live model backends

## Required Reporting

CI output must identify:

- platform
- skill
- failing validation or installability rule
- enough context to reproduce the failure locally

## Readiness Rule

A bundled-platform distribution is releasable only when both structural
validation and installability smoke checks pass.
