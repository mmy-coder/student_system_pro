"""认证路由 — 注册 / 登录 / 个人信息"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import get_db_connection
from auth import hash_password, verify_password, create_access_token, get_current_user
from models import UserRegister, UserLogin, TokenResponse, UserInfo, ChangePasswordRequest, MessageResponse

router = APIRouter(prefix="", tags=["认证"])


@router.post("/register")
async def register(user: UserRegister, request: Request):
    """注册新用户 — 密码 bcrypt 哈希存储"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")

            hashed = hash_password(user.password)
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (user.username, hashed),
            )
            conn.commit()

            # 审计日志
            uid = cur.lastrowid
            _audit_log(conn, uid, "REGISTER", "user", uid,
                       f"新用户注册: {user.username}", request)

            return {"message": "注册成功"}
    finally:
        conn.close()


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, request: Request):
    """登录 — 验证密码后返回 JWT 令牌"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password FROM users WHERE username = %s",
                (user.username,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="用户名或密码错误")

            if not verify_password(user.password, row["password"]):
                raise HTTPException(status_code=401, detail="用户名或密码错误")

            token = create_access_token(row["id"], row["username"])

            # 审计日志
            _audit_log(conn, row["id"], "LOGIN", "user", row["id"],
                       f"用户登录: {row['username']}", request)

            return TokenResponse(
                access_token=token,
                user_id=row["id"],
                username=row["username"],
            )
    finally:
        conn.close()


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, created_at FROM users WHERE id = %s",
                (current_user["user_id"],),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="用户不存在")
            return UserInfo(
                id=row["id"],
                username=row["username"],
                created_at=str(row["created_at"]) if row.get("created_at") else None,
            )
    finally:
        conn.close()


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """修改当前用户密码"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password FROM users WHERE id = %s",
                (current_user["user_id"],),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="用户不存在")

            if not verify_password(req.current_password, row["password"]):
                raise HTTPException(status_code=400, detail="当前密码不正确")

            new_hash = hash_password(req.new_password)
            cur.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (new_hash, current_user["user_id"]),
            )
            conn.commit()

            _audit_log(conn, current_user["user_id"], "CHANGE_PASSWORD", "user",
                       current_user["user_id"], "修改密码", request)

            return MessageResponse(message="密码修改成功")
    finally:
        conn.close()


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    current_user: dict = Depends(get_current_user),
):
    """注销当前账号（同时删除关联的学生数据）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            uid = current_user["user_id"]
            cur.execute("DELETE FROM students WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM audit_logs WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM users WHERE id = %s", (uid,))
            conn.commit()
            return MessageResponse(message="账号已注销")
    finally:
        conn.close()


# ==================== 辅助函数 ====================
def _audit_log(conn, user_id: int, action: str, entity_type: str,
               entity_id: int | None, detail: str, request: Request | None = None):
    """记录审计日志到 audit_logs 表"""
    try:
        ip = request.client.host if request and request.client else None
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO audit_logs (user_id, action, entity_type, entity_id, detail, ip_address)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, action, entity_type, entity_id, detail, ip),
            )
        conn.commit()
    except Exception:
        pass  # 审计日志写入失败不影响主流程
