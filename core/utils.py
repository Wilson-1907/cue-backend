from rest_framework.response import Response
from rest_framework import status

def success_response(data=None, message="Data retrieved successfully", status_code=status.HTTP_200_OK):
    return Response({"success": True, "message": message, "data": data}, status=status_code)

def created_response(data=None, message="Created successfully"):
    return success_response(data, message, status.HTTP_201_CREATED)

def error_response(message="Request failed", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "message": message, "errors": errors or {}}, status=status_code)