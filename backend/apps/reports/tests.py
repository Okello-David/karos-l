import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.payments.models import Payment
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit

from .services import (
    FINANCIAL_COLUMNS,
    OCCUPANCY_COLUMNS,
    OCCUPANTS_COLUMNS,
    ReportService,
)

TODAY = date.today()


class ReportTestBase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="manager", password="testpass123", is_staff=True,
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)

        self.prop = Property.objects.create(name="Kikoni Heights", code="KIK")
        section = Section.objects.create(name="Block A", property=self.prop)
        # Capacity 3 across two units, so occupancy rate is not a trivial 0/100.
        self.unit_full = Unit.objects.create(
            name="A-101", section=section, capacity=1,
            semester_price=Decimal("1200000.00"), monthly_price=Decimal("300000.00"),
        )
        self.unit_partial = Unit.objects.create(
            name="A-102", section=section, capacity=2,
            semester_price=Decimal("1000000.00"), monthly_price=Decimal("250000.00"),
        )

        self.paid_student = Student.objects.create(
            first_name="Aisha", last_name="Nakato",
            email="aisha@example.com", phone="+256700000001",
            student_id_number="STU-001", national_id="CM1UG",
        )
        self.owing_student = Student.objects.create(
            first_name="Brian", last_name="Okello",
            email="brian@example.com", phone="+256700000002",
            student_id_number="STU-002", national_id="CM2UG",
        )
        self.unassigned_student = Student.objects.create(
            first_name="Oscar", last_name="Mubiru",
            email="oscar@example.com", student_id_number="STU-003", national_id="CM3UG",
        )

        Occupancy.objects.create(
            student=self.paid_student, unit=self.unit_full,
            start_date=TODAY - timedelta(days=30), billing_mode="semester",
            agreed_price=Decimal("1200000.00"),
        )
        Occupancy.objects.create(
            student=self.owing_student, unit=self.unit_partial,
            start_date=TODAY - timedelta(days=20), billing_mode="semester",
            agreed_price=Decimal("1000000.00"),
        )

        # Paid in full.
        Payment.objects.create(
            student=self.paid_student, amount=Decimal("1200000.00"),
            payment_date=TODAY - timedelta(days=10), payment_method="cash",
        )
        # Part paid -> 600,000 outstanding.
        Payment.objects.create(
            student=self.owing_student, amount=Decimal("400000.00"),
            payment_date=TODAY - timedelta(days=5), payment_method="transfer",
        )

    def auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class OccupancyReportTests(ReportTestBase):

    url = "/api/reports/occupancy/"

    def test_unauthenticated(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_occupancy_figures(self):
        self.auth()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["summary"]
        self.assertEqual(summary["total_capacity"], 3)
        self.assertEqual(summary["total_occupied"], 2)
        self.assertEqual(summary["total_available"], 1)
        self.assertEqual(summary["occupancy_rate"], 67)

        row = response.data["rows"][0]
        self.assertEqual(row["property"], "Kikoni Heights")
        self.assertEqual(row["code"], "KIK")
        self.assertEqual(row["units"], 2)
        self.assertEqual(row["capacity"], 3)
        self.assertEqual(row["occupied"], 2)

    def test_archived_unit_excluded_from_capacity(self):
        """Space you cannot sell is not capacity, matching the dashboard."""
        self.unit_partial.status = "archived"
        self.unit_partial.save()

        self.auth()
        summary = self.client.get(self.url).data["summary"]
        self.assertEqual(summary["total_capacity"], 1)

    def test_no_division_by_zero_with_no_units(self):
        Occupancy.objects.all().delete()
        # Saved one at a time on purpose: Unit.is_active is derived inside
        # Unit.save(), so a queryset .update() would change status and leave
        # is_active stale.
        for unit in Unit.objects.all():
            unit.status = "archived"
            unit.save()

        self.auth()
        summary = self.client.get(self.url).data["summary"]
        self.assertEqual(summary["total_capacity"], 0)
        self.assertEqual(summary["occupancy_rate"], 0)


class FinancialReportTests(ReportTestBase):

    url = "/api/reports/financial/"

    def test_unauthenticated(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_totals(self):
        self.auth()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["summary"]
        self.assertEqual(Decimal(summary["total_collected"]), Decimal("1600000.00"))
        self.assertEqual(Decimal(summary["total_outstanding"]), Decimal("600000.00"))
        self.assertEqual(summary["payment_count"], 2)
        self.assertEqual(summary["occupants_in_arrears"], 1)

    def test_payment_method_breakdown(self):
        self.auth()
        methods = {m["method"]: m for m in self.client.get(self.url).data["by_method"]}
        self.assertEqual(Decimal(methods["cash"]["amount"]), Decimal("1200000.00"))
        self.assertEqual(Decimal(methods["transfer"]["amount"]), Decimal("400000.00"))

    def test_date_range_filters_collections_but_not_outstanding(self):
        """Narrowing the window changes what was collected in it.

        It must not pretend the debt changed too -- what someone owes today is
        not a function of which dates you are looking at.
        """
        self.auth()
        start = (TODAY - timedelta(days=7)).isoformat()
        data = self.client.get(f"{self.url}?start_date={start}").data

        self.assertEqual(Decimal(data["summary"]["total_collected"]), Decimal("400000.00"))
        self.assertEqual(Decimal(data["summary"]["total_outstanding"]), Decimal("600000.00"))

    def test_invalid_date_rejected(self):
        self.auth()
        response = self.client.get(f"{self.url}?start_date=not-a-date")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_end_before_start_rejected(self):
        self.auth()
        response = self.client.get(
            f"{self.url}?start_date={TODAY.isoformat()}"
            f"&end_date={(TODAY - timedelta(days=5)).isoformat()}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_range_returns_zeros_not_error(self):
        self.auth()
        future = (TODAY + timedelta(days=365)).isoformat()
        data = self.client.get(f"{self.url}?start_date={future}").data
        self.assertEqual(Decimal(data["summary"]["total_collected"]), Decimal("0.00"))
        self.assertEqual(data["summary"]["payment_count"], 0)

    def test_per_property_totals_reconcile_with_headline(self):
        """Per-property collections must sum to the headline figure.

        A payment from someone with no active unit has no property to attribute
        it to (a real case -- see BUG-022), so it must land under "Unassigned"
        rather than being silently dropped.
        """
        Payment.objects.create(
            student=self.unassigned_student, amount=Decimal("50000.00"),
            payment_date=TODAY, payment_method="cash",
        )

        self.auth()
        data = self.client.get(self.url).data
        rows_total = sum(Decimal(r["collected"]) for r in data["rows"])
        self.assertEqual(rows_total, Decimal(data["summary"]["total_collected"]))
        self.assertIn("Unassigned", [r["property"] for r in data["rows"]])


class OccupantsReportTests(ReportTestBase):

    url = "/api/reports/occupants/"

    def test_unauthenticated(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_all_active_occupants_with_assignment_and_balance(self):
        self.auth()
        data = self.client.get(self.url).data

        self.assertEqual(data["summary"]["total_occupants"], 3)
        self.assertEqual(data["summary"]["assigned"], 2)
        self.assertEqual(data["summary"]["unassigned"], 1)

        by_name = {r["name"]: r for r in data["rows"]}
        self.assertEqual(by_name["Brian Okello"]["unit"], "A-102")
        self.assertEqual(by_name["Brian Okello"]["property"], "Kikoni Heights")
        self.assertEqual(Decimal(by_name["Brian Okello"]["balance"]), Decimal("600000.00"))
        self.assertEqual(by_name["Oscar Mubiru"]["status"], "Unassigned")

    def test_archived_occupant_excluded(self):
        self.unassigned_student.is_active = False
        self.unassigned_student.save()

        self.auth()
        self.assertEqual(self.client.get(self.url).data["summary"]["total_occupants"], 2)


class ReportExportTests(ReportTestBase):
    """Guards against the BUG-011 failure mode.

    ExportService maps a header to a row key with
    ``header.lower().replace(" ", "_").replace("-", "_")``. That transform is
    lossy and fails silently: a mismatch produces a column that exists but is
    always blank, which is exactly how three of the four original exports
    shipped. Asserting the pairing is cheap; noticing a blank column in a
    spreadsheet months later is not.
    """

    CASES = [
        ("/api/reports/occupancy/", OCCUPANCY_COLUMNS),
        ("/api/reports/financial/", FINANCIAL_COLUMNS),
        ("/api/reports/occupants/", OCCUPANTS_COLUMNS),
    ]

    def test_every_header_transforms_to_its_declared_key(self):
        for _, columns in self.CASES:
            for header, key in columns:
                with self.subTest(header=header):
                    self.assertEqual(
                        header.lower().replace(" ", "_").replace("-", "_"),
                        key,
                        f"Header {header!r} would look up {header.lower().replace(' ', '_')!r}, "
                        f"but the rows use {key!r} -- that column would export blank.",
                    )

    def test_declared_keys_match_the_keys_reports_actually_produce(self):
        for builder, columns in [
            (ReportService.occupancy_report, OCCUPANCY_COLUMNS),
            (ReportService.financial_report, FINANCIAL_COLUMNS),
            (ReportService.occupants_report, OCCUPANTS_COLUMNS),
        ]:
            rows = builder()["rows"]
            self.assertTrue(rows, "fixture should produce rows to check")
            for row in rows:
                self.assertEqual(set(row.keys()), {key for _, key in columns})

    def test_csv_export_has_no_blank_columns(self):
        self.auth()
        for url, columns in self.CASES:
            with self.subTest(url=url):
                response = self.client.get(f"{url}?file_format=csv")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "text/csv")
                self.assertIn("attachment;", response["Content-Disposition"])

                rows = list(csv.reader(io.StringIO(response.content.decode())))
                self.assertEqual(rows[0], [header for header, _ in columns])
                self.assertGreater(len(rows), 1, "export should contain data rows")

                for column_index, (header, _) in enumerate(columns):
                    values = [r[column_index] for r in rows[1:]]
                    self.assertTrue(
                        any(v not in ("", "None") for v in values),
                        f"Column {header!r} is blank in every row of {url}.",
                    )

    def test_xlsx_export_returns_a_real_workbook(self):
        self.auth()
        response = self.client.get("/api/reports/occupancy/?file_format=xlsx")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # XLSX files are zip archives; the magic bytes catch an empty or
        # HTML-error response masquerading as a download.
        self.assertTrue(response.content.startswith(b"PK"))

    def test_unsupported_format_rejected(self):
        self.auth()
        response = self.client.get("/api/reports/occupancy/?file_format=pdf")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
