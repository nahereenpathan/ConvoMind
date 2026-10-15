# ConvoMind — AI Meeting Intelligence

ConvoMind is an AI-powered meeting intelligence platform that transforms meeting recordings and conversations into searchable transcripts, actionable tasks, meeting summaries, decisions, and useful insights.

The platform helps teams organize meeting knowledge, track action items, and retrieve information from previous discussions.

## Features

- **Meeting Management:** Upload and organize meeting recordings.
- **AI Transcription:** Convert audio recordings into text with timestamps.
- **Meeting Summaries:** Generate executive summaries and detailed overviews.
- **Action Items:** Extract tasks, assignees, priorities, and deadlines where available.
- **Speaker Management:** Review and map speakers in meeting transcripts.
- **AI Meeting Chat:** Ask questions about a specific meeting and retrieve relevant transcript passages.
- **Workspace Management:** Organize meetings and related information within workspaces.
- **Follow-up Assistance:** Prepare follow-up email drafts based on meeting discussions.
- **Authentication:** User registration, login, and account recovery.
- **Billing:** Subscription and billing functionality, subject to configuration.
- **Deployment:** Docker Compose and Nginx configuration for deployment.

> Feature availability depends on the current implementation, environment configuration, and connected AI services.

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS

### Backend
- Python
- FastAPI
- SQLAlchemy
- Alembic database migrations

### Data and Background Processing
- Relational database configured through environment variables
- Redis and background workers, where configured
- Audio processing and transcription pipeline
- LLM integration for meeting intelligence and question answering

### Infrastructure
- Docker
- Docker Compose
- Nginx
- Git and GitHub

## Project Structure

```text
ConvoMind/
├── apps/
│   ├── api/              # Backend API and business logic
│   └── web/              # Frontend application
├── nginx/                # Nginx configuration
├── scripts/              # Utility and database scripts
├── .env.example          # Development environment template
├── .env.production.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.prod.yml
├── pyrightconfig.json
└── README.md
```

## Prerequisites

Install the following tools before running the project:

- Git
- Python version compatible with `apps/api/requirements.txt`
- Node.js version compatible with the frontend configuration
- npm
- Docker Desktop and Docker Compose, if using containers
- Access credentials for the database and any external AI services used by the application

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/nahereenpathan/ConvoMind.git
cd ConvoMind
```

### 2. Configure Environment Variables

Create your local environment file using the example template.

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

For production, review `.env.production.example` and configure the environment variables through your deployment platform or secure server configuration.

**Important:** Replace placeholder values with your own credentials. Never commit real `.env` files, API keys, passwords, access tokens, or production secrets.

Check the application configuration before starting the services. Some components may require additional environment variables.

### 3. Run with Docker Compose

Review `docker-compose.yml` and the environment requirements first.

Start the configured services:

```bash
docker compose up --build
```

To run the services in the background:

```bash
docker compose up --build -d
```

View service logs:

```bash
docker compose logs -f
```

Stop the services:

```bash
docker compose down
```

The available services and ports depend on the current Docker Compose configuration. Check that file for the actual local URLs.

### 4. Run Frontend and Backend Separately

**Frontend**

```bash
cd apps/web
npm install
npm run dev
```

Use the local URL printed by Vite in the terminal.

**Backend**

Open a separate terminal:

```bash
cd apps/api
```

Create and activate a Python virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the API using the project's configured ASGI application entry point. For example, if the application is exposed as `app` in `app.main`:

```bash
uvicorn app.main:app --reload
```

The exact module path, database requirements, and port must match the current backend configuration.

## Database Migrations

ConvoMind uses Alembic for database schema migrations.

Before running migrations, configure the correct database connection and ensure a backup exists when working with important data.

Check the project's migration configuration, then run:

```bash
cd apps/api
alembic upgrade head
```

Do not run production migrations until the database connection, migration history, and rollback or recovery plan have been reviewed.

## API Documentation

If the backend exposes FastAPI's default documentation endpoints, the API documentation is available at:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI schema: `/openapi.json`

Use the actual backend base URL configured for your environment.

## Testing and Quality Checks

Run the tests and checks supported by the project configuration.

Typical commands include:

```bash
# Frontend production build
cd apps/web
npm run build
```

```bash
# Backend tests
cd apps/api
pytest
```

These commands assume the corresponding scripts, dependencies, test configuration, and required services are available. Review the project configuration before treating a successful command as a complete production-readiness check.

## Security

- Keep the repository private unless the project is intentionally ready for public release.
- Never commit real credentials, API keys, passwords, private recordings, database backups, or personal information.
- Use environment variables or a secrets manager for sensitive configuration.
- Validate uploads and enforce file size and file type restrictions.
- Apply authentication and authorization checks to protected endpoints.
- Enforce workspace-level access control for meetings, transcripts, tasks, and AI chat.
- Verify that AI retrieval is restricted to the correct user's authorized meeting data.
- Configure HTTPS, secure cookies, CORS, rate limits, and appropriate security headers for production.
- Protect logs from exposing tokens, credentials, and sensitive transcript content.
- Back up production databases securely and test recovery procedures.

## Deployment

Production deployment should include:

1. Production environment configuration and secret management.
2. Database provisioning and reviewed migrations.
3. Redis and background worker configuration, if required.
4. Frontend build and backend deployment.
5. HTTPS and reverse-proxy configuration.
6. Health checks, logging, and monitoring.
7. Authentication, authorization, upload, and workspace-isolation testing.
8. Backup and recovery verification.

Review `docker-compose.prod.yml` and the Nginx configuration before deploying. Do not expose internal database or Redis ports publicly unless explicitly required and securely configured.

## Current Status

ConvoMind is under active development. Features, configuration, and deployment requirements may change as implementation and testing progress.

## Contributing

1. Create a feature branch.
2. Make focused changes.
3. Run relevant tests and checks.
4. Review changes for secrets and sensitive data.
5. Submit a pull request with a clear description.

## License

No license has been specified yet. All rights are reserved by default unless a license is added by the project owner.
