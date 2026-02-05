# Macro Analytics API

FastAPI application for processing files and storing transaction data in PostgreSQL.

## Setup Instructions

### 1. Install Dependencies

Using Poetry (recommended):
```bash
poetry install
```

Or using pip:
```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-multipart pydantic pydantic-settings
```

### 2. Configure PostgreSQL Database

Create a PostgreSQL database:
```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create database
CREATE DATABASE "macro-analytics";

# Create user (optional)
CREATE USER your_username WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE "macro-analytics" TO your_username;
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:
```env
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=macro-analytics
```

### 4. Run the Application

```bash
# Using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or using poetry
poetry run uvicorn main:app --reload

# Or run the Python file directly
python main.py
```

The API will be available at: `http://localhost:8000`

## Database Migrations with Alembic

This project uses Alembic for database migrations. Alembic tracks changes to your SQLAlchemy models and applies them to the database.

### Initial Setup (Already Done)

The alembic configuration is already set up:
- `alembic.ini` - Alembic configuration file
- `alembic/env.py` - Environment configuration (reads database URL from `.env`)
- `alembic/versions/` - Migration scripts

### Creating a New Migration

After modifying `models.py`, generate a migration:

```bash
# Auto-generate migration based on model changes
alembic revision --autogenerate -m "describe your changes"
```

### Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply migrations up to a specific revision
alembic upgrade <revision_id>
```

### Reverting Migrations

```bash
# Downgrade by one revision
alembic downgrade -1

# Downgrade to a specific revision
alembic downgrade <revision_id>

# Downgrade all the way (empty database)
alembic downgrade base
```

### Viewing Migration History

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show detailed history
alembic history --verbose
```

## API Endpoints

### Core Endpoints

- `POST /upload` - Upload and process JSON file with transaction data

### Interactive API Documentation

FastAPI provides automatic interactive documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Example

### Upload a file:
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_file.json" \
  -F "client_name=Your Client Name"
```

## Project Structure

```
macro-analytics/
├── main.py           # Main FastAPI application
├── database.py       # Database configuration and session management
├── models.py         # SQLAlchemy models (Transaction table)
├── schemas.py        # Pydantic schemas for validation
├── alembic.ini       # Alembic configuration
├── alembic/          # Alembic migrations directory
│   ├── env.py        # Alembic environment (reads from .env)
│   ├── script.py.mako
│   └── versions/     # Migration scripts
├── .env              # Environment variables (not in git)
├── pyproject.toml    # Poetry dependencies
└── README.md         # This file
```

## Development Tips

- Database tables are created automatically on application startup if they don't exist
- Use `--reload` flag during development for auto-reloading
- Always use Alembic migrations when modifying models in production
- Check the logs for database connection issues
- Test your API using the Swagger UI at `/docs`
