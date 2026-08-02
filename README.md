# Elite Dashboard

Production-ready Flask application for college elite batch task management, submissions, approvals, point ledger, leaderboard, support messages, and Excel reports.

## Stack

- Flask
- Flask-Login
- Flask-SQLAlchemy
- Flask-Migrate
- PostgreSQL for production
- SQLite only as a local fallback or migration source
- Render deployment support

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://username:password@host:5432/database_name
```

If `DATABASE_URL` is absent, the app falls back to `instance/elite_dashboard.sqlite3` for local development only.

## Database Migrations

Do not use `db.create_all()` in production.

Create or update tables with Flask-Migrate:

```bash
python -m flask --app run.py db upgrade
```

Create a new migration after model changes:

```bash
python -m flask --app run.py db migrate -m "describe change"
python -m flask --app run.py db upgrade
```

## Manual Seed Commands

The app does not auto-seed users or tasks on startup.

Create the first admin manually:

```bash
python -m flask --app run.py seed-admin
```

Seed the task catalog manually:

```bash
python -m flask --app run.py seed-task-catalog
```

Default seeded admin:

- Email: `admin@elite.edu`
- Password: `Admin@123`

Change this password after first login in a real deployment.

## SQLite To PostgreSQL Migration

Your SQLite database remains untouched at:

```txt
instance/elite_dashboard.sqlite3
```

Before migration:

1. Back up `instance/elite_dashboard.sqlite3`.
2. Set PostgreSQL `DATABASE_URL` in `.env`.
3. Run migrations on PostgreSQL:

```bash
python -m flask --app run.py db upgrade
```

Then migrate data:

```bash
python scripts/migrate_sqlite_to_postgres.py
```

Verify row counts and relationships:

```bash
python scripts/verify_postgres_migration.py
```

The migration script is idempotent. Existing primary keys are skipped, IDs are preserved, and password hashes are copied as-is.

## Render Deployment

This repo includes:

- `Procfile`
- `runtime.txt`
- `render.yaml`
- `requirements.txt`

On Render:

1. Push this project to GitHub.
2. Create a Render PostgreSQL database.
3. Create a Render Web Service from the GitHub repo.
4. Set environment variables:
   - `SECRET_KEY`
   - `DATABASE_URL`
5. Build command:

```bash
pip install -r requirements.txt && flask --app run.py db upgrade
```

6. Start command:

```bash
gunicorn run:app
```

## GitHub

The `.gitignore` excludes:

- `.env`
- virtual environments
- Python cache files
- SQLite database files
- uploaded files

Push with:

```bash
git init
git add .
git commit -m "Prepare Elite Dashboard for PostgreSQL deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## Restore Backup

To return to local SQLite development, remove or comment `DATABASE_URL` in `.env`, restore your backed up SQLite file to:

```txt
instance/elite_dashboard.sqlite3
```

Then run:

```bash
python -m flask --app run.py run --debug
```
