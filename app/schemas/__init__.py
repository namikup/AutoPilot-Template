# app/schemas/__init__.py
from .admin import (
    AdminCreateUser,
    AdminEventResponse,
    ApprovedDomainsRequest,
    ApprovedDomainsResponse,
    BulkActionResponse,
    GroupActionResponse,
    GroupCreateRequest,
    GroupMemberRequest,
    GroupResponse,
    GroupRoleRequest,
    GroupUpdateRequest,
    LoginEventResponse,
    LoginEventsSummaryResponse,
    PaginatedUsersResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RoleActionResponse,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    SessionActionResponse,
    SessionResponse,
    SessionStatsResponse,
    UserApprovalResponse,
    UserResponse,
    UserRoleAssignRequest,
    UserRoleResponse,
)
from .ai import AIChatRequest, AIChatResponse
from .audit import AuditLogListResponse, AuditLogResponse, AuditStatsResponse
from .auth import PendingStatusResponse, UserRegistration, UserRegistrationResponse
from .insight import InsightActionResponse, InsightComputeResponse, InsightOut
from .item import Item, ItemBase, ItemCreate
from .policy import (
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluationOut,
    PolicyOut,
    PolicyUpdate,
)

__all__ = [
    # AI schemas
    "AIChatRequest",
    "AIChatResponse",
    # Item schemas
    "ItemBase",
    "ItemCreate",
    "Item",
    # Policy schemas
    "PolicyUpdate",
    "PolicyOut",
    "PolicyEvaluationOut",
    "PolicyEvaluateRequest",
    "PolicyEvaluateResponse",
    # Insight schemas
    "InsightOut",
    "InsightComputeResponse",
    "InsightActionResponse",
    # Auth schemas
    "UserRegistration",
    "UserRegistrationResponse",
    "PendingStatusResponse",
    # Admin schemas
    "UserResponse",
    "PaginatedUsersResponse",
    "UserApprovalResponse",
    "AdminCreateUser",
    "BulkActionResponse",
    "ApprovedDomainsRequest",
    "ApprovedDomainsResponse",
    # Role schemas
    "RoleResponse",
    "RoleCreateRequest",
    "RoleUpdateRequest",
    "RoleActionResponse",
    # User role assignment schemas
    "UserRoleAssignRequest",
    "UserRoleResponse",
    # Password reset schemas
    "PasswordResetRequest",
    "PasswordResetResponse",
    # Group schemas
    "GroupResponse",
    "GroupCreateRequest",
    "GroupUpdateRequest",
    "GroupActionResponse",
    "GroupMemberRequest",
    "GroupRoleRequest",
    # Session schemas
    "SessionResponse",
    "SessionStatsResponse",
    "SessionActionResponse",
    # Login events schemas
    "LoginEventResponse",
    "AdminEventResponse",
    "LoginEventsSummaryResponse",
    # Audit schemas
    "AuditLogResponse",
    "AuditLogListResponse",
    "AuditStatsResponse",
]
