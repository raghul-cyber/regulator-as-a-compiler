import logging
import tiktoken
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.documents import DocumentSection

logger = logging.getLogger(__name__)

# Standard OpenAI encoding for gpt-4
encoding = tiktoken.get_encoding("o200k_base")

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

class SectionChunk:
    def __init__(self):
        self.sections: List[DocumentSection] = []
        self.text = ""
        self.token_count = 0
        self.section_ids: List[UUID] = []

    def add_section(self, section: DocumentSection):
        self.sections.append(section)
        self.section_ids.append(section.id)
        
        # Format the text with its reference label for the LLM
        formatted = f"\n\n--- {section.reference_label} ---\n{section.raw_text}"
        self.text += formatted
        self.token_count += count_tokens(formatted)

async def chunk_document(source_document_id: UUID, db: AsyncSession, max_tokens: int = 2000) -> List[SectionChunk]:
    """
    Groups document sections into LLM-sized chunks (e.g. ~2000 tokens).
    Ensures that sections stay together if possible.
    """
    stmt = select(DocumentSection).where(
        DocumentSection.source_document_id == source_document_id
    ).order_by(DocumentSection.order_index)
    
    result = await db.execute(stmt)
    sections = list(result.scalars().all())
    
    if not sections:
        return []

    chunks = []
    current_chunk = SectionChunk()
    
    for section in sections:
        section_tokens = count_tokens(f"\n\n--- {section.reference_label} ---\n{section.raw_text}")
        
        # If adding this section exceeds max_tokens and we already have sections in the chunk,
        # finish the current chunk and start a new one.
        if current_chunk.token_count + section_tokens > max_tokens and current_chunk.sections:
            chunks.append(current_chunk)
            current_chunk = SectionChunk()
            
        current_chunk.add_section(section)
        
    if current_chunk.sections:
        chunks.append(current_chunk)
        
    return chunks
