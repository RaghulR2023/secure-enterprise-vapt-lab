# Threat Model: TechCorp E-Commerce Platform

| Field          | Value                                          |
|----------------|------------------------------------------------|
| **Document ID** | TM-TECHCORP-ECOM-2026-001                     |
| **Author**      | Security Assessment Team                       |
| **Date**        | 2026-09-15                                     |
| **Version**     | 1.0                                            |
| **Status**      | Draft                                          |
| **Classification** | Internal — Confidential                    |

## Scope

This threat model covers the TechCorp e-commerce web application, including all application-layer components, containerized infrastructure, inter-service communication channels, and authentication/authorization mechanisms. The assessment scope includes intentional vulnerabilities introduced for security testing (secure vs. vulnerable mode) as well as production-relevant attack surfaces.

---

## 1. System Overview

TechCorp is a web-based e-commerce platform that allows registered users to browse a product catalog, place orders, and manage their account information. Administrators have elevated capabilities to manage products, view all users and orders, and access aggregate statistics.

**Primary Users:**
- **Normal Users** — register, log in, browse products, place and view orders, manage profile.
- **Administrators** — full CRUD on products, order status management, user and order visibility, dashboard statistics.

**Technology Stack:**

| Component    | Technology                | Network Segment        |
|-------------|---------------------------|------------------------|
| Frontend    | Nginx + HTML/JavaScript   | `frontend-network`     |
| Backend     | FastAPI (Python)          | `backend-network`, `database-network` |
| Database    | PostgreSQL                | `database-network` (internal) |

**Containerization:** Three Docker containers (`frontend`, `backend`, `postgres`) connected through three isolated Docker networks. The `database-network` is configured as internal-only, preventing external access.

---

## 2. Assets

| Asset Category          | Description                                                                 | Sensitivity |
|------------------------|-----------------------------------------------------------------------------|-------------|
| **User Credentials**   | Usernames, email addresses, password hashes (bcrypt), JWT secrets           | Critical    |
| **Personal Information (PII)** | User email, bio, profile data                                        | High        |
| **Order Data**         | Order records, order line items, status history, total amounts              | High        |
| **Product Catalog**    | Product names, descriptions, pricing, stock levels                          | Medium      |
| **Application Integrity** | Business logic correctness, order totals, stock counts, role assignments | High        |
| **Session Data**       | JWT tokens, token expiry, role claims embedded in tokens                    | High        |
| **Administrative Access** | Admin role assignments, admin-only API access                            | Critical    |
| **Database Integrity** | Relational consistency, foreign key constraints, data at rest              | High        |
| **Infrastructure Config** | Docker network definitions, Nginx config, environment variables          | Medium      |

---

## 3. Actors

| Actor                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Unauthenticated User**     | Any visitor to the public-facing frontend; can view products, register, log in. |
| **Authenticated User**       | A registered user with a valid JWT; can place orders, manage profile.       |
| **Administrator**            | A user with the `ADMIN` role; has full control over products, orders, and user data. |
| **External Attacker (Simulated)** | A malicious actor attempting to exploit vulnerabilities for unauthorized access, data exfiltration, or system compromise. |

---

## 4. Entry Points

### 4.1 API Endpoints

| Method | Path                          | Access     | Description                          |
|--------|-------------------------------|------------|--------------------------------------|
| POST   | `/api/register`               | Public     | New user registration                |
| POST   | `/api/login`                  | Public     | Authentication, returns JWT          |
| GET    | `/api/users/me`               | Auth       | Current user profile                 |
| GET    | `/api/users/{id}`             | Auth       | View user by ID                      |
| PUT    | `/api/users/{id}`             | Auth       | Update user by ID                    |
| GET    | `/api/products`               | Public     | List all products                    |
| POST   | `/api/products`               | Admin      | Create a product                     |
| PUT    | `/api/products/{id}`          | Admin      | Update a product                     |
| DELETE | `/api/products/{id}`          | Admin      | Delete a product                     |
| GET    | `/api/products/search?q=`     | Public     | Product search (**SQL-injection-vulnerable path**) |
| POST   | `/api/orders`                 | Auth       | Create an order                      |
| GET    | `/api/orders`                 | Auth       | List current user's orders           |
| GET    | `/api/orders/{id}`            | Auth       | View order by ID                     |
| PUT    | `/api/orders/{id}/status`     | Admin      | Update order status                  |
| GET    | `/api/admin/users`            | Admin      | List all users                       |
| GET    | `/api/admin/orders`           | Admin      | List all orders                      |
| GET    | `/api/admin/stats`            | Admin      | Aggregate statistics                 |

