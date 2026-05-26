# Transportation Management System (TMS)

轻量级 Transportation Management System 原型，用于包裹转运、集运和打包结算流程。

项目目标：减少客户、员工和仓库操作员之间的人工协调，先把核心流程跑通，再逐步补强数据持久化、鉴权和测试。

## 当前状态

这是一个 MVP / demo 项目，当前实现特征如下：

- 后端为 FastAPI 单文件服务，入口是 `backend/main.py`
- 前端为 Vue 3 + Vite + Pinia + Vue Router
- 数据层目前使用内存字典，服务重启后数据会丢失
- 登录是本地 mock，不是正式鉴权方案
- 文件上传是 demo 实现，文件保存在 `/tmp/tms_uploads`

这意味着它适合演示业务流程、验证页面和接口联动，但不应被当作生产系统设计完成版。

## 业务角色

| 角色 | 职责 |
| --- | --- |
| `customer` | 提交包裹、查看包裹和订单状态、申请打包 |
| `staff` | 管理包裹、创建/调整订单、处理通知、更新重量和价格 |
| `operator` | 处理打包任务、填写实际重量、完成打包 |

## 核心业务流程

1. 客户提交包裹
2. 包裹进入在途状态
3. 仓库或员工标记包裹到仓
4. 客户选择已到仓包裹并提交打包申请
5. 系统自动生成或复用订单，并同步创建/使用打包任务
6. 操作员开始打包
7. 操作员填写实际重量并完成打包
8. 订单进入待发货，任务仍保持进行中
9. 员工完成发货并通知客户
10. 系统再同步订单、任务和包裹状态
11. 员工进行计价或人工覆盖最终价格

## 状态模型

### Parcel

当前后端使用的包裹状态如下：

```text
SUBMITTED -> IN_TRANSIT / REJECTED
IN_TRANSIT -> ARRIVED
ARRIVED -> PACK_REQUESTED / PACKED
PACK_REQUESTED -> PACKED
REJECTED -> terminal
PACKED -> terminal
```

说明：

- 当前 `POST /parcels` 创建后会直接进入 `IN_TRANSIT`
- `PACK_REQUESTED` 表示客户已申请打包
- 任务完成时，关联包裹会自动同步为 `PACKED`

### Order

```text
DRAFT -> READY_TO_PACK -> PACKING -> READY_TO_SHIP -> COMPLETED
```

说明：

- 客户提交打包申请后，系统会自动创建或复用订单
- 任务开始时，订单会同步为 `PACKING`
- 打包完成时，订单会同步为 `READY_TO_SHIP`
- 发货完成后，订单才会同步为 `COMPLETED`

### Task

```text
TODO -> IN_PROGRESS -> DONE
```

说明：

- 当前是 MVP 模型：一个订单对应一个任务

## 技术栈与入口

### 后端

- 框架：FastAPI
- 入口：`backend/main.py`
- 依赖：`backend/requirements.txt`
- 数据：内存字典
- 上传目录：`/tmp/tms_uploads`

### 前端

- 框架：Vue 3
- 构建工具：Vite
- 状态管理：Pinia
- 路由：Vue Router
- 入口：`frontend/src/main.js`
- 路由定义：`frontend/src/router/index.js`
- API client：`frontend/src/api/client.js`

### 其他

- `tms.py`：早期 CLI / JSON demo，可作为业务雏形参考，不是当前主线入口
- `agents/`：项目角色化 agent 约束文档

## 当前目录结构

```text
TMS/
├── .editorconfig
├── .gitattributes
├── .prettierrc.json
├── pyproject.toml
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── constants/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── views/
│   │   ├── App.vue
│   │   ├── main.js
│   │   └── style.css
│   ├── package.json
│   └── vite.config.*
├── agents/
├── todo/
├── tms.py
└── README.md
```

## 代码规范文件

仓库当前使用以下基础规范文件：

- `.editorconfig`
  - 统一 UTF-8、LF、结尾换行、去除多余尾随空格
  - 前端默认 2 空格缩进，Python 默认 4 空格缩进
- `.gitattributes`
  - 统一 Git 文本文件的 LF 换行行为
