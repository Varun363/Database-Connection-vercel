from sqlalchemy import Column, Integer, String, VARCHAR , CheckConstraint , DateTime
from db import Base

class dashboard(Base):
    __tablename__ = "resort_db"

    gst_id = Column(Integer, primary_key=True)
    gst_name = Column(String)
    rooms_alt = Column(Integer)
    amt = Column(
        Integer, 
        CheckConstraint("amt <= 500000", name="check_amt_max")
        )
    Status = Column(String)
    transaction_due = Column(DateTime)

    

