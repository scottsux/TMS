# Logistics Agent Harness 接入对齐审计

## 2026-11-06 实施后状态修订

本节更新本文档此前记录的租户/仓库基线；以下内容优先于后文中“未找到租户/仓库隔离”的审计快照。此次实施仍未接入 Agent/Harness。

- `backend/app/db/schema.py::_migrate_tenant_warehouse_scope` 已为既有 SQLite 数据库增加并回填 `tenants`、`warehouses`，并对 customer/user 的 tenant 与 warehouse 关系安装 SQLite 触发器。旧数据迁移到 `Default Company` / `Default Warehouse`，不代表已识别出真实公司归属；上线前仍需管理员正确分配。
- 已确认的业务边界为：公司是 tenant，含多个 customer/warehouse；staff 看本公司全部客户，operator 仅看分配仓库。身份 token 增加 tenant/warehouse claims，后端 Service/Repository 查询范围和 API 权限测试已覆盖租户及仓库越权场景。证据：`backend/app/core/security.py`、`backend/app/services/`、`backend/app/repositories/`、`backend/tests/test_p0_flow.py::PermissionApiTests`。
- `backend/manage_scope.py` 提供仅本机使用的 `create-tenant`、`create-warehouse`、`assign-customer`、`assign-user` 管理命令；目前未找到对应 Web 管理界面或管理 API。该命令不是 Harness Tool，也不能作为 Agent 接入点。
- 数据隔离基础已落地，但尚非完整生产租户治理：未实现组织/仓库管理 API、审批人身份、通用 Action/Approval 持久化、幂等键、全域审计、Memory/Transcript 隔离与治理。后文对此类能力“未找到”的结论仍然有效；凡涉及 tenant/warehouse 字段和过滤的旧结论均以本节为准。
- 验证：`backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow`（31 项）；另验证 `backend/.venv/bin/python -m backend.manage_scope --help` 与 `git diff --check`。本次测试结果以实施完成汇报为准。

## 2026-11-06 受控只读接口实施状态

新增只读集成 API：`GET /integration/v1/parcels`、`GET /integration/v1/parcels/{pid}`、`GET /integration/v1/orders`、`GET /integration/v1/orders/{oid}`、`GET /integration/v1/exceptions`、`GET /integration/v1/exceptions/{eid}`。Router 位于 `backend/app/api/integration_read.py`，由 `backend/app/api/routes.py` 装配；使用现有 `parcel:view`、`order:view`、`exception:view` 权限依赖，并调用领域 Service。DTO 位于 `backend/app/schemas/integration_read.py`，不返回包裹备注/描述、customer 名称/ID、订单 forwarding/收件信息/价格、异常原因/解决备注或员工邮箱。

包裹与订单列表沿用已做 tenant/customer/warehouse 范围过滤的 Service；包裹详情使用 `parcel_service.get_parcel` 做对象级授权；异常详情使用 `exception_service.get_exception` 先校验异常所属订单范围。验收覆盖未认证 401、跨 tenant/warehouse 403、伪造 query scope 不改变身份范围、以及敏感字段白名单。验证命令 `backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow`，当前共 33 项通过。该 API 只读，不包含 Agent 运行时或写 Tool。

> 审计日期：2026-10-29
>
> 审计方式：只读检查当前仓库文档、后端、前端、SQLite schema 与现有测试；未修改业务代码、配置、数据库、依赖、API 行为或测试。
>
> 验证命令：`backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow`，结果为 22/22 通过。
>
> 结论口径：只有当前代码、schema、路由和测试能够证明的能力才记为“已有”；`ARCHITECTURE_ROADMAP.md`、`IMPLEMENTATION_PLAN.md`、`FLOWS_DIAGRAMS.md` 和 TODO 中的 M5–M13 均属于规划，不能当作实现。

## 1. 审计范围与仓库现状

### 1.1 当前用途与技术栈

当前仓库是一个集运仓库运营场景的 TMS MVP/demo，覆盖包裹提交、到仓、申请集运/打包、订单与打包任务、重量、内部“发货完成”、基础计价和订单异常。它不是生产 TMS，也没有 AI/LLM、真实承运商、运输轨迹、路线、合规规则引擎或支付能力。证据：`README.md` 的 “Implemented workflow”“Current limitations”；`agents/AGENTS.md` 的“通用项目背景”。

技术栈与入口如下：

| 层次 | 当前实现 | 入口/证据 |
| --- | --- | --- |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Fetch API | `frontend/src/main.js`；`frontend/src/router/index.js`；`frontend/src/api/client.js` |
| 后端 | FastAPI 模块化单体、Pydantic | 兼容入口 `backend/main.py`；应用装配 `backend/app/api/routes.py::app` |
| 后端分层 | Router → Service → Domain Repository → SQLite | `agents/AGENTS.md`；`README.md`；`backend/app/api/`、`services/`、`repositories/` |
| 数据库 | Python `sqlite3` + SQLite，启动时建表/seed，无 ORM/Alembic | `backend/app/db/connection.py::get_conn`；`backend/app/db/schema.py::init_db/seed` |
| 认证 | 邮箱/密码、PBKDF2、HMAC 签名 Bearer Token | `backend/app/services/auth_service.py::login`；`backend/app/core/security.py` |
| 启动 | Uvicorn 导入 `backend.main:app` | `README.md` 的 Run locally；`backend/main.py` |

`backend/main.py` 只保留 app 和兼容导出，真实业务实现位于 `backend/app/`。API Router 负责 HTTP 解析、`Depends` 认证/RBAC，Service 负责业务规则与事务编排，Repository 才允许执行领域 SQL。未来 Harness 不能把 Repository、`get_conn()` 或 ORM/SQLite 当作 Tool 接入点。

### 1.2 当前持久化与核心表

`backend/app/db/schema.py::init_db` 当前创建：`customers`、`users`、`parcels`、`orders`、`order_parcels`、`tasks`、`notifications`、`order_exceptions`、`order_audits`。未找到 `tenants`、`organizations`、`warehouses`、`shipments`、`shipment_events`、`routes`、`quotes`、`approvals`、`actions`、`idempotency_keys`、Memory 或 Run Transcript 表。

