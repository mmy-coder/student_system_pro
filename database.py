"""数据库连接管理与初始化"""
import pymysql
from fastapi import HTTPException
from config import DB_CONFIG, DB_CONFIG_NO_DB, DB_NAME


def get_db_connection():
    """获取数据库连接，统一处理连接异常"""
    try:
        config = DB_CONFIG.copy()
        config["cursorclass"] = pymysql.cursors.DictCursor
        return pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else 0
        messages = {
            1045: "数据库认证失败，请设置 DB_USER / DB_PASSWORD 环境变量",
            1049: f"数据库 {DB_NAME} 不存在",
            2003: "无法连接到 MySQL 服务器，请确认 MySQL 服务已启动",
        }
        detail = messages.get(code, f"数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {e}")


def init_database():
    """
    启动时自动创建数据库和表（如果不存在）。
    先连接到 MySQL（不指定数据库），创建数据库后再创建表。
    """
    try:
        conn = pymysql.connect(**DB_CONFIG_NO_DB)
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.close()
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else 0
        if code == 1045:
            user = DB_CONFIG_NO_DB.get("user", "root")
            print(f"[WARN] MySQL 认证失败 — 用户名={user}")
            print("[WARN] 请设置环境变量: $env:DB_PASSWORD='你的MySQL密码'")
        elif code == 2003:
            print("[WARN] 无法连接到 MySQL 服务器 (localhost)")
            print("[WARN] 请确认 MySQL 服务已启动: net start MySQL80")
        else:
            print(f"[WARN] 数据库连接失败: {e}")
        print("[WARN] 服务将继续运行，但数据库功能不可用")
        return

    try:
        config = DB_CONFIG.copy()
        config["cursorclass"] = pymysql.cursors.DictCursor
        conn = pymysql.connect(**config)
        with conn.cursor() as cur:
            # 用户表 — password 列保留原名但存 bcrypt hash
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    security_question VARCHAR(200) DEFAULT '',
                    security_answer VARCHAR(255) DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 兼容旧表：如果 users 表没有 security_question 列则添加
            try:
                cur.execute("SELECT security_question FROM users LIMIT 1")
            except Exception:
                cur.execute(
                    "ALTER TABLE users ADD COLUMN security_question VARCHAR(200) DEFAULT '' AFTER password"
                )
                cur.execute(
                    "ALTER TABLE users ADD COLUMN security_answer VARCHAR(255) DEFAULT '' AFTER security_question"
                )

            # 学生表 — 增加软删除 + 更新时间
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(50) NOT NULL,
                    age INT NOT NULL,
                    gender VARCHAR(10) NOT NULL,
                    score DECIMAL(5,1) NOT NULL,
                    phone VARCHAR(20) DEFAULT '',
                    class_name VARCHAR(50) DEFAULT '',
                    enrollment_date DATE DEFAULT NULL,
                    address VARCHAR(200) DEFAULT '',
                    height DECIMAL(5,1) DEFAULT NULL,
                    is_deleted TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_name (name),
                    INDEX idx_is_deleted (is_deleted),
                    INDEX idx_class_name (class_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 审计日志表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INT DEFAULT NULL,
                    detail TEXT DEFAULT NULL,
                    ip_address VARCHAR(45) DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_created_at (created_at),
                    INDEX idx_entity (entity_type, entity_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 兼容旧表：如果 students 表没有 is_deleted 列则添加
            try:
                cur.execute(
                    "SELECT is_deleted FROM students LIMIT 1"
                )
            except Exception:
                cur.execute(
                    "ALTER TABLE students ADD COLUMN is_deleted TINYINT(1) DEFAULT 0"
                )
                cur.execute(
                    "ALTER TABLE students ADD INDEX idx_is_deleted (is_deleted)"
                )

            # 兼容：如果有 class_name 列则加索引
            try:
                cur.execute(
                    "SELECT class_name FROM students LIMIT 1"
                )
                cur.execute(
                    "ALTER TABLE students ADD INDEX idx_class_name (class_name)"
                )
            except Exception:
                pass

            # 兼容旧表：添加 updated_at 列
            try:
                cur.execute(
                    "SELECT updated_at FROM students LIMIT 1"
                )
            except Exception:
                cur.execute(
                    "ALTER TABLE students ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                )

        conn.commit()
        conn.close()
        print(f"[OK] 数据库初始化完成 — {DB_NAME} (users + students + audit_logs)")
    except Exception as e:
        print(f"[WARN] 建表失败: {e}")
        print("[WARN] 服务将继续运行，但数据库功能可能不可用")
