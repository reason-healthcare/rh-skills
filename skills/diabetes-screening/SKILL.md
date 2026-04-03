---
name: "diabetes-screening"
description: "Clinical decision support for evidence-based diabetes screening using ADA criteria"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "Clinical Informatics Team"
  created: "2026-04-03"
  domain: "diabetes"
---

## Overview

This skill supports evidence-based diabetes screening decisions using American Diabetes Association (ADA) guidelines. It progresses from raw guideline text through structured criteria to a computable artifact with FHIRPath-compatible logic.

## Usage

This skill progresses through three artifact levels:

- **L1 (Discovery)**: Raw ADA guideline extracts, clinical notes
- **L2 (Semi-structured)**: Structured screening criteria and risk factor definitions
- **L3 (Computable)**: Computable value sets, measures, and pathway definitions

## Instructions

When working with this skill:

1. Use L1 artifacts as source material — do not modify them; they are the authoritative capture.
2. When deriving L2, focus on extracting discrete, testable clinical criteria from the raw text.
3. When converging to L3, map criteria to FHIRPath-compatible expressions where possible.
4. Include population denominator and numerator definitions in the measures section.

## Fixtures

See `fixtures/` for LLM test conversation pairs. Run with:
```
hi test diabetes-screening
```
