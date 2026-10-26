"""Validate review metadata; malformed or contradictory reports never imply approval."""
from typing import Literal
from pydantic import BaseModel, Field, ValidationError, ConfigDict


class Finding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    severity: Literal['high','medium','low','info']
    path: str | None = Field(max_length=500)
    line: int | None = Field(ge=1)
    message: str = Field(min_length=1,max_length=2000)


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    verdict: Literal['approved','changes_requested','needs_review']
    summary: str = Field(max_length=3000)
    findings: list[Finding] = Field(max_length=50)


def parse_review(text: str) -> dict:
    try:
        review=Review.model_validate_json(text).model_dump()
        if review['verdict']=='approved' and any(item['severity'] in {'high','medium'} for item in review['findings']):
            review['verdict']='changes_requested'
        return review
    except (ValidationError,ValueError):
        return {'verdict':'needs_review','summary':'La revisión no devolvió un informe estructurado válido. Revisa el texto de SENTINEL.','findings':[]}
