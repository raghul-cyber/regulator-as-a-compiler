import time
import logging
from typing import List, Optional, Tuple
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field
import openai

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.requirements import Requirement, RequirementType, Severity
from app.models.llm_logs import LLMCallLog
from app.pipelines.chunking import SectionChunk
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI async client
# Requires OPENAI_API_KEY in environment
client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class ExtractRequirementType(str, Enum):
    obligation = "obligation"
    prohibition = "prohibition"
    permission = "permission"

class ExtractSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ExtractedRequirement(BaseModel):
    type: ExtractRequirementType
    title: str
    description: str
    conditions: List[str] = Field(description="A list of conditions under which this requirement applies")
    actions: List[str] = Field(description="A list of specific actions required to satisfy this requirement")
    severity: ExtractSeverity = Field(description="Estimated severity/impact of non-compliance")
    evidence_required: List[str] = Field(description="Types of evidence needed to prove compliance")
    references: List[str] = Field(description="References back to the text, like 'Article 5(1)'")

class ExtractionResult(BaseModel):
    requirements: List[ExtractedRequirement]

class ClassificationResult(BaseModel):
    has_requirements: bool = Field(description="True if the text contains legal requirements (obligations, prohibitions, permissions)")

async def log_llm_call(db: AsyncSession, stage: str, model: str, response, start_time: float):
    """Helper to log LLM usage."""
    latency = int((time.time() - start_time) * 1000)
    prompt_tokens = 0
    completion_tokens = 0
    
    if hasattr(response, 'usage') and response.usage:
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        
    # Cost estimation (approximate as of mid-2024 pricing)
    cost = 0.0
    if "gpt-4o-mini" in model:
        cost = (prompt_tokens / 1_000_000) * 0.15 + (completion_tokens / 1_000_000) * 0.60
    elif "gpt-4o" in model:
        cost = (prompt_tokens / 1_000_000) * 5.00 + (completion_tokens / 1_000_000) * 15.00
        
    log_entry = LLMCallLog(
        pipeline_stage=stage,
        model_used=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency,
        cost_usd=cost
    )
    db.add(log_entry)
    # We won't commit here, we let the parent transaction handle it

async def classify_chunk(chunk_text: str, db: AsyncSession) -> bool:
    """Uses a cheap model to determine if the chunk contains requirements."""
    start_time = time.time()
    model = "gpt-4o-mini"
    try:
        response = await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": "You are a legal text classifier. Answer if the provided text contains any strict legal obligations, prohibitions, or permissions."},
                {"role": "user", "content": chunk_text}
            ],
            response_format=ClassificationResult,
            temperature=0.0
        )
        
        await log_llm_call(db, "classification", model, response, start_time)
        return response.choices[0].message.parsed.has_requirements
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        # Fail open: if classification fails, assume it has requirements to be safe
        return True

async def extract_requirements(chunk_text: str, db: AsyncSession) -> List[ExtractedRequirement]:
    """Uses a strong model to extract structured requirements with a retry loop."""
    model = "gpt-4o-2024-08-06"
    max_retries = 1
    
    for attempt in range(max_retries + 1):
        start_time = time.time()
        try:
            response = await client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": "Extract all legal requirements (obligations, prohibitions, permissions) from the provided regulation text. Provide accurate severity, conditions, and actions."},
                    {"role": "user", "content": chunk_text}
                ],
                response_format=ExtractionResult,
                temperature=0.0
            )
            
            await log_llm_call(db, "extraction", model, response, start_time)
            parsed = response.choices[0].message.parsed
            
            if parsed:
                return parsed.requirements
            return []
            
        except Exception as e:
            logger.warning(f"Extraction failed on attempt {attempt}: {e}")
            if attempt == max_retries:
                logger.error("Max retries reached for extraction.")
                return []

def calculate_confidence(extracted: ExtractedRequirement) -> float:
    """
    Score the extraction quality based on rule-based heuristics.
    Since OpenAI Structured Outputs guarantees schema conformity, 
    we score based on completeness of data.
    """
    score = 1.0
    
    if not extracted.conditions:
        score -= 0.1
    if not extracted.actions:
        score -= 0.1
    if not extracted.evidence_required:
        score -= 0.1
    if not extracted.references:
        score -= 0.1
        
    # Example heuristic: if the title is extremely short, penalize
    if len(extracted.title) < 10:
        score -= 0.1
        
    return max(0.0, score)

async def process_chunk_extraction(chunk: SectionChunk, regulation_version_id: UUID, db: AsyncSession) -> List[Requirement]:
    """Orchestrates classification, extraction, and scoring for a chunk."""
    
    has_reqs = await classify_chunk(chunk.text, db)
    if not has_reqs:
        return []
        
    extracted_list = await extract_requirements(chunk.text, db)
    
    db_requirements = []
    
    # We assign the requirement to the first section_id in the chunk
    # (or could map based on references, but taking first is safe fallback)
    primary_section_id = chunk.section_ids[0] if chunk.section_ids else None
    
    for ext in extracted_list:
        score = calculate_confidence(ext)
        
        req = Requirement(
            regulation_version_id=regulation_version_id,
            section_id=primary_section_id,
            type=RequirementType(ext.type.value),
            title=ext.title,
            description=ext.description,
            conditions={"items": ext.conditions},
            actions={"items": ext.actions},
            severity=Severity(ext.severity.value),
            evidence_required={"items": ext.evidence_required},
            references={"items": ext.references},
            confidence_score=score
            # validation_status is handled by validation_routing.py
        )
        db_requirements.append(req)
        
    return db_requirements
