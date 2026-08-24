# AGENTS.md

## 说明

本目录存放 TMS 项目的角色化 agent 约束文档。当前拆分为：

- `backend-engineer.md`：后端开发师，负责 FastAPI、状态流转、接口和业务规则。
- `frontend-engineer.md`：前端开发师，负责 Vue 页面、后台工作台体验、表格表单和视觉一致性。

当前前端默认视觉方向：

- 优先采用“订单页式后台页面”结构
- 优先是“标题 + 浅指标卡 + 工具条 + 表格”
- 避免把仪表盘或列表页做成卡片墙或营销式工作台

## 通用项目背景

这是一个轻量级 Transportation Management System (TMS) 原型，用于包裹转运、集运和打包结算流程。系统目标是减少客户、员工和仓库操作员之间的人工协调。

主要角色：

- `customer`：提交包裹、查看包裹和订单状态、申请打包。
- `staff`：审核和管理包裹、创建订单、处理通知、更新重量和价格。
- `operator`：处理打包任务、填写实际重量、完成打包。

当前项目是 MVP/demo 状态：优先保证核心流程可跑，避免过早引入复杂抽象。

实施任务必须先阅读仓库根目录的 `IMPLEMENTATION_PLAN.md`。默认一次只执行一个里程碑；完成验收后停止并报告，不得自动进入下一阶段。

## 技术栈与入口

后端：

- FastAPI 模块化单体服务，兼容入口是 `backend/main.py`；应用模块位于 `backend/app/`。
- 依赖在 `backend/requirements.txt`。
- 当前使用 SQLite 作为 MVP 数据库；迁移、生产数据库和完整审计仍属于后续工作。
- 文件上传 demo 存储目录是 `/tmp/tms_uploads`。

前端：

- Vue 3 + Vite + Pinia + Vue Router。
- 入口是 `frontend/src/main.js`。
- 路由定义在 `frontend/src/router/index.js`。
- API client 在 `frontend/src/api/client.js`。
- 页面主要放在 `frontend/src/views`。

其他：

- `tms.py` 是早期 CLI/JSON demo，可作为业务雏形参考，不是当前主线应用入口。
- `README.md` 是产品和接口规格说明，但部分实际代码已经比 README 多。

## 核心业务流程

1. 客户提交包裹。
2. 包裹进入在途或到仓状态。
3. 客户或员工申请打包。
4. 系统生成订单和对应任务。
5. 操作员开始打包，完成后填写实际重量。
6. 系统同步订单、任务、包裹状态。
7. 员工结算，按重量和费率计算价格，也可以手动覆盖最终价格。

主要状态：

- 包裹：`SUBMITTED`、`IN_TRANSIT`、`ARRIVED`、`PACK_REQUESTED`、`PACKED`、`REJECTED`。
- 订单：`DRAFT`、`READY_TO_PACK`、`PACKING`、`READY_TO_SHIP`、`COMPLETED`。
- 任务：`TODO`、`IN_PROGRESS`、`DONE`。

修改状态相关逻辑时，需要同步检查：

- 后端 `backend/app/models/enums.py`、`backend/app/services/` 和路由中的状态流转。
- 前端 `frontend/src/constants/enums.js`。
- 相关页面中的按钮、筛选、状态展示和权限判断。
- `README.md` 中的业务说明。

## 通用开发约定

- 保持 MVP 简洁，延续现有 FastAPI 模块化单体和 Vue 页面结构，避免无职责边界的碎片文件。
- 不要把 SQLite MVP 持久化误认为生产级数据库；当前仍缺少迁移、备份和生产配置。
- 当前登录已包含后端密码校验和签名 Token，但仍是演示级认证，不是生产身份系统。
- 修改业务流程时，同时检查前后端状态枚举、路由页面、权限判断和 README。
- 新增接口时，尽量保持请求/响应结构简单，并让前端通过 `frontend/src/api/client.js` 访问。
- 图片上传当前只是 demo 存储，不包含真实对象存储、鉴权、访问 URL 或清理机制。
- 现有中文文本有乱码迹象，后续编辑统一使用 UTF-8，尽量不要扩大乱码范围。
- 避免无关格式化和大规模重构，尤其不要顺手改 `node_modules`、`dist` 或生成物。

## 仓库规范文件

仓库内以下规范文件属于默认必须遵守的工程约束：

- `.editorconfig`
- `.gitattributes`
- `.prettierrc.json`
- `pyproject.toml`

执行要求：

- 文本文件统一使用 UTF-8 + LF。
- 前端代码默认使用 2 空格缩进。
- Python 代码默认使用 4 空格缩进。
- 前端格式化风格以 Prettier 配置为准。
- Python 格式和 import 顺序以 Ruff 配置为准。
- 不要提交 `frontend/dist`、`frontend/node_modules`、`.ruff_cache` 等生成物或缓存目录。

## 本地运行

Python 环境：

- 优先使用仓库中可用的项目环境 `backend/.venv`；如果不可用，先报告环境问题，不要擅自删除或重建环境。

后端：

```bash
cd backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端格式规范文件：

```bash
./.prettierrc.json
```

Python / Ruff 规范文件：

```bash
./pyproject.toml
```

默认前端 API 地址来自 `frontend/src/api/client.js`：

- `VITE_API_BASE` 环境变量。
- 未设置时使用 `http://localhost:8000`。