### 4.2 Frontend Entry Point

- The Nginx-served static web application (HTML/JS) on `frontend-network`.
- Renders forms for registration, login, product browsing, and order placement.
- Handles JWT storage and transmission to the backend API.

### 4.3 Direct Database Access

- PostgreSQL listens on the `database-network` interface.
- Accessible only from the `backend` container via the shared `database-network`.
- Default or weak database credentials are a risk if not managed via environment variables.

### 4.4 Docker Network Interfaces

- `frontend-network` — connects frontend and backend containers.
- `backend-network` — connects backend and frontend (allows backend reachability).
- `database-network` — internal-only; connects backend and postgres containers.

---

## 5. Trust Boundaries

Five distinct trust boundaries are identified within the system:

| Boundary | Description | Components |
|----------|-------------|------------|
| **TB-1: User ↔ Frontend** | Browser-based rendering and client-side JavaScript execution. The user controls the DOM and can manipulate any client-side code. | User's browser, Nginx-served static files |
| **TB-2: Frontend ↔ Backend** | HTTP API communication. The frontend sends requests; the backend validates and processes them. This is the primary attack surface. | Frontend Nginx, FastAPI backend |
| **TB-3: Backend ↔ Database** | SQL query execution. The backend constructs queries; the database executes them. SQL injection is possible if parameterization is disabled. | FastAPI backend, PostgreSQL |
| **TB-4: User ↔ Backend (AuthN)** | JWT-based authentication boundary. Tokens authenticate the user; a forged or stolen token grants unauthorized access. | User's browser/client, FastAPI JWT validation |
| **TB-5: User ↔ User (AuthZ)** | Authorization boundary between users. A normal user must not access another user's data or admin functions. Role-based access control enforces this. | User sessions, RBAC logic in backend |

---

## 6. Data Flows

### 6.1 Authentication Flow (Login)

```
┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
│          │  HTTPS  │          │  HTTP   │          │  SQL    │          │
│   User   │◄───────►│ Frontend │◄───────►│ Backend  │◄───────►│ Database │
│ (Browser)│         │ (Nginx)  │         │ (FastAPI)│         │(Postgres)│
└──────────┘         └──────────┘         └──────────┘         └──────────┘
                         │                     │                     │
     1. Enter creds      │  2. POST /api/      │                     │
     ───────────────────►│     login {user,    │                     │
                         │     pass}           │                     │
                         │                     │  3. SELECT user     │
                         │                     │     WHERE username= │
                         │                     │  ──────────────────►│
                         │                     │                     │
                         │                     │  4. User record     │
                         │                     │  ◄──────────────────│
                         │                     │                     │
                         │                     │  5. bcrypt.verify() │
                         │                     │     password        │
                         │                     │                     │
                         │  6. JWT token       │                     │
                         │  ◄──────────────────│                     │
                         │     (HS256 signed)  │                     │
     7. Store JWT,       │                     │                     │
     redirect to app     │                     │                     │
     ◄───────────────────│                     │                     │
```

### 6.2 Order Creation Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
│          │  HTTP   │          │  HTTP   │          │  SQL    │          │
│   User   │◄───────►│ Frontend │◄───────►│ Backend  │◄───────►│ Database │
│ (Browser)│ +JWT    │ (Nginx)  │         │ (FastAPI)│         │(Postgres)│
└──────────┘         └──────────┘         └──────────┘         └──────────┘
                         │                     │                     │
     1. Add items to     │                     │                     │
     cart, place order   │                     │                     │
     ───────────────────►│                     │                     │
                         │  2. POST /api/orders│                     │
                         │     {items[], ...}  │                     │
                         │     + JWT header    │                     │
                         │  ──────────────────►│                     │
                         │                     │                     │
                         │                     │  3. Validate JWT    │
                         │                     │     Extract user_id │
                         │                     │                     │
                         │                     │  4. Verify products │
                         │                     │     exist, check    │
                         │                     │     stock           │
                         │                     │  ──────────────────►│
                         │                     │                     │
                         │                     │  5. Product data    │
                         │                     │  ◄──────────────────│
                         │                     │                     │
                         │                     │  6. BEGIN TXN       │
                         │                     │     INSERT orders   │
                         │                     │     INSERT items    │
                         │                     │     UPDATE stock    │
                         │                     │  ──────────────────►│
                         │                     │                     │
                         │                     │  7. COMMIT / OK     │
                         │                     │  ◄──────────────────│
                         │                     │                     │
                         │  8. 201 Created     │                     │
                         │  ◄──────────────────│                     │
     9. Show confirmation │                     │                     │
     ◄───────────────────│                     │                     │
