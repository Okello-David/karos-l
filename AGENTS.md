# KarosL - Agent Summary

## Architecture

- **Backend**: Django 5.2 + Django REST Framework + SQLite (dev) / PostgreSQL (prod)
- **Frontend**: React 19 + React Router 7 + Tailwind CSS 4 + Vite
- **Auth**: DRF Token auth (custom `/api/auth/login/`, `/api/auth/logout/`)
- **Permissions**: IsPropertyManager (group-based), IsStaff, IsSuperAdmin; `|` combos

## Backend Structure

```
backend/
  config/          settings, root urls
  apps/
    core/          base mixins (TimeStampedModel), exceptions (ConflictError, NotFoundError), permissions, validators, constants (BillingMode)
    accounts/      login/logout API views
    properties/    Property model (name, code, address, description, is_active)
    sections/      Section model (name, description, property FK, is_active, order)
    units/         Unit model (name, capacity, status=active/maintenance/archived, order, semester_price, monthly_price, section FK)
    occupants/     Student model with full CRUD + archive
    occupancy/     Occupancy model with assign/checkout/list/update services, agreed_price snapshot
    payments/      Payment model + Receipt model; record/list/balance/overdue services; auto-generated receipts; PDF download via reportlab
    dashboard/     DashboardView with summary stats endpoint
    administration/ Admin CRUD for properties/sections/units + pricing rules + user management
    audit/         AuditLog model, AuditService, views (list/detail/entity-types/actions), IsSuperAdmin
    backup/        Backup model, BackupService, ExportService (CSV/XLSX), views (list/create/detail/restore/validate/export), IsSuperAdmin
```
### Existing Serializers
- `PropertySerializer` — id, name only
- `SectionSerializer` — id, name, property
- `UnitSerializer` — id, name, capacity, current_occupant_count, available_spaces, is_full (SerializerMethodFields)
- `PropertyDetailSerializer` — nested Property → Section → Unit hierarchy with occupancy data
- `UnitExplorerSerializer` — unit card fields (name, capacity, occupancy count/percentage, active occupants, color status)
- `PaymentSerializer` — includes receipt_id, receipt_number computed fields
- `ReceiptSerializer` — full receipt snapshot (payment_id, receipt_number, issued_at, amount, balance, occupant/unit/property info)
- `AdminPropertySerializer` — full Property fields incl address, description, is_active
- `AdminSectionSerializer` — full Section fields incl property_name, is_active, order
- `AdminUnitSerializer` — full Unit fields incl section_name, property_name, status, order, pricing
- `PricingRuleSerializer` — unit_name, billing_mode, price, effective_date
- `AdminUserSerializer` — username, email, names, is_staff, is_superuser, groups, group_names

### Existing Backend Patterns
- Service classes with static methods (`OccupancyService`, `PaymentService`, `AuditService`)
- Paginated list endpoints returning `{ count, page, page_size, total_pages, results }`
- `NotFoundError` and `ConflictError` custom exceptions
- Permission classes: `IsAuthenticated | IsPropertyManager`
- `IsAuthenticated & IsSuperAdmin` for audit/backup endpoints (both must be true)

## Audit Trail Architecture

- **AuditLog model** (`apps/audit/models.py`): actor FK, entity_type (choices: occupant/occupancy/payment/receipt/property/section/unit/pricing_rule/user), entity_id, action (choices: create/update/delete/archive/assign/checkout/record_payment/login/other), description, changes (JSON), ip_address, timestamp (auto, indexed)
- **AuditService** (`apps/audit/services.py`): `log()` (creates entry), `list_logs()` (paginated with filters), `get_log()` (by pk)
- **Integration**: Audit calls are made in the **view layer** (not service layer), after successful operations. Each view file imports `AuditLog.EntityType`/`AuditLog.Action` enums and `AuditService.log()`.
- **Security**: All audit endpoints use `IsAuthenticated & IsSuperAdmin`
- **Endpoints**: `GET /api/audit/` (paginated list, filters), `GET /api/audit/<id>/` (detail), `GET /api/audit/entity-types/`, `GET /api/audit/actions/`
- **Frontend**: Audit tab integrated into Administration page; uses `useAuditLogs`/`useAuditMeta` hooks; timeline view with filters + detail panel

## Backup Architecture

- **Backup model** (`apps/backup/models.py`): created_by FK, status (pending/in_progress/completed/failed), file_path, file_size, metadata (JSON), notes, created_at
- **BackupService** (`apps/backup/services.py`): `create_backup()` serializes 8 models to JSON file, `list_backups()` paginated, `get_backup()` by pk, `validate_backup()` checks file integrity, `restore_backup()` transactional upsert
- **ExportService** (`apps/backup/services.py`): `export_occupants/occupancies/payments/receipts()` returns (content, filename, content_type) tuple for CSV or XLSX
- **Security**: All backup endpoints use `IsAuthenticated & IsSuperAdmin`
- **Endpoints**: `GET/POST /api/backups/` (list/create), `GET /api/backups/<id>/` (detail), `POST /api/backups/<id>/restore/`, `GET /api/backups/<id>/validate/`, `GET /api/backups/export/?entity=X&file_format=csv|xlsx`
- **Frontend**: Backup page at /backup with Create/Export/Restore cards, history table, RestoreWizard modal, ExportDialog modal
- **Note**: Use `file_format` query parameter (not `format`) to avoid DRF content negotiation conflict

