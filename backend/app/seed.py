"""Idempotent seeding of the lab test fixtures.

Creates the two standard users and one administrator if they do not
already exist so the VAPT demonstration has predictable test data.
"""

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Product, User
from .security_logging import log_event

SEED_USERS = [
    {
        "username": "user1",
        "email": "user1@techcorp.local",
        "password": "password1",
        "role": "USER",
        "bio": "I work in the accounting department.",
    },
    {
        "username": "user2",
        "email": "user2@techcorp.local",
        "password": "password2",
        "role": "USER",
        "bio": "Customer support team.",
    },
    {
        "username": "admin",
        "email": "admin@techcorp.local",
        "password": "admin123",
        "role": "ADMIN",
        "bio": "Platform administrator.",
    },
]


def seed_data(db: Session) -> None:
    for spec in SEED_USERS:
        if db.query(User).filter(User.username == spec["username"]).first():
            continue
        user = User(
            username=spec["username"],
            email=spec["email"],
            password_hash=hash_password(spec["password"]),
            role=spec["role"],
            bio=spec["bio"],
        )
        db.add(user)
        log_event("seed_user_created", {"username": user.username, "role": user.role})
    db.commit()

    # Seed a couple of products if catalog is empty (init.sql also seeds).
    if db.query(Product).count() == 0:
        db.add_all(
            [
                Product(name="Desk Lamp", description="LED desk lamp", price=19.99, stock=25),
                Product(name="Cable Kit", description="USB-C cable assortment", price=12.50, stock=40),
            ]
        )
        db.commit()