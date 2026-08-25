"""One-time cutover tool: classify and remove confirmed demo/test business data
ahead of real onboarding, without touching users or the audit log.

Classification is conservative by design: a row is only ever DEMO or TEST when
it unambiguously matches this project's established naming/seed conventions
(the seed_demo_data dataset, and the AUDIT-TEST / RDS-MIGRATION-TEST-DELETE-ME
verification passes documented in docs/LIVE_DATA_AUDIT.md). Anything else --
including real data -- is UNKNOWN and is never deleted. Classification is
recomputed fresh on every invocation, never cached, so re-running is safe.

    python manage.py reset_live_data                # dry-run report only
    python manage.py reset_live_data --confirm       # delete DEMO+TEST rows
"""

import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.payments.models import Payment, Receipt
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit

DEMO = "DEMO"
TEST = "TEST"
UNKNOWN = "UNKNOWN"

DEMO_PROPERTY_CODES = {"KIK", "WDG"}
DEMO_PROPERTY_NAMES = {"Kikoni Heights", "Wandegeya Court"}
TEST_NAME_RE = re.compile(r"AUDIT-TEST|RDS-MIGRATION-TEST|DELETE-ME", re.IGNORECASE)
DEMO_EMAIL_RE = re.compile(r"^[^@]+@example\.com$", re.IGNORECASE)
DEMO_STUDENT_ID_RE = re.compile(r"^STU-\d{4}-\d{3}$")

CONFIRM_PHRASE = "DELETE DEMO AND TEST DATA"

MODEL_LABELS = [
    "properties", "sections", "units", "pricing_rules",
    "students", "occupancies", "payments", "receipts",
]
DELETE_ORDER = [
    "receipts", "payments", "occupancies", "students",
    "pricing_rules", "units", "sections", "properties",
]


def _classify_property(prop):
    if prop.code in DEMO_PROPERTY_CODES:
        return DEMO
    name_matches = bool(TEST_NAME_RE.search(prop.name) or TEST_NAME_RE.search(prop.code))
    if name_matches and not prop.is_active:
        return TEST
    return UNKNOWN


def _classify_student_pattern(student):
    """Fallback signal for students unreachable via occupancy (e.g. unassigned)."""
    email_ok = bool(student.email and DEMO_EMAIL_RE.match(student.email))
    id_ok = bool(student.student_id_number and DEMO_STUDENT_ID_RE.match(student.student_id_number))
    if email_ok and id_ok:
        return DEMO
    name_or_id_test = bool(
        TEST_NAME_RE.search(student.first_name)
        or TEST_NAME_RE.search(student.last_name)
        or (student.student_id_number and TEST_NAME_RE.search(student.student_id_number))
    )
    if name_or_id_test:
        return TEST
    return None


class Classification:
    """A fresh classify-everything snapshot of the current DB state."""

    def __init__(self):
        self.properties = {}
        self.sections = {}
        self.units = {}
        self.pricing_rules = {}
        self.students = {}
        self.occupancies = {}
        self.payments = {}
        self.receipts = {}
        self.unknown_detail = {label: [] for label in MODEL_LABELS}
        self._compute()

    def _mark_unknown(self, label, cls, detail):
        if cls == UNKNOWN:
            self.unknown_detail[label].append(detail)

    def _compute(self):
        for prop in Property.objects.all():
            cls = _classify_property(prop)
            self.properties[prop.id] = cls
            self._mark_unknown(
                "properties", cls,
                f"id={prop.id} code={prop.code!r} name={prop.name!r} is_active={prop.is_active}",
            )

        for section in Section.objects.all():
            cls = self.properties.get(section.property_id, UNKNOWN)
            self.sections[section.id] = cls
            self._mark_unknown(
                "sections", cls,
                f"id={section.id} name={section.name!r} property_id={section.property_id}",
            )

        for unit in Unit.objects.all():
            # Unit.is_active is self-derived from status, not cascaded from the
            # parent -- classification must come from the section chain only.
            cls = self.sections.get(unit.section_id, UNKNOWN)
            self.units[unit.id] = cls
            self._mark_unknown(
                "units", cls,
                f"id={unit.id} name={unit.name!r} section_id={unit.section_id}",
            )

        for rule in PricingRule.objects.all():
            cls = self.units.get(rule.unit_id, UNKNOWN)
            self.pricing_rules[rule.id] = cls
            self._mark_unknown("pricing_rules", cls, f"id={rule.id} unit_id={rule.unit_id}")

        occ_classes_by_student = {}
        for occ in Occupancy.objects.all():
            unit_cls = self.units.get(occ.unit_id, UNKNOWN)
            occ_classes_by_student.setdefault(occ.student_id, set()).add(unit_cls)

        for student in Student.objects.all():
            occ_classes = occ_classes_by_student.get(student.id, set())
            if occ_classes == {DEMO}:
                occ_result = DEMO
            elif occ_classes == {TEST}:
                occ_result = TEST
            elif occ_classes:
                occ_result = UNKNOWN  # mixed, or touches an UNKNOWN unit
            else:
                occ_result = None  # no occupancy at all -- fall back to pattern

            pattern_result = _classify_student_pattern(student)

            if occ_result is None:
                final = pattern_result or UNKNOWN
            elif occ_result == UNKNOWN:
                final = UNKNOWN
            elif pattern_result is None or pattern_result == occ_result:
                final = occ_result
            else:
                final = UNKNOWN  # occupancy and naming disagree -- don't guess

            self.students[student.id] = final
            self._mark_unknown(
                "students", final,
                f"id={student.id} name={student.full_name()!r} email={student.email!r} "
                f"student_id_number={student.student_id_number!r}",
            )

        for occ in Occupancy.objects.all():
            unit_cls = self.units.get(occ.unit_id, UNKNOWN)
            student_cls = self.students.get(occ.student_id, UNKNOWN)
            cls = unit_cls if unit_cls == student_cls else UNKNOWN
            self.occupancies[occ.id] = cls
            self._mark_unknown(
                "occupancies", cls,
                f"id={occ.id} student_id={occ.student_id} unit_id={occ.unit_id} "
                f"(unit={unit_cls}, student={student_cls})",
            )

        for payment in Payment.objects.all():
            cls = self.students.get(payment.student_id, UNKNOWN)
            self.payments[payment.id] = cls
            self._mark_unknown("payments", cls, f"id={payment.id} student_id={payment.student_id}")

        for receipt in Receipt.objects.all():
            cls = self.payments.get(receipt.payment_id, UNKNOWN)
            # Cross-check against the receipt's own denormalized snapshot.
            if cls == DEMO and receipt.property_name not in DEMO_PROPERTY_NAMES:
                cls = UNKNOWN
            if cls == TEST and not TEST_NAME_RE.search(receipt.property_name):
                cls = UNKNOWN
            self.receipts[receipt.id] = cls
            self._mark_unknown(
                "receipts", cls,
                f"id={receipt.id} receipt_number={receipt.receipt_number!r} "
                f"property_name={receipt.property_name!r}",
            )

    def _map(self, label):
        return {
            "properties": self.properties, "sections": self.sections, "units": self.units,
            "pricing_rules": self.pricing_rules, "students": self.students,
            "occupancies": self.occupancies, "payments": self.payments, "receipts": self.receipts,
        }[label]

    def counts(self, label):
        mapping = self._map(label)
        return {
            "total": len(mapping),
            DEMO: sum(1 for v in mapping.values() if v == DEMO),
            TEST: sum(1 for v in mapping.values() if v == TEST),
            UNKNOWN: sum(1 for v in mapping.values() if v == UNKNOWN),
        }

    def delete_ids(self, label):
        return [pk for pk, cls in self._map(label).items() if cls in (DEMO, TEST)]

    def total_unknown(self):
        return sum(self.counts(label)[UNKNOWN] for label in MODEL_LABELS)


