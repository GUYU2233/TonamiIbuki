"""RBAC service – Role-Based Access Control for TonamiIbuki.
from __future__ import annotations

Manages users, roles, and permissions. Provides middleware integration points
for API token authentication and role-based authorization.
"""


import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import json

from config.settings import settings


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "diagnosis:run",
        "diagnosis:approve",
        "tools:execute",
        "kb:import",
        "kb:query",
        "cases:manage",
        "audit:read",
        "audit:export",
        "system:config",
        "users:manage",
    },
    Role.OPERATOR: {
        "diagnosis:run",
        "diagnosis:approve",
        "tools:execute",
        "kb:import",
        "kb:query",
        "cases:manage",
        "audit:read",
    },
    Role.VIEWER: {
        "kb:query",
        "audit:read",
    },
}


@dataclass
class RBACUser:
    username: str
    role: Role
    password_hash: str
    token_hash: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: str = ""


# ---------------------------------------------------------------------------
# RBAC Service
# ---------------------------------------------------------------------------

class RBACService:
    """In-memory RBAC with JSON persistence."""

    STORE_PATH = Path(settings.KB_RUNBOOKS_PATH).parent / "state" / "rbac_users.json"

    def __init__(self) -> None:
        self._users: dict[str, RBACUser] = {}
        self._load()
        if not self._users:
            self._seed_default_admin()

    # ------------------------------------------------------------------
    # user management
    # ------------------------------------------------------------------

    def create_user(self, username: str, password: str, role: Role = Role.VIEWER) -> Optional[RBACUser]:
        if username in self._users:
            return None
        token = secrets.token_urlsafe(32)
        user = RBACUser(
            username=username,
            role=role,
            password_hash=self._hash(password),
            token_hash=self._hash(token),
        )
        self._users[username] = user
        self._save()
        # Return user with plain token (only time token is visible)
        user.token_hash = token
        return user

    def delete_user(self, username: str) -> bool:
        if username not in self._users:
            return False
        del self._users[username]
        self._save()
        return True

    def update_role(self, username: str, role: Role) -> bool:
        if username not in self._users:
            return False
        self._users[username].role = role
        self._save()
        return True

    def regenerate_token(self, username: str) -> Optional[str]:
        if username not in self._users:
            return None
        token = secrets.token_urlsafe(32)
        self._users[username].token_hash = self._hash(token)
        self._save()
        return token

    def create_token(self, username: str, password: str) -> Optional[str]:
        """Authenticate with username/password and generate a new API token."""
        user = self.authenticate_password(username, password)
        if not user:
            return None
        token = secrets.token_urlsafe(32)
        self._users[username].token_hash = self._hash(token)
        self._save()
        return token

    # ------------------------------------------------------------------
    # authentication
    # ------------------------------------------------------------------

    def authenticate_token(self, token: str) -> Optional[RBACUser]:
        """Validate API token and return user."""
        token_hash = self._hash(token)
        for user in self._users.values():
            if user.token_hash == token_hash:
                user.last_login = datetime.now(timezone.utc).isoformat()
                return user
        return None

    def authenticate_password(self, username: str, password: str) -> Optional[RBACUser]:
        """Validate username/password and return user."""
        user = self._users.get(username)
        if not user:
            return None
        if user.password_hash != self._hash(password):
            return None
        user.last_login = datetime.now(timezone.utc).isoformat()
        return user

    # ------------------------------------------------------------------
    # authorization
    # ------------------------------------------------------------------

    def has_permission(self, username: str, permission: str) -> bool:
        user = self._users.get(username)
        if not user:
            return False
        return permission in ROLE_PERMISSIONS.get(user.role, set())

    def get_user(self, username: str) -> Optional[RBACUser]:
        return self._users.get(username)

    def list_users(self) -> list[dict]:
        return [
            {
                "username": u.username,
                "role": u.role.value,
                "created_at": u.created_at,
                "last_login": u.last_login,
                "has_token": bool(u.token_hash),
            }
            for u in self._users.values()
        ]

    def status(self) -> dict:
        return {
            "ready": True,
            "users": len(self._users),
            "roles": {r.value: len([u for u in self._users.values() if u.role == r]) for r in Role},
        }

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self.STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "username": u.username,
                "role": u.role.value,
                "password_hash": u.password_hash,
                "token_hash": u.token_hash,
                "created_at": u.created_at,
                "last_login": u.last_login,
            }
            for u in self._users.values()
        ]
        self.STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self.STORE_PATH.exists():
            return
        try:
            data = json.loads(self.STORE_PATH.read_text(encoding="utf-8"))
            for item in data:
                self._users[item["username"]] = RBACUser(
                    username=item["username"],
                    role=Role(item["role"]),
                    password_hash=item["password_hash"],
                    token_hash=item["token_hash"],
                    created_at=item.get("created_at", ""),
                    last_login=item.get("last_login", ""),
                )
        except (json.JSONDecodeError, KeyError):
            pass

    def _seed_default_admin(self) -> None:
        """Create default admin user if no users exist."""
        user = self.create_user("admin", "tonamiibuki2026", Role.ADMIN)
        if user:
            # Store the token so admin can retrieve it
            self._save()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


rbac_service = RBACService()
