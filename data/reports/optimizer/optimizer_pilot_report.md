# Deterministic Markdown Optimizer: Pilot Execution Report

- **Run Timestamp**: 2026-10-19 12:01:01
- **Scope**: Pilot optimization across representative test-period store-SKU inventory states
- **Constraints Applied**: Pricing policy hierarchy, minimum margin threshold, allowed steps, stockout risk bounds
- **Approval Workflow**: Explicit Human-in-the-Loop approval gate enforced

---

## 1. Pilot Recommendations Summary Table

| Date | Store | SKU | Category | Reg Price | Cost | Opening Stock | 7D Stockout Risk | Policy Applied | Recommended Markdown | Rec Price | Expected 7D Profit | Terminal Stock | Approval Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-04-01 | STORE-01 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 12.0 | 24.1% (LOW) | POL-003 | **10.0%** | **₹719.1** | ₹3673.15 | 3.0 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-01 | SKU-0161 | Dress | ₹2499.0 | ₹923.0 | 33.0 | 0.0% (LOW) | POL-005 | **0.0%** | **₹2499.0** | ₹3102.14 | 31.0 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-01 | SKU-0176 | Activewear | ₹2299.0 | ₹808.0 | 0.0 | 94.5% (HIGH) | POL-007 | **0.0%** | **₹2299.0** | ₹0.00 | 0.0 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-01 | SKU-0191 | Jeans | ₹2599.0 | ₹1146.0 | 18.0 | 0.1% (LOW) | POL-004 | **0.0%** | **₹2599.0** | ₹2391.18 | 16.4 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-02 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 49.0 | 0.0% (LOW) | POL-003 | **0.0%** | **₹799.0** | ₹1736.17 | 45.4 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-02 | SKU-0156 | Dress | ₹3499.0 | ₹1393.0 | 37.0 | 0.0% (LOW) | POL-005 | **0.0%** | **₹3499.0** | ₹5591.31 | 34.3 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-02 | SKU-0181 | Activewear | ₹1999.0 | ₹835.0 | 17.0 | 0.0% (LOW) | POL-007 | **0.0%** | **₹1999.0** | ₹1859.83 | 15.4 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-02 | SKU-0191 | Jeans | ₹2599.0 | ₹1146.0 | 14.0 | 0.2% (LOW) | POL-004 | **0.0%** | **₹2599.0** | ₹2173.12 | 12.5 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-03 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 22.0 | 0.3% (LOW) | POL-003 | **0.0%** | **₹799.0** | ₹2322.29 | 17.3 | `APPROVED_BY_RULE_AND_HUMAN` |
| 2025-04-01 | STORE-03 | SKU-0156 | Dress | ₹3499.0 | ₹1393.0 | 33.0 | 0.0% (LOW) | POL-005 | **10.0%** | **₹3149.1** | ₹3070.04 | 31.3 | `APPROVED_BY_RULE_AND_HUMAN` |

---

## 2. Decision Logic and Policy Precedence Verified

1. **Policy Hierarchy**: SKU-specific overrides (e.g. `POL-009` through `POL-013` with 30% discount cap) override category and chain rules.
2. **Margin Constraint**: Candidates violating `minimum_margin_pct` (e.g., 10% to 15%) are rejected deterministically before profit ranking.
3. **Inventory & Stockout Guardrails**: Items with high stockout risk (>60%) receive an inventory risk penalty, discouraging aggressive markdowns on scarce stock.
4. **Audit Trail**: Every evaluated candidate, rejected step, and financial calculation is logged in `pilot_optimization_audit.json`.
