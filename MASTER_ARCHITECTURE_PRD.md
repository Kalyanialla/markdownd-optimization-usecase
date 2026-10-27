# UC-RT-03 — Markdown Optimization Platform
## Master Architecture & Product Requirements Document (PRD)

**Document type:** Master PRD + Technical Architecture + Implementation and Acceptance Plan  
**Project root:** `C:\MarkDown Optimization Usecase`  
**Status:** Baseline derived from the reported Milestone 3 completion report; verify all repository details before implementation.  
**Architecture principle:** One source of truth, phased implementation, no competing designs.

---

## 1. Executive Summary

Build a professional markdown optimization decision-support application for apparel, specialty, and seasonal retail. The application will reuse the project's existing demand, observational price-response, and stockout models and existing deterministic optimizer services to evaluate candidate prices, estimate financial outcomes, enforce pricing policies, and support human-reviewed recommendations.

The product must connect data exploration, optimization, governance, and auditability in one end-to-end workflow. It must not retrain or replace existing models merely to fit the application. It must not execute real external price changes: approval records a business decision only unless a separately approved execution integration is later defined.

### Product objectives
- Explore products, inventory, and price history.
- Generate candidate prices using existing models and optimizer logic.
- Compare estimated demand, financial outcomes, risk, and policy constraints.
- Persist runs, candidates, recommendations, approvals, and audit events.
- Require authorized human review before a recommendation is marked approved.
- Provide reproducible, explainable records of inputs, model versions, policies, and decisions.
- Deliver a secure, responsive React application backed by FastAPI and PostgreSQL.

### Non-goals
- Retraining, replacing, or silently modifying existing ML models.
- Claiming causal price uplift from observational price-response predictions.
- Real-world price execution or retailer-system integrations in this POC.
- Introducing microservices, Redis, or a separate task platform without measured need.
- Duplicating all CSV data into PostgreSQL without a demonstrated requirement.

---

## 2. Current Reported Baseline

The following reflects the user's Milestone 3 report and is not an independent inspection of the local repository.

| Area | Reported baseline | Required treatment |
|---|---|---|
| Backend | FastAPI, SQLAlchemy models, Alembic migrations | Inspect and extend in place |
| Authentication | Signup, login, refresh, logout, current user, RBAC | Verify in browser and against PostgreSQL |
| Database models | Eight tables: users, refresh_tokens, optimization_runs, optimization_candidates, recommendations, approval_events, audit_events, report_artifacts | Preserve; evolve via migrations |
| Frontend | React + TypeScript + Vite application shell | Complete existing pages |
| Model 1 | XGBoost demand model | Reuse existing artifact and feature contract |
| Model 2 | Observational price-response model | Reuse with explicit limitations |
| Model 3 | XGBoost stockout model | Reuse and verify candidate-specific feature alignment |
| Optimizer | Pricing rules, financial calculator, model service, audit service | Integrate existing services; do not duplicate |
| Data | Cleaned data, engineered features, stockout labels, price history, policies | Inspect actual schemas and use validated adapters |
| Tests | Reported 19 backend tests, 66 ML/optimizer tests, frontend production build passed | Preserve and expand; rerun actual commands |

Reported data files include:
- `data/processed/markdown_optimization_cleaned.csv`
- `data/processed/markdown_features_canonical.csv`
- `data/processed/stockout_7d_labels.csv`
- `data/raw/price_history.csv`
- `data/raw/pricing_policies.csv`

Reported model artifacts include:
- `ml/artifacts/model1/xgboost_demand_model.joblib`
- `ml/artifacts/model2/xgboost_price_response_model.joblib`
- `ml/artifacts/model3/xgboost_stockout_model.joblib`

**Mandatory discovery rule:** Before changing code, inspect actual files, columns, model metadata, encoder contracts, current routes, ORM models, migrations, tests, and current frontend structure. Treat the paths above as reported references, not guaranteed facts.

---

## 3. Product Users and Roles

### Admin
- View application-wide operational records.
- List users and change roles under authorization controls.
- Inspect runs, recommendations, policies, and audit events.
- Access administrative governance functionality.

### Analyst
- Browse products, inventory, and historical prices.
- Create optimization runs.
- Compare candidates and their estimates/constraints.
- Submit recommendations for review.
- View runs and recommendations they are authorized to access.

### Approver
- Review submitted recommendations and associated run/candidate evidence.
- Approve or reject with required rationale according to the final permission matrix.
- Inspect prior decisions and associated audit events.

