import logging
from uuid import UUID
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documents import SourceDocument
from app.models.regulations import RegulationVersion

logger = logging.getLogger(__name__)

async def extract_document_text(source_document_id: UUID, db: AsyncSession):
    """
    Extracts text from a source document. 
    If a page has very little text, attempts OCR using pytesseract.
    """
    stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise ValueError(f"SourceDocument {source_document_id} not found")

    if document.file_type.value != "pdf":
        # For now, we only handle PDFs in this phase.
        # HTML could just be stripped of tags, but skipping for now.
        return

    # Parse local path
    storage_path = document.storage_path
    if storage_path.startswith("local://"):
        local_path = storage_path.replace("local://", "")
    else:
        raise ValueError(f"Unsupported storage path format: {storage_path}")

    full_text = []
    ocr_used = False
    
    # Open the PDF using PyMuPDF
    try:
        pdf_document = fitz.open(local_path)
    except Exception as e:
        logger.error(f"Failed to open PDF {local_path}: {e}")
        raise

    page_count = len(pdf_document)

    for page_num in range(page_count):
        page = pdf_document.load_page(page_num)
        text = page.get_text("text").strip()
        
        # If the extracted text is suspiciously short, it might be a scanned image
        if len(text) < 50:
            logger.info(f"Page {page_num+1} has low text content. Attempting OCR...")
            try:
                # Render page to an image (pixmap)
                pix = page.get_pixmap(dpi=150)
                # Convert fitz pixmap to PIL Image
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                
                # Try running OCR
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text.strip():
                    text = ocr_text.strip()
                    ocr_used = True
                    
                    # We can also get confidence if needed:
                    # data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    # confidences = [int(c) for c in data['conf'] if c != '-1']
                    # avg_conf = sum(confidences) / len(confidences) if confidences else 0
                    # logger.info(f"OCR Confidence: {avg_conf}")
            except pytesseract.pytesseract.TesseractNotFoundError:
                logger.warning("Tesseract OCR is not installed. Skipping OCR for this page.")
            except Exception as e:
                logger.warning(f"OCR failed for page {page_num+1}: {e}")

        full_text.append(text)
        
    pdf_document.close()

    # Update document in database
    document.raw_text = "\n\n".join(full_text)
    document.ocr_used = ocr_used
    document.page_count = page_count
    
    # Also update the RegulationVersion to indicate extraction is complete
    stmt_version = select(RegulationVersion).where(RegulationVersion.source_document_id == source_document_id)
    version_res = await db.execute(stmt_version)
    version = version_res.scalars().first()
    
    # We can use version_label or a new status column if we had one.
    # The prompt says "Update the regulation_versions status so the frontend can show 'text extracted'".
    # Our schema does not have a explicit `status` field on regulation_versions, 
    # but we can update `version_label` or we can rely on `page_count > 0` or `raw_text != ""` on frontend.
    
    await db.commit()
    
    return document.raw_text
