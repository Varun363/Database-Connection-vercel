from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(30), unique=True, nullable=False, index=True)
    full_name = Column(String(80), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="customer")
    resort_name = Column(String(100), default="Ocean View Resort")
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    number = Column(String(20), unique=True, nullable=False)
    floor = Column(Integer, nullable=False, default=1)
    room_type = Column(String(80), nullable=False)
    description = Column(Text, default="")
    price = Column(Float, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="Available")

    bookings = relationship("Booking", back_populates="room")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guests = Column(Integer, nullable=False, default=1)
    total = Column(Float, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="Confirmed")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    task_type = Column(String(50), default="General")
    room_area = Column(String(100), default="")
    assignee = Column(String(100), default="")
    priority = Column(String(20), default="Medium")
    status = Column(String(30), default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    room = Column(String(100), default="")
    category = Column(String(50), default="General")
    priority = Column(String(20), default="Medium")
    description = Column(Text, default="")
    status = Column(String(30), default="Open")
    created_at = Column(DateTime, default=datetime.utcnow)
