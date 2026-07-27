from typing import List
from app.models.requirements import Requirement, ValidationStatus, Severity

def route_requirements(requirements: List[Requirement], confidence_threshold: float = 0.8) -> List[Requirement]:
    """
    Assigns validation_status based on confidence and severity thresholds.
    High/Critical severity or low confidence routes to pending_review.
    Otherwise, starts at draft.
    """
    for req in requirements:
        if req.confidence_score < confidence_threshold or req.severity in (Severity.high, Severity.critical):
            req.validation_status = ValidationStatus.pending_review
        else:
            req.validation_status = ValidationStatus.draft
            
    return requirements