### 1.3 本次边界

本次只做接入前对齐审计，不实施 Harness、Agent Tool、Adapter、身份桥接、数据库迁移、审批、幂等、Shipment/Route/Quote 或任何 API 行为变更。唯一新增内容是本文档。

## 2. 用户、登录、角色与权限

### 2.1 用户实体、登录与 Token

- 用户实体是 SQLite `users(id, email, password_hash, role, customer_id)`；`customer_id` 可空。证据：`backend/app/db/schema.py::init_db`。
- 登录接口为 `POST /auth/login`，Router 调用 `auth_service.login`；密码用 PBKDF2-HMAC-SHA256 校验。证据：`backend/app/api/auth.py::login_route`；`backend/app/services/auth_service.py::login`；`backend/app/core/security.py::verify_password`。
- Token 是自定义 HMAC 签名 Bearer Token，不是服务端 Session，也不是标准 JWT 库实现。payload 包含 `sub`、`role`、`customer_id`、`exp`，默认 12 小时。证据：`backend/app/core/security.py::create_token/parse_token`；`backend/app/config.py::TOKEN_TTL_HOURS`。
- `get_current_user` 验证 Bearer Token 后，以 `sub` 重新查询当前用户；缺 Token、无效/过期 Token、用户不存在均返回 401。证据：`backend/app/core/security.py::get_current_user`；测试 `PermissionApiTests.test_missing_token_is_rejected`。
- Token secret 是代码内开发值 `tms-dev-secret`，认证仍是 demo 级。证据：`backend/app/config.py::TOKEN_SECRET`；`agents/AGENTS.md` 的“通用开发约定”。
- 前端将 token、role、user 放在 `localStorage`，统一在 `Authorization: Bearer ...` 中发送。证据：`frontend/src/stores/auth.js`；`frontend/src/api/client.js::request/upload`。

### 2.2 角色定义与角色管理

当前角色只有：`customer`、`staff`、`operator`。证据：`backend/app/models/enums.py::UserRole`。

`backend/app/db/schema.py::seed` 只在 demo seed 中创建三个账号。未找到用户注册、用户创建/编辑、角色注册、角色分配、角色管理 Router/API 或前端管理页面。角色不是数据库可配置的 role/permission 表，而是代码枚举和静态权限矩阵。

### 2.3 RBAC、Permission、依赖注入与 401/403

- 权限矩阵在 `backend/app/core/permissions.py::PERMISSIONS`；角色到 permission 的映射为代码常量。
- 路由通过 `Depends(require_permission("..."))` 认证并检查权限；无认证由 `get_current_user` 返回 401，已认证但无 permission 由 `require_permission` 返回 403。
- customer 的资源所有权边界由 `ensure_customer_scope(user, customer_id)` 实现；customer 访问其他 `customer_id` 返回 403。Service 列表查询还会把 customer 请求的过滤条件覆盖为 token 对应 `customer_id`。证据：`backend/app/core/permissions.py::ensure_customer_scope`；`parcel_service.list_parcels/parcels_by_customer`；`order_service.list_orders/get_order`；`exception_service.list_exceptions`。
- 现有测试实际覆盖：缺 Token 访问 `/orders` 返回 401；customer 访问 `/tasks`、staff 开始任务、operator 发货返回 403；customer 不能访问另一客户的订单/包裹。证据：`backend/tests/test_p0_flow.py::PermissionApiTests` 和 `BusinessRuleApiTests.test_customer_cannot_access_another_customers_order_or_parcel`；本次 22/22 通过。
- 当前未找到认证中间件；认证/RBAC 是 FastAPI dependency。CORS 允许任意 origin，属于 demo 配置。证据：`backend/app/api/routes.py`。

重要接入约束：大多数 Service 函数接收一个 `sqlite3.Row user`，但通用 permission 检查位于 Router dependency，而不是 Service 内。Harness 若在 Python 内直接构造 user row 并调用 Service，会绕过 `require_permission`。因此“复用 Service”必须置于一个由已验证 Token 建立的 Agent Facade/Router 后面，并显式执行 tool permission；不能把 Service 函数本身误认为完整授权边界。

### 2.4 前端隐藏与后端授权

- 前端 `frontend/src/stores/auth.js::PERMISSIONS/can` 复制后端 permission 名称；路由的 `meta.roles`、Navbar 和页面中的 `can(...)` 只负责隐藏页面或按钮。
- 例如 `Orders.vue` 仅在 `task:start` 时显示开始打包、仅在 `order:ship` 时显示发货；`OrderDetail.vue` 同样按 `task:complete`、`order:ship` 控制按钮。
- 真实安全边界仍是后端 Router 的 `Depends(require_permission(...))`，不能依赖隐藏按钮。证据：`FRONTEND_PAGE_FUNCTIONS.md` 开头说明；`frontend/src/stores/auth.js`；`backend/app/api/*.py`；上述 403 测试。

### 2.5 tenant / organization / warehouse / company 隔离

- 未找到 `tenant_id`、organization、company 字段或实体。
- `customer_id` 存在于 users、parcels、orders、notifications，并用于 customer 所有权过滤；它表示客户业务归属，不是经过定义的租户边界。
- `staff`、`operator` 的 `customer_id` 为 NULL，当前可以看到全局订单/包裹/任务/异常；未找到其所属 company/warehouse/tenant 范围。
- 未找到 Warehouse 实体、仓库 ID、仓库成员关系或仓库级数据隔离。当前 `tasks` 只是打包任务。
- 因此不能把 `customer_id` 直接等同于生产 `tenant_id`。若未来一个企业租户内包含多个 customer，二者语义明显不同；若 MVP 明确“一 customer 即一 tenant”，也必须由业务方确认并写成约束，而不是由 Agent 推断。

### 2.6 审计、操作人与审批人

