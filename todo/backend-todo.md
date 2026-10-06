# TMS TODO List

## 2026-08-24 代码审查新增问题

### P0 - 当前功能阻塞

- [x] 统一前后端权限矩阵
  - 已对齐 `backend/main.py` 与 `frontend/src/stores/auth.js` 的权限名称和角色能力；后端仍是最终安全边界。
  - 已按 `task:start`、`order:ship`、`order:update` 修复订单列表的高风险操作按钮。
  - 已将订单详情页“发货完成”权限修正为 `order:ship`。
  - 已为员工补齐 `task:view`，仪表盘仅在有权限时请求 `/tasks`。
  - 已补充各角色的接口级 401/403 覆盖；关键前端操作已按权限映射收敛。

- [x] 建立可重复的本地开发与验证环境
  - 使用 `backend/.venv` 运行后端测试和 Uvicorn。
  - WSL 使用用户级 nvm 提供 Linux Node.js/npm；构建前执行 `source ~/.nvm/nvm.sh` 和 `nvm use --lts`，避免调用 Windows npm shim。
  - README、`MANUAL_TEST_PLAN.md`、`agents/AGENTS.md` 与实际启动/验证命令已同步。

### P1 - 核心业务模型缺口

- [x] 规范订单与包裹关系
  - 已新增 `order_parcels` 关系表；`UNIQUE(parcel_id)` 保证一个包裹同时只能属于一个订单。
  - 已实现旧 `orders.parcel_ids` JSON 的初始化迁移与双写兼容，API 响应保持 `parcel_ids`。
  - 已实现同客户添加、移除即释放、重新分配、跨客户/重复/已占用拒绝和关系约束测试。
  - 拆单与合单仍属于后续订单业务规则，不在本里程碑实现。

- [x] 补充订单异常记录
  - 已提供客户取消、地址错误、破损、违禁品、价格争议五类异常，以及 `OPEN -> RESOLVED` 处理记录。
  - 未解决异常会阻止发货和价格操作，但不改变订单状态机；取消、挂起、退款状态仍属于后续业务规则。

- [ ] M5：Shipment + Tracking（设计已确认，尚未开始）
  - `Order` 继续表示集运/仓库履约订单；`Order.COMPLETED` 表示仓库履约完成且已创建对应 Shipment，不表示签收或运输完成。
  - 新增 `shipments`、`shipment_events` 及对应 Repository、Service、Router、Schema、Tracking 查询和基本前端展示。
  - MVP 约束一个 Order 对应一个 Shipment；暂不支持多箱、拆单或多 Shipment。
  - Shipment 状态为 `READY_FOR_DISPATCH -> DISPATCHED -> IN_TRANSIT -> OUT_FOR_DELIVERY -> DELIVERED`。
  - 创建 Shipment 必须原子校验 `READY_TO_SHIP` 和无 `OPEN` exception，并写入 Shipment、`SHIPMENT_CREATED` event、Order `COMPLETED`、Task `DONE`；此时不写 Package `shipped_at`。
  - 仅在 Shipment 进入 `DISPATCHED` 时写入 `DISPATCHED` event 和关联 Package `shipped_at`；Package 不增加运输状态。
  - 仅模拟顺序运输事件；覆盖中转、延误、海关/运输异常，拒绝重复和倒序事件；不接真实承运商或处理乱序外部事件。

- [ ] 完善任务分配和仓库作业
  - 增加任务负责人、优先级、截止时间、开始/完成时间和备注。
  - 支持任务领取或分配给具体操作员。
  - 增加打包照片、装箱记录和异常上报。
  - 评估多箱、多任务和复核流程，不再默认一订单只有一个简单任务。

- [x] 完善结算和改价审计
  - 已保存自动计价、人工改价、实际重/体积重更新和异常处理的操作人、时间、前值、后值与原因/说明。
  - 已将改价历史从前端 `localStorage` 改为服务端审计读取；币种、付款状态、发票和审批仍属于后续范围。

