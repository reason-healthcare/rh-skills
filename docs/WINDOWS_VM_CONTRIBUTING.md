# Windows VM Contributing Guide

This guide is for contributors validating Windows behavior while developing on a
non-Windows host (for example, macOS + Windows VM).

Use this when you need to verify end-user install parity from current source
changes before merge/release.

## Goal

Validate both of these paths in the VM:

1. Local source parity install: `pipx install --force .`
2. End-user install path: `pipx install --force "git+https://github.com/reason-healthcare/rh-skills.git"`

## Prerequisites

Before running the parity workflow, confirm:

1. Windows VM PowerShell session is active.
2. Python 3.13+ is available (`py --version` or `python --version`).
3. `pipx` is installed and on PATH (`pipx --version`).
4. Git is installed and on PATH (`git --version`).
5. You are in the repo root (or your mounted repo path exists) and it contains
	`pyproject.toml`.
6. Network access to GitHub is available for `git+https` install tests.

Helpful pre-checks:

```powershell
Get-Location
Test-Path ".\pyproject.toml"

# If using an explicit mounted path instead:
Test-Path "<mounted-repo-path>"
Test-Path "<mounted-repo-path>\pyproject.toml"
```

## 1) Confirm command source

Before installing, check which launcher PowerShell resolves:

```powershell
where rh-skills
Get-Command rh-skills | Format-List Source,Definition
```

If this points to a stale or host-linked launcher, ignore/remove it for parity
testing.

## 2) Install from mounted local source

From the mounted repo root:

```powershell
Set-Location "<mounted-repo-path>"
pipx uninstall rh-skills
pipx install --force .
```

Smoke check:

```powershell
pipx run --spec rh-skills python -c "import rh_skills, rh_skills.commands, jinja2; print('ok')"
rh-skills --help
```

## 3) Verify end-user GitHub install path

```powershell
pipx uninstall rh-skills
pipx install --force "git+https://github.com/reason-healthcare/rh-skills.git"
rh-skills --help
```

If local source install passes but GitHub install fails, investigate branch,
commit, or source selection differences.

## 4) Optional wheel parity check

If you built a wheel from the host:

```powershell
pipx uninstall rh-skills
pipx install --force "<mounted-repo-path>\\dist\\rh_skills-0.1.0-py3-none-any.whl"
rh-skills --help
```