from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Número da página, começando em 1.")
    page_size: int = Field(default=20, ge=1, le=100, description="Itens por página (máx. 100).")


class Page(BaseModel, Generic[T]):
    items: list[T] = Field(description="Itens da página atual.")
    page: int = Field(description="Página atual.")
    page_size: int = Field(description="Tamanho de página solicitado.")
    total: int = Field(
        description="Total de itens ativos (todas as páginas), para calcular quantas páginas há."
    )
