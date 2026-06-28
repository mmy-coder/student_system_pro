# Student Hub — 学生数据管理平台

基于 **FastAPI + MySQL** 的多用户学生信息管理系统。支持 JWT 认证、多用户数据隔离、完整 CRUD、搜索筛选分页排序、CSV 批量导入导出、数据统计图表、审计日志、Docker Compose 一键部署。

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.138-green)
![MySQL](https://img.shields.io/badge/MySQL-8.4-orange)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ 功能特性

| 模块 | 功能 |
| :--- | :--- |
| 🔐 用户认证 | JWT 令牌 + bcrypt 密码哈希，注册 / 登录 / 个人信息 |
| 👥 多用户隔离 | SQL 层强制 `WHERE user_id = %s`，用户只能操作自己的数据 |
| 📋 学生 CRUD | 添加、编辑、删除（软删除）、批量删除、恢复已删除 |
| 🔍 搜索筛选 | 按姓名模糊搜索，按班级、性别、成绩范围筛选 |
| 📄 分页排序 | 前端分页控件 + 多字段排序（姓名/年龄/成绩/班级/入学日期） |
| 📥 CSV 导入 | 批量导入学生数据，自动校验格式 |
| 📤 CSV 导出 | UTF-8 BOM 编码，Excel/WPS 直接打开无乱码 |
| 📊 数据统计 | 仪表盘总览、成绩分布柱状图、月度入学折线图、班级对比 |
| 📝 审计日志 | 记录所有增删改操作，含 IP 地址与操作时间 |
| 🛡️ 限流保护 | 登录接口 5 次/分钟，全局 60 次/分钟 |
| 🐳 Docker 部署 | `docker compose up -d` 一键启动，自动建库建表 |
| 📖 API 文档 | Swagger UI + ReDoc 自动生成 |

---

## 🛠️ 技术栈

| 层级 | 技术 |
| :--- | :--- |
| 后端框架 | FastAPI 0.138 |
| 服务器 | Uvicorn 0.49 |
| 数据库 | MySQL 8.4 + PyMySQL 1.2 |
| 认证 | JWT (PyJWT 2.13) + bcrypt 5.0 |
| 数据校验 | Pydantic v2 |
| 限流 | slowapi 0.1 |
| 前端 | HTML5 / CSS3 / JavaScript ES6+ |
| 图表 | Chart.js 4.4 |
| 部署 | Docker + Docker Compose |
| 版本管理 | Git + GitHub |

---

## 📁 项目结构

```
student_system_pro/
├── main.py                     # FastAPI 应用入口，生命周期、中间件、路由注册
├── config.py                   # 集中配置管理（环境变量注入，无硬编码）
├── database.py                 # 数据库连接 + 启动自动建库建表
├── auth.py                     # bcrypt 密码哈希 + JWT 令牌签发/验证
├── models.py                   # Pydantic 请求/响应模型
├── routers/
│   ├── auth_router.py          # POST /register  /login  /me
│   ├── student_router.py       # CRUD / 批量操作 / CSV 导入导出 / 筛选
│   └── stats_router.py         # 仪表盘统计 / 图表数据 / 审计日志
├── index.html                  # SPA 单页前端（含登录态管理）
├── requirements.txt            # Python 依赖清单
├── start.sh                    # 一键启动脚本（后端 + cpolar 内网穿透）
├── Dockerfile                  # Docker 镜像构建文件
├── docker-compose.yml          # 多容器编排（web + db）
├── .env.example                # 环境变量模板
└── .dockerignore               # Docker 构建忽略清单
```

---

## 🚀 快速开始 — 本地 venv

### 前置条件

- Python 3.10+
- MySQL 8.0+（需运行中）

### 1. 克隆仓库

```bash
git clone https://github.com/mmy-coder/student_system_pro.git
cd student_system_pro
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 MySQL 密码
```

### 4. 启动服务

```bash
uvicorn main:app --reload --port 8000
```

### 5. 访问系统

| 地址 | 说明 |
| :--- | :--- |
| http://localhost:8000 | 前端页面 |
| http://localhost:8000/docs | Swagger UI 接口文档 |
| http://localhost:8000/redoc | ReDoc 接口文档 |
| http://localhost:8000/health | 健康检查 |

---

## 🐳 快速开始 — Docker Compose

### 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 已安装并运行

### 1. 克隆仓库

```bash
git clone https://github.com/mmy-coder/student_system_pro.git
cd student_system_pro
```

### 2. （可选）配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入数据库密码等（也可跳过，使用示例默认值直接体验）
```

### 3. 一键启动

```bash
docker compose up -d
```

首次启动会自动：
- 拉取 Python 3.13-slim 和 MySQL 8.4 镜像
- 构建 web 镜像（安装依赖）
- 启动 MySQL 容器 → 健康检查通过 → 启动 web 容器
- 自动创建数据库和表结构

### 4. 访问系统

| 地址 | 说明 |
| :--- | :--- |
| http://localhost:8001 | 前端页面（映射到容器 8000） |
| http://localhost:8001/docs | Swagger UI |
| http://localhost:8001/health | 健康检查 |

### 端口说明

> ⚠️ 为避免和本机 FastAPI（8000）及 MySQL（3306）冲突：
>
> - `web` 容器内部 8000 → 映射本机 **8001**
> - `db` 容器内部 3306 → 映射本机 **3307**
>
> 如需连接数据库调试：`mysql -h 127.0.0.1 -P 3307 -u root -p`

### 常用命令

```bash
docker compose ps              # 查看容器状态
docker compose logs -f web     # 查看 web 日志
docker compose down            # 停止并移除容器（保留数据）
docker compose down -v         # 停止并删除数据卷（重置数据库）
docker compose up --build -d   # 重新构建并启动
```

---

## 🗄️ 数据库

首次启动时 `database.py` 自动执行：

- `CREATE DATABASE IF NOT EXISTS student_pro_db`
- 建表 `users`（用户表 — id, username, bcrypt_password, created_at）
- 建表 `students`（学生表 — 含 user_id、软删除 is_deleted、索引）
- 建表 `audit_logs`（审计日志 — 操作记录、IP 地址）

完全零手动 SQL 操作。

---

## 🧪 功能验证记录

以下功能已通过本地测试和 Docker 环境测试：

| 验证项 | 状态 |
| :--- | :--- |
| 用户注册 / 登录 | ✅ |
| JWT 令牌签发与 Bearer 认证 | ✅ |
| user_id 数据隔离（用户 A 无法访问用户 B 的数据） | ✅ |
| 越权修改 / 删除被拒绝（403） | ✅ |
| 学生 CRUD（添加、编辑、删除、软删除恢复） | ✅ |
| 搜索、筛选、分页、排序 | ✅ |
| CSV 批量导入 | ✅ |
| CSV 导出（Excel 直接打开） | ✅ |
| 审计日志记录 | ✅ |
| /health 返回 200 | ✅ |
| Docker Compose 一键启动 | ✅ |
| Swagger UI 接口文档 | ✅ |

---

## 🏆 项目亮点

### 后端工程实践

- RESTful API 设计，遵循 FastAPI 最佳实践
- JWT 无状态认证 + bcrypt 密码加盐哈希
- Pydantic v2 请求校验，自动生成 OpenAPI 文档
- 中间件层：CORS、全局异常处理、slowapi 限流
- 数据库层：软删除、索引优化、参数化查询防 SQL 注入
- 审计日志：全操作追踪，含 IP 记录

### 安全设计

- 所有 SQL 使用参数化查询，杜绝注入
- 多用户数据隔离：SQL 层强制 `WHERE user_id = %s`
- 密码强度校验（必须含字母 + 数字）
- 令牌过期机制 + Bearer 认证头
- 敏感配置通过环境变量注入，`.env` 不会提交到 Git

### 运维友好

- `docker compose up -d` 一键部署
- 启动自动建库建表，零手动 SQL
- 环境变量集中管理（`config.py`）
- 健康检查端点 `/health`
- 容器健康检查（MySQL → web 依赖启动顺序）

---

## 📋 Roadmap

### 已完成

- [x] JWT 登录认证 + bcrypt 加密
- [x] 学生 CRUD + 软删除与恢复
- [x] user_id 多用户数据隔离
- [x] 搜索、筛选、分页、排序
- [x] CSV 批量导入
- [x] CSV 导出（UTF-8 BOM）
- [x] 审计日志
- [x] 暗色主题 UI + Chart.js 数据可视化
- [x] 限流保护
- [x] Docker Compose 部署
- [x] Swagger / ReDoc 自动文档

### 计划中

- [ ] pytest 自动化测试（单元测试 + 集成测试）
- [ ] CI/CD（GitHub Actions 自动构建测试）
- [ ] 云服务器部署（AWS EC2 / 阿里云）
- [ ] 管理员角色与权限系统
- [ ] 密码重置（邮箱验证）
- [ ] 前后端分离：React / Vue 3 + TypeScript 重构
- [ ] Redis 缓存层
- [ ] API 版本管理 (`/api/v1/`)

---

## 📖 项目学习价值

本项目从零构建了一个完整的 Web 后端管理系统，覆盖了 **数据库设计 → 认证鉴权 → RESTful API → 前端交互 → 数据可视化 → CSV 数据处理 → 容器化部署 → Git 版本管理** 的全流程。对于计算机专业学生而言，它是理解「真实项目怎么做」的理想教学案例——你会看到参数化查询如何防 SQL 注入、JWT 如何实现无状态认证、多用户数据隔离如何在 SQL 层实现、Docker Compose 如何让部署变成一条命令。代码遵循工程规范：配置与逻辑分离、错误统一处理、日志记录可追溯。

---

## 📄 License

MIT License
