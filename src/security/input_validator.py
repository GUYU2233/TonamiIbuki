"""Input validation and sanitization utilities."""

import re
import html
from typing import Any


class InputValidator:
    """Validates and sanitizes user inputs."""

    # Maximum allowed lengths
    MAX_STRING_LENGTH = 10000
    MAX_TITLE_LENGTH = 200
    MAX_USERNAME_LENGTH = 50
    MAX_PASSWORD_LENGTH = 128

    # Allowed characters for usernames
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.@]{3,50}$")

    # SQL injection patterns (basic detection)
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(?:')?(?:\s)*;?(?:\s)*(?:--|#|\/\*|\*\/)", re.IGNORECASE),
        re.compile(r"\b(?:DROP|ALTER|TRUNCATE|CREATE)\s+(?:TABLE|DATABASE|INDEX)\b", re.IGNORECASE),
        re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
        re.compile(r"\bEXEC(?:UTE)?\s*\(", re.IGNORECASE),
    ]

    # XSS patterns (basic detection)
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=\s*[\"'].*?[\"']", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    ]

    @classmethod
    def validate_string(cls, value: str, max_length: int = MAX_STRING_LENGTH, field_name: str = "input") -> str:
        """Validate and sanitize a string input.

        Returns the sanitized string.
        Raises ValueError on invalid input.
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")

        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")

        if cls._detect_sql_injection(value):
            raise ValueError(f"{field_name} contains suspicious SQL patterns")

        if cls._detect_xss(value):
            raise ValueError(f"{field_name} contains suspicious script patterns")

        # HTML-escape to neutralize any remaining XSS
        return html.escape(value, quote=True)

    @classmethod
    def validate_username(cls, username: str) -> str:
        """Validate a username."""
        if not isinstance(username, str):
            raise ValueError("Username must be a string")
        if not cls.USERNAME_PATTERN.match(username):
            raise ValueError("Username must be 3-50 alphanumeric characters (a-z, 0-9, _, -, ., @)")
        return username

    @classmethod
    def validate_password(cls, password: str) -> str:
        """Validate password strength."""
        if not isinstance(password, str):
            raise ValueError("Password must be a string")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        if len(password) > cls.MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password exceeds maximum length of {cls.MAX_PASSWORD_LENGTH}")
        return password

    @classmethod
    def sanitize_dict(cls, data: dict, max_depth: int = 5) -> dict:
        """Recursively sanitize all string values in a dict."""
        if max_depth <= 0:
            return {}
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = sanitize_input(value)
            elif isinstance(value, dict):
                result[key] = cls.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                result[key] = cls.sanitize_list(value, max_depth - 1)
            else:
                result[key] = value
        return result

    @classmethod
    def sanitize_list(cls, data: list, max_depth: int = 5) -> list:
        """Recursively sanitize all string values in a list."""
        if max_depth <= 0:
            return []
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(sanitize_input(item))
            elif isinstance(item, dict):
                result.append(cls.sanitize_dict(item, max_depth - 1))
            elif isinstance(item, list):
                result.append(cls.sanitize_list(item, max_depth - 1))
            else:
                result.append(item)
        return result

    @classmethod
    def _detect_sql_injection(cls, value: str) -> bool:
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @classmethod
    def _detect_xss(cls, value: str) -> bool:
        for pattern in cls.XSS_PATTERNS:
            if pattern.search(value):
                return True
        return False


def sanitize_input(value: str, max_length: int = 10000) -> str:
    """Quick sanitize a string — escape HTML, truncate if needed."""
    if not isinstance(value, str):
        return ""
    if len(value) > max_length:
        value = value[:max_length]
    return html.escape(value, quote=True)
