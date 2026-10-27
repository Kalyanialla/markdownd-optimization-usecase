"""
Pricing Policies management and resolution endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from backend.app.core.permissions import get_current_user
from backend.app.db.models.user import User
from backend.app.schemas.dashboard import PolicyItem, PolicyResolveResponse
from backend.app.services.policy_service import PolicyService

router = APIRouter(prefix="/policies", tags=["Pricing Policies"])


@router.get("", response_model=List[PolicyItem])
def list_policies(current_user: User = Depends(get_current_user)):
    """
    List all active and historical pricing policies governing markdowns.
    """
    return PolicyService.list_policies()


@router.get("/resolve", response_model=PolicyResolveResponse)
def resolve_policy(
    category: str = Query("TShirt", description="Product category"),
    sku: Optional[str] = Query(None, description="Optional SKU for SKU-level override check"),
    store: Optional[str] = Query(None, description="Optional Store ID for Store-level override check"),
    date: Optional[str] = Query(None, description="Target evaluation date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user)
):
    """
    Simulates the strict 4-level policy hierarchy (SKU > STORE > CATEGORY > CHAIN)
    and returns the winning policy and constraints.
    """
    return PolicyService.resolve_policy(category=category, sku_id=sku, store_id=store, date_str=date)
