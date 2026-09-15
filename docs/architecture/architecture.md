# TechCorp VAPT Lab — Architecture

> A containerized reference implementation of a small e-commerce application,
> used to demonstrate enterprise application architecture and security
> assessment.

---

## 1. System Overview

TechCorp is a fictional small e-commerce company. Its online storefront and
order system are delivered as a **containerized web/API application** deployed
locally via **Docker Compose**.

The purpose of this lab is twofold:

1. **Demonstrate enterprise application architecture** — clear service
   separation, network segmentation, layered trust boundaries, and
   defensible security controls.
2. **Provide a target for security assessment (VAPT)** — a deployable
   application against which penetration tests, configuration reviews, and
   threat models can be exercised and documented.

The lab ships in two modes:

| Mode | Documented build | Purpose |
|------|------------------|---------|
| `secure`       | `docker compose up --build` | The remediated / secure baseline (default) |
| `vulnerable`   | `APP_MODE=vulnerable docker compose up --build` | Deliberately introduced weaknesses for training |

This document describes the **secure build** and the reference architecture.

---

## 2. Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend  | Nginx + HTML/CSS/JS | User interface, static asset serving, reverse proxy to the API |
| Backend   | Python 3.11 + FastAPI | API, authentication, authorization, business logic, orchestration |
| Database  | PostgreSQL 16 | Persistent data storage (users, products, orders, order items) |

The three components map directly onto the three Docker containers and the
three Docker networks described below.

---

## 3. Docker Containers

| Container | Image | Role |
|-----------|-------|------|
| `techcorp-frontend` | `nginx:alpine` | Serves static HTML/CSS/JS and proxies `/api` requests to the backend |
| `techcorp-backend`  | `python:3.11-slim` + FastAPI | Implements the REST API, auth, and business logic |
| `techcorp-db`       | `postgres:16-alpine` | Relational data store, seeded with the TechCorp catalog and demo users |

Host port mapping:

| Container | Container Port | Host Port |
|-----------|----------------|-----------|
| `techcorp-frontend` | `80` (Nginx) | `8080` |
| `techcorp-backend`  | `8000` (FastAPI/UVicorn) | `8000` |
| `techcorp-db`       | `5432` (PostgreSQL) | **not published** |

> The database is never exposed to the host. It is reachable only from the
> backend container over the internal database network.

---

## 4. Network Architecture

```
USER
  │
  ▼ (frontend-network)
┌──────────┐
│ Frontend │ ←── Nginx:80 → static files + reverse proxy to backend
└──────────┘
  │
  ▼ (backend-network)
┌──────────┐
│ Backend  │ ←── FastAPI:8000 → auth, API, business logic
└──────────┘
  │
  ▼ (database-network, internal: true)
┌──────────┐
│ Postgres │ ←── PostgreSQL:5432 → users, products, orders
└──────────┘
```

### 4.1 Network Zones

| Network | `internal` | Attached Containers | Role |
|---------|-----------|---------------------|------|
| `frontend-network` | no | frontend, backend | Browser-facing zone; only the frontend and backend attach here |
| `backend-network`  | no | backend, frontend | Application zone; only the backend and frontend attach here |
| `database-network` | yes | backend, postgres | Data isolation zone; only the backend and postgres attach here |

**frontend-network** — the browser-facing zone. The frontend publishes port
`8080` here and the backend's published port `8000` also lives in this zone
(lab convenience for direct API testing). This is the zone that receives
untrusted external traffic.

**backend-network** — the application zone. The Nginx reverse proxy in the
frontend forwards `/api` traffic to the FastAPI backend across this network.
The backend serves the API and business logic here.

**database-network (`internal: true`)** — the data isolation zone. The Docker
network is flagged `internal: true`, so it has **no external gateway**: the
Postgres container cannot reach the internet, and no other container is
attached. Only the backend and the postgres instance communicate here, over
port `5432`.

---

## 5. Trust Boundaries

A trust boundary exists wherever data crosses between differently trusted
regions. The lab defines the following boundaries:

| Boundary | Type | Notes |
|----------|------|-------|
| Browser ↔ Nginx | HTTP | No TLS in the lab; plaintext HTTP over the local host |
| Nginx ↔ FastAPI | Internal reverse proxy | Hardcoded proxy target, internal network only |
| FastAPI ↔ PostgreSQL | SQL over internal network | Database credentials passed via container env, internal-only network |
| User ↔ API | JWT authentication | Bearer token in `Authorization` header |
| User ↔ Resource | Authorization | Object-level ownership checks + role-based checks |

Each boundary is an opportunity for attack (MITM, spoofing, injection,
horizontal/vertical privilege escalation) and is therefore enumerated
explicitly in the threat model.

---

## 6. Data Flow Diagrams

### 6.1 Authentication

```
Client → POST /api/login → Backend → query User table → verify password → return JWT
```

### 6.2 Order Creation

```
Client → POST /api/orders → Backend → validate auth → check product stock →
  compute total from catalog → create Order + OrderItems → commit → return order
```

### 6.3 Admin Operations

```
Admin → GET /api/admin/users → Backend → verify JWT → require_admin() →
  query all users → return user list
```

---

## 7. Security Controls (Secure Build)

The secure build applies defense-in-depth across the stack:

| Control | Implementation |
|---------|----------------|
| JWT signing | Random signing key (from environment), 30-minute expiry |
| Password storage | bcrypt hashing (`hash_password` / `verify_password`) |
| Object-level authorization | Ownership checks, e.g. `order.owner == current_user` (or admin) |
| Role-based access control | `require_admin` dependency enforced in the `ADMIN` build |
| SQL injection defence | Parameterized queries via SQLAlchemy ORM |
| Security headers middleware | `X-Frame-Options`, CSP, HSTS-like, and related headers |
| Content-Security-Policy | Also injected via HTML `<meta>` tag |
| CORS | Explicit whitelist — no wildcard |
| Debug mode | Disabled |
| API documentation | Hidden in production builds |
| Security event logging | Non-sensitive events only (no secrets/credentials) |
| Network segmentation | Internal-only database network |

---

## 8. Authentication Flow

```
POST /api/login {username, password}
  → look up user by username
  → bcrypt.verify(password, password_hash)
  → if valid: create_access_token(username) → return JWT
  → if invalid: log event, return 401
```

```
GET /api/users/me (Authorization: Bearer <token>)
  → decode_token(token) → verify exp, type=access
  → look up user by username from token sub claim
  → return user data
```

The token flow is implemented by `create_access_token(subject)` and
`decode_token(token)` in `backend/app/auth.py`, and consumed per-request by the
`get_current_user` dependency.

---

## 9. Authorization Flow

Authentication and authorization are distinct concerns:

- **Authentication** — *is the user who they claim to be?* Proven by JWT
  validation (`decode_token` → verify expiry and token type).

- **Authorization** — *is the user allowed to access this resource?*
  - **Object-level** — resource ownership, e.g. `order.owner == current_user`
    (or the user is an admin).
  - **Function-level** — role gating, e.g.
    `current_user.role == 'ADMIN'` via the `require_admin` dependency.

Authorization is evaluated **after** authentication on every protected route;
neither check can be bypassed independently.