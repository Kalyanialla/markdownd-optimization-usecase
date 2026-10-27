"""
Product catalog exploration endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from backend.app.core.permissions import get_current_user
from backend.app.db.models.user import User
from backend.app.schemas.product import ProductDetail, PriceHistoryItem, PaginatedProductsResponse, ProductStats
from backend.app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Product Catalog"])


@router.get("", response_model=PaginatedProductsResponse)
def list_products(
    q: Optional[str] = Query(None, description="Search query across SKU ID, product name, or style ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    store: Optional[str] = Query(None, description="Filter by store ID"),
    status: Optional[str] = Query(None, description="Filter by product status (ACTIVE, DISCONTINUED, etc.)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("sku_id", description="Field to sort by"),
    sort_dir: str = Query("asc", description="Sort direction: asc or desc"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns filtered, sorted, and paginated product inventory catalog.
    """
    return ProductService.get_products(
        query=q,
        category=category,
        brand=brand,
        store=store,
        product_status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )



@router.get("/stats", response_model=ProductStats)
def get_product_stats(current_user: User = Depends(get_current_user)):
    """
    Returns aggregate KPI stats: total products, markdown opportunities,
    low stock count, and high margin count.
    """
    return ProductService.get_product_stats()


@router.get("/{sku_id}", response_model=ProductDetail)
def get_product(
    sku_id: str,
    store_id: Optional[str] = Query(None, description="Optional store ID to check inventory for"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns full details for a single SKU.
    """
    return ProductService.get_product_by_sku(sku_id, store_id=store_id)


@router.get("/{sku_id}/price-history", response_model=List[PriceHistoryItem])
def get_product_price_history(
    sku_id: str,
    store_id: Optional[str] = Query(None, description="Optional store filter"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns historical price change events and approved audit trail for a SKU.
    """
    return ProductService.get_price_history(sku_id, store_id)
