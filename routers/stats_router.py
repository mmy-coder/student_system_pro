"""统计路由 — 仪表盘数据 + 图表数据"""
from fastapi import APIRouter, Depends
from database import get_db_connection
from auth import get_current_user
from models import StatsResponse

router = APIRouter(prefix="/stats", tags=["数据统计"])


# ==================== 仪表盘汇总（一站式） ====================
@router.get("/dashboard")
async def get_dashboard_summary(current_user: dict = Depends(get_current_user)):
    """返回仪表盘所需的全部数据：统计 + 最近学生 + 最近操作"""
    conn = get_db_connection()
    uid = current_user["user_id"]
    try:
        with conn.cursor() as cur:
            # 统计
            cur.execute(
                "SELECT COUNT(*) as total FROM students WHERE is_deleted = 0 AND user_id = %s",
                (uid,),
            )
            total = cur.fetchone()["total"]

            cur.execute(
                "SELECT AVG(score) as avg_score FROM students WHERE is_deleted = 0 AND user_id = %s",
                (uid,),
            )
            avg_score = round(float((cur.fetchone()["avg_score"] or 0)), 1)

            cur.execute(
                """SELECT gender, COUNT(*) as cnt
                   FROM students WHERE is_deleted = 0 AND user_id = %s
                   GROUP BY gender""",
                (uid,),
            )
            gender_rows = cur.fetchall()
            male = next((r["cnt"] for r in gender_rows if r["gender"] == "男"), 0)
            female = next((r["cnt"] for r in gender_rows if r["gender"] == "女"), 0)

            cur.execute(
                "SELECT COUNT(*) as cnt FROM students WHERE is_deleted = 0 AND user_id = %s AND score >= 85",
                (uid,),
            )
            excellent = cur.fetchone()["cnt"]
            cur.execute(
                "SELECT COUNT(*) as cnt FROM students WHERE is_deleted = 0 AND user_id = %s AND score < 60",
                (uid,),
            )
            failed = cur.fetchone()["cnt"]

            # 最近添加的 5 名学生
            cur.execute(
                """SELECT id, name, age, gender, score, class_name, enrollment_date, created_at
                   FROM students WHERE is_deleted = 0 AND user_id = %s
                   ORDER BY created_at DESC LIMIT 5""",
                (uid,),
            )
            recent_students = cur.fetchall()
            for r in recent_students:
                if r.get("enrollment_date"):
                    r["enrollment_date"] = str(r["enrollment_date"])
                if r.get("created_at"):
                    r["created_at"] = str(r["created_at"])

            # 最近 5 条审计日志
            cur.execute(
                """SELECT action, entity_type, entity_id, detail, created_at
                   FROM audit_logs WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT 5""",
                (uid,),
            )
            recent_logs = cur.fetchall()
            for r in recent_logs:
                if r.get("created_at"):
                    r["created_at"] = str(r["created_at"])

            # 成绩分布
            score_dist = _score_distribution(cur, uid)

            return {
                "total": total,
                "avg_score": avg_score,
                "male": male,
                "female": female,
                "excellent": excellent,
                "failed": failed,
                "score_distribution": score_dist,
                "recent_students": recent_students,
                "recent_logs": recent_logs,
            }
    finally:
        conn.close()


