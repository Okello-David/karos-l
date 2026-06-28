import io
import os
from decimal import Decimal

from django.conf import settings
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.core.exceptions import ConflictError, NotFoundError
from apps.core.permissions import IsPropertyManager

from .serializers import PaymentSerializer, ReceiptSerializer
from .services import PaymentService


def _get_payment_or_error(pk):
    try:
        return PaymentService.get_payment(pk)
    except NotFoundError as e:
        from rest_framework.exceptions import NotFound
        raise NotFound(detail=e.detail)


class PaymentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated | IsPropertyManager]

    def list(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        result = PaymentService.list_payments(
            search=request.query_params.get("search"),
            property_id=request.query_params.get("property_id"),
            student_id=request.query_params.get("student_id"),
            payment_method=request.query_params.get("payment_method"),
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
            page=page,
            page_size=page_size,
        )
        serializer = PaymentSerializer(result["results"], many=True)
        result["results"] = serializer.data
        return Response(result)

    def create(self, request):
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = PaymentService.record_payment(
                student_id=serializer.validated_data["student"].id,
                amount=serializer.validated_data["amount"],
                payment_date=serializer.validated_data["payment_date"],
                payment_method=serializer.validated_data["payment_method"],
                reference=serializer.validated_data.get("reference", ""),
                notes=serializer.validated_data.get("notes", ""),
            )
        except ConflictError as e:
            return Response({"detail": e.detail}, status=status.HTTP_409_CONFLICT)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PAYMENT,
            entity_id=payment.id,
            action=AuditLog.Action.RECORD_PAYMENT,
            description=f"Payment of {payment.amount} recorded for {payment.student} ({payment.payment_method}).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = PaymentSerializer(payment)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        payment = _get_payment_or_error(pk)
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def student_balance(self, request):
        student_id = request.query_params.get("student_id")
        if not student_id:
            return Response(
                {"detail": "student_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            balance = PaymentService.calculate_student_balance(student_id)
        except NotFoundError as e:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail=e.detail)
        return Response(balance)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        overdue_list = PaymentService.list_overdue_students()
        return Response({
            "count": len(overdue_list),
            "results": overdue_list,
        })


class ReceiptViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated | IsPropertyManager]

    def list(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        result = PaymentService.list_receipts(
            search=request.query_params.get("search"),
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
            page=page,
            page_size=page_size,
        )
        serializer = ReceiptSerializer(result["results"], many=True)
        result["results"] = serializer.data
        return Response(result)

    def retrieve(self, request, pk=None):
        try:
            receipt = PaymentService.get_receipt(pk)
        except NotFoundError as e:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail=e.detail)
        serializer = ReceiptSerializer(receipt)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        try:
            receipt = PaymentService.get_receipt(pk)
        except NotFoundError as e:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail=e.detail)

        buf = _generate_pdf_receipt(receipt)
        filename = f"receipt_{receipt.receipt_number}.pdf"
        return FileResponse(buf, as_attachment=True, filename=filename)


def _generate_pdf_receipt(receipt):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReceiptTitle",
        fontSize=22,
        leading=26,
        spaceAfter=4,
        textColor=colors.HexColor("#1e40af"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="Subtitle",
        fontSize=10,
        leading=14,
        spaceAfter=20,
        textColor=colors.HexColor("#6b7280"),
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="SectionLabel",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#9ca3af"),
        fontName="Helvetica",
        spaceBefore=8,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="SectionValue",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#111827"),
        fontName="Helvetica",
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#9ca3af"),
        fontName="Helvetica",
        alignment=1,
    ))

    method_labels = {"cash": "Cash", "transfer": "Bank Transfer", "card": "Card"}

    elements = []

    elements.append(Paragraph("KarosL", styles["ReceiptTitle"]))
    elements.append(Paragraph("Property Management — Official Receipt", styles["Subtitle"]))

    elements.append(Table(
        [[Paragraph(f"<b>Receipt #:</b> {receipt.receipt_number}", styles["SectionValue"])]],
        colWidths=[460],
    ))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("RECEIPT DETAILS", styles["SectionLabel"]))
    elements.append(Spacer(1, 2 * mm))

    data = [
        ["Occupant", receipt.student_name],
        ["ID Number", receipt.student_id_number or "—"],
        ["Property", receipt.property_name or "—"],
        ["Unit", receipt.unit_name or "—"],
        ["Payment Date", receipt.payment_date.isoformat()],
        ["Payment Method", method_labels.get(receipt.payment_method, receipt.payment_method)],
        ["Reference", receipt.reference or "—"],
    ]

    t = Table(data, colWidths=[140, 320])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (0, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (1, 0), (1, -1), 11),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#f3f4f6")),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#e5e7eb")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("PAYMENT SUMMARY", styles["SectionLabel"]))
    elements.append(Spacer(1, 2 * mm))

    total_data = [
        ["Amount Paid", f"UGX {receipt.amount:,.2f}"],
        ["Outstanding Balance", f"UGX {receipt.outstanding_balance_after:,.2f}"],
    ]

    total_t = Table(total_data, colWidths=[140, 320])
    total_t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (0, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (1, -1), 14),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#f3f4f6")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
    ]))
    elements.append(total_t)
    elements.append(Spacer(1, 2 * cm))

    elements.append(Paragraph(
        f"Issued: {receipt.issued_at.strftime('%d %B %Y at %H:%M')}",
        styles["Footer"],
    ))
    elements.append(Paragraph(
        "This is a computer-generated receipt. No signature is required.",
        styles["Footer"],
    ))

    doc.build(elements)
    buf.seek(0)
    return buf
