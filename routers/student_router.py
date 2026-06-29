"""学生管理路由 — CRUD + 批量操作 + CSV 导出 + CSV 导入"""
import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from database import get_db_connection
from auth import get_current_user
from models import StudentCreate, StudentUpdate, PaginatedResponse, MessageResponse, ImportResult, ImportError

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

            # 数据隔离 — 只查当前用户的数据
            where.append("user_id = %s")
            params.append(current_user["user_id"])

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
                "SELECT * FROM students WHERE id = %s AND user_id = %s AND is_deleted = 0",
                (student_id, current_user["user_id"]),
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

            params.extend([student_id, current_user["user_id"]])
            sql = f"UPDATE students SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
            cur.execute(sql, params)
            conn.commit()

            # 只记录实际变化的字段
            import copy
            changed = []
            for k, new_v in fields.items():
                old_v = existing.get(k)
                if str(old_v) != str(new_v):
                    # 字段名映射为中文
                    field_cn = {
                        "name": "姓名", "age": "年龄", "gender": "性别",
                        "score": "成绩", "phone": "电话", "class_name": "班级",
                        "enrollment_date": "入学日期", "address": "地址", "height": "身高"
                    }.get(k, k)
                    changed.append(f"{field_cn}: {old_v} → {new_v}")
            changes = "; ".join(changed) if changed else "无实际变更"
            _audit_log(conn, current_user["user_id"], "UPDATE", student_id,
                       f"{existing['name']} — {changes}", request)

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
                "SELECT id, name FROM students WHERE id = %s AND user_id = %s AND is_deleted = 0",
                (student_id, current_user["user_id"]),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="未找到该学生")

            cur.execute(
                "UPDATE students SET is_deleted = 1 WHERE id = %s AND user_id = %s",
                (student_id, current_user["user_id"]),
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
                "SELECT id, name FROM students WHERE id = %s AND user_id = %s AND is_deleted = 1",
                (student_id, current_user["user_id"]),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="未找到已删除的学生记录")

            cur.execute(
                "UPDATE students SET is_deleted = 0 WHERE id = %s AND user_id = %s",
                (student_id, current_user["user_id"]),
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
                f"UPDATE students SET is_deleted = 1 WHERE id IN ({placeholders}) AND user_id = %s",
                id_list + [current_user["user_id"]],
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
            where = ["is_deleted = 0", "user_id = %s"]
            params = [current_user["user_id"]]

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
                # 日期统一转为 ISO 格式并以 ="..." 输出，避免 Excel/WPS 列宽不足显示 ###
                enroll = row.get("enrollment_date")
                if enroll is not None and enroll != "":
                    if hasattr(enroll, 'strftime'):
                        enroll_str = f'="{enroll.strftime("%Y-%m-%d")}"'
                    elif hasattr(enroll, 'isoformat'):
                        enroll_str = f'="{enroll.isoformat()}"'
                    else:
                        enroll_str = f'="{str(enroll)}"'
                else:
                    enroll_str = ""

                writer.writerow([
                    row["id"], row["name"], row["age"], row["gender"],
                    row["score"], row.get("phone", ""), row.get("class_name", ""),
                    enroll_str,
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


# ==================== CSV 批量导入 ====================
# 必填字段与可选字段定义
REQUIRED_HEADERS = {"name", "age", "gender", "score"}
OPTIONAL_HEADERS = {"phone", "class_name", "enrollment_date", "address", "height"}
ALL_ALLOWED_HEADERS = REQUIRED_HEADERS | OPTIONAL_HEADERS
FORBIDDEN_HEADERS = {"user_id", "is_deleted", "id", "created_at", "updated_at"}


@router.post("/import-csv", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """批量导入 CSV 学生数据 — 绑定当前用户，逐行校验，部分失败不影响合法行"""
    # 1. 校验文件类型
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 .csv 文件")

    # 2. 读取文件内容
    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用 UTF-8 编码的 CSV")

    if not content.strip():
        raise HTTPException(status_code=400, detail="CSV 文件为空")

    # 3. 解析 CSV
    reader = csv.DictReader(io.StringIO(content))
    headers = [h.strip() for h in (reader.fieldnames or [])]

    if not headers:
        raise HTTPException(status_code=400, detail="未检测到 CSV 表头")

    # 4. 校验表头
    header_set = set(headers)
    forbidden_found = header_set & FORBIDDEN_HEADERS
    if forbidden_found:
        raise HTTPException(
            status_code=400,
            detail=f"CSV 不允许包含以下字段：{', '.join(sorted(forbidden_found))}",
        )

    missing = REQUIRED_HEADERS - header_set
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"缺少必填字段：{', '.join(sorted(missing))}",
        )

    # 5. 逐行解析 & 校验
    rows_to_insert = []
    errors = []
    uid = current_user["user_id"]
    row_num = 0  # 数据行号（不含表头）

    for row in reader:
        row_num += 1
        # 跳过空行
        if all(not v.strip() for v in row.values() if v):
            continue

        # 只保留允许的字段
        filtered = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k.strip() in ALL_ALLOWED_HEADERS}

        # 校验必填字段
        name = filtered.get("name", "")
        age_str = filtered.get("age", "")
        gender = filtered.get("gender", "")
        score_str = filtered.get("score", "")

        if not name:
            errors.append({"row": row_num, "reason": "姓名为必填项"})
            continue

        # 年龄必须是整数
        try:
            age = int(age_str)
            if age < 1 or age > 150:
                errors.append({"row": row_num, "reason": f"年龄必须在 1-150 之间，当前值: {age}"})
                continue
        except (ValueError, TypeError):
            errors.append({"row": row_num, "reason": f"年龄必须是整数，当前值: '{age_str}'"})
            continue

        # 性别
        if gender not in ("男", "女"):
            errors.append({"row": row_num, "reason": f"性别必须是 '男' 或 '女'，当前值: '{gender}'"})
            continue

        # 成绩
        try:
            score = float(score_str)
            if score < 0 or score > 100:
                errors.append({"row": row_num, "reason": f"成绩必须在 0-100 之间，当前值: {score}"})
                continue
        except (ValueError, TypeError):
            errors.append({"row": row_num, "reason": f"成绩必须是数字，当前值: '{score_str}'"})
            continue

        # 可选字段清洗
        phone = filtered.get("phone", "")[:20]
        class_name = filtered.get("class_name", "")[:50]
        enrollment_date_str = filtered.get("enrollment_date", "")
        address = filtered.get("address", "")[:200]

        # 入学日期校验
        enrollment_date = None
        if enrollment_date_str:
            import re
            if re.match(r"^\d{4}-\d{2}-\d{2}$", enrollment_date_str):
                enrollment_date = enrollment_date_str
            else:
                errors.append({"row": row_num, "reason": f"入学日期格式错误，应为 YYYY-MM-DD，当前值: '{enrollment_date_str}'"})
                continue

        # 身高
        height = None
        height_str = filtered.get("height", "")
        if height_str:
            try:
                height = float(height_str)
                if height < 0 or height > 300:
                    errors.append({"row": row_num, "reason": f"身高必须在 0-300 之间，当前值: {height}"})
                    continue
            except (ValueError, TypeError):
                errors.append({"row": row_num, "reason": f"身高必须是数字，当前值: '{height_str}'"})
                continue

        rows_to_insert.append((
            uid, name, age, gender, score, phone, class_name,
            enrollment_date, address, height,
        ))

    # 6. 如果所有行都失败且有错误信息
    if not rows_to_insert and errors:
        return ImportResult(
            total=row_num,
            success=0,
            failed=len(errors),
            errors=[ImportError(**e) for e in errors],
        )

    if not rows_to_insert and not errors:
        return ImportResult(total=0, success=0, failed=0, errors=[])

    # 7. 批量插入（参数化 SQL）
    conn = get_db_connection()
    success_count = 0
    try:
        with conn.cursor() as cur:
            sql = """INSERT INTO students
                     (user_id, name, age, gender, score, phone, class_name,
                      enrollment_date, address, height)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.executemany(sql, rows_to_insert)
            success_count = cur.rowcount
            conn.commit()

            _audit_log(conn, uid, "IMPORT_CSV", None,
                       f"CSV 导入 {success_count} 条学生数据（共 {row_num} 行，失败 {len(errors)} 行）", request)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {e}")
    finally:
        conn.close()

    return ImportResult(
        total=row_num,
        success=success_count,
        failed=len(errors),
        errors=[ImportError(**e) for e in errors],
    )


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
                   WHERE is_deleted = 0 AND user_id = %s AND class_name != ''
                   ORDER BY class_name""",
                (current_user["user_id"],),
            )
            classes = [r["class_name"] for r in cur.fetchall()]
            return {"classes": classes}
    finally:
        conn.close()
