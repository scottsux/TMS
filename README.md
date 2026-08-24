# Transportation Management System (TMS) MVP

A full-stack logistics workflow prototype for parcel consolidation, warehouse packing, shipment completion, and settlement. The project models the handoffs between customers, operations staff, and warehouse operators in a lightweight Transportation Management System (TMS).

> **Portfolio scope:** This is an independent MVP, not a production deployment. It demonstrates full-stack delivery and logistics workflow modeling. It does **not** include AI/LLM features, carrier integrations, payment processing, or production infrastructure.

The planned expansion from this MVP to an AI-enabled TMS is documented in
[ARCHITECTURE_ROADMAP.md](ARCHITECTURE_ROADMAP.md). The roadmap separates implemented
capabilities from future work so that portfolio and CV claims remain evidence-based.

## Why this project

Parcel-consolidation operations frequently depend on manual coordination: customers submit parcels, warehouses confirm arrival, customers request consolidation, operators pack and weigh orders, and staff complete shipping and pricing.

This MVP turns that workflow into a role-based web application with explicit state transitions, API-level authorization, persistent operational data, and a browser-based operations console.

## Implemented workflow

```text
Customer creates parcel
  -> Parcel is in transit
  -> Staff marks it arrived
  -> Customer selects arrived parcels and requests packing
  -> System creates or reuses an order and a packing task
  -> Operator starts the task and completes packing
  -> Order becomes ready to ship
  -> Staff completes shipment and can calculate/override price
```

In the current implementation, “complete shipment” is an internal order completion
and timestamp update. It is not carrier tracking, delivery confirmation, or proof of
receipt.

### Roles

| Role | Implemented responsibilities |
| --- | --- |
| `customer` | Create parcels, view only owned parcels/orders, request packing for eligible parcels |
| `staff` | Mark parcels arrived, manage orders, price orders, complete shipment, view customers |
| `operator` | View packing work, start and complete packing tasks, view notifications |

## Features implemented

- **Authentication and API authorization:** email/password login, PBKDF2 password verification, signed HMAC token, and server-side role checks.
- **Parcel intake:** unique tracking-number validation, customer-scoped parcel access, parcel status updates, and image-upload validation (up to five PNG/JPEG/WebP files, 5 MB each).
- **Order consolidation:** create an order from eligible parcels, prevent cross-customer or duplicate assignment, and save forwarding/consignee information as an order snapshot.
- **Warehouse task flow:** create one packing task per order, start packing, record actual weight, and synchronize task/order/parcel states.
- **Shipping and notifications:** complete shipment for ready-to-ship orders and store customer-oriented notification payloads.
- **Settlement:** calculate `actual_weight × rate_per_kg + extra_fee` and allow a staff user to override the final price.
- **Operations UI:** role-aware dashboard, parcel list, order list/detail, task board, billing view, customer list, and parcel-upload page.

## Architecture

```text
Vue 3 + Vite + Pinia + Vue Router
              |
       fetch + Bearer token
              |
FastAPI monolith (REST APIs, RBAC, state transitions)
              |
      Python sqlite3 / SQLite
              |
customers, users, parcels, orders, tasks, notifications
```

### Technology stack

- **Frontend:** Vue 3, Vite, Pinia, Vue Router, browser Fetch API, Tailwind/PostCSS utilities
- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Data:** SQLite with parameterized SQL via Python's built-in `sqlite3`
- **Developer tooling:** Ruff configuration, Prettier configuration, EditorConfig, Git

## Data model and workflow states

The application initializes the following SQLite tables: `customers`, `users`, `parcels`, `orders`, `tasks`, and `notifications`.

Current workflow states are intentionally small and explicit:

```text
Parcel: IN_TRANSIT -> ARRIVED -> PACK_REQUESTED -> PACKED
Order:  DRAFT -> READY_TO_PACK -> PACKING -> READY_TO_SHIP -> COMPLETED
Task:   TODO -> IN_PROGRESS -> DONE
```

