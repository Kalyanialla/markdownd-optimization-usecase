"""
Standard application exceptions and error codes.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "INTERNAL_ERROR",
        extra: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} with id '{identifier}' not found.",
            error_code="ENTITY_NOT_FOUND"
        )


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found."):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="NOT_FOUND"
        )


class ConflictException(AppException):
    def __init__(self, detail: str, error_code: str = "RESOURCE_CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code=error_code
        )


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Invalid or expired authentication credentials."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="UNAUTHORIZED"
        )


class ForbiddenException(AppException):
    def __init__(self, detail: str = "You do not have permission to perform this action."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN"
        )


class ValidationException(AppException):
    def __init__(self, detail: str, error_code: str = "VALIDATION_ERROR"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code
        )
