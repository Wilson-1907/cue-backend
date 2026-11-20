from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        if isinstance(exc, (DjangoValidationError, IntegrityError)):
            return Response(
                {"success": False, "message": "Validation error", "errors": {"detail": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    detail = response.data
    message = "Request failed"
    errors = detail

    if isinstance(detail, dict):
        if "detail" in detail and len(detail) == 1:
            message = str(detail["detail"])
            errors = {}
        elif "non_field_errors" in detail:
            message = "; ".join(map(str, detail["non_field_errors"]))
            errors = detail
        else:
            message = "Validation error"
    elif isinstance(detail, list):
        message = "; ".join(map(str, detail))
        errors = {"detail": detail}

    response.data = {"success": False, "message": message, "errors": errors}
    return response