# Quickstart

Use this walkthrough to go from a new topic to validated structured and
computable artifacts.

## 1. Initialize a topic

```bash
rh-skills init diabetes-screening --title "Diabetes Screening" --author "My Team"
```

## 2. Discover and ingest source materials

Use the RH informatics skills to identify and ingest the source material for the
topic. In a typical workflow, `rh-inf-discovery` guides source selection and
`rh-inf-ingest` registers and prepares the resulting L1 artifacts.

## 3. Check topic status

```bash
rh-skills status show diabetes-screening
```

## 4. Derive structured artifacts

```bash
rh-skills promote derive diabetes-screening --source ada-guidelines --name screening-criteria
rh-skills promote derive diabetes-screening --source ada-guidelines --name risk-factors
```

## 5. Validate the L2 artifacts

```bash
rh-skills validate diabetes-screening l2 screening-criteria
```

## 6. Converge to a computable artifact

```bash
rh-skills promote combine diabetes-screening \
  --sources screening-criteria,risk-factors \
  --name diabetes-screening-pathway
```

## 7. Validate the L3 artifact

```bash
rh-skills validate diabetes-screening l3 diabetes-screening-pathway
```

## 8. Review all topics

```bash
rh-skills list
```
