"""Read-only reporting over existing data.

No new models and no new business rules. Every figure here is derived with the
same code the rest of the app already uses -- in particular
``PaymentService._calculate_occupancy_charge`` for what an occupancy costs --
so a report can never disagree with the occupant's own balance or the dashboard.
"""

from decimal import Decimal

from django.db.models import Count, Sum

from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from apps.properties.models import Property
from apps.units.models import Unit


# Export headers are paired with their row-dict keys deliberately.
#
# ExportService maps a header to a key with
#   header.lower().replace(" ", "_").replace("-", "_")
# which is lossy and silent: a header whose transform does not match a key
# produces a column that exists but is always blank. Three of the four original
# exports shipped that way (BUG-011). Keeping the key beside the header here,
# and asserting the pairing in tests, is what stops it happening again.
OCCUPANCY_COLUMNS = [
    ("Property", "property"),
    ("Code", "code"),
    ("Units", "units"),
    ("Capacity", "capacity"),
    ("Occupied", "occupied"),
    ("Available", "available"),
    ("Occupancy Rate", "occupancy_rate"),
]

FINANCIAL_COLUMNS = [
    ("Property", "property"),
    ("Code", "code"),
    ("Payments", "payments"),
    ("Collected", "collected"),
    ("Outstanding", "outstanding"),
]

OCCUPANTS_COLUMNS = [
    ("Name", "name"),
    ("Student ID", "student_id"),
    ("Phone", "phone"),
    ("Email", "email"),
    ("Property", "property"),
    ("Unit", "unit"),
    ("Status", "status"),
    ("Balance", "balance"),
]


def headers_for(columns):
    return [header for header, _ in columns]


