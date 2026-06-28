# Development Guide

## Project Structure

```
backend/
├── apps/
│   ├── core/              # Shared infrastructure
│   │   ├── constants.py   # Enum-like choices (BillingMode, PaymentMethod)
│   │   ├── exceptions.py  # Base exception classes
│   │   ├── mixins.py      # Reusable model mixins (TimeStampedModel)
│   │   ├── permissions.py # Permission classes (future)
│   │   ├── utils.py       # Pure utility functions
│   │   └── validators.py  # Shared field validators (validate_positive)
│   ├── accounts/          # System users (auth)
│   ├── properties/        # Property management
│   │   └── services/      # Property business logic (future)
│   ├── sections/          # Section management
│   │   └── services/      # Section business logic (future)
│   ├── units/             # Unit management
│   │   └── services/      # Unit business logic (future)
│   ├── occupants/         # Student occupants
│   │   └── services/      # Occupant business logic (future)
│   ├── occupancy/         # Occupancy records
│   │   └── services/      # Occupancy business logic (future)
│   ├── payments/          # Payment records
│   │   └── services/      # Payment business logic (future)
│   └── dashboard/         # Reporting and views
│       └── services/      # Dashboard business logic (future)
├── config/
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL configuration
│   └── wsgi.py            # WSGI application
├── .env                   # Environment variables (gitignored)
├── manage.py
└── requirements.txt
```

## Naming Conventions

| Layer | Convention | Example |
|---|---|---|
| Models | Singular noun, PascalCase | `Property`, `Occupancy` |
| Model fields | snake_case | `start_date`, `billing_mode` |
| Model methods | snake_case | `current_occupant_count()`, `is_full()` |
| Services | Verb-based, PascalCase | `PropertyService`, `AssignUnitService` |
| Service methods | snake_case | `assign_student()`, `record_payment()` |
| Serializers | PascalCase | `PropertySerializer` |
| Views / ViewSets | PascalCase | `PropertyViewSet` |
| URLs | kebab-case | `/api/properties/` |
| Migrations | Auto-generated | `0001_initial.py` |
| Tests | `test_<scenario>` | `test_assign_student_to_full_unit` |
| Constants | UPPER_SNAKE_CASE | `MAX_CAPACITY` |
| Module-level vars | snake_case | `_db_name` |

## Where Business Logic Belongs

### Services Layer (`services/`)

All business logic lives in service classes or functions inside the `services/` package of each app.

- Services receive typed inputs and raise typed exceptions.
- Services do NOT know about HTTP, serializers, or request objects.
- Services return domain objects or simple data structures.

Example service signature:

```python
# occupants/services.py
def register_student(first_name: str, last_name: str, email: str) -> Student:
    ...
```

### Models

Models are responsible for:

- Data definition (fields, constraints, indexes)
- Basic query helpers (`current_occupant_count()`)
- String representation (`__str__`)
- Validation that is intrinsic to the field (validators on the field definition)

Models are NOT responsible for:

- Cross-entity business rules
- Complex queries involving multiple models
- Triggering side effects (emails, notifications)

### Views / ViewSets (future)

Views are responsible for:

- Handling HTTP requests and responses
- Authentication and permission checks
- Serialization and deserialization
- Calling services and returning results

Views are NOT responsible for:

- Business logic
- Database queries beyond simple lookups

## Service Layer Usage

1. Create a service function or class in the appropriate `services/` module.
2. The service accepts primitives or model instances as parameters.
3. The service raises custom exceptions from `apps.core.exceptions`.
4. The caller (view, management command, test) catches exceptions and translates them to the appropriate response.

```python
# occupancy/services.py
from apps.core.exceptions import ConflictError
from apps.occupants.models import Student
from apps.occupancy.models import Occupancy

def assign_student_to_unit(student: Student, unit_id: int) -> Occupancy:
    if Occupancy.objects.filter(student=student, end_date__isnull=True).exists():
        raise ConflictError("Student already has an active occupancy.")
    ...
```

## Documentation Expectations

- All public service functions must have a docstring describing parameters and return value.
- Complex business rules must reference the relevant section in `docs/DATABASE.md` or `docs/WORKFLOWS.md`.
- Model fields with non-obvious semantics must have `help_text`.
- Every app must have at least one `services/` module if it contains business logic.

## Model Responsibilities

- `__str__` must be concise and useful in admin dropdowns.
- `Meta.ordering` must be set for consistent list views.
- `verbose_name` / `verbose_name_plural` set where plural is irregular.
- Constraints and indexes are defined in `Meta`, not in raw SQL.
- `clean()` is used for model-level validation that spans multiple fields.
- Override `save()` only when `full_clean()` must be enforced.

## Authentication

### Approach

KarosL uses **Token Authentication** (`rest_framework.authtoken`).

**Rationale:** Token-based auth avoids CSRF concerns inherent in cookie-based auth with SPAs. The client stores the token and sends it via the `Authorization: Token <key>` header. Token revocation is immediate (DELETE from the `authtoken_token` table). No additional libraries are needed beyond DRF itself.

JWT was considered but rejected for this project: the system has a single owner operator, there is no mobile app, and the simplicity of server-side token storage outweighs the scalability benefits of stateless JWT.

### Endpoints

| Method | URL | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login/` | None | Returns token + user data |
| POST | `/api/auth/logout/` | Token | Deletes the current token |
| GET | `/api/auth/me/` | Token | Returns authenticated user profile |

### Login Response

```json
{
    "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
    "user": {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "first_name": "",
        "last_name": "",
        "is_staff": true,
        "is_superuser": true,
        "groups": []
    }
}
```

### Client Usage

```javascript
// Login
const res = await fetch('/api/auth/login/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username, password})
});
const {token, user} = await res.json();

// Subsequent requests
fetch('/api/auth/me/', {
    headers: {'Authorization': `Token ${token}`}
});

// Logout
fetch('/api/auth/logout/', {
    method: 'POST',
    headers: {'Authorization': `Token ${token}`}
});
```

## Authorization

### Roles

| Role | Implementation | Description |
|---|---|---|
| **Super Administrator** | `is_superuser = True` | Full system access. Created via `createsuperuser`. |
| **Property Manager** | Django Group: "Property Manager" | Manages properties, sections, units, students. |
| **Staff** | Django Group: "Staff" | Read-only or limited operational access. |

Default groups ("Property Manager", "Staff") are automatically created by a `post_migrate` signal in `apps/accounts/apps.py`.

### Permission Classes (`apps/core/permissions.py`)

| Class | Behaviour |
|---|---|
| `IsSuperAdmin` | Superuser only |
| `IsPropertyManager` | Property Manager group or superuser |
| `IsStaff` | Any user with `is_staff=True` |
| `IsStaffOrSuperAdmin` | Staff or superuser |
| `HasGroupPermission` | Configurable — checks `view.required_groups` against user's groups |

These are reusable across all future API viewsets.

## Testing

- Unit tests for services go in `tests/` of each app.
- Tests should use factories, not fixtures, for test data.
- Every service function must have tests for the happy path and all error paths.
