# OCI Always Free deployment guide

This guide deploys the FSD-XAI research demonstrator on an OCI Always Free VM
with a hosted SQLite database and private OCI Object Storage. It is designed
for a low-traffic thesis demonstration, not operational forensic casework.

## Before you start

You cannot recover a cloud account or its provider credentials from the source
code. Use the provider's **Forgot password** flow if you still own the account
email. If the AWS bucket was permanently deleted, its original objects cannot
be restored from the local SQLite metadata alone.

The local project still has the source, checkpoints and `fsd_xai.db`. First
make two copies of both `fsd_xai.db` and `storage_local/`: one on removable
storage and one encrypted backup location.

OCI requires a new account, a verified mobile number, and usually a credit
card for signup. Never use `FSDXAI_OFFLINE_MODE=1` on a server accessible from
the internet.

## 1. Regain an application administrator account locally

From the project root in PowerShell:

```powershell
python scripts\recover_admin_access.py --database .\fsd_xai.db --username admin
```

Choose and record a new password in a password manager. This updates only the
local SQLite account entry; it does not touch AWS or OCI.

Test the recovered account locally:

```powershell
Remove-Item Env:FSDXAI_OFFLINE_MODE -ErrorAction SilentlyContinue
python -m streamlit run app\streamlit_app.py
```

Sign in using the password you just chose, then stop Streamlit with `Ctrl+C`.

## 2. Create the OCI account and Always Free VM

1. Go to the OCI Free Tier signup page and create a new account. Save its email,
   password, recovery codes, tenancy OCID and home region in a password manager.
2. Choose the home region carefully. Always Free ARM compute is available only
   in the home region.
3. In **Compute > Instances**, create an Ubuntu 24.04 instance.
4. Select `VM.Standard.A1.Flex`, with **2 OCPUs and 12 GB RAM**. Confirm the
   instance is labelled **Always Free Eligible** before creating it.
5. Generate and download an SSH key. Keep it private; it is the administrator
   login for the VM.
6. Use a 50 GB boot volume initially. Keep total use within OCI's free limits.
7. In the VCN security list or network security group, allow:
   - TCP 22 **only from your own public IP** for SSH.
   - TCP 443 from the internet for the application after HTTPS is configured.
   - Do **not** expose port 8501 publicly.

OCI may temporarily report that the Always Free ARM shape has no available
capacity. Wait and retry or try another availability domain; do not select a
paid shape by mistake.

## 3. Create private object storage

1. Create a compartment named `fsd-xai`.
2. Go to **Storage > Buckets > Create bucket** in that compartment.
3. Use a non-sensitive name such as `fsd-xai-artifacts-<random-suffix>`.
4. Choose the **Standard** tier, keep the bucket **private**, enable object
   versioning, and enable automatic cleanup of incomplete multipart uploads.
5. Use Oracle-managed encryption initially. Do not make the bucket public and
   do not create public pre-authenticated links for fingerprints or reports.
6. Create a least-privilege application user/group that can inspect the bucket
   and read/create/overwrite/delete objects only in this bucket.
7. In that user's profile, create a **Customer Secret Key**. Copy its access key
   and secret once into your password manager. These values are used by OCI's
   S3-compatible API.
8. Note the bucket name, Object Storage namespace, and region. The endpoint is:

   ```text
   https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
   ```

## 4. Copy the project and database to the VM

On Windows, use `scp` or VS Code Remote SSH. Do not copy `.env`, AWS keys,
`storage_local/` contents from real cases, or the old AWS credential CSV.

On the VM:

```bash
sudo adduser --disabled-password --gecos "" fsdxai
sudo mkdir -p /opt/fsd-xai /var/lib/fsd-xai
sudo chown -R fsdxai:fsdxai /opt/fsd-xai /var/lib/fsd-xai
```

Copy the source to `/opt/fsd-xai` and copy a **backup** of `fsd_xai.db` to
`/var/lib/fsd-xai/fsd_xai.db`. Keep the original Windows copy unchanged.

