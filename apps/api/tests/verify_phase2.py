import asyncio
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app as main_app
from app.models.users import User, UserRole
from app.core.auth import get_current_user

client = TestClient(main_app)

roles = [UserRole.admin, UserRole.compliance_officer, UserRole.developer, UserRole.legal_counsel, UserRole.auditor]

org_a_id = uuid4()
org_b_id = uuid4()
dummy_req_id = "c5555555-5555-5555-5555-555555555555"
dummy_reg_id = "c1111111-1111-1111-1111-111111111111"

actions = {
    "Upload Regulations": ("POST", "/api/regulations/upload", {"data": {"jurisdiction": "EU", "name": "GDPR"}, "files": {"file": ("test.pdf", b"test", "application/pdf")}}),
    "Review/Approve Requirements": ("PATCH", f"/api/requirements/{dummy_req_id}", {"json": {"validation_status": "approved"}}),
    "Manage API Keys": ("POST", "/api/api-keys", {"json": {"name": "test"}}),
    "View Dashboard": ("GET", f"/api/regulations/{dummy_reg_id}", {}),
    "Manage Org Users": ("GET", "/api/org/users", {}),
}

expected_matrix = {
    UserRole.admin: {"Upload Regulations": True, "Review/Approve Requirements": True, "Manage API Keys": True, "View Dashboard": True, "Manage Org Users": True},
    UserRole.compliance_officer: {"Upload Regulations": True, "Review/Approve Requirements": True, "Manage API Keys": False, "View Dashboard": True, "Manage Org Users": False},
    UserRole.developer: {"Upload Regulations": False, "Review/Approve Requirements": False, "Manage API Keys": True, "View Dashboard": True, "Manage Org Users": False},
    UserRole.legal_counsel: {"Upload Regulations": False, "Review/Approve Requirements": True, "Manage API Keys": False, "View Dashboard": True, "Manage Org Users": False},
    UserRole.auditor: {"Upload Regulations": False, "Review/Approve Requirements": False, "Manage API Keys": False, "View Dashboard": True, "Manage Org Users": False},
}

def run_tests():
    print("| Role | Action | Expected | Actual | PASS/FAIL |")
    print("|---|---|---|---|---|")
    
    for role in roles:
        user = User(id=uuid4(), org_id=org_a_id, clerk_user_id=f"clerk_{role.value}", role=role, email=f"{role.value}@orga.com")
        main_app.dependency_overrides[get_current_user] = lambda: user
        
        for action_name, (method, url, kwargs) in actions.items():
            expected = expected_matrix[role][action_name]
            
            res_status = None
            try:
                res = client.request(method, url, **kwargs)
                res_status = res.status_code
                if action_name == "Manage API Keys":
                    actual = res_status != 403 and res_status != 404
                else:
                    actual = res_status not in (403, 401)
            except Exception as e:
                # If an exception is raised (e.g. IntegrityError from DB), it means RBAC allowed the request
                print(f"EXCEPTION for {role.value} {action_name}: {repr(e)}")
                actual = True
            
            if action_name == "Manage API Keys" and expected:
                pass_str = "FAIL (Not Implemented)"
            else:
                passed = (expected == actual)
                pass_str = "PASS" if passed else f"FAIL (Status: {res_status})"
            
            print(f"| {role.value} | {action_name} | {expected} | {actual} | {pass_str} |")

if __name__ == "__main__":
    run_tests()
