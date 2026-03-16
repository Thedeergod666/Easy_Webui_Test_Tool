# Stability And Reporting Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the current unit-test failures by fixing runtime contracts, unsafe locator parsing, smart-fix retry behavior, and pytest reporting/session-flow infrastructure.

**Architecture:** Keep the public `Keywords` API stable while tightening internal contracts and moving reusable flow execution out of test modules. Treat runtime fixes and pytest/reporting fixes as separate slices so each can be verified with focused tests before the full suite.

**Tech Stack:** Python, pytest, Playwright, pytest-html

---

### Task 1: Lock runtime contract regressions

**Files:**
- Modify: `tests/unit/test_comprehensive_improvements.py`
- Modify: `tests/unit/test_smart_fix_system.py`
- Modify: `tests/unit/test_try_status_error_handling.py`

- [ ] **Step 1: Write failing tests for statistics contract, smart-fix expression execution, and codegen prefix behavior**
- [ ] **Step 2: Run the targeted tests and confirm they fail for the expected reasons**
- [ ] **Step 3: Implement the minimal runtime changes**
- [ ] **Step 4: Re-run the targeted tests and confirm they pass**

### Task 2: Remove pytest collection/reporting side effects

**Files:**
- Create: `tests/helpers/step_flow_runner.py`
- Modify: `tests/test_flows/test_steps_by_session_json.py`
- Modify: `tests/unit/test_try_status_integration.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests for reusable step execution and report attachment handling**
- [ ] **Step 2: Run the affected tests and confirm current collection/reporting failures**
- [ ] **Step 3: Extract helper logic, defer config loading, and unify html report attachments**
- [ ] **Step 4: Re-run the affected tests and confirm the collection/reporting path is stable**

### Task 3: Final verification

**Files:**
- Modify: `framework/keywords/error_handling.py`
- Modify: `framework/keywords/element_locator.py`
- Modify: `framework/keywords/smart_fix_engine.py`
- Modify: `framework/keywords/base.py`
- Modify: `framework/utils/execution_status.py`
- Modify: `tests/unit/test_integration_scenarios.py`

- [ ] **Step 1: Fix remaining test issues that mask real regressions**
- [ ] **Step 2: Run targeted suites for runtime, reporting, and integration coverage**
- [ ] **Step 3: Run `pytest -q tests/unit -q` and confirm the suite is green**
