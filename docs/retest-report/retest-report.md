# TechCorp VAPT Retest Report

| | |
|---|---|
| **Client** | TechCorp |
| **Engagement** | Post-remediation Retest of Web Application VAPT |
| **Test Environment** | Secure Enterprise VAPT Lab (Docker-based, `APP_MODE=secure`) |
| **Date of Retest** | September 15, 2026 |
| **Report Version** | 1.0 |
| **Reference** | TechCorp VAPT Report v1.0, August 2026 |
| **Classification** | **CONFIDENTIAL — Authorized Lab Environment Only** |

---

## 1. Purpose

This report presents the results of the **retest phase** of the TechCorp Vulnerability Assessment and Penetration Testing (VAPT) lifecycle. All eight (8) findings identified in the original assessment (VULN-001 through VULN-008) were retested against the **secure build** after the security remediation work was completed.

The objective of the retest was to independently confirm that each previously identified vulnerability has been remediated and that no regression of the applied security controls has occurred.

---

## 2. Retest Methodology

Each finding was retested by **replaying the identical attack vectors** that were used to confirm the vulnerability during the original assessment, but against the **secure build** (`APP_MODE=secure`).

- **Target:** TechCorp application running the remediated/secure configuration (`docker compose up --build`).
- **Reference build:** The vulnerable build (`APP_MODE=vulnerable`) was used only to confirm exploitability baseline; all remediation verification was performed on the secure build.
- **Verification approach:** Automated API verification suite (20 endpoint/behavior tests) plus manual verification for findings requiring browser/header-level inspection.
- **Attack surface tested:** Authentication, authorization (BOLA / function-level), token handling, input validation (SQL injection / business logic), client-side rendering (XSS), application configuration, and network segmentation.

The retest used the same test accounts as the original assessment:

| Role  | Username  | Password   |
|-------|-----------|------------|
| User  | user1     | password1  |
| User  | user2     | password2  |
| Admin | admin     | admin123   |

---

## 3. Retest Results — Finding by Finding

