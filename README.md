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

### 3. Update Database Configuration

Edit `database.py` and update the `DATABASE_URL` with your credentials:
```python
DATABASE_URL = "postgresql://username:password@localhost:5432/macro-analytics"
```

Or use environment variables (recommended):
- Copy `.env.example` to `.env`
- Update the credentials in `.env`

### 4. Define Your Transaction Schema

**Important:** Update the following files with your actual transaction fields:

1. **`models.py`** - Update the `Transaction` model:
   - Add columns matching your data structure
   - Example fields are commented out - uncomment and modify as needed

2. **`schemas.py`** - Update the Pydantic schemas:
   - Update `TransactionBase`, `TransactionCreate`, and `TransactionResponse`
   - Match the fields you defined in your model

### 5. Implement File Processing Logic

Edit `apis.py` in the `upload_file` function:

- Add your file parsing logic (CSV, JSON, Excel, etc.)
- Map file data to Transaction model fields
- The TODO comments guide you through the implementation

Example for CSV:
```python
import csv
csv_data = io.StringIO(contents.decode('utf-8'))
reader = csv.DictReader(csv_data)

for row in reader:
    transaction = Transaction(
        transaction_id=row['id'],
        amount=float(row['amount']),
        # ... map other fields
        source_file=file.filename
    )
    db.add(transaction)

db.commit()
```

### 6. Run the Application

```bash
# Using uvicorn directly
uvicorn apis:app --reload --host 0.0.0.0 --port 8000

# Or using poetry
poetry run uvicorn apis:app --reload

# Or run the Python file directly
python apis.py
```

The API will be available at: `http://localhost:8000`

## API Endpoints

### Core Endpoints

- `POST /upload` - Upload and process file

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
  -F "file=@your_file.csv"
```

### Get all transactions:
```bash
curl -X GET "http://localhost:8000/transactions"
```

### Get transaction by ID:
```bash
curl -X GET "http://localhost:8000/transactions/1"
```

## Project Structure

```
macro-analytics/
├── apis.py           # Main FastAPI application
├── database.py       # Database configuration and session management
├── models.py         # SQLAlchemy models (Transaction table)
├── schemas.py        # Pydantic schemas for validation
├── .env.example      # Example environment variables
├── pyproject.toml    # Poetry dependencies
└── README.md         # This file
```

## Next Steps (TODO)

1. **Update Transaction Schema**
   - Edit `models.py` to add your transaction fields
   - Edit `schemas.py` to match your model

2. **Implement File Processing**
   - Edit the `upload_file` function in `apis.py`
   - Add logic to parse your specific file format
   - Map data to Transaction model

3. **Add Custom Endpoints** (optional)
   - Filter transactions by date range
   - Get analytics/statistics
   - Bulk operations
   - Export functionality

4. **Security Enhancements** (for production)
   - Add authentication/authorization
   - Implement rate limiting
   - Add input validation
   - Use environment variables for secrets

5. **Error Handling**
   - Add comprehensive error handling
   - Implement logging
   - Add data validation

## Development Tips

- The database tables are created automatically on application startup
- Use `--reload` flag during development for auto-reloading
- Check the logs for database connection issues
- Test your API using the Swagger UI at `/docs`
