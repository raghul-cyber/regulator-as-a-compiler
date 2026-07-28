import asyncio
import os
import sys
import uuid
import time
from datetime import date, datetime, timezone
from httpx import AsyncClient, ASGITransport
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import select

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.organizations import Organization, PlanType
from app.models.users import User, UserRole
from app.models.regulations import Regulation, RegulationVersion
from app.models.requirements import Requirement, ValidationStatus, RequirementType, Severity
from app.models.documents import SourceDocument, DocumentSection, FileType
from app.models.api_keys import ApiKey
async def setup_test_data():
    async with AsyncSessionLocal() as db:
        # Create Org & Admin
        org = Organization(name="Test Org 9", plan="trial")
        db.add(org)
        await db.flush()
        
        admin = User(clerk_user_id=f"test_clerk_{uuid.uuid4()}", email="admin9@test.com", org_id=org.id, role="admin")
        db.add(admin)
        await db.flush()
        
        # Create Regulation & Requirements
        reg = Regulation(name="GDPR_Phase9", jurisdiction="EU", source_url="http://test.com/gdpr.pdf")
        db.add(reg)
        await db.flush()
        
        ver = RegulationVersion(regulation_id=reg.id, version_label="v1", source_document_id=None, published_date=date.today(), ingested_at=datetime.now(timezone.utc))
        db.add(ver)
        await db.flush()
        
        doc = SourceDocument(regulation_version_id=ver.id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
        db.add(doc)
        await db.flush()
        section = DocumentSection(source_document_id=doc.id, order_index=1, reference_label="Art 1", raw_text="Text")
        db.add(section)
        await db.flush()
        
        # Add 3 Requirements: 2 Approved, 1 Draft
        reqs = []
        for i in range(3):
            status = ValidationStatus.approved if i < 2 else ValidationStatus.draft
            req = Requirement(
                regulation_version_id=ver.id,
                section_id=section.id,
                type=RequirementType.obligation,
                title=f"Req {i}",
                description="desc",
                conditions={}, actions={},
                severity=Severity.high,
                evidence_required={}, references={}, confidence_score=0.95,
                validation_status=status
            )
            db.add(req)
            reqs.append(req)
        await db.commit()
        
        # Fetch actual user with ID
        await db.refresh(admin)
        return org, admin, reg, ver

async def run_tests():
    org, admin, reg, ver = await setup_test_data()
    
    # We need a client that mocks get_current_user for the Settings endpoints
    # To do this cleanly, we'll just bypass auth dependency override for API tests and provide headers for api_keys
    
    from app.core.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: admin

    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        
        print("--- 1 & 2. API Key Creation & Scopes & Hashes ---")
        # Create keys
        res = await client.post("/api/v1/settings/api-keys", json={"scopes": ["read-only"]})
        assert res.status_code == 200
        key_read = res.json()["raw_key"]
        
        res = await client.post("/api/v1/settings/api-keys", json={"scopes": ["check-compliance"]})
        key_check = res.json()["raw_key"]
        
        res = await client.post("/api/v1/settings/api-keys", json={"scopes": ["admin"]})
        key_admin = res.json()["raw_key"]
        
        # Verify DB only stores hash
        async with AsyncSessionLocal() as db:
            keys = (await db.execute(select(ApiKey).where(ApiKey.org_id == org.id))).scalars().all()
            for k in keys:
                assert not k.key_hash.startswith("sk_live_")
        print("Raw key returned once, only hash stored in DB.")
        
        # Test scopes
        # Read-only trying to check-compliance
        res = await client.post("/api/v1/check-compliance", json={"payload": {}, "scope": "sys", "regulation_id": str(reg.id)}, headers={"Authorization": f"Bearer {key_read}"})
        assert res.status_code == 403, "Read-only should be rejected for check-compliance"
        
        # Check-compliance trying to read
        res = await client.get(f"/api/v1/policy/{reg.id}", headers={"Authorization": f"Bearer {key_check}"})
        assert res.status_code == 403, "Check-compliance should be rejected for read-only"
        
        # Admin trying both
        res = await client.get(f"/api/v1/policy/{reg.id}", headers={"Authorization": f"Bearer {key_admin}"})
        assert res.status_code == 200, "Admin can read"
        print("Scopes properly enforced.")

        print("--- 3. Key Revocation ---")
        # Get list of keys to find ID
        res = await client.get("/api/v1/settings/api-keys")
        assert res.status_code == 200
        keys_list = res.json()
        target_key_id = keys_list[0]["id"]
        
        res = await client.delete(f"/api/v1/settings/api-keys/{target_key_id}")
        assert res.status_code == 204
        
        # It was the read-only key, let's try a request that requires admin just to check if it's 401 (revoked)
        # Wait, the first key was read-only, let's just make an invalid request to see if it's rejected as revoked
        res = await client.get(f"/api/v1/policy/{reg.id}", headers={"Authorization": f"Bearer {key_read}"})
        assert res.status_code == 401
        assert "revoked" in res.json()["error"]["message"]
        print("Revoked key correctly rejected.")

        print("--- 4. Rate Limits ---")
        import redis.asyncio as aioredis
        from app.core.config import settings
        r = aioredis.from_url(settings.REDIS_URL)
        await r.flushall()
        await r.aclose()
        # Admin key has 10 req/min (trial org)
        # Let's make 12 requests
        success_count = 0
        limited = False
        for i in range(12):
            res = await client.get(f"/api/v1/policy/{reg.id}", headers={"Authorization": f"Bearer {key_admin}"})
            if res.status_code == 200:
                success_count += 1
            elif res.status_code == 429:
                limited = True
                break
        assert success_count == 10
        assert limited == True
        print(f"Rate limits enforced: {success_count} succeeded, throttled at 11th request.")

        print("--- 5. Endpoint Content Filtering ---")
        # We need a new fresh key with read-only to avoid rate limit or use a different org.
        # Wait, rate limit is per org. The admin key hit the limit.
        # We can mock a new org or manually delete redis keys. For simplicity, just use key_check for check-compliance which might have different limit? No, limit is per org.
        # Let's flush redis for the test.
        import redis.asyncio as redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL)
        await r.flushdb()
        
        res = await client.get(f"/api/v1/policy/{reg.id}", headers={"Authorization": f"Bearer {key_admin}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 2  # Only the 2 approved ones
        print("Policy endpoint returns only approved/enforceable data.")

        print("--- 6. Sync vs Async Check-Compliance ---")
        # Sync
        res = await client.post("/api/v1/check-compliance", json={"payload": {"bad_config": True}, "scope": "sys", "regulation_id": str(reg.id)}, headers={"Authorization": f"Bearer {key_admin}"})
        assert res.status_code == 200
        assert res.json()["status"] == "fail"
        
        # Async
        large_payload = {"config": "x" * 60000}
        res = await client.post("/api/v1/check-compliance", json={"payload": large_payload, "scope": "sys", "regulation_id": str(reg.id)}, headers={"Authorization": f"Bearer {key_admin}"})
        assert res.status_code == 200
        assert "job_id" in res.json()
        print("Sync and Async payload size routing works correctly.")
        
        print("--- 7. Consistent Error Shape and Cursor Pagination ---")
        res = await client.get("/api/v1/non-existent-route")
        assert res.status_code == 404
        assert "error" in res.json()
        assert res.json()["error"]["code"] == 404
        
        # Pagination
        res = await client.get(f"/api/v1/policy/{reg.id}?limit=1", headers={"Authorization": f"Bearer {key_admin}"})
        assert res.status_code == 200
        data1 = res.json()["data"]
        cursor = res.json()["next_cursor"]
        assert len(data1) == 1
        assert cursor is not None
        
        res2 = await client.get(f"/api/v1/policy/{reg.id}?limit=1&cursor={cursor}", headers={"Authorization": f"Bearer {key_admin}"})
        data2 = res2.json()["data"]
        assert len(data2) == 1
        assert data1[0]["id"] != data2[0]["id"]
        print("Error shape is consistent and cursor pagination works seamlessly.")

    print("\nALL PHASE 9 TESTS PASSED.")

if __name__ == "__main__":
    asyncio.run(run_tests())
