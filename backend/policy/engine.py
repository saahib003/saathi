"""Risk-aware policy engine."""

from enum import StrEnum
from pathlib import Path

from backend.policy.permissions import PermissionScope, PermissionStore
from backend.tools.base import RiskLevel, ToolDefinition


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    ASK = "ASK"
    DENY = "DENY"


class PolicyEngine:
    def __init__(self, permission_store: PermissionStore | None = None, confirmation_behavior: str = "ask") -> None:
        self.permission_store = permission_store
        self.confirmation_behavior = confirmation_behavior

    def evaluate(self, definition: ToolDefinition, arguments: object) -> PolicyDecision:
        if definition.risk is RiskLevel.CRITICAL:
            return PolicyDecision.DENY
        if definition.risk is RiskLevel.HIGH:
            return PolicyDecision.ASK
        if self.confirmation_behavior == "always":
            return PolicyDecision.ASK
        if definition.risk is RiskLevel.MEDIUM:
            if self.permission_store and self.permission_store.allows(definition.name, arguments.model_dump() if hasattr(arguments, "model_dump") else arguments):
                return PolicyDecision.ALLOW
            return PolicyDecision.ASK
        return PolicyDecision.ALLOW

    def grant_permission(self, definition: ToolDefinition, scope_type: str, scope_value: str | None = None) -> None:
        if scope_type == PermissionScope.PERMANENT and definition.risk not in {RiskLevel.LOW, RiskLevel.MEDIUM}:
            raise ValueError("Permanent permissions are limited to LOW and MEDIUM tools")
        if scope_type == PermissionScope.SCOPED and not scope_value:
            raise ValueError("Scoped permissions require a scope value")
        if self.permission_store:
            self.permission_store.grant(definition.name, scope_type, scope_value)


class MinimalPolicy(PolicyEngine):
    """Compatibility policy used by Phase 3 unit tests and isolated tools."""

    def __init__(self) -> None:
        super().__init__(None, "ask")

