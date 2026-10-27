# Deterministic Markdown Optimizer: Pilot Execution Report

- **Run ID**: `run_20261019_155359_pilot_d12416`
- **Run Timestamp**: 2026-10-19 15:53:59
- **Scope**: Pilot optimization across representative test-period store-SKU inventory states
- **Constraints Applied**: Pricing policy hierarchy, minimum margin threshold, allowed steps, stockout risk bounds
- **Approval Workflow**: Explicit Human-in-the-Loop approval gate enforced

---

## 1. Pilot Recommendations Summary Table

| Date | Store | SKU | Category | Reg Price | Cost | Opening Stock | 7D Stockout Risk | Policy Applied | Recommended Markdown | Rec Price | Expected 7D Profit | Terminal Stock | Approval Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-04-01 | STORE-01 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 12.0 | 25.0% (LOW) | POL-003 | **10.0%** | **₹719.1** | ₹3673.27 | 3.0 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-01 | SKU-0161 | Dress | ₹2499.0 | ₹923.0 | 33.0 | 0.0% (LOW) | POL-005 | **0.0%** | **₹2499.0** | ₹3102.20 | 31.0 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-01 | SKU-0176 | Activewear | ₹2299.0 | ₹808.0 | 0.0 | 92.4% (HIGH) | POL-007 | **0.0%** | **₹2299.0** | ₹0.00 | 0.0 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-01 | SKU-0191 | Jeans | ₹2599.0 | ₹1146.0 | 18.0 | 0.1% (LOW) | POL-004 | **0.0%** | **₹2599.0** | ₹2391.20 | 16.4 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-02 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 49.0 | 0.0% (LOW) | POL-003 | **0.0%** | **₹799.0** | ₹1736.15 | 45.4 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-02 | SKU-0156 | Dress | ₹3499.0 | ₹1393.0 | 37.0 | 0.0% (LOW) | POL-005 | **0.0%** | **₹3499.0** | ₹5591.64 | 34.3 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-02 | SKU-0181 | Activewear | ₹1999.0 | ₹835.0 | 17.0 | 0.0% (LOW) | POL-007 | **0.0%** | **₹1999.0** | ₹1860.19 | 15.4 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-02 | SKU-0191 | Jeans | ₹2599.0 | ₹1146.0 | 14.0 | 0.2% (LOW) | POL-004 | **0.0%** | **₹2599.0** | ₹2173.54 | 12.5 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-03 | SKU-0141 | TShirt | ₹799.0 | ₹310.0 | 22.0 | 0.2% (LOW) | POL-003 | **0.0%** | **₹799.0** | ₹2322.16 | 17.3 | `PENDING_APPROVAL` |
| 2025-04-01 | STORE-03 | SKU-0156 | Dress | ₹3499.0 | ₹1393.0 | 33.0 | 0.0% (LOW) | POL-005 | **10.0%** | **₹3149.1** | ₹3069.49 | 31.3 | `PENDING_APPROVAL` |

---

## 2. Decision Logic and Policy Precedence Verified

1. **Policy Hierarchy**: SKU-specific overrides (e.g. `POL-009` through `POL-013` with 30% discount cap) override category and chain rules.
2. **Margin Constraint**: Candidates violating `minimum_margin_pct` (e.g., 10% to 15%) are rejected deterministically before profit ranking.
3. **Inventory & Stockout Guardrails**: Items with candidate-specific stockout risk (>60%) receive an inventory risk penalty, discouraging aggressive markdowns on scarce stock.
4. **Audit Trail**: Every evaluated candidate, rejected step, and financial calculation is logged in an isolated, versioned audit run directory.
