class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(DomainError):
    status_code = 401


class NotFoundError(DomainError):
    status_code = 404


class PermissionDeniedError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    """The request is valid but the auction's current state does not allow it."""

    status_code = 409


class BusinessRuleError(DomainError):
    status_code = 422


class FieldError(BusinessRuleError):
    """A business rule tied to one input field, reported in FastAPI's validation-error shape."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