```

### 6.3 Admin Operations Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
│          │  HTTP   │          │  HTTP   │          │  SQL    │          │
│  Admin   │◄───────►│ Frontend │◄───────►│ Backend  │◄───────►│ Database │
│ (Browser)│ +JWT    │ (Nginx)  │         │ (FastAPI)│         │(Postgres)│
└──────────┘         └──────────┘         └──────────┘         └──────────┘
                         │                     │                     │
     1. Admin action     │                     │                     │
     (e.g. update order  │                     │                     │
     status, view users) │                     │                     │
     ───────────────────►│                     │                     │
                         │  2. PUT /api/orders/│                     │
                         │     {id}/status     │                     │
                         │     OR GET /api/    │                     │
                         │     admin/users     │                     │
                         │     + JWT header    │                     │
                         │  ──────────────────►│                     │
                         │                     │                     │
                         │                     │  3. Validate JWT    │
                         │                     │     Verify ADMIN    │
                         │                     │     role claim      │
                         │                     │                     │
                         │                     │  4. Enforce RBAC:   │
                         │                     │     role == ADMIN?  │
                         │                     │                     │
                         │                     │  5. Execute query   │
                         │                     │  ──────────────────►│
                         │                     │                     │
                         │                     │  6. Result set      │
                         │                     │  ◄──────────────────│
                         │                     │                     │
                         │  7. Response 200    │                     │
                         │  ◄──────────────────│                     │
     8. Display admin    │                     │                     │
     dashboard data      │                     │                     │
     ◄───────────────────│                     │                     │
```

---

## 7. STRIDE Threat Analysis

### 7.1 Trust Boundary TB-1: User ↔ Frontend

| STRIDE Category | Threat | Impact | Likelihood | Notes |
|----------------|--------|--------|------------|-------|
| **Spoofing** | Attacker impersonates a user by injecting a crafted JWT into localStorage/cookies. | High | Medium | Client-side JWT storage is accessible to XSS payloads. |
| **Tampering** | User modifies client-side JavaScript, form values, or request payloads before they reach the backend. | High | High | Any client-side validation can be bypassed. |
| **Repudiation** | User denies placing an order; no client-side audit trail exists. | Medium | Low | Server-side logging mitigates this. |
| **Information Disclosure** | Sensitive data exposed in HTML source, JavaScript bundles, or browser developer tools. | Medium | Medium | JWT tokens stored in client are readable. |
| **Denial of Service** | Flooding the Nginx frontend with requests overwhelms the server. | Medium | Medium | Rate limiting not implemented in lab environment. |
| **Elevation of Privilege** | User manipulates client-side role indicators to access admin UI elements. | High | Low | RBAC enforced server-side; cosmetic only if bypassed. |

### 7.2 Trust Boundary TB-2: Frontend ↔ Backend

| STRIDE Category | Threat | Impact | Likelihood | Notes |
|----------------|--------|--------|------------|-------|
| **Spoofing** | Attacker sends requests with forged JWT tokens to impersonate other users or admins. | Critical | High | Weak JWT secret or algorithm confusion (none/HS256) could allow token forgery. |
| **Tampering** | Man-in-the-middle modifies API requests/responses in transit. No TLS in lab environment. | High | High | HTTP-only communication on Docker networks; no TLS. |
| **Repudiation** | Malicious admin claims they did not modify product prices. | Medium | Low | Requires audit logging of admin actions. |
| **Information Disclosure** | Backend returns excessive data in error responses (stack traces, SQL errors). | High | Medium | Verbose error handling in debug mode leaks internal state. |
| **Denial of Service** | Repeated unauthenticated requests (e.g., `/api/login`, `/api/products`) exhaust backend resources. | High | Medium | No rate limiting on login endpoint allows brute-force. |
| **Elevation of Privilege** | Attacker exploits IDOR in `/api/users/{id}` or `/api/orders/{id}` to access other users' data. | Critical | High | Path parameter `{id}` must be validated against the authenticated user's identity. |

### 7.3 Trust Boundary TB-3: Backend ↔ Database

