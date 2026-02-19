"""
FastAPI application for file upload and transaction processing
"""

import gc
import logging
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Form
from sqlalchemy import insert, text
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import re
from database import get_db, init_db
from models import Transaction
from schemas import FileUploadResponse
import os
import boto3
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

INSERT_BATCH_SIZE = 500

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Macro Analytics API",
    description="API for processing files and storing transaction data",
    version="1.0.0",
)

# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class GeneralBedrockModel(BaseModel):
    model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    max_output_tokens: int = 4096
    user_prompt: str

    async def call_api(self, messages, inference_config):
        session = boto3.Session()
        bedrock_runtime = session.client(service_name="bedrock-runtime")

        converse_params = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": inference_config,
        }

        response = bedrock_runtime.converse(**converse_params)

        return response["output"]["message"]["content"][0]["text"]

    async def __call__(self, *args, **kwargs):
        # prepare inference config
        inference_config = {
            "maxTokens": self.max_output_tokens,
        }

        messages = [{"role": "user", "content": [{"text": self.user_prompt}]}]

        # call api
        response = await self.call_api(
            messages=messages, inference_config=inference_config
        )

        return response


@app.on_event("startup")
async def startup_event():
    """
    Initialize database on application startup.
    This will create all tables if they don't exist.
    """
    logger.info("Application startup - initializing database")
    init_db()
    logger.info("Application startup complete")


def mask_account_number(account_number, exists_in_db=False):
    """
    Mask account number with the following logic:
    - If NOT in database: Show last 4 digits (XXXXXX1234)
    - If IN database: Show last 5 digits (XXXXX56789)

    Args:
        account_number: The full account number string
        exists_in_db: Boolean indicating if this masked number exists in DB

    Returns:
        Masked account number string
    """
    logger.debug(f"mask_account_number called: exists_in_db={exists_in_db}")
    if not account_number:
        logger.debug("Account number is empty, returning None")
        return None

    account_number = str(account_number).strip()

    if "x" in account_number.lower():
        logger.debug("Account number already masked, returning as-is")
        return account_number

    if len(account_number) <= 4:
        logger.debug(
            f"Account number too short ({len(account_number)} chars), returning as-is"
        )
        return account_number

    digits_to_show = 5 if exists_in_db else 4

    digits_to_show = min(digits_to_show, len(account_number))

    last_digits = account_number[-digits_to_show:]

    mask_length = len(account_number) - digits_to_show
    masked = "X" * mask_length + last_digits

    logger.debug(f"Masked account number: {masked}")
    return masked


def get_masked_account_number(db: Session, account_number: str) -> tuple[bool, str]:
    """
    Get the masked account number, checking if it already exists in the database.

    Args:
        db: Database session
        account_number: The account number to mask

    Returns:
        Tuple of (exists_in_db, masked_account_number)
    """
    logger.debug("get_masked_account_number called")
    if not account_number:
        logger.debug("No account number provided, returning (False, None)")
        return False, None

    masked_4_digits = mask_account_number(account_number, exists_in_db=False)
    logger.debug(f"Checking database for masked account: {masked_4_digits}")

    existing = (
        db.query(Transaction)
        .filter(Transaction.masked_account_number == masked_4_digits)
        .first()
    )

    if existing:
        logger.debug(f"Account found in database, returning 5-digit mask")
        return True, mask_account_number(account_number, exists_in_db=True)
    logger.debug("Account not found in database, returning 4-digit mask")
    return False, masked_4_digits


def get_existing_work_order_ids(db: Session, work_order_ids: list[str]) -> set[str]:
    """
    Check which work_order_ids already exist in the database.

    Args:
        db: Database session
        work_order_ids: List of work_order_ids to check

    Returns:
        Set of work_order_ids that already exist in the database
    """
    if not work_order_ids:
        return set()

    unique_ids = list(set(wid for wid in work_order_ids if wid))
    if not unique_ids:
        return set()

    existing = (
        db.query(Transaction.work_order_id)
        .filter(Transaction.work_order_id.in_(unique_ids))
        .distinct()
        .all()
    )
    db.expire_all()

    existing_set = {row[0] for row in existing}
    logger.info(
        f"Found {len(existing_set)} existing work_order_ids out of {len(unique_ids)} checked"
    )
    return existing_set


