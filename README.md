# FinTech AI Agent

A Django 5.2 project using PostgreSQL.

## Requirements

- Python 3.12+
- PostgreSQL 14+

## Local setup (Linux/macOS)

Run these commands from the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the PostgreSQL database name, username, password, host, and port in `.env`. For example:

```dotenv
SECRET_KEY=replace-with-a-unique-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=fintech_db
DB_USER=fintech_user
DB_PASSWORD=your_secure_database_password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Generate a unique random key for `SECRET_KEY` while the virtual environment is active:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Make sure PostgreSQL is running. If the database or user does not exist yet, open `psql` as a PostgreSQL administrator and run:

```sql
CREATE USER fintech_user WITH PASSWORD 'your_secure_database_password';
CREATE DATABASE fintech_db OWNER fintech_user;
```

The database name, username, and password in these SQL statements must match `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in `.env`. Replace the example password with a secure password of your own.

## Database migration

From the repository root, apply the database migrations:

```bash
python AI_Agent/manage.py migrate
```

## Development server

```bash
python AI_Agent/manage.py runserver
```

Then open <http://127.0.0.1:8000/> in your browser. To use the Django admin site, create a superuser and open <http://127.0.0.1:8000/admin/>:

```bash
python AI_Agent/manage.py createsuperuser
```

## Security

- Never commit secrets or database credentials from `.env` to source control; `.env` is already listed in `.gitignore`.
- Set `DEBUG=False` in production and include only your domain in `ALLOWED_HOSTS`.