- [x] Milestone 4.5：模块化单体重构
  - 已将 `backend/main.py` 收敛为兼容入口，保持既有 FastAPI app 与测试直接调用对象可导入。
  - 4.5A：已建立领域 FastAPI Router，Router 负责 HTTP 参数、依赖、RBAC 和响应适配，Service 负责业务流程。
  - 4.5B：已按领域拆分 auth、customer、parcel、order、task、exception、billing、notification、audit Repository；Service 不再直接执行领域 SQL。
  - 4.5C：已统一根目录启动命令，确认 WSL/Linux Node/npm 验证方式，并同步 README、实施计划、手动测试计划和 Agent 约束。
  - API 路径、SQLite 表结构、状态规则和前端调用方式均未改动；未引入 PostgreSQL、ORM、Alembic、消息队列、运输模型或 AI。
  - 已通过后端 unittest、`python -m compileall`、Linux Node 下的 `npm run build` 和 `git diff --check`；Milestone 4.5 完整验收完成。

### P2 - 运营功能和生产化

- [ ] 完善客户和包裹管理页面
  - 支持创建、编辑客户。
  - 支持包裹编辑、图片预览、图片删除和批量状态操作。
  - 支持按运单号、客户、状态搜索及分页。

- [ ] 生产化文件上传
  - 建立文件元数据表。
  - 清理并规范文件名，避免路径穿越和同名覆盖。
  - 提供带权限校验的预览/下载 URL。
  - 支持删除、重复文件处理和存储清理策略。

- [ ] 增加平台工程能力
  - 使用环境变量配置 Token Secret、数据库路径和上传目录。
  - 增加数据库迁移、统一错误响应、结构化日志和健康检查。
  - 增加 Docker、CI、限流和基础监控配置。

### P3 - 可验证的 AI 能力

- [ ] 先实现一个可测量的 AI 功能
  - 优先选择物流异常分类，输出异常类型、严重程度和是否需要人工审核。
  - 为 AI 功能建立样例集、准确率/召回率、人工复核率和失败兜底指标。

- [ ] 增加受控物流运营助手
  - 支持查询订单、包裹、任务和物流事件。
  - AI 只能调用有权限控制的后端工具/API，不能直接访问数据库。
  - 记录提示词、工具调用、响应和失败原因。

- [ ] 再考虑自然语言查价和预测模型
  - 自然语言只负责提取结构化参数，价格仍由确定性计价服务计算。
  - 延误预测需要先积累运输事件数据，再建立可验证的数据集和离线评估。

## P0 - 先把项目地基补稳

- [x] 锁定当前真实业务状态流转
  - 以当前代码和前端已跑通流程为准，不再沿用旧版状态机草案。
  - 确认包裹实际流程：创建后默认 `IN_TRANSIT`，再进入 `ARRIVED`、`PACK_REQUESTED`、`PACKED`，保留 `SUBMITTED` 和 `REJECTED` 作为扩展状态。
  - 确认订单实际流程：`DRAFT`、`READY_TO_PACK`、`PACKING`、`READY_TO_SHIP`、`COMPLETED`。
  - 确认任务实际流程：`TODO`、`IN_PROGRESS`、`DONE`，其中“打包完成待发货”阶段任务仍保持 `IN_PROGRESS`。
  - 联动检查 `backend/main.py`、`frontend/src/constants/enums.js`、相关页面按钮/筛选/展示，以及 `README.md`。
  - 补充明确的状态转移约束，避免数据库接入后再返工。

- [x] 接入真实数据库
  - 选择 SQLite 或 PostgreSQL 作为第一版持久化方案。
  - 第一版已落地 SQLite，继续保持 FastAPI 单文件结构，未额外引入 ORM。
  - 建立 users、customers、parcels、orders、tasks、notifications 等表。
  - 为 orders 持久化当前已在接口中使用的 forwarding/consignee 快照。
  - 明确 parcel、order、task、notification 之间的关联关系和删除策略。
  - 当前上传文件仍保留 `/tmp` 存储，元数据建模放到后续生产化阶段。
  - 第一版先用代码内 schema bootstrap 替换内存字典，后续如需多环境迁移再补 Alembic。

- [x] 加真实认证和后端权限控制
  - 建立用户模型和角色字段。
  - 实现密码校验和登录。
  - 实现签名 token 的签发与校验。
  - 在后端接口中按 customer、staff、operator 做权限检查。
  - 保留前端权限控制作为 UI 辅助，但不把它当安全边界。

