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

## Email OTP setup

Registration sends a one-time verification code to the email address entered in the sign-up form. Configure the SMTP variables in `.env` before using registration:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-gmail-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=Fundora <your-email@gmail.com>
```

For Gmail, enable 2-Step Verification on the sending account and create an **App Password**. Put that app password in `EMAIL_HOST_PASSWORD`; do not use your normal Gmail password. If you use another email provider, replace `EMAIL_HOST`, `EMAIL_PORT`, TLS/SSL options, and sender credentials with the provider's SMTP settings. Use either TLS or SSL according to your provider, not both.

The values in `.env.example` are placeholders. Replace them with your real email settings in the ignored `.env` file, then restart Django. Never commit real SMTP credentials.

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