- 已有订单审计表 `order_audits`：记录 `order_id`、可选 `exception_id`、`action`、`actor_id`、时间、before/after JSON、reason。证据：`backend/app/db/schema.py`；`backend/app/repositories/audit_repository.py::record/list_for_order`。
- 已审计的操作包括异常创建/解决、实际重/体积重更新、自动计价、人工改价。证据：`exception_service`、`billing_service`、`task_service.complete_task` 调用 `record_order_audit`；测试 `test_exception_type_permissions_and_resolution_audit`、`test_weight_and_price_rules_create_server_audits`。
- 异常表持久化 `created_by`、`resolved_by`，查询附带创建人/解决人 email。证据：`order_exceptions` schema；`exception_repository.list_for_order/list_all`。
- 未找到全域审计：创建包裹、建单、调整订单包裹、开始任务、发货、通知清理等操作没有统一审计记录。
- 未找到 approval 实体、审批请求、审批角色、审批人字段或审批 API。`resolved_by` 是异常解决操作人，不是审批人；不能把异常 `OPEN → RESOLVED` 说成审批流。

### 2.7 AgentContext 映射建议

| Harness 字段 | TMS 实际来源 | 证据 | 是否可直接复用 |
| --- | --- | --- | --- |
| `tenant_id` | 当前未找到。`customer_id` 只是 customer 数据归属；需新增正式 tenant，或经业务确认后定义临时映射 | `users.customer_id`、`parcels.customer_id`、`orders.customer_id`；无 tenant 表/字段 | 否 |
| `user_id` | Token `sub`，随后由 `get_current_user` 查询 `users.id` | `security.py::create_token/get_current_user`；`auth_repository.get_user_by_id` | 是，但必须来自已验证 Token，不能信任模型参数 |
| `roles` | 当前单角色 `users.role` / Token `role` | `models/enums.py::UserRole`；`users.role` | 部分可复用；Harness 的 roles 集合需适配为单角色或升级模型 |
| `permissions` | 服务端 `PERMISSIONS[UserRole]` 动态派生 | `core/permissions.py::PERMISSIONS/require_permission` | 是；必须服务端计算，不能信任 Tool 输入或前端副本 |
| `approver identity` | 当前未找到。未来可从审批请求处理时的已验证 `users.id/email` 获取，并要求专用 permission；不能默认任何 staff 都是审批人 | 当前只有 `order_exceptions.resolved_by`、`order_audits.actor_id`，无 approval/approver | 否 |

## 3. 真实物流领域能力清单

“Agent 可调用性”严格使用指定四种结论。所谓“可直接通过现有受控 Service 调用”仍须经过已认证的 Agent Facade/Router，复用后端 permission 与 scope 校验，不代表允许 Harness 直接 import Repository 或伪造 user row。

| 领域能力 | 已有实体/表 | Service 层 | Router/API | 前端页面 | 当前状态 | Agent 可调用性 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 订单 Order | `orders`、`order_parcels`；一个 parcel 受 `UNIQUE(parcel_id)` 约束 | `order_service`：创建、列表、详情、调整包裹、内部发货；`order_rules` | `POST/GET /orders`、`GET /orders/{oid}`、`PATCH /orders/{oid}/parcels`、`PATCH /orders/{oid}/ship` 等 | `/orders`、`/orders/:id` | 已实现集运/仓内履约订单；当前 `COMPLETED` 是内部发货完成，不是签收 | 可直接通过现有受控 Service 调用 | `schema.py`；`order_service.py`；`api/orders.py`；`Orders.vue/OrderDetail.vue` |
| 包裹 Parcel / Package | `parcels`，含 customer、tracking、品类、描述、仓内时间戳 | `parcel_service`；状态校验 `common.ensure_transition` | `POST/GET /parcels`、`GET /customers/{cid}/parcels`、`PATCH /parcels/{pid}/status`、文件上传 | `/upload`、`/parcels` | 已实现创建、列表、到仓/打包状态；没有单包详情 GET、尺寸/单包重量、合规事实 | 可直接通过现有受控 Service 调用 | `schema.py`；`parcel_service.py`；`api/parcels.py`；`Parcels.vue/Upload.vue` |
| 集运 Consolidation | `orders` + `order_parcels`；forwarding JSON 保存渠道、目的地、服务、收件人 | `notification_service.notify_ready_to_pack` 会选择 ARRIVED 包裹并创建/复用订单；`order_service.patch_order_parcels` | `POST /notify/ready_to_pack`、订单创建/调整 API | `/parcels` 申请打包；订单页调整包裹 | 只有确定性申请打包/成单；未找到方案生成、箱型优化、方案版本或 preview | 有 API 但缺少必要权限/幂等/审计 | `notification_service.py::notify_ready_to_pack`；`ReadyNotify`；`Parcels.vue` |
| 仓库 Warehouse | 未找到 warehouse 表；`tasks` 仅代表打包任务 | `task_service` 开始/完成打包 | `GET /tasks`、`PATCH /tasks/{tid}/start|complete` | `/tasks`、订单详情 | 有仓库作业流程，但无仓库实体、库位、仓库隔离、负责人/领取 | 有 API 但缺少必要权限/幂等/审计 | `schema.py::tasks`；`task_service.py`；`api/tasks.py`；`Tasks.vue` |
| 路线 Route | 未找到 | 未找到 | 未找到 | 未找到 | 规划在 M6，当前未实现 | 当前未实现 | `IMPLEMENTATION_PLAN.md` M6 明确 PLANNED；当前代码无 route 模块 |
| 运费 Quote | 无 quote/pricing_rule 表；订单只有 `final_price` | `order_rules.price_formula` 与 `billing_service.patch_order_price` 是完成订单结算写入 | `PATCH /orders/{oid}/price`、`override_price` | `/billing` | 有 `actual_weight × rate + extra_fee` 结算；不是只读 shipping quote，无路线/币种/时效/限制输入 | 当前未实现 | `order_rules.py::price_formula`；`billing_service.py`；`Billing.vue` |
| Shipment / 运单 | 未找到 shipments / shipment_events；parcel 仅有 `shipped_at` | 当前 `order_service.ship_order` 只把 Order 置 COMPLETED、Task 置 DONE、parcel 写 shipped_at | `PATCH /orders/{oid}/ship` | 订单页/详情“发货完成” | 真实 Shipment 未实现；M5 只是规划 | 当前未实现 | `schema.py`；`order_service.py::ship_order`；`README.md` Current limitations/M5 |
| Tracking / 轨迹 | 未找到事件表；parcel 的 tracking_number 是入库快递单号，不是运输事件流 | 未找到 | 未找到 | 未找到 Tracking 页面 | 未实现 | 当前未实现 | `schema.py::parcels`；`README.md` Current limitations |
| Exception / 异常 | `order_exceptions`、`order_audits` | `exception_service`：创建、列表、解决；`ensure_no_open_exceptions` 阻止发货/计价 | `/orders/{oid}/exceptions`、`GET /exceptions`、`PATCH /exceptions/{eid}/resolve`、audits | `/exceptions` | 已实现五类订单异常、`OPEN → RESOLVED`、角色类型约束和审计；无 SOP、严重度、补偿动作 | 可直接通过现有受控 Service 调用 | `models/enums.py::ExceptionType/Status`；`exception_service.py`；`api/exceptions.py` |
| 限制 Restriction / 敏感货 / 合规 | 只有异常枚举 `PROHIBITED` 与 parcel 文本品类/描述 | `exception_types_for_role` 允许 operator/staff 登记 PROHIBITED；不是规则判断 | 只能作为订单异常创建 | `/exceptions` | 未找到目的地/路线/货物限制规则、规则版本、判定结果；PROHIBITED 异常不能冒充合规引擎 | 当前未实现 | `models/enums.py::ExceptionType.PROHIBITED`；`order_rules.py::exception_types_for_role`；M6 仍 PLANNED |
| Action / Task / 待办 | `tasks(id, order_id, status, actual_weight)`；无通用 action 表 | `task_service.list/start/complete` | `/tasks`、`/tasks/{tid}/start|complete` | `/tasks` | 只有一订单一打包任务；无 owner/claim、优先级、截止时间、通用 Action payload、审批关联 | 有 API 但缺少必要权限/幂等/审计 | `schema.py::tasks`；`task_service.py`；`FRONTEND_PAGE_FUNCTIONS.md` 任务限制 |
| 审批 Approval | 未找到 | 未找到 | 未找到 | 未找到 | 当前未实现；异常解决与人工改价均是直接有权执行，不是先审批后执行 | 当前未实现 | 全仓 approval/approver 搜索无实现；M8/M11 仍 PLANNED |