### VULN-001 — Broken Object Level Authorization (BOLA) / IDOR

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-001 |
| **Title** | Broken Object Level Authorization (Order Access) |
| **Remediation Applied** | Server-side ownership check added to `GET /api/orders/{order_id}`. The handler now verifies `order.user_id == current_user.id` and denies access (403) when a non-admin requests another user's order. |
| **Retest Steps** | 1. Authenticate as `user1` and create an order to obtain an order ID owned by `user1`.<br>2. Authenticate as `user2` to obtain a valid `user2` token.<br>3. Send `GET /api/orders/{user1_order_id}` using `user2`'s token.<br>4. Confirm the response is `403 Forbidden`. |
| **Retest Evidence** | ```bash
# user1 creates an order (order id 1)
curl -s -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":2}]}'

# user2 attempts to read user1's order
curl -s -i http://localhost:8000/api/orders/1 \
  -H "Authorization: Bearer $TOKEN_USER2"
```
Expected: `HTTP 403 Forbidden` — *"You may only view your own orders"*.
Actual: `HTTP/1.1 403 Forbidden` — access denied. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-002 — Broken Function-Level Authorization

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-002 |
| **Title** | Broken Function-Level Authorization (Missing Role Check on Admin Endpoints) |
| **Remediation Applied** | All administrative endpoints (`/api/admin/users`, `/api/admin/orders`, `/api/admin/stats`, and product create/update/delete) now use the `require_admin()` dependency, which enforces `role == 'ADMIN'` and rejects non-admin users with `403 Forbidden`. |
| **Retest Steps** | 1. Authenticate as regular user `user1`.<br>2. Send `GET /api/admin/users` with `user1`'s token.<br>3. Send `GET /api/admin/orders` with `user1`'s token.<br>4. Send `GET /api/admin/stats` with `user1`'s token.<br>5. Send `POST /api/products` with `user1`'s token.<br>6. Confirm all requests return `403 Forbidden`; confirm the same requests with the `admin` token return `200 OK`. |
| **Retest Evidence** | ```bash
curl -s -i http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $TOKEN_USER1"

curl -s -i http://localhost:8000/api/admin/stats \
  -H "Authorization: Bearer $TOKEN_USER1"

curl -s -i http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $TOKEN_ADMIN"
```
Expected: `403 Forbidden` for `user1` on all admin endpoints; `200 OK` for `admin`.
Actual: `HTTP/1.1 403 Forbidden` — *"Administrator role required"* for `user1`; `HTTP/1.1 200 OK` for `admin`. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-003 — Authentication / Token Weakness

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-003 |
| **Title** | Weak JWT: Hard-coded Secret, No Expiry (`exp` Claim), Type Claim Not Validated |
| **Remediation Applied** | `SECRET_KEY` is now auto-generated at boot (or injected via environment) instead of being hard-coded. The `exp` claim is emitted for all tokens with a default 30-minute lifetime, and the `type: access` claim is validated on decode. |
| **Retest Steps** | 1. Authenticate and capture the issued JWT.<br>2. Decode the token payload and confirm the `exp` and `type` claims are present with a ~30-minute lifetime.<br>3. Wait for token expiry (or force it via `TOKEN_EXPIRE_MINUTES`) and confirm access is rejected.<br>4. Forge a token signed with the old known weak secret (`techcorp-fixed-lab-secret-key-please-change`) and confirm it is rejected. |
| **Retest Evidence** | ```bash
# decode the token payload (header + payload are not encrypted)
echo "$TOKEN_USER1" | cut -d. -f2 | base64 -d 2>/dev/null
# -> {"sub":"user1","type":"access","iat":...,"exp":...}   (exp present)

# forged token signed with the old static secret
curl -s -i http://localhost:8000/api/users/me \
  -H "Authorization: Bearer $FORGED_WEAK_SECRET_TOKEN"

# expired token
curl -s -i http://localhost:8000/api/users/me \
  -H "Authorization: Bearer $EXPIRED_TOKEN"
```
Expected: token decode shows `exp` (~30 min from issue); forged and expired tokens return `401 Unauthorized`.
Actual: `exp` claim present and validated; both forged and expired tokens returned `HTTP 401 Unauthorized`. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-004 — SQL Injection

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-004 |
| **Title** | SQL Injection in Product Search |
| **Remediation Applied** | The search endpoint now uses fully parameterized SQL statements (`SQLAlchemy` `text()` with bound parameters / `ILIKE :pattern`). User input can no longer alter the structure of the SQL statement. |
| **Retest Steps** | 1. Send `GET /api/products/search` with payload `' OR 1=1--` and confirm no data is extracted (empty result list).<br>2. Send a normal / legitimate search query (`Keyboard`) and confirm search functionality still works correctly.<br>3. Compare the result count with the vulnerable baseline (which returned all 6 catalog rows under the same injection). |
| **Retest Evidence** | ```bash
# injection probe — must NOT return any rows
curl -s 'http://localhost:8000/api/products/search?q=%27%20OR%201=1--'
# -> [] (0 rows)

# normal search still works
curl -s 'http://localhost:8000/api/products/search?q=Keyboard'
# -> [{"id":2,"name":"Mechanical Keyboard",...}] (1 row)
```
Expected: injection payload returns `[]` (0 rows); normal search returns `1` row (`Mechanical Keyboard`).
Actual: `[]` for the injection probe (vulnerable baseline: 6 rows extracted); `1` row for `Keyboard`. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-005 — Cross-Site Scripting (XSS)

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-005 |
| **Title** | Stored/Reflected Cross-Site Scripting via User-Controlled Content |
| **Remediation Applied** | The frontend now renders user-controlled content (user bios, product descriptions) using `textContent` instead of `innerHTML`, so content can never execute as markup. A strict Content-Security-Policy meta tag is injected in secure mode. |
| **Retest Steps** | 1. Authenticate as `user1` and set the account `bio` to the XSS payload `<img src=x onerror=alert(1)>`.<br>2. Log in as `admin` and load the Admin Dashboard where the bio is displayed.<br>3. Inspect the rendered DOM / HTML source and confirm the payload is displayed as literal text (escaped), not executed. |
| **Retest Evidence** | ```bash
# set a stored XSS payload in the bio
curl -s -X PUT http://localhost:8000/api/users/1 \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -H 'Content-Type: application/json' \
  -d '{"bio":"<img src=x onerror=alert(1)>"}'
```
Expected: bio renders as the literal text string; no script execution; HTML source shows escaped output.
Actual: Admin panel displayed the payload as plain text; no `alert()` fired; source contained escaped markup. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-006 — Security Misconfiguration

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-006 |
| **Title** | Security Misconfiguration (Exposed Docs/OpenAPI, Missing Security Headers, Verbose Errors, Permissive CORS, Debug Mode) |
| **Remediation Applied** | Interactive docs and the OpenAPI schema are disabled in secure mode; CORS origins are whitelisted; a security-headers middleware adds `X-Frame-Options`, `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and `Cache-Control`; debug mode is off and the verbose traceback exception handler is removed (500s return a generic message). |
| **Retest Steps** | 1. Send `GET /docs` and `GET /openapi.json` and confirm both return `404 Not Found`.<br>2. Send a request to `/health` and inspect the response headers for the hardened security headers.<br>3. Trigger an internal error and confirm the response is generic (no stack trace / traceback). |
| **Retest Evidence** | ```bash
curl -s -i http://localhost:8000/docs
# -> HTTP/1.1 404 Not Found

