from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..models import Order, OrderItem, Product, User
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate
from ..security_logging import log_event

router = APIRouter(prefix="/api/orders", tags=["orders"])

admin_dependency = get_current_user if settings.is_vulnerable() else require_admin

VALID_STATUSES = {"PENDING", "PAID", "SHIPPED", "COMPLETED", "CANCELLED"}
# Allowed lifecycle transitions, managed by administrators.
ALLOWED_TRANSITIONS = {
    "PENDING": {"PAID", "CANCELLED"},
    "PAID": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def _order_out(order: Order) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": float(item.price),
            }
            for item in order.items
        ],
    }


def _create_order_secure(payload: OrderCreate, user: User, db: Session) -> Order:
    """Remediated order creation.

    - unit prices come ONLY from the product catalog (client `price` ignored)
    - totals are computed server-side (client `status` and total ignored)
    - quantity is validated (positive, sane cap)
    - stock is checked before accepting the order
    """
    total = Decimal("0.00")
    order_items = []
    for line in payload.items:
        if line.quantity <= 0 or line.quantity > 100000:
            raise HTTPException(status_code=400, detail="Invalid quantity")
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {line.product_id} not found")
        if product.stock < line.quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")

        unit_price = Decimal(str(product.price))
        total += unit_price * line.quantity
        order_items.append(OrderItem(product_id=product.id, quantity=line.quantity, price=unit_price))

    order = Order(user_id=user.id, status="PENDING", total_amount=total, items=order_items)
    db.add(order)
    db.commit()
    db.refresh(order)
    log_event("order_created", {"order_id": order.id, "user_id": user.id})
    return order


def _create_order_vulnerable(payload: OrderCreate, user: User, db: Session) -> Order:
    """FIXME (VULN-007): business-logic weakness - trusts client input.

    - accepts a client-supplied unit `price` per line item
    - accepts a client-supplied order `status` (workflow bypass)
    - derives the order total from those untrusted values
    """
    total = Decimal("0.00")
    order_items = []
    for line in payload.items:
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {line.product_id} not found")
        unit_price = Decimal(str(line.price)) if line.price is not None else Decimal(str(product.price))
        total += unit_price * line.quantity
        order_items.append(OrderItem(product_id=product.id, quantity=line.quantity, price=unit_price))

    status_value = (payload.status or "PENDING").upper()
    if status_value not in VALID_STATUSES:
        status_value = "PENDING"
    order = Order(user_id=user.id, status=status_value, total_amount=total, items=order_items)
    db.add(order)
    db.commit()
    db.refresh(order)
    log_event("order_created", {"order_id": order.id, "user_id": user.id})
    return order


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if settings.is_vulnerable():
        order = _create_order_vulnerable(payload, current_user, db)
    else:
        order = _create_order_secure(payload, current_user, db)
    return _order_out(order)


@router.get("", response_model=list[dict])
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = db.query(Order).filter(Order.user_id == current_user.id).all()
    return [_order_out(o) for o in orders]


@router.get("/{order_id}", response_model=dict)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # FIXME (VULN-001): BOLA / IDOR. The vulnerable build returns any order
    # to any authenticated user. The secure build enforces ownership.
    if not settings.is_vulnerable():
        if order.user_id != current_user.id and current_user.role != "ADMIN":
            log_event(
                "authorization_failure",
                {"username": current_user.username, "target_order_id": order.id},
                level="warning",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only view your own orders",
            )
    return _order_out(order)


@router.put("/{order_id}/status", response_model=dict)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status.upper()
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not settings.is_vulnerable():
        allowed = ALLOWED_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition {order.status} -> {new_status}",
            )

    order.status = new_status
    db.commit()
    db.refresh(order)
    log_event(
        "admin_action",
        {"action": "update_order_status", "order_id": order.id, "to": new_status, "actor": current_user.username},
    )
    return _order_out(order)