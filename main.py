import csv
import io
from datetime import date
import pymysql
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

import os

# ==================== 数据库配置 ====================
DB_CONFIG = {
    "host": "localhost",
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
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
    phone: Optional[str] = ""
    class_name: Optional[str] = ""
    enrollment_date: Optional[str] = None
    address: Optional[str] = ""
    height: Optional[float] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    score: Optional[float] = None
    phone: Optional[str] = None
    class_name: Optional[str] = None
    enrollment_date: Optional[str] = None
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
            offset = (page - 1) * size
            sql = "SELECT * FROM students WHERE 1=1"
            params = []

            if keyword:
                sql += " AND name LIKE %s"
                params.append(f"%{keyword}%")

            # 获取总记录数
            count_sql = sql.replace("SELECT *", "SELECT COUNT(*) as total")
            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

            # 获取当前页数据
            sql += " ORDER BY id ASC LIMIT %s OFFSET %s"
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
            sql = """INSERT INTO students (user_id, name, age, gender, score, phone, class_name, enrollment_date, address, height)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(
                sql,
                (
                    user_id,
                    student.name,
                    student.age,
                    student.gender,
                    student.score,
                    student.phone or "",
                    student.class_name or "",
                    student.enrollment_date or None,
                    student.address or "",
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
            cur.execute("SELECT id FROM students WHERE id = %s", (student_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="未找到该学生")
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
            if student.phone is not None:
                updates.append("phone = %s")
                params.append(student.phone)
            if student.class_name is not None:
                updates.append("class_name = %s")
                params.append(student.class_name)
            if student.enrollment_date is not None:
                updates.append("enrollment_date = %s")
                params.append(student.enrollment_date)
            if student.address is not None:
                updates.append("address = %s")
                params.append(student.address)
            if student.height is not None:
                updates.append("height = %s")
                params.append(student.height)
            if updates:
                sql = f"UPDATE students SET {', '.join(updates)} WHERE id = %s"
                params.append(student_id)
                cur.execute(sql, params)
                conn.commit()
                return {"message": "更新成功"}
            return {"message": "无更新内容"}
    finally:
        conn.close()


# 8. 批量删除学生
@app.delete("/students/batch/")
async def batch_delete_students(user_id: int, ids: str = Query(...)):
    """批量删除，ids 为逗号分隔的 ID 列表，如 ids=1,3,5"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
        if not id_list:
            raise HTTPException(status_code=400, detail="请提供要删除的学生 ID")
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(id_list))
            cur.execute(f"DELETE FROM students WHERE id IN ({placeholders})", id_list)
            conn.commit()
            return {"message": f"成功删除 {cur.rowcount} 名学生"}
    finally:
        conn.close()


# 9. 数据统计接口
@app.get("/stats/")
async def get_stats(user_id: int):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM students")
            total = cur.fetchone()["total"]
            cur.execute("SELECT AVG(score) as avg_score FROM students")
            avg_score = cur.fetchone()["avg_score"] or 0
            cur.execute("SELECT gender, COUNT(*) as cnt FROM students GROUP BY gender")
            gender_rows = cur.fetchall()
            male = next((r["cnt"] for r in gender_rows if r["gender"] == "男"), 0)
            female = next((r["cnt"] for r in gender_rows if r["gender"] == "女"), 0)
            cur.execute("SELECT COUNT(*) as cnt FROM students WHERE score >= 85")
            excellent = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) as cnt FROM students WHERE score < 60")
            failed = cur.fetchone()["cnt"]
            cur.execute("SELECT class_name, COUNT(*) as cnt FROM students WHERE class_name != '' GROUP BY class_name ORDER BY cnt DESC")
            class_stats = cur.fetchall()
            return {
                "total": total,
                "avg_score": round(float(avg_score), 1),
                "male": male,
                "female": female,
                "excellent": excellent,
                "failed": failed,
                "class_stats": class_stats,
            }
    finally:
        conn.close()


# 10. 导出学生数据为 CSV
@app.get("/students/export/")
async def export_students(user_id: int, keyword: str = ""):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            sql = "SELECT id, name, age, gender, score, phone, class_name, enrollment_date, address, height FROM students WHERE 1=1"
            params = []
            if keyword:
                sql += " AND name LIKE %s"
                params.append(f"%{keyword}%")
            sql += " ORDER BY id ASC"
            cur.execute(sql, params)
            data = cur.fetchall()
            output = io.StringIO()
            output.write('﻿')  # UTF-8 BOM for Excel 中文兼容
            writer = csv.writer(output)
            writer.writerow(["学号", "姓名", "年龄", "性别", "成绩", "电话", "班级", "入学日期", "地址", "身高(cm)"])
            for row in data:
                writer.writerow([
                    row["id"], row["name"], row["age"], row["gender"], row["score"],
                    row.get("phone", ""), row.get("class_name", ""), row.get("enrollment_date", ""),
                    row.get("address", ""), row.get("height", "")
                ])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": "attachment; filename=students_export.csv"}
            )
    finally:
        conn.close()


# 11. 直接托管前端网页
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
