---
name: "diabetes-screening"
description: "Clinical decision support for evidence-based diabetes screening using ADA criteria."
compatibility: "rh-skills-framework >= 0.1.0"
metadata:
  author: "Clinical Informatics Team"
  created: "2026-04-03"
  domain: "diabetes"
---

## Overview

This topic captures evidence-based diabetes screening logic derived from the ADA
Standards of Care 2024. The sample artifacts show how one raw source can be
promoted into semi-structured screening criteria and risk factors, then
converged into a computable artifact for workflow and measure use cases.

## Artifact Levels

- **L1 (Discovery)**: raw source material stored under `sources/`
- **L2 (Semi-structured)**: structured YAML artifacts in `structured/`
- **L3 (Computable)**: computable YAML artifacts in `computable/`

## Instructions

Use this sample topic as a reference for directory layout, provenance links in
`tracking.yaml`, and the expected field shapes for L2 and L3 artifacts.
