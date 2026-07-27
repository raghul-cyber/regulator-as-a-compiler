<div align="center">

# <img src="https://capsule-render.vercel.app/api?type=waving&color=0:000000,100:0a0a0a&height=200&section=header&text=Regulation-as-Code%20Compiler&fontSize=42&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=YC%20Winter%202026%20%E2%80%A2%20GDPR%20%26%20Regulatory%20Compliance,%20Compiled&descAlignY=58&descSize=16" alt="Regulation-as-Code Compiler Header" width="100%" />

<a href="https://github.com/DenverCoder1/readme-typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Inter&weight=600&size=20&duration=3000&pause=1000&color=9CA3AF&center=true&vCenter=true&width=600&height=50&lines=Turns+regulatory+text+into+machine-readable+policy.;GDPR+%26+SOC2+compliance%2C+compiled.;Upload+a+regulation.+Get+an+enforceable+API.;Deterministic.+Auditable.+Developer-first." alt="Typing SVG" /></a>

<br />

[![CI Status](https://img.shields.io/github/actions/workflow/status/rcrag/regulation-as-code-compiler/ci.yml?branch=main&style=for-the-badge&logo=github&label=CI%20Build)](https://github.com/rcrag/regulation-as-code-compiler/actions)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20YC-0a0a0a?style=for-the-badge&border=1&borderColor=374151)](LICENSE)
[![Version](https://img.shields.io/badge/Release-v0.1.0--alpha-2563EB?style=for-the-badge)](https://github.com/rcrag/regulation-as-code-compiler/releases)
[![Next.js](https://img.shields.io/badge/Next.js-14.2.35-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.2.5-520253?style=for-the-badge)](https://github.com/pgvector/pgvector)
[![Celery](https://img.shields.io/badge/Celery-5.4.0-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)

</div>

<br />

## What is Regulation-as-Code Compiler?

**Regulation-as-Code Compiler** is an enterprise-grade compliance automation platform that ingests complex legal statutes, regulatory frameworks (GDPR, EU AI Act, SOC2, HIPAA), and internal governance documents, transforming them into structured, machine-readable rules and deterministic enforcement APIs. Unlike legacy governance tools or unstructured chat assistants, our compiler uses AI-powered semantic extraction combined with rigorous vector deduplication (`pgvector`) and human-in-the-loop validation to produce an **enforceable compliance graph**. Engineers and compliance officers can test system architectures in CI/CD pipelines via sub-millisecond API evaluations (`POST /api/v1/check-compliance`), generate cryptographically verifiable audit evidence, and automatically track system impact across regulatory amendments.

---

## 30-Second Demo

<!-- TODO: record demo.gif — see /docs/media/README.md for instructions -->
<div align="center">
  <p><em>End-to-end demo recording in progress. See <a href="./docs/media/README.md">/docs/media/README.md</a> for recording instructions and script.</em></p>
</div>

---

## System Architecture

The repository is organized as a unified monorepo running a high-performance **FastAPI** asynchronous backend coupled with a **Next.js 14 App Router** frontend, supported by **Celery** distributed workers and **PostgreSQL 16 + pgvector**.

### A. Top-Level System Overview

```mermaid
graph TD
    Browser["Client Browser or Developer App"] -->|HTTPS and REST| Web["Next.js 14 Web App"]
    Browser -->|HTTPS and REST| API["FastAPI Backend"]
    Browser <-->|Auth Tokens and OIDC| Clerk["Clerk Authentication"]
    API <-->|Auth Validation| Clerk
    API -->|Async SQL with pgvector| DB[("PostgreSQL 16 Database")]
    API -->|Task Enqueue and PubSub| Redis[("Redis Broker and Cache")]
    API -->|PutObject and GetObject| S3["S3 or Local Storage Service"]
    Redis -->|Task Dequeue| Worker["Celery Workers"]
    Worker -->|Async SQL with pgvector| DB
    Worker -->|Read and Write Documents| S3
    Worker -->|API Calls with JSON Schema| LLM["LLM Provider - OpenAI GPT-4o"]
```

### B. Regulatory Ingestion Pipeline

Our multi-stage ingestion pipeline transforms unstructured regulatory text into structured, deduplicated compliance obligations:

```mermaid
graph LR
    Upload["1. Document Upload"] --> Extract["2. Text / OCR Extraction"]
    Extract --> Segment["3. Section Segmentation"]
    Segment --> Chunk["4. Semantic Chunking"]
    Chunk --> Classify["5a. LLM Classification"]
    Classify --> LLMExtract["5b. Structured Extraction"]
    LLMExtract --> Score["5c. Confidence Scoring"]
    Score --> Dedup["6. Vector Dedup & Embedding"]
    Dedup --> Route{"7. Validation Routing"}
    Route -->|Confidence < 0.7| Review["8a. Human Review (Pending)"]
    Route -->|Confidence >= 0.7| Auto["8b. Auto-Approved"]
    Review -->|Officer Approve| Approved["9. Approved & Enforceable Policy"]
    Auto --> Approved
```

### C. Database Schema (ERD)

> [!NOTE]
> **Auto-Generated Entity Relationship Diagram**  
> This diagram is generated directly from our declarative SQLAlchemy models using our introspection script:  
> `docker compose -f infra/docker-compose.yml exec -T api python scripts/generate_erd.py`  
> It represents the exact relational schema enforced in production.

```mermaid
erDiagram
    api_keys {
        UUID id PK
        UUID org_id FK
        String key_hash
        Array scopes
        Timestamp revoked_at
        Timestamp created_at
        Timestamp updated_at
    }
    audit_log {
        UUID id PK
        UUID org_id FK
        UUID actor_id FK
        String action
        String entity_type
        UUID entity_id
        JSONB metadata_payload
        Timestamp created_at
    }
    background_jobs {
        UUID id PK
        String job_type
        String status
        JSONB payload
        String error_message
        Integer retries
        Timestamp created_at
        Timestamp updated_at
    }
    compliance_checks {
        UUID id PK
        UUID org_id FK
        UUID policy_id FK
        String input_payload_ref
        String result
        JSONB violations
        Timestamp created_at
        Timestamp updated_at
    }
    document_sections {
        UUID id PK
        UUID source_document_id FK
        String reference_label
        String raw_text
        Integer order_index
        Timestamp created_at
        Timestamp updated_at
    }
    impact_records {
        UUID id PK
        UUID org_id FK
        UUID system_mapping_id FK
        UUID requirement_diff_id FK
        String severity
        String overridden_severity
        String status
        Timestamp created_at
        Timestamp updated_at
    }
    llm_call_logs {
        UUID id PK
        String pipeline_stage
        String model_used
        Integer prompt_tokens
        Integer completion_tokens
        Integer latency_ms
        Float cost_usd
        Timestamp created_at
        Timestamp updated_at
    }
    notifications {
        UUID id PK
        UUID org_id FK
        String type
        JSONB payload
        Timestamp delivered_at
        Timestamp created_at
        Timestamp updated_at
    }
    organizations {
        UUID id PK
        String name
        String plan
        Timestamp created_at
        Timestamp updated_at
    }
    policies {
        UUID id PK
        UUID org_id FK
        UUID regulation_version_id FK
        Array requirement_ids
        String status
        Timestamp deployed_at
        Timestamp created_at
        Timestamp updated_at
    }
    regulation_versions {
        UUID id PK
        UUID regulation_id FK
        String version_label
        Timestamp published_date
        Timestamp ingested_at
        UUID source_document_id FK
        JSONB diff_summary
        Timestamp created_at
        Timestamp updated_at
    }
    regulations {
        UUID id PK
        String name
        String jurisdiction
        String source_url
        UUID current_version_id FK
        Timestamp created_at
        Timestamp updated_at
    }
    reports {
        UUID id PK
        UUID org_id FK
        UUID regulation_id FK
        String report_type
        String storage_path
        Timestamp generated_at
        Timestamp created_at
        Timestamp updated_at
    }
    requirement_diffs {
        UUID id PK
        UUID regulation_version_id FK
        UUID old_requirement_id FK
        UUID new_requirement_id FK
        String status
        Timestamp created_at
        Timestamp updated_at
    }
    requirement_embeddings {
        UUID requirement_id PK, FK
        Vector embedding
        String model_used
        Timestamp created_at
        Timestamp updated_at
    }
    requirements {
        UUID id PK
        UUID regulation_version_id FK
        UUID section_id FK
        String type
        String title
        String description
        JSONB conditions
        JSONB actions
        String severity
        JSONB evidence_required
        JSONB references
        Float confidence_score
        String validation_status
        UUID reviewed_by_user_id FK
        Timestamp reviewed_at
        String rejection_reason
        Timestamp created_at
        Timestamp updated_at
    }
    source_documents {
        UUID id PK
        UUID regulation_version_id FK
        String file_type
        String storage_path
        String raw_text
        Boolean ocr_used
        Integer page_count
        Timestamp created_at
        Timestamp updated_at
    }
    system_mappings {
        UUID id PK
        UUID org_id FK
        String system_name
        Array mapped_requirement_ids
        Timestamp created_at
        Timestamp updated_at
    }
    users {
        UUID id PK
        UUID org_id FK
        String clerk_user_id
        String role
        String email
        Timestamp created_at
        Timestamp updated_at
    }
    webhooks {
        UUID id PK
        UUID org_id FK
        String url
        Array event_types
        String secret
        Timestamp created_at
        Timestamp updated_at
    }

    document_sections ||--o{ requirements : "references"
    organizations ||--o{ api_keys : "references"
    organizations ||--o{ audit_log : "references"
    organizations ||--o{ compliance_checks : "references"
    organizations ||--o{ impact_records : "references"
    organizations ||--o{ notifications : "references"
    organizations ||--o{ policies : "references"
    organizations ||--o{ reports : "references"
    organizations ||--o{ system_mappings : "references"
    organizations ||--o{ users : "references"
    organizations ||--o{ webhooks : "references"
    policies ||--o{ compliance_checks : "references"
    regulation_versions ||--o{ policies : "references"
    regulation_versions ||--o{ regulations : "references"
    regulation_versions ||--o{ requirement_diffs : "references"
    regulation_versions ||--o{ requirements : "references"
    regulation_versions ||--o{ source_documents : "references"
    regulations ||--o{ regulation_versions : "references"
    regulations ||--o{ reports : "references"
    requirement_diffs ||--o{ impact_records : "references"
    requirements ||--o{ requirement_diffs : "references"
    requirements ||--o{ requirement_embeddings : "references"
    source_documents ||--o{ document_sections : "references"
    source_documents ||--o{ regulation_versions : "references"
    system_mappings ||--o{ impact_records : "references"
    users ||--o{ audit_log : "references"
    users ||--o{ requirements : "references"
```

### D. Request Sequence: Check-Compliance Evaluation

The developer check-compliance API supports both synchronous evaluation for lightweight system payloads and asynchronous queue offloading for large architectural manifests:

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / CI System
    participant API as POST /api/v1/check-compliance
    participant Auth as API Key Auth & Rate Limiter
    participant DB as PostgreSQL / pgvector
    participant Queue as Celery Queue (Redis)
    participant Worker as Compliance Worker
    participant WH as Webhook Dispatcher

    Dev->>API: Send system configuration payload
    API->>Auth: Validate API Key & check rate limits (org plan)
    Auth-->>API: Key valid, scope 'check-compliance' verified
    API->>DB: Fetch active Policy & enforceable Requirements
    DB-->>API: Return rules & conditions

    alt Payload <= Size Threshold (Sync Execution)
        API->>API: Evaluate rules deterministically against payload
        API->>DB: Record ComplianceCheck (status: COMPLETED)
        API-->>Dev: Return HTTP 200 with pass/fail & violation details
    else Payload > Size Threshold (Async Execution)
        API->>DB: Record BackgroundJob & ComplianceCheck (status: PENDING)
        API->>Queue: Enqueue task_check_compliance(job_id, check_id)
        API-->>Dev: Return HTTP 202 Accepted with job_id & check_id
        Queue->>Worker: Dequeue task_check_compliance
        Worker->>Worker: Evaluate rules against large config payload
        Worker->>DB: Update ComplianceCheck (status: COMPLETED, violations)
        Worker->>WH: Trigger webhook event 'compliance.evaluated'
        WH-->>Dev: Deliver signed JSON payload to registered webhook URL
    end
```

### E. Multi-Tenancy & RBAC Permission Matrix

Our role-based access control is enforced at the route level via strict dependency injection (`require_role`) in `app/core/auth.py`.

<details open>
<summary><b>View Role Permission Matrix</b></summary>
<br />

| User Role | Upload Regs | Review & Approve | System Mappings | API Keys & Users | Check Compliance API | Generate Reports | View Dashboard |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Admin** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **Compliance Officer** | :white_check_mark: | :white_check_mark: | :x: | :x: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **Legal Counsel** | :white_check_mark: | :white_check_mark: | :x: | :x: | :x: | :white_check_mark: | :white_check_mark: |
| **Risk Officer** | :x: | :x: | :white_check_mark: | :x: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **Developer** | :x: | :x: | :white_check_mark: | :white_check_mark: (Keys only) | :white_check_mark: | :x: | :white_check_mark: |
| **Auditor** | :x: | :x: | :x: | :x: | :x: | :white_check_mark: (Read only) | :white_check_mark: |
| **Viewer** | :x: | :x: | :x: | :x: | :x: | :x: | :white_check_mark: |

</details>

---

## Technology Stack

Our production stack is curated for low-latency rule evaluation, deterministic document generation, and enterprise multi-tenancy:

| Layer | Technology | Version | Rationale & Architectural Purpose |
| :--- | :--- | :---: | :--- |
| **Frontend Framework** | Next.js | `14.2.35` | React Server Components (RSC) and App Router for dynamic SSR and static optimization. |
| **Styling & UI** | Tailwind CSS & Shadcn UI | `3.4.1` / `4.15.0` | Restrained Vercel/Linear dark theme aesthetic with accessible primitives. |
| **3D Visualizations** | Three.js & React Three Fiber | `0.185.1` / `9.6.1` | Interactive, restrained compilation meshes for visualizing regulatory structures. |
| **Authentication** | Clerk (`@clerk/nextjs`) | `7.6.1` | Seamless enterprise multi-tenancy, JWT session validation, and organization scoping. |
| **Backend Framework** | FastAPI (Python) | `0.110.0` | High-performance asynchronous REST API with built-in Pydantic validation & OpenAPI docs. |
| **Database & ORM** | PostgreSQL & SQLAlchemy | `16.0` / `2.0.31` | ACID compliance and async ORM (`asyncpg`) with Alembic database migrations. |
| **Vector Database** | `pgvector` | `0.2.5` | Native PostgreSQL extension for embedding similarity searches and obligation deduplication. |
| **Task Queue** | Celery & Redis | `5.4.0` / `5.0.3` | Distributed asynchronous workers for OCR extraction, LLM pipelines, and webhook dispatch. |
| **LLM Integration** | OpenAI / Tiktoken | `1.52.0` / `0.8.0` | Structured JSON extraction of legal conditions, actions, and evidence requirements. |
| **Document Processing** | PyMuPDF & pytesseract | `1.24.4` / `0.3.10` | High-speed PDF text parsing and fallback optical character recognition for scanned docs. |
| **Observability** | Sentry SDK & JSON Logging | `2.66.1` / `4.1.0` | Real-time error tracking and context-aware structured JSON logging (`request_id` propagation). |

---

## Repository Structure

```text
regulation-as-code-compiler/
├── .github/
│   └── workflows/                # CI/CD pipelines (PyTest test runners, code linting)
├── apps/
│   ├── api/                      # FastAPI backend application & Celery workers
│   │   ├── app/
│   │   │   ├── api/routers/      # REST endpoints (regulations, requirements, policies, check-compliance)
│   │   │   ├── core/             # Security hardening, JWT auth, RBAC, structured logging, storage
│   │   │   ├── db/               # Async SQLAlchemy engine, session management, repositories
│   │   │   ├── models/           # Declarative database schemas (16 core tables)
│   │   │   ├── pipelines/        # AI ingestion (extract, chunk, LLM extract, dedup) & PDF reports
│   │   │   ├── schemas/          # Pydantic data validation schemas and serialization models
│   │   │   └── worker/           # Celery asynchronous worker setup and background tasks
│   │   ├── scripts/              # Automation tools (dynamic Mermaid ERD generator)
│   │   └── tests/                # Unit tests, regression suites, and extraction quality tests
│   └── web/                      # Next.js 14 App Router web frontend
│       ├── app/                  # Public landing pages, dashboard, reports, and admin UI
│       ├── components/           # Reusable UI components, interactive requirement browsers, diffs
│       └── lib/                  # Clerk authentication helpers and API client utilities
└── infra/                        # Infrastructure definitions, Docker Compose, database init scripts
```

---

## Getting Started

Follow these exact commands to spin up the complete full-stack compiler locally in Docker:

### 1. Clone & Configure Environment
```bash
git clone https://github.com/rcrag/regulation-as-code-compiler.git
cd regulation-as-code-compiler

# Copy example environment files
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
```

<details>
<summary><b>Required Environment Variables (apps/api/.env)</b></summary>
<br />

```ini
ENVIRONMENT="development"
LOG_LEVEL="INFO"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/regulation_compiler"
REDIS_URL="redis://redis:6379/0"
OPENAI_API_KEY="sk-your-openai-api-key"
CLERK_SECRET_KEY="sk_test_your_clerk_secret"
SENTRY_DSN="" # Optional for local dev
```

</details>

### 2. Launch Services with Docker Compose
```bash
docker compose -f infra/docker-compose.yml up --build -d
```
This starts PostgreSQL 16 (with `pgvector`), Redis, the FastAPI backend on port `8000`, Celery worker processes, and the Next.js web app on port `3000`.

### 3. Run Database Migrations & Verify Health
```bash
# Execute Alembic migrations to construct all 16 database tables and pgvector extension
docker compose -f infra/docker-compose.yml exec api alembic upgrade head

# Verify deep system health (Database, Redis broker, and Worker connectivity)
curl http://localhost:8000/api/health
```
Expected response: `{"status": "healthy", "database": "connected", "redis": "connected", "worker": "responsive"}`

---

## Testing & Quality Assurance

We enforce strict test coverage across our deterministic pipelines and API endpoints:

### Running Backend Unit & Integration Tests
```bash
docker compose -f infra/docker-compose.yml exec api pytest -v
```

### Golden Dataset Extraction Regression Test
To prevent silent LLM prompt regressions or model drift from breaking legal obligation extraction, we maintain a curated regression suite against a golden regulatory dataset:
```bash
docker compose -f infra/docker-compose.yml exec api pytest tests/test_extraction_quality.py -v
```
This test asserts that extraction accuracy, obligation classification, and confidence scoring remain strictly above our `95%` precision threshold across model updates.

---

## API Reference

The FastAPI backend automatically serves OpenAPI documentation:
* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Reference**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Example 1: Upload a Regulation for Compilation
```bash
curl -X POST "http://localhost:8000/api/v1/regulations/upload" \
  -H "Authorization: Bearer <clerk_jwt_token>" \
  -F "file=@./GDPR_Official_Text.pdf" \
  -F "name=General Data Protection Regulation" \
  -F "jurisdiction=European Union"
```

### Example 2: Evaluate System Compliance against Active Policy
```bash
curl -X POST "http://localhost:8000/api/v1/check-compliance" \
  -H "X-API-Key: sk_live_your_scoped_developer_key" \
  -H "Content-Type: application/json" \
  -d '{
    "system_name": "User-Service-Authentication",
    "configuration": {
      "data_retention_days": 30,
      "encryption_at_rest": "AES-256",
      "user_consent_recorded": true,
      "third_party_sharing": false
    }
  }'
```

---

## Deployment Architecture

In production, frontend application bundles are deployed globally on the **Vercel Edge Network**, while asynchronous backend API instances, Celery workers, and managed PostgreSQL databases are isolated within VPC containers on **Railway** / **AWS ECS**.

```mermaid
graph LR
    Git["GitHub Repository (main branch)"] -->|Push / Merge| CI["GitHub Actions CI/CD (.github/workflows/ci.yml)"]
    CI -->|Run PyTest & E2E| Verify{"Tests Pass?"}
    Verify -->|Yes: Deploy Web| Vercel["Vercel Edge Network (apps/web)"]
    Verify -->|Yes: Deploy API/Worker| Railway["Railway / Docker Containers (apps/api & worker)"]
    Verify -->|Yes: Migrate DB| Postgres["Managed PostgreSQL 16 + pgvector"]
    Verify -->|No| Reject["Build Rejected / Notification"]
```

---

## Master Build Roadmap & Status

Our compiler development is structured across 15 rigorous phases. Every completed phase is backed by an extensive verification suite and end-to-end audit:

- [x] **Phase 0**: Base monorepo scaffold, Docker Compose orchestration & environment setup
- [x] **Phase 1**: Declarative database schema, SQLAlchemy models & Alembic migrations
- [x] **Phase 2**: Multi-tenancy authentication & RBAC dependency injection (`@clerk/nextjs` + FastAPI)
- [x] **Phase 3**: Regulatory document upload, storage services & OCR preprocessing (`PyMuPDF` / `tesseract`)
- [x] **Phase 4**: Section segmentation & semantic chunking pipeline
- [x] **Phase 5**: LLM structured extraction, confidence scoring, `pgvector` dedup & embeddings
- [x] **Phase 6**: Interactive requirement browser & human-in-the-loop compliance review workflow
- [x] **Phase 7**: Executive dashboard, severity breakdown charts & real-time analytics
- [x] **Phase 8**: Deterministic reporting engine, server-side PDF generation & signed URLs
- [x] **Phase 9**: Developer API, token-bucket rate limiting, scoped API keys & `/check-compliance`
- [x] **Phase 10**: Regulation versioning, semantic similarity diff engine & amendment change tracking
- [x] **Phase 11**: System mappings CRUD, impact analysis records & notification dispatch groundwork
- [x] **Phase 12**: Asynchronous processing (Celery + Redis workers), dead-letter queues & webhook delivery
- [x] **Phase 13**: High-performance search (combined GIN full-text keyword + pgvector semantic vector search)
- [x] **Phase 14**: Observability (`sentry-sdk`, JSON logging, request tracing), security hardening & CI/CD deployment

---

## License & Contributing

**Proprietary / Y Combinator Winter 2026 Submission**  
This repository and its underlying regulatory compilation algorithms contain proprietary intellectual property. It is currently licensed for internal YC evaluation and review only. Unlicensed copying, distribution, or commercial exploitation is strictly prohibited.

For internal team contributions, please ensure all new pipeline stages include corresponding unit tests in `apps/api/tests/` and run the ERD generator script before opening a pull request.
