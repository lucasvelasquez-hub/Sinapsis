import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import REQUEST_ID_HEADER, request_id_of

logger = logging.getLogger(__name__)


class CoreDomainError(Exception):
    """Base exception for domain-level operational errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "DOMAIN_ERROR",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class ConflictError(CoreDomainError):
    """Raised when the request conflicts with the current state of an entity."""

    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT, code=code)


class ResourceNotFoundError(CoreDomainError):
    """Raised when a requested entity does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
        )


def _envelope(request: Request, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "request_id": request_id_of(request), **extra}
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI app."""

    @app.exception_handler(CoreDomainError)
    async def handle_domain_error(request: Request, exc: CoreDomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_envelope(request, exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                request,
                "VALIDATION_ERROR",
                "Invalid request payload or parameters.",
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Runs in Starlette's outermost ServerErrorMiddleware: the response does not pass
        # back through RequestIdMiddleware, so the header is set here too.
        request_id = request_id_of(request)
        logger.exception(
            "Unhandled error request_id=%s %s %s", request_id, request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(request, "INTERNAL_ERROR", "Error interno del servidor."),
            headers={REQUEST_ID_HEADER: request_id} if request_id else None,
        )
