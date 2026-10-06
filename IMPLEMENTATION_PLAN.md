# TMS 分阶段实施计划

本文是给 Codex Agent 或其他代码 Agent 的执行说明。它把 [todo/backend-todo.md](todo/backend-todo.md) 和 [ARCHITECTURE_ROADMAP.md](ARCHITECTURE_ROADMAP.md) 转换为可执行的小里程碑。

## 0. 总体目标和边界

目标是把当前集运仓库 MVP 逐步发展成一个有可靠业务闭环、可追踪运输事件、可审计结算、并能安全接入 AI 的 TMS。

当前项目的真实基础是：

```text
Vue 3 + Vite + Pinia
        ↓
FastAPI 单体 REST API + 后端 RBAC
        ↓
SQLite + 包裹/订单/任务/通知表
```

Agent 必须遵守：

1. 一次只执行一个里程碑。
2. 未通过当前里程碑验收前，不得开始下一个里程碑。
3. 不得为了“看起来更企业级”直接改成微服务、Java 或引入 Agent。
4. 不得把规划功能写成已实现功能。
5. 修改状态、权限或数据库时，必须同步检查后端、前端、测试、README、流程文档和 TODO。
6. 不得删除用户已有改动、重置工作区或大范围格式化。
7. 每个里程碑只修改完成该里程碑所需的文件。
8. 如果发现需求与现有代码冲突，先停止并报告冲突，不要自行选择新业务规则。

## 1. Agent 每次开始前的固定检查

执行任何修改前：

1. 读取本文件和相关 TODO。
2. 运行 `git status --short`，记录已有修改，避免覆盖。
3. 阅读仓库内适用的 `AGENTS.md`。
4. 检查目标文件当前内容，不依赖旧摘要。
5. 明确本次只处理哪个里程碑和哪些文件。
6. 先写出“本次不做什么”，再开始编辑。

每次结束时必须报告：

- 修改了哪些文件。
- 完成了哪些验收条件。
- 运行了哪些测试和结果。
- 哪些测试因环境原因未运行。
- 是否发现新的需求或数据模型冲突。
- 下一里程碑是什么，但不要自动执行它。

## 2. 统一验收命令

后端环境可用时：

```bash
backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow
```

如果项目环境改为其他 Python 环境，Agent 必须在报告中写明实际解释器路径。

前端环境可用时：

```bash
source ~/.nvm/nvm.sh
nvm use --lts
cd frontend
npm run build
```

文档和代码修改后至少执行：

```bash
git diff --check
```

## 3. Milestone 0：建立可重复的验证基线

### 目标

让后端测试和前端构建可以在当前 WSL 环境中重复运行，先解决验证能力，不修改业务逻辑。

### 允许修改

- `backend/requirements.txt`
- `frontend/package.json` 或锁文件（只有确实需要时）
- README 和 `MANUAL_TEST_PLAN.md` 中的运行命令
- 环境说明文件

### 小步骤

1. 检查 Python、pip、Node.js、npm 的实际路径和版本。
2. 确认 `backend/.venv` 是否可用；不可用时不得擅自删除或重建已有环境。
3. 安装缺失依赖前先报告需要安装什么。
4. 运行后端测试。
5. 运行前端构建。
6. 只修正与环境/命令直接相关的问题。

### 不做

- 不修改权限逻辑。
- 不修改数据库结构。
- 不修改页面设计。
- 不升级无关依赖。

### 完成条件

- 后端测试命令可以运行并得到明确结果。
- 前端构建命令可以运行并得到明确结果。
- README、手动测试计划和实际命令一致。

完成后停止，等待下一步指令。

## 4. Milestone 1：修复前后端权限和操作入口

### 目标

让页面显示的动作和后端真正允许的动作一致，优先修复当前确定存在的 403 和错误按钮。

### 允许修改