- `.prettierrc.json`
  - 统一前端的 JS / Vue / CSS / JSON 格式风格
- `pyproject.toml`
  - 统一 Python 的 Ruff lint / format 基础配置

开发时应默认遵守这些文件，而不是依赖个人编辑器默认设置。

## 已实现接口

以下接口基于当前 `backend/main.py` 实现。

### Auth

- `POST /auth/login`
  - demo 登录
  - 返回固定 token：`{"token": "jwt_token"}`

### Parcels

- `POST /parcels`
  - 创建包裹
  - 校验 `tracking_number` 唯一
  - 当前创建后初始状态为 `IN_TRANSIT`
- `GET /parcels`
  - 查询包裹列表
  - 支持 `customer_id`、`status`、`page`、`page_size`
- `PATCH /parcels/{pid}/status`
  - 更新包裹状态
  - 按当前状态机校验合法流转
- `POST /parcels/{pid}/files`
  - 上传包裹图片
  - 最多 5 张
  - 单张最大 5MB
  - 仅支持 `png` / `jpeg` / `webp`

### Orders

- `POST /orders`
  - 创建订单
  - 同步创建一个 `TODO` 状态任务
- `POST /orders/auto`
  - 根据客户与允许状态自动收集可用包裹并建单
- `GET /orders`
  - 查询订单列表
  - 支持 `customer_id`、`status`、`page`、`page_size`
- `GET /orders/{oid}`
  - 查询订单详情
- `PATCH /orders/{oid}/price`
  - 按 `actual_weight * rate_per_kg + extra_fee` 计算最终价格
- `PATCH /orders/{oid}/volumetric`
  - 更新体积重量
- `PATCH /orders/{oid}/actual_weight`
  - 更新实际重量
- `PATCH /orders/{oid}/override_price`
  - 人工覆盖最终价格
- `PATCH /orders/{oid}/parcels`
  - 调整订单中的包裹
- `PATCH /orders/{oid}/order_no`
  - 更新订单号

### Tasks

- `GET /tasks`
  - 查询任务列表
  - 支持 `order_id`
- `PATCH /tasks/{tid}/start`
  - 开始任务
  - 同步订单状态为 `PACKING`
- `PATCH /tasks/{tid}/complete`
  - 完成打包
  - 可携带 `actual_weight`
  - 同步订单状态为 `READY_TO_SHIP`
  - 任务保持 `IN_PROGRESS`
  - 同步订单关联包裹状态为 `PACKED`
- `PATCH /orders/{oid}/ship`
  - 完成发货
  - 同步订单状态为 `COMPLETED`
  - 同步关联任务状态为 `DONE`

### Notifications

- `POST /notify/ready_to_pack`
  - 客户申请打包通知
  - 可能自动生成或复用订单
  - 会写入转运信息和收件信息快照
- `POST /notify/ready_to_ship`
  - 打包完成待发货通知
- `POST /notify/shipped`
  - 发货完成通知客户
- `GET /notifications`
  - 查询通知
  - 支持 `type`、`customer_id`
- `DELETE /notifications`
  - 清空通知
  - 支持按 `type` 清空

### Customers

- `GET /customers`
  - 查询客户列表
  - 支持 `page`、`page_size`、`q`
- `GET /customers/{cid}`
  - 查询客户详情
- `GET /customers/{cid}/parcels`
  - 查询客户包裹
  - 支持 `status`

## 价格规则

系统当前的自动计价规则：

```text
final_price = actual_weight * rate_per_kg + extra_fee
```

规则说明：

- 重量单位为 `kg`
- 结果保留 2 位小数
- 员工可以人工覆盖 `final_price`

## 文件上传规则

- 每个包裹最多上传 5 张图片
- 单张图片最大 5MB
- 仅支持 `jpg / jpeg / png / webp`
- 当前保存目录：`/tmp/tms_uploads/{parcel_id}/`
- 暂未提供正式文件访问 URL、鉴权和清理机制

## 前端页面

当前主要页面位于 `frontend/src/views`：

- `Login.vue`
  - 本地 mock 角色登录
- `Dashboard.vue`
  - 当前仍偏静态概览，后续建议改成角色化工作台
- `Upload.vue`
  - 提交包裹并上传图片
