# Transportation Management System (TMS) – Development Specification

---

## 1. Project Overview

A lightweight web-based system for parcel forwarding and consolidation.

Goal: reduce manual coordination between customer, staff, and warehouse operator.

---

## 2. Roles

| Role     | Description                             |
| -------- | --------------------------------------- |
| customer | submits parcels, views status           |
| staff    | reviews, creates orders, manages system |
| operator | handles packing tasks                   |

---

## 3. Core Workflow

1. Customer submits parcel
2. Staff reviews parcel
3. Parcel arrives warehouse
4. Staff creates order
5. Operator packs
6. System calculates price

---

## 4. State Transition Rules

### Parcel

```
SUBMITTED -> APPROVED / REJECTED
APPROVED -> ARRIVED
ARRIVED -> PACKED
REJECTED -> (terminal)
```

### Order

```
DRAFT -> READY_TO_PACK -> PACKING -> COMPLETED
```

### Task

```
TODO -> IN_PROGRESS -> DONE
```

---

## 5. Permission Matrix

| Action                       | customer | staff | operator |
| ---------------------------- | -------- | ----- | -------- |
| create parcel                | yes      | yes   | no       |
| edit parcel (before approve) | yes      | yes   | no       |
| approve parcel               | no       | yes   | no       |
| mark arrived                 | no       | yes   | no       |
| create order                 | no       | yes   | no       |
| assign task                  | no       | yes   | no       |
| start task                   | no       | no    | yes      |
| complete task                | no       | no    | yes      |
| update price                 | no       | yes   | no       |

---

## 6. Database Constraints

### General

* all `id` fields: primary key
* all timestamps: auto-generated

### Parcel

* `tracking_number`: UNIQUE
* `customer_id`: FK -> Customer.id
* `status`: ENUM
* cannot belong to multiple active orders

### Order

* `customer_id`: FK
* `status`: ENUM
* `actual_weight >= 0`

### OrderParcel

* unique(order_id, parcel_id)

### Task

* `order_id`: FK
* one order -> one task (MVP)

---

## 7. API Specification

### Auth

#### POST /auth/login

Request:

```
{
  "email": "test@test.com",
  "password": "123456"
}
```

Response:

```
{
  "token": "jwt_token"
}
```

---

### Parcel

#### POST /parcels

```
{
  "customer_id": 1,
  "tracking_number": "SF123",
  "courier_company": "SF",
  "item_category": "cosmetics",
  "item_description": "lipstick",
  "note": "liquid"
}
```

Response:

```
{
  "id": 1,
  "status": "SUBMITTED"
}
```

#### PATCH /parcels/{id}/status

```
{
  "status": "APPROVED"
}
```

---

### Order

#### POST /orders

```
{
  "customer_id": 1,
  "parcel_ids": [1,2,3]
}
```

#### PATCH /orders/{id}/price

```
{
  "actual_weight": 2.5,
  "rate_per_kg": 50,
  "extra_fee": 10
}
```

Response:

```
{
  "final_price": 135
}
```

---

### Task

#### PATCH /tasks/{id}/start

#### PATCH /tasks/{id}/complete

```
{
  "actual_weight": 2.5
}
```

---

## 8. Pricing Rules

```
final_price = actual_weight * rate_per_kg + extra_fee
```

Rules:

* weight unit: kg
* round to 2 decimal places
* staff can override final_price

---

## 9. File Upload Rules

* max size: 5MB
* formats: jpg/png/webp
* max 5 images per parcel
* stored path: /uploads/{parcel_id}/

---

## 10. Frontend Pages

* Login Page
* Customer List
* Customer Detail
* Parcel List
* Parcel Create
* Order List
* Order Detail
* Task Board

---

## 11. Local Development Setup

### Backend

```
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Dev notes
- CORS 已开启（允许任意源），前端可直接请求 `http://localhost:8000`。
- 当前为内存存储（演示用），重启会清空；后续接数据库再替换。
- 已实现 README 中的核心接口：
  - `POST /auth/login` 返回 `{"token": "jwt_token"}`
  - `POST /parcels` 创建包裹（校验 tracking 唯一，初始状态 SUBMITTED）
  - `PATCH /parcels/{id}/status` 状态流转（按 SUBMITTED→APPROVED/REJECTED→ARRIVED→PACKED）
  - `POST /orders` 创建订单（同步创建一条 TODO 任务）
  - `PATCH /orders/{id}/price` 返回 `final_price`（两位小数）
  - `PATCH /tasks/{id}/start`、`/complete`（complete 可带 `actual_weight`，会同步订单状态/实重）
  - 便于前端调试的列表/详情：`GET /parcels`、`GET /orders`、`GET /orders/{id}`


### Frontend

```
cd frontend
npm install
npm run dev
```

### Database

```
alembic upgrade head
```

---

## 12. Folder Structure

```
tms/
├── backend/
│   ├── app/
│   ├── models/
│   ├── routes/
│   └── main.py
├── frontend/
└── README.md
```

---

## 13. Development Order

1. auth
2. customer
3. parcel
4. order
5. task
6. pricing
7. upload

---

## 14. Notes

* keep MVP simple
* no over-engineering
* prioritize working workflow

---

## 15. Summary

This document defines:

* system behavior
* API contract
* database rules
* development workflow

Ready for implementation.
