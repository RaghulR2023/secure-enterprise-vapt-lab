from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..models import Order, Product, User
from ..schemas import AdminStats, OrderOut, UserOut
from ..security_logging import log_event

router = APIRouter(prefix="/api/admin", tags=["admin"])

# VULN-002: vulnerable build requires only authentication for admin endpoints;
# secure build enforces role == ADMIN via require_admin.
admin_dependency = get_current_user if settings.is_vulnerable() else require_admin


@router.get("/users", response_model=list[UserOut])
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    log_event(
        "admin_action",
        {"action": "list_users", "actor": current_user.username},
    )
    return db.query(User).order_by(User.id).all()


@router.get("/orders", response_model=list[dict])
def admin_list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    log_event(
        "admin_action",
        {"action": "list_orders", "actor": current_user.username},
    )
    from .orders import _order_out

    orders = db.query(Order).order_by(Order.id).all()
    return [_order_out(o) for o in orders]


@router.get("/stats", response_model=AdminStats)
def admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    users = db.query(func.count(User.id)).scalar() or 0
    products = db.query(func.count(Product.id)).scalar() or 0
    orders = db.query(func.count(Order.id)).scalar() or 0
    revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar() or 0
    log_event("admin_action", {"action": "view_stats", "actor": current_user.username})
    return AdminStats(users=users, products=products, orders=orders, total_revenue=float(revenue))