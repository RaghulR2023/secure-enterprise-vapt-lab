-- =====================================================================
-- TechCorp E-Commerce Database Schema
-- Author: TechCorp Engineering / VAPT Lab
-- Description: Canonical relational data model for the TechCorp
--              e-commerce application. This file is executed by
--              the PostgreSQL Docker container on first initialization.
--
-- Entities: users, products, orders, order_items
-- Roles:    USER, ADMIN
-- =====================================================================

-- ---------------------------------------------------------------------
-- Table: users
-- A registered account. Passwords are stored ONLY as strong hashes.
-- role is constrained to the two allowed values (USER | ADMIN).
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id            SERIAL         PRIMARY KEY,
    username      VARCHAR(50)    NOT NULL UNIQUE,
    email         VARCHAR(255)   NOT NULL UNIQUE,
    password_hash VARCHAR(255)   NOT NULL,
    role          VARCHAR(20)    NOT NULL DEFAULT 'USER',
    is_active     BOOLEAN        NOT NULL DEFAULT TRUE,
    bio           TEXT           NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_users_role CHECK (role IN ('USER','ADMIN'))
);

-- ---------------------------------------------------------------------
-- Table: products
-- The product catalog. Prices are stored as NUMERIC(10,2) for money
-- accuracy. Only administrators may modify catalog entries.
-- ---------------------------------------------------------------------
CREATE TABLE products (
    id          SERIAL         PRIMARY KEY,
    name        VARCHAR(255)   NOT NULL,
    description TEXT           NOT NULL DEFAULT '',
    price       NUMERIC(10,2)  NOT NULL CHECK (price >= 0),
    stock       INTEGER        NOT NULL DEFAULT 0 CHECK (stock >= 0),
    created_by  INTEGER        REFERENCES users(id),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- Table: orders
-- A customer order. The status column models the order lifecycle:
-- PENDING -> PAID -> SHIPPED -> COMPLETED
-- (or -> CANCELLED from PENDING/PAID)
-- total_amount should be calculated server-side from the product
-- catalog, never trusted from client input.
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    id           SERIAL        PRIMARY KEY,
    user_id      INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
                   CHECK (status IN ('PENDING','PAID','SHIPPED','COMPLETED','CANCELLED')),
    total_amount NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- Table: order_items
-- Line items belonging to an order. price_at_time records the unit
-- price from the catalog at the time the order was placed.
-- ---------------------------------------------------------------------
CREATE TABLE order_items (
    id         SERIAL         PRIMARY KEY,
    order_id   INTEGER        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER        NOT NULL REFERENCES products(id),
    quantity   INTEGER        NOT NULL CHECK (quantity > 0),
    price      NUMERIC(10,2)  NOT NULL CHECK (price >= 0),
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- Indexes for frequently queried columns
-- ---------------------------------------------------------------------
CREATE INDEX idx_orders_user_id          ON orders(user_id);
CREATE INDEX idx_orders_status           ON orders(status);
CREATE INDEX idx_order_items_order_id    ON order_items(order_id);
CREATE INDEX idx_order_items_product_id  ON order_items(product_id);
CREATE INDEX idx_products_name           ON products(name);
CREATE INDEX idx_users_role              ON users(role);

-- ---------------------------------------------------------------------
-- Products: initial catalog (non-sensitive seed data)
-- ---------------------------------------------------------------------
INSERT INTO products (name, description, price, stock) VALUES
    ('Wireless Mouse',      'Ergonomic 2.4GHz wireless mouse', 29.99, 100),
    ('Mechanical Keyboard', 'Tactile mechanical keyboard, RGB', 89.99,  50),
    ('USB-C Hub',           '7-in-1 USB-C docking hub',        45.50,  80),
    ('27" 4K Monitor',      'Ultra HD IPS color-accurate monitor', 349.00, 20),
    ('Webcam 1080p',        'Full HD webcam with privacy shutter', 59.99, 60),
    ('Laptop Stand',        'Adjustable aluminium laptop stand', 25.00, 120);

-- NOTE:
-- Application users (user1 / user2 / admin) and their detailed data are
-- seeded by the backend application at startup so that password hashes
-- are always produced by the application's hashing routine. This
-- guarantees the stored hashes match the verification logic.