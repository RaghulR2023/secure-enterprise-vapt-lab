"""Vulnerable database access patterns.

WARNING - LAB ONLY. These functions intentionally demonstrate insecure
patterns and MUST NOT be used outside the authorized local laboratory.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def search_products_vulnerable(db: Session, query: str) -> list:
    """Search products using raw string concatenation.

    VULN-004 (SQL injection): user input is interpolated directly into
    the SQL statement instead of being bound as a parameter. An attacker
    can break out of the string literal and execute arbitrary SQL.
    """
    sql = f"SELECT id, name, description, price, stock FROM products WHERE name ILIKE '%{query}%'"
    result = db.execute(text(sql))
    return [dict(row._mapping) for row in result]