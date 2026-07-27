# Demo Media Instructions

This directory houses demo GIFs and video recordings of the **Regulation-as-Code Compiler** workflow for presentation in the main root `README.md`.

## How to Record `demo.gif`

To record the 30-second end-to-end demo:
1. **Start the local Docker stack**:
   ```bash
   docker compose -f infra/docker-compose.yml up -d
   ```
2. **Open the application**: Navigate to `http://localhost:3000` in Google Chrome or Arc.
3. **Record using Terminalizer or Screenflow / LICEcap**:
   - Step 1: Upload a sample regulation (`GDPR_Official_Text.pdf`) in the `/regulations/upload` view.
   - Step 2: Navigate to the Requirement Browser (`/regulations/[id]`) and filter by `validation_status = pending_review`.
   - Step 3: Expand an obligation row, click the reference link to highlight the source OCR document text, and click **Approve**.
   - Step 4: Open a terminal window alongside the browser and execute a live API evaluation call:
     ```bash
     curl -X POST "http://localhost:8000/api/v1/check-compliance" \
       -H "X-API-Key: sk_live_demo_key" \
       -H "Content-Type: application/json" \
       -d '{"system_name":"Checkout-Service","configuration":{"data_retention_days":30,"encryption_at_rest":"AES-256"}}'
     ```
4. **Export and save**:
   - Save the recording as `demo.gif` in this directory (`docs/media/demo.gif`).
   - Keep file size under 15 MB for fast GitHub README rendering.
5. **Update README.md**:
   - Replace the placeholder comment in the main `README.md` with:
     ```html
     <div align="center">
       <img src="./docs/media/demo.gif" alt="Regulation-as-Code Compiler Demo" width="85%" style="border-radius: 12px; border: 1px solid #374151;" />
     </div>
     ```
