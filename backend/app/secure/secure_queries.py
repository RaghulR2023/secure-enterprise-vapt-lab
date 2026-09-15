"""Secure database access patterns (remediated implementation)."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def search_products_secure(db: Session, query: str) -> list:
    """Search products using a fully parameterized prepared statement.

    Remediation of VULN-004: user input is passed as a bound parameter,
    so it can never alter the structure of the SQL statement. Full-text
    behavior (ILIKE) is preserved while injection is impossible.
    """
    stmt = text(
        "SELECT id, name, description, price, stock FROM products "
        "WHERE name ILIKE :pattern"
    )
    result = db.execute(stmt, {"pattern": f"%{query}%"})
    return [dict(row._mapping) for row in result]