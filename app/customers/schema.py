from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    full_name: str
    date_of_birth: date
    phone: str | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None


class CustomerResponse(BaseModel):
    id: str
    full_name: str
    date_of_birth: date
    phone: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
