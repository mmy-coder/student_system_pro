import pymysql
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

# ==================== 数据库配置 ====================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "200561@Mayun",
    "database": "student_pro_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

app = FastAPI(title="企业级学生管理系统")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ==================== Pydantic 数据模型 ====================
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class StudentCreate(BaseModel):
    name: str
    age: int
    gender: str
    score: float
    address: Optional[str] = ""
    height: Optional[float] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    score: Optional[float] = None
    address: Optional[str] = None
    height: Optional[float] = None


# ==================== 后端路由逻辑 ====================


# 1. 注册接口
@app.post("/register")
async def register(user: UserRegister):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")
            # 注意：企业级项目密码需用 bcrypt 哈希，此处为教学简单使用明文
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (user.username, user.password),
            )
            conn.commit()
            return {"message": "注册成功"}
    finally:
        conn.close()


# 2. 登录接口
@app.post("/login")
async def login(user: UserLogin):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username FROM users WHERE username = %s AND password = %s",
                (user.username, user.password),
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            return {
                "user_id": result["id"],
                "username": result["username"],
                "message": "登录成功",
            }
    finally:
        conn.close()


# 3. 获取、搜索与分页学生列表（企业级核心接口）
@app.get("/students/")
async def get_students(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str = "",
):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # 计算偏移量
            offset = (page - 1) * size
            sql = "SELECT * FROM students WHERE user_id = %s"
            params = [user_id]

            if keyword:
                sql += " AND name LIKE %s"
                params.append(f"%{keyword}%")

            # 获取总记录数
            count_sql = sql.replace("SELECT *", "SELECT COUNT(*) as total")
            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

            # 获取当前页数据
            sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
            params.extend([size, offset])
            cur.execute(sql, params)
            data = cur.fetchall()

            return {"total": total, "page": page, "size": size, "data": data}
    finally:
        conn.close()


# 4. 添加学生
@app.post("/students/")
async def add_student(user_id: int, student: StudentCreate):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            sql = """INSERT INTO students (user_id, name, age, gender, score, address, height)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(
                sql,
                (
                    user_id,
                    student.name,
                    student.age,
                    student.gender,
                    student.score,
                    student.address,
                    student.height,
                ),
            )
            conn.commit()
            return {"message": "添加成功"}
    finally:
        conn.close()


# 5. 删除学生（带企业级软/硬删除，此处用硬删除）
@app.delete("/students/{student_id}")
async def delete_student(student_id: int, user_id: int):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM students WHERE id = %s AND user_id = %s",
                (student_id, user_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="未找到该学生或无权操作")
            cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
            conn.commit()
            return {"message": "删除成功"}
    finally:
        conn.close()


# 6. 修改学生
@app.put("/students/{student_id}")
async def update_student(student_id: int, user_id: int, student: StudentUpdate):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            updates, params = [], []
            if student.name is not None:
                updates.append("name = %s")
                params.append(student.name)
            if student.age is not None:
                updates.append("age = %s")
                params.append(student.age)
            if student.gender is not None:
                updates.append("gender = %s")
                params.append(student.gender)
            if student.score is not None:
                updates.append("score = %s")
                params.append(student.score)
            if student.address is not None:
                updates.append("address = %s")
                params.append(student.address)
            if student.height is not None:
                updates.append("height = %s")
                params.append(student.height)
            if updates:
                sql = f"UPDATE students SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
                params.extend([student_id, user_id])
                cur.execute(sql, params)
                conn.commit()
                return {"message": "更新成功"}
            return {"message": "无更新内容"}
    finally:
        conn.close()


# 7. 直接托管前端网页
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
