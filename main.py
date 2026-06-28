"""Student Hub — 企业级学生数据管理平台 (FastAPI + MySQL)"""
import os
import sys
from pathlib import Path

# 加载 .env 文件（必须在 config 导入之前）
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key not in os.environ:
                    os.environ[key] = value

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import APP_TITLE, APP_VERSION, RATE_LIMIT_AUTH, RATE_LIMIT_GLOBAL
from database import init_database

# 修复 Windows 控制台中文编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ==================== 应用生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库，关闭时清理资源"""
    init_database()
    yield


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 限流中间件 ====================
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_GLOBAL])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    HAS_RATE_LIMIT = True
except ImportError:
    HAS_RATE_LIMIT = False
    print("[WARN] slowapi 未安装，跳过限流 — 安装: pip install slowapi")


# ==================== 全局异常处理 ====================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """统一异常处理 — 防止敏感信息泄露"""
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": str(exc.status_code)},
        )
    print(f"[ERROR] 未处理异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试", "error_code": "INTERNAL_ERROR"},
    )


# ==================== 注册路由 ====================
from routers.auth_router import router as auth_router
from routers.student_router import router as student_router
from routers.stats_router import router as stats_router

# 对认证端点添加更严格的限流
if HAS_RATE_LIMIT:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    # 为敏感端点添加装饰器
    auth_router_routes = [
        r for r in auth_router.routes
        if hasattr(r, "endpoint") and hasattr(r, "methods")
    ]
    for route in auth_router_routes:
        path = getattr(route, "path", "")
        if path in ("/register", "/login"):
            # 在路由定义中已通过装饰器处理，此处跳过
            pass

app.include_router(auth_router)
app.include_router(student_router)
app.include_router(stats_router)


# ==================== 静态文件 & SPA ====================
@app.get("/", response_class=HTMLResponse)
async def index():
    """托管前端单页应用"""
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ==================== 健康检查 ====================
@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}
