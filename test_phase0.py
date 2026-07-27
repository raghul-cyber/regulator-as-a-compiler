import subprocess
import time
import urllib.request
import urllib.error
import sys
import os

def test_endpoint(url, name, expected_status_codes=[200], max_retries=15):
    print(f"Testing {name} at {url}...")
    for i in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                status = response.getcode()
                if status in expected_status_codes:
                    print(f"[{name}] SUCCESS: Status {status}")
                    return True
                else:
                    print(f"[{name}] FAILURE: Unexpected status {status}")
                    return False
        except urllib.error.HTTPError as e:
            if e.code in expected_status_codes:
                print(f"[{name}] SUCCESS (HTTPError): Status {e.code}")
                return True
            else:
                print(f"[{name}] RETRYING ({i+1}/{max_retries}): Status {e.code}")
        except urllib.error.URLError as e:
            print(f"[{name}] RETRYING ({i+1}/{max_retries}): {e.reason}")
        except Exception as e:
            print(f"[{name}] RETRYING ({i+1}/{max_retries}): {e}")
        time.sleep(2)
    print(f"[{name}] FATAL: Could not connect to {url}")
    return False

def main():
    api_process = None
    web_process = None
    success = True
    
    try:
        # 1. Start API Server
        print("Starting FastAPI Backend...")
        # Since we use powershell script to activate, we just run the python from venv directly
        venv_python = os.path.join("apps", "api", "venv", "Scripts", "python.exe")
        uvicorn_module = "uvicorn"
        api_process = subprocess.Popen(
            [venv_python, "-m", uvicorn_module, "app.main:app", "--port", "8000"],
            cwd="apps/api"
        )
        
        # 2. Start Next.js Frontend
        print("Starting Next.js Frontend...")
        web_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "-p", "3000"],
            cwd="apps/web",
            shell=True
        )
        
        # 3. Test API Health
        api_ok = test_endpoint("http://localhost:8000/health", "API /health")
        
        # 4. Test Web Sign-In Page (should return 200)
        # Note: Clerk will handle the sign-in URL, it should return HTML
        web_ok = test_endpoint("http://localhost:3000/sign-in", "Web /sign-in")
        
        if not api_ok or not web_ok:
            success = False
            
    finally:
        print("Cleaning up processes...")
        if api_process:
            api_process.terminate()
        if web_process:
            web_process.terminate()
            
    if success:
        print("\n=== ALL TESTS PASSED ===")
        sys.exit(0)
    else:
        print("\n=== SOME TESTS FAILED ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
