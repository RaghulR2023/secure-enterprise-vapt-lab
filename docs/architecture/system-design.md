# TechCorp VAPT Lab — System Design Considerations

> A design review of the TechCorp lab architecture, examining how each layer
> would scale from the current single-host lab deployment to a production
> deployment, and mapping the local components onto equivalent AWS services.

---

## 1. Scaling Considerations

| Concern | Current (Lab) | Production |
|---------|---------------|------------|
| Service separation | Monolith (single FastAPI app) | Microservices |
| Async processing | Synchronous request/response | Task queues (Celery/Redis) |
| Database scaling | Single Postgres instance | Read replicas + connection pooling |
| Caching | None | Redis for sessions/products |
| Rate limiting | None | API gateway + per-user limits |
| Secrets management | Environment variables | Vault / Secrets Manager |
| Logging | stdout | Centralized (ELK/SIEM) |
| Monitoring | None | Prometheus + Grafana |

The lab is deliberately a **small, single-host** deployment: one FastAPI
process, one Postgres instance, no message bus, no cache. Every row above is a
known production gap rather than an accident, and the sections below describe
the target state.

---

## 2. Service Separation

- **Current:** a single FastAPI app handles all routes — auth, products,
  orders, users, and admin endpoints are all mounted in `backend/app/main.py`.
- **Production:** the monolith decomposes into dedicated services:
  - `auth-service` — login, token issuance, user identity
  - `product-service` — catalog, stock, pricing
  - `order-service` — order lifecycle and fulfilment
  - `admin-service` — administration and reporting
- **Benefits:** independent scaling, fault isolation, and per-team ownership.
- **Tradeoffs:** inter-service communication overhead, distributed transaction
  complexity, and a larger operational surface (service discovery, tracing,
  retries).

---

## 3. Asynchronous Processing

Synchronous request/response works while load is low; long-running work must
move off the request path:

- **Order confirmation emails** → dispatched to a task queue
- **Inventory reconciliation** → background worker compares stock vs. orders
- **Audit log aggregation** → buffered via an async pipeline
- **Failed job retry** → with exponential backoff and dead-letter handling

A typical production stack: **Celery workers consuming from Redis/RabbitMQ**,
with a flower-style dashboard for worker visibility.

---

## 4. Database Scaling

- **Current:** single PostgreSQL 16 instance with all reads and writes
  (name-resolution, auth, catalog, orders) hitting one node.
- **Production:**
  - **Primary + read replicas** — read-heavy queries (product browsing,
    reporting) fan out to replicas; writes stay on the primary.
  - **Connection pooling (PgBouncer)** — amortizes connection churn across
    many concurrent API instances.
  - **Index strategy** — the schema already ships key indexes on look-up
    columns (e.g. `username`, order ownership FKs); production expands these
    based on query patterns and `EXPLAIN` analysis.

---

## 5. Caching

Introduce **Redis** as the caching tier:

- **Session/token cache** — reduces DB lookups when resolving a token subject
  to a user row.
- **Product catalog caching** — the catalog is far read-heavier than write, an
  ideal cache candidate with cache invalidation on product updates.
- **Rate-limiting counters** — per-user/number counters stored in Redis with
  atomic increments and time-window expiry.

---

## 6. Authentication at Scale

- **Current:** simple JWT with a symmetric shared secret (`HS256`) and a
  30-minute expiry.
- **Production:**
  - **Asymmetric keys (`RS256`)** — sign with a private key, verify with a
    public key; the verification key can be safely distributed to other
    services.
  - **Short-lived access tokens + refresh tokens** — minimizes the blast
    radius of token theft.
  - **OAuth2/OIDC** — enables SSO integration with identity providers.
  - **Token revocation list** — for immediate invalidation of compromised or
    logged-out sessions.

---

## 7. Secrets Management

- **Current:** secrets live in environment files / Compose variables
  (`SECRET_KEY`, database password) — acceptable for a local lab, not for
  production.