## 4. Harness Tool → TMS 能力映射

### 4.1 映射表

| Harness Tool | 读/写/高风险 | 所需输入 | TMS 可复用 Service/API | 缺失能力 | 是否应审批 | 是否应幂等 | 实施建议 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `get_user_packages` | 读 | AgentContext 中 verified user/tenant；可选 status、分页 | `parcel_service.list_parcels` / `GET /parcels` | tenant；稳定 Tool DTO；按 permission/scope 的 Agent facade | 否 | 否 | 第一批开放；customer_id 必须由上下文推导，禁止模型指定他人 customer_id |
| `get_package_detail` | 读 | package/parcel id + verified context | 可复用 `get_parcel_or_404` 的逻辑，但当前没有受控 Service/`GET /parcels/{pid}` | 单包详情 Service/API；tenant/scope；最小化 PII 响应 | 否 | 否 | 新增薄 Service/API 后开放；不能直接调用 `parcel_repository.get_parcel_by_id` |
| `generate_consolidation_plan` | 读/规划 | parcel ids、目的地、服务偏好、包裹重量尺寸、限制 | 可复用订单-包裹关系校验思想；无可复用计划 Service/API | 单包 shipping facts、Route、Restriction、方案算法、版本/过期时间 | 否 | 对纯计算非必需；如持久化方案则是 | 等 M6/M7；输出只读 plan，不创建订单、不改变 parcel 状态 |
| `prepare_consolidation` | 写入前准备/高风险候选 | plan id/快照、parcel ids、forwarding/consignee、verified context | `notification_service.notify_ready_to_pack` / `POST /notify/ready_to_pack` 能真实建/复用订单并改状态 | preview 与 execute 分离；PII 脱敏；permission 精化；持久 Action/Approval；幂等；完整审计 | 准备本身否；真实执行是 | 是 | 不直接把现接口暴露给 Agent；先创建 Action 快照，确认后由 Service 一次执行 |
| `get_shipping_routes` | 读 | origin、destination、service、包裹事实、时间 | 未找到 | Route/Carrier/ServiceRoute 数据与 Service/API | 否 | 否 | 等 M6；路线由确定性目录返回，模型只比较/解释 |
| `check_shipping_restrictions` | 读/合规高影响 | route/destination、品类、重量尺寸、敏感货事实、规则版本 | 未找到；`PROHIBITED` 只是事后异常类型 | 限制规则、版本、证据、判定原因、人工复核标志 | 通常否；人工 override 是 | 对查询否；override 是 | 等 M6；fail-closed，规则不确定时返回需人工复核，模型不得自行放行 |
| `calculate_shipping_quote` | 读/确定性计算 | plan、route、计费重、币种、费率版本、附加费 | `price_formula` 仅可复用最简单算术，不等于报价；`PATCH /price` 是结算写操作 | 只读 Quote Service、币种、费率/路线/时效/限制、明细、有效期 | 否 | 查询通常否；若保存/接受报价则是 | 等 M7；新建纯计算接口，严禁调用结算 PATCH 冒充 quote |
| `get_shipment` | 读 | shipment id 或 order id + context | 未找到 | Shipment 实体、Service/API、scope | 否 | 否 | 等 M5 实装并验收；当前 `/orders/{oid}` 不能冒充 Shipment |
| `get_shipment_tracking` | 读 | shipment id + context | 未找到 | shipment_events、顺序、来源、Tracking API | 否 | 否 | 等 M5；只返回授权范围内事件和必要字段 |
| `prepare_shipment` | 写入前准备/高风险 | order id、route/carrier/service、收发信息、预期副作用 | 当前 `order_service.ship_order` 是旧语义的直接写，不能作为 Shipment prepare | Shipment、preview/action、approval、idempotency、审计、补偿 | 准备否；真实创建/出库是 | 是 | 不接当前 legacy `/ship`；完成 M5 后通过 Action/Approval 执行 Shipment 创建/出库 |
| `get_exception_detail` | 读 | exception id + context | 可通过订单异常列表组合；无单 exception 详情受控 API | 按 exception id 的 Service/API 与所属订单 scope 校验 | 否 | 否 | 新增 Service/API；禁止直接用 `exception_repository.get_by_id` |
| `search_exception_sop` | 读/RAG | exception type、场景、jurisdiction、语言 | 未找到 | SOP 文档源、版本、检索权限、引用与更新机制 | 否 | 否 | 作为独立知识检索 Tool；与业务 DB 查询分开，答案必须带来源/版本 |
| `prepare_exception_resolution` | 写入前准备/高风险候选 | exception id、建议、resolution note、证据、context | `exception_service.resolve_order_exception` 是可复用的最终业务 Service；现为直接执行 | preview/action、审批人、幂等、执行结果、失败状态、补偿/重开策略 | 准备否；解除 OPEN 阻断的真实执行是 | 是 | 推荐作为首个审批写闭环：Agent 只准备，staff/approver 批准后调用 Service |
| `create_action` | 写 | tenant/user/run、tool、目标、参数快照、风险级别 | 未找到 | Action 表/Repository/Service/API、状态机、TTL、敏感字段策略 | 否；高风险 Action 创建后进入待审批 | 是 | 新增持久化 action，使用 client request/idempotency key + 唯一约束 |
| `get_action` | 读 | action id + context | 未找到 | Action 读取与 owner/tenant/role scope | 否 | 否 | 只允许 action owner、授权 operator/approver 读取；响应脱敏 |
| `claim_action` | 写/并发敏感 | action id、operator identity、expected version | `tasks` 无 assignee/claim，不能复用 | owner、lease/version、并发 CAS、审计 | 视风险而定；领取本身通常否 | 是 | 用原子 compare-and-set，重复领取返回相同结果或明确冲突 |
| `complete_action` | 写/高风险 | action id、execution result、expected version、actor | 未找到；不能用 `tasks.complete` 代替通用 Action | 执行状态机、审批前置、幂等结果回放、失败/重试、业务引用 | 已标高风险时必须 | 是 | 只允许 APPROVED action；保存 result/error 和业务对象 ID，重复调用回放首个结果 |

