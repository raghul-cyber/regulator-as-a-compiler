from uuid import UUID, uuid4
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.requirements import Requirement, RequirementEmbedding
from app.models.diffs import RequirementDiff, DiffStatus
from app.models.regulations import RegulationVersion

logger = logging.getLogger(__name__)

async def compute_version_diff(old_version_id: UUID, new_version_id: UUID, db: AsyncSession):
    """
    Computes the semantic diff between two regulation versions.
    Populates the RequirementDiff table and updates the new RegulationVersion's diff_summary.
    """
    # 1. Fetch old requirements and their embeddings
    old_reqs_stmt = select(Requirement, RequirementEmbedding).join(
        RequirementEmbedding, Requirement.id == RequirementEmbedding.requirement_id
    ).where(Requirement.regulation_version_id == old_version_id)
    
    old_results = (await db.execute(old_reqs_stmt)).all()
    
    # 2. Fetch new requirements and their embeddings
    new_reqs_stmt = select(Requirement, RequirementEmbedding).join(
        RequirementEmbedding, Requirement.id == RequirementEmbedding.requirement_id
    ).where(Requirement.regulation_version_id == new_version_id)
    
    new_results = (await db.execute(new_reqs_stmt)).all()
    
    old_reqs = {req.id: {"req": req, "emb": emb} for req, emb in old_results}
    new_reqs = {req.id: {"req": req, "emb": emb} for req, emb in new_results}
    
    diff_records = []
    matched_old_ids = set()
    
    # Track summary
    summary = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}

    # If there's no old version data, everything is added.
    if not old_results:
        for new_id in new_reqs:
            diff_records.append(RequirementDiff(
                id=uuid4(),
                regulation_version_id=new_version_id,
                old_requirement_id=None,
                new_requirement_id=new_id,
                status=DiffStatus.added
            ))
            summary["added"] += 1
    else:
        # For each new requirement, find the closest old requirement
        for new_id, new_data in new_reqs.items():
            new_emb = new_data["emb"].embedding
            new_req = new_data["req"]
            
            # Find the best match among old requirements that hasn't been matched yet
            best_match_id = None
            best_distance = float('inf')
            
            # We can use cosine distance manually or via DB. Since we already loaded them into memory, 
            # and the number per regulation is likely < 10,000, we can compute cosine distance here or 
            # we could have used pgvector to query. Doing it in Python for simplicity:
            for old_id, old_data in old_reqs.items():
                if old_id in matched_old_ids:
                    continue
                
                old_emb = old_data["emb"].embedding
                
                # Compute cosine distance
                import numpy as np
                v1 = np.array(new_emb)
                v2 = np.array(old_emb)
                distance = 1.0 - (np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                
                if distance < best_distance:
                    best_distance = distance
                    best_match_id = old_id

            # Threshold for similarity
            SIMILARITY_THRESHOLD = 0.1
            
            if best_match_id is not None and best_distance < SIMILARITY_THRESHOLD:
                matched_old_ids.add(best_match_id)
                old_req = old_reqs[best_match_id]["req"]
                
                # Determine if modified or unchanged
                # Compare critical fields (excluding ID, version, etc)
                is_modified = (
                    old_req.title != new_req.title or
                    old_req.description != new_req.description or
                    old_req.severity != new_req.severity or
                    old_req.type != new_req.type or
                    old_req.conditions != new_req.conditions or
                    old_req.actions != new_req.actions
                )
                
                status = DiffStatus.modified if is_modified else DiffStatus.unchanged
                
                diff_records.append(RequirementDiff(
                    id=uuid4(),
                    regulation_version_id=new_version_id,
                    old_requirement_id=best_match_id,
                    new_requirement_id=new_id,
                    status=status
                ))
                summary[status.value] += 1
            else:
                # No close match found -> added
                diff_records.append(RequirementDiff(
                    id=uuid4(),
                    regulation_version_id=new_version_id,
                    old_requirement_id=None,
                    new_requirement_id=new_id,
                    status=DiffStatus.added
                ))
                summary["added"] += 1
                
        # Unmatched old requirements are removed
        for old_id in old_reqs:
            if old_id not in matched_old_ids:
                diff_records.append(RequirementDiff(
                    id=uuid4(),
                    regulation_version_id=new_version_id,
                    old_requirement_id=old_id,
                    new_requirement_id=None,
                    status=DiffStatus.removed
                ))
                summary["removed"] += 1

    # Insert all diff records
    db.add_all(diff_records)
    
    # Generate ImpactRecords for modified/removed requirements mapped to systems
    from app.models.policies import SystemMapping
    from app.models.impacts import ImpactRecord, ImpactStatus
    from app.models.reports import Notification, NotificationType
    from sqlalchemy.dialects.postgresql import array
    
    impacts_to_add = []
    notifications_to_add = []
    
    for diff in diff_records:
        if diff.status in [DiffStatus.modified, DiffStatus.removed] and diff.old_requirement_id:
            # Find systems mapping to this old requirement
            stmt = select(SystemMapping).where(
                SystemMapping.mapped_requirement_ids.any(diff.old_requirement_id)
            )
            affected_systems = (await db.execute(stmt)).scalars().all()
            
            for sys in affected_systems:
                # Determine severity: get from old requirement for removed, new requirement for modified.
                # Actually, old_reqs has the old req dict
                old_req = old_reqs[diff.old_requirement_id]["req"]
                req_severity = old_req.severity
                
                if diff.status == DiffStatus.modified and diff.new_requirement_id:
                    new_req = new_reqs[diff.new_requirement_id]["req"]
                    req_severity = new_req.severity
                    
                impact = ImpactRecord(
                    id=uuid4(),
                    org_id=sys.org_id,
                    system_mapping_id=sys.id,
                    requirement_diff_id=diff.id,
                    severity=req_severity,
                    status=ImpactStatus.unresolved
                )
                impacts_to_add.append(impact)
                
                notif = Notification(
                    id=uuid4(),
                    org_id=sys.org_id,
                    type=NotificationType.impact_alert,
                    payload={
                        "system_name": sys.system_name,
                        "impact_record_id": str(impact.id),
                        "requirement_diff_id": str(diff.id),
                        "severity": req_severity.value
                    }
                )
                notifications_to_add.append(notif)
                
    db.add_all(impacts_to_add)
    db.add_all(notifications_to_add)
    await db.flush() # Need IDs for background jobs
    
    # --- Phase 12 Async Notification Dispatch ---
    from app.models.jobs import BackgroundJob, JobStatus
    
    jobs_to_add = []
    for notif in notifications_to_add:
        job = BackgroundJob(
            job_type="notification",
            status=JobStatus.pending,
            payload={"notification_id": str(notif.id)}
        )
        jobs_to_add.append(job)
        
    if jobs_to_add:
        db.add_all(jobs_to_add)
        await db.flush()
        
        from app.worker.tasks import task_dispatch_notification
        for job, notif in zip(jobs_to_add, notifications_to_add):
            task_dispatch_notification.apply_async(
                args=[str(job.id), str(notif.id)],
                queue="notifications"
            )

    # Update RegulationVersion.diff_summary
    version_stmt = select(RegulationVersion).where(RegulationVersion.id == new_version_id)
    new_version = (await db.execute(version_stmt)).scalar_one_or_none()
    if new_version:
        new_version.diff_summary = summary
        
    await db.flush()
    logger.info(f"Computed diff for version {new_version_id}: {summary}")
    return summary