| STRIDE Category | Threat | Impact | Likelihood | Notes |
|----------------|--------|--------|------------|-------|
| **Spoofing** | Attacker gains direct database access using leaked credentials. | Critical | Low | Database is on internal network; risk increases if credentials are in source code. |
| **Tampering** | SQL injection via `/api/products/search?q=` allows arbitrary SQL execution. | Critical | **Very High** | This is the designated vulnerable endpoint in vulnerable mode. |
| **Repudiation** | Database changes cannot be attributed to a specific application user. | Medium | Medium | Application-level audit logging needed. |
| **Information Disclosure** | SQL injection on search endpoint allows UNION-based data extraction across all tables. | Critical | **Very High** | Password hashes, user PII, and order data are all extractable. |
| **Denial of Service** | Resource-intensive SQL queries (e.g., `pg_sleep()`, Cartesian joins) degrade database performance. | High | High | SQL injection payloads can include time-based DoS. |
| **Elevation of Privilege** | SQL injection allows `UPDATE users SET role='ADMIN'` — privilege escalation to admin. | Critical | High | A single injection point grants full system compromise. |

### 7.4 Trust Boundary TB-4: User ↔ Backend (Authentication)

| STRIDE Category | Threat | Impact | Likelihood | Notes |
|----------------|--------|--------|------------|-------|
| **Spoofing** | Attacker brute-forces login credentials via `/api/login`. | High | High | No rate limiting, no account lockout, no CAPTCHA. |
| **Spoofing** | Attacker uses stolen/replayed JWT tokens from other users. | High | Medium | Tokens have no revocation mechanism; no expiry validation weakness. |
| **Tampering** | Attacker modifies JWT token payload to change `role` from `USER` to `ADMIN`. | Critical | Medium | HS256 with a weak or leaked secret enables token tampering. |
| **Repudiation** | User denies login attempt; no login audit trail. | Medium | Low | Failed login attempts are not logged. |
| **Information Disclosure** | JWT secret leaked via environment variable exposure or source code. | Critical | Low | Depends on deployment hygiene. |
| **Denial of Service** | Account enumeration via `/api/register` (username/email already exists error messages). | Medium | Medium | Differential error messages reveal existing accounts. |
| **Elevation of Privilege** | Algorithm confusion attack: submitting JWT with `alg: "none"` to bypass signature verification. | Critical | Low-Medium | Depends on whether the backend validates the algorithm. |

### 7.5 Trust Boundary TB-5: User ↔ User (Authorization)

| STRIDE Category | Threat | Impact | Likelihood | Notes |
|----------------|--------|--------|------------|-------|
| **Spoofing** | User1 accesses User2's orders by manipulating the order ID in `/api/orders/{id}`. | High | **High** | IDOR vulnerability if ownership is not verified. |
| **Tampering** | User1 modifies User2's profile via `/api/users/{id}` PUT. | High | High | Must verify `id == authenticated_user.id` or `role == ADMIN`. |
| **Repudiation** | User denies viewing another user's profile; no access log. | Medium | Medium | Authorization check logging is needed. |
| **Information Disclosure** | `/api/admin/users` and `/api/admin/orders` accessible to non-admin users. | Critical | High | Must verify admin role before returning data. |
| **Denial of Service** | User places orders with invalid data, exhausting stock or database resources. | Medium | Medium | Input validation and stock limits mitigate this. |
| **Elevation of Privilege** | Normal user accesses admin endpoints (`/api/admin/*`) by sending requests directly to the backend. | Critical | High | RBAC middleware must be applied to all admin routes. |

---

## 8. Existing Security Controls

| Control                          | Status (Secure Mode) | Status (Vulnerable Mode) | Notes |
|----------------------------------|----------------------|--------------------------|-------|
| **JWT Authentication (HS256)**   | Active               | Active                   | Tokens issued on login; validated on protected endpoints. |
| **bcrypt Password Hashing**      | Active               | Active                   | Passwords hashed with bcrypt before storage. |
| **Role-Based Access Control (RBAC)** | Active           | Weakened                 | USER and ADMIN roles enforced; vulnerable mode may have bypasses. |
| **Network Segmentation**         | Active               | Active                   | 3 Docker networks isolate frontend, backend, and database. |
| **SQL Parameterization**         | Active               | **Disabled**             | Secure mode uses parameterized queries; vulnerable mode uses string concatenation. |
| **Input Validation**             | Active               | Reduced                  | Secure mode validates and sanitizes inputs. |
| **Security Headers**             | Active               | Missing                  | Secure mode sets X-Content-Type-Options, X-Frame-Options, etc. |
| **Content Security Policy (CSP)** | Active              | Missing                  | Secure mode frontend includes CSP meta tag/header. |
| **Security Logging**             | Active               | Minimal                  | Secure mode logs auth events, access control failures, and input validation errors. |
| **Rate Limiting**                | Not implemented     | Not implemented          | No rate limiting on login or API endpoints in either mode. |
| **TLS/HTTPS**                    | Not implemented     | Not implemented          | Lab limitation; all communication is over plaintext HTTP. |

