# SupplyMind

**Anticipate stock-outs. Understand inventory risk. Make better replenishment decisions.**

SupplyMind is an AI-powered inventory risk intelligence platform designed for small and medium-sized businesses that sell physical products and depend on reliable inventory and vendor management.

It helps business owners identify products at risk of running out of stock, understand the factors contributing to that risk, and decide what action to take before shortages affect their operations.

Instead of relying solely on fixed reorder thresholds or guesswork, SupplyMind combines inventory records, sales history, vendor delivery performance, exchange-rate movements, and demand seasonality to produce explainable inventory risk assessments.

> **Product principle:** SupplyMind recommends. Business owners decide. The platform does not automatically purchase inventory or send purchase orders to vendors.

## Current repository status

**As of 2026-10-29 the backend can register an owner, sign them in, and read their workspace.** It is not the full SupplyMind product. Inventory, risk, alerts, email, and the frontend are not built.

- Engineering rules for agents: `AGENTS.md`
- What has actually been built and verified: `IMPLEMENTATION_PLAN.md`
- Decisions and specification gaps: `docs/DECISIONS.md`
- Target boundaries: `ARCHITECTURE.md`

The checked-in master prompt ends at Section 13.2. Sections 14–16 and Appendix A are not in that file. The Getting Started commands below describe the intended workflow. Use the implementation ledger to see which commands have been run.

---

## Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Approach](#our-approach)
- [Core Features](#core-features)
- [How It Works](#how-it-works)
- [AI and Risk Intelligence](#ai-and-risk-intelligence)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Security and Data Privacy](#security-and-data-privacy)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Testing and Quality Assurance](#testing-and-quality-assurance)
- [Deployment](#deployment)
- [Current Scope and Limitations](#current-scope-and-limitations)
- [Development Roadmap](#development-roadmap)
- [Documentation](#documentation)
- [Current repository status](#current-repository-status)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Small businesses often manage inventory using spreadsheets, manual stock counts, historical experience, and fixed reorder levels. These approaches can work under stable conditions, but they become less reliable when customer demand changes, suppliers deliver late, or operating costs fluctuate.

SupplyMind is being designed to make inventory risk easier to understand and act upon.

The platform provides a centralized workspace where businesses can manage products, record stock movements, maintain vendor information, import historical sales data, and monitor product-level inventory risk.

Its risk engine performs the numerical analysis, while an OpenAI-powered explanation layer translates validated results into understandable explanations and recommendations.

### Target users

- Small and medium-sized retailers.
- Product distributors and wholesalers.
- Businesses that depend on external suppliers.
- Inventory managers and purchasing decision-makers.
- Business owners who need actionable inventory insights without a dedicated data science team.

The initial product is designed primarily for businesses operating in Nigeria, with the Nigerian naira (NGN) as the default currency.

---

## The Problem

Inventory decisions involve several related questions:

- Which products are likely to run out of stock?
- Is current stock sufficient to cover expected demand until replenishment?
- How reliable are the vendors supplying those products?
- Could demand increase during an upcoming seasonal period?
- Could exchange-rate movements affect replenishment timing for imported goods?
- How much stock should a business consider replenishing?
- How reliable is the available evidence behind each recommendation?

Traditional reorder thresholds do not answer all these questions. A product may have sufficient stock today but still face a shortage before its next delivery arrives.

SupplyMind aims to provide a more complete, evidence-based view of these risks.

---

## Our Approach

SupplyMind combines operational inventory data, statistical estimation, explicit causal assumptions, and AI-generated explanations.

The platform is designed around four principles:

1. **Evidence before confidence:** Recommendations must reflect the quality and freshness of the available data.
2. **Explainable risk:** Users should understand the factors contributing to an assessment.
3. **Deterministic calculations:** Risk figures are calculated by the backend engine, not invented by a language model.
4. **Human-controlled decisions:** The platform supports business decisions without autonomously purchasing stock.

---

## Core Features

The following describes the intended version 1 scope. Individual features should be treated as implemented only when verified in the repository and its acceptance tests.

### 1. Business workspace and onboarding

Businesses can create an account and configure a workspace containing their company information, products, vendors, risk preferences, and notification settings.

The onboarding workflow is designed to guide users through the minimum information needed to begin assessing inventory risk.

### 2. Product and inventory management

Manage product records, including:

- Product name and SKU.
- Current stock level.
- Reorder threshold.
- Unit of measurement.
- Optional unit cost.
- Primary and backup vendors.

Stock changes are recorded through an auditable adjustment ledger rather than silently overwriting inventory history.

### 3. Vendor management

Maintain vendor information and monitor delivery performance using recorded orders.

SupplyMind uses historical delivery records to estimate vendor lead times and lateness when sufficient evidence exists.

### 4. Sales-history import

Businesses can import historical sales data through CSV files.

The import workflow is designed to validate files, preview errors, identify duplicate or unknown products, and commit valid records safely.

Sales-history imports inform demand estimation. They do not automatically change on-hand inventory unless the user explicitly enables the supported stock-deduction option.

### 5. Inventory risk assessment

The risk engine evaluates factors including:

- Current stock relative to estimated demand.
- Estimated days of stock cover.
- Expected replenishment timing.
- Historical vendor reliability.
- Demand seasonality.
- Naira exchange-rate movements for relevant imported goods.

Risk assessments include a risk band, confidence indicator, evidence quality, and data-freshness information.

### 6. Explainable AI insights

SupplyMind uses OpenAI to translate validated risk-engine outputs into plain-language explanations.

An explanation can identify the relevant contributing factors, describe why a product requires attention, communicate data limitations, and suggest an appropriate action.

The language model cannot independently change risk scores, calculate replacement figures, or introduce unsupported evidence.

### 7. Alerts and notifications

The platform is designed to identify important inventory conditions, including elevated stock-out risk and reorder thresholds being reached.

Alerts support a lifecycle for opening, acknowledging, escalating, and resolving issues. Email notifications are intended to communicate relevant changes without repeatedly notifying users about unchanged conditions.

### 8. Monitoring and auditability

The system is designed to record inventory adjustments, important business changes, risk snapshots, alert transitions, background jobs, and AI usage.

These records help explain how an assessment was produced and support operational troubleshooting.

---

## How It Works

The intended workflow is:

1. **Create a workspace:** Register and configure the business.
2. **Add inventory and vendors:** Enter product details, stock levels, reorder thresholds, and supplier information.
3. **Import sales history:** Upload available historical sales records to support demand estimation.
4. **Configure risk factors:** Select the relevant supported factors.
5. **Calculate inventory risk:** The backend evaluates demand, stock position, and replenishment timing.
6. **Explain the results:** The explanation layer converts validated calculations into readable insights.
7. **Review alerts:** The dashboard prioritizes products requiring attention.
8. **Take action:** The business decides whether to review stock, replenish earlier, contact a vendor, or monitor the situation.

The process is designed to repeat as inventory records, sales history, orders, and external signals change.

---

## AI and Risk Intelligence

SupplyMind does not depend on a language model to perform its core numerical risk calculations.

Its intelligence layer separates numerical computation from natural-language generation.

### Risk calculation

The backend risk engine is responsible for:

- Estimating demand from available sales history.
- Calculating stock cover.
- Modeling replenishment timing.
- Estimating stock-out risk.
- Evaluating supported risk factors.
- Assigning confidence and evidence tiers.
- Producing risk snapshots and factor contributions.

The model uses documented statistical methods and explicit assumptions. Its performance must be evaluated through backtesting rather than assumed.

### OpenAI integration

OpenAI provides the natural-language explanation layer.

The integration is designed to use structured outputs, schema validation, bounded retries, fallback explanations, caching, and workspace-level usage limits.

Only the minimum necessary information should be sent to the model. Sensitive business and vendor information is excluded from requests by default.

If the AI provider is unavailable, the application should continue using deterministic fallback explanations where possible.

### Supported risk factors

| Factor | Intended role |
|---|---|
| Stock position | Establishes baseline risk from current stock, demand, and nominal replenishment timing. |
| Vendor reliability | Uses historical delivery performance when sufficient evidence exists. |
| Demand seasonality | Estimates demand changes from the product's own historical sales during comparable periods. |
| Naira exchange rate | Evaluates potential replenishment-delay effects for relevant imported goods when the required evidence or explicitly configured assumptions exist. |

Not every factor will be quantifiable for every business. SupplyMind must communicate insufficient or stale evidence instead of presenting unsupported numerical contributions.

---

## Technology Stack

The planned version 1 stack is designed around a modular monolith with a separate frontend, backend, database, and background worker process.

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Routing and data | React Router, TanStack Query |
| Forms and validation | React Hook Form, Zod |
| Styling and UI | Tailwind CSS, shadcn/ui primitives |
| Visualization | Recharts |
| Backend API | Python 3.12, FastAPI, Pydantic v2 |
| Database | PostgreSQL 16 |
| ORM and migrations | SQLAlchemy 2.0, Alembic |
| Risk calculations | NumPy, SciPy, and selected supporting libraries |
| Causal modeling | NetworkX and documented structural equations |
| Language model | OpenAI API through a provider abstraction |
| Background processing | PostgreSQL-backed job queue and worker |
| Authentication | Server-side sessions, Argon2id password hashing, CSRF protection |
| Email | SMTP through an interchangeable provider interface |
| Backend testing | pytest, pytest-asyncio, HTTPX |
| Frontend testing | Vitest, React Testing Library, MSW |
| End-to-end testing | Playwright |
| Packaging and deployment | uv, npm, Docker, Docker Compose, Caddy |
| Continuous integration | GitHub Actions |

This is the intended architecture, not a claim that every dependency or service has already been implemented or deployed.

---

## System Architecture

SupplyMind follows a modular monolith architecture.

```text
┌───────────────────────────────────────┐
│            React Frontend             │
│ Dashboard · Inventory · Vendors       │
│ Orders · Imports · Alerts · Settings  │
└───────────────────┬───────────────────┘
                    │ HTTPS / REST
                    ▼
┌───────────────────────────────────────┐
│             FastAPI Backend           │
│                                       │
│ Identity and Workspaces               │
│ Catalog and Inventory                 │
│ Sales and Orders                      │
│ Risk Engine and Causal Layer          │
│ Explanations and Alerts               │
│ Notifications and Audit               │
└────────────┬────────────────┬─────────┘
             │                │
             ▼                ▼
┌─────────────────────┐  ┌─────────────────────┐
│    PostgreSQL       │  │ Background Worker   │
│ Business data       │  │ Scheduled jobs      │
│ Risk snapshots      │  │ Risk recalculation  │
│ Audit records       │  │ AI explanations     │
│ Job queue           │  │ Notifications        │
└─────────────────────┘  └──────────┬──────────┘
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                   OpenAI API          External FX source
```

The frontend communicates with the backend through a versioned REST API under `/api/v1`. Business rules and numerical calculations remain on the backend.

PostgreSQL is used for persistent business data and background-job coordination, avoiding a separate Redis or message-broker dependency in the initial version.

---

## Security and Data Privacy

Security and data isolation are core system requirements.

The intended implementation includes:

- Secure password hashing and revocable server-side sessions.
- CSRF protection for state-changing requests.
- Restricted CORS origins and production security headers.
- Workspace-scoped data access and authorization.
- Database constraints that prevent cross-workspace relationships.
- Input validation and bounded pagination.
- CSV upload limits and spreadsheet-formula-injection protection.
- Environment-based secret management.
- Rate limiting on authentication, imports, and expensive operations.
- Audit records for sensitive business changes.
- AI request minimization, structured response validation, and usage caps.
- Automated cross-workspace isolation tests.

The OpenAI API key must remain server-side and must never be exposed in the frontend bundle.

Security controls and their effectiveness must be verified through implementation and tests.

---

## Project Structure

The repository is intended to follow a structure similar to:

```text
supplymind/
├── README.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── Makefile
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── migrations/
│   ├── src/
│   │   └── supplymind/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── core/
│   │       ├── db/
│   │       └── modules/
│   │           ├── identity/
│   │           ├── workspaces/
│   │           ├── onboarding/
│   │           ├── catalog/
│   │           ├── inventory/
│   │           ├── sales/
│   │           ├── orders/
│   │           ├── signals/
│   │           ├── risk/
│   │           ├── alerts/
│   │           ├── explanations/
│   │           ├── notifications/
│   │           ├── jobs/
│   │           └── audit/
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── features/
│       ├── pages/
│       ├── routes/
│       └── lib/
├── e2e/
├── scripts/
├── deploy/
└── docs/
    ├── DECISIONS.md
    ├── RISK_ENGINE.md
    ├── SECURITY.md
    ├── API.md
    ├── RUNBOOK.md
    ├── DEPLOYMENT.md
    ├── KNOWN_LIMITATIONS.md
    └── ACCEPTANCE_REPORT.md
```

The actual repository may differ during development. The implementation plan and architecture documentation should reflect the code that exists.

---

## Getting Started

The exact setup commands depend on the current repository state and the implementation completed so far. The following is the intended local development workflow once the corresponding scripts and configuration are available.

### Prerequisites

- Git
- Python 3.12
- Node.js and npm
- Docker and Docker Compose
- Access to a PostgreSQL instance, or the project's local Compose environment

An OpenAI API key is needed for live AI-generated explanations. Local fallback explanations should remain available without it.

### 1. Clone the repository

```bash
git clone <repository-url>
cd supplymind
```

Replace `<repository-url>` with the actual repository URL.

### 2. Configure environment variables

Create a local environment file using the project's example:

```bash
cp .env.example .env
```

On Windows Command Prompt, use:

```bat
copy .env.example .env
```

Configure the required database, application, email, and optional OpenAI settings according to the environment documentation. Never commit `.env` or real credentials.

### 3. Start the development environment

Once the development Compose configuration is implemented:

```bash
docker compose -f deploy/dev/compose.yml up --build
```

Use the actual Compose filename present in the repository if it differs.

### 4. Apply database migrations

After the backend and migration configuration are available, run the repository's documented migration command. The final command should be recorded in `Makefile` and `docs/DEPLOYMENT.md`.

### 5. Start the application

Follow the repository's documented frontend and backend development commands. API documentation is expected to be available through FastAPI's OpenAPI interface in development.

**Important:** These are setup instructions for the intended project structure. Verify the actual scripts, Compose files, environment variables, and service ports before treating this section as a working installation guide.

---

## Configuration

Configuration is managed through typed backend settings and environment variables.

Expected configuration areas include:

| Area | Purpose |
|---|---|
| Application | Environment, application secret, frontend origins |
| Database | PostgreSQL connection |
| Sessions | Expiration, security, and session controls |
| OpenAI | API key, model identifier, timeout, token pricing, and usage limits |
| Exchange rates | Provider selection, refresh interval, and staleness thresholds |
| Email | SMTP host, port, sender, and credentials |
| Risk engine | Recalculation interval, model settings, and default thresholds |
| Imports | File-size and row-count limits |
| Operations | Logging, worker scheduling, and backup configuration |

The `.env.example` file should list all required variable names, their purpose, and safe example values without containing actual secrets.

---

## Testing and Quality Assurance

SupplyMind's release process is designed to require evidence that features work, rather than relying on code completion alone.

Expected quality checks include:

- Backend unit, integration, API, and security tests.
- Frontend component and API-interaction tests.
- End-to-end onboarding and inventory-risk workflows.
- Database migration and transaction tests.
- Cross-workspace authorization and data-isolation tests.
- CSV validation, duplicate detection, and import-commit tests.
- Risk-engine reference calculations and boundary tests.
- Causal contribution and evidence-tier tests.
- OpenAI response-validation, fallback, caching, and cost-limit tests.
- Background-job retry and idempotency tests.
- Linting, type checking, dependency auditing, and production build checks.

### Risk-model evaluation

The risk engine must be evaluated using historical data where available and clearly labelled synthetic data for harness validation.

Evaluation should report relevant metrics such as precision, recall, false-alert rate, warning lead time, Brier score, and sample size.

Synthetic-data results must not be presented as evidence of real-world predictive accuracy. SupplyMind must not claim superior predictive performance unless a measured comparison supports that conclusion.

---

## Deployment

The planned production architecture uses:

- A React frontend served over HTTPS.
- A FastAPI backend.
- A PostgreSQL database with persistent storage.
- A background worker running from the backend codebase.
- Caddy for reverse proxying and automatic TLS.
- Scheduled database backups to S3-compatible storage.
- Environment-based configuration and protected secrets.
- Automated checks through GitHub Actions.

The initial deployment is designed to minimize recurring infrastructure costs while preserving a path to managed PostgreSQL and more scalable infrastructure when justified.

Production readiness requires verified migrations, health checks, backup and restore procedures, security headers, logging, worker monitoring, and a documented recovery process.

---

## Current Scope and Limitations

### Included in version 1

- Business account and workspace setup.
- Product, stock, vendor, and order management.
- Historical sales CSV import.
- Inventory risk assessment.
- Vendor reliability, seasonality, and exchange-rate risk factors.
- Explainable risk assessments through OpenAI.
- Alerts and email notifications.
- Background processing, usage limits, and audit records.

### Explicitly excluded from version 1

- Automatic purchasing or sending purchase orders.
- ERP and third-party inventory integrations.
- A customer-facing public API product.
- A free-text AI chatbot.
- An interactive natural-language scenario simulator.
- Port-congestion signals without a verified suitable data source.
- Training or hosting a proprietary language model.
- Unnecessary microservices or costly infrastructure.

### Known modeling limitations

The risk engine relies on explicit assumptions about demand distributions, delivery timing, and the relationships between risk factors. Limited historical data can reduce confidence, and some products may not have sufficient data for a probability estimate.

The platform must communicate these limitations to users and avoid presenting assumptions as proven causal relationships.

---

## Development Roadmap

The implementation is intended to proceed through verified stages:

1. Repository audit and architecture foundation.
2. Database, authentication, and workspace isolation.
3. Business onboarding and configuration.
4. Product, inventory, vendor, and order management.
5. Historical sales CSV import.
6. Baseline inventory risk engine.
7. External signals and seasonality.
8. Causal reasoning and factor contributions.
9. Risk orchestration and alert lifecycle.
10. OpenAI explanation integration.
11. Email notifications and background processing.
12. Dashboard, user experience, and operational diagnostics.
13. End-to-end testing and security hardening.
14. Deployment, monitoring, and backup procedures.
15. Final acceptance audit and evidence-based completion report.

Each stage should have defined entry conditions, implementation tasks, verification commands, acceptance criteria, and a recorded completion status.

The implementation ledger must distinguish completed work from pending work and genuine external blockers.

---

## Documentation

The following documents are intended to provide more detailed engineering guidance:

- `AGENTS.md` — instructions for coding agents working in this repository.
- `ARCHITECTURE.md` — system boundaries, modules, and data flow.
- `IMPLEMENTATION_PLAN.md` — staged execution and verification ledger.
- `docs/DECISIONS.md` — architecture decisions, assumptions, and trade-offs.
- `docs/RISK_ENGINE.md` — calculations, model assumptions, confidence, and evaluation.
- `docs/SECURITY.md` — authentication, tenancy, privacy, and security controls.
- `docs/API.md` — API conventions and endpoint contracts.
- `docs/RUNBOOK.md` — routine operations and incident handling.
- `docs/DEPLOYMENT.md` — environment setup and deployment procedures.
- `docs/KNOWN_LIMITATIONS.md` — verified limitations and deferred capabilities.
- `docs/ACCEPTANCE_REPORT.md` — final acceptance evidence and outstanding issues.

Documentation must remain synchronized with the actual implementation.

---

## Contributing

Contributions should preserve SupplyMind's core architectural and product principles:

- Keep business logic in the backend service layer.
- Keep the risk engine authoritative for all numerical outputs.
- Require tenant-scoped data access.
- Add tests for new behaviour, failure cases, and security boundaries.
- Document material architecture decisions.
- Never weaken tests or security controls simply to make a build pass.
- Do not introduce new paid services or infrastructure without justification.
- Do not claim that a feature works without verifying it.

For substantial changes, document the implementation, tests, known limitations, and any migration requirements.

---

**SupplyMind — See inventory risk before it becomes a stock-out.**
