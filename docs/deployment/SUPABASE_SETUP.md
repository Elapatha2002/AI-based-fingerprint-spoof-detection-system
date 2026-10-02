# Connect FSD-XAI to your Supabase project

This setup targets **fingerprint-spoof-detection-system**, project
`cbifgdvmohxaxvjlxdkx`, and the private bucket `fingerprint-evidence`.
Do not use the older signature-attendance project.

## 1. Prepare Supabase

Open your fingerprint project in the Supabase dashboard.

1. Open **Connect** and select the **Session pooler** connection. The provided
   project uses host `aws-0-ap-southeast-1.pooler.supabase.com`, port `5432`.
   If the dashboard now shows a different host, stop and update `HOST` in
   `app/setup_supabase.py` before setup.
2. Have your **database password** ready. This is the password chosen when
   creating the project, not your Supabase website password. If forgotten, use
   **Reset database password**. Resetting affects other connections to this
   project; do not reset it unnecessarily.
3. Open **Storage**. Ensure the bucket is named **fingerprint-evidence** and
   **Public bucket is OFF**. Do not make fingerprint evidence public.
4. Open Storage's **S3 configuration** section (it may appear under Storage
   settings). Copy its S3 **endpoint** and **region**. Generate an **S3 access
   key**, and privately save its **Access Key ID** and **Secret Access Key**.
   These are NOT the publishable/anon key or service-role API key.

