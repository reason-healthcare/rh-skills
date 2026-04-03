---
name: "SKILL_NAME"
description: "SKILL_DESCRIPTION"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "SKILL_AUTHOR"
  created: "CREATED_DATE"
  domain: ""
---

## Overview

SKILL_DESCRIPTION

## Usage

This skill progresses through three artifact levels:

- **L1 (Discovery)**: Raw clinical knowledge — guidelines, notes, research extracts
- **L2 (Semi-structured)**: Structured YAML artifacts derived from L1 content
- **L3 (Computable)**: Computable YAML artifacts converged from L2, FHIR-compatible

## Instructions

<!-- Describe how an agent or human should reason about and use this skill. -->

## Fixtures

Fixture files are stored in `fixtures/` as input/expected-output conversation pairs
for LLM-based testing via `hi test`.
