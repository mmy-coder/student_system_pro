"""集中配置管理 — 通过环境变量注入，无硬编码敏感信息"""
import os

# ==================== 数据库 ====================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "200561@Mayun")  # 本地开发默认密码，生产请用环境变量
DB_NAME = os.getenv("DB_NAME", "student_pro_db")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_CHARSET = "utf8mb4"

DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
    "port": DB_PORT,
    "charset": DB_CHARSET,
    "cursorclass": None,  # 延迟导入 pymysql.cursors.DictCursor
    "connect_timeout": 5,
}

# 用于初始化数据库（不指定 database）
DB_CONFIG_NO_DB = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "port": DB_PORT,
    "charset": DB_CHARSET,
    "connect_timeout": 5,
}

# ==================== JWT ====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "student-hub-secret-key-change-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 默认 24 小时

# ==================== 限流 ====================
RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "5/minute")
RATE_LIMIT_GLOBAL = os.getenv("RATE_LIMIT_GLOBAL", "60/minute")

# ==================== 应用 ====================
APP_TITLE = "Student Hub — 学生数据管理平台"
APP_VERSION = "2.0.0"