### 4.2 接入点约束与真实写操作副作用

1. **不得直连 Repository/SQLite。** Repository 函数没有完整的 HTTP permission dependency，且是 SQL 持久层。Agent Tool 应调用受控 API，或调用一个显式完成认证、permission、scope、参数校验和审计的 Agent Application Service。
2. **只有 Router 也必须追到 Service。** 当前路由均较薄，真实副作用在 Service：
   - `notify_ready_to_pack`：写 notification；创建/复用 Order；写 order_parcels；把 Parcel 改为 PACK_REQUESTED。
   - `task_service.start_task`：Task TODO → IN_PROGRESS；Order → PACKING。
   - `task_service.complete_task`：写重量；Order → READY_TO_SHIP；Parcel → PACKED；写部分重量 audit。
   - `order_service.ship_order`：Order → COMPLETED；Task → DONE；Parcel 写 shipped_at。
   - `exception_service.resolve_order_exception`：Exception OPEN → RESOLVED；写 resolver、时间和 audit，并间接解除发货/计价阻断。
   - `billing_service.patch_order_price/override_price`：改 `final_price` 并写 audit。
3. **事务与回滚。** 上述 Service 多数在单 SQLite connection 中 `commit`，异常发生在 commit 前时由连接关闭回滚；但未找到跨请求 Saga/outbox 或已提交后的业务补偿 API。`order_repository.create_order_record` 自己执行 `commit`，它被 `notify_ready_to_pack` 调用时会使 Service 的完整流程不是严格单一事务边界；这是未来 Action 执行需要修正的原子性风险。
4. **已提交后的补偿现状。** 当前未找到订单撤销、Shipment 取消、异常重开、价格审批撤回或 Action 逆操作。接入真实写 Tool 前必须逐项定义“可逆/不可逆”：能回滚的提供显式补偿 Service；不能回滚的必须审批、幂等并提供人工修复流程，不能靠删除数据库记录。

## 5. 审批、幂等、审计与状态机

### 5.1 当前状态机与规则落点

| 对象 | 当前状态/流转 | 规则实现 | 审计现状 |
| --- | --- | --- | --- |
| Parcel | `IN_TRANSIT → ARRIVED → PACK_REQUESTED → PACKED`；另定义 SUBMITTED、REJECTED | `models/enums.py::ParcelStatus`；`repositories/common.py::ensure_transition`；部分批量推进在 Service 内 | 状态变化未统一审计 |
| Order | `DRAFT → READY_TO_PACK → PACKING → READY_TO_SHIP → COMPLETED` | `OrderStatus`；流转分散在 `notification_service`、`task_service`、`order_service` | 重量/价格审计；普通状态流转与 ship 未统一审计 |
| Task | `TODO → IN_PROGRESS`；完成打包后仍 IN_PROGRESS，ship 时 DONE | `TaskStatus`；`task_service.start_task/complete_task`；`order_service.ship_order` | 无 start/complete/ship 的统一 action audit |
| Exception | `OPEN → RESOLVED` | `ExceptionStatus`；`exception_service.resolve_order_exception` | 已记录 created_by/resolved_by 和 order_audits |

Parcel 有集中 `ensure_transition`；Order/Task 的状态前置条件分散在多个 Service。未来 Agent 写操作不能自行拼状态更新，必须复用/集中这些业务前置条件。

### 5.2 重复执行与幂等现状

全仓未找到 `request_id`、`idempotency_key`、幂等记录表、请求结果回放或基于唯一键的通用幂等组件。

当前行为不是生产幂等：

- 开始任务、完成任务、发货、解决异常的重复请求通常因状态不符返回 400；它们不会返回第一次成功结果。
- 重复创建异常会新增多条异常和 audit。
- 重复计价/改价/重量更新可重复写 audit。
- `notify_ready_to_pack` 的 notification 有 `(type, customer_id)` 唯一约束并 upsert，但它同时执行成单和状态更新；重试不保证返回第一次的 `order_id`，不能把 notification upsert 当作整个业务命令幂等。
- 订单与包裹的 `UNIQUE(parcel_id)` 防止同一包裹属于多个订单，这是业务不变量，不是 request idempotency。

