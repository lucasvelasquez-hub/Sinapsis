from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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


class ResourceNotFoundError(CoreDomainError):
    """Raised when a requested entity does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI app."""

    @app.exception_handler(CoreDomainError)
    async def handle_domain_error(_: Request, exc: CoreDomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload or parameters.",
                    "details": exc.errors(),
                }
            },
        )