@app.get("/")
async def serve_query_page():
    """Serve the main query interface page"""
    return FileResponse(static_dir / "query.html")


@app.post("/query")
async def query_data(
    natural_query: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Convert a natural language query to SQL and execute it.

    Args:
        natural_query: The natural language query from the user
        db: Database session (injected)

    Returns:
        Query results in JSON format
    """
    try:
        if not natural_query or len(natural_query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        logger.info(f"Processing natural language query: {natural_query[:100]}")

        # Get database schema information for the prompt
        schema_info = """
                        Database Table: transactions
                        Columns:
                        - id (Integer, Primary Key)
                        - work_order_id (String)
                        - client_name (String)
                        - date (DateTime)
                        - description (Text)
                        - amount (Float)
                        - type (String) - credit/debit type
                        - balance (Float)
                        - reference (String)
                        - od_limit (Float)
                        - charges (Float)
                        - category (String)
                        - category_2 (String)
                        - mode (String)
                        - masked_account_number (String)
                        - account_name (String)
                        - account_type (String)
                        - bank_name (String)
                        - ifsc_code (String)
                        - micr_code (String)
                        - pincode (String)
                        - entities (Text)
                        - created_at (DateTime)
                        - updated_at (DateTime)

                        IMPORTANT: Always return valid PostgreSQL syntax only. Do not include explanations or markdown code blocks.
                    """

        # Create prompt for LLM
        prompt = f"""Convert the following natural language query to a PostgreSQL SELECT query.

                    Schema:
                    {schema_info}

                    Natural Language Query: "{natural_query}"

                    Return ONLY the PostgreSQL query, nothing else. No explanations, no markdown, just the SQL query.
                
                """

        # Get SQL from LLM
        sql_query = await GeneralBedrockModel(user_prompt=prompt)()
        sql_query = sql_query.strip()

        # Remove markdown code blocks if present
        if sql_query.startswith("```"):
            sql_query = sql_query.split("```")[1]
            if sql_query.startswith("sql"):
                sql_query = sql_query[3:]
            sql_query = sql_query.strip()

        logger.info(f"Generated SQL: {sql_query}")

        # Execute the query with safety checks
        if not sql_query.lower().startswith("select"):
            raise HTTPException(
                status_code=400, detail="Only SELECT queries are allowed"
            )

        # Execute query
        result = db.execute(text(sql_query))
        rows = result.fetchall()

        # Convert rows to dictionaries
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]

        # Convert datetime objects to ISO format strings
        for row in data:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()

        logger.info(f"Query executed successfully, returned {len(data)} rows")

        return {
            "success": True,
            "query": natural_query,
            "sql": sql_query,
            "rows_returned": len(data),
            "data": data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")


@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    client_name: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a JSON file and process its contents to store transactions.

    This endpoint:
    1. Validates that the uploaded file is a JSON file
    2. Reads and parses the JSON contents
    3. Extracts transactions from the JSON structure
    4. Stores transaction data to the database

    Args:
        file: The uploaded JSON file
        client_name: Client name for all transactions (optional form parameter)
        db: Database session (injected)

    Returns:
        FileUploadResponse with processing results
    """
    try:
        logger.info(
            f"Upload request received: filename={file.filename if file else None}, client_name={client_name}"
        )

        if not file:
            logger.error("No file uploaded")
            raise HTTPException(status_code=400, detail="No file uploaded")

        if not file.filename.endswith(".json"):
            logger.error(f"Invalid file type: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only JSON files are accepted.",
            )

        logger.debug("Reading file contents...")
        contents = await file.read()
        logger.debug(f"File size: {len(contents)} bytes")

        if not contents:
            logger.error("Uploaded file is empty")
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            logger.debug("Parsing JSON contents...")
            data = json.loads(contents.decode("utf-8"))
            del contents
            logger.debug("JSON parsed successfully")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON format: {str(e)}"
            )

        work_order_id = data.get("A0000", {}).get("Workorder ID", None)
        logger.debug(f"Work order ID: {work_order_id}")

        xns_data = data.get("Xns")
        metadata = data.get("MetaData")
        logger.debug(
            f"Xns data type: {type(xns_data).__name__}, MetaData present: {metadata is not None}"
        )
        if not xns_data:
            logger.error("Required key 'Xns' not found in JSON file")
            raise HTTPException(
                status_code=400, detail="Required key 'Xns' not found in JSON file"
            )

        all_transactions = []
        logger.debug("Starting transaction extraction...")

        if isinstance(xns_data, dict):
            logger.debug("Processing Xns as dictionary format")
            try:
                for idx in range(len(xns_data.get("date", []))):
                    txn = {
                        "client_name": client_name,
                        "work_order_id": work_order_id,
                        "date": xns_data.get("date")[idx],
                        "description": xns_data.get("description")[idx],
                        "type": xns_data.get("credit/debit")[idx],
                        "amount": xns_data.get("amount")[idx],
                        "balance": xns_data.get("balance")[idx],
                        "account_number": xns_data.get("account_number")[idx],
                        "reference": xns_data.get("reference")[idx],
                        "entities": xns_data.get("renamed_entity")[idx],
                        "od_limit": xns_data.get("od_limit")[idx],
                        "charges": xns_data.get("charges")[idx],
                        "bank_name": xns_data.get("bank_name")[idx],
                        "category": xns_data.get("category")[idx],
                        "category_2": xns_data.get("category_2")[idx],
                        "mode": xns_data.get("mode")[idx],
                        "account_name": metadata.get("account_name"),
                        "ifsc_code": metadata.get("ifsc_code"),
                        "micr_code": metadata.get("micr_code"),
                        "account_type": metadata.get("account_type"),
                        "account_address": metadata.get("account_address"),
                        "pincode": (
                            (
                                re.search(
                                    r"\b\d{6}\b", metadata.get("account_address") or ""
                                )
                            )
                            .group(0)
                            .replace(" ", "")
                            if (
                                re.search(
                                    r"\b\d{6}\b", metadata.get("account_address") or ""
                                )
                            )
                            else ""
                        ),
                    }
                    all_transactions.append(txn)
                logger.debug(
                    f"Extracted {len(all_transactions)} transactions from dict format"
                )
            except Exception as e:
                logger.error(f"Error extracting transactions from dict: {str(e)}")

        elif isinstance(xns_data, list):
            logger.debug(f"Processing Xns as list format with {len(xns_data)} items")
            id = 0
            for item in xns_data:
                if not isinstance(item, dict):
                    continue

                try:
                    for key, value in item.items():
                        if key.lower().startswith("bankstatement"):

                            if isinstance(value, dict):
                                for idx in range(len(value.get("date", []))):
                                    txn = {
                                        "client_name": client_name,
                                        "work_order_id": work_order_id,
                                        "date": value.get("date")[idx],
                                        "description": value.get("description")[idx],
                                        "type": value.get("credit/debit")[idx],
                                        "amount": value.get("amount")[idx],
                                        "balance": value.get("balance")[idx],
                                        "account_number": value.get("account_number")[
                                            idx
                                        ],
                                        "reference": value.get("reference")[idx],
                                        "entities": value.get("renamed_entity")[idx],
                                        "od_limit": value.get("od_limit")[idx],
                                        "charges": value.get("charges")[idx],
                                        "bank_name": value.get("bank_name")[idx],
                                        "category": value.get("category")[idx],
                                        "category_2": value.get("category_2")[idx],
                                        "mode": value.get("mode")[idx],
                                        "account_name": value.get("account_name")[idx],
                                        "ifsc_code": metadata.get("ifsc_code")[id],
                                        "micr_code": metadata.get("micr_code")[id],
                                        "account_type": metadata.get("account_type")[
                                            id
                                        ],
                                        "account_address": metadata.get(
                                            "account_address"
                                        )[id],
                                        "pincode": (
                                            (
                                                re.search(
                                                    r"\b\d{6}\b",
                                                    metadata.get("account_address")[id]
                                                    or "",
                                                )
                                            )
                                            .group(0)
                                            .replace(" ", "")
                                            if (
                                                re.search(
                                                    r"\b\d{6}\b",
                                                    metadata.get("account_address")[id]
                                                    or "",
                                                )
                                            )
                                            else ""
                                        ),
                                    }
                                    all_transactions.append(txn)
                            id += 1
                except Exception as e:
                    logger.error(
                        f"Error extracting transactions from list item: {str(e)}"
                    )

            logger.debug(
                f"Extracted {len(all_transactions)} transactions from list format"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unexpected type for 'Xns': {type(xns_data).__name__}. Expected dict or list.",
            )

        if not all_transactions:
            logger.error("No transaction data found in the JSON structure")
            raise HTTPException(
                status_code=200,
                detail="No transaction data found in the JSON structure",
            )

        del data

        total_transactions = len(all_transactions)
        logger.info(f"Total transactions extracted: {total_transactions}")

        processed_transactions = []
        errors = []
        duplicates_skipped = 0

        first_account_number = (
            all_transactions[0].get("account_number") if all_transactions else None
        )
        first_masked_account = mask_account_number(
            first_account_number, exists_in_db=False
        )

        # Single query: check which work_order_ids already exist
        incoming_work_order_ids = [txn.get("work_order_id") for txn in all_transactions]
        existing_work_order_ids = get_existing_work_order_ids(
            db, incoming_work_order_ids
        )

        if work_order_id and work_order_id in existing_work_order_ids:
            duplicates_skipped = len(all_transactions)
            logger.info(
                f"Work order {work_order_id} already exists in DB. Skipping all {duplicates_skipped} transactions."
            )
        else:
            for idx, row in enumerate(all_transactions):
                try:
                    transaction_date = None
                    if row.get("date"):
                        try:
                            transaction_date = datetime.fromisoformat(
                                row.get("date").replace("Z", "+00:00")
                            )
                        except:
                            try:
                                transaction_date = datetime.strptime(
                                    row.get("date"), "%d/%m/%Y"
                                )
                            except:
                                pass

                    row["date"] = transaction_date
                    row["masked_account_number"] = first_masked_account

                    row.pop("account_number", None)
                    row.pop("account_address", None)

                    processed_transactions.append(row)

                except Exception as e:
                    error_msg = f"Error processing record {idx + 1}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue

        del all_transactions

        logger.info(
            f"Processing complete: {len(processed_transactions)} to save, {duplicates_skipped} duplicates skipped, {len(errors)} errors"
        )

        try:
            records_saved = 0
            if processed_transactions:
                for i in range(0, len(processed_transactions), INSERT_BATCH_SIZE):
                    batch = processed_transactions[i : i + INSERT_BATCH_SIZE]
                    db.execute(insert(Transaction).values(batch))
                    db.commit()
                    records_saved += len(batch)
                    db.expire_all()
                logger.info(
                    f"Database commit successful: {records_saved} records in batches of {INSERT_BATCH_SIZE}"
                )
            del processed_transactions
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

        message = f"File processed successfully. {records_saved} transactions saved."
        if duplicates_skipped > 0:
            message += f" {duplicates_skipped} duplicates skipped."
        if errors:
            message += f" {len(errors)} records failed."

        logger.info(f"Upload complete: {message}")
        return FileUploadResponse(
            filename=file.filename,
            message=message,
            records_processed=total_transactions,
            records_saved=records_saved,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

    finally:
        await file.close()
        gc.collect()


if __name__ == "__main__":
    import uvicorn

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    RELOAD = os.getenv("RELOAD", "true").lower() == "true"
    WORKERS = int(os.getenv("WORKERS", "1" if RELOAD else "2"))
    LIMIT_MAX_REQUESTS = int(os.getenv("LIMIT_MAX_REQUESTS", "1000"))

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        workers=WORKERS,
        limit_max_requests=LIMIT_MAX_REQUESTS,
    )
