from fastapi import APIRouter, Request, HTTPException, Depends
from svix.webhooks import Webhook
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.organizations import Organization
from app.models.users import User

router = APIRouter()

@router.post("/clerk")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    headers = request.headers

    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(status_code=400, detail="Missing svix headers")

    wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
    try:
        evt = wh.verify(payload, headers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    evt_type = evt.get("type")
    data = evt.get("data", {})

    if evt_type == "user.created":
        clerk_user_id = data.get("id")
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address") if email_addresses else ""
        
        new_org = Organization(name=f"{email}'s Org", plan="trial")
        db.add(new_org)
        await db.flush() 

        new_user = User(
            clerk_user_id=clerk_user_id,
            email=email,
            org_id=new_org.id,
            role="admin" 
        )
        db.add(new_user)
        await db.flush()

        from app.models.audit import AuditLog
        audit_log = AuditLog(
            org_id=new_org.id,
            actor_id=new_user.id,
            action="user.created",
            entity_type="user",
            entity_id=new_user.id,
            metadata_payload={"email": email}
        )
        db.add(audit_log)
        await db.commit()

    return {"success": True}
