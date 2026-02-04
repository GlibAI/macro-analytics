"""
Database models for the application
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from database import Base


class Transaction(Base):
    """
    Transaction model for storing transaction data with comprehensive banking details.
    """

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    work_order_id = Column(String(100), index=True)
    client_name = Column(String(255))

    date = Column(DateTime)
    description = Column(Text)
    amount = Column(Float, nullable=False)
    type = Column(String(50))
    balance = Column(Float)
    reference = Column(String(255))
    od_limit = Column(Float)
    charges = Column(Float)

    category = Column(String(100))
    category_2 = Column(String(100))

    mode = Column(String(50))

    masked_account_number = Column(String(50), nullable=True, index=True)
    account_name = Column(String(255))
    account_type = Column(String(50))

    bank_name = Column(String(255))
    ifsc_code = Column(String(20))
    micr_code = Column(String(20))

    pincode = Column(String(10))

    entities = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Transaction(id={self.id})>"
