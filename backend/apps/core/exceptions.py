class KarosLError(Exception):
    """Base exception for all application-level errors."""
    detail = "An unexpected error occurred."

    def __init__(self, detail=None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class ConflictError(KarosLError):
    detail = "The request conflicts with the current state."


class NotFoundError(KarosLError):
    detail = "The requested resource was not found."


class PermissionDeniedError(KarosLError):
    detail = "You do not have permission to perform this action."


def drf_exception_handler(exc, context):
    """
    Global DRF exception handler that returns consistent JSON responses
    for all API exceptions, preventing HTML error pages from being returned.

    Preserves field-level validation errors for serializers while ensuring
    top-level exceptions (auth, not found, etc.) return a uniform structure.
    """
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)
    if response is not None:
        data = response.data
        if isinstance(data, dict):
            if "detail" not in data:
                data["status_code"] = response.status_code
            else:
                data = {"detail": data["detail"], "status_code": response.status_code}
        else:
            data = {"detail": str(data), "status_code": response.status_code}
        response.data = data
    return response