class ReportService:

    # ------------------------------------------------------------------
    # Occupancy
    # ------------------------------------------------------------------
    @staticmethod
    def occupancy_report():
        """Capacity and utilisation per property, plus overall totals.

        Only active units count toward capacity, matching DashboardSummaryView --
        an archived or under-maintenance unit is not space you can sell.
        """
        properties = Property.objects.filter(is_active=True).order_by("name")

        # One aggregate for capacity and one for occupancy, rather than a query
        # per property.
        capacity_by_property = {
            row["section__property_id"]: row
            for row in Unit.objects
            .filter(is_active=True)
            .values("section__property_id")
            .annotate(capacity=Sum("capacity"), units=Count("id"))
        }
        occupied_by_property = {
            row["unit__section__property_id"]: row["occupied"]
            for row in Occupancy.objects
            .filter(end_date__isnull=True)
            .values("unit__section__property_id")
            .annotate(occupied=Count("id"))
        }

        rows = []
        for prop in properties:
            stats = capacity_by_property.get(prop.id, {})
            capacity = stats.get("capacity") or 0
            units = stats.get("units") or 0
            occupied = occupied_by_property.get(prop.id, 0)
            rows.append({
                "property": prop.name,
                "code": prop.code,
                "units": units,
                "capacity": capacity,
                "occupied": occupied,
                "available": capacity - occupied,
                "occupancy_rate": round((occupied / capacity) * 100) if capacity else 0,
            })

        total_capacity = sum(r["capacity"] for r in rows)
        total_occupied = sum(r["occupied"] for r in rows)

        return {
            "summary": {
                "total_properties": len(rows),
                "total_units": sum(r["units"] for r in rows),
                "total_capacity": total_capacity,
                "total_occupied": total_occupied,
                "total_available": total_capacity - total_occupied,
                "occupancy_rate": round((total_occupied / total_capacity) * 100) if total_capacity else 0,
            },
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Financial
    # ------------------------------------------------------------------
    @staticmethod
    def financial_report(start_date=None, end_date=None):
        """Collections and outstanding balances, optionally within a date range.

        The date range filters *payments* only. Outstanding balance is a
        standing figure -- what someone owes today is not a function of which
        dates you happen to be looking at -- so narrowing the range changes
        collections without pretending the debt changed too.
        """
        payments = Payment.objects.select_related("student")
        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
        if end_date:
            payments = payments.filter(payment_date__lte=end_date)

        total_collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        by_method = [
            {
                "method": row["payment_method"],
                "count": row["count"],
                "amount": str(row["amount"] or Decimal("0.00")),
            }
            for row in payments.values("payment_method")
            .annotate(count=Count("id"), amount=Sum("amount"))
            .order_by("-amount")
        ]

        balances = ReportService._student_balances()

        # Attribute each payment and each outstanding balance to the property of
        # the student's active unit. A payment from someone with no current
        # assignment has no property to attribute it to -- a real case, not an
        # error (see BUG-022) -- so it is collected under "Unassigned" rather
        # than silently dropped, which would make the per-property totals
        # disagree with the headline figure.
        collected_by_property = {}
        payment_count_by_property = {}
        for payment in payments:
            key = balances.get(payment.student_id, {}).get("property") or "Unassigned"
            collected_by_property[key] = collected_by_property.get(key, Decimal("0.00")) + payment.amount
            payment_count_by_property[key] = payment_count_by_property.get(key, 0) + 1

        outstanding_by_property = {}
        for entry in balances.values():
            if entry["balance"] <= 0:
                continue
            key = entry["property"] or "Unassigned"
            outstanding_by_property[key] = outstanding_by_property.get(key, Decimal("0.00")) + entry["balance"]

        rows = []
        codes = {p.name: p.code for p in Property.objects.all()}
        for name in sorted(set(collected_by_property) | set(outstanding_by_property)):
            rows.append({
                "property": name,
                "code": codes.get(name, ""),
                "payments": payment_count_by_property.get(name, 0),
                "collected": str(collected_by_property.get(name, Decimal("0.00"))),
                "outstanding": str(outstanding_by_property.get(name, Decimal("0.00"))),
            })

        total_outstanding = sum(
            (e["balance"] for e in balances.values() if e["balance"] > 0),
            Decimal("0.00"),
        )

        return {
            "summary": {
                "total_collected": str(total_collected),
                "total_outstanding": str(total_outstanding),
                "payment_count": payments.count(),
                "occupants_in_arrears": sum(1 for e in balances.values() if e["balance"] > 0),
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
            },
            "by_method": by_method,
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Occupants
    # ------------------------------------------------------------------
    @staticmethod
    def occupants_report():
        """Every active occupant with their assignment and current balance."""
        balances = ReportService._student_balances()

        rows = []
        for student in Student.objects.filter(is_active=True).order_by("last_name", "first_name"):
            entry = balances.get(student.id, {})
            rows.append({
                "name": student.full_name(),
                "student_id": student.student_id_number or "",
                "phone": student.phone or "",
                "email": student.email or "",
                "property": entry.get("property") or "",
                "unit": entry.get("unit") or "",
                "status": "Assigned" if entry.get("unit") else "Unassigned",
                "balance": str(entry.get("balance", Decimal("0.00"))),
            })

        return {
            "summary": {
                "total_occupants": len(rows),
                "assigned": sum(1 for r in rows if r["status"] == "Assigned"),
                "unassigned": sum(1 for r in rows if r["status"] == "Unassigned"),
            },
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------
    @staticmethod
    def _student_balances():
        """Balance, unit, and property for every active occupant, keyed by id.

        Mirrors PaymentService.list_overdue_students, but keeps everyone rather
        than only those in arrears, and reuses its charge calculation so the
        numbers agree with what an occupant's own profile shows. Prefetching
        keeps this to a small constant number of queries rather than one per
        occupant.
        """
        students = (
            Student.objects.filter(is_active=True)
            .prefetch_related("occupancies__unit__section__property")
        )

        paid_by_student = {
            row["student_id"]: row["paid"]
            for row in Payment.objects.values("student_id").annotate(paid=Sum("amount"))
        }

        balances = {}
        for student in students:
            total_charges = Decimal("0.00")
            active_occ = None
            for occ in student.occupancies.all():
                total_charges += PaymentService._calculate_occupancy_charge(occ)
                if occ.end_date is None:
                    active_occ = occ

            paid = paid_by_student.get(student.id) or Decimal("0.00")
            balances[student.id] = {
                "balance": total_charges - paid,
                "unit": active_occ.unit.name if active_occ else None,
                "property": active_occ.unit.section.property.name if active_occ else None,
            }

        return balances
