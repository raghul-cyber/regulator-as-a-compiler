import logging
import time
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.requirements import Requirement, RequirementEmbedding
from app.models.llm_logs import LLMCallLog
from app.core.config import settings
import openai

logger = logging.getLogger(__name__)
client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_embedding(text: str, db: AsyncSession) -> List[float]:
    model = "text-embedding-3-small"
    start_time = time.time()
    
    response = await client.embeddings.create(
        input=[text],
        model=model
    )
    
    # Log usage
    latency = int((time.time() - start_time) * 1000)
    prompt_tokens = response.usage.prompt_tokens
    cost = (prompt_tokens / 1_000_000) * 0.02
    
    log_entry = LLMCallLog(
        pipeline_stage="embedding",
        model_used=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=0,
        latency_ms=latency,
        cost_usd=cost
    )
    db.add(log_entry)
    
    return response.data[0].embedding

async def deduplicate_requirements(requirements: List[Requirement], db: AsyncSession, threshold: float = 0.95) -> List[Requirement]:
    """
    Generates embeddings and compares via pgvector cosine distance.
    Returns deduplicated list.
    """
    unique_reqs = []
    
    for req in requirements:
        embed_text = f"{req.title}. {req.description}"
        try:
            vector = await generate_embedding(embed_text, db)
        except Exception as e:
            logger.error(f"Embedding failed for requirement '{req.title}': {e}")
            unique_reqs.append(req)
            continue
            
        # Check against existing embeddings
        # pgvector cosine_distance (<=>) is 1 - cosine_similarity
        distance_threshold = 1.0 - threshold
        
        stmt = select(RequirementEmbedding).where(
            RequirementEmbedding.embedding.cosine_distance(vector) < distance_threshold
        ).limit(1)
        
        result = await db.execute(stmt)
        duplicate = result.scalars().first()
        
        if duplicate:
            logger.info(f"Duplicate requirement found matching existing ID {duplicate.requirement_id}. Dropping.")
        else:
            # Temporarily store the vector on the object to save it after flushing
            req._embedding_vector = vector
            unique_reqs.append(req)
            
    return unique_reqs

async def persist_embeddings(requirements: List[Requirement], db: AsyncSession):
    """
    After requirements are flushed (so they have IDs), persist their embeddings.
    """
    for req in requirements:
        if hasattr(req, "_embedding_vector") and req._embedding_vector:
            emb = RequirementEmbedding(
                requirement_id=req.id,
                embedding=req._embedding_vector,
                model_used="text-embedding-3-small"
            )
            db.add(emb)
