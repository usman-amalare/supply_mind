# SupplyMind agent instructions

These instructions apply to every coding agent working in this repository. Read them at the start of a task, then read the documents below before changing code.

## Authorities

1. `SUPPLYMIND_MASTER_BUILD_PROMPT.md` is the engineering authority: stack, architecture, business rules, data model, API conventions, and security requirements.
2. `SupplyMind — Product Brief (v1 Scope).pdf` is the product-scope authority: who the product is for, which capabilities are in v1, and which are non-goals.
3. Where those two conflict on engineering, follow the master prompt. Where they conflict on product scope, follow the product brief. Record the conflict and the resolution in `docs/DECISIONS.md`.
4. Section 4.3 of the master prompt is an explicit, already recorded deviation from the product brief's onboarding order. Follow that deviation.

The checked-in master prompt **ends at Section 13.2**. It references Sections 14, 15, 16, and Appendix A, but those parts are **not in the file**. Do not invent their text, do not treat the document as complete, and do not cite them as if their contents were read. Use `IMPLEMENTATION_PLAN.md` as the reconstructed stage plan. The product brief PDF is the full brief that was available; it is five pages.

## Required reading before changes

- `AGENTS.md` (this file)
- `SUPPLYMIND_MASTER_BUILD_PROMPT.md`
- `SupplyMind — Product Brief (v1 Scope).pdf`
- `IMPLEMENTATION_PLAN.md`
- `docs/DECISIONS.md`
- `ARCHITECTURE.md` when the change affects boundaries, data flow, or deployment

Re-read the master prompt sections that govern the area you are changing, and re-read the current stage in `IMPLEMENTATION_PLAN.md`, every time work resumes.

## How to build

- Build in the recorded stage order. Do not skip a prerequisite stage.
- Keep `IMPLEMENTATION_PLAN.md` current. It is the ledger: stage status, acceptance criteria, commands actually run, observed results, files changed, blockers, and the next valid stage.
- Record architectural decisions, assumptions, and unresolved questions in `docs/DECISIONS.md` before or as you act on them. Routine decisions are recorded and work continues. Do not stop for them.
- The backend is first. Do not implement frontend screens until the backend has a tested API contract for that feature. The `frontend/` directory existing is not permission to build the UI.
- Generate and commit TypeScript API types from the verified OpenAPI schema only when that contract is stable enough to be a source of truth. Until then, do not invent a parallel client model.
- Preserve existing repository files and conventions unless a decision in `docs/DECISIONS.md` explains the change. Do not overwrite the master prompt, the product brief, or the existing product README.
- Prefer the smallest dependency and infrastructure set that the current stage needs. The locked architecture is a modular monolith, one PostgreSQL 16 database, and a PostgreSQL-backed worker. Do not add Redis, a message broker, microservices, or Kubernetes without an approved decision.
- Keep migrations, SQLAlchemy models, API documentation, generated client types, and tests aligned in the same stage. Do not edit an Alembic revision after it has been applied outside a disposable local database.

## Truthfulness

- Never invent product requirements, provider capabilities, environment variable names, benchmark results, pilot outcomes, or test results.
- Never claim a command passed unless you ran it in this session and recorded the relevant output in the ledger.
- Label statements as **Implemented** (code exists and the applicable checks passed), **Measured** (produced by a command you ran), **Proposed** (designed, not built), **Assumed** (chosen but not verified), or **Blocked**.
- A mocked provider test proves the code handles that contract. It does not prove the live integration. Say so.
- Synthetic data stays labelled synthetic. Do not present it as real-world accuracy.
- Never claim a feature is complete without running its applicable checks.
- Never weaken, skip, or delete a test, or loosen a security control, to hide a failure. Fix the cause or record a real blocker.
- Never put placeholder, TODO-stubbed, hard-coded, or mock-only behaviour on a production path and call that feature complete.
- Targets in the specifications (including the 20-minute onboarding target and the 20-product hand check) are acceptance targets, not results.

## Secrets and safety

- Never print, log, commit, or echo secret values. When auditing an environment file, report variable names and whether they are set, not their values.
- Never commit a populated `.env`. Commit `.env.example` only, with placeholders.
- Do not run destructive git or database operations unless the user explicitly requests them.
- SupplyMind suggests. It has no code path that purchases stock or sends a purchase order.
- The risk engine is the only source of numbers shown to users. A language model may write prose about those numbers and must not produce, alter, or recalculate them.
- When evidence is insufficient, the product says so. Do not manufacture precise probabilities, causal contributions, or confidence.

## Reporting

Report blockers, assumptions, and unverified external integrations explicitly. A folder scaffold is not a working application. A passing unit test is not proof that an external provider works. A deployment document is not a deployed service.

Finish each stage with evidence, unresolved issues, and the next valid step.
