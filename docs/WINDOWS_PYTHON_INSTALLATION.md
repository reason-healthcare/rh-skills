# Windows Setup Guide for Python CLI Tools

1. Install Python from the official Windows installer
2. Install pipx
3. Install Git
4. Use pipx to install each CLI globally for that user

## 1) Install Python

Python 3.13+ is required. Download and run the official Python 3.13 or newer Windows installer from [python.org](https://www.python.org/downloads/windows/).

During installation, check **"Add python.exe to PATH"**.

After installation, verify in PowerShell:

```powershell
py --version
```

or

```powershell
python --version
```

On Windows, `py` is often the safest command to use because it avoids some PATH confusion.

## 2) Install pipx

Pipx keeps each tool isolated in its own virtual environment while exposing a normal command on PATH.

In PowerShell:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Then **close and reopen the terminal**. The `ensurepath` step updates PATH so pipx-installed apps can be run directly.

If `py` is not available but `python` is:

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

Verify:

```powershell
pipx --version
```

## 3) Install Git

Pipx needs Git to install packages directly from GitHub repositories.

Download and run the official installer from [git-scm.com](https://git-scm.com/download/win).

The defaults are fine for most users. Make sure **"Git from the command line and also from 3rd-party software"** is selected so Git is added to PATH.

Close and reopen the terminal, then verify:

```powershell
git --version
```

## 4) Install the CLI tool with pipx

For a package published on GitHub:

```powershell
pipx install git+https://github.com/reason-healthcare/rh-skills.git
```

Verify it installed:

```powershell
pipx list
```

The CLI command should now be available directly in any new terminal window.

## Troubleshooting

- **`pipx: command not found`** — Close and reopen the terminal after `pipx ensurepath`. If still missing, run `py -m pipx ensurepath` again and check that `%USERPROFILE%\.local\bin` is in your PATH.
- **`git: command not found` during pipx install** — Git isn't on PATH. Reinstall Git and select the command-line option, then reopen the terminal.
- **Upgrading a tool later** — `pipx upgrade <package-name>` or `pipx reinstall <package-name>` for a fresh install from the same source.
