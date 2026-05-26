# AGENTS.md

## 说明

本目录存放 TMS 项目的角色化 agent 约束文档。当前拆分为：

- `backend-engineer.md`：后端开发师，负责 FastAPI、状态流转、接口和业务规则。
- `frontend-engineer.md`：前端开发师，负责 Vue 页面、后台工作台体验、表格表单和视觉一致性。

## 通用项目背景

这是一个轻量级 Transportation Management System (TMS) 原型，用于包裹转运、集运和打包结算流程。系统目标是减少客户、员工和仓库操作员之间的人工协调。

主要角色：

- `customer`：提交包裹、查看包裹和订单状态、申请打包。
- `staff`：审核和管理包裹、创建订单、处理通知、更新重量和价格。
- `operator`：处理打包任务、填写实际重量、完成打包。

当前项目是 MVP/demo 状态：优先保证核心流程可跑，避免过早引入复杂抽象。

## 技术栈与入口

后端：

- FastAPI 单文件服务，入口是 `backend/main.py`。
- 依赖在 `backend/requirements.txt`。
- 当前使用内存字典作为 demo 数据库，服务重启后数据会丢失。
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
- 订单：`DRAFT`、`READY_TO_PACK`、`PACKING`、`COMPLETED`。
- 任务：`TODO`、`IN_PROGRESS`、`DONE`。

修改状态相关逻辑时，需要同步检查：

- 后端 `backend/main.py` 中的枚举和状态流转。
- 前端 `frontend/src/constants/enums.js`。
- 相关页面中的按钮、筛选、状态展示和权限判断。
- `README.md` 中的业务说明。

## 通用开发约定

- 保持 MVP 简洁，优先延续现有 FastAPI 单文件和 Vue 页面结构，除非改动已经明显需要拆分。
- 不要假设数据已持久化；目前后端重启会清空内存数据。
- 不要把当前 mock 登录当作真实鉴权。涉及安全、角色隔离或后台权限时，需要先设计后端鉴权。
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

- 本项目后端固定使用 Conda 环境 `/home/scottsux/miniconda3/envs/python312`。
- 运行 Python、pip、uvicorn 或测试命令时，优先使用这个解释器，不使用 `backend/.venv`。

后端：

```bash
cd backend
/home/scottsux/miniconda3/envs/python312/bin/python -m pip install -r requirements.txt
/home/scottsux/miniconda3/envs/python312/bin/python -m uvicorn main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端格式规范文件：

```bash
/home/scottsux/TMS/.prettierrc.json
```

Python / Ruff 规范文件：

```bash
/home/scottsux/TMS/pyproject.toml
```

默认前端 API 地址来自 `frontend/src/api/client.js`：

- `VITE_API_BASE` 环境变量。
- 未设置时使用 `http://localhost:8000`。