The backend is the authority for role permissions. Hiding a button in React is not authorization.

---

## 4. End-to-End Business Workflow

1. User signs in.
2. User searches products and inspects supported inventory and price-history fields.
3. User selects a SKU/store and requests an optimization run with validated parameters.
4. Backend resolves applicable pricing policies and validates bounds and other constraints.
5. Existing feature preparation and ML services score permitted candidate prices.
6. Existing financial calculator evaluates candidate outcomes and exposes its assumptions.
7. Backend persists the run, candidate results, input/model/policy snapshots, status, and audit evidence.
8. User compares candidates and selects a candidate for recommendation.
9. Analyst submits the recommendation with rationale.
10. Authorized approver approves or rejects; invalid state transitions are refused.
11. Dashboard and audit pages reflect persisted records and real system status.
12. No external price change is executed by this POC.

### Recommendation lifecycle
`DRAFT` (if supported) → `SUBMITTED` → `APPROVED` or `REJECTED`.

Withdrawal or resubmission may be added only with explicit state-transition rules. All transitions must be enforced by the backend and recorded. A recommendation must reference a valid run and candidate. Stale data or obsolete policy snapshots must be flagged or require regeneration according to a documented rule.

---

## 5. Target Architecture

Use a **modular monolith**. Keep clear boundaries without introducing unnecessary distributed infrastructure.

### Frontend
- React
- TypeScript
- Vite
- React Router
- Existing design tokens and components
- Existing animation library if already installed and useful

### Backend
- FastAPI
- Pydantic request/response models
- SQLAlchemy 2
- Alembic migrations
- Existing ML and optimizer modules
- Structured, redacted logging
- Centralized exception and validation handling

### Persistence and data
- PostgreSQL for users, sessions, runs, candidate results, recommendations, decisions, audit events, and artifact metadata.
- Existing CSVs and model files remain local/file-backed for this POC behind validated repository/service adapters.
- File paths are configuration-based and independent of a developer's machine.
- Use bounded caching where appropriate; document cache invalidation and data refresh behavior.
- Do not silently fall back to SQLite when PostgreSQL is configured but unavailable.

### Logical request flow

`React UI → typed API client → FastAPI router → application service → domain/ML services → PostgreSQL + dataset/artifact adapters`

### Architecture rules
- Routes validate and delegate; they do not contain business logic.
- React does not read CSVs or load model artifacts.
- Model predictions are separate from deterministic constraints, permissions, and policy decisions.
- Do not duplicate the policy resolver or profit calculator.
- Load model artifacts through a managed service, validate feature names/order and encoders, and avoid per-request reloads.
- Use background jobs only if measured run latency requires them.
- A missing required model/data file, incompatible schema, or unavailable configured database must fail explicitly.
- Preserve existing working code and tests; refactor only when justified by a verified defect or a clear integration need.

---

## 6. Backend Modules and API Contracts

