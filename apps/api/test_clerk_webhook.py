import json
import time
import hmac
import hashlib
import base64
import urllib.request

webhook_secret = "whsec_cGxhY2Vob2xkZXJfc2VjcmV0X2tleV8xMjM0NTY3ODk="

payload = {
    "data": {
        "id": "user_2test12345",
        "email_addresses": [{"email_address": "test@example.com"}]
    },
    "type": "user.created"
}

payload_bytes = json.dumps(payload).encode('utf-8')

# Build svix signature manually
msg_id = "msg_test123"
timestamp = str(int(time.time()))
secret_bytes = base64.b64decode(webhook_secret.removeprefix("whsec_"))
to_sign = f"{msg_id}.{timestamp}.{payload_bytes.decode('utf-8')}"
signature = base64.b64encode(
    hmac.new(secret_bytes, to_sign.encode('utf-8'), hashlib.sha256).digest()
).decode('utf-8')

headers = {
    "svix-id": msg_id,
    "svix-timestamp": timestamp,
    "svix-signature": f"v1,{signature}",
    "Content-Type": "application/json",
}

req = urllib.request.Request(
    'http://localhost:8000/webhooks/clerk',
    data=payload_bytes,
    headers=headers,
    method='POST'
)

try:
    response = urllib.request.urlopen(req)
    print(f"Status: {response.status}")
    print(f"Response: {response.read().decode('utf-8')}")
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