- `Parcels.vue`
  - 包裹列表、状态推进、打包申请、通知查看
- `Orders.vue`
  - 订单列表、筛选、开始打包、调整包裹
- `OrderDetail.vue`
  - 订单详情、实际重量、体积重量、打包完成与通知
- `Tasks.vue`
  - 真实任务看板，接入 `/tasks`
- `Billing.vue`
  - 结算页，围绕待结算订单、计价和人工覆盖
- `Customers.vue`
  - 客户列表
- `CustomerDetail.vue`
  - 客户详情与关联订单

## 权限说明

当前前端主要通过 `frontend/src/stores/auth.js` 中的本地角色和 permission map 控制按钮和页面展示。

这只是 demo 级 UI 控制，不是服务端安全鉴权。

## 本地开发

### 后端

项目后端固定使用 Conda 环境：

```bash
/home/scottsux/miniconda3/envs/python312/bin/python
```

安装依赖并启动：

```bash
cd backend
/home/scottsux/miniconda3/envs/python312/bin/python -m pip install -r requirements.txt
/home/scottsux/miniconda3/envs/python312/bin/python -m uvicorn main:app --reload --port 8000
```

Windows PowerShell 可通过 WSL 启动：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /home/scottsux/TMS/backend && source /home/scottsux/miniconda3/bin/activate python312 && uvicorn main:app --reload --port 8000"
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认前端 API 地址来自 `frontend/src/api/client.js`：

- 优先读取 `VITE_API_BASE`
- 未设置时默认使用 `http://localhost:8000`

### 生产构建检查

```bash
cd frontend
npm run build
```

### 可选的本地格式检查工具

如果本地已安装对应工具，可以按以下规范文件执行格式检查：

```bash
# 前端格式化
prettier --check "frontend/src/**/*.{js,vue,css,json}"

# Python lint / format
ruff check backend
ruff format backend
```

## 示例请求

### 创建包裹

```json
{
  "customer_id": 1,
  "tracking_number": "SF123",
  "courier_company": "SF",
  "item_category": "cosmetics",
  "item_description": "lipstick",
  "note": "liquid"
}
```

### 自动计价

```json
{
  "actual_weight": 2.5,
  "rate_per_kg": 50,
  "extra_fee": 10
}
```

### 提交打包申请

```json
{
  "customer_id": 1,
  "parcel_ids": [1, 2],
  "channel": "air",
  "destination": "UK",
  "service": "express",
  "consignee_name": "John Smith",
  "consignee_state": "England",
  "consignee_city": "London",
  "consignee_address": "221B Baker Street",
  "consignee_phone": "07123456789",
  "consignee_email": "john@example.com",
  "consignee_postcode": "NW16XE"
}
```

## 开发约定

- 保持 MVP 简洁，优先延续当前单文件后端和现有 Vue 页面结构
- 不要假设数据已持久化；重启后内存数据会清空
- 不要把 mock 登录误当成正式鉴权
- 修改业务流程时，要同步检查前后端状态枚举和页面展示
- 新增接口时，尽量让前端继续通过 `frontend/src/api/client.js` 访问
- 编辑中文内容统一使用 UTF-8，避免扩大乱码范围
- 默认遵守仓库中的 `.editorconfig`、`.gitattributes`、`.prettierrc.json`、`pyproject.toml`
- 前端默认 2 空格缩进，Python 默认 4 空格缩进
- 避免无关格式化和大规模重构

## 已知限制与后续方向

- 尚未接入真实数据库
- 尚未实现服务端鉴权、用户模型、密码校验、JWT 校验
- `README` 与代码未来仍可能继续演进，需要以实现为准
- `Dashboard.vue` 目前仍偏静态，后续应改为按角色的真实工作台
- 文件上传缺少文件名清理、重复文件处理、访问地址和生产存储方案
- 测试覆盖较少，后续接数据库或拆模块前应优先补测试

## 相关文档

- `agents/AGENTS.md`：项目级 agent 总说明
- `agents/backend-engineer.md`：后端开发师约束
- `agents/frontend-engineer.md`：前端开发师约束
- `todo/frontend-ui-style-todo.md`：前端 UI 优化待办
