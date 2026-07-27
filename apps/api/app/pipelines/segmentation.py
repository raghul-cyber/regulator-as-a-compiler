import re
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documents import SourceDocument, DocumentSection

logger = logging.getLogger(__name__)

# Basic regex for articles and sections. 
# Matches "Article 1", "Section 3.2", "Part I", etc. at the start of a line.
# For more complex nested clauses like "5(1)(e)", we'll need a more robust parser in the future,
# but this regex will handle standard high-level boundaries for Phase 4.
SECTION_PATTERN = re.compile(
    r'^(?:Article|Section|Part|Chapter)\s+([A-Z0-9\.\-]+(?:(?:\([a-z0-9]\))+)?)[^\n]*',
    re.IGNORECASE | re.MULTILINE
)

async def segment_document(source_document_id: UUID, db: AsyncSession):
    """
    Segments a document's raw_text into logical sections (e.g. Articles, Sections)
    using regular expressions, preserving document order.
    """
    stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise ValueError(f"SourceDocument {source_document_id} not found")

    text = document.raw_text
    if not text:
        logger.warning(f"SourceDocument {source_document_id} has no raw_text to segment.")
        return

    # Find all section headers
    matches = list(SECTION_PATTERN.finditer(text))
    
    sections_to_add = []
    
    if not matches:
        # If no sections are found, treat the whole document as one section
        logger.info("No section boundaries detected. Storing entire document as one section.")
        sections_to_add.append(
            DocumentSection(
                source_document_id=source_document_id,
                reference_label="Document",
                raw_text=text.strip(),
                order_index=0
            )
        )
    else:
        # Handle preamble (text before the first matched section)
        if matches[0].start() > 0:
            preamble_text = text[0:matches[0].start()].strip()
            if preamble_text:
                sections_to_add.append(
                    DocumentSection(
                        source_document_id=source_document_id,
                        reference_label="Preamble",
                        raw_text=preamble_text,
                        order_index=0
                    )
                )
        
        # Iterate over matches to extract sections
        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            section_content = text[start_pos:end_pos].strip()
            
            # The reference label will be the match itself (e.g. "Article 5")
            reference_label = match.group(0).strip()
            
            sections_to_add.append(
                DocumentSection(
                    source_document_id=source_document_id,
                    reference_label=reference_label,
                    raw_text=section_content,
                    order_index=len(sections_to_add)
                )
            )
            
    db.add_all(sections_to_add)
    await db.commit()
    
    return len(sections_to_add)
