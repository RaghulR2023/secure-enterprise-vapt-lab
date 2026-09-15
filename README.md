# TechCorp — Secure Enterprise VAPT Lab

A locally-deployed, Docker-based simulated enterprise e-commerce environment built to demonstrate a **complete Vulnerability Assessment and Penetration Testing (VAPT) lifecycle** — from architecture design and threat modeling, through manual exploitation and evidence collection, to remediation, retesting, and professional reporting.

> **IMPORTANT:** This is an authorized local security laboratory. Do not deploy the vulnerable version publicly.

## Overview

**TechCorp** is a fictional small e-commerce organization running a three-tier application (browser → FastAPI → PostgreSQL) on Docker with separate networks. The repository ships **two builds** of the same application:
- `APP_MODE=secure` — the remediated, hardened build (default)
- `APP_MODE=vulnerable` — an intentionally vulnerable lab build with 8 documented weaknesses

### Problem Being Solved
Most security-training projects bolt generic scanners onto a demo app. This project instead builds a realistic application and its architecture **from scratch**, models the trust boundaries, introduces *specific, understood* vulnerabilities, finds them through a **manual, systematic VAPT**, fixes each root cause, retests every fix, and documents it like a real engagement. The deliverable is an understanding of **why** each vulnerability exists and **how** to remove it — not a scan report.

## What This Demonstrates

- Enterprise application architecture and system design
- Docker networking and network segmentation (3 isolated networks, trust zones)
- Web/API security (OWASP Top 10: A01, A03, A04, A05, A07)
- Threat modeling (STRIDE, assets, data flows, trust boundaries)
- Systematic manual VAPT methodology
- Vulnerability remediation (root cause fixes, not feature removal)
- Retesting (every finding verified remediated)
- Professional security reporting (client-style VAPT + retest reports)
- Scaling and AWS mapping of the architecture

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    DOCKER HOST                       │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Frontend   │  │  Backend   │  │  PostgreSQL   │  │
│  │  (Nginx +   │──│  (FastAPI) │──│  (Database)   │  │
│  │   HTML/JS)  │  │            │  │               │  │
│  └────────────┘  └────────────┘  └──────────────┘  │
│       │               │               │              │
│  frontend-       backend-         database-          │
│  network         network          network            │
└─────────────────────────────────────────────────────┘
```

- [`diagrams/architecture-diagrams.md`](diagrams/architecture-diagrams.md) — Mermaid diagrams (system, trust boundaries, auth flow, BOLA flow, AWS)
- [`docs/architecture/architecture.md`](docs/architecture/architecture.md) — full architecture document

**Network Segmentation (Docker):**
- `frontend-network` — browser-facing zone (frontend + backend for proxy)
- `backend-network` — application zone (backend + frontend)
- `database-network` (`internal: true`) — data zone (backend + postgres **only**)

The frontend cannot reach the database; the database is never published to the host in the secure build.

## Tech Stack

| Component  | Technology     |
|------------|----------------|
| Frontend   | HTML/CSS/JS + Nginx |
| Backend    | Python 3.11 + FastAPI |
| Database   | PostgreSQL 16 |
| Container  | Docker + Docker Compose (3 networks) |

## Quick Start

### Prerequisites
- Docker Engine 20.10+ and Docker Compose v2+

### Running the Lab

```bash
# Secure (remediated) build — default
docker compose up --build

# Vulnerable application build (intentional lab weaknesses)
APP_MODE=vulnerable docker compose up --build

# Vulnerable application + insecure network architecture (VULN-008)
docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml up --build

