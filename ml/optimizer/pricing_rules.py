"""
UC-RT-03: Pricing Policies and Feasibility Constraints Checker.

Reads pricing_policies.csv and evaluates candidate prices against:
1. Hierarchy precedence: SKU > STORE > CATEGORY > CHAIN.
2. Active status and effective date window.
3. Policy constraints:
   - Allowed markdown steps
   - Minimum margin percentage
   - Minimum absolute price
   - Maximum discount percentage
   - Minimum days between price changes
4. Historical cadence enforcement via PriceHistoryService.
"""

import os
import ast
import logging
import pandas as pd
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
POLICIES_PATH = os.path.join(REPO_ROOT, "data/raw/pricing_policies.csv")
PRICE_HISTORY_PATH = os.path.join(REPO_ROOT, "data/raw/price_history.csv")


def validate_policy_configuration(policy: Dict[str, Any]) -> None:
    """
    Validates that a pricing policy dictionary contains valid, non-contradictory settings.
    Raises ValueError on malformed or invalid configurations.
    """
    if not isinstance(policy, dict):
        raise ValueError(f"Policy must be a dictionary, got {type(policy)}")
        
    # 1. Allowed steps validation
    allowed_steps = policy.get("allowed_steps_list")
    if allowed_steps is None or not isinstance(allowed_steps, (list, tuple)) or len(allowed_steps) == 0:
        raise ValueError(f"Policy allowed_steps_list must be a non-empty list of steps, got {allowed_steps}")
    for s in allowed_steps:
        if not isinstance(s, (int, float)) or s < 0 or s > 100:
            raise ValueError(f"Invalid discount step {s} in policy; must be a number in [0, 100]")
            
    # 2. Maximum discount validation
    max_disc = policy.get("maximum_discount_pct")
    if max_disc is None or not isinstance(max_disc, (int, float)) or max_disc < 0 or max_disc > 100:
        raise ValueError(f"Invalid maximum_discount_pct {max_disc}; must be a number in [0, 100]")
        
    # 3. Minimum price validation
    min_p = policy.get("minimum_price")
    if min_p is not None and (not isinstance(min_p, (int, float)) or min_p < 0):
        raise ValueError(f"Invalid minimum_price {min_p}; must be non-negative")
        
    # 4. Minimum margin validation
    min_margin = policy.get("minimum_margin_pct")
    if min_margin is not None and not isinstance(min_margin, (int, float)):
        raise ValueError(f"Invalid minimum_margin_pct {min_margin}; must be numeric")
        
    # 5. Cadence validation
    min_days = policy.get("minimum_days_between_changes")
    if min_days is not None and (not isinstance(min_days, (int, float)) or min_days < 0):
        raise ValueError(f"Invalid minimum_days_between_changes {min_days}; must be non-negative integer")


class PriceHistoryService:
    """
    Queries verified, approved historical price-setting events from price_history.csv.
    """
    def __init__(self, history_path: str = PRICE_HISTORY_PATH):
        self.history_path = history_path
        self._df = self._load_verified_history()
        
    def _load_verified_history(self) -> pd.DataFrame:
        if not os.path.exists(self.history_path):
            logger.warning(f"Price history file not found at {self.history_path}")
            return pd.DataFrame(columns=["sku_id", "store_id", "effective_from", "previous_price", "new_price"])
            
        df = pd.read_csv(self.history_path)
        # Filter strictly approved price events
        df = df[df["approval_status"] == "APPROVED"].copy()
        df["effective_from"] = pd.to_datetime(df["effective_from"], errors="coerce")
        
        # Keep genuine price-setting events (INITIAL establishes price; MARKDOWN / ROLLBACK changes price)
        price_changed = (df["previous_price"] != df["new_price"]) | (df["price_change_type"] == "INITIAL")
        df = df[price_changed].copy()
        df = df.dropna(subset=["effective_from", "store_id", "sku_id"])
        
        # Handle duplicates on (store_id, sku_id, effective_from): sort and keep latest approved
        df = df.sort_values(["store_id", "sku_id", "effective_from"])
        df = df.drop_duplicates(subset=["store_id", "sku_id", "effective_from"], keep="last")
        return df

    def get_last_price_change_date(self, sku_id: str, store_id: str, as_of_date: str) -> Optional[pd.Timestamp]:
        """
        Returns the latest valid approved price change date strictly on or before as_of_date.
        Returns None if no history exists for the entity on or before as_of_date.
        """
        if self._df.empty:
            return None
        dt = pd.to_datetime(as_of_date)
        match = self._df[
            (self._df["sku_id"] == sku_id) &
            (self._df["store_id"] == store_id) &
            (self._df["effective_from"] <= dt)
        ]
        if match.empty:
            return None
        return match["effective_from"].max()

    def get_days_since_last_change(self, sku_id: str, store_id: str, as_of_date: str) -> Optional[int]:
        """
        Returns the number of elapsed calendar days between the last price change and as_of_date.
        Returns None if no prior approved price event is found.
        """
        last_dt = self.get_last_price_change_date(sku_id, store_id, as_of_date)
        if last_dt is None:
            return None
        dt = pd.to_datetime(as_of_date)
        return max(0, int((dt - last_dt).days))


