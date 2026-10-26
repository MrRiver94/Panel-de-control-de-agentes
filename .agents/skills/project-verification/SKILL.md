---
name: project-verification
description: Review and verify code changes in this FastAPI and plain JavaScript application. Use when the user asks to verify work, before a requested commit or PR, or when a task explicitly includes testing.
metadata:
  origin: ECC verification-loop (adapted for this repository)
---

# Project verification

Use this workflow when verification is requested or explicitly part of the task. Do not run tests merely because a code change was made; the project workflow requires tests to be requested.

## 1. Inspect the change

- Check `git status`, the diff, and changed paths.
- Review the relevant code for unintended changes, error handling, and boundary conditions.
- Keep generated frontend files in sync with `frontend/src` when the task requires it.

## 2. Run the requested checks

The repository currently exposes `npm test`, which runs Python `unittest` discovery in `backend/tests` using `backend/.venv` and JavaScript tests in `frontend/tests` with Node. Run it only when requested or required by the task. Do not assume `npm run build`, lint, type-check, or coverage scripts exist; inspect `package.json` before using any command.

If the requested check cannot run, report the exact command and the blocker. Do not claim checks passed unless they actually ran.

## 3. Report

Summarize the files reviewed, checks actually run, their results, and any issues that remain. Distinguish a static diff review from executed tests.