All application routes should use `/api/v1` unless the existing application has a documented compatible convention. Reconcile the following contracts with actual routes before adding anything; do not create duplicate endpoints.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/signup` | Register user; public input cannot assign privileged role |
| POST | `/api/v1/auth/login` | Authenticate |
| POST | `/api/v1/auth/refresh` | Rotate refresh session |
| POST | `/api/v1/auth/logout` | Revoke refresh session |
| GET | `/api/v1/auth/me` | Current authenticated user |
| GET | `/api/v1/users` | Admin-only paginated user listing |
| PATCH | `/api/v1/users/{user_id}/role` | Admin-only role change |
| GET | `/api/v1/products` | Filtered, sorted, paginated catalog |
| GET | `/api/v1/products/{sku}` | Product details |
| GET | `/api/v1/products/{sku}/price-history` | Historical prices for a supported SKU/store |
| POST | `/api/v1/optimization-runs` | Create/execute a run |
| GET | `/api/v1/optimization-runs` | List authorized runs |
| GET | `/api/v1/optimization-runs/{run_id}` | Run detail and status |
| GET | `/api/v1/optimization-runs/{run_id}/candidates` | Candidate results |
| GET | `/api/v1/optimization-runs/{run_id}/report` | Report metadata/content if supported |
| POST | `/api/v1/recommendations` | Submit recommendation |
| GET | `/api/v1/recommendations` | Filtered recommendation queue |
| GET | `/api/v1/recommendations/{id}` | Recommendation detail |
| POST | `/api/v1/recommendations/{id}/approve` | Approve if authorized and transition valid |
| POST | `/api/v1/recommendations/{id}/reject` | Reject if authorized; require reason |
| POST | `/api/v1/recommendations/{id}/withdraw` | Optional, only if state policy supports it |
| GET | `/api/v1/policies` | Read policy list |
| GET | `/api/v1/policies/resolve` | Explain matching policy for SKU/store/context |
| GET | `/api/v1/audit` | Filtered, paginated audit events |
| GET | `/api/v1/audit/{event_id}` | Audit event detail |
| GET | `/api/v1/dashboard/summary` | Aggregates from persisted records |
| GET | `/api/v1/system/health` | Process health |
| GET | `/api/v1/system/ready` | Dependency readiness |
| GET | `/api/v1/system/models` | Model loading and feature-contract status |

### API requirements
- Typed Pydantic request and response models.
- Consistent error shape and meaningful HTTP status codes.
- Pagination with bounded limits and deterministic ordering.
- Validate sorting fields against an allowlist.
- Validate SKU/store existence against source data.
- Enforce authorization and record ownership/scope in backend queries.
- Use request IDs/correlation IDs in logs without leaking secrets.
- Add idempotency support to operations where client retries could create duplicate runs or decisions.
- Avoid returning absolute filesystem paths or stack traces to clients.
- Document APIs through OpenAPI.

---

## 7. Database and Persistence Requirements

Preserve and inspect the reported eight-table schema before modifying it.

| Table | Responsibility |
|---|---|
| `users` | Identity, password hash, role, active state, timestamps |
| `refresh_tokens` | Token hash, expiry, rotation/revocation metadata |
| `optimization_runs` | Request, status, requester, SKU/store, idempotency key, input/model/policy snapshots, error metadata |
| `optimization_candidates` | Candidate price, predictions, risk, constraints, financial components, candidate status |
| `recommendations` | Run/candidate reference, submitter, status, rationale |
| `approval_events` | Actor, decision, reason, timestamp, prior/new status |
| `audit_events` | Actor, action, resource, event time, structured details |
| `report_artifacts` | Run linkage, relative artifact reference, checksum, metadata |

### Persistence rules
- Use UUIDs where already established and timezone-aware timestamps.
- Use PostgreSQL-compatible JSON storage and explicit validation for snapshot schemas.
- Use Alembic for every schema change.
- Use foreign keys and appropriate indexes/unique constraints.
- Enforce idempotency at the database level where appropriate.
- Keep approval and audit history append-only at the application level; do not rewrite prior events to represent a new decision.
- Store relative artifact references and checksums; prevent path traversal and access outside the approved artifact root.
- Snapshot model identifiers/versions or hashes, relevant inputs, policy resolution, scoring configuration, and feature-contract identifiers for reproducibility.
- Test migration from the real existing schema and preserve user/application data.
- SQLite unit tests are useful but do not replace PostgreSQL integration tests.

---

## 8. Authentication and Security

Retain the reported Milestone 3 implementation but verify it before extending.

- Strong password hashing using a maintained, compatible implementation.
- Access JWTs with explicit token type, issuer/audience validation where configured, and short expiry.
- Cryptographically secure refresh tokens; store only hashes.
- Refresh rotation, expiry, revocation, and replay rejection.
- Logout revokes the refresh session and clears cookies.
- Public signup ignores/rejects client-selected privileged roles.
- First-admin bootstrap must be concurrency-safe on PostgreSQL; test simultaneous first-signup requests against PostgreSQL.
- Prevent accidental demotion/deactivation of the last viable administrator.
- Use HttpOnly cookies with suitable `Secure` and `SameSite` flags in deployment.
- If cookies authenticate state-changing requests, implement CSRF defenses appropriate to the selected architecture.
- CORS allowlist must be environment-configured and narrow.
- Never log passwords, access tokens, refresh tokens, cookie values, or secrets.
- Store secrets in environment configuration or a suitable secret manager, never source control.
- Apply server-side role checks to every protected endpoint.
- Validate file paths, request sizes, pagination bounds, and accepted enum values.
- Use generic login errors to avoid account enumeration.
- Ensure authentication state and API retries cannot cause duplicate state-changing requests.

---

## 9. ML Model and Optimizer Integration

### Existing reported artifacts
- Model 1: `ml/artifacts/model1/xgboost_demand_model.joblib`
- Model 2: `ml/artifacts/model2/xgboost_price_response_model.joblib`
- Model 3: `ml/artifacts/model3/xgboost_stockout_model.joblib`

Inspect actual artifact paths, metadata, encoders, feature columns/order, package versions, and service interfaces before implementation.

### Model responsibilities
- **Model 1 — Baseline demand:** estimate demand using its trained feature contract.
- **Model 2 — Candidate price response:** estimate candidate demand from observational training data. Do not present this as causal price elasticity or proven incremental uplift.
- **Model 3 — Stockout risk:** estimate candidate-specific stockout risk; ensure candidate features are recomputed correctly and match the trained feature order.

### Optimization orchestration
1. Validate user authorization and run request.
2. Load/validate SKU, store, current price, inventory and required features.
3. Resolve applicable policy using the existing hierarchy: SKU → STORE → CATEGORY → CHAIN → DEFAULT.
4. Validate pricing constraints and generate allowed candidate prices.
5. Prepare candidate-specific feature rows using existing feature preparation logic.
6. Score candidates with existing model service and verify output shape/ranges.
7. Calculate financial estimates using the existing financial calculator.
8. Apply deterministic risk/constraint handling as already specified in existing optimizer code.
9. Persist run, candidates, status, model/policy/input snapshots and audit events.
10. Return candidate comparisons and explicit warnings/assumptions.

Do not create a parallel model-serving stack, a second policy engine, or a second profit calculator.

### Financial interpretation and limitations
- Predicted demand is not guaranteed sales.
- The reported financial calculator uses a seven-day demand approximation; label outputs as estimates if that remains the implementation.
- Fulfilled demand, terminal stock, gross profit, and stockout penalties must be explained according to the actual formula.
- Heuristic stockout thresholds/penalties must be visible and configurable through the existing approved mechanism.
- Observational price-response estimates are scenarios, not causal uplift.
- Prior reports noted distribution shift and unverified probability calibration. Preserve these caveats until new evidence supports changing them.
- Never fabricate confidence intervals, performance metrics, causal effects, or business savings.
- Do not retrain models as part of application integration.

---

## 10. Pricing Policy and Constraint Governance

- Reuse the existing deterministic policy resolver and conflict-resolution rules.
- Preserve the reported hierarchy: SKU > STORE > CATEGORY > CHAIN > DEFAULT.
- Verify active/retired policy handling and deterministic tie-breaking.
- Show the effective policy, source scope, policy identifier, and relevant constraints for a run.
- Reject invalid requests and block policy-violating candidates; never silently bypass a constraint.
- Snapshot the effective policy and its relevant version/content for each run.
- Treat policy management as read-only for the POC unless write workflows, permissions, validation, and audit requirements are explicitly approved.
- Ensure candidate prices obey actual configured price bounds, markdown limits, margin constraints, cadence constraints, and other implemented rules.
- Tests must cover overlapping scopes, retired policies, ties, missing policies, invalid prices, and boundary conditions supported by the existing policy model.

---

## 11. Frontend Product Requirements

Keep the existing Industrial Editorial design system reported in Milestone 3:
- Obsidian surfaces: `#10151B`, `#151C24`, `#1A232E`, `#212C3A`
- Borders: `#232F3E`, `#334356`
- Signal Lime: `#C7F36B`
- Mint: `#66D9CB`
- Amber: `#F1A76B`
- Coral: `#FF6B6B`
- Respect reduced-motion preferences and visible keyboard focus.
- Preserve the existing typography choices if they are already integrated.