curl -s -i http://localhost:8000/openapi.json
# -> HTTP/1.1 404 Not Found

curl -s -i -D- -o /dev/null http://localhost:8000/health
# -> x-frame-options: DENY
#    x-content-type-options: nosniff
#    content-security-policy: default-src 'self'
#    referrer-policy: strict-origin-when-cross-origin
#    permissions-policy: camera=(), microphone=()
#    cache-control: no-store
```
Expected: `404` on `/docs` and `/openapi.json`; security headers present; generic 500 body without traceback.
Actual: both endpoints returned `404`; all hardening headers observed; 500 responses contained no traceback. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-007 — Business Logic Flaw

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-007 |
| **Title** | Business Logic Flaw: Client-Controlled Price, Status Bypass, and Unvalidated Quantity |
| **Remediation Applied** | Order prices and totals are now computed server-side exclusively from the product catalog (client-supplied `price` is ignored); order `status` is force-set to `PENDING`; quantity is validated (positive, with a sane upper cap); and a server-enforced state machine governs allowed status transitions. |
| **Retest Steps** | 1. Create an order for product 1 (`Wireless Mouse`, catalog price `29.99`) submitting a client `price` of `0.01` and confirm the order total is the catalog price `29.99`.<br>2. Create an order submitting `status=COMPLETED` and confirm the stored/returned status is `PENDING`.<br>3. Submit an order with an invalid quantity (e.g. `0` or negative) and confirm it is rejected.<br>4. As admin, attempt an invalid `PENDING -> COMPLETED` transition and confirm it is rejected by the state machine. |
| **Retest Evidence** | ```bash
# client price is ignored -> catalog price (29.99) is used
curl -s -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":1,"price":0.01}]}'
# -> total_amount 29.99, status "PENDING"

# client status is ignored -> forced to PENDING
curl -s -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":1}],"status":"COMPLETED"}'
# -> status "PENDING"

# invalid quantity rejected
curl -s -i -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":0}]}'
# -> HTTP/1.1 400 Bad Request  (Invalid quantity)

# state machine enforces PENDING -> PAID|CANCELLED only
curl -s -i -X PUT http://localhost:8000/api/orders/1/status \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"status":"COMPLETED"}'
# -> HTTP/1.1 400 Bad Request  (Invalid transition PENDING -> COMPLETED)
```
Expected: order totals always match catalog prices; status always `PENDING`; invalid quantity and illegal transitions rejected.
Actual: total `29.99` (catalog) with price `0.01` submitted; status forced to `PENDING`; invalid quantity and illegal transitions returned `400`. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

### VULN-008 — Network Architecture Weakness

| Field | Content |
|-------|---------|
| **Finding ID** | VULN-008 |
| **Title** | Database Exposure: PostgreSQL Published to Host and Public Zone Breakout |
| **Remediation Applied** | The `database-network` is now declared `internal: true`; PostgreSQL is no longer published to the host on port `5432`; and the frontend (public zone) has been removed from the database network, restoring the intended trust-boundary segmentation. |
| **Retest Steps** | 1. From the Docker host, attempt to connect to PostgreSQL on `localhost:5432` via `psql` and confirm the connection is refused/times out.<br>2. From inside the `frontend` container, attempt to reach the database service and confirm it is unreachable.<br>3. Confirm the backend↔database link still works (data-plane functionality intact). |
| **Retest Evidence** | ```bash
# from the host: database is no longer published
psql "postgresql://techcorp:techcorp@localhost:5432/techcorp" -c 'select 1'
# -> psql: error: connection to server at "localhost" (127.0.0.1),
#    port 5432 failed: Connection refused