class Command(BaseCommand):
    help = (
        "One-time cutover tool: classify and remove confirmed demo/test business "
        "data (seed_demo_data plus prior AUDIT-TEST/RDS-MIGRATION-TEST passes) "
        "ahead of real onboarding. Never touches users or the audit log. "
        "Defaults to a dry-run report; pass --confirm to actually delete."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only (default behavior).")
        parser.add_argument("--confirm", action="store_true", help="Delete the classified DEMO+TEST rows.")
        parser.add_argument(
            "--allow-unknown", action="store_true",
            help="Proceed with --confirm even though UNKNOWN rows exist elsewhere. "
                 "UNKNOWN rows are still never deleted.",
        )
        parser.add_argument(
            "--noinput", action="store_true",
            help="Skip the typed confirmation prompt (still requires --confirm).",
        )

    def handle(self, *args, **options):
        if options["dry_run"] and options["confirm"]:
            raise CommandError("--dry-run and --confirm are mutually exclusive.")

        classification = Classification()
        self._print_report(classification)

        if not options["confirm"]:
            return

        unknown_total = classification.total_unknown()
        if unknown_total and not options["allow_unknown"]:
            raise CommandError(
                f"{unknown_total} UNKNOWN row(s) found -- refusing to proceed. "
                "Review the report above, or pass --allow-unknown to proceed leaving them untouched."
            )

        if not options["noinput"]:
            self.stdout.write("")
            typed = input(f"Type '{CONFIRM_PHRASE}' to delete the DEMO+TEST rows listed above: ")
            if typed != CONFIRM_PHRASE:
                raise CommandError("Confirmation phrase did not match. Nothing was deleted.")

        with transaction.atomic():
            self.stdout.write(self.style.WARNING("\nDeleting classified demo/test rows..."))
            querysets = {
                "receipts": Receipt.objects.filter(id__in=classification.delete_ids("receipts")),
                "payments": Payment.objects.filter(id__in=classification.delete_ids("payments")),
                "occupancies": Occupancy.objects.filter(id__in=classification.delete_ids("occupancies")),
                "students": Student.objects.filter(id__in=classification.delete_ids("students")),
                "pricing_rules": PricingRule.objects.filter(id__in=classification.delete_ids("pricing_rules")),
                "units": Unit.objects.filter(id__in=classification.delete_ids("units")),
                "sections": Section.objects.filter(id__in=classification.delete_ids("sections")),
                "properties": Property.objects.filter(id__in=classification.delete_ids("properties")),
            }
            for label in DELETE_ORDER:
                deleted, _ = querysets[label].delete()
                self.stdout.write(f"    removed {deleted} {label}")

        self.stdout.write(self.style.SUCCESS("\nDone. Users and the audit log were not touched."))

    def _print_report(self, classification):
        self.stdout.write(self.style.MIGRATE_HEADING("Live data classification report"))
        for label in MODEL_LABELS:
            c = classification.counts(label)
            self.stdout.write(
                f"  {label:14s} total={c['total']:4d}  demo={c[DEMO]:4d}  "
                f"test={c[TEST]:4d}  unknown={c[UNKNOWN]:4d}"
            )
            for detail in classification.unknown_detail[label]:
                self.stdout.write(self.style.WARNING(f"      UNKNOWN: {detail}"))

        total_unknown = classification.total_unknown()
        if total_unknown:
            self.stdout.write(
                self.style.WARNING(f"\n{total_unknown} UNKNOWN row(s) -- these will never be auto-deleted.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo UNKNOWN rows -- everything present is classified DEMO or TEST."))
