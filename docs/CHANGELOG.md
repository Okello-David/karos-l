# Changelog

## [Unreleased]

### Added
- Project foundation: Django backend with DRF, CORS, env support, custom User model, 8 apps
- React frontend with Vite, Tailwind CSS, placeholder pages, responsive sidebar layout
- Project documentation: VISION, REQUIREMENTS, DATABASE, WORKFLOWS, ROADMAP, CHANGELOG, MEETING_NOTES

### Database Models (Sprint 2)

- **Property** — name, code (unique), address, description, is_active, timestamps
- **Section** — FK to Property, name, description, is_active, timestamps; unique constraint on (property, name)
- **Unit** — FK to Section, name, capacity, semester_price, monthly_price, is_active, timestamps; unique constraint on (section, name); indexes on capacity and is_active
- **Student** — first_name, last_name, email (unique), phone, student_id_number (unique), is_active, timestamps; index on (last_name, first_name)
- **Occupancy** — FK to Student, FK to Unit, start_date, end_date (nullable), billing_mode, is_active, created_at; check constraint on end_date > start_date; partial unique indexes on active student and active unit; model-level validation prevents duplicate active occupancy
- **Payment** — FK to Student, amount, payment_date, payment_method, reference, notes, timestamps; indexes on (student, payment_date) and payment_date

All models registered in Django Admin with search, filters, date hierarchy, and related field displays.

### Admin Improvements (Sprint 3)

- **PropertyAdmin** — SectionInline (name, is_active), fieldsets with collapsed audit section, `section_count` display column
- **SectionAdmin** — UnitInline (name, capacity, prices, is_active), `autocomplete_fields` for property, `list_select_related`, `unit_count` column
- **UnitAdmin** — OccupancyInline (student, dates, billing_mode), `autocomplete_fields` for section, `list_select_related`, `occupancy_status` column showing current/capacity
- **StudentAdmin** — OccupancyInline and PaymentInline with ordering, fieldsets, `get_queryset` uses `Prefetch` with `select_related` to avoid N+1 on `current_unit`, fullname and student ID in search
- **OccupancyAdmin** — `autocomplete_fields` for student and unit, `list_select_related`, fieldsets, student ID number in search
- **PaymentAdmin** — `autocomplete_fields` for student, `list_select_related`, fieldsets, student ID number in search
- **UserAdmin** — custom `fieldsets` and `add_fieldsets`, `readonly_fields` for `last_login` and `date_joined`
- Cross-app inlines provide hierarchical navigation: Property → Section → Unit → Occupancy
- All list views include `list_select_related` or `prefetch_related` to minimize database queries