---

## 9. Assumptions and Dependencies

### Assumptions

1. **Docker is the deployment boundary.** Container orchestration (Docker Compose) defines the network topology. Attacks requiring Docker-level access (container escape) are out of scope.
2. **TLS is not implemented.** This is a lab limitation. All network traffic between containers and to the host is unencrypted. In production, TLS termination at a reverse proxy or load balancer would be mandatory.
3. **No WAF/CDN in place.** The lab environment does not include a Web Application Firewall or Content Delivery Network. In production, these would provide additional layers of protection (rate limiting, DDoS mitigation, bot detection).
4. **Intentional vulnerabilities exist.** The "vulnerable mode" configuration disables parameterization, security headers, and CSP for educational/testing purposes. The threat model documents both modes.
5. **JWT secret is stored in an environment variable.** If the secret is weak, predictable, or exposed, token forgery becomes trivial.
6. **Database credentials are passed via environment variables.** These are not committed to source code but are visible in `docker-compose.yml` or `.env` files.

### Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| FastAPI framework | Framework vulnerabilities, dependency CVEs | Pin dependency versions; run `pip-audit` or `safety check` |
| PostgreSQL | Database-level vulnerabilities | Keep version current; restrict network access |
| Nginx | Web server vulnerabilities, misconfiguration | Follow Nginx hardening guidelines |
| bcrypt library | Weak hashing if cost factor is too low | Use default cost factor (12+) |
| PyJWT library | Algorithm confusion vulnerabilities | Explicitly specify allowed algorithms |
| Docker | Container escape, image supply chain | Use official base images; scan with Trivy |

---

## 10. Risk Summary

| Rank | Threat | Trust Boundary | STRIDE | Likelihood | Impact | Risk Level |
|------|--------|----------------|--------|------------|--------|------------|
| 1 | SQL Injection via product search endpoint | TB-3 (Backend↔DB) | Tampering, Info Disclosure | **H** | **H** | **Critical** |
| 2 | IDOR on user/order endpoints — access other users' data | TB-5 (User↔User) | Spoofing, Info Disclosure | **H** | **H** | **Critical** |
| 3 | JWT token forgery (weak secret / algorithm confusion) | TB-4 (AuthN) | Spoofing, EoP | **M** | **H** | **Critical** |
| 4 | Admin endpoint access without role verification | TB-5 (User↔User) | EoP, Info Disclosure | **M** | **H** | **High** |
| 5 | Brute-force attack on login endpoint (no rate limiting) | TB-4 (AuthN) | Spoofing, DoS | **H** | **M** | **High** |
| 6 | Man-in-the-middle on plaintext HTTP traffic | TB-2 (Frontend↔Backend) | Tampering, Info Disclosure | **H** | **M** | **High** |
| 7 | XSS via reflected/stored user input | TB-1 (User↔Frontend) | Tampering, Spoofing | **M** | **M** | **Medium** |
| 8 | Verbose error messages leaking internal state | TB-2 (Frontend↔Backend) | Info Disclosure | **M** | **M** | **Medium** |
| 9 | Account enumeration via registration/login errors | TB-4 (AuthN) | Info Disclosure | **M** | **L** | **Medium** |
| 10 | Denial of Service via resource-exhaustion on search/login | TB-2 (Frontend↔Backend) | DoS | **L** | **M** | **Low-Medium** |

---

## 11. Recommendations (Summary)

| Priority | Recommendation |
|----------|---------------|
| **P0** | Enforce SQL parameterization at all times; never use string concatenation for queries. |
| **P0** | Verify resource ownership on all IDOR-prone endpoints (`/api/users/{id}`, `/api/orders/{id}`). |
| **P0** | Validate JWT algorithm explicitly; reject `alg: none`; use a strong, randomly-generated secret. |
| **P1** | Enforce RBAC checks on all admin endpoints with middleware; deny by default. |
| **P1** | Implement rate limiting on `/api/login`, `/api/register`, and high-traffic endpoints. |
| **P1** | Deploy TLS in all environments, including lab (use self-signed certs if needed). |
| **P2** | Sanitize all user input on both client and server; implement CSP to mitigate XSS. |
| **P2** | Use generic error messages; do not reveal whether a username/email exists. |
| **P2** | Add structured audit logging for authentication events, authorization failures, and admin actions. |
| **P3** | Run container image vulnerability scans (Trivy) and dependency audits in CI/CD. |

---

*End of Threat Model Document*