- **Production:** **HashiCorp Vault** or **AWS Secrets Manager**.
- **Rule:** no secrets in code, configuration files, or Docker Compose files;
  secrets are fetched at runtime and rotated on a schedule.

---

## 8. Centralized Logging

- **Current:** structured logs written to container stdout.
- **Production:**
  - **Structured JSON logs** → **Filebeat/Logstash** → **Elasticsearch** →
    **Kibana** (the ELK stack).
  - **Security event correlation** — auth failures, privilege escalations, and
    admin actions aggregated across all services.
  - **Alerting** on suspicious patterns (login spikes, repeated 401/403s,
    anomalous admin access).

---

## 9. Fault Tolerance

- **Health checks** — the backend already exposes `/health`; production uses it
  for Liveness/Readiness probes and load-balancer routing.
- **Circuit breakers** — for external service calls, fail fast instead of
  hanging.
- **Graceful degradation** — degraded UX (cached catalog, offline mode) when
  downstream services are unavailable.
- **Data backup and recovery** — automated Postgres backups with tested restore
  procedures and defined RPO/RTO.

---

## 10. Network Isolation

- **Current:** three Docker bridge networks (`frontend-`, `backend-`,
  `database-network` with `internal: true`) segment traffic into browser /
  application / data zones.
- **Production:** a **VPC** with:
  - **Public subnets** — for the load-balanced web tier
  - **Private subnets** — for application and database tiers (no direct
    internet access)
  - **Security groups + NACLs** — network-level firewalling
  - **WAF** — web application firewall protecting against common web attacks
  - **DDoS protection** — at the edge

The Docker-network model in the lab is a faithful miniature of the AWS subnet
model, which makes the mapping in the next section straightforward.

---

## AWS Mapping

| Local Component | AWS Equivalent | Justification |
|-----------------|----------------|---------------|
| Docker network | VPC | Logical network isolation |
| frontend-network | Public subnet | Browser-accessible tier |
| backend-network | Private subnet | Application tier, no direct internet |
| database-network | Private subnet (isolated) | Data tier |
| Frontend container | ECS Fargate task (ALB) | Managed container orchestration |
| Backend container | ECS Fargate task | Auto-scaling API service |
| PostgreSQL container | RDS PostgreSQL | Managed database with backups, HA |
| Docker volume | EBS + RDS storage | Persistent storage |
| Security headers | WAF + CloudFront | Edge security |
| Secrets | AWS Secrets Manager | Managed secret rotation |
| Logs | CloudWatch Logs | Centralized logging |
| Monitoring | CloudWatch + X-Ray | APM and metrics |
| Docker networks | Security Groups | Network-level firewall rules |
| /health endpoint | ALB health check | Load balancer routing |

### AWS Architecture

```
                          Internet
                             │
                             ▼
                        CloudFront
                        (CDN + WAF)
                             │
                      ┌──────┴──────┐
                      ▼             ▼
                    ALB        CloudWatch/X-Ray
              (public subnet)  (logging, metrics)
                      │
                      ▼
        ┌─────────────────────────────┐
        │      Frontend task          │   ECS Fargate
        │      (Nginx static UI)      │   — public subnet
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │      Backend API task       │   ECS Fargate
        │      (FastAPI, auto-scale)  │   — private subnet
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │      RDS PostgreSQL         │   Private, isolated subnet
        │      (multi-AZ + replicas)  │   — PgBouncer in front
        └─────────────────────────────┘

        Supporting services:
          • Secrets Manager   — SECRET_KEY, DB credentials
          • SQS / ElastiCache — task queues, session cache, rate limits
          • CloudWatch Logs   — centralized logging + alerting
          • Security Groups   — per-tier network ACLs
```

The mapping is one-to-one where possible: each lab container/network becomes an
AWS service or subnet tier, preserving the same trust-boundary story in the
cloud.