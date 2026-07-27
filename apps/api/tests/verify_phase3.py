import asyncio
import io
from uuid import uuid4
import httpx
from httpx import ASGITransport
from app.main import app as main_app
from app.models.users import User, UserRole
from app.core.auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.regulations import Regulation, RegulationVersion
from app.models.documents import SourceDocument
from app.models.audit import AuditLog

org_a_id = uuid4()

async def run_tests():
    print("--- Phase 3 Verification ---")
    transport = ASGITransport(app=main_app)
    # 1. Fetch an existing Admin user to test successful upload
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.role == UserRole.admin))).scalars().first()
        if not admin_user:
            from app.models.organizations import Organization
            org = (await db.execute(select(Organization))).scalars().first()
            if not org:
                org = Organization(id=uuid4(), name="Test Org")
                db.add(org)
                await db.flush()
            admin_user = User(id=uuid4(), org_id=org.id, clerk_user_id="clerk_admin", role=UserRole.admin, email="admin@orga.com")
            db.add(admin_user)
            await db.commit()

    main_app.dependency_overrides[get_current_user] = lambda: admin_user

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Upload a real GDPR PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        files = {'file': ('gdpr_test.pdf', pdf_content, 'application/pdf')}
        data = {'jurisdiction': 'EU', 'name': 'GDPR Phase3 Test'}
        
        print("\n1. Uploading PDF...")
        res = await client.post("/api/regulations/upload", data=data, files=files)
        print("Upload Response:", res.status_code)
        
        if res.status_code == 200:
            resp_json = res.json()
            reg_id = resp_json['regulation_id']
            version_id = resp_json['regulation_version_id']
            
            # Verify DB objects
            async with AsyncSessionLocal() as db:
                reg = (await db.execute(select(Regulation).where(Regulation.id == reg_id))).scalar_one_or_none()
                reg_ver = (await db.execute(select(RegulationVersion).where(RegulationVersion.id == version_id))).scalar_one_or_none()
                src_doc = (await db.execute(select(SourceDocument).where(SourceDocument.regulation_version_id == version_id))).scalar_one_or_none()
                
                print(f"DB Row Regulation: {'PASS' if reg else 'FAIL'}")
                print(f"DB Row RegulationVersion: {'PASS' if reg_ver else 'FAIL'}")
                print(f"DB Row SourceDocument: {'PASS' if src_doc else 'FAIL'}")
                print(f"Source Document Storage Path: {src_doc.storage_path}")
                
                # Step 2: Confirm file exists at storage path
                try:
                    # Strip local:// prefix
                    path = src_doc.storage_path.replace("local://", "")
                    with open(path, "rb") as f:
                        saved_bytes = f.read()
                    print(f"2. File bytes match: {'PASS' if saved_bytes == pdf_content else 'FAIL'}")
                except Exception as e:
                    print(f"2. File check failed: {e}")

                # Step 3: Confirm audit_log row
                audit = (await db.execute(
                    select(AuditLog).where(
                        AuditLog.entity_id == reg_id,
                        AuditLog.action == "regulation.uploaded"
                    )
                )).scalars().first()
                print(f"3. Audit Log written: {'PASS' if audit and audit.actor_id == admin_user.id else 'FAIL'}")

        # Step 4: Attempt non-PDF
        print("\n4. Uploading non-PDF file...")
        bad_files = {'file': ('test.txt', b"hello world", 'text/plain')}
        res_bad = await client.post("/api/regulations/upload", data=data, files=bad_files)
        print("Non-PDF Upload Response:", res_bad.status_code, res_bad.json())

        # Step 5: Attempt as Developer
        print("\n5. Uploading as Developer...")
        dev_user = User(id=uuid4(), org_id=org_a_id, clerk_user_id="clerk_dev", role=UserRole.developer, email="dev@orga.com")
        main_app.dependency_overrides[get_current_user] = lambda: dev_user
        
        res_dev = await client.post("/api/regulations/upload", data=data, files=files)
        print("Developer Upload Response:", res_dev.status_code, res_dev.json())

if __name__ == "__main__":
    asyncio.run(run_tests())