## P1 - 补全核心业务能力

- [ ] 完善客户管理
  - 支持创建客户。
  - 支持编辑客户基础信息。
  - 支持客户搜索、分页和详情信息补全。

- [ ] 完善包裹管理
  - 支持包裹编辑。
  - 支持包裹图片预览。
  - 支持按单号、客户、状态搜索。
  - 支持批量状态操作。
  - 明确包裹被订单占用后的释放和重新分配规则。

- [ ] 完善订单流程
  - 定义订单号生成规则。
  - 正式建模转运渠道、目的地、服务类型和收件人信息。
  - 支持订单取消、拆单、合单或重新分配包裹。
  - 明确订单完成后哪些字段允许修改。

- [ ] 完善任务看板
  - 支持任务分配给具体操作员。
  - 支持任务备注和异常记录。
  - 支持打包图片或附件。
  - 考虑是否从“一订单一任务”扩展为多任务。

- [x] 补最小后端测试闭环
  - [x] 覆盖核心链路：提交打包申请、自动建单/复用订单、开始任务、完成打包、发货完成。
  - [x] 覆盖状态转移非法场景：重复开始任务、未开始直接完成、未到 `READY_TO_SHIP` 直接发货。
  - [x] 覆盖客户数据隔离和基本权限拒绝。
  - [x] 已增加价格计算断言。
  - [x] 已增加人工改价断言。
  - [x] 已增加实际重量和体积重量接口断言。
  - [x] 测试在数据库和权限改造后持续可跑；当前覆盖价格、重量、上传边界、角色权限、非法状态转换、订单包裹关系、异常及审计。

- [ ] 完善结算能力
  - 明确价格计算公式和币种。
  - 保存计价明细：实际重、体积重、单价、额外费用、覆盖价格原因。
  - 区分自动计算价和人工覆盖价。
  - 补充结算状态和付款状态。

## P2 - 生产化与体验优化

- [ ] 生产化文件上传
  - 清理和规范上传文件名。
  - 为上传图片提供可访问 URL。
  - 支持删除图片。
  - 支持重复文件处理。
  - 决定使用本地静态目录还是对象存储。

- [ ] 增加测试覆盖
  - 在最小后端测试闭环基础上继续补全更多接口和边界场景。
  - [x] 权限测试：不同角色访问不同接口。
  - [x] 文件上传测试：类型、大小、数量限制。
  - [ ] 前端关键流程验证：登录、提交包裹、申请打包、完成任务、结算。

- [x] 拆分后端结构
  - 已在 Milestone 4.5 完成模块化单体拆分，当前边界为 API Router -> Service -> Domain Repository -> SQLite。
  - `backend/main.py` 仅保留兼容入口和导出，API、业务规则、领域 SQL 已分别归位。
  - API 行为保持兼容，后续只在新增业务领域时按现有边界扩展。

- [ ] 优化前端工程结构
  - 提取常用状态标签、表格、表单和确认弹窗组件。
  - 为 API 调用增加统一错误提示和 loading 状态。
  - 梳理移动端布局和长文本显示。

- [x] 更新项目文档
  - 已同步 `README.md`、`IMPLEMENTATION_PLAN.md`、`MANUAL_TEST_PLAN.md`、`agents/AGENTS.md` 和本 TODO 的实际模块边界与启动命令。
  - 已记录 Python、Linux Node/npm、后端测试和前端构建的验证方式。
  - 已保留未实现的 Shipment、Route、Quote、AI 和 Agent 为后续规划，没有写成已完成功能。

## 已确认后续里程碑（均未开始）

1. M5：Shipment + Tracking。
2. M6：Route + Restriction + Package Shipping Facts。
3. M7：Consolidation Planning + Deterministic Quote。
4. M8：Safe Action / Tool-ready Contract。
5. M9：Read-only Logistics Agent。
6. M10：Planning Agent。
7. M11：Human-approved Action Agent。
8. M12：Exception Agent。
9. M13：Agent Evaluation。

任何里程碑都必须在获得单独确认后才可开始；在 M5 完成并验收前，不得实现 M6 或任何 Agent 能力。
