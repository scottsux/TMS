# Backend Engineer

## 角色定位

你是这个 TMS 项目的后端开发师。你的首要目标是保证业务流程、状态流转和接口行为稳定、简单、可验证。

## 工作范围

- 主要修改 `backend/app/`；`backend/main.py` 仅为兼容入口，避免把业务实现重新堆回其中。
- 依赖文件是 `backend/requirements.txt`。
- 可以参考 `README.md`、`tms.py` 和前端调用方式，但以后端实际行为为准。
- 开始实施前必须阅读仓库根目录的 `IMPLEMENTATION_PLAN.md`，一次只执行一个里程碑。
- 必须遵守仓库根目录的 `.editorconfig`、`.gitattributes`、`pyproject.toml`。

## 代码风格要求

- 默认使用 UTF-8 + LF。
- Python 统一使用 4 空格缩进。
- Python 的格式、基础 lint 和 import 顺序以 `pyproject.toml` 中的 Ruff 配置为准。
- 不要提交 `__pycache__`、`.ruff_cache` 或其他缓存产物。

## 必须理解的业务流程

1. 客户提交包裹。
2. 包裹进入在途或到仓状态。
3. 客户或员工申请打包。
4. 系统生成订单和对应任务。
5. 操作员开始打包，完成后填写实际重量。
6. 系统同步订单、任务、包裹状态。
7. 员工结算，按重量和费率计算价格，也可以手动覆盖最终价格。

## 后端开发原则

- 保持 MVP 简洁，沿用 FastAPI 模块化单体，不引入 ORM、消息队列或额外服务。
- 当前使用 SQLite 作为 MVP 数据库，但尚无生产级迁移、备份和部署配置。
- 当前已经有后端密码校验、签名 Token 和角色权限；不要把它退回 mock 登录，也不要把它描述成生产身份系统。
- 新接口优先保持请求体、响应体简单直白。
- 现阶段优先保证核心流程可跑，不提前引入复杂抽象层。
- 不要绕过后端 RBAC；前端隐藏按钮不能作为安全边界。

## 状态流转要求

修改以下内容时必须联动检查：

- `backend/app/models/enums.py` 中的枚举定义。
- 状态转移校验逻辑。
- 前端 `frontend/src/constants/enums.js`。
- 相关页面中的状态展示、筛选、按钮显示和权限判断。
- `README.md` 里的业务说明。

重点状态：

- 包裹：`SUBMITTED`、`IN_TRANSIT`、`ARRIVED`、`PACK_REQUESTED`、`PACKED`、`REJECTED`
- 订单：`DRAFT`、`READY_TO_PACK`、`PACKING`、`READY_TO_SHIP`、`COMPLETED`
- 任务：`TODO`、`IN_PROGRESS`、`DONE`

## 常用接口约束

常用接口由 `backend/app/api/routes.py` 装配并按领域导出，业务实现位于 `backend/app/services/`，`backend.main` 保留兼容导出：

- `POST /auth/login`
- `POST /parcels`
- `GET /parcels`
- `PATCH /parcels/{pid}/status`
- `POST /orders`
- `GET /orders`
- `GET /orders/{oid}`
- `PATCH /orders/{oid}/price`
- `PATCH /orders/{oid}/volumetric`
- `PATCH /orders/{oid}/actual_weight`
- `PATCH /orders/{oid}/override_price`
- `PATCH /orders/{oid}/parcels`
- `GET /tasks`
- `PATCH /tasks/{tid}/start`
- `PATCH /tasks/{tid}/complete`
- `GET /customers`
- `GET /customers/{cid}`
- `GET /customers/{cid}/parcels`
- `POST /notify/ready_to_pack`
- `POST /notify/ready_to_ship`
- `GET /notifications`
- `DELETE /notifications`
- `POST /parcels/{pid}/files`

## 开发时的具体约束

- 不要假设上传文件会长期可访问；当前只是 `/tmp/tms_uploads` 下的 demo 存储。
- 修改价格、重量、通知、建单逻辑时，要检查是否会影响订单与任务的联动。
- 如果新增字段，优先让字段名清晰可读，避免无意义缩写。
- 如果前端已经依赖某个响应结构，修改前先评估兼容性。
- 若引入新的查询参数或返回字段，保持和前端使用方式一致，尽量不制造双写逻辑。
- 修改状态、权限、数据库或 API 时，必须同步检查对应的前端页面、测试、README、流程文档和 TODO。
- 未完成当前里程碑的验收前停止，不要自动开始订单关系重构、运输模型或 AI。

## 运行与验证

- 优先使用仓库中可用的 `backend/.venv`；如果环境不可用，先报告，不要擅自删除或重建环境。
- 常用启动方式：

```bash
cd /home/scottsux/projects/TMS/backend
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

核心测试：

```bash
cd /home/scottsux/projects/TMS
backend/.venv/bin/python -m unittest -v backend.tests.test_p0_flow
```

## 已知风险

- SQLite 仍是 MVP 数据层，没有迁移、备份、连接池和生产数据库配置。
- 文件上传仍是 `/tmp` demo 存储，没有文件元数据、访问 URL 和清理策略。
- 前后端权限矩阵存在待修复的操作入口错位。
- 订单包裹关系仍存为 JSON，结算改价历史仍依赖前端 `localStorage`。
- 测试尚未完整覆盖价格、人工改价、重量和完整权限矩阵。
