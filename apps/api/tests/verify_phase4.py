import asyncio
import os
import fitz
from uuid import uuid4
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.main import app as main_app
from app.models.users import User, UserRole
from app.core.auth import get_current_user
from app.db.session import AsyncSessionLocal
from app.models.documents import SourceDocument, DocumentSection
from app.models.organizations import Organization
from app.pipelines.extraction import extract_document_text
from app.pipelines.segmentation import segment_document

org_a_id = uuid4()

def create_mock_gdpr_pdf():
    path = "mock_gdpr.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = """Preamble
This is the GDPR Mock PDF for testing Phase 4.
Article 5
Principles relating to processing of personal data.
Personal data shall be processed lawfully, fairly and in a transparent manner.
Article 17
Right to erasure ('right to be forgotten').
The data subject shall have the right to obtain from the controller the erasure of personal data.
Article 33
Notification of a personal data breach to the supervisory authority.
In the case of a personal data breach, the controller shall without undue delay...
"""
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()
    return path

def create_low_quality_pdf():
    # Creating an image-based PDF for OCR fallback testing
    path = "mock_low_quality.pdf"
    doc = fitz.open()
    page = doc.new_page()
    
    # We will simulate a scanned page by just inserting a tiny string or empty string
    # Actually, the extraction logic checks `len(text) < 50` and falls back to OCR.
    # We can just put a very small string that doesn't trigger OCR, wait, < 50 triggers OCR.
    # Let's put a short string to trigger OCR fallback.
    text = "Short text"
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()
    return path

async def run_tests():
    print("--- Phase 4 Verification ---")
    transport = ASGITransport(app=main_app)
    
    # Setup Admin user
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.role == UserRole.admin))).scalars().first()
        if not admin_user:
            org = (await db.execute(select(Organization))).scalars().first()
            if not org:
                org = Organization(id=uuid4(), name="Test Org", plan="standard")
                db.add(org)
                await db.flush()
            admin_user = User(id=uuid4(), org_id=org.id, clerk_user_id="clerk_admin", role=UserRole.admin, email="admin@orga.com")
            db.add(admin_user)
            await db.commit()

    main_app.dependency_overrides[get_current_user] = lambda: admin_user

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Normal Extraction & Segmentation
        pdf_path = create_mock_gdpr_pdf()
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        print("\n1. Uploading GDPR PDF...")
        res = await client.post(
            "/api/regulations/upload", 
            data={'jurisdiction': 'EU', 'name': 'GDPR Phase4 Test'}, 
            files={'file': ('mock_gdpr.pdf', pdf_bytes, 'application/pdf')}
        )
        print("Upload Response:", res.status_code)
        
        if res.status_code == 200:
            version_id = res.json()['regulation_version_id']
            
            async with AsyncSessionLocal() as db:
                src_doc = (await db.execute(select(SourceDocument).where(SourceDocument.regulation_version_id == version_id))).scalar_one_or_none()
                
                # Run Phase 4 pipelines explicitly (normally they run inline if no Celery)
                # We will just verify the raw_text is populated
                print(f"1. SourceDocument.raw_text populated: {'PASS' if src_doc.raw_text else 'FAIL'}")
                print(f"Raw Text Preview: {src_doc.raw_text[:100]}...\n")
                
                sections = (await db.execute(select(DocumentSection).where(DocumentSection.source_document_id == src_doc.id).order_by(DocumentSection.order_index))).scalars().all()
                
                print(f"2. Sections found: {len(sections)}")
                for sec in sections:
                    print(f"   - Label: {sec.reference_label} | Order: {sec.order_index} | Preview: {sec.raw_text[:50]}...")
                
                print("\n3. Order Index is monotonically increasing:", all(sections[i].order_index <= sections[i+1].order_index for i in range(len(sections)-1)))

        # 4. Low Quality / Scanned Page (OCR Fallback)
        low_pdf = create_low_quality_pdf()
        with open(low_pdf, "rb") as f:
            low_pdf_bytes = f.read()
            
        print("\n4. Uploading low quality PDF to trigger OCR fallback...")
        res_ocr = await client.post(
            "/api/regulations/upload", 
            data={'jurisdiction': 'EU', 'name': 'Low Quality Test'}, 
            files={'file': ('mock_low.pdf', low_pdf_bytes, 'application/pdf')}
        )
        if res_ocr.status_code == 200:
            version_id_ocr = res_ocr.json()['regulation_version_id']
            async with AsyncSessionLocal() as db:
                src_doc_ocr = (await db.execute(select(SourceDocument).where(SourceDocument.regulation_version_id == version_id_ocr))).scalar_one_or_none()
                print(f"OCR Used Flag: {src_doc_ocr.ocr_used}")
                
        # Cleanup
        os.remove(pdf_path)
        os.remove(low_pdf)

if __name__ == "__main__":
    asyncio.run(run_tests())
