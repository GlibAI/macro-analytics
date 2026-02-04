"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel

class FileUploadResponse(BaseModel):
    """
    Response schema for file upload endpoint
    """
    filename: str
    message: str
    records_processed: int
    records_saved: int