- `backend/main.py` 的权限矩阵和必要的权限测试
- `frontend/src/stores/auth.js`
- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Orders.vue`
- `frontend/src/views/OrderDetail.vue`
- 相关路由或通知页面
- `backend/tests/`

### 固定权限基线

| 动作 | customer | staff | operator |
|---|---:|---:|---:|
| 创建自己的包裹 | ✓ | ✓ | — |
| 查看任务 | — | ✓ | ✓ |
| 开始打包任务 | — | — | ✓ |
| 完成打包任务 | — | — | ✓ |
| 确认发货 | — | ✓ | — |
| 计算/覆盖价格 | — | ✓ | — |

如果要改变这张表，必须先说明业务理由，并同步修改 TODO 和文档。

### 小步骤

1. 将前端 permission map 对齐后端权限名称。
2. 修复订单列表的“开始打包”按钮，只给有 `task:start` 权限的角色显示。
3. 修复订单列表的“发货完成”按钮，只给有 `order:ship` 权限的角色显示。
4. 修复订单详情页发货按钮使用错误权限的问题。
5. 修复员工仪表盘请求任务时的权限问题；若员工确实需要查看任务，增加后端 `task:view` 并测试。
6. 增加每个角色至少一个允许和一个拒绝的接口测试。
7. 手动检查客户、员工、操作员的导航和关键按钮。

### 完成条件

- 页面不再向无权限角色显示对应高风险动作。
- 后端仍然是安全边界，前端隐藏按钮不能替代后端检查。
- 角色接口测试通过。
- 原有 P0 流程测试通过。

完成后停止，不得顺手修改数据库结构或 UI 风格。

## 5. Milestone 2：补齐业务规则测试

### 目标

把目前只覆盖主链路的测试扩展到价格、重量、权限和文件边界；不改变业务规则本身。

### 允许修改

- `backend/tests/`
- 只有测试发现明确 bug 时，才修改对应的 `backend/main.py` 小范围逻辑

### 小步骤

1. 测试价格公式：重量、单价、额外费用和两位小数。
2. 测试负数重量、负数价格和非法输入。
3. 测试人工改价成功、非员工拒绝和负数拒绝。
4. 测试实际重量和体积重量保存后可读取。
5. 测试文件数量、类型和 5MB 大小限制。
6. 测试客户只能访问自己的订单和包裹。
7. 测试非法状态转换。

### 完成条件

- 测试明确覆盖 TODO 中列出的价格、改价、重量和文件边界。
- 测试失败时先修复原因，不通过删除断言来“通过测试”。
- 测试结果可重复。

完成后停止。不要在这个里程碑引入 PostgreSQL、ORM 或 AI。

## 6. Milestone 3：规范订单与包裹关系

### 目标

用关系表替代 `orders.parcel_ids` JSON，同时保持现有 API 行为尽可能兼容。

### 允许修改

- `backend/main.py` 或后续拆分出的数据库/模型文件
- 数据库迁移文件
- 订单相关测试
- `frontend/src/views/Orders.vue`
- `frontend/src/views/OrderDetail.vue`
- README、流程文档和 TODO

### 小步骤

1. 先记录当前 `parcel_ids` 的读写位置和 API 响应格式。
2. 设计 `order_parcels(order_id, parcel_id, ...)` 表，并说明唯一约束。
3. 写迁移或兼容初始化逻辑，不直接删除旧列。
4. 先实现读路径，再实现新订单写路径。
5. 增加同客户、跨客户、已占用包裹和重复包裹测试。
6. 实现添加、移除和释放规则。
7. 确认旧前端仍能读取订单详情。
8. 只有迁移和回归测试通过后，才考虑移除旧 JSON 字段。

### 完成条件

- 订单与包裹关系可查询、添加、移除和约束。
- 不允许跨客户或重复占用包裹。
- 现有核心链路和前端构建通过。
- 文档明确新的数据模型。

完成后停止，不得同时实现拆单、合单、运输或 AI。

## 7. Milestone 4：订单异常和结算审计

### 目标

先让订单和价格在真实运营中可解释、可追溯，再扩展运输。

### 小步骤 A：订单异常

1. 列出需要支持的异常：客户取消、地址错误、破损、违禁品、价格争议。
2. 为每个异常确定状态、触发角色、允许动作和结束条件。
3. 增加异常记录表或等价模型，不要只增加一个无来源的枚举。
4. 增加员工处理页面和接口测试。

### 小步骤 B：结算审计

1. 建模计价明细、币种、自动价格、最终价格和付款状态。
2. 保存改价原因、操作人和时间。
3. 将前端 `localStorage` 记录改为服务端读取。
4. 增加员工权限、重复改价和已完成订单修改规则。
5. 更新 Billing 页面和用户可见的费用摘要。

### 完成条件

- 每次价格变化可以追溯到操作人和原因。
- 异常订单有记录、有处理状态和有审计结果。
- 计价和改价测试通过。

完成后停止，不得把付款接入或发票系统假设为已完成。

## 8. Milestone 4.5：模块化单体重构

### 当前状态

**COMPLETE（最终验收：2026-10-06）**。4.5A 已完成 API Router 与 Service
分离，4.5B 已完成领域 SQL 向 Repository 下沉，4.5C 已完成启动方式、Linux
Node/npm 验证环境和文档同步。当前实际边界为：

```text
FastAPI Router -> Service -> Domain Repository -> SQLite
```

后端测试、`compileall`、前端 production build 和 `git diff --check` 均已通过。
本里程碑没有新增 Shipment、Route、Quote、AI 或 Agent 功能；下一阶段仍需单独
确认后才能开始。

### 适用时机

Milestone 4 的异常处理和服务端审计核心完成后、Milestone 5 的运输模型开始前执行。当前 `backend/main.py` 已同时包含应用配置、数据库、模型、认证、权限、异常、审计、订单、任务和文件上传逻辑，继续堆叠会增加回归风险。

### 目标

在不改变现有业务规则和外部行为的前提下，把后端从单文件整理为模块化单体。此次重构只改变代码组织，不新增运输功能、不切换数据库、不引入 AI。

### 必须保持不变

- API 路径、HTTP 方法和请求/响应 JSON 结构。
- 当前订单、包裹、任务、异常和审计状态规则。
- SQLite 表结构和现有数据兼容性。
- `backend.main` 的测试导入兼容性，或在同一里程碑内完成等价测试迁移。
- 前端页面和 `frontend/src/api/client.js` 的调用方式。

### 目标目录

```text
backend/
├── main.py                    # 兼容入口；创建 app 或导出兼容对象
└── app/
    ├── config.py              # 配置和环境变量
    ├── db/
    │   ├── connection.py      # SQLite 连接
    │   └── schema.py          # 建表、seed、现有迁移
    ├── core/
    │   ├── security.py        # 密码、Token、当前用户
    │   ├── permissions.py     # RBAC
    │   └── errors.py           # 统一错误辅助函数
    ├── models/
    │   └── enums.py           # 状态、角色、异常类型
    ├── schemas/               # Pydantic 请求/响应模型
    ├── repositories/          # 按领域组织的 SQL 查询和持久化
    ├── services/              # 业务规则和跨表流程
    └── api/                   # FastAPI 路由