@router.get("/", response_model=StatsResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """获取仪表盘统计数据"""
    conn = get_db_connection()
    uid = current_user["user_id"]
    try:
        with conn.cursor() as cur:
            # 总人数
            cur.execute(
                "SELECT COUNT(*) as total FROM students WHERE is_deleted = 0 AND user_id = %s",
                (uid,),
            )
            total = cur.fetchone()["total"]

            # 平均分
            cur.execute(
                "SELECT AVG(score) as avg_score FROM students WHERE is_deleted = 0 AND user_id = %s",
                (uid,),
            )
            avg_score = round(float((cur.fetchone()["avg_score"] or 0)), 1)

            # 性别分布
            cur.execute(
                """SELECT gender, COUNT(*) as cnt
                   FROM students WHERE is_deleted = 0 AND user_id = %s
                   GROUP BY gender""",
                (uid,),
            )
            gender_rows = cur.fetchall()
            male = next((r["cnt"] for r in gender_rows if r["gender"] == "男"), 0)
            female = next((r["cnt"] for r in gender_rows if r["gender"] == "女"), 0)

            # 优秀 / 不及格
            cur.execute(
                "SELECT COUNT(*) as cnt FROM students WHERE is_deleted = 0 AND user_id = %s AND score >= 85",
                (uid,),
            )
            excellent = cur.fetchone()["cnt"]
            cur.execute(
                "SELECT COUNT(*) as cnt FROM students WHERE is_deleted = 0 AND user_id = %s AND score < 60",
                (uid,),
            )
            failed = cur.fetchone()["cnt"]

            # 班级统计
            cur.execute(
                """SELECT class_name, COUNT(*) as cnt
                   FROM students WHERE is_deleted = 0 AND user_id = %s AND class_name != ''
                   GROUP BY class_name ORDER BY cnt DESC""",
                (uid,),
            )
            class_stats = cur.fetchall()

            # 成绩分布 (每 10 分一段)
            score_dist = _score_distribution(cur, uid)

            # 月度入学趋势 (近 12 个月)
            monthly = _monthly_enrollment(cur, uid)

            return StatsResponse(
                total=total,
                avg_score=avg_score,
                male=male,
                female=female,
                excellent=excellent,
                failed=failed,
                class_stats=class_stats,
                score_distribution=score_dist,
                monthly_enrollment=monthly,
            )
    finally:
        conn.close()


@router.get("/score-distribution")
async def get_score_distribution(
    current_user: dict = Depends(get_current_user),
):
    """成绩分布数据（供前端柱状图使用）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            return {"distribution": _score_distribution(cur, current_user["user_id"])}
    finally:
        conn.close()


@router.get("/monthly-enrollment")
async def get_monthly_enrollment(
    current_user: dict = Depends(get_current_user),
):
    """月度入学趋势（供前端折线图使用）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            return {"monthly": _monthly_enrollment(cur, current_user["user_id"])}
    finally:
        conn.close()


@router.get("/class-comparison")
async def get_class_comparison(
    current_user: dict = Depends(get_current_user),
):
    """班级对比数据（供前端横向柱状图使用）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT class_name,
                           COUNT(*) as cnt,
                           AVG(score) as avg_score,
                           SUM(CASE WHEN score >= 85 THEN 1 ELSE 0 END) as excellent_cnt
                    FROM students WHERE is_deleted = 0 AND user_id = %s AND class_name != ''
                    GROUP BY class_name ORDER BY cnt DESC""",
                (current_user["user_id"],),
            )
            rows = cur.fetchall()
            for r in rows:
                r["avg_score"] = round(float(r["avg_score"]), 1)
            return {"classes": rows}
    finally:
        conn.close()


@router.get("/audit/")
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    page: int = 1,
    size: int = 20,
):
    """获取当前用户的审计日志"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as total FROM audit_logs WHERE user_id = %s",
                (current_user["user_id"],),
            )
            total = cur.fetchone()["total"]

            offset = (page - 1) * size
            cur.execute(
                """SELECT id, user_id, action, entity_type, entity_id, detail,
                          ip_address, created_at
                   FROM audit_logs WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (current_user["user_id"], size, offset),
            )
            data = cur.fetchall()
            for row in data:
                if row.get("created_at"):
                    row["created_at"] = str(row["created_at"])

            return {"total": total, "page": page, "size": size, "data": data}
    finally:
        conn.close()


# ==================== 辅助函数 ====================
def _score_distribution(cur, user_id: int) -> list[dict]:
    """计算成绩分布：0-59, 60-69, 70-79, 80-89, 90-100"""
    ranges = [
        ("0-59", 0, 59),
        ("60-69", 60, 69),
        ("70-79", 70, 79),
        ("80-89", 80, 89),
        ("90-100", 90, 100),
    ]
    result = []
    for label, low, high in ranges:
        cur.execute(
            """SELECT COUNT(*) as cnt FROM students
               WHERE is_deleted = 0 AND user_id = %s AND score >= %s AND score <= %s""",
            (user_id, low, high),
        )
        result.append({"range_label": label, "count": cur.fetchone()["cnt"]})
    return result


def _monthly_enrollment(cur, user_id: int) -> list[dict]:
    """过去 12 个月每月新增学生数"""
    try:
        cur.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as cnt
            FROM students
            WHERE is_deleted = 0
              AND user_id = %s
              AND created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY month
            ORDER BY month ASC
        """, (user_id,))
        rows = cur.fetchall()
        return [{"month": r["month"], "count": r["cnt"]} for r in rows]
    except Exception:
        # created_at 列可能不存在（旧表兼容）
        return []
