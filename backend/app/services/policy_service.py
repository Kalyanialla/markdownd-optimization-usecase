"""
Service wrapping Pricing Policies resolution and catalog listing.
"""

import ast
import os
import pandas as pd
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from ml.optimizer.pricing_rules import PricingPolicyEngine, POLICIES_PATH
from backend.app.schemas.dashboard import PolicyItem, PolicyResolveResponse


class PolicyService:
    _engine: Optional[PricingPolicyEngine] = None

    @classmethod
    def get_engine(cls) -> PricingPolicyEngine:
        if cls._engine is None:
            cls._engine = PricingPolicyEngine()
        return cls._engine

    @classmethod
    def list_policies(cls) -> List[PolicyItem]:
        if not os.path.exists(POLICIES_PATH):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policies CSV not found")

        df = pd.read_csv(POLICIES_PATH)
        items = []
        for _, row in df.iterrows():
            steps = []
            raw_steps = row.get("allowed_markdown_steps")
            if pd.notna(raw_steps):
                try:
                    steps = [float(s) for s in ast.literal_eval(str(raw_steps))]
                except Exception:
                    steps = []

            items.append(
                PolicyItem(
                    policy_id=str(row.get("policy_id")),
                    category=f"{row.get('scope_type')}: {row.get('scope_id')}",
                    min_markdown_pct=0.0,
                    max_markdown_pct=float(row.get("maximum_discount_pct", 0.0)),
                    allowed_steps=steps,
                    min_gross_margin_pct=float(row.get("minimum_margin_pct", 0.0)),
                    max_markdown_frequency_days=int(row.get("minimum_days_between_changes", 14)),
                    cadence=f"{row.get('minimum_days_between_changes', 14)} days min interval",
                    effective_start=str(row.get("effective_from")),
                    effective_end=str(row.get("effective_to")),
                    is_active=str(row.get("policy_status", "")).upper() == "ACTIVE",
                )
            )
        return items

    @classmethod
    def resolve_policy(
        cls,
        category: str,
        sku_id: Optional[str] = None,
        store_id: Optional[str] = None,
        date_str: Optional[str] = None
    ) -> PolicyResolveResponse:
        engine = cls.get_engine()
        # Default target evaluation date matches the latest dataset period (2025-06-30)
        target_date = date_str or "2025-06-30"
        target_sku = sku_id or "SKU-0001"
        target_store = store_id or "STORE-01"

        try:
            matched = engine.resolve_policy(
                sku_id=target_sku,
                store_id=target_store,
                category=category,
                date_str=target_date
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error resolving policy hierarchy: {str(e)}"
            )

        if not matched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No matching active policy found for scope: {category} on {target_date}"
            )

        scope_type = matched.get("scope_type", "UNKNOWN")
        scope_id = matched.get("scope_id", "UNKNOWN")
        rule_source = f"{scope_type} level override ({scope_id})"

        # Query real verified price change history
        from ml.optimizer.pricing_rules import PriceHistoryService
        phs = PriceHistoryService()
        last_dt = phs.get_last_price_change_date(target_sku, target_store, target_date)
        days_since = phs.get_days_since_last_change(target_sku, target_store, target_date)
        min_days = int(matched.get("minimum_days_between_changes", 14))
        cadence_eligible = (days_since is not None and days_since >= min_days)

        return PolicyResolveResponse(
            category=category,
            target_date=target_date,
            matched_policy_id=matched.get("policy_id"),
            min_markdown_pct=0.0,
            max_markdown_pct=float(matched.get("maximum_discount_pct", 60.0)),
            allowed_steps=[float(s) for s in matched.get("allowed_steps_list", [])],
            min_gross_margin_pct=float(matched.get("minimum_margin_pct", 10.0)),
            cadence=f"{min_days} days minimum between price changes",
            rule_source=rule_source,
            last_price_change_date=last_dt.strftime("%Y-%m-%d") if last_dt is not None else None,
            days_since_last_change=days_since,
            minimum_days_required=min_days,
            cadence_eligible=cadence_eligible,
        )
