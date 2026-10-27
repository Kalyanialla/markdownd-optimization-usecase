"""
Pydantic schemas for product catalog and inventory exploration.
"""

from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field


class ProductListItem(BaseModel):
    sku_id: str
    product_name: str
    style_id: str
    category: str
    subcategory: str
    brand: str
    size: str
    color: str
    season_id: str
    regular_price: float
    unit_cost: float
    minimum_price: float
    maximum_discount_pct: float
    product_status: str
    current_stock: int = 0
    margin_pct: float = 0.0
    store_id: Optional[str] = "STORE-01"
    launch_date: Optional[str] = None


class ProductDetail(ProductListItem):
    season_end_date: Optional[str] = None



class PriceHistoryItem(BaseModel):
    price_event_id: str
    sku_id: str
    store_id: str
    effective_from: str
    effective_to: Optional[str] = None
    previous_price: float
    new_price: float
    price_change_type: str
    change_reason: str
    approval_status: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class PaginatedProductsResponse(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    categories: List[str]
    brands: List[str]
    stores: List[str] = []


class ProductStats(BaseModel):
    total_products: int
    markdown_opportunities: int
    low_stock_products: int
    high_margin_products: int

