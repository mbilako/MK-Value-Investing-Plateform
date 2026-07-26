from fastapi import APIRouter
from pydantic import BaseModel

from mkvip.analysis.rules import RULES

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleRead(BaseModel):
    key: str
    label: str
    source_note: str


@router.get("", response_model=list[RuleRead])
async def list_rules() -> list[RuleRead]:
    return [
        RuleRead(
            key=rule.key,
            label=rule.label,
            source_note=rule.source_note,
        )
        for rule in RULES.values()
    ]
