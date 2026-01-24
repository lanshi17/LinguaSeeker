"""FastAPI application entrypoint for the REST facade."""
from fastapi import FastAPI

from src.presentation.api_routes import router
from src.presentation.errors import APIException, create_error_response

app = FastAPI(
    title="Multilingual Document Evidence Collection Platform",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)

app.include_router(router)


@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    return create_error_response(exc)