对 Agent 所有写 Tool 应要求：`idempotency_key` 绑定 `tenant_id + user_id + tool_name + canonical_request_hash`，数据库唯一约束，保存首次状态/结果/业务对象 ID；相同 key 同参数回放首次结果，不同参数返回冲突。

### 5.3 角色建议

| 角色 | 适合动作 | 不应直接执行 |
| --- | --- | --- |
| customer | 查询自己的 parcel/order/exception；提出集运或异常处置请求；确认本人高风险请求 | 指定任意 customer_id；全局查询；自批高风险操作；直接改运输/结算状态 |
| operator | 查询授权工作；领取/执行低风险仓库 Action；补充重量/操作结果 | 批准自己的高风险 Action；跨 warehouse/tenant；改价、发货或解除合规阻断（除非单独授权） |
| approver | 审查 Action 快照、风险和证据；批准/拒绝；查看执行结果 | 修改 Agent 原始参数后无重新审批直接执行；批准自己发起且策略禁止自批的 Action |

当前 TMS 只有 customer/staff/operator，没有 approver 角色或 permission。最小方案可先增加 `action:approve` permission，并由业务确认授予特定 staff；不能仅凭 `staff` 名称默认其有审批权。

### 5.4 最小审批状态机

```text
PENDING → APPROVED → EXECUTED
        ↘ REJECTED

APPROVED → EXECUTION_FAILED（如真实 TMS 执行失败）
```

建议约束：

- `PENDING`：保存不可变 Tool 名、参数快照、目标对象、请求人、tenant、风险级别、业务版本和 idempotency key。
- `APPROVED`：保存 approver user_id、角色/permission 快照、批准时间和理由；批准后不得静默修改参数。
- `REJECTED`：保存拒绝人、时间、原因；不可执行；重新提交产生新 Action/Approval。
- `EXECUTED`：保存 executor、执行时间、业务对象 ID、结果摘要和 audit link。
- `EXECUTION_FAILED`：保存结构化错误、重试安全性与 attempts；只有同一 idempotency key 的安全重试才能继续，不能生成重复业务副作用。
- 状态更新使用版本号/CAS，防止两个审批人或执行器并发推进。

### 5.5 当前差距

- 没有 approvals/actions 表，因此 pending approval 重启后无法保留——不是“会丢”，而是当前根本没有 pending approval 概念。
- 没有 approver 身份/permission、发起人/审批人职责分离、拒绝记录、批准快照或执行结果状态。
- 没有通用幂等键与结果回放。
- 审计只覆盖订单部分动作，不覆盖所有高风险写操作；legacy ship 没有 order audit。
- 没有把业务对象版本/当前状态锁进 approval，批准后目标状态可能已变化。
- 没有明确补偿流程；执行失败只能依赖事务回滚，已提交后的纠正未建模。

## 6. 数据隔离与 Memory 接入边界

### 6.1 TMS 边界到 Harness 存储的映射

当前可确认的边界只有 `users.id` 和 customer 角色的 `customer_id`。生产接入前应先由业务确定 tenant 模型：

1. 推荐新增正式 `tenant_id`，让 users、customers、业务对象、Action、Approval、Transcript、Memory 都可追溯到同一 tenant。
2. `user_id` 始终取已验证 Token 的 `sub`；customer 资源范围继续由服务端关联推导。
3. 如果过渡期决定“一 customer 即一 tenant”，必须明确 staff/operator 如何归属 tenant/warehouse；当前全局 staff/operator 不能直接用于多租户生产。
4. Harness 存储的每次读写都必须同时带 tenant scope 和 user/role/permission snapshot；不能只用 `session_id` 隔离。

### 6.2 可进入 Memory 的内容

在有明确用途、用户可见/可删除、带来源和 TTL 的前提下，可保存：

- 用户明确表达的非敏感偏好，例如语言、单位、默认服务偏好；
- 稳定的业务引用与摘要，例如 `parcel_id/order_id/shipment_id/action_id`、最后已确认状态及来源时间；
- 用户确认过的工作流偏好，例如“报价优先时效/成本”，但不能代替每次业务规则校验；
- SOP 文档引用、版本和检索 provenance，而不是把整段受限文档长期复制进用户 Memory。

每次回答实时状态、路线、限制、价格、审批状态时必须重新调用 Tool；Memory 不能作为业务事实源。

### 6.3 绝不能进入长期 Memory 的内容

- 收件人姓名、详细地址、电话、邮箱、邮编；当前这些字段位于 `ReadyNotify` 和 orders/notifications 的 forwarding/payload JSON。
- 密码、password_hash、Bearer Token、Token secret、API key、Cookie 或其他凭据。
- 完整报价、费率表、支付/账单敏感明细；报价应按有效期实时重算或用业务 quote_id 引用。
- 完整临时 Tool 输出、原始数据库行、上传文件内容、未经脱敏的异常描述。
- 模型隐式推断的身份、角色、健康/财务等敏感属性。
- 可由业务系统实时取得的全量订单/包裹/轨迹快照。

Run Transcript 即使为排障保留，也应做字段级脱敏、访问控制、短 TTL，并与用户长期 Memory 分开。

### 6.4 建议隔离维度

| 存储 | 必需隔离/索引维度 | 额外要求 |
| --- | --- | --- |
| Action | `tenant_id + action_id`；owner `user_id`；target customer/order；run_id | permission snapshot、risk、immutable request、version、TTL、idempotency key |
| Approval | `tenant_id + approval_id/action_id`；requested_by；approved/rejected_by | approver permission、职责分离、理由、时间、决定后的不可变快照 |
| Run Transcript | `tenant_id + user_id + run_id` | tool 输入/输出脱敏、访问级别、保留期、trace id；不得当 Memory |
| Memory | `tenant_id + user_id + namespace` | provenance、consent、TTL、删除能力；共享团队记忆需独立 ACL |

### 6.5 现有数据治理能力

已有：customer 对自身订单/包裹/异常的服务端 scope；部分 actor 审计；SQLite 外键；订单-包裹唯一占用约束。

