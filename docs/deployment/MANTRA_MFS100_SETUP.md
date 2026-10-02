# Mantra MFS100 capture setup

The application now starts capture through the Mantra SDK. You do **not**
need to open MFS100 Test or click its **Start Capture** command.

The replaceable file at
`C:\Program Files\Mantra\MFS100\Driver\MFS100Test\FingerData\FingerImage.bmp`
is not used. The SDK image is transferred from memory, so a new capture cannot
silently replace the evidence while the application is reading it.

## How capture works

Local Streamlit:

`Streamlit -> 32-bit capture helper -> MANTRA.MFS100.dll -> USB sensor`

Hosted Streamlit:

`Hosted page in examiner browser -> 127.0.0.1 bridge -> SDK -> USB sensor`

The hosted server cannot read a USB device or a `C:` drive on an examiner's
computer. The bridge is therefore required when the application is hosted.
It listens only on the loopback address, checks the exact website origin and a
pairing code, and accepts one capture at a time.

## Before testing

1. Install the Mantra MFS100 driver/SDK 9.0.2.5 on the Windows computer.
2. Connect the MFS100 directly to a USB port.
3. Close **MFS100 Test Application**. Two programs cannot control the sensor at
   the same time.
4. Confirm Windows Device Manager shows the scanner without a warning icon.

## Local application

No bridge is required when Streamlit and the sensor are on the same Windows PC.
The application detects the installed SDK and uses direct capture.

```powershell
python -m streamlit run app/streamlit_app.py
```

Open **Analyze**, choose **Capture from Mantra sensor**, press **Capture
fingerprint**, and then place one finger flat on the scanner. `AutoCapture`
starts and stops the scanner automatically.

To use mock images deliberately, set `MANTRA_SENSOR_MODE=mock`. Real capture is
the default.

## Hosted application

### 1. Configure the hosted Streamlit process

Set these variables on the hosting provider:

```text
MANTRA_SENSOR_MODE=real
MANTRA_SENSOR_TRANSPORT=bridge
MANTRA_BRIDGE_URL=http://127.0.0.1:8765
```

`MANTRA_BRIDGE_URL` is intentionally loopback. JavaScript runs in the
examiner's browser, so this address refers to the examiner's PC.

### 2. Start the bridge on every examiner PC

Open PowerShell in the project folder. Replace the example with the exact
origin shown in the browser address bar (scheme, host, and port; no path):

```powershell
powershell -ExecutionPolicy Bypass -File tools/mantra_bridge/start_bridge.ps1 `
  -HostedOrigin "https://your-fsd-domain.example"
```

Keep that PowerShell window open. It displays a **Pairing code**. The code is
stored for the current Windows user at
`%LOCALAPPDATA%\FSD-XAI\mantra-bridge-token.txt`, so it remains the same after a
restart unless that file is removed.

### 3. Pair and capture

1. Open the hosted system in current Microsoft Edge or Google Chrome.
2. Select **Capture from Mantra sensor**.
3. Enter the pairing code and press **Connect**.
4. If the browser asks for permission to access devices on the local network,
   choose **Allow**. Modern Chromium browsers require this permission for a
   public HTTPS site to call a loopback service.
5. Press **Capture fingerprint**, then place the finger on the sensor.

The pairing code stays in browser local storage. It is not sent to the hosted
Streamlit Python process. Captured image data is sent to Streamlit only after a
successful SDK capture.

## Common errors

- **MFS100 not Found (-1307):** reconnect the USB cable, check Device Manager,
  close MFS100 Test, and restart the bridge.
- **Incorrect format / BadImageFormat:** run the supplied helper; it deliberately
  launches 32-bit Windows PowerShell for the installed 32-bit native DLL.
- **Web origin is not allowed:** restart the bridge with the exact hosted origin.
  `https://example.com` and `https://www.example.com` are different origins.
- **Could not connect to local bridge:** keep the bridge window open and allow
  the browser's local-network permission. Check that security software is not
  blocking loopback port 8765.
- **Timeout (-1140):** hold a clean, dry finger flat and still, then retry.

Do not expose port 8765 through router forwarding, a public IP, or a reverse
proxy. It is designed only for `127.0.0.1` on the examiner's computer.
