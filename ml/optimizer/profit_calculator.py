"""
UC-RT-03: Profit and Inventory Constraint Calculator for Markdown Optimization.

Calculates:
- Expected sales capped by available inventory.
- Expected daily revenue and gross profit.
- Expected 7-day terminal inventory.
- Risk penalty based on stockout probability.
"""

from typing import Dict, Any

class MarkdownProfitCalculator:
    @staticmethod
    def calculate_candidate_financials(
        candidate_price: float,
        unit_cost: float,
        predicted_daily_demand: float,
        opening_stock: float,
        stockout_prob: float,
        planning_horizon_days: int = 7,
        objective_mode: str = "MAX_PROFIT",
        clearance_holding_cost_rate: float = 0.15
    ) -> Dict[str, Any]:
        """
        Calculates expected financials accounting for inventory constraints, stockout risk,
        sell-through rate, and terminal inventory holding/clearance economics.

        Economic Valuation Assumptions for Seasonal Clearance (P1):
        -------------------------------------------------------------
        1. Gross Profit is earned exclusively on units sold (Fulfilled Units * Unit Margin).
        2. Cost of Goods Sold (COGS) for fulfilled units is already subtracted in Gross Profit.
        3. Terminal Inventory (Opening Stock - Fulfilled Units) is unsold stock at the end of the horizon:
           - Unsold stock is NOT assumed to be a 100% loss because it retains future salvage / liquidation value.
           - Instead, carrying unsold inventory past the clearance window incurs:
             a. Capital tie-up & warehouse carrying costs (approx. 5%-10% of cost).
             b. Secondary salvage markdown loss upon ultimate off-price liquidation (approx. 10%-15% of cost).
           - Net Holding & Obsolescence Rate (alpha): default = 0.15 (15% of unit cost per leftover unit).
           - Residual Holding Cost = Terminal Stock * (Unit Cost * alpha).
        4. Clearance-Adjusted Profit = Risk-Adjusted Profit - Residual Holding Cost.
        5. Objective Modes:
           - 'MAX_PROFIT' (P0 Baseline): ranking_score = Risk-Adjusted Profit.
           - 'CLEAR_INVENTORY' (P1 Mode): ranking_score = Clearance-Adjusted Profit.
        6. Sell-Through Rate:
           - Defined as (Fulfilled Units / Opening Stock) * 100.
           - When Opening Stock is zero, returns None (documented as N/A: Zero Opening Stock).
        """
        p_price = float(candidate_price)
        u_cost = float(unit_cost)
        daily_d = max(0.0, float(predicted_daily_demand))
        open_stock = max(0.0, float(opening_stock))
        s_prob = max(0.0, min(1.0, float(stockout_prob)))
        h_days = max(1, int(planning_horizon_days))
        h_rate = max(0.0, min(1.0, float(clearance_holding_cost_rate)))
        mode = str(objective_mode).strip().upper() if objective_mode else "MAX_PROFIT"

        unit_margin = round(p_price - u_cost, 2)

        # 1. Demand & Inventory Constraints
        effective_demand_7d = round(daily_d * h_days, 2)
        fulfilled_units_7d = round(min(effective_demand_7d, open_stock), 2)
        terminal_stock_7d = round(max(0.0, open_stock - fulfilled_units_7d), 2)

        # 2. Sell-Through Percentage
        if open_stock > 0:
            sell_through_pct = round((fulfilled_units_7d / open_stock) * 100.0, 2)
        else:
            sell_through_pct = None

        # 3. Revenue & Gross Profit
        expected_revenue_7d = round(fulfilled_units_7d * p_price, 2)
        expected_gross_profit_7d = round(fulfilled_units_7d * unit_margin, 2)

        # 4. Stockout Risk Penalty (P0 Linear Penalty above 60% probability)
        stockout_penalty = 0.0
        if s_prob > 0.60:
            # Only penalize positive margin units; selling below cost does not earn penalty relief
            stockout_penalty = round(max(0.0, (s_prob - 0.60) * unit_margin * fulfilled_units_7d * 0.25), 2)

        risk_adjusted_profit = round(expected_gross_profit_7d - stockout_penalty, 2)

        # 5. Clearance Economics: Residual Holding & Obsolescence Cost
        # If unit_cost <= 0, holding cost on inventory value is 0.0
        unit_holding_loss = max(0.0, u_cost) * h_rate
        residual_holding_cost = round(terminal_stock_7d * unit_holding_loss, 2)
        clearance_adjusted_profit = round(risk_adjusted_profit - residual_holding_cost, 2)

        # 6. Objective Ranking Score
        if mode == "CLEAR_INVENTORY":
            ranking_score = clearance_adjusted_profit
            explanation = (
                f"Evaluated under Seasonal Clearance objective: ${risk_adjusted_profit:.2f} risk-adjusted profit "
                f"minus ${residual_holding_cost:.2f} terminal holding cost on {terminal_stock_7d:.1f} leftover units "
                f"({sell_through_pct if sell_through_pct is not None else 0.0:.1f}% sell-through). "
                f"Net clearance score: ${clearance_adjusted_profit:.2f}."
            )
        else:
            ranking_score = risk_adjusted_profit
            explanation = (
                f"Evaluated under Margin Maximization objective: ${risk_adjusted_profit:.2f} risk-adjusted profit "
                f"based on {fulfilled_units_7d:.1f} fulfilled units ({sell_through_pct if sell_through_pct is not None else 0.0:.1f}% sell-through) "
                f"with {terminal_stock_7d:.1f} residual inventory."
            )

        return {
            # Legacy P0 fields (strictly preserved for backward compatibility)
            "candidate_price": round(p_price, 2),
            "unit_margin": unit_margin,
            "predicted_daily_demand": round(daily_d, 3),
            "effective_demand_7d_approximation": effective_demand_7d,
            "expected_fulfilled_units_7d": fulfilled_units_7d,
            "expected_revenue_7d": expected_revenue_7d,
            "expected_gross_profit_7d": expected_gross_profit_7d,
            "risk_adjusted_profit_7d": risk_adjusted_profit,
            "expected_terminal_stock_7d": terminal_stock_7d,
            # Horizon-neutral standardized metrics
            "planning_horizon_days": h_days,
            "expected_fulfilled_units": fulfilled_units_7d,
            "expected_revenue": expected_revenue_7d,
            "expected_gross_profit": expected_gross_profit_7d,
            "risk_adjusted_profit": risk_adjusted_profit,
            "expected_terminal_stock": terminal_stock_7d,
            "stockout_probability": round(s_prob, 4),
            "stockout_risk_penalty": stockout_penalty,
            # P1 Seasonal Clearance & Sell-Through Metrics
            "sell_through_pct": sell_through_pct,
            "residual_holding_cost": residual_holding_cost,
            "clearance_adjusted_profit": clearance_adjusted_profit,
            "ranking_score": ranking_score,
            "objective_mode": mode,
            "clearance_holding_cost_rate": h_rate,
            "explanation": explanation,
            "horizon_approximation_note": f"{h_days}-day demand is a linear extrapolation approximation of single-day forecast (does not account for intra-week day-of-week demand variance)",
            "stockout_penalty_heuristic_note": "Penalty scales with fulfilled volume above 60% probability; requires calibration with merchandising for near-zero inventory states",
            "clearance_economic_note": f"Terminal inventory holding & obsolescence rate set to {h_rate * 100:.1f}% of unit cost (${unit_holding_loss:.2f}/unit)"
        }