### Required pages
1. `/login` — authentication.
2. `/signup` — registration.
3. `/dashboard` — truthful system/data/run/recommendation summary.
4. `/products` — searchable, filterable product/inventory explorer.
5. `/optimize` — run configuration, execution state, candidate comparison and explanations.
6. `/reviews` — submitted recommendation queue and authorized review actions.
7. `/policies` — policy list, matching policy and resolution explanation.
8. `/audit` — searchable/paginated event history.
9. Admin user-management view, if not already available.

### Shared UI
- Responsive application shell, sidebar/navigation, top bar, current user and sign-out.
- Typed API client and shared error handling.
- Loading, empty, success, stale-data and error states.
- Protected routes and role-aware actions.
- Accessible keyboard interactions and focus management.
- Responsive tables and usable mobile layouts.
- No hardcoded fake counts or placeholder records in production views.
- Do not put authorization, policy, scoring, or financial business rules in React.
- Charts must use real API data and clearly labelled units/time ranges.

### Products page
- Search by supported product identifiers and names.
- Filters for category/store/stock status only if source data contains those fields.
- Sorting through a safe allowlist and server pagination.
- Detail view for available inventory and price history.
- Missing data should be explained; do not invent elasticity or product KPIs.

### Optimization page
- Select supported SKU/store and valid run parameters.
- Explain current price and applicable policy.
- Show run status, errors, candidate prices, demand estimate, stockout risk, financial estimates, constraint results, and assumptions.
- Compare candidates using consistent units and a clear baseline.
- Allow recommendation submission only when run/candidate/state requirements pass.
- Avoid implying a model prediction is a guaranteed outcome.

