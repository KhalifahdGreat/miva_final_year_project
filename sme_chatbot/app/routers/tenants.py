"""Admin endpoints for tenant lifecycle and persona configuration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.tenant_service import default_config
from core.types import EscalationRule, TenantConfig

from ..deps import get_tenant_service

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    business_name: str


class TenantOut(BaseModel):
    tenant_id: str
    business_name: str
    tone: str
    languages: list[str]
    version: int


class TenantConfigUpdate(BaseModel):
    tagline: str | None = None
    tone: str | None = None
    languages: list[str] | None = None
    greeting: str | None = None
    out_of_hours: str | None = None
    fallback: str | None = None
    escalation_rules: list[dict] | None = None
    brand_voice_examples: list[str] | None = None


@router.post("", response_model=TenantOut)
def create_tenant(body: CreateTenantRequest, tenants=Depends(get_tenant_service)):
    tid = str(uuid.uuid4())
    cfg = default_config(tid, body.business_name)
    tenants.save(cfg)
    return TenantOut(
        tenant_id=tid,
        business_name=cfg.business_name,
        tone=cfg.tone,
        languages=list(cfg.languages),
        version=cfg.version,
    )


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: str, tenants=Depends(get_tenant_service)):
    try:
        cfg = tenants.get(tenant_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TenantOut(
        tenant_id=cfg.tenant_id,
        business_name=cfg.business_name,
        tone=cfg.tone,
        languages=list(cfg.languages),
        version=cfg.version,
    )


@router.patch("/{tenant_id}/config", response_model=TenantOut)
def update_config(
    tenant_id: str,
    body: TenantConfigUpdate,
    tenants=Depends(get_tenant_service),
):
    try:
        cfg = tenants.get(tenant_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    updates = body.model_dump(exclude_none=True)

    if "escalation_rules" in updates:
        updates["escalation_rules"] = [EscalationRule(**r) for r in updates["escalation_rules"]]

    new_cfg = TenantConfig(
        tenant_id=cfg.tenant_id,
        business_name=cfg.business_name,
        tagline=updates.get("tagline", cfg.tagline),
        tone=updates.get("tone", cfg.tone),
        languages=updates.get("languages", list(cfg.languages)),
        timezone=cfg.timezone,
        operating_hours=cfg.operating_hours,
        greeting=updates.get("greeting", cfg.greeting),
        out_of_hours=updates.get("out_of_hours", cfg.out_of_hours),
        fallback=updates.get("fallback", cfg.fallback),
        escalation_rules=updates.get("escalation_rules", cfg.escalation_rules),
        brand_voice_examples=updates.get("brand_voice_examples", cfg.brand_voice_examples),
        retrieval_weights=cfg.retrieval_weights,
        version=cfg.version,
    )
    tenants.save(new_cfg)
    return TenantOut(
        tenant_id=new_cfg.tenant_id,
        business_name=new_cfg.business_name,
        tone=new_cfg.tone,
        languages=list(new_cfg.languages),
        version=new_cfg.version,
    )
