# Seven-Day Stockout Risk Target Construction Audit (v2 - with Boundary Purge)

- **Generated Date**: 2026-10-19 12:16:14
- **Version**: v2 (fixes temporal contamination via 7-day split-boundary purge)

## 1. Boundary Purge Applied

| Purge Region | Rows Purged |
| :--- | :--- |
| Train rows 2024-12-25 to 2024-12-31 (window into val) | 1,995 |
| Val rows 2025-03-25 to 2025-03-31 (window into test) | 1,820 |

## 2. Label Statistics by Split

| Split | Eligible Rows | Positive Rate |
| :--- | :--- | :--- |
| Train (2024) | 100,696 | 26.07% |
| Validation (Q1 2025) | 20,320 | 0.46% |
| Test (Q2 2025) | 22,918 | 42.43% |

## 3. Leakage Guardrails

- [x] Forward shift applied: T+1 to T+7 only (current day excluded).
- [x] 7-day boundary purge applied at each split transition.
- [x] No leakage columns in inference features.