### Review page
- Show recommendation status, submitter, SKU/store, candidate, run link and rationale.
- Show relevant evidence and warnings.
- Enforce role/state checks on server actions.
- Require rejection reason and record the decision.
- Prevent duplicate decisions and refresh stale records after a transition.

### Audit page
- Filter by date, actor, action, resource and run/recommendation identifiers where supported.
- Paginate deterministically.
- Show before/after state or structured event details where captured.
- Never present missing audit data as if it existed.

---

## 12. Dashboard and Observability

Dashboard metrics must be calculated from actual persisted records and current system checks.

Potential metrics, only where supported by real data:
- Runs by status and recent period.
- Recommendations awaiting review.
- Approved/rejected counts.
- Recent activity.
- Model load/contract status.
- Dataset availability and last successful validation.
- Database readiness.

Do not show invented margin improvement, revenue lift, model accuracy, or savings. If a metric is not available, show a clear unavailable state rather than a fabricated zero.

Operational logging should include request/correlation ID, endpoint, elapsed time, run ID where relevant, and a safe error code. Redact credentials, tokens, personal secrets and sensitive request payloads.

Health and readiness must be distinct:
- Health: process can respond.
- Readiness: required dependencies for the requested service are available.
- Model status: artifacts load and satisfy expected contracts; expose safe diagnostics only.

---

## 13. Testing and Acceptance Criteria

### Backend and database
- Signup/login/refresh/logout/expiry and role enforcement.
- Simultaneous first-admin signup against PostgreSQL.
- Alembic migration from the actual current schema.
- PostgreSQL integration tests for constraints, transactions, JSON fields, locking and idempotency where used.
- Product adapter validation, filters, pagination, missing files, malformed rows and unknown SKUs.
- API authentication, validation, authorization and error responses.
- Run lifecycle, candidate persistence, retry/error behavior and idempotency.
- Policy resolution and invalid-candidate rejection.
- Recommendation transitions, approval/rejection permissions and duplicate decisions.
- Audit event creation and historical preservation.
- Artifact path validation and checksum behavior.

### ML and financial scoring
- Existing artifact loading and feature/encoder compatibility.
- Feature names/order and candidate-specific feature recomputation.
- Prediction shape, non-finite output and invalid-input handling.
- Existing model/optimizer regression tests remain passing.
- Financial calculations tested against deterministic known examples.
- Policy constraints remain enforced under edge cases.
- Existing data/model limitations are documented, not hidden.

### Frontend
- `tsc` and production build.
- Login/logout/session refresh and protected routes.
- Product search/filter/sort/pagination/detail/history.
- Optimization request, run status, candidate comparisons and errors.
- Recommendation submission and approval/rejection flows.
- Policies and audit filters.
- Loading/empty/error states, keyboard accessibility and responsive layout.

### End-to-end
- Launch frontend, FastAPI and PostgreSQL.
- Complete the workflow from product selection through optimization, recommendation, decision, and audit inspection.
- Restart the backend and verify persisted runs and decisions remain.
- Verify database/model/data outages produce explicit errors.
- Confirm no real external pricing action occurs.

### Acceptance gate
A phase is complete only when its acceptance criteria have been run and the actual results recorded. Report separately:
- Verified by automated tests.
- Verified manually in the browser.
- Verified against PostgreSQL.
- Not tested.
- Known limitations.

Do not claim production readiness from a successful frontend build or SQLite-only tests.

---

## 14. Delivery Phases — One PRD, Controlled Execution

The architecture and requirements above remain the single source of truth. Execute in these dependency-ordered phases:

### Phase A — Inspect and verify foundation
- Inspect repository, Milestone 2/3 implementation, routes, migrations, tests, datasets and model contracts.
- Run current tests.
- Run Alembic against the configured PostgreSQL instance.
- Fix only verified foundation defects.
- Verify auth/session behavior and first-admin concurrency against PostgreSQL.

