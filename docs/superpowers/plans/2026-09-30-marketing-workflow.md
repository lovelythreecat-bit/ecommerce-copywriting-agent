# Marketing Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Replace one-shot generation with sourced marketing strategy, drafting, editing and revision.
**Architecture:** Preserve the model adapter and public generation methods. Introduce independent knowledge retrieval and typed intermediate business artifacts; keep GUI a consumer.
**Tech Stack:** Existing Python, Pydantic, LangGraph, Tkinter, pytest. No database or new model vendor dependency.
**Spec:** docs/superpowers/specs/2026-09-30-marketing-workflow-design.md

## Global Constraints

The spec fixes field names, budgets and defaults. Preserve image validation, secret handling, sync/async support and request isolation. There is no Git repository: keep a file ledger instead of inventing commits. User authorized proceeding with engineering judgment and multiple agents; no new routine approval checkpoint. Independent ownership permits parallel implementation once the interfaces below are fixed.

## Review Focus

- Sparse/contradictory inputs must not become invented product facts (prompt and real evaluation).
- Unknown source IDs must never turn into invented URLs (workflow tests).
- Malformed intermediate results must not consume the reserved final stages (budget tests).
- Custom retriever failures and total timeouts must not expose service details (workflow tests).
- New GUI request/failure must clear all previous artifacts (desktop smoke).

## Task 1: Core workflow

Ownership: marketing.py, schemas.py, agent.py, workflow.py, prompts.py, validation.py, __init__.py, tests/test_workflow.py, tests/test_agent.py, tests/test_marketing_models.py.
Interfaces: exact types in spec; consume KnowledgeRetriever.retrieve(request), default LocalKnowledgeRetriever().
- [x] Write failing tests for typed artifacts, four stages, source references, two shared repairs, exhausted budgets, timeout, usage and concurrent requests.
- [x] Run targeted pytest to establish missing functionality.
- [x] Implement types and request-local graph nodes with shared bounded stage helper; preserve final validate_output.
- [x] Run targeted tests and self-review; report files, commands and limitations.

## Task 2: Knowledge retrieval

Ownership: knowledge.py, knowledge_data.py, tests/test_knowledge.py, docs/marketing-sources.md.
Interfaces: import KnowledgeSource from marketing.py and CopyRequest from schemas.py; expose KnowledgeRetriever and LocalKnowledgeRetriever as specified.
- [x] Verify selected public professional sources and record what was actually read, dates and limitations.
- [x] Write failing tests for relevant ranking, custom documents, empty collection, isolation and deterministic results.
- [x] Implement a small curated collection with Chinese editorial summaries and traceable URLs; select by request context without requiring fixed product categories.
- [x] Run targeted tests and document a custom online retriever example contract.

## Task 3: Desktop inspection

Ownership: desktop/app.py, desktop/presentation.py if needed, tests/manual/desktop_smoke.py, tests/test_desktop_presentation.py, docs/product-design.md.
Interfaces: consume new defaulted CopyResult fields; no changes to model configuration or worker lifetime.
- [x] Add minimal artifact views with Chinese labels, safe display and no stale content.
- [x] Validate pure formatting and run actual Tk smoke covering success, failure, duplicate submission, copy, close lifecycle and artifact clearing.

## Task 4: Integration and evaluation (coordinator)

Ownership: examples/compare_workflows.py, examples/evaluation_cases.json, tests/test_evaluation.py, existing example/package smoke fixture updates, README.md, docs/verification.md, packaging metadata if needed.
- [x] Add labeled synthetic product cases and a local-credential comparison runner with no fabricated model outputs.
- [x] Update affected integration fixtures for four-stage responses, preserving adapter and install checks.
- [x] Run full pytest, Tk smoke, compile/build as appropriate. Inspect independent reviewer findings and fix substantive defects.
- [x] Record achieved checks and untested real-model copy quality accurately.

