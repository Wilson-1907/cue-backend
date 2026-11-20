from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import generics

from core.permissions import IsOperatorOrAdmin
from core.utils import error_response, success_response

from .models import FinanceEntry, FinanceSettings
from .serializers import (
    FinanceEntryCreateSerializer,
    FinanceEntrySerializer,
    FinanceSettingsSerializer,
    MaintenanceCreateSerializer,
)
from . import services


class FinanceSummaryView(APIView):
    """Staff/operator only — never public."""

    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request):
        try:
            days = int(request.query_params.get("days") or 30)
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 3650))
        return success_response(services.summary(days=days), "Finance summary")


class FinanceEntryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request):
        qs = FinanceEntry.objects.all()
        et = request.query_params.get("entry_type")
        cat = request.query_params.get("category")
        src = request.query_params.get("source")
        if et:
            qs = qs.filter(entry_type=et)
        if cat:
            qs = qs.filter(category=cat)
        if src:
            qs = qs.filter(source=src)
        limit = min(int(request.query_params.get("limit") or 100), 500)
        data = FinanceEntrySerializer(qs[:limit], many=True).data
        return success_response(data, "Finance entries")

    def post(self, request):
        ser = FinanceEntryCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid entry", errors=ser.errors)
        d = ser.validated_data
        entry = services.record_entry(
            entry_type=d["entry_type"],
            category=d.get("category") or FinanceEntry.Category.OTHER,
            amount=d["amount"],
            title=d["title"],
            notes=d.get("notes") or "",
            source=FinanceEntry.Source.MANUAL,
            reference=d.get("reference") or "",
            occurred_at=d.get("occurred_at") or timezone.now(),
            user=request.user,
        )
        if not entry:
            return error_response("Could not create entry", status_code=400)
        return success_response(FinanceEntrySerializer(entry).data, "Entry recorded", status_code=201)


class FinanceEntryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def delete(self, request, pk):
        entry = FinanceEntry.objects.filter(pk=pk).first()
        if not entry:
            return error_response("Not found", status_code=404)
        if entry.source == FinanceEntry.Source.AUTO:
            return error_response("Automatic entries cannot be deleted (keep audit trail).", status_code=400)
        entry.delete()
        return success_response(message="Deleted")


class FinanceSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request):
        return success_response(FinanceSettingsSerializer(FinanceSettings.load()).data)

    def patch(self, request):
        obj = FinanceSettings.load()
        ser = FinanceSettingsSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid settings", errors=ser.errors)
        ser.save()
        return success_response(ser.data, "Finance settings updated")


class FinanceMaintenanceView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def post(self, request):
        ser = MaintenanceCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid maintenance", errors=ser.errors)
        d = ser.validated_data
        entry = services.record_maintenance(
            title=d["title"],
            amount=d.get("amount"),
            notes=d.get("notes") or "",
            reference=d.get("reference") or "",
            user=request.user,
        )
        return success_response(FinanceEntrySerializer(entry).data, "Maintenance logged", status_code=201)


class FinanceReportView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request):
        period = (request.query_params.get("period") or "month").lower()
        days = {"week": 7, "month": 30, "quarter": 90, "year": 365}.get(period, 30)
        data = services.summary(days=days)
        data["period"] = period
        return success_response(data, f"Finance report ({period})")