```

### 小步骤

1. 运行现有后端测试并保存基线结果；如果环境不可用，先报告，不修改业务逻辑。
2. 记录当前 API、公开函数、模型和数据库表，尤其是 `backend.tests.test_p0_flow` 直接调用的对象。
3. 抽出配置、数据库连接和 schema 初始化，不改变调用结果。
4. 抽出枚举和 Pydantic schemas。
5. 抽出密码、Token、当前用户和权限检查。
6. 抽出 repository；只移动 SQL，不同时优化 SQL 或改变字段。
7. 按领域抽出 parcel、order、task、exception、billing/audit services。
8. 将路由函数变成薄适配层，只负责请求解析、权限依赖、调用 service 和返回响应。
9. 保留 `backend.main` 的兼容导出，或同步更新测试并保证相同业务覆盖。
10. 按领域拆分测试，但保留原有核心流程回归测试。
11. 更新 README、流程文档、Agent 文档和文件路径说明。

### 不做

- 不引入 PostgreSQL、SQLAlchemy、Alembic 或消息队列。
- 不新增 `shipment`、预测、RAG、Agent 或外部承运商接口。
- 不修改数据库表结构。
- 不顺手重写前端或统一格式化整个仓库。
- 不为了减少 `main.py` 行数而制造没有职责边界的碎片文件。

### 完成条件

- `main.py` 不再承载全部业务实现，只保留入口和必要兼容导出。
- 所有当前 API 的路径、响应和权限行为保持一致。
- 现有流程、异常、审计和权限测试通过。
- 前端构建通过。
- `git diff --check` 通过。
- 文档和目录结构反映实际代码。

完成后停止，等待确认后再开始 Milestone 5。

## 9. Milestone 5：Shipment + Tracking

### 当前状态

**PLANNED（M5.0 设计已确认，尚未开始实现）**。本里程碑只建立确定性的出库与运输事实层；不实现 Route、Restriction、Quote、AI 或 Agent。

### 目标和状态语义

- `Order` 继续表示集运/仓库履约订单。
- `Order.COMPLETED` 固定表示：**仓库履约完成，并已经创建对应 Shipment**。它不表示承运商已签收、运输完成或妥投。
- Shipment 单独表达运输状态：`READY_FOR_DISPATCH -> DISPATCHED -> IN_TRANSIT -> OUT_FOR_DELIVERY -> DELIVERED`。
- Package 不增加运输状态，继续表达入仓和打包流程；只有 Shipment 进入 `DISPATCHED` 时，才为关联 Package 写入 `shipped_at`。
- MVP 固定为一个 Order 对应一个 Shipment，不支持多箱、拆单或多 Shipment。

### 必须实现

1. 新增 `shipments`、`shipment_events`，以及 Shipment Repository、Service、Router 和 Pydantic Schema；不改变现有模块化单体边界。
2. Shipment 至少记录订单、承运商、服务、转运单号、起点、目的地、状态、预计送达时间和创建/更新时间；Shipment Event 至少记录类型、地点、描述、发生时间和来源。
3. 创建 Shipment 必须在一个 Service 事务中完成：
   - 校验 Order 为 `READY_TO_SHIP`；
   - 校验不存在 `OPEN` exception；
   - 创建 Shipment 和 `SHIPMENT_CREATED` event；
   - Order 转为 `COMPLETED`；
   - Task 转为 `DONE`；
   - 不写 Package `shipped_at`。
4. Shipment 进入 `DISPATCHED` 时，在同一事务中推进 Shipment 状态、写入 `DISPATCHED` event，并为关联 Package 写入 `shipped_at`。
5. 支持 Tracking 查询、事件列表和仅用于演示的模拟运输事件；事件至少覆盖创建、出库、运输中、中转到达、派送、签收、延误、海关/运输异常。
6. 为 Shipment 读取和模拟事件写入增加 RBAC、客户数据隔离、状态跳转、事件顺序和重复事件测试。
7. 增加基本前端 Tracking 展示及订单详情入口。

### 事件规则

- `SHIPMENT_CREATED` 由创建流程写入；`ARRIVED_AT_HUB` 只记录轨迹，不改变 `IN_TRANSIT` 状态。
- `DELAYED`、`CUSTOMS_HOLD`、`TRANSPORT_EXCEPTION` 在 M5 中作为事件记录，不自动创建新的订单异常或自动处理动作。
- M5 只接受顺序追加的模拟事件；重复事件和倒序事件必须拒绝，`DELIVERED` 为终态。
- 真实承运商事件、Webhook、外部事件 ID 和乱序事件重放不属于 M5。

### 不做

- 不实现 Route、Restriction、Quote、Consolidation Planning、Agent 或 Tool Calling。
- 不接真实承运商，不把模拟事件表述为承运商集成。
- 不实现多 Shipment、多箱、复杂拆单、真实运输异常自动处置。
- 不处理乱序真实承运商事件，不引入消息队列、Redis、PostgreSQL 或微服务。

### 完成条件

- Order 完成、Shipment 出库和 Shipment 签收有唯一且不冲突的状态归属。
- 一个 Order 只能创建一个 Shipment；所有创建和状态联动保持原子性。
- 模拟 Tracking 在前端可查询和展示，事件有时间顺序和来源。
- 现有流程回归测试及新增 Shipment 测试通过；前端构建、`compileall`、`git diff --check` 通过。

完成后停止，等待下一里程碑确认。

## 10. Milestone 6：Route + Restriction + Package Shipping Facts

**PLANNED，尚未开始。** 建立确定性的路线目录、货物/目的地/重量尺寸限制判断，并补齐报价所需的 Package 单包重量、尺寸或体积等 shipping facts 及稳定读取接口。不得实现 Quote、Agent 或真实承运商接入。

## 11. Milestone 7：Consolidation Planning + Deterministic Quote

**PLANNED，尚未开始。** 提供只读的合箱方案、计费重、费用明细、路线比较和预计时效；价格和限制必须由确定性 Service 计算，不能由模型生成或写入业务数据。

## 12. Milestone 8：Safe Action / Tool-ready Contract

**PLANNED，尚未开始。** 为未来写操作建立 `Plan/Preview -> User Confirmation -> Execute` 边界，并加入用户身份、权限、幂等、动作快照、执行审计和重复执行保护；此里程碑本身不实现 Agent。

## 13. Milestone 9：Read-only Logistics Agent

**PLANNED，尚未开始。** Agent 只能通过受 RBAC 保护的后端读取包裹、订单、Shipment 和 Tracking，不能直接访问数据库或执行写操作。

## 14. Milestone 10：Planning Agent

**PLANNED，尚未开始。** Agent 调用确定性的 Route、Restriction、Consolidation Planning 和 Quote 能力，输出预算、时效和风险比较建议。

## 15. Milestone 11：Human-approved Action Agent

**PLANNED，尚未开始。** Agent 只能生成动作预览；只有产品内的明确用户确认才能通过 Safe Action Layer 执行一次业务动作。

## 16. Milestone 12：Exception Agent

**PLANNED，尚未开始。** 读取异常和 SOP，生成处置建议；高风险动作仍须经过人工确认和安全动作层。

## 17. Milestone 13：Agent Evaluation

**PLANNED，尚未开始。** 建立场景集与安全评估，包括工具调用成功率、参数错误、权限绕过、确认正确率、成本和人工接管率。

## 18. 禁止的捷径

- 不把 `localStorage` 数据当作服务端审计记录。
- 不把大模型输出直接写入订单价格或状态。
- 不让 Agent 直接访问数据库。
- 不为了展示技术栈而无业务需要引入 LangChain、LangGraph、Neo4j 或多模型。
- 不把 SQLite 改成 PostgreSQL 后就声称完成了生产化。
- 不把模拟运输事件写成真实承运商接入。
- 不把未完成的规划模块写入“Features implemented”。
- 不删除失败测试、放宽断言或修改测试数据来掩盖行为变化。

## 19. 里程碑完成报告模板

```text
里程碑：M__
目标：

本次修改文件：
- 

已完成的小步骤：
- 

验收结果：
- 后端测试：通过 / 失败 / 未运行（原因）
- 前端构建：通过 / 失败 / 未运行（原因）
- git diff --check：通过 / 失败

未完成事项：
- 

发现的风险或业务决策：
- 

下一里程碑（仅说明，不执行）：M__
```
