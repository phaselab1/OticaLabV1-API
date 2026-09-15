from typing import Annotated

from fastapi import APIRouter, Query, status

from app.customers.dependencies import CustomerServiceDep
from app.customers.model import Customer
from app.customers.schema import CustomerCreate, CustomerResponse, CustomerUpdate
from app.shared.pagination import Page

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(data: CustomerCreate, service: CustomerServiceDep) -> Customer:
    return await service.create(data)


@router.get("/", response_model=Page[CustomerResponse])
async def list_customers(
    service: CustomerServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[Customer]:
    return await service.get_all(page=page, page_size=page_size)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, service: CustomerServiceDep) -> Customer:
    return await service.get_by_id(customer_id)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str, data: CustomerUpdate, service: CustomerServiceDep
) -> Customer:
    return await service.update(customer_id, data)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: str, service: CustomerServiceDep) -> None:
    await service.delete(customer_id)
