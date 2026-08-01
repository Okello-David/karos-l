"""Seed a realistic demo dataset.

Built for showing the app to someone, so the data has to look like a real
hostel rather than "Test Property 1". It goes through the same service layer
the UI uses -- AdminService, StudentService, OccupancyService, PaymentService --
rather than writing rows directly, so everything it creates obeys the real
validation, pricing and receipt-generation rules. A demo dataset that could not
have been produced through the UI would be worse than no dataset at all.

Occupancy is deliberately uneven: some units full, some partly filled, some
empty. The Property Explorer's traffic-light visualisation is the strongest
surface in the app, and it only shows anything if the data exercises all three
states.

    python manage.py seed_demo_data            # refuses if business data exists
    python manage.py seed_demo_data --reset    # wipes business data first
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.administration.services import AdminService
from apps.occupancy.models import Occupancy
from apps.occupancy.services import OccupancyService
from apps.occupants.models import Student
from apps.occupants.services import StudentService
from apps.payments.models import Payment, Receipt
from apps.payments.services import PaymentService
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit

TODAY = date.today()

PROPERTIES = [
    {
        "name": "Kikoni Heights",
        "code": "KIK",
        "address": "Plot 24, Kikoni, Makerere, Kampala",
        "description": "Purpose-built student accommodation a short walk from Makerere University.",
        "sections": [
            {
                "name": "Block A",
                "units": [
                    ("A-101", 2, "1200000.00", "300000.00"),
                    ("A-102", 2, "1200000.00", "300000.00"),
                    ("A-103", 3, "1000000.00", "260000.00"),
                    ("A-104", 1, "1600000.00", "400000.00"),
                ],
            },
            {
                "name": "Block B",
                "units": [
                    ("B-201", 2, "1250000.00", "310000.00"),
                    ("B-202", 4, "900000.00", "240000.00"),
                    ("B-203", 2, "1250000.00", "310000.00"),
                ],
            },
        ],
    },
    {
        "name": "Wandegeya Court",
        "code": "WDG",
        "address": "Bombo Road, Wandegeya, Kampala",
        "description": "Self-contained units with 24-hour security and back-up power.",
        "sections": [
            {
                "name": "Main Wing",
                "units": [
                    ("W-01", 1, "1500000.00", "380000.00"),
                    ("W-02", 2, "1150000.00", "290000.00"),
                    ("W-03", 2, "1150000.00", "290000.00"),
                    ("W-04", 3, "950000.00", "250000.00"),
                ],
            },
        ],
    },
]

# (first, last, phone suffix, billing mode, unit name or None for unassigned)
OCCUPANTS = [
    ("Aisha",    "Nakato",    "701", "semester", "A-101"),
    ("Brian",    "Okello",    "702", "semester", "A-101"),   # A-101 now full (2/2)
    ("Cynthia",  "Auma",      "703", "semester", "A-102"),   # A-102 half full
    ("David",    "Mugisha",   "704", "monthly",  "A-103"),
    ("Esther",   "Nabirye",   "705", "semester", "A-103"),   # A-103 2/3
    ("Farouk",   "Ssebugwawo", "706", "semester", "A-104"),  # A-104 full (1/1)
    ("Grace",    "Atim",      "707", "monthly",  "B-201"),
    ("Henry",    "Kato",      "708", "semester", "B-202"),
    ("Irene",    "Namusoke",  "709", "semester", "B-202"),
    ("Joseph",   "Wamala",    "710", "monthly",  "B-202"),   # B-202 3/4
    ("Kevin",    "Tumwine",   "711", "semester", "W-01"),    # W-01 full (1/1)
    ("Lydia",    "Achieng",   "712", "semester", "W-02"),
    ("Moses",    "Kigongo",   "713", "semester", "W-02"),    # W-02 full (2/2)
    ("Nancy",    "Birungi",   "714", "monthly",  "W-04"),
    ("Oscar",    "Mubiru",    "715", "semester", None),      # registered, not yet placed
    ("Patricia", "Nalwoga",   "716", "semester", None),
]
# B-203 and W-03 are left deliberately empty so the Explorer shows vacant units.

# (occupant index, amount, days ago, method, reference)
# A mix of paid-in-full, part-paid, and nothing-yet, so balances are non-trivial
# and the overdue widget has something real to show.
PAYMENTS = [
    (0,  "1200000.00", 40, "transfer", "TRX-88213"),   # fully paid
    (1,  "600000.00",  38, "cash",     ""),            # half paid
    (2,  "1200000.00", 35, "transfer", "TRX-88240"),   # overpaid vs 1.2m -> settled
    (3,  "300000.00",  30, "cash",     ""),            # monthly, partial
    (4,  "400000.00",  28, "card",     "CD-4471"),
    (5,  "1600000.00", 25, "transfer", "TRX-88311"),   # fully paid
    (6,  "310000.00",  20, "cash",     ""),
    (7,  "450000.00",  18, "cash",     ""),
    (8,  "900000.00",  15, "transfer", "TRX-88402"),   # fully paid
    (10, "1500000.00", 12, "transfer", "TRX-88455"),   # fully paid
    (11, "500000.00",  9,  "card",     "CD-4502"),
    (12, "1150000.00", 6,  "transfer", "TRX-88510"),   # fully paid
    (13, "250000.00",  3,  "cash",     ""),
    # Occupants 9 and 14/15 have paid nothing -- deliberate, so arrears exist.
]


class Command(BaseCommand):
    help = "Seed a realistic demo dataset for showing the app. Not for production use."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing business data first. Users and the audit log are never touched.",
        )

    def handle(self, *args, **options):
        existing = self._count_business_rows()

        if existing and not options["reset"]:
            raise CommandError(
                f"Refusing to run: the database already holds business data ({existing}).\n"
                "Re-run with --reset to replace it, or point DB_NAME at an empty database.\n"
                "Nothing has been changed."
            )

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            self._seed()

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded."))
        self.stdout.write(f"  {Property.objects.count()} properties, "
                          f"{Section.objects.count()} sections, "
                          f"{Unit.objects.count()} units")
        self.stdout.write(f"  {Student.objects.count()} occupants, "
                          f"{Occupancy.objects.filter(end_date__isnull=True).count()} active occupancies")
        self.stdout.write(f"  {Payment.objects.count()} payments, "
                          f"{Receipt.objects.count()} receipts")

    # ------------------------------------------------------------------
    def _count_business_rows(self):
        counts = {
            "properties": Property.objects.count(),
            "occupants": Student.objects.count(),
            "payments": Payment.objects.count(),
        }
        present = {k: v for k, v in counts.items() if v}
        return ", ".join(f"{v} {k}" for k, v in present.items())

    def _reset(self):
        """Delete business data only.

        Users, auth tokens, and the audit log are deliberately left alone: the
        audit trail is meant to be immutable, and it is also the record that
        this deletion happened. Order matters -- several foreign keys use
        on_delete=RESTRICT, so children must go first.
        """
        self.stdout.write(self.style.WARNING("--reset: deleting existing business data..."))
        for label, qs in [
            ("receipts", Receipt.objects.all()),
            ("payments", Payment.objects.all()),
            ("occupancies", Occupancy.objects.all()),
            ("occupants", Student.objects.all()),
            ("pricing rules", PricingRule.objects.all()),
            ("units", Unit.objects.all()),
            ("sections", Section.objects.all()),
            ("properties", Property.objects.all()),
        ]:
            deleted, _ = qs.delete()
            if deleted:
                self.stdout.write(f"    removed {deleted} {label}")

    def _seed(self):
        units_by_name = {}

        self.stdout.write("Creating properties, sections and units...")
        for prop_spec in PROPERTIES:
            prop = AdminService.create_property({
                "name": prop_spec["name"],
                "code": prop_spec["code"],
                "address": prop_spec["address"],
                "description": prop_spec["description"],
            })
            for order, section_spec in enumerate(prop_spec["sections"]):
                section = AdminService.create_section({
                    "property": prop,
                    "name": section_spec["name"],
                    "order": order,
                })
                for unit_order, (name, capacity, semester, monthly) in enumerate(section_spec["units"]):
                    units_by_name[name] = AdminService.create_unit({
                        "section": section,
                        "name": name,
                        "capacity": capacity,
                        "order": unit_order,
                        "semester_price": Decimal(semester),
                        "monthly_price": Decimal(monthly),
                    })

        self.stdout.write("Registering occupants and assigning units...")
        students = []
        for index, (first, last, suffix, billing_mode, unit_name) in enumerate(OCCUPANTS):
            student = StudentService.create_student({
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}@example.com",
                "phone": f"+2567{suffix}{100000 + index:06d}"[:20],
                "student_id_number": f"STU-{2026}-{index + 1:03d}",
                "national_id": f"CM{90000000 + index}UG",
            })
            students.append(student)

            if unit_name:
                # Staggered start dates so occupancy history looks lived-in
                # rather than everyone arriving on the same day.
                OccupancyService.assign_student(
                    student_id=student.id,
                    unit_id=units_by_name[unit_name].id,
                    start_date=TODAY - timedelta(days=60 - index),
                    billing_mode=billing_mode,
                )

        self.stdout.write("Recording payments...")
        for occupant_index, amount, days_ago, method, reference in PAYMENTS:
            PaymentService.record_payment(
                student_id=students[occupant_index].id,
                amount=Decimal(amount),
                payment_date=TODAY - timedelta(days=days_ago),
                payment_method=method,
                reference=reference,
                notes="",
            )
