from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.payments.models import Payment, Receipt
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit


def _make_demo_property():
    """Mirrors seed_demo_data's KIK dataset shape closely enough to classify as DEMO."""
    prop = Property.objects.create(name="Kikoni Heights", code="KIK", address="Kikoni")
    section = Section.objects.create(property=prop, name="Block A")
    unit = Unit.objects.create(
        section=section, name="A-101", capacity=2,
        semester_price=Decimal("100000"), monthly_price=Decimal("30000"),
    )
    student = Student.objects.create(
        first_name="Aisha", last_name="Nakato",
        email="aisha.nakato@example.com", student_id_number="STU-2026-001",
    )
    occ = Occupancy.objects.create(student=student, unit=unit, start_date=date.today() - timedelta(days=10))
    payment = Payment.objects.create(
        student=student, amount=Decimal("100000"),
        payment_date=date.today(), payment_method="cash", reference="",
    )
    receipt = Receipt.objects.create(
        payment=payment, receipt_number="RCPT-0001", outstanding_balance_after=Decimal("0"),
        student_name=student.full_name(), student_id_number=student.student_id_number,
        unit_name=unit.name, property_name=prop.name, amount=payment.amount,
        payment_date=payment.payment_date, payment_method=payment.payment_method,
        reference=payment.reference,
    )
    return prop, section, unit, student, occ, payment, receipt


def _make_test_property():
    """Mirrors an archived AUDIT-TEST verification chain, per docs/LIVE_DATA_AUDIT.md."""
    prop = Property.objects.create(name="AUDIT-TEST Property", code="AUD", is_active=False)
    section = Section.objects.create(property=prop, name="AUDIT-TEST Section")
    unit = Unit.objects.create(
        section=section, name="AUDIT-101", capacity=1,
        semester_price=Decimal("1000"), monthly_price=Decimal("1000"),
    )
    student = Student.objects.create(first_name="AUDIT-TEST", last_name="Occupant")
    occ = Occupancy.objects.create(
        student=student, unit=unit, start_date=date.today(), end_date=date.today(),
    )
    payment = Payment.objects.create(
        student=student, amount=Decimal("1000"),
        payment_date=date.today(), payment_method="cash", reference="",
    )
    receipt = Receipt.objects.create(
        payment=payment, receipt_number="RCPT-TEST-0001", outstanding_balance_after=Decimal("0"),
        student_name=student.full_name(), student_id_number="",
        unit_name=unit.name, property_name=prop.name, amount=payment.amount,
        payment_date=payment.payment_date, payment_method=payment.payment_method,
        reference=payment.reference,
    )
    return prop, section, unit, student, occ, payment, receipt


class ResetLiveDataCommandTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="karosadmin", email="admin@example.com", password="adminpass123",
        )

    def _run(self, *args):
        out = StringIO()
        call_command("reset_live_data", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_makes_no_writes(self):
        _make_demo_property()
        _make_test_property()

        output = self._run()

        self.assertEqual(Property.objects.count(), 2)
        self.assertEqual(Student.objects.count(), 2)
        self.assertIn("demo=   1", output)
        self.assertIn("test=   1", output)
        self.assertIn("No UNKNOWN rows", output)

    def test_confirm_deletes_demo_and_test_leaves_users_and_audit_untouched(self):
        prop, *_ = _make_demo_property()
        _make_test_property()
        AuditLog.objects.create(
            actor=self.admin, entity_type="property", entity_id=prop.id,
            action="create", description="seeded",
        )
        audit_count_before = AuditLog.objects.count()

        self._run("--confirm", "--noinput")

        self.assertEqual(Property.objects.count(), 0)
        self.assertEqual(Section.objects.count(), 0)
        self.assertEqual(Unit.objects.count(), 0)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Occupancy.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(Receipt.objects.count(), 0)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), audit_count_before)

    def test_unknown_row_blocks_confirm_without_allow_unknown(self):
        _make_demo_property()
        # Matches the TEST naming pattern but is still active -- only one of the
        # two required signals, so it must classify UNKNOWN, not TEST.
        Property.objects.create(name="AUDIT-TEST Property", code="AUD2", is_active=True)

        with self.assertRaises(CommandError):
            call_command("reset_live_data", "--confirm", "--noinput", stdout=StringIO())

        self.assertEqual(Property.objects.count(), 2)

    def test_allow_unknown_still_never_deletes_unknown_rows(self):
        _make_demo_property()
        unknown_prop = Property.objects.create(name="Some Real Client Property", code="RCP", is_active=True)

        self._run("--confirm", "--noinput", "--allow-unknown")

        self.assertTrue(Property.objects.filter(id=unknown_prop.id).exists())
        self.assertEqual(Property.objects.count(), 1)

    def test_confirm_twice_is_a_safe_noop(self):
        _make_demo_property()
        self._run("--confirm", "--noinput")
        self.assertEqual(Property.objects.count(), 0)

        output = self._run("--confirm", "--noinput")
        self.assertIn("removed 0 properties", output)

    def test_dry_run_and_confirm_together_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command("reset_live_data", "--dry-run", "--confirm", stdout=StringIO())