未找到：tenant/warehouse 隔离、行级安全、Memory/Transcript 治理、PII 分类/脱敏、保留期/删除策略、加密、密钥管理、结构化日志、trace/metrics、审批/Action 数据治理。`notifications.payload` 和 `orders.forwarding` 会存收件人 PII，但当前没有字段级访问/保留策略。

## 7. 最小可落地集成切片

### 7.1 第一阶段：只读客户查询

- **身份来源**：复用 `POST /auth/login` 的 Bearer Token；AgentContext 的 `user_id/role/customer_id` 只从 `get_current_user` 获取，permissions 由后端计算。
- **可开放 Tool**：先开放 `get_user_packages`、只读 `get_order`/订单列表；补一个受控的 `get_package_detail`。不开放 Repository、通知、任务或任何写接口。
- **必需 API/Service**：复用 `parcel_service.list_parcels`、`order_service.list_orders/get_order`；新增单 parcel detail 的 Service/API 或专用 Agent Facade；统一输出最小 DTO，去掉不必要的 PII。
- **验收条件**：无 Token 401；错误角色/权限 403；customer 无法用参数读取其他 customer；模型传入伪造 user/customer/role 被忽略；staff/operator 的可见范围有明确业务决定；Tool 不访问 DB；日志只记录脱敏参数；现有 22 个测试继续通过并新增 Agent scope 测试。

这是唯一建议下一轮立即实施的集成范围。若 tenant 语义尚未确认，只允许单租户/demo 环境验收，不应宣称多租户安全。

### 7.2 第二阶段：操作员创建 Action

- **需要的角色**：operator 可创建/领取指定类型 Action；customer 可创建本人请求；staff 是否可创建由 permission 决定。
- **持久化位置**：新增独立 `actions`（或 `agent_actions`）表及 Repository/Service/Router，不复用简单 `tasks` 表，不写 Harness Memory 代替业务记录。
- **审计字段**：tenant_id、action_id、tool/type、requested_by、owner/claimed_by、target type/id、参数摘要/哈希、risk、status、idempotency key、run/trace id、created/updated/executed timestamps、result/error、version。
- **验收条件**：重启后 Action 保留；跨 tenant/user 不可读；并发 claim 只有一个成功；重复 create/complete 回放同一结果；状态非法跳转拒绝；完整 actor audit。

### 7.3 第三阶段：高风险审批写操作

- **首个适合操作**：`prepare_exception_resolution → 审批 → exception_service.resolve_order_exception`。理由：当前已有真实持久化异常、明确 `OPEN → RESOLVED` 前置条件、staff permission、操作人和 audit；同时解决异常会解除发货/计价阻断，确实需要人工把关。不要把 legacy `/orders/{oid}/ship` 作为首个操作，因为 Shipment 尚未实现且 ship 缺少完整 Action/Approval/幂等审计。
- **幂等与审批**：Action 保存 exception id、当前 status/version、resolution note 和证据；具备 `action:approve` 的非发起人批准；执行时重新校验 OPEN、scope 和版本；相同 key 回放；结果保存 exception/audit id。
- **副作用与补偿**：成功后 Exception RESOLVED，订单可能重新允许发货/计价。当前没有 reopen；第一版应明确执行后只能由新建纠正异常或专门 reopen Service 补偿，不能删除历史记录。
- **验收条件**：PENDING 重启保留；拒绝不改异常；批准不等于已执行；执行成功变 EXECUTED 且只发生一次；Service 失败变 EXECUTION_FAILED 且异常保持原状态；批准后目标被其他人解决时安全失败；全链路 actor/approver/trace 可追踪。

## 8. 缺口矩阵与优先级

| 优先级 | 缺口 | 风险 | 影响范围 | 建议动作 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| P0 | 正式 `tenant_id`/组织/warehouse 边界未找到；staff/operator 当前全局 | 用户/租户数据串读，Memory/Action 串租户 | 所有读写 Tool、Memory、Transcript、Approval | 先确认租户模型；为身份与业务对象建立 tenant scope；增加跨租户 403 测试 | 业务确认“一 tenant 多 customer/warehouse”关系 |
| P0 | Service 直接调用不能自动复用 Router permission；Harness 可伪造 user row | 绕过 RBAC 和 customer scope | 所有 Tool | 建立认证后的 Agent Facade/API；Context 只由 Token 构造；每 Tool 显式 permission + resource scope | 现有 security/permissions；Tool contract |
| P0 | Approval/Action 持久化完全未实现 | 高风险写操作不可审批、重启丢流程、无法拒绝/追踪 | prepare/execute 类 Tool | 新增 actions/approvals 状态机、角色 permission、不可变快照、actor audit | tenant/user 身份模型 |
| P0 | 通用 idempotency/request result replay 未实现 | Agent 重试造成重复异常、重复审计或重复业务副作用 | 所有写 Tool | idempotency key + request hash + DB unique + 首次结果回放；并发测试 | Action persistence、事务边界 |
| P0 | 高风险写操作审计不完整；legacy ship 无 audit，任务/成单也不全 | 无法证明谁通过 Agent 改了什么 | 发货、成单、任务、订单关系、通知 | 建立 action audit 与业务 audit link；执行前后快照和 trace id | Action/Approval schema |
| P0 | Agent 若直连 Repository/SQLite 将绕过 Service 规则 | 越权、非法状态、部分提交 | 全部业务域 | 明文禁止并用架构/测试约束；Tool adapter 只能依赖 Facade/Service contract | 现有模块化分层 |
| P1 | Shipment/Tracking 未实现；当前 ship 是 legacy Order COMPLETED + shipped_at | Harness 运输 Tool 会返回虚假语义或写错状态 | shipment/tracking/prepare_shipment | 先完成并验收 M5，再映射 Shipment Tool | 已批准的 M5 设计 |
| P1 | Route/Restriction/Package shipping facts/Quote 未实现 | 模型可能臆造路线、限制与价格 | planning、restriction、quote | 按 M6/M7 建确定性 Service；Quote 只读、带版本/有效期 | M5 之后的业务里程碑 |
| P1 | `create_order_record` 内部 commit 破坏上层完整事务边界 | Action 中途失败可能形成部分持久化 | 集运 prepare/execute | commit 归 Service transaction boundary；增加故障注入原子性测试 | 不改变现有行为的事务重构设计 |
| P1 | Order/Task 状态规则分散；业务对象无 version/CAS | 批准后状态漂移、并发重复执行 | 任务、异常、未来 Shipment | 执行时重校验状态并加 version/expected state；集中命令前置条件 | Action/Approval |
| P1 | 单 parcel/单 exception 详情受控 API 缺失 | Tool 被诱导直调 Repository或过量列表 | read tools | 新增最小 detail Service/API 和 scope 测试 | 第一阶段 Facade |
| P1 | PII 位于 forwarding/notification JSON，无脱敏/保留策略 | Transcript/Memory 泄露地址电话邮箱 | Memory、Tracing、Tool response | DTO 最小化、日志脱敏、TTL/删除策略；Memory 禁存清单 | 数据治理决定 |
| P1 | approver 角色/permission 和职责分离未定义 | 自批或任意 staff 批准 | Approval | 增加 `action:approve` 等细粒度 permission；确认是否禁止自批 | 业务选择 |
| P2 | 自定义 Token、硬编码 secret、CORS `*`、无生产密钥管理 | 生产认证与部署风险 | 整体系统 | 接入生产身份/密钥配置前再上线；当前限定 demo | 部署与身份平台选择 |
| P2 | 无结构化日志、Trace/Metrics、Transcript 治理 | Agent 故障难诊断，成本/行为不可观测 | Harness 运行与运营 | 统一 trace/run/action id；脱敏结构化事件和指标 | 数据治理/观测方案 |
| P2 | SOP/RAG 数据源与版本未找到 | 异常建议无权威依据 | `search_exception_sop` | 建权威文档源、权限、版本、引用、评测 | 运营 SOP 提供方 |