## Frontend Structure

```
frontend/src/
  App.jsx           routes (Dashboard, Explorer, Properties, Occupants, Payments, Receipts, Reports, Backup, Administration)
  layouts/          MainLayout (Sidebar + Topbar + Outlet)
  pages/            Dashboard, Explorer, Properties, Occupants, OccupantDetail, OccupantForm, Payments, Receipts, Reports, Backup, Administration
  components/       Sidebar, Topbar, PageContainer, Card, Button, EmptyState, StatusBadge, ConfirmDialog, FormField, Spinner, SearchInput, RecordPaymentDialog, PaymentDetailDialog
  components/explorer/  PropertyNode, SectionNode, UnitNode, UnitDetailPanel
  services/         api.js (base client), occupants.js, payments.js, properties.js, occupancy.js, explorer.js, audit.js, backup.js
  hooks/            useOccupants, useOccupant, usePayments (includes useReceipts, useReceipt, useStudentBalance, useOverdueStudents, useStudentPaymentHistory), useOccupancy, useExplorer, useAudit, useBackup
```

### Sidebar Navigation
Overview (/), Explorer (/explorer), Properties (/properties), Occupants (/occupants), Payments (/payments), Receipts (/receipts), Reports (/reports), Backup (/backup), Administration (/administration)

## What's Been Built (Sprints)

### Sprint 1-7: Foundation
- Django project/apps scaffolded, React app scaffolded with Vite, Tailwind CSS configured
- Core app: TimeStampedModel, exceptions, permissions, validators, BillingMode constants
- Accounts app: DRF Token auth (login/logout)
- Properties, Sections, Units apps with models + list endpoints
- Sidebar/Topbar layout, routing, reusable component library
- Empty placeholder pages for all sections

### Sprint 8: Occupant Management (DONE)
- Backend: Student model, full CRUD, archive, serializers, views, urls, tests
- Frontend: occupantsService, useOccupants/useOccupant hooks, Occupants page (list, create, archive, search, pagination)

### Sprint 9: Occupancy Management (DONE)
- Backend: Occupancy model, OccupancyService (assign, checkout, list, update), views, urls, full test suite
- Frontend: occupancyService, useOccupancy hooks, Occupancy tab on Occupant detail page, unit occupancy indicators in assignment forms

### Sprint 10: Payment Management (DONE)
- Backend: Payment model, PaymentService (record, list, calculate_balance, overdue), views/urls
- Frontend: paymentsService, usePayments hook, Payments page (list, record, overdue), Dashboard widgets for recent payments + overdue count
- Dashboard view/service refactored out into its own app

### Sprint 11: Interactive Property Explorer (DONE)
- Backend: PropertyExplorerSerializer/SectionExplorerSerializer/UnitExplorerSerializer, PropertyExplorerView with search, UnitDetailView, 13 tests
- Frontend: explorer service, useExplorer hook, Explorer page, PropertyNode/SectionNode/UnitNode/UnitDetailPanel components, sidebar/route wiring, Dashboard link

### Sprint 12: Receipts & Transaction History (DONE)
- Backend: Receipt model (auto-generated RCP-YYYYMMDD-NNNN), auto-create via PaymentService, ReceiptSerializer, ReceiptViewSet (list/search/retrieve/pdf), PDF via reportlab, tests
- Frontend: receiptService + useReceipts hook, Receipts page (search, date-filter, paginated table, PDF download), receipt link in PaymentDetailDialog, sidebar nav item + route, link from Payments page

### Sprint 13: Administration Module (DONE)
- Model changes: Section.order, Unit.status/order (active/maintenance/archived), PricingRule model (effective-dated), Occupancy.agreed_price snapshot
- Backend: apps/administration/ with AdminPropertyViewSet, AdminSectionViewSet (incl reorder), AdminUnitViewSet, PricingRuleViewSet, AdminUserViewSet; AdminService layer with business rules; 39 tests
- Frontend: adminService + useAdmin hooks; 5-tab Administration page (Properties/Sections/Units/Pricing/Users); AdminFormDialog + ConfirmDialog for all CRUD operations; loading/error/empty states

### Sprint 14: Audit Trail (DONE)
- Backend: apps/audit/ with AuditLog model, AuditService, serializers, views, URLs; endpoints at /api/audit/ (list/detail/entity-types/actions); 20 tests
- Frontend: auditService + useAuditLogs/useAuditLog/useAuditMeta hooks; Audit Log tab in Administration page with timeline/filters/detail

### Sprint 15: Backup, Restore & Data Export (DONE)
- Backend: apps/backup/ with Backup model, BackupService (create/list/get/validate/restore), ExportService (CSV/XLSX for occupants/occupancies/payments/receipts), 4 APIView endpoints, /api/backups/export/ endpoint; 31 tests
- Frontend: backupService + useBackups/useBackup/useBackupAction hooks; Backup page (Create/Export/Restore cards, Backup History table, RestoreWizard modal, ExportDialog modal); route /backup + sidebar nav

## Key Observations
- Square brackets used in PaymentService (line 48, 54) but elsewhere `list()` is used. Follow existing patterns.

- Properties page is a placeholder; may be replaced/redirected to /explorer