class PricingPolicyEngine:
    def __init__(self, policies_path: str = POLICIES_PATH):
        self.policies_path = policies_path
        self.df_policies = self._load_policies()
        
    def _load_policies(self) -> pd.DataFrame:
        df = pd.read_csv(self.policies_path)
        
        # Parse allowed_markdown_steps strictly without permissive silent fallback
        def parse_steps(x):
            if pd.isna(x) or not str(x).strip():
                raise ValueError("allowed_markdown_steps cannot be empty or null")
            try:
                parsed = ast.literal_eval(str(x))
            except Exception as e:
                raise ValueError(f"Malformed allowed_markdown_steps '{x}': {e}")
            if not isinstance(parsed, list) or len(parsed) == 0:
                raise ValueError(f"allowed_markdown_steps must be a non-empty list, got {parsed}")
            for s in parsed:
                if not isinstance(s, (int, float)) or s < 0 or s > 100:
                    raise ValueError(f"Invalid discount step {s} in allowed_markdown_steps; must be 0 <= step <= 100")
            return sorted(list(set(parsed)))
            
        df["allowed_steps_list"] = df["allowed_markdown_steps"].apply(parse_steps)
        return df

    @staticmethod
    def _select_deterministic_policy(matches: pd.DataFrame, scope_type: str, scope_id: str) -> Dict[str, Any]:
        """
        Deterministically selects a policy from matching active rows:
        1. If 1 match, return it.
        2. If multiple matches:
           - Sort by policy_version descending and effective_from descending.
           - Check for ambiguous tie (multiple rows with the same top version and effective date).
             If top rows differ in constraints, raise ValueError (fail closed).
           - Otherwise return the top resolved policy.
        """
        if matches.empty:
            return None
        if len(matches) == 1:
            pol = matches.iloc[0].to_dict()
            validate_policy_configuration(pol)
            return pol
            
        df = matches.copy()
        if "policy_version" in df.columns:
            df["_parsed_version"] = pd.to_numeric(df["policy_version"], errors="coerce").fillna(1.0)
        else:
            df["_parsed_version"] = 1.0
            
        df["_parsed_effective_from"] = pd.to_datetime(df["effective_from"], errors="coerce")
        sorted_df = df.sort_values(by=["_parsed_version", "_parsed_effective_from"], ascending=[False, False])
        top_row = sorted_df.iloc[0]
        
        # Check if there is an equal tie on top version and effective_from
        tied_candidates = sorted_df[
            (sorted_df["_parsed_version"] == top_row["_parsed_version"]) &
            (sorted_df["_parsed_effective_from"] == top_row["_parsed_effective_from"])
        ]
        
        if len(tied_candidates) > 1:
            # Check if constraints differ
            unique_steps = tied_candidates["allowed_steps_list"].apply(tuple).nunique()
            unique_margins = tied_candidates["minimum_margin_pct"].nunique()
            unique_max_disc = tied_candidates["maximum_discount_pct"].nunique()
            if unique_steps > 1 or unique_margins > 1 or unique_max_disc > 1:
                policy_ids = list(tied_candidates["policy_id"])
                raise ValueError(
                    f"Ambiguous policy conflict at {scope_type}={scope_id}: "
                    f"Multiple active policies {policy_ids} have identical version ({top_row['_parsed_version']}) "
                    f"and effective date ({top_row['effective_from']}) but conflicting constraints."
                )
                
        pol_dict = top_row.drop(labels=["_parsed_version", "_parsed_effective_from"]).to_dict()
        validate_policy_configuration(pol_dict)
        return pol_dict

    def resolve_policy(self, sku_id: str, store_id: str, category: str, date_str: str) -> Dict[str, Any]:
        """
        Resolves the applicable policy using hierarchy:
        SKU > STORE > CATEGORY > CHAIN
        Filtered by ACTIVE status and effective date.
        Deterministically selects latest policy version and fails safely on ambiguous ties.
        """
        active_policies = self.df_policies[
            (self.df_policies["policy_status"] == "ACTIVE") &
            (self.df_policies["effective_from"] <= date_str) &
            (self.df_policies["effective_to"] >= date_str)
        ].copy()
        
        # 1. Check SKU level
        sku_matches = active_policies[(active_policies["scope_type"] == "SKU") & (active_policies["scope_id"] == sku_id)]
        if not sku_matches.empty:
            return self._select_deterministic_policy(sku_matches, "SKU", sku_id)
            
        # 2. Check STORE level
        store_matches = active_policies[(active_policies["scope_type"] == "STORE") & (active_policies["scope_id"] == store_id)]
        if not store_matches.empty:
            return self._select_deterministic_policy(store_matches, "STORE", store_id)
            
        # 3. Check CATEGORY level
        cat_matches = active_policies[(active_policies["scope_type"] == "CATEGORY") & (active_policies["scope_id"] == category)]
        if not cat_matches.empty:
            return self._select_deterministic_policy(cat_matches, "CATEGORY", category)
            
        # 4. Check CHAIN level
        chain_matches = active_policies[(active_policies["scope_type"] == "CHAIN") & (active_policies["scope_id"] == "ALL")]
        if not chain_matches.empty:
            return self._select_deterministic_policy(chain_matches, "CHAIN", "ALL")
            
        # Fallback default
        default_pol = {
            "policy_id": "DEFAULT",
            "scope_type": "CHAIN",
            "scope_id": "ALL",
            "minimum_margin_pct": 10.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 50.0,
            "allowed_steps_list": [0, 10, 20, 30, 40, 50],
            "minimum_days_between_changes": 14,
            "requires_approval": 1
        }
        validate_policy_configuration(default_pol)
        return default_pol

    def validate_candidate(
        self,
        candidate_price: float,
        discount_pct: float,
        regular_price: float,
        unit_cost: float,
        policy: Dict[str, Any],
        days_since_last_change: Optional[int] = None,
        has_history: bool = True
    ) -> Dict[str, Any]:
        """
        Validates if a candidate discount satisfies binding business constraints.
        Enforces policy validity, allowed steps, max discount, min price, min margin,
        and cadence. Missing or unverified history blocks markdowns pending review.
        """
        # 0. Policy configuration integrity
        try:
            validate_policy_configuration(policy)
        except ValueError as err:
            return {
                "is_feasible": False,
                "rejection_reason": f"Malformed or invalid policy configuration: {err}"
            }
            
        # 1. Allowed steps
        allowed_steps = policy.get("allowed_steps_list", [])
        if discount_pct not in allowed_steps:
            return {
                "is_feasible": False,
                "rejection_reason": f"Discount {discount_pct}% not in allowed markdown steps {allowed_steps}"
            }
            
        # 2. Maximum discount
        max_disc = float(policy.get("maximum_discount_pct", 50.0))
        if discount_pct > max_disc:
            return {
                "is_feasible": False,
                "rejection_reason": f"Discount {discount_pct}% exceeds policy maximum {max_disc}%"
            }
            
        # 3. Minimum price
        min_p = float(policy.get("minimum_price", 0.0))
        if candidate_price < min_p:
            return {
                "is_feasible": False,
                "rejection_reason": f"Price ₹{candidate_price:.2f} is below minimum price ₹{min_p:.2f}"
            }
            
        # 4. Minimum margin percentage
        margin_pct = ((candidate_price - unit_cost) / candidate_price) * 100.0 if candidate_price > 0 else 0.0
        min_margin = float(policy.get("minimum_margin_pct", 10.0))
        if margin_pct < min_margin:
            return {
                "is_feasible": False,
                "rejection_reason": f"Margin {margin_pct:.1f}% is below minimum required {min_margin}%"
            }
            
        # 5. Cadence / days between changes
        min_days = int(policy.get("minimum_days_between_changes", 14))
        if discount_pct > 0:
            if not has_history:
                return {
                    "is_feasible": False,
                    "rejection_reason": "Missing or unverified price-change history: cadence constraint cannot be validated; markdown blocked pending review"
                }
            if days_since_last_change is not None and days_since_last_change < min_days:
                return {
                    "is_feasible": False,
                    "rejection_reason": f"Only {days_since_last_change} days since last change (minimum {min_days} required)"
                }
                
        return {
            "is_feasible": True,
            "margin_pct": round(margin_pct, 2),
            "rejection_reason": None
        }