The app uses Supabase's PostgreSQL session pooler and S3-compatible Storage.
S3 access keys bypass Storage RLS and must remain on your server, never in
browser code or shared screenshots. See the official
[database connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)
and [S3 authentication guide](https://supabase.com/docs/guides/storage/s3/authentication).

## 2. Open your project's terminal

In VS Code, choose **Terminal > New Terminal**. It must be in the project
folder, the folder containing `app` and `requirements-supabase.txt`.
Stop any running Streamlit app first with **Ctrl+C** in its terminal.

Run this command and wait for it to finish:

```powershell
python -m pip install -r requirements-supabase.txt
```

This adds connection/UI dependencies to your existing Python environment.
It does not install or replace the project's trained models or all inference
dependencies. For a new hosting server, also use `requirements-hosted.txt`
and provide the selected checkpoint. Supabase does not run the Streamlit app.

## 3. Run the setup wizard

```powershell
python -m app.setup_supabase
```

Answer the questions one at a time:

| Question | What to enter |
| --- | --- |
| Supabase DATABASE password | The database password from step 1 |
| Administrator username | Press Enter for `admin`, or choose your own |
| Full name | Your name, shown as the examiner |
| APPLICATION login password | Choose a new password of at least 12 characters |
| Type it again | Repeat that same new application password |
| Connect file storage now? | Press Enter for Yes |
| S3 endpoint | Paste the endpoint from Storage's S3 configuration |
| S3 region | Use the region shown there; default is `ap-southeast-1` |
| S3 Access Key ID | Paste the generated S3 Access Key ID |
| S3 Secret Access Key | Paste the generated S3 Secret Access Key |
| Type SETUP | Type `SETUP` and press Enter to confirm |

**Hidden prompts show no characters, including no dots. This is normal.**
Paste/type the value and press Enter. Do not send passwords or keys in chat.

The wizard creates private application tables, a restricted database login,
and your first super-admin account. It saves the runtime configuration in
`.env.supabase`, already excluded by `.gitignore`. It does **not** save the
Supabase database administrator password or your application password there.
The application password is stored only as a salted hash in the database.

This is a **fresh cloud database**, not an automatic data migration. Existing
SQLite files, local evidence and any old cloud data are left untouched; they
are not automatically copied or recovered. Back them up before any later
migration. Rerunning setup preserves existing application accounts and does
not reset their passwords. Keep the original `.env.supabase` to resume setup.

If you select No for storage, database accounts work but evidence files remain
on this computer. Do not deploy that configuration to a server without a
persistent disk. Rerun the wizard and select Yes to configure cloud storage.

## 4. Start the app and sign in

The Supabase setup dependencies do not include model/explanation libraries.
Before running fingerprint analysis, install the full application dependencies
in the same Python environment:

```powershell
python -m pip install -r requirements-hosted.txt
```

In particular, Python's `pytorch_grad_cam` module is installed by the
**grad-cam** package (not a package named `pytorch_grad_cam`). The full
requirements also install SHAP and LIME. If you see a missing-module error,
stop Streamlit, run the command above, and restart it.

Local dependency repair verified on 2026-10-02: `grad-cam 1.5.7`,
`shap 0.52.0`, and `lime 0.2.0.1` import successfully in
`C:\Python313\python.exe`. Grad-CAM++ generated a 224 x 224 heatmap using the
real default MobileNet checkpoint on a synthetic image. This verifies the
Grad-CAM execution path, not biometric accuracy or full SHAP/LIME execution.
Missing explainers now show individual errors without crashing the result;
failed panels are excluded from saved heatmaps and block complete-XAI reports.

```powershell
python -m streamlit run app/streamlit_app.py
```

Open the local URL printed in the terminal. Sign in with the **application
username and application password you chose**, not the Supabase password.

The browser keeps a signed session for up to eight hours, so a normal refresh
does not return the examiner to the login page. The cookie contains only an
opaque signed account identifier/version and expiry, never a password or case
data. It is revalidated against the database after a full refresh. Signing out,
disabling the account, changing its password or changing its role invalidates
the session. Hosted deployments must use HTTPS; browsers with cookies disabled
cannot retain the session across a refresh.

## 5. Manage examiner accounts

1. Sign in as your super admin.
2. Open **Settings > Add examiner**.
3. Enter a unique username, full name and password; keep role **examiner**.
4. Click **Create account**. Share the login privately with that person.
5. In **Settings > Users**, use **Edit** to change the name, email, role or
   reset the password. Usernames are intentionally fixed.
6. Use **Disable**, then confirm, to revoke access without deleting the account.
   Use **Enable** to restore access.
7. To delete, expand **Delete account @username**, type the exact username,
   then confirm permanent deletion. Cases and audit records remain intact.

Examiners see **My account**, not user-management controls. They can change
their own password by supplying the current one. Password resets, role changes,
disabling or deleting an account revoke its existing sessions when those
sessions next interact with the app. Already-running analysis is not cancelled.
Logout clears that session's case context. The last active super admin cannot
be deleted, disabled or demoted, and you cannot delete or disable yourself.

User-management changes are recorded atomically in the database audit log.
This retains the existing shared-case workspace: examiner roles do not imply
per-examiner isolation of forensic case records.

## Where users are stored

In Supabase, use **Table Editor** and select schema **fsd_app**, then **users**.
These are application accounts using the existing username/password login.
They will **not** appear under **Authentication > Users**: this implementation
does not migrate to Supabase Auth or add public registration/email reset flows.
Use the application's Settings screen for account changes, not manual table
edits, so validation, session revocation and auditing run together.

The private schema is not intended to be exposed through the Data API. Browser
roles cannot read it; only the restricted server login gets data permissions.
That login cannot create tables or update/delete audit entries. All application
users share that server connection role; the Python service checks individual
user permissions. Never expose database/S3 credentials to application users.

## Check the connection or troubleshoot

### Navigation/Analyze fix: restart after updating the code

The navigation bar previously redirected internal result/processing pages to
Home, so Run analysis could never reach the classifier. Navigation now uses
change callbacks instead of triggering a second full render, and the single
analysis button prepares its result page in a callback. Ordinary navigation
reuses a verified identity for up to 30 seconds. Account mutations bypass that
short cache and verify permissions inside their database transaction.

PostgreSQL connections now use a lazy, bounded, thread-safe pool (up to three
per application process). Cloud schema checks no longer run on every UI click.
The pool allows enough time for Supabase's regional TLS negotiation and does
not issue a separate health query for every connection lease.
These changes follow the documented
[Streamlit callback API](https://docs.streamlit.io/develop/api-reference/widgets/st.pills)
and [Psycopg connection-pool lifecycle](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).

Stop the running app with **Ctrl+C**, then run:

```powershell
python -m pip install -r requirements-supabase.txt
python -m streamlit run app/streamlit_app.py
```

Do not rerun the provisioning wizard for this fix. The first model load and
SHAP/LIME explanation generation still take computation time. The fix removes
redundant navigation/database work; it does not bypass real inference.

Follow-up verification: **46 tests passed; 20 disposable-PostgreSQL integration
tests skipped**. The real default MobileNet classifier completed a synthetic
image smoke test. Three read-only Supabase `SELECT 1` checks succeeded, including
reused connections. This did not change cloud records, validate biometric
accuracy, or test a complete real-image XAI run.

### Connection check

```powershell
python -m app.setup_supabase --check
```

This checks the database and bucket without uploading evidence. A successful
check is not a completed upload/download pilot. Before giving access to pilot
users, save a non-sensitive test analysis, restart the app, reopen it from
History, and verify the stored image and PDF. Use synthetic test images first.

- **Module not found:** rerun the dependency-install command with the same
  `python` used to launch the app.
- **Connection failure:** confirm the project is active, the session-pooler
  host is still correct, the network permits port 5432, and the database
  password is correct. Do not paste connection URLs into chat.
- **Storage failure:** check both S3 keys, endpoint and region. Confirm the
  bucket exists and is private. An API key is not an S3 key.
- **Interrupted setup:** rerun the wizard using the original `.env.supabase`.
  It saves the generated runtime secret before provisioning for safe retries.
- **No tables under public:** select schema **fsd_app**, not **public**.
- **Old environment settings:** operating-system/hosting environment variables
  override files. Remove/update stale `DATABASE_URL` or `FSDXAI_STORAGE_BACKEND`
  in the launching environment privately. Restart the app after changes.
- **Forgotten application password:** another super admin can reset it in
  Settings. If the only super admin is locked out, controlled owner recovery
  is needed; rerunning setup does not bypass login or overwrite passwords.

## When you deploy

Deploy the Streamlit app to a Python host that supports its long-running
process and model memory requirements. Set the values from `.env.supabase` in
that host's private environment-variable settings; do not publish the file in
`public_html`, source control or a downloadable archive. No need to save the
Supabase administrator password on the host. Keep `FSDXAI_OFFLINE_MODE=0` and
use HTTPS. SQLite remains available locally only when `DATABASE_URL` is empty.
A configured PostgreSQL failure never silently switches to SQLite.

Keep separate backups of the database and evidence objects. Deleting an account
does not delete its forensic evidence. Review retention, access control and
consent before using real biometric data. This change is not a security audit
or a certification of forensic admissibility.

## Verification recorded for this change

On 2026-10-01, the unit/regression suite passed **40 tests**, including actual
Streamlit account-widget tests. **20 PostgreSQL integration tests were
skipped**: the disposable PostgreSQL Docker image download did not complete.
The separate thesis service harness passed **29 checks**, with **6 scenarios
not executed** and no failures. Its new results are in
`Documents/Thsis final submission/verification/supabase_regression_20261001/`;
the previous thesis register was not overwritten.

No live Supabase connection or real Storage upload/download was tested, and no
cloud data was provisioned. Run the setup/check and synthetic-evidence steps
above before pilot testing. The storage unit tests use a mocked S3 client;
they are not evidence of a successful cloud upload.

To rerun the local suite:

```powershell
python -B -m unittest discover -s tests -v
```

PostgreSQL integration tests are opt-in using `FSD_TEST_POSTGRES_URL`. They
require a **disposable**, localhost-only PostgreSQL database named `fsd_test`
and a test administrator able to create roles. They truncate their own fixture
tables on each test. Never point them at your Supabase project or real data.
