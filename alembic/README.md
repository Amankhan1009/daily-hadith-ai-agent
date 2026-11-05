# Database Migrations (`alembic/`)

This directory contains database schema migrations for the **Daily Hadith AI Agent** managed via [Alembic](https://alembic.sqlalchemy.org/).

Migrations track database schema evolution across environments (local SQLite development and cloud Neon PostgreSQL production) with zero data loss.

---

## Directory Structure

```
alembic/
├── versions/               # Timestamped schema revision scripts
│   └── f02e818f721d_initial_schema.py  # Baseline schema migration
├── env.py                  # Migration runner connecting SQLAlchemy Base to target DB
├── script.py.mako          # Template for newly generated migration scripts
└── README.md               # Directory guide (this file)
```

---

## Key Tables Managed

1. **`hadith_candidates`**: Stores raw and verified Hadith texts, collection citations, Hadith numbers, canonical URLs, and verification statuses (`VERIFIED`, `REJECTED`, `PENDING`).
2. **`daily_delivery_logs`**: Tracks daily notification dispatches and carries a strict `UNIQUE` constraint on `scheduled_date` to enforce daily delivery idempotency.

---

## Common Migration Commands

### Check Current Migration Status
```bash
.venv/bin/alembic current
```

### Apply All Pending Migrations to Head
```bash
.venv/bin/alembic upgrade head
```

### Create a New Automatic Schema Migration
```bash
.venv/bin/alembic revision --autogenerate -m "describe_schema_changes"
```

### Rollback the Last Applied Migration
```bash
.venv/bin/alembic downgrade -1
```

