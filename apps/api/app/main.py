"""HTTP entry point. Audit calculations belong in second_opinion."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from second_opinion.variants import all_variants

from .routes import audit, export, extract, roles

app = FastAPI(title="SecondOpinion API", version="0.1.0")

for _module in (extract, audit, export, roles):
    app.include_router(_module.router)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "second-opinion-api"


class VariantResponse(BaseModel):
    id: str
    subtype_source: str
    sex_filter: str
    sample_scope: str


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/variants", response_model=list[VariantResponse], tags=["audit"])
def variants() -> list[VariantResponse]:
    return [
        VariantResponse(
            id=variant.id,
            subtype_source=variant.subtype_source,
            sex_filter=variant.sex_filter,
            sample_scope=variant.sample_scope,
        )
        for variant in all_variants()
    ]
