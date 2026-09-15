from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..models import Product, User
from ..schemas import ProductCreate, ProductOut, ProductUpdate
from ..security_logging import log_event
from ..secure.secure_queries import search_products_secure
from ..vulnerable.vuln_queries import search_products_vulnerable

router = APIRouter(prefix="/api/products", tags=["products"])

# VULN-002: in the vulnerable build, administrative product operations only
# require authentication; the secure build requires the ADMIN role.
admin_dependency = get_current_user if settings.is_vulnerable() else require_admin


def _product_response(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": float(product.price),
        "stock": product.stock,
        "created_at": product.created_at,
    }


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id).all()
    return products


@router.get("/search")
def search_products(q: str, db: Session = Depends(get_db)):
    """Product search.

    VULN-004 (SQL injection): the vulnerable build concatenates `q` into a
    raw SQL statement; the secure build uses a parameterized query.
    """
    if settings.is_vulnerable():
        results = search_products_vulnerable(db, q)
    else:
        results = search_products_secure(db, q)
    return results


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    product = Product(
        name=payload.name,
        description=payload.description,
        price=payload.price,
        stock=payload.stock,
        created_by=current_user.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    log_event(
        "admin_action",
        {"action": "create_product", "product_id": product.id, "actor": current_user.username},
    )
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(product, field, value)

    db.commit()
    db.refresh(product)
    log_event(
        "admin_action",
        {"action": "update_product", "product_id": product.id, "actor": current_user.username},
    )
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_dependency),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    log_event(
        "admin_action",
        {"action": "delete_product", "product_id": product_id, "actor": current_user.username},
    )