# from the frontend (public zone): database network is unreachable
docker exec techcorp-frontend sh -c 'nc -zv techcorp-db 5432'
# -> unreachable (timeout / connection refused)

# backend still reaches the database normally (no regression)
curl -s http://localhost:8000/api/products
# -> 200 OK with catalog JSON
```
Expected: `connection refused`/timeout on host port `5432`; DB unreachable from the frontend; backend↔DB still functional.
Actual: host connection to `5432` refused; frontend cannot reach the database; application API returned catalog data normally. |
| **Original Result** | VULNERABLE |
| **Retest Result** | PASS |
| **Status** | REMEDIATED |

---

## 4. Summary of Results

| Finding | Title | Severity | Original | Retest | Status |
|---------|-------|----------|----------|--------|--------|
| VULN-001 | BOLA / IDOR (Order Access) | High | VULNERABLE | PASS | REMEDIATED |
| VULN-002 | Broken Function-Level Auth | High | VULNERABLE | PASS | REMEDIATED |
| VULN-003 | Authentication / Token Weakness | High | VULNERABLE | PASS | REMEDIATED |
| VULN-004 | SQL Injection | High | VULNERABLE | PASS | REMEDIATED |
| VULN-005 | Cross-Site Scripting (XSS) | Medium | VULNERABLE | PASS | REMEDIATED |
| VULN-006 | Security Misconfiguration | Medium | VULNERABLE | PASS | REMEDIATED |
| VULN-007 | Business Logic Flaw | High | VULNERABLE | PASS | REMEDIATED |
| VULN-008 | Network Architecture Weakness | Medium | VULNERABLE | PASS | REMEDIATED |

**Automated verification totals:**

| Build | Tests | Result |
|-------|-------|--------|
| Secure (`APP_MODE=secure`) | 20 | ALL PASS |
| Vulnerable (baseline confirmation) | 13 | ALL PASS (vulnerabilities confirmed exploitable) |

---

## 5. Residual Risk Notes

The following items were **out of scope** for this retest and remain as accepted residual risk in the lab environment. They are noted for future hardening but are **not** part of the 8 remediated findings:

- **No rate limiting / brute-force protection** on the login endpoint — the lab relies on a single-host, controlled scope.
- **No TLS** — the application is served over plain HTTP on localhost.
- **No account lockout or MFA** — out of scope for the simulated small-enterprise threat model.
- Passwords use bcrypt hashing; however, the seeded lab credentials (`password1`, `password2`, `admin123`) are intentionally weak for lab usability and must never be reused outside the lab.

These items are **acceptable for the lab scope** and do not affect the remediation status of VULN-001 through VULN-008.

---

## 6. Conclusion

All **8 (eight)** findings from the original TechCorp VAPT report — VULN-001 through VULN-008 — were successfully retested against the secure build and confirmed **REMEDIATED**.

Each finding was replayed using the identical attack vector from the original assessment. In every case the previously exploitable condition no longer holds, verified through **20 passing automated security tests** on the secure build and manual confirmation of header-level, error-handling, and network-segmentation controls. The vulnerable build was used only to confirm the baseline exploitability of the exact same tests (13/13 confirmed), providing a direct before/after comparison.

The secure build demonstrates effective security controls across authentication, authorization, input validation, client-side rendering, configuration hardening, and network segmentation. **No vulnerabilities remain open from the original assessment.**

---

*Prepared by: TechCorp Security Testing Team — Secure Enterprise VAPT Lab*

*This report documents testing performed against an authorized, locally-deployed laboratory environment. Findings and evidence apply to the lab scope only.*