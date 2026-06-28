"""学生管理路由 — CRUD + 批量操作 + CSV 导出"""
import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from database import get_db_connection
from auth import get_current_user
from models import StudentCreate, StudentUpdate, PaginatedResponse, MessageResponse

router = APIRouter(prefix="/students", tags=["学生管理"])


# ==================== 辅助 ====================
def _audit_log(conn, user_id: int, action: str, entity_id: int | None,
               detail: str, request: Request | None = None):
    """记录审计日志"""
    try:
        ip = request.client.host if request and request.client else None
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO audit_logs (user_id, action, entity_type, entity_id, detail, ip_address)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, action, "student", entity_id, detail, ip),
            )
        conn.commit()
    except Exception:
        pass


# ==================== 查询学生列表 ====================
@router.get("/")
async def get_students(
    request: Request,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str = "",
    class_name: str = "",
    gender: str = "",
    score_min: float | None = Query(None, ge=0, le=100),
    score_max: float | None = Query(None, ge=0, le=100),
    sort_by: str = Query("id", pattern="^(id|name|age|gender|score|enrollment_date|class_name)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """获取学生列表 — 支持搜索、筛选、排序、分页"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 构建 WHERE 条件
            where = ["is_deleted = 0"]
            params: list = []

            # 数据隔离 — 只查当前用户的数据（管理员可通过特殊参数查看全局，此处简化）
            # 注：保留灵活度，后续可添加管理员角色
            # where.append("user_id = %s")
            # params.append(current_user["user_id"])

            if keyword:
                where.append("name LIKE %s")
                params.append(f"%{keyword}%")
            if class_name:
                where.append("class_name = %s")
                params.append(class_name)
            if gender:
                where.append("gender = %s")
                params.append(gender)
            if score_min is not None:
                where.append("score >= %s")
                params.append(score_min)
            if score_max is not None:
                where.append("score <= %s")
                params.append(score_max)

            where_clause = "WHERE " + " AND ".join(where)

            # 排序字段白名单
            allowed_sort = {
                "id", "name", "age", "gender", "score",
                "enrollment_date", "class_name"
            }
            if sort_by not in allowed_sort:
                sort_by = "id"
            order = "DESC" if sort_order.lower() == "desc" else "ASC"

            # 总记录数
            cur.execute(f"SELECT COUNT(*) as total FROM students {where_clause}", params)
            total = cur.fetchone()["total"]

            # 当前页数据
            offset = (page - 1) * size
            cur.execute(
                f"SELECT * FROM students {where_clause} "
                f"ORDER BY {sort_by} {order} LIMIT %s OFFSET %s",
                params + [size, offset],
            )
            data = cur.fetchall()

            # 序列化日期
            for row in data:
                if row.get("enrollment_date"):
                    row["enrollment_date"] = str(row["enrollment_date"])
                if row.get("created_at"):
                    row["created_at"] = str(row["created_at"])
                if row.get("updated_at"):
                    row["updated_at"] = str(row["updated_at"])

            return PaginatedResponse(total=total, page=page, size=size, data=data)
    finally:
        conn.close()


# ==================== 添加学生 ====================
@router.post("/")
async def add_student(
    student: StudentCreate,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """添加新学生"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """INSERT INTO students
                     (user_id, name, age, gender, score, phone, class_name,
                      enrollment_date, address, height)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (
                current_user["user_id"],
                student.name,
                student.age,
                student.gender,
                student.score,
                student.phone or "",
                student.class_name or "",
                student.enrollment_date or None,
                student.address or "",
                student.height,
            ))
            conn.commit()
            new_id = cur.lastrowid

            _audit_log(conn, current_user["user_id"], "CREATE", new_id,
                       f"添加学生: {student.name}", request)

            return {"message": "添加成功", "id": new_id}
    finally:
        conn.close()


# ==================== 修改学生 ====================
@router.put("/{student_id}")
async def update_student(
    student_id: int,
    student: StudentUpdate,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """更新学生信息"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM students WHERE id = %s AND is_deleted = 0",
                (student_id,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="未找到该学生")

            # 构建动态 UPDATE
            fields = student.model_dump(exclude_unset=True)
            if not fields:
                return {"message": "无更新内容"}

            updates = []
            params = []
            for key, val in fields.items():
                updates.append(f"{key} = %s")
                params.append(val)

            params.append(student_id)
            sql = f"UPDATE students SET {', '.join(updates)} WHERE id = %s"
            cur.execute(sql, params)
            conn.commit()

            changes = ", ".join(f"{k}={v}" for k, v in fields.items())
            _audit_log(conn, current_user["user_id"], "UPDATE", student_id,
                       f"更新学生 [{existing['name']}]: {changes}", request)

            return {"message": "更新成功"}
    finally:
        conn.close()


# ==================== 删除学生（软删除） ====================
@router.delete("/{student_id}")
async def delete_student(
    student_id: int,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """软删除学生 — 标记 is_deleted=1"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM students WHERE id = %s AND is_deleted = 0",
                (student_id,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="未找到该学生")

            cur.execute(
                "UPDATE students SET is_deleted = 1 WHERE id = %s",
                (student_id,),
            )
            conn.commit()

            _audit_log(conn, current_user["user_id"], "DELETE", student_id,
                       f"软删除学生: {existing['name']}", request)

            return {"message": "删除成功"}
    finally:
        conn.close()


# ==================== 恢复学生 ====================
@router.post("/{student_id}/restore")
async def restore_student(
    student_id: int,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """恢复已软删除的学生"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM students WHERE id = %s AND is_deleted = 1",
                (student_id,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="未找到已删除的学生记录")

            cur.execute(
                "UPDATE students SET is_deleted = 0 WHERE id = %s",
                (student_id,),
            )
            conn.commit()

            _audit_log(conn, current_user["user_id"], "RESTORE", student_id,
                       f"恢复学生: {existing['name']}", request)

            return {"message": "已恢复"}
    finally:
        conn.close()


# ==================== 批量删除 ====================
@router.delete("/batch/")
async def batch_delete_students(
    ids: str = Query(...),
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """批量软删除 — ids 为逗号分隔的 ID 列表"""
    conn = get_db_connection()
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
        if not id_list:
            raise HTTPException(status_code=400, detail="请提供要删除的学生 ID")

        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(id_list))
            cur.execute(
                f"UPDATE students SET is_deleted = 1 WHERE id IN ({placeholders})",
                id_list,
            )
            conn.commit()

            _audit_log(conn, current_user["user_id"], "BATCH_DELETE", None,
                       f"批量删除 {cur.rowcount} 名学生: ids={ids}", request)

            return {"message": f"成功删除 {cur.rowcount} 名学生"}
    finally:
        conn.close()


# ==================== CSV 导出 ====================
@router.get("/export/")
async def export_students(
    current_user: dict = Depends(get_current_user),
    keyword: str = "",
    class_name: str = "",
    gender: str = "",
    score_min: float | None = None,
    score_max: float | None = None,
):
    """导出学生数据为 CSV（兼容 Excel 中文）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            where = ["is_deleted = 0"]
            params = []

            if keyword:
                where.append("name LIKE %s")
                params.append(f"%{keyword}%")
            if class_name:
                where.append("class_name = %s")
                params.append(class_name)
            if gender:
                where.append("gender = %s")
                params.append(gender)
            if score_min is not None:
                where.append("score >= %s")
                params.append(score_min)
            if score_max is not None:
                where.append("score <= %s")
                params.append(score_max)

            where_clause = "WHERE " + " AND ".join(where)
            sql = f"""SELECT id, name, age, gender, score, phone, class_name,
                             enrollment_date, address, height
                      FROM students {where_clause} ORDER BY id ASC"""
            cur.execute(sql, params)
            data = cur.fetchall()

            output = io.StringIO()
            output.write('﻿')  # UTF-8 BOM
            writer = csv.writer(output)
            writer.writerow([
                "学号", "姓名", "年龄", "性别", "成绩", "电话", "班级",
                "入学日期", "地址", "身高(cm)"
            ])
            for row in data:
                writer.writerow([
                    row["id"], row["name"], row["age"], row["gender"],
                    row["score"], row.get("phone", ""), row.get("class_name", ""),
                    str(row["enrollment_date"]) if row.get("enrollment_date") else "",
                    row.get("address", ""), row.get("height", "")
                ])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition":
                    "attachment; filename=students_export.csv"
                },
            )
    finally:
        conn.close()


# ==================== 获取筛选选项 ====================
@router.get("/filters/")
async def get_filter_options(
    current_user: dict = Depends(get_current_user),
):
    """返回筛选下拉框的可用选项（班级列表、成绩范围）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT class_name FROM students
                   WHERE is_deleted = 0 AND class_name != ''
                   ORDER BY class_name"""
            )
            classes = [r["class_name"] for r in cur.fetchall()]
            return {"classes": classes}
    finally:
        conn.close()
