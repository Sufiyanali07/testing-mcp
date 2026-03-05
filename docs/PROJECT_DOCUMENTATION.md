# FlowGen AI – Full Project Documentation

**Document version:** 1.0  
**Last updated:** February 2025  
**Purpose:** Complete technical and functional specification of the FlowGen AI system. This document can be exported to PDF (e.g. via “Markdown PDF” in VS Code/Cursor, or by printing the rendered Markdown to PDF).

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Backend in Detail](#4-backend-in-detail)
5. [Database Design](#5-database-design)
6. [API Specification](#6-api-specification)
7. [AI Integration (Gemini)](#7-ai-integration-gemini)
8. [Guardrails and Safety](#8-guardrails-and-safety)
9. [Security and Input Validation](#9-security-and-input-validation)
10. [Frontend in Detail](#10-frontend-in-detail)
11. [Observability and Logging](#11-observability-and-logging)
12. [Configuration and Environment](#12-configuration-and-environment)
13. [Deployment and Operations](#13-deployment-and-operations)
14. [Future Improvements](#14-future-improvements)
15. [Appendix](#15-appendix)

---

## 1. Introduction

### 1.1 Purpose of the Document

This document describes the **FlowGen AI** project in full: its goals, architecture, backend and frontend implementation, API contract, AI and guardrail behaviour, security, configuration, and how to run and deploy it. It is intended for developers, maintainers, and stakeholders who need a single reference for the entire system.

### 1.2 What is FlowGen AI?

FlowGen AI is a **full-stack application** that automates the initial processing of customer support tickets using **Google Gemini** for:

- **Classification** (category, urgency)
- **Prioritization** (priority score, confidence score)
- **Draft reply** generation
- **Reasoning summary** for transparency

The system does **not** blindly trust the model. It applies **deterministic guardrails** in Python (e.g. low confidence, high urgency, risky phrases in the draft) and **routes** each ticket to either **Human Review** or **Auto-Resolve**. All inputs, model outputs, and routing decisions are **logged** and visible in an **Admin Dashboard** for observability and audit.

### 1.3 Key Principles

- **Human-in-the-loop:** High-risk or ambiguous cases are always marked for human review.
- **Structured AI output:** Gemini is constrained to JSON; invalid or failed responses trigger retries and a safe fallback.
- **Explicit guardrails:** Safety and routing rules are implemented in code, not only in prompts.
- **Observability:** Every ticket has a log record (raw input, AI output, guardrail flags, routing).
- **Clean architecture:** Clear separation of routers, services, database, and utilities for maintainability and testing.

---

## 2. System Overview

### 2.1 High-Level Flow

1. **User** enters name, email, subject, and message in the frontend and submits.
2. **Frontend** sends `POST /tickets` with JSON body to the backend.
3. **Backend** validates input (Pydantic + security filters), checks for duplicate (message hash), then calls **Gemini** with a structured prompt.
4. **Gemini** returns a single JSON object: category, urgency, priority_score, confidence_score, draft_reply, reasoning_summary.
5. **Backend** runs **guardrails** on the result (e.g. low confidence, high urgency, risky phrases in draft).
6. **Backend** sets **status** and **routing_decision** from guardrail flags, persists the **Ticket** and a **TicketLog** entry, and returns the full **TicketResponse** to the frontend.
7. **Frontend** displays the result (badges, progress bars, draft reply, guardrail flags).
8. **Admins** can open the **Admin Dashboard**, filter tickets by status/urgency, and inspect **ticket logs** (raw input, AI output, flags, routing) for each ticket.

### 2.2 Technology Stack Summary

| Component   | Technologies |
|------------|--------------|
| Backend    | Python 3, FastAPI, Uvicorn, Pydantic, Pydantic-Settings, SQLAlchemy, SQLite, google-generativeai, python-dotenv |
| Frontend   | React 18, Vite, TypeScript, TailwindCSS, shadcn-style UI components |
| AI         | Google Gemini (e.g. gemini-1.5-flash or gemini-2.5-flash) |
| Database   | SQLite by default; schema is portable to PostgreSQL/MySQL |

---

## 3. Architecture

### 3.1 Component Diagram (Logical)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  TicketForm  │  TicketResult  │  AdminDashboard  │  api.ts       │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (JSON)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                             │
│  main.py: CORS, error handlers, startup (DB create tables)       │
│  routers/tickets.py: POST/GET /tickets, GET /tickets/{id}/logs    │
└───┬─────────────────────────────────────────────────────────────┘
    │
    ├── config (Settings from .env)
    ├── database/session.py (engine, get_db)
    ├── database/models.py (Ticket, TicketLog)
    ├── database/crud.py (create_ticket, list_tickets, get_ticket_by_hash, create_ticket_log, list_ticket_logs)
    ├── models/schemas.py (Pydantic request/response models)
    ├── services/gemini_service.py (call_gemini)
    ├── services/guardrail_service.py (apply_guardrails)
    └── utils/security.py, rate_limiter.py, logging_config.py
```

### 3.2 Request Flow for Ticket Submission

1. **Request** hits `POST /tickets` with `TicketCreate` body.
2. **Rate limiter** (dependency) checks per-IP limit; if exceeded, returns 429.
3. **Security validation** (`validate_content_safety`) runs on name, subject, message; if issues, 400.
4. **Message hash** (SHA-256 of normalized message) is computed; **CRUD** looks up existing ticket by hash → duplicate flag and original_ticket_id set if found.
5. **Gemini service** is called with ticket content; returns `(GeminiResult, raw_json, error_message)`. On failure after retry, fallback result and error are used.
6. **Guardrail service** runs on `GeminiResult` → `GuardrailResult` (flags, status, needs_human_review). Routing decision is derived (Human Review vs Auto-Resolve).
7. **Ticket** and **TicketLog** are written via **CRUD**.
8. **TicketResponse** is built from the created ticket and returned.

### 3.3 Directory Structure

```
FlowGen AI/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── database/
│   │   ├── session.py
│   │   ├── models.py
│   │   └── crud.py
│   ├── models/
│   │   └── schemas.py
│   ├── routers/
│   │   └── tickets.py
│   ├── services/
│   │   ├── gemini_service.py
│   │   └── guardrail_service.py
│   └── utils/
│       ├── security.py
│       ├── rate_limiter.py
│       └── logging_config.py
├── frontend/
│   ├── package.json, index.html, vite.config.ts, tailwind.config.js, etc.
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── lib/api.ts
│       └── components/
│           ├── TicketForm.tsx, TicketResult.tsx, AdminDashboard.tsx
│           └── ui/  (button, card, badge, alert, textarea, select, table, progress, tabs, skeleton, toast)
├── docs/
│   └── PROJECT_DOCUMENTATION.md
├── .env, .gitignore, README.md
```

---

## 4. Backend in Detail

### 4.1 main.py

- **FastAPI app** with title and version from config.
- **Startup:** Creates database tables from SQLAlchemy `Base.metadata` (e.g. `tickets`, `ticket_logs`).
- **CORS:** Middleware with `allow_origins` from settings (or default localhost:5173 / 127.0.0.1:5173), credentials, all methods and headers.
- **Routes:** `GET /health` returns `{"status": "ok"}`; ticket routes are mounted via `include_router(tickets.router)` under `/tickets`.
- **Exception handlers:**
  - **HTTPException:** JSON with `code` and `message` (and existing detail if dict).
  - **RequestValidationError:** 422 with `code: "validation_error"` and `details.errors`.
  - **Exception:** 500 with `code: "internal_error"`, generic message; full traceback only in server logs.

### 4.2 config.py

- **Settings** class (Pydantic BaseSettings from pydantic-settings):
  - `app_name`, `environment`
  - `gemini_api_key` (required), `gemini_model` (default e.g. gemini-1.5-flash)
  - `database_url` (default SQLite)
  - `allowed_origins` (list of AnyHttpUrl; validated from env)
  - `rate_limit_requests_per_minute` (default 5)
- **Validator:** `allowed_origins` can be read as comma-separated string from env and split into list.
- **get_settings():** Cached with `lru_cache` so settings are loaded once.

### 4.3 database/session.py

- **Engine** from `database_url`; for SQLite, `check_same_thread=False`.
- **SessionLocal** (sessionmaker), **Base** (declarative_base).
- **get_db():** Generator that yields a session and closes it in a `finally` block (dependency for FastAPI).

### 4.4 database/models.py

- **Ticket:**  
  id, name, email, subject, message, message_hash, is_duplicate, original_ticket_id, category, urgency, priority_score, confidence_score, draft_reply, reasoning_summary, status, guardrail_flags (text, comma-separated), routing_decision, created_at. Relationship to `Ticket` (original_ticket) and `TicketLog` (logs).

- **TicketLog:**  
  id, ticket_id (FK), timestamp, raw_input, ai_output, guardrail_flags, routing_decision. Relationship to `Ticket`.

### 4.5 database/crud.py

- **get_ticket_by_hash(db, message_hash):** Returns latest ticket with that hash, or None.
- **create_ticket(db, ticket):** Adds and commits ticket, refreshes, returns it.
- **create_ticket_log(db, ticket_id, raw_input, ai_output, guardrail_flags, routing_decision):** Creates and returns TicketLog.
- **list_tickets(db, status, urgency, limit=50):** Query tickets with optional filters, ordered by created_at desc, limited.
- **list_ticket_logs(db, ticket_id):** All logs for ticket, ordered by timestamp asc.

### 4.6 models/schemas.py

- **TicketCreate:** name, email, subject, message with length and whitespace validators.
- **GeminiResult:** category, urgency, priority_score, confidence_score, draft_reply, reasoning_summary (all optional).
- **GuardrailResult:** flags (list of str), status, needs_human_review.
- **TicketResponse:** Full ticket view for API response (includes id, timestamps, guardrail_flags as list, etc.); `model_config = ConfigDict(from_attributes=True)`.
- **TicketListItem:** Summary fields for list endpoint.
- **TicketLogEntry:** Single log entry for logs endpoint.
- **TicketListResponse:** `{ items: List[TicketListItem] }`.
- **ErrorResponse:** code, message, details (optional).

### 4.7 routers/tickets.py

- **POST ""** (create_ticket):  
  Depends: get_db, rate_limiter. Request body: TicketCreate. Runs security validation; on failure returns 400. Computes message_hash, checks duplicate. Calls call_gemini, then apply_guardrails. Builds Ticket and TicketLog, returns TicketResponse.

- **GET ""** (list_tickets):  
  Query params: status, urgency. Returns TicketListResponse with items built from CRUD list_tickets.

- **GET "/{ticket_id}/logs"** (get_ticket_logs):  
  Returns list of TicketLogEntry built from CRUD list_ticket_logs (no from_orm; manual construction for Pydantic v2).

### 4.8 services/gemini_service.py

- **Configuration:** Uses settings.gemini_api_key and settings.gemini_model; configures genai and builds GenerativeModel.
- **System prompt:** Instructs model to respond only with a JSON object (no markdown). Schema: category (billing|technical|account|general), urgency (low|medium|high), priority_score (1–100), confidence_score (0–1), draft_reply, reasoning_summary. Style rules: may greet by customer name; sign off as “Sufiyan Ali”.
- **User prompt:** Ticket name, email, subject, message.
- **call_gemini(ticket):** Async; runs sync generate_content in thread pool with timeout 20s. Up to 2 attempts. On success: parse JSON, build GeminiResult, return (result, raw_json, None). On timeout, JSON error, or API error: set last_error, retry once, then return fallback GeminiResult and error message. Fallback draft_reply is a safe “forwarded to human support” message.

### 4.9 services/guardrail_service.py

- **HIGH_RISK_PHRASES:** List of phrases (refund, legal, compliant, policy, terms, etc.).
- **scan_draft_for_risks(draft):** Scans draft text for these phrases and regex (refund, reimburse, compensate, credit); returns sorted list of flag codes (e.g. refund_or_financial_commitment, legal_advice_or_liability, compliance_claim, fabricated_or_risky_policy).
- **apply_guardrails(result):**  
  - Adds low_confidence if confidence_score < 0.65.  
  - Adds high_urgency if urgency == "high".  
  - Extends flags with scan_draft_for_risks(draft_reply).  
  - needs_human_review = (len(flags) > 0).  
  - status = "Needs Human Review" or "Auto-Resolved".  
  Returns GuardrailResult.

### 4.10 utils/security.py

- **contains_script_injection(text):** Regex for `<script` and `on*=`.
- **contains_sql_injection_pattern(text):** Regex for SQL keywords and `--`.
- **is_emoji_only(text):** True if no alphanumeric character.
- **validate_content_safety(*fields):** Concatenates fields; returns list of error messages for script injection, SQL pattern, or emoji-only across all provided fields.
- **hash_message(message):** SHA-256 of stripped, lowercased message (hex).

### 4.11 utils/rate_limiter.py

- In-memory store: client_ip → (count, window_start).
- **rate_limiter(request):** Gets client IP, fixed window 60 seconds, max_requests from settings. Resets window if expired. Increments count; if count > max_requests, raises HTTP 429 with structured detail.

### 4.12 utils/logging_config.py

- **setup_logging():** Creates `logs/` dir if needed. RotatingFileHandler for `logs/flowgen_backend.log` (5 MB, 3 backups), UTF-8. Adds console handler. Root logger INFO. Formatter: time, name, level, message.

---

## 5. Database Design

### 5.1 Table: tickets

| Column             | Type      | Notes |
|--------------------|-----------|--------|
| id                 | Integer   | PK, index |
| name               | String(255) | NOT NULL |
| email              | String(255) | NOT NULL, index |
| subject            | String(255) | NOT NULL |
| message            | Text      | NOT NULL |
| message_hash       | String(128) | NOT NULL, index (for duplicate check) |
| is_duplicate       | Boolean   | NOT NULL, default False |
| original_ticket_id | Integer   | FK tickets.id, nullable |
| category           | String(50) | nullable |
| urgency            | String(50) | nullable |
| priority_score     | Integer   | nullable |
| confidence_score   | Float     | nullable |
| draft_reply        | Text      | nullable |
| reasoning_summary  | Text      | nullable |
| status             | String(50) | NOT NULL, default "Needs Human Review" |
| guardrail_flags    | Text      | nullable, comma-separated codes |
| routing_decision  | String(50) | nullable |
| created_at         | DateTime  | NOT NULL, default utcnow |

### 5.2 Table: ticket_logs

| Column            | Type      | Notes |
|-------------------|-----------|--------|
| id                | Integer   | PK, index |
| ticket_id         | Integer   | FK tickets.id, NOT NULL, index |
| timestamp         | DateTime  | NOT NULL, default utcnow |
| raw_input         | Text      | NOT NULL |
| ai_output         | Text      | nullable (includes raw JSON or error text) |
| guardrail_flags   | Text      | nullable |
| routing_decision  | String(50) | nullable |

---

## 6. API Specification

### 6.1 Base URL and Conventions

- Base: `http://localhost:8000` (or deployed URL).
- Content-Type: `application/json` for request and response where applicable.
- Error body shape: `{ "code": string, "message": string, "details": object? }`.

### 6.2 GET /health

- **Purpose:** Liveness check.
- **Response:** 200, `{ "status": "ok" }`.

### 6.3 POST /tickets

- **Purpose:** Submit a support ticket; backend runs validation, duplicate check, Gemini, guardrails, persistence, and returns full result.
- **Request body:**

```json
{
  "name": "string (1–255)",
  "email": "valid email",
  "subject": "string (1–255)",
  "message": "string (10–5000)"
}
```

- **Success:** 200, TicketResponse (id, name, email, subject, message, category, urgency, priority_score, confidence_score, draft_reply, reasoning_summary, status, guardrail_flags[], routing_decision, is_duplicate, original_ticket_id, created_at).
- **Errors:** 400 (security/validation), 422 (Pydantic), 429 (rate limit).

### 6.4 GET /tickets

- **Query:** `status` (optional), `urgency` (optional).
- **Response:** 200, `{ "items": [ { id, name, email, subject, category, urgency, priority_score, confidence_score, status, created_at }, ... ] }`.

### 6.5 GET /tickets/{ticket_id}/logs

- **Response:** 200, array of `{ id, timestamp, raw_input, ai_output, guardrail_flags, routing_decision }`.

---

## 7. AI Integration (Gemini)

### 7.1 Model and Configuration

- Library: `google-generativeai`. Model ID from settings (e.g. gemini-1.5-flash or gemini-2.5-flash).
- Generation config: temperature 0.3, `response_mime_type="application/json"` to encourage JSON-only output.

### 7.2 Prompt Design

- **System:** Strict instruction to respond only with a single JSON object; no markdown or commentary. Schema and enums (category, urgency) and rules for priority_score, confidence_score, draft_reply, reasoning_summary. Style: optional greeting by name; sign-off as “Sufiyan Ali”.
- **User:** “Now analyze the following support ticket:” plus name, email, subject, message.

### 7.3 Retry and Fallback

- Two attempts; 20-second timeout per attempt. On success: return parsed GeminiResult and raw JSON.
- On failure (timeout, JSON decode, 429/quota, or other API error): after retries, return a fallback GeminiResult with safe draft_reply and reasoning_summary, and store error in ticket log (ai_output includes "ERROR: ...").

---

## 8. Guardrails and Safety

### 8.1 Flag Types

- **low_confidence:** confidence_score < 0.65.
- **high_urgency:** urgency == "high".
- **refund_or_financial_commitment:** Refund/guarantee phrases or regex (refund, reimburse, compensate, credit).
- **legal_advice_or_liability:** Legal/liability phrases.
- **compliance_claim:** PCI/HIPAA/GDPR/compliant phrases.
- **fabricated_or_risky_policy:** Policy/terms phrases.

### 8.2 Routing Rules

- If **any** flag is present → status = "Needs Human Review", routing_decision = "Human Review".
- If **no** flags → status = "Auto-Resolved", routing_decision = "Auto-Resolve".

### 8.3 Why In-Code Guardrails

- Ensures high-risk or ambiguous cases are never auto-sent without human review.
- Same rules for every environment; auditable and testable.

---

## 9. Security and Input Validation

### 9.1 Pydantic Validation

- Required: name, email, subject, message. EmailStr for email. Lengths: name/subject 1–255, message 10–5000. Custom validator: no whitespace-only values.

### 9.2 Security Filters

- Script injection: reject if `<script` or `on*=` present.
- SQL injection: reject if common SQL keywords or `--` present.
- Emoji-only: reject if all provided fields are emoji-only (no alphanumeric).

### 9.3 Duplicate Detection

- Hash = SHA-256(normalized message). Normalized = stripped, lowercased. New ticket with same hash is marked is_duplicate and original_ticket_id set.

### 9.4 Rate Limiting

- Per client IP; fixed 60-second window; max N requests (configurable, default 5). 429 with code "rate_limit_exceeded" when exceeded.

### 9.5 CORS and Secrets

- Origins from ALLOWED_ORIGINS (or default localhost/127.0.0.1:5173). API key and DB URL from .env only.

---

## 10. Frontend in Detail

### 10.1 Stack and Build

- React 18, Vite, TypeScript, TailwindCSS. No backend proxy; frontend calls API via `VITE_API_BASE_URL` (default http://localhost:8000).

### 10.2 App Structure

- **App.tsx:** Header (“FlowGen AI”), Tabs: “Submit Ticket” | “Admin Dashboard”. Submit tab: grid with TicketForm (left) and TicketResult (right). Admin tab: AdminDashboard. ToastProvider wraps app.

### 10.3 lib/api.ts

- **submitTicket(payload):** POST /tickets, returns TicketResponse; throws on non-ok with message from body.
- **getTickets({ status, urgency }):** GET /tickets?…, returns items array.
- **getTicketLogs(ticketId):** GET /tickets/{id}/logs, returns array of log entries.
- Types: TicketPayload, TicketResponse, TicketListItem, TicketLogEntry.

### 10.4 TicketForm

- State: form (name, email, subject, message), errors, submitting. Validation: required fields, email regex, message length 10–5000. On submit: submitTicket, onResult callback, onLoadingChange, toast success/error.

### 10.5 TicketResult

- States: loading (skeleton), no ticket (placeholder text), has ticket (badges for category, urgency, routing; progress bars for priority and confidence; guardrail flags; reasoning summary; draft reply with safety note; duplicate notice if applicable).

### 10.6 AdminDashboard

- State: statusFilter, urgencyFilter, tickets, loading, selectedTicketId, logs, logsLoading, showLogsPanel, logFilter (all|flags|errors), expandedLogIds. loadTickets on mount and when filters change. Click row → loadLogs(ticketId). Table: ID, subject/email, category, urgency, priority, status. Log panel: toggle “Show logs”; filter dropdown; per-log entry with timestamp, badges (Guardrails, Gemini error), routing, “Show details”/“Hide details”; when expanded: raw_input, ai_output, guardrail_flags (badges).

### 10.7 UI Components

- button, card, badge, alert, textarea, select, table, progress, tabs, skeleton, toast (shadcn-style, Tailwind).

---

## 11. Observability and Logging

### 11.1 Database Audit Trail

- Every ticket has one or more ticket_logs: raw_input (concatenated name, email, subject, message), ai_output (raw JSON + optional ERROR line), guardrail_flags, routing_decision, timestamp.

### 11.2 Backend Logs

- Rotating file: logs/flowgen_backend.log (5 MB, 3 backups). Console: same format. Level: INFO. Logs include startup, validation/HTTP errors, Gemini errors, unhandled exceptions.

### 11.3 Admin Dashboard

- Ticket list and per-ticket logs provide full visibility into classification, guardrails, and Gemini failures for debugging and compliance.

---

## 12. Configuration and Environment

### 12.1 Backend (.env in project root)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GEMINI_API_KEY | Yes | — | Gemini API key |
| GEMINI_MODEL | No | gemini-1.5-flash | Model ID |
| DATABASE_URL | No | sqlite:///./flowgen.db | SQLAlchemy URL |
| ALLOWED_ORIGINS | No | (see below) | Comma-separated CORS origins; if empty, http://localhost:5173 and http://127.0.0.1:5173 |
| RATE_LIMIT_REQUESTS_PER_MINUTE | No | 5 | Per-IP limit |
| ENVIRONMENT | No | development | App environment label |

### 12.2 Frontend

- **VITE_API_BASE_URL:** Default http://localhost:8000. Set at build time for production.

---

## 13. Deployment and Operations

### 13.1 Running Locally

- **Backend:** From project root: `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`. Use virtualenv and install from backend/requirements.txt.
- **Frontend:** `cd frontend`, `npm install`, `npm run dev`. Open http://localhost:5173.

### 13.2 Production-Like Run

- Backend: `uvicorn backend.main:app --host 0.0.0.0 --port 8000` (no --reload). Set ALLOWED_ORIGINS to frontend URL. For production DB, set DATABASE_URL and run migrations if any.
- Frontend: `npm run build`; serve dist/ statically. Set VITE_API_BASE_URL to backend URL at build time.

### 13.3 Scalability Notes

- Rate limiter is in-memory; for multiple instances use a shared store (e.g. Redis).
- SQLite is single-writer; for higher concurrency use PostgreSQL/MySQL.
- Gemini is called per request; for high throughput consider a job queue and workers.

---

## 14. Future Improvements

- **Stronger guardrails:** PII/hate/abuse detection; configurable rules in DB.
- **Human-in-the-loop UI:** Edit/approve draft replies and send via email or ticketing integration (e.g. Zendesk, Freshdesk).
- **Background processing:** Queue Gemini calls to workers for better latency isolation and retries.
- **Analytics:** Dashboards for category/urgency distribution, auto-resolve vs human review, guardrail trigger rates.
- **Auth:** Protect admin and sensitive endpoints with JWT/sessions/SSO and RBAC.

---

## 15. Appendix

### 15.1 Error Response Codes (Backend)

- **validation_error:** Input failed security or business validation (400) or Pydantic validation (422).
- **rate_limit_exceeded:** Too many requests (429).
- **http_error:** Generic HTTP exception (4xx/5xx).
- **internal_error:** Unhandled server error (500).

### 15.2 Gemini JSON Schema (Expected)

```json
{
  "category": "billing | technical | account | general",
  "urgency": "low | medium | high",
  "priority_score": 1–100,
  "confidence_score": 0–1,
  "draft_reply": "string",
  "reasoning_summary": "string"
}
```

### 15.3 How to Export This Document to PDF

1. **VS Code / Cursor:** Install “Markdown PDF” extension. Open this file, right-click → “Markdown PDF: Export (pdf)”.
2. **Browser:** View the file on GitHub or another Markdown viewer, then Print → Save as PDF.
3. **Pandoc:** `pandoc docs/PROJECT_DOCUMENTATION.md -o FlowGen_AI_Project_Documentation.pdf`

---

*End of Project Documentation.*