### Phase B — Product and inventory
- Implement validated dataset adapters and backend APIs.
- Complete product search, filters, pagination, detail and price history.
- Add unit/API/UI tests.

### Phase C — Optimization integration
- Integrate existing model service, candidate generation, policy resolver and financial calculator.
- Persist run and candidate results.
- Add failure handling, snapshots, idempotency and tests.

### Phase D — Recommendation and approvals
- Implement submission, queue, approval/rejection and state-transition enforcement.
- Record decision rationale and audit events.
- Test permissions, concurrency and invalid transitions.

### Phase E — Policies, audit and dashboard
- Connect real policy resolution and audit queries.
- Build persisted operational summaries and system status views.
- Remove misleading placeholders.

### Phase F — End-to-end hardening
- Complete backend, PostgreSQL, ML regression, frontend and end-to-end tests.
- Review warnings and security behavior.
- Document environment configuration, migrations, launch, recovery and limitations.

**Execution rule:** Do not stop after writing a plan. Inspect, implement, run tests, fix failures, and continue through the phases unless a blocker requires user input. If blocked, state the exact blocker, evidence, and the smallest decision needed.

---

## 15. Environment and Local Run Requirements

- Keep secrets in `backend/.env` or an approved secret manager; commit only `.env.example`.
- Configure the PostgreSQL URL using the driver's supported SQLAlchemy format, e.g. `postgresql+psycopg://<user>:<password>@localhost:<port>/<database>`.
- URL-encode special characters in credentials where required.
- Confirm the database exists and the configured database user has least-privilege permissions.
- Run Alembic migrations using the project's configured Alembic setup.
- Install backend dependencies from the actual project requirements.
- Start FastAPI using the verified app import path.
- Install frontend dependencies using the existing lockfile and run the Vite dev server.
- Never probe common passwords or print secrets while troubleshooting.
- Document the exact verified commands and ports in the final implementation report.
- Do not claim the application is deployed; this PRD covers local POC completion unless a deployment target is separately approved.

---

## 16. Final Deliverables

At completion, provide:
1. Implemented architecture and module map.
2. Final API endpoint list and OpenAPI location.
3. Database migration list and PostgreSQL verification evidence.
4. ML artifacts reused, feature contracts verified, and known model limitations.
5. Product/inventory, optimization, recommendation, policy, dashboard and audit workflows implemented.
6. Security/session/RBAC checks completed.
7. Actual commands and test results, grouped by backend, PostgreSQL, ML, frontend and end-to-end.
8. Known warnings, limitations and untested areas.
9. Exact local setup and launch instructions.
10. A phase-by-phase acceptance matrix with pass/fail/not-tested status.

---

## 17. Master Coding-Agent Directive

Use this directive together with the entire PRD:

> Treat this document as the single source of truth for completing the existing UC-RT-03 Markdown Optimization application at `C:\MarkDown Optimization Usecase`. Inspect the real repository before editing. Complete all remaining phases in dependency order using one coherent architecture. Do not create competing PRDs or duplicate business logic. Preserve existing trained ML artifacts, datasets, feature contracts, optimizer services, policy hierarchy, financial calculations and passing regression tests. Verify Milestone 3 authentication and migrations against PostgreSQL, then complete product/inventory integration, optimization orchestration, persisted runs/candidates, recommendations, human approvals, policies, audit, dashboard and end-to-end validation.
>
> Use React + TypeScript + Vite, FastAPI, SQLAlchemy 2, Alembic and PostgreSQL as specified. Keep ML orchestration and business rules on the backend. Enforce server-side RBAC, secure session handling, idempotency, transaction-safe state transitions, input/model/policy snapshots and traceable audit events. Do not fabricate metrics or outputs, silently fall back to SQLite, probe database passwords, expose secrets, retrain models unnecessarily, or execute external price changes.
>
> Work incrementally: inspect, plan briefly, implement, test, fix, and continue. Do not stop after a plan. Do not claim completion while required acceptance criteria remain unverified. Report actual commands and results, changed files, unresolved issues, and whether each phase gate passed. At final completion, report architecture, API contracts, migrations, ML integration, security checks, actual test results, known limitations and exact local launch instructions. Never claim a test, migration, browser workflow, or deployment succeeded unless it actually ran and passed.