# Explicit secure overlay (restores trust boundaries)
docker compose -f docker-compose.yml -f docker-compose.secure.yml up --build
```

### Accessing the Application

| Service  | URL                 |
|----------|---------------------|
| Frontend | http://localhost:8080 |
| API      | http://localhost:8000  |
| API Docs | http://localhost:8000/docs *(vulnerable build only)* |

### Default Test Credentials (lab only)

| Role  | Username | Password   |
|-------|----------|------------|
| User  | user1    | password1  |
| User  | user2    | password2  |
| Admin | admin    | admin123   |

## Threat Model

STRIDE-based threat model covering assets, actors, entry points, 5 trust boundaries, data flows, existing controls, and a prioritized risk table.

- [`docs/threat-model/threat-model.md`](docs/threat-model/threat-model.md)

## Security Controls (Secure Build)

- **Authentication** — bcrypt password hashing; JWT with a random signing key and 30-minute expiry
- **Authorization** — object-level ownership checks (BOLA fix) + role-based access control (`require_admin`)
- **Input validation** — Pydantic schemas; server-side price/quantity/status validation
- **SQL safety** — fully parameterized queries (SQLAlchemy ORM + bound parameters)
- **Output handling** — `textContent` rendering + injected Content-Security-Policy (XSS fix)
- **Config hardening** — debug mode off, docs hidden, whitelisted CORS, security-header middleware
- **Network hardening** — internal-only database network; no host DB exposure
- **Security logging** — structured events (login, authz failures, admin actions) — never passwords or tokens

## Vulnerabilities Assessed (8)

| ID     | Vulnerability                      | Severity | CVSS   |
|--------|-----------------------------------|----------|--------|
| VULN-001 | BOLA / Insecure Direct Object Reference — Order Access | High  | 8.1 |
| VULN-002 | Broken Function-Level Authorization — Admin Endpoints | High | 7.5 |
| VULN-003 | Authentication / Token Weakness — Predictable Secret & No Expiration | High | 7.4 |
| VULN-004 | SQL Injection — Product Search | High  | 7.5 |
| VULN-005 | Stored Cross-Site Scripting (XSS) | Medium | 6.1 |
| VULN-006 | Security Misconfiguration — Debug, Wildcard CORS, No Security Headers | Medium | 5.3 |
| VULN-007 | Business Logic — Price Manipulation & Status Bypass | High | 7.1 |
| VULN-008 | Network Architecture — Database Exposed to Host/Public Zone | Medium | 4.3 |

## VAPT Methodology

1. Scope definition → 2. Reconnaissance → 3. Enumeration → 4. Attack-surface mapping → 5. Authentication testing → 6. Authorization testing → 7. Input validation testing → 8. Business-logic testing → 9. Network/service testing → 10. Vulnerability validation → 11. Risk classification → 12. Reporting → 13. Remediation → 14. Retesting

Each finding was discovered and validated **manually** with curl, forged-JWT scripts, SQL payloads, and browser testing against the local lab (attack tools are supporting evidence only).

## Findings & Evidence

- Full report: [`docs/vapt-report/vapt-report.md`](docs/vapt-report/vapt-report.md)
- Raw evidence (sanitized request/response captures): [`evidence/`](evidence/)

Each finding includes: Finding ID, severity, CVSS, affected component/endpoint, description, preconditions, steps to reproduce, evidence, technical & business impact, root cause, CWE/OWASP references, remediation.

## Remediation

Remediation was implemented as code in the same repository — the **secure build** (`APP_MODE=secure`) — fixing each root cause with a proper security control (see table above and per-finding details in the VAPT report). Vulnerability-specific and implementation notes are inline in the backend/frontend source.

## Retesting

Every finding was retested against the secure build using the original attack vectors:

| Finding | Original | Retest | Status |
|---------|----------|--------|--------|
| VULN-001 BOLA | VULNERABLE | `403 Forbidden` on cross-user order read | REMEDIATED |
| VULN-002 Broken Function-Level Auth | VULNERABLE | `403` on user → admin endpoints | REMEDIATED |
| VULN-003 Token Weakness | VULNERABLE | `exp` enforced; forged tokens rejected | REMEDIATED |
| VULN-004 SQL Injection | VULNERABLE | parameterized query returns `[]`; search intact | REMEDIATED |
| VULN-005 XSS | VULNERABLE | payload rendered as inert text | REMEDIATED |
| VULN-006 Misconfiguration | VULNERABLE | `/docs` 404; headers present; generic errors | REMEDIATED |
| VULN-007 Business Logic | VULNERABLE | catalog price enforced; status forced to PENDING | REMEDIATED |
| VULN-008 Network Architecture | VULNERABLE | DB not exposed; segmentation restored | REMEDIATED |

- Retest report: [`docs/retest-report/retest-report.md`](docs/retest-report/retest-report.md)

An automated verification suite mirrors both results (20 secure-mode checks and 13 vulnerable-mode checks, all passing) — see the retest report.

## System-Design Considerations

Scaling analysis covering service separation, asynchronous processing, job queues/workers, database scaling and indexing, caching, rate limiting, auth at scale, secrets management, centralized logging, monitoring, fault tolerance, availability, and network isolation.

## Future AWS Architecture

Local → AWS component mapping (Docker networks → VPC/subnets, containers → ECS Fargate, PostgreSQL → RDS, firewall → Security Groups, secrets → Secrets Manager, logs → CloudWatch) with diagrams.

- [`docs/architecture/system-design.md`](docs/architecture/system-design.md)

## Lessons Learned

- **Segmentation is the first line of defense** — VULN-008 showed that even a well-hardened application is trivial to bypass when a service (the DB) is reachable from the wrong zone.
- **Authorization ≠ authentication** — being logged in must never imply access to every resource; both object-level (BOLA) and function-level (role) checks are required.
- **Sessions/tokens must die** — a token that never expires and is signed with a known secret is not authentication at all.
- **Trust nothing from the client** — prices, statuses, totals, and identifiers are server-authoritative; VULN-007 and VULN-001 are both symptoms of trusting client input.
- **Parameterization is non-negotiable** — the SQLi finding was trivially preventable with bound parameters but catastrophic without them.
- **Error messages leak** — verbose tracebacks turned minor bugs into an information-disclosure channel (VULN-006).
- **Test the fix, not just the feature** — the retest phase proved each control stops the original exploit, which is the only proof remediation matters.
- **Development-time savings from early testing** — a local test cluster caught two real integration bugs (native PG enum vs. ORM string, and an unwired lifespan) that would otherwise have landed in the Docker image.

## Limitations

- Lab-only scope: no TLS, no rate limiting, no brute-force protection, no WAF — all noted as acceptable lab limitations.
- Severity capped at **High** intentionally (no Critical/RCE) to keep the lab safe.
- Frontend is deliberately simple (vanilla JS) — the focus is backend/API security and architecture.
- Real browser-based XSS execution requires a human-in-the-loop; the lab documents the stored payload and the sink in code.
- Docker daemon access is required — see Quick Start.

## Future Improvements

- Suricata-based network monitoring overlay (attack → traffic → detection → log → investigation)
- Automated CI security scan (dependency + SAST) on the secure build
- Sticky-session/final-state business-logic scenario (e.g., quantity caps, coupon abuse)
- Idempotency + request signing, refresh-token rotation
- Full OWASP ASVS sweep mapped to the findings
- Cloud deployment of the *secure* build to AWS free tier (documented in system-design.md)

## Project Structure

```
secure-enterprise-vapt-lab/
├── frontend/            # Nginx + static HTML/JS frontend
├── backend/             # FastAPI backend (secure + vulnerable modes)
│   ├── app/             # Core application (routers, auth, models, logging)
│   ├── secure/          # Parameterized/remediated DB access
│   └── vulnerable/      # Intentional lab SQLi pattern (isolated)
├── docker/              # postgres init.sql (canonical schema)
├── docker-compose.yml   # base compose (secure), 3 networks
├── docker-compose.vulnerable.yml  # lab overlay (VULN-008 network weakness)
├── docker-compose.secure.yml      # hardened overlay
├── docs/
│   ├── architecture/    # architecture.md + system-design.md (incl. AWS)
│   ├── threat-model/    # threat-model.md
│   ├── vapt-report/     # vapt-report.md
│   └── retest-report/   # retest-report.md
├── evidence/            # sanitized evidence per finding (vuln-001..008)
├── diagrams/            # Mermaid diagrams
└── README.md
```

## License

MIT — for educational and authorized lab use only. The vulnerable build must never be deployed publicly.