## 9. 建议的下一步实施范围

下一轮只建议实施“第一阶段：只读客户查询的受控接入面”，不要同时实施 M5–M8、写 Action、审批、Memory 或前端 Agent UI。

### 9.1 预计修改/新增的模块

以下是建议范围，尚未执行：

- `backend/app/core/permissions.py`：增加只读 Agent Tool 所需的细粒度 permission（如业务决定沿用现有 `parcel:view/order:view`，则只补 Tool policy 映射，不扩大角色权限）。
- `backend/app/schemas/`：新增最小、去 PII 的 Tool/Agent 读取 DTO，或复用现有 Parcel/Order DTO 前先明确字段暴露。
- `backend/app/services/parcel_service.py`：新增受 scope 约束的单 parcel detail application service；继续通过 Repository 读取。
- `backend/app/services/order_service.py`：复用现有列表/详情，必要时增加专用只读 facade，不改状态逻辑。
- `backend/app/api/`：新增一个薄的受认证 Agent/Tool Router，或在现有 Router 增加缺失的 `GET /parcels/{pid}`；必须使用 `Depends(get_current_user/require_permission)`。
- `backend/app/api/routes.py`：只注册上述只读 Router（若选择新 Router）。
- `backend/tests/`：新增只读 Tool 接口测试。
- Harness 仓库的 TMS Adapter/Tool contracts：作为跨仓改动单独实施；仅调用 TMS API，不共享 SQLite、不 import TMS Repository。

### 9.2 明确不改

- 不改现有订单/包裹/任务/异常状态机和写 API 行为。
- 不实现 Shipment/Tracking、Route、Restriction、Quote、Action、Approval 或 Memory。
- 不改变 SQLite 为 PostgreSQL，不引入 ORM、Redis、消息队列或 LangGraph。
- 不改前端页面或新增聊天 UI。
- 不把 `customer_id` 擅自重命名为/等同于 `tenant_id`。
- 不开放 `POST/PATCH/DELETE` 给 Agent。

### 9.3 预计新增测试

1. Tool API 无 Token 返回 401。
2. 没有对应 permission 返回 403。
3. customer 只能读取自己的 parcel/order；传其他 customer_id 或其他资源 ID 返回 403。
4. Token 中的 user/role/customer 与请求 body/query 冲突时，以服务端身份为准。
5. staff/operator 的读取范围按已确认业务规则测试，不默认全租户。
6. detail 不泄露 address/phone/email/token/password_hash 等字段。
7. Adapter 使用 HTTP/API，静态检查或架构测试保证不 import Repository/`get_conn`。
8. 现有 `backend.tests.test_p0_flow` 22 个测试全部继续通过。

### 9.4 需要业务方确认的选择

1. **tenant 定义**：tenant 是 customer、company，还是一个 company 下包含多个 customer/warehouse？
2. **staff/operator 作用域**：全平台、tenant、warehouse，还是分配到具体客户/任务？
3. **只读第一阶段字段**：Agent 是否可以读取 item description/note/forwarding；哪些字段必须脱敏或完全不返回？
4. **Agent 身份模式**：严格用户委托（on-behalf-of user token）还是服务账号 + user delegation；推荐前者用于第一阶段。
5. **审批人模型**：未来由特定 staff、独立 approver 角色，还是基于 permission/金额/风险动态审批；是否禁止发起人自批？
6. **首个审批写操作**：是否接受“异常解决”作为首个闭环，还是业务上更希望选择集运确认；在 Shipment 未实现前不建议选择 legacy ship。

## 总结判断

当前仓库已经具备开始做**受控只读 PoC**的基础：真实 Bearer 身份、静态 RBAC、customer 数据 scope、清晰的 Router → Service → Repository 分层、可复用的 Parcel/Order/Exception Service，以及可运行的 401/403/状态/审计测试。

当前仓库**尚不具备直接接入完整 Harness 或开放真实写 Tool 的条件**。阻断项是：正式 tenant/组织边界未定义，Service 直调不能自动继承 Router permission，持久化 Action/Approval/幂等不存在，高风险写操作审计不完整，Shipment/Route/Restriction/Quote 仍未实现。建议先完成只读身份与 scope 接入面，再按 Action → Approval/Idempotency → 首个真实写操作递进。
