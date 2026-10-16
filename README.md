# Fundora

Fundora is a Django financial assistant prototype for international students and cross-border users. The intended scope is described in [`idea.md`](idea.md), the implementation sequence is tracked in [`build.md`](build.md), and working rules are in [`instruction.md`](instruction.md).

The existing `Agent` Django app is retained for authentication and current UI compatibility. On case-insensitive filesystems such as Windows it cannot coexist with a second package named `agent`; new agent workflow modules will be added to `Agent`, while deterministic transfer simulation is isolated in the lowercase `sandbox` app.

Transfers and financial data in the current project are simulations. Do not use this prototype to move real money or make financial decisions.

## Requirements

- Python 3.12 or newer
- PostgreSQL 14 or newer for the target application setup
- Dependencies from `requirements.txt`

## Local setup

Run all commands from the repository root. Create and activate a virtual environment:

**Windows PowerShell**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**Linux/macOS**

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` before starting Django. Set a unique `SECRET_KEY`, set `DEBUG=True` for local development, and fill in the PostgreSQL database name, user, and password. The `.env.example` values are placeholders. Keep `.env` private and never commit it.

If the PostgreSQL role/database do not exist, create them as a PostgreSQL administrator, replacing the example password with your own:

```sql
CREATE USER fintech_user WITH PASSWORD 'your_secure_database_password';
CREATE DATABASE fintech_db OWNER fintech_user;
```

Set matching values in `.env`:

```dotenv
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fintech_db
DB_USER=fintech_user
DB_PASSWORD=your_secure_database_password
DB_HOST=127.0.0.1
DB_PORT=5432
```

For a temporary UI-only local run when PostgreSQL is unavailable, use SQLite in the ignored `.env`:

```dotenv
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=local.sqlite3
```

SQLite is not the target database and does not replace PostgreSQL verification for completed features.

## Email OTP

Registration sends a one-time verification code. Configure SMTP in `.env` to deliver it to an inbox. The `.env.example` includes Gmail-shaped placeholders; Gmail requires an App Password created after enabling 2-Step Verification. Do not use your regular Gmail password. For local development without SMTP, set:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

With the console backend, the OTP email is printed in the Django server terminal instead of being delivered.

## Agent and sandbox configuration

The environment template includes optional provider settings for DeepSeek chat and Gemini vision, plus sandbox and approval controls:

- `DEEPSEEK_API_KEY` and `GEMINI_API_KEY` are private credentials; do not commit or paste them into logs.
- `SANDBOX_MODE=True` keeps transfer behavior simulated.
- `APPROVAL_TTL_SECONDS` and `MAX_AGENT_ITERATIONS` must be positive integers.
- FX rates use `FX_API_URL` and `FX_API_KEY`; keep the key private. The live endpoint requires network access and valid provider credentials.

Provider-dependent development should use mocked clients in automated tests so tests do not need network access or real credentials.

## Database and server

From the repository root:

```bash
python AI_Agent/manage.py check
python AI_Agent/manage.py migrate
python AI_Agent/manage.py runserver
```

Open <http://127.0.0.1:8000/>. The Django admin is at <http://127.0.0.1:8000/admin/>; create an administrator with:

```bash
python AI_Agent/manage.py createsuperuser
```

For ASGI serving, the project exposes `AI_Agent.asgi:application`; the locked production server choice is Uvicorn. Production deployment instructions will be expanded as the application phases are implemented.

## Development workflow

1. Read [`instruction.md`](instruction.md), [`idea.md`](idea.md), [`build.md`](build.md), and the latest entry in [`test_results.md`](test_results.md).
2. Work on the earliest incomplete build phase and implement its acceptance checks.
3. Run focused tests and the complete app suite explicitly: `python AI_Agent/manage.py test Agent sandbox`. A bare `manage.py test` from this nested repository currently discovers no tests.
4. Run Django checks, migration checks, and the phase-specific scenarios.
5. Record commands and results in `test_results.md`, then update the corresponding checklist status in `build.md`.

## Security and limitations

- Never commit `.env`, provider/email credentials, uploads, local databases, or generated Python cache files.
- Keep `DEBUG=False` in production and set only trusted hostnames in `ALLOWED_HOSTS`.
- The product specification requires deterministic server-side enforcement for compliance, user tier, approval, and transfer execution. The LLM must not own those controls.
- Simulated rates, compliance results, rails, balances, and transfers are not real financial services.
