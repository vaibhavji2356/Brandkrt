"""Staff permissions come exclusively from the current database user record."""
from fastapi import HTTPException


def require_permission(user: dict, permission: str) -> None:
    if user.get("role") == "admin":
        return
    permissions = user.get("permissions", [])
    if user.get("role") == "staff" and isinstance(permissions, list) and permission in permissions:
        return
    raise HTTPException(403, "Forbidden")
