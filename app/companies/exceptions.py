from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class CompanyNotFoundError(Exception):
    def __init__(self, company_id: str) -> None:
        super().__init__(f"Company {company_id} not found")


class CompanyAlreadyExistsError(Exception):
    def __init__(self, cnpj: str) -> None:
        super().__init__(f"Company with CNPJ '{cnpj}' already exists")


class CompanyUnitNotFoundError(Exception):
    def __init__(self, unit_id: str) -> None:
        super().__init__(f"Company unit {unit_id} not found")


class CompanyUnitAlreadyExistsError(Exception):
    pass


class CompanyUserLinkNotFoundError(Exception):
    def __init__(self, link_id: str) -> None:
        super().__init__(f"Company user link {link_id} not found")


class CompanyUserLinkAlreadyExistsError(Exception):
    def __init__(self) -> None:
        super().__init__("User already has an active link for this company/unit")


class CompanyOrUnitRequiredError(Exception):
    pass


class ManagerRequiresUnitError(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id} is a manager and must be linked to a specific unit")


def register_company_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CompanyNotFoundError)
    async def company_not_found_handler(
        request: Request, exc: CompanyNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CompanyAlreadyExistsError)
    async def company_already_exists_handler(
        request: Request, exc: CompanyAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CompanyUnitNotFoundError)
    async def company_unit_not_found_handler(
        request: Request, exc: CompanyUnitNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CompanyUnitAlreadyExistsError)
    async def company_unit_already_exists_handler(
        request: Request, exc: CompanyUnitAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CompanyUserLinkNotFoundError)
    async def company_user_link_not_found_handler(
        request: Request, exc: CompanyUserLinkNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CompanyUserLinkAlreadyExistsError)
    async def company_user_link_already_exists_handler(
        request: Request, exc: CompanyUserLinkAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CompanyOrUnitRequiredError)
    async def company_or_unit_required_handler(
        request: Request, exc: CompanyOrUnitRequiredError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ManagerRequiresUnitError)
    async def manager_requires_unit_handler(
        request: Request, exc: ManagerRequiresUnitError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
