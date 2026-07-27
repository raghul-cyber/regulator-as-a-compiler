from typing import Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.users import User
from app.models.requirements import Requirement, RequirementType, Severity, ValidationStatus
from app.models.audit import AuditLog
from app.models.regulations import RegulationVersion, Regulation

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

class HighRiskControl(BaseModel):
    id: UUID
    title: str
    severity: Severity
    validation_status: ValidationStatus
    regulation_name: str
    
class RecentActivity(BaseModel):
    id: UUID
    action: str
    title: str
    created_at: datetime
    metadata_payload: dict

class AffectedSystem(BaseModel):
    id: UUID
    system_name: str
    impact_record_id: UUID
    severity: Severity
    created_at: datetime
    status: str

class DashboardSummaryResponse(BaseModel):
    total_requirements: int
    counts_by_type: Dict[str, int]
    counts_by_severity: Dict[str, int]
    counts_by_status: Dict[str, int]
    recent_activity: List[RecentActivity]
    high_risk_controls: List[HighRiskControl]
    affected_systems: List[AffectedSystem]

@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Base query for user's organization requirements
    # Assuming for now that requirements belong to regulations which belong to orgs, 
    # OR that we just scope by joining AuditLog or we just do all for now (since MVP).
    # Wait, in the schema, requirements don't have org_id directly.
    # Let's scope it to all requirements for now, as MVP doesn't have multi-tenant fully scoped at requirement level.
    
    # 1. Total Requirements
    total_stmt = select(func.count(Requirement.id))
    total_requirements = (await db.execute(total_stmt)).scalar() or 0
    
    # 2. Counts by Type
    type_stmt = select(Requirement.type, func.count(Requirement.id)).group_by(Requirement.type)
    type_results = (await db.execute(type_stmt)).all()
    counts_by_type = {t.value if hasattr(t, 'value') else t: c for t, c in type_results}
    
    # 3. Counts by Severity
    sev_stmt = select(Requirement.severity, func.count(Requirement.id)).group_by(Requirement.severity)
    sev_results = (await db.execute(sev_stmt)).all()
    counts_by_severity = {s.value if hasattr(s, 'value') else s: c for s, c in sev_results}
    
    # 4. Counts by Status
    status_stmt = select(Requirement.validation_status, func.count(Requirement.id)).group_by(Requirement.validation_status)
    status_results = (await db.execute(status_stmt)).all()
    counts_by_status = {s.value if hasattr(s, 'value') else s: c for s, c in status_results}
    
    # 5. High Risk Controls (Severity High/Critical, Status Draft/Pending)
    high_risk_stmt = (
        select(Requirement, Regulation.name.label("regulation_name"))
        .join(RegulationVersion, Requirement.regulation_version_id == RegulationVersion.id)
        .join(Regulation, RegulationVersion.regulation_id == Regulation.id)
        .where(
            Requirement.severity.in_([Severity.high, Severity.critical]),
            Requirement.validation_status.in_([ValidationStatus.draft, ValidationStatus.pending_review])
        )
        .order_by(Requirement.created_at.desc())
        .limit(10)
    )
    high_risk_results = (await db.execute(high_risk_stmt)).all()
    high_risk_controls = [
        HighRiskControl(
            id=req.Requirement.id,
            title=req.Requirement.title,
            severity=req.Requirement.severity,
            validation_status=req.Requirement.validation_status,
            regulation_name=req.regulation_name
        ) for req in high_risk_results
    ]
    
    # 6. Recent Activity (AuditLog joined with Requirement title)
    audit_stmt = (
        select(AuditLog, Requirement.title)
        .outerjoin(Requirement, AuditLog.entity_id == Requirement.id)
        .where(AuditLog.entity_type == "requirement")
        .order_by(AuditLog.created_at.desc())
        .limit(5)
    )
    audit_results = (await db.execute(audit_stmt)).all()
    recent_activity = [
        RecentActivity(
            id=log.AuditLog.id,
            action=log.AuditLog.action,
            title=log.title or "Unknown Requirement",
            created_at=log.AuditLog.created_at,
            metadata_payload=log.AuditLog.metadata_payload or {}
        ) for log in audit_results
    ]
    
    # 7. Affected Systems (Unresolved ImpactRecords)
    from app.models.impacts import ImpactRecord, ImpactStatus
    from app.models.policies import SystemMapping
    
    impact_stmt = (
        select(ImpactRecord, SystemMapping.system_name)
        .join(SystemMapping, ImpactRecord.system_mapping_id == SystemMapping.id)
        .where(ImpactRecord.status == ImpactStatus.unresolved)
        .order_by(ImpactRecord.created_at.desc())
        .limit(10)
    )
    impact_results = (await db.execute(impact_stmt)).all()
    affected_systems = [
        AffectedSystem(
            id=impact.system_mapping_id,
            system_name=sys_name,
            impact_record_id=impact.id,
            severity=impact.overridden_severity or impact.severity,
            created_at=impact.created_at,
            status=impact.status.value
        ) for impact, sys_name in impact_results
    ]
    
    return DashboardSummaryResponse(
        total_requirements=total_requirements,
        counts_by_type=counts_by_type,
        counts_by_severity=counts_by_severity,
        counts_by_status=counts_by_status,
        recent_activity=recent_activity,
        high_risk_controls=high_risk_controls,
        affected_systems=affected_systems
    )
