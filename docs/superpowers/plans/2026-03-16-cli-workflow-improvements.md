# CLI Workflow Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the command-line workflow reliable and self-explanatory by fixing non-interactive behavior, returning correct process exit codes, and adding `init`/`validate` commands with aligned documentation.

**Architecture:** Keep the existing `main.py -> FunctionExecutor -> runner` structure, but make CLI behavior explicit through small helper functions instead of ad hoc `sys.argv` mutation. Add a focused validation layer for `test_config.json` that both `init` and `validate` can reuse, and update README/examples to match the real entrypoints and report paths.

**Tech Stack:** Python, pytest, JSON, Markdown

---

### Task 1: Lock CLI regression coverage

**Files:**
- Create: `tests/unit/test_cli_workflow.py`

- [ ] **Step 1: Write failing tests for non-interactive case listing, init, validate, and exit codes**
- [ ] **Step 2: Run the targeted tests and confirm they fail for the expected reasons**
- [ ] **Step 3: Implement the minimal CLI-facing code changes**
- [ ] **Step 4: Re-run the targeted tests and confirm they pass**

### Task 2: Add reusable config init/validate support

**Files:**
- Create: `framework/utils/config_workflow.py`
- Modify: `framework/utils/main.py`
- Modify: `framework/utils/executor.py`
- Modify: `framework/utils/ui/view_test_cases.py`
- Modify: `framework/utils/run_tests/runner.py`

- [ ] **Step 1: Introduce reusable config helpers for default config generation and validation**
- [ ] **Step 2: Route existing startup and menu actions through the shared helpers**
- [ ] **Step 3: Ensure CLI commands return explicit status codes instead of printing-only failures**
- [ ] **Step 4: Re-run the targeted CLI tests**

### Task 3: Align user-facing docs and help text

**Files:**
- Modify: `README.md`
- Modify: `framework/utils/main.py`
- Modify: `framework/utils/ui/main_menu.py`
- Modify: `reports/report_README.md`

- [ ] **Step 1: Update help text and menu labels to include `init` and `validate`**
- [ ] **Step 2: Rewrite README quick-start and report instructions to reference `main.bat/.sh` and dated report files**
- [ ] **Step 3: Re-run CLI help and smoke checks against the updated wording**

### Task 4: Final verification

**Files:**
- Modify: `tests/unit/test_cli_workflow.py`

- [ ] **Step 1: Run the targeted unit suite for CLI workflow changes**
- [ ] **Step 2: Run CLI smoke commands for `--help`, `init`, `validate`, and case listing**
- [ ] **Step 3: Confirm the repository diff only contains the intended workflow changes**
