"""Request and response shapes.

Pydantic validates every incoming request body before our code sees it, so
bad input is rejected with HTTP 422 instead of reaching the database.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class EventCreate(BaseModel):
    event_id: str = Field(pattern=r"^[a-z0-9-]{3,40}$", examples=["cloud-workshop-2026"])
    name: str = Field(min_length=3, max_length=120)
    venue: str = Field(min_length=2, max_length=120)
    starts_at: datetime
    capacity: int = Field(ge=1, le=10_000)


class Event(EventCreate):
    registered_count: int
    seats_left: int


class RegistrationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    student_id: str = Field(pattern=r"^[A-Za-z0-9]{3,20}$")


class Registration(BaseModel):
    registration_id: str
    event_id: str
    name: str
    email: EmailStr
    status: str = "confirmed"
