# Architecture Diagrams

All diagrams render natively on GitHub (Mermaid). Each diagram below is also
reproduced in the documentation it belongs to.

---

## 1. System Architecture & Network Segmentation

```mermaid
flowchart TB
    subgraph HOST["Docker Host"]
        subgraph FE_NET["frontend-network"]
            FRONTEND["Frontend<br/>nginx:alpine<br/>:80"]
        end
        subgraph BE_NET["backend-network"]
            BACKEND["Backend<br/>python:3.11 + FastAPI<br/>:8000"]
        end
        subgraph DB_NET["database-network (internal)"]
            POSTGRES["PostgreSQL 16<br/>:5432"]
        end
    end

    USER["User / Browser"] -->|"HTTP :8080"| FRONTEND
    FRONTEND -->|"reverse proxy /api"| BACKEND
    BACKEND -->|"SQL over pg network"| POSTGRES

    style FRONTEND fill:#0b7285,color:#fff
    style BACKEND fill:#2b8a3e,color:#fff
    style POSTGRES fill:#a61e4d,color:#fff
```

---

## 2. Trust Boundaries

```mermaid
flowchart LR
    subgraph Z1["TRUST ZONE 1 — Browser"]
        B["Web Browser"]
    end
    subgraph Z2["TRUST ZONE 2 — Frontend"]
        F["Nginx Reverse Proxy"]
    end
    subgraph Z3["TRUST ZONE 3 — Application"]
        A["FastAPI Backend"]
    end
    subgraph Z4["TRUST ZONE 4 — Data"]
        D["PostgreSQL"]
    end

    B --o|"HTTP (no TLS in lab)"| F
    F --o|"proxy_pass /api"| A
    A --o|"SQL (parameterized)"| D

    B -.->|"JWT header"| A
    A -.->|"JWT + role checks"| A

    style Z1 fill:#transparent
```

---

## 3. Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend (Nginx)
    participant A as FastAPI Backend
    participant D as PostgreSQL

    U->>F: POST /api/login {username, password}
    F->>A: forward request
    A->>D: SELECT * FROM users WHERE username = ?
    D-->>A: user record (password_hash)
    A->>A: bcrypt.verify(password, hash)
    alt valid credentials
        A->>A: create JWT (sub, type, exp)
        A-->>U: 200 {access_token}
        Note over U,A: browser stores token, sends as Authorization: Bearer
    else invalid credentials
        A-->>U: 401 Invalid credentials
    end
```

---

## 4. Order Authorization Flow (BOLA / IDOR)

```mermaid
sequenceDiagram
    participant U2 as User B (attacker)
    participant A as FastAPI Backend
    participant D as PostgreSQL

    U2->>A: GET /api/orders/{user_a_order_id} (Bearer: B's token)
    A->>A: authenticate token -> User B
    A->>D: SELECT * FROM orders WHERE id = ?
    D-->>A: user_b_order_id
    Note over A: SECURE build:
    Note over A: check order.user_id == B.id OR role == ADMIN
    alt owner or admin
        A-->>U2: 200 order details
    else not owner
        A-->>U2: 403 Forbidden
    end
```

---

## 5. AWS Target Architecture

```mermaid
flowchart TB
    subgraph AWS["AWS (future target)"]
        subgraph VPC["VPC 10.0.0.0/16"]
            subgraph Pub["Public Subnet"]
                ALB["Application Load Balancer"]
                NATG["NAT Gateway"]
            end
            subgraph Priv["Private Subnet A (app)"]
                ECS1["ECS Fargate — Frontend"]
                ECS2["ECS Fargate — Backend"]
            end
            subgraph Data["Private Subnet B (data — isolated)"]
                RDS["RDS PostgreSQL"]
            end
        end
    end

    USER["Internet"] -->|"HTTPS"| ALB
    ALB --> ECS1
    ECS1 --> ECS2
    ECS2 --> RDS
    ECS2 --> NATG

    style VPC fill:#232946,color:#fff
    style Pub fill:#0b7285,color:#fff
    style Priv fill:#2b8a3e,color:#fff
    style Data fill:#a61e4d,color:#fff
```