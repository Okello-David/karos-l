# KarosL

[![CI](https://github.com/Okello-David/karos-l/actions/workflows/ci.yml/badge.svg)](https://github.com/Okello-David/karos-l/actions/workflows/ci.yml)

An accommodation-management platform: Django REST Framework + React (Vite), with PostgreSQL in production
and SQLite for local development.

CI runs the backend suite against **both SQLite and PostgreSQL**, the frontend lint/test/build, and a
build of both Docker images — on pushes to `dev` and `cloud-deployment`, and on every pull request.
See `.github/workflows/ci.yml`.

## Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker (production-like)

```bash
cp .env.example .env   # then set real values
docker compose up --build
```

## Docs

`docs/DEVOPS.md` (architecture, logging, backup & recovery), `docs/DEPLOYMENT.md` (build/run/verify),
`docs/AWS_DEPLOYMENT_PLAN.md` (the phased cloud path), `docs/PROJECT_STATE.md` (where things stand).
