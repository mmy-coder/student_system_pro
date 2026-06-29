"""Pydantic 数据模型 — 请求验证 + 响应结构"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date


# ==================== 认证模型 ====================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, description="用户名 (3-30字符)")
    password: str = Field(..., min_length=6, max_length=128, description="密码 (6-128字符)")
    security_question: Optional[str] = Field(default="", max_length=200, description="安全问题(可选)")
    security_answer: Optional[str] = Field(default="", max_length=255, description="安全答案(可选)")

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含至少一个字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        return v

    @field_validator("security_answer")
    @classmethod
    def answer_required_if_question(cls, v: str, info) -> str:
        """如果设置了安全问题，答案必填"""
        # Pydantic v2: fields are accessible via info.data
        return v.strip() if v else ""


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class UserInfo(BaseModel):
    id: int
    username: str
    created_at: Optional[str] = None


# ==================== 学生模型 ====================
class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    age: int = Field(..., ge=1, le=150, description="年龄")
    gender: str = Field(..., min_length=1, max_length=10, description="性别 (男/女)")
    score: float = Field(..., ge=0, le=100, description="成绩 (0-100)")
    phone: Optional[str] = Field(default="", max_length=20)
    class_name: Optional[str] = Field(default="", max_length=50)
    enrollment_date: Optional[str] = None  # "YYYY-MM-DD"
    address: Optional[str] = Field(default="", max_length=200)
    height: Optional[float] = Field(default=None, ge=0, le=300)

    @field_validator("gender")
    @classmethod
    def gender_valid(cls, v: str) -> str:
        if v not in ("男", "女"):
            raise ValueError("性别只能是 '男' 或 '女'")
        return v


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    age: Optional[int] = Field(default=None, ge=1, le=150)
    gender: Optional[str] = Field(default=None, max_length=10)
    score: Optional[float] = Field(default=None, ge=0, le=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    class_name: Optional[str] = Field(default=None, max_length=50)
    enrollment_date: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=200)
    height: Optional[float] = Field(default=None, ge=0, le=300)

    @field_validator("gender")
    @classmethod
    def gender_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in ("男", "女"):
            raise ValueError("性别只能是 '男' 或 '女'")
        return v


class StudentResponse(BaseModel):
    id: int
    name: str
    age: int
    gender: str
    score: float
    phone: str = ""
    class_name: str = ""
    enrollment_date: Optional[str] = None
    address: str = ""
    height: Optional[float] = None
    created_at: Optional[str] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    size: int
    data: list[dict]


# ==================== 统计模型 ====================
class StatsResponse(BaseModel):
    total: int
    avg_score: float
    male: int
    female: int
    excellent: int  # >= 85
    failed: int     # < 60
    class_stats: list[dict]
    score_distribution: list[dict] = []
    monthly_enrollment: list[dict] = []


class ScoreDistribution(BaseModel):
    range_label: str
    count: int


class MonthlyEnrollment(BaseModel):
    month: str
    count: int


# ==================== 审计模型 ====================
class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: str


# ==================== 通用响应 ====================
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


# ==================== 修改密码 ====================
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("新密码必须包含至少一个字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("新密码必须包含至少一个数字")
        if len(v) < 6:
            raise ValueError("新密码至少6位")
        return v


# ==================== CSV 导入模型 ====================
class ImportError(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    total: int
    success: int
    failed: int
    errors: list[ImportError] = []


# ==================== 找回密码模型 ====================
class ForgotPasswordCheck(BaseModel):
    username: str = Field(..., min_length=1)


class ForgotPasswordCheckResponse(BaseModel):
    username: str
    has_security_question: bool
    security_question: str = ""


class ForgotPasswordReset(BaseModel):
    username: str = Field(..., min_length=1)
    security_answer: str = Field(..., min_length=1, description="安全问题答案")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("新密码必须包含至少一个字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("新密码必须包含至少一个数字")
        return v
