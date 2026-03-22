from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    code = Column(String)
    name = Column(String)
    type = Column(String)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    description = Column(String)

class TransactionLine(Base):
    __tablename__ = "transaction_lines"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    debit = Column(Float)
    credit = Column(Float)