Install the application dependencies and create a virtual environment:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip build-essential libgl1 sqlite3
sudo -u fsdxai python3 -m venv /opt/fsd-xai/.venv
sudo -u fsdxai /opt/fsd-xai/.venv/bin/python -m pip install --upgrade pip
sudo -u fsdxai /opt/fsd-xai/.venv/bin/pip install -r /opt/fsd-xai/requirements-hosted.txt
```

Then check that the MobileNet checkpoint can load before exposing the service:

```bash
sudo -u fsdxai /opt/fsd-xai/.venv/bin/python -c "
import torch
from src.models.factory import get_model
model = get_model('mobilenetv3_large', pretrained=False)
state = torch.load('checkpoints/mobilenetv3_large_20260616_105902/best.pth', map_location='cpu', weights_only=False)
model.load_state_dict(state['model_state'] if 'model_state' in state else state)
print('Checkpoint load passed')
"
```

## 5. Configure OCI secrets outside the repository

Create `/etc/fsd-xai/fsd-xai.env`, owned by root and readable only by root and
the `fsdxai` service account. This is not the project `.env` file.

```ini
DATABASE_PATH=/var/lib/fsd-xai/fsd_xai.db
FSDXAI_REAL_MODEL=1
FSDXAI_MODEL=mobilenetv3_large
FSDXAI_CHECKPOINT=checkpoints/mobilenetv3_large_20260616_105902/best.pth

AWS_ACCESS_KEY_ID=<OCI customer-secret access key>
AWS_SECRET_ACCESS_KEY=<OCI customer-secret secret key>
AWS_REGION=<OCI region, for example ap-mumbai-1>
S3_BUCKET_NAME=<private OCI bucket name>
S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
S3_ADDRESSING_STYLE=path
S3_SERVER_SIDE_ENCRYPTION=none
```

The names `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are retained only for
the existing boto3 client interface. They contain **OCI Customer Secret Key**
values in this configuration, not AWS credentials.

Secure the file after creating it:

```bash
sudo chown root:root /etc/fsd-xai/fsd-xai.env
sudo chmod 600 /etc/fsd-xai/fsd-xai.env
```

## 6. Run Streamlit behind a reverse proxy

Run Streamlit only on loopback:

```bash
sudo -u fsdxai /opt/fsd-xai/.venv/bin/python -m streamlit run \
  /opt/fsd-xai/app/streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Put Caddy or Nginx in front of it. Use a domain you control and configure the
proxy to terminate HTTPS and forward only to `127.0.0.1:8501`. Do not present
real fingerprint data over plain HTTP. Keep the application login enabled and
use the recovered admin account to create examiner accounts.

Create `/etc/systemd/system/fsd-xai.service`:

```ini
[Unit]
Description=FSD-XAI Streamlit service
After=network.target

[Service]
User=fsdxai
Group=fsdxai
WorkingDirectory=/opt/fsd-xai
EnvironmentFile=/etc/fsd-xai/fsd-xai.env
ExecStart=/opt/fsd-xai/.venv/bin/python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fsd-xai
sudo systemctl status fsd-xai --no-pager
```

With a domain pointing to the VM public IP, a minimal Caddy configuration is:

```caddy
your-domain.example {
    reverse_proxy 127.0.0.1:8501
}
```

Open only port 443 to the public internet after Caddy is working. Use
`sudo journalctl -u fsd-xai -f` to diagnose startup failures.

## 7. Verify and back up

1. Sign in through HTTPS with the recovered administrator account.
2. Upload one non-sensitive test image and confirm an analysis, heatmap and PDF
   appear in the private bucket.
3. Restart the VM and confirm the case history still appears.
4. Make a SQLite backup before upgrades and copy it to a versioned backup bucket
   or encrypted external storage.
5. Set OCI budget/usage alerts and monitor the Always Free limits monthly.

## Recovery rule

Keep three copies: the VM database, versioned private object storage, and an
encrypted offline backup. Never make any one free provider the only copy of
case data.
