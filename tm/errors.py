"""Application errors with a stable JSON shape."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


def not_found(kind: str, ident: str) -> AppError:
    return AppError(404, "not_found", f"{kind} {ident!r} not found")


def bad_request(message: str, details: Any | None = None) -> AppError:
    return AppError(400, "validation_error", message, details)


def validation_details(exc: Exception) -> list[dict[str, Any]]:
    """Turn a pydantic ValidationError into JSON-safe details."""
    raw = exc.errors() if hasattr(exc, "errors") else []
    details: list[dict[str, Any]] = []
    for item in raw:
        details.append(
            {
                "loc": list(item.get("loc", [])),
                "msg": item.get("msg", ""),
                "type": item.get("type", ""),
            }
        )
    return details