`SUBMITTED` and `REJECTED` are also present in the parcel enum, but the current parcel-creation endpoint starts directly at `IN_TRANSIT`.

## Repository layout

```text
backend/
  main.py                 # FastAPI app, schema bootstrap, business logic, APIs
  requirements.txt
  tests/test_p0_flow.py   # Core workflow test cases
frontend/
  src/
    api/                  # HTTP client
    stores/               # Authentication and UI state
    router/               # Route definitions and client-side guards
    views/                # Role-facing operational pages
README.md
ARCHITECTURE_ROADMAP.md     # Current-to-target architecture and CV boundaries
IMPLEMENTATION_PLAN.md      # Agent execution rules and milestone gates
FLOWS_DIAGRAMS.md         # Workflow diagrams and business-flow notes
FRONTEND_PAGE_FUNCTIONS.md # Current pages, roles, and planned page extensions
MANUAL_TEST_PLAN.md       # Manual verification scenarios
```

## Run locally

### Prerequisites

- Python 3.12 recommended
- Node.js and npm

### Backend

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

The API runs at `http://localhost:8000`. FastAPI also exposes interactive API documentation at `http://localhost:8000/docs`.

The SQLite database is created at `backend/tms.db` when the service starts. Seed demo accounts are created only when the `customers` table is empty:

| Role | Email | Password |
| --- | --- | --- |
| Customer | `customer@example.com` | `demo123` |
| Staff | `staff@example.com` | `demo123` |
| Operator | `operator@example.com` | `demo123` |

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (normally `http://localhost:5173`). Set `VITE_API_BASE` if the API is not running at `http://localhost:8000`.

## Validation

The repository contains a Python `unittest` suite for the primary backend flow: login, packing request, automatic order creation, task start/completion, shipment, invalid transitions, and customer scoping. Price calculation, manual price override, weight updates, and full role-matrix coverage still need dedicated assertions.

```bash
backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow
```

The frontend production build can be checked with:

```bash
cd frontend
npm run build
```

## Current limitations

These limitations are intentional to keep the project honest as an MVP:

- No AI, LLM, OCR, prediction, optimization, or model evaluation code.
- No carrier API, tracking-number lifecycle, shipment-tracking events, warehouse inventory, payment, customs, or label generation.
- File uploads are demo files stored under `/tmp/tms_uploads`; there is no object storage, metadata table, preview URL, deletion flow, or cleanup policy.
- SQLite schema is initialized in application code; there are no migrations, ORM, connection pool, or production database configuration.
- Orders store parcel references as a JSON ID list rather than a normalized order-parcel join table.
- The service is a single FastAPI module without Docker, CI/CD, observability, rate limiting, or production secret management.
- The current frontend permission map and several visible actions need further alignment with the backend permission map before production use.
- The billing page's price-override history is stored in browser `localStorage`, not as a server-side audit trail.

## Planned next steps

The most valuable next improvements are:

1. Align frontend actions with backend permissions and establish a repeatable local validation environment.
2. Add dedicated tests for permissions, price calculation, manual overrides, and weight updates.
3. Normalize the order-to-parcel relationship and introduce database migrations.
4. Add shipment metadata, carrier events, exceptions, cancellation, and audit records.
5. Add task assignment, warehouse exception handling, and production file storage.
6. Only after a reliable logistics event model exists, add a measurable AI feature such as exception classification or an operations-assistant workflow.

## Portfolio framing

For an AI full-stack or logistics technology portfolio, this project is best described as:

> Built a full-stack Transportation Management System MVP with Vue 3, FastAPI, and SQLite, modeling parcel consolidation, warehouse packing tasks, role-based access, operational state transitions, and settlement workflows.

Do not describe it as an AI system, a production deployment, or an integrated carrier platform; those capabilities are not present in this repository.
