# FreeNetMeter: Windows Beginner Verification Checklist

This document provides a step-by-step verification protocol for **FreeNetMeter**. Every test is designed for a beginner with zero prior experience. Each step details the exact action, expected result, and diagnostic steps if anything unexpected occurs.

---

### Step 1: Install Dependencies
- **ACTION**:
  Open PowerShell in the project directory (`e:\projects\internet speed meter`) and execute:
  ```powershell
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```
- **EXPECTED RESULT**:
  All packages install successfully: `psutil`, `PyQt6`, `pytest`, `pytest-cov`, `hypothesis`, `black`, `ruff`, `mypy`, `pyinstaller`. Output ends with `Successfully installed ...` without errors.
- **IF IT FAILS**:
  Verify Python version by typing `python --version`. Python 3.11 or newer is required. Ensure your PowerShell has internet access.

---

### Step 2: Run Automated Unit Tests
- **ACTION**:
  Run pytest with coverage verification:
  ```powershell
  python -m pytest --cov=core --cov=storage --cov=tools --cov-report=term-missing
  ```
- **EXPECTED RESULT**:
  All 54 tests pass (`54 passed`), with **`core/` test coverage >= 90%** (currently 95%). No test failures or fatal errors.
- **IF IT FAILS**:
  Copy the failure traceback and note which test failed. Ensure no previous instance of the app is locking the SQLite database.

---

### Step 3: Run the Independent Windows Counter Cross-Check
- **ACTION**:
  Run the automated verification script:
  ```powershell
  python tools/verify_counters.py
  ```
  Wait 30 seconds for the two independent sources (`psutil` vs. Windows PowerShell `Get-NetAdapterStatistics`) to compare byte counters.
- **EXPECTED RESULT**:
  A summary table is printed showing each active adapter's received bytes from both sources, difference percentage (within 2% tolerance), and a final status line:
  ```text
  RESULT: PASS - the app's numbers match Windows
  ```
- **IF IT FAILS**:
  Check if Windows PowerShell execution policy restricts scripts. If the status reports `FAIL`, note the difference percentage and verify if large unmeasured background traffic occurred on an excluded adapter.

---

### Step 4: Compare Live Speeds with Windows Task Manager
- **ACTION**:
  1. Open Windows Task Manager (`Ctrl + Shift + Esc`).
  2. Click on the **Performance** tab, and select your active network adapter (e.g. **Wi-Fi** or **Ethernet**).
  3. In PowerShell, run the console debug telemetry stream:
     ```powershell
     python main.py --debug-speeds
     ```
  4. Start a download (e.g. download a large file or stream a 4K video) for 15 seconds.
  5. Press `Ctrl + C` in PowerShell to stop.
- **EXPECTED RESULT**:
  The console throughput (in KB/s or MB/s) matches Task Manager's live graph within a few percent.
- **IF IT FAILS**:
  Verify you are comparing the same physical adapter in Task Manager as selected in FreeNetMeter. Note that Task Manager displays throughput in bits per second (Kbps/Mbps) by default; multiply FreeNetMeter bytes/sec by 8 to compare exact bitrates.

---

### Step 5: Start the GUI Application
- **ACTION**:
  Launch FreeNetMeter:
  ```powershell
  python main.py
  ```
- **EXPECTED RESULT**:
  1. A sleek, semi-transparent, frameless desktop widget appears in the upper-right corner of your screen showing live upload (`▲`, top row) and download (`▼`, bottom row) speeds with tight typography.
  2. A vibrant green/blue circular speedometer icon appears in your Windows system tray (near the system clock).
- **IF IT FAILS**:
  Check `%APPDATA%\FreeNetMeter\logs\freenetmeter.log` for initialization errors. Ensure your monitor is not set to an unsupported virtual display.

---

### Step 6: Test Widget Dragging and Position Memory
- **ACTION**:
  1. Left-click and drag the floating desktop widget to the bottom-center of your screen.
  2. Right-click the widget, select **Exit FreeNetMeter**.
  3. Start the app again: `python main.py`.
- **EXPECTED RESULT**:
  The widget reappears at the exact location where you dragged it.
- **IF IT FAILS**:
  Verify write permissions to `%APPDATA%\FreeNetMeter\settings.json`. Check if the position was locked in the context menu.

---

### Step 7: Test Live Customization in Settings
- **ACTION**:
  1. Right-click the widget and select **Settings...**.
  2. In the **Appearance** tab: change the font size to 12 pt, select a different font family, and adjust the background opacity slider.
  3. In the **Display & Units** tab: change the unit to Bits (Mbps) and arrow style to `↓ / ↑`.
  4. Observe the desktop widget while the Settings dialog is still open.
  5. Click **OK**.
- **EXPECTED RESULT**:
  The widget updates instantly in real-time as you move sliders or change combo boxes. After clicking OK, settings persist across restarts.
- **IF IT FAILS**:
  Check if changes revert after restart. If so, check `%APPDATA%\FreeNetMeter\settings.json.bad`.

---

### Step 8: Compare Data Usage Window with Windows Settings
- **ACTION**:
  1. Right-click the widget and select **Data Usage...**.
  2. Open Windows Settings > **Network & Internet** > **Data usage**.
  3. Compare the totals for Today and the Past 30 Days.
- **EXPECTED RESULT**:
  FreeNetMeter displays total downloaded, uploaded, and combined bytes per adapter in modern metric cards and an itemized table. Totals agree with Windows OS historical accounting within a small margin of error (accounting for system startup timing).
- **IF IT FAILS**:
  Click the **Refresh** button in the FreeNetMeter Data Usage window. Ensure the same adapter is selected in the filter dropdown.

---

### Step 9: Test Windows Autostart
- **ACTION**:
  1. Open FreeNetMeter Settings > **System & Storage** tab.
  2. Check **Start FreeNetMeter with Windows (HKCU Run)** and click **OK**.
  3. Open Windows Task Manager > **Startup apps** tab (or check registry key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
- **EXPECTED RESULT**:
  `FreeNetMeter` is listed in Startup apps. No administrator rights or UAC prompt was requested.
- **IF IT FAILS**:
  Verify the registry entry using PowerShell:
  `Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "FreeNetMeter"`.

---

### Step 10: Test System Sleep and Resume
- **ACTION**:
  1. Leave FreeNetMeter running.
  2. Put your computer to Sleep (`Windows Key > Power > Sleep`).
  3. Wait 30 seconds, wake the PC, and log back in.
- **EXPECTED RESULT**:
  FreeNetMeter detects the sample gap (> 5 seconds), re-baselines the counters, and shows normal throughput without an artificial speed spike or invalid million-MB/s spike.
- **IF IT FAILS**:
  Check `%APPDATA%\FreeNetMeter\logs\freenetmeter.log` for gap detection logs.

---

### Step 11: Test Dynamic Adapter Changes (VPN / Wi-Fi)
- **ACTION**:
  1. Connect to a VPN (e.g. ProtonVPN, Tailscale, or corporate VPN) or plug in a USB Ethernet adapter.
  2. Disconnect the VPN after 20 seconds.
- **EXPECTED RESULT**:
  The app handles adapters appearing and disappearing cleanly without crashes or freezes. Unchecked/excluded virtual VPN adapters do not distort physical totals.
- **IF IT FAILS**:
  Inspect `%APPDATA%\FreeNetMeter\logs\freenetmeter.log` to check adapter enumeration events.

---

### Step 12: Test Single-Instance Enforcement
- **ACTION**:
  1. While FreeNetMeter is running, open a new PowerShell terminal and launch a second instance:
     ```powershell
     python main.py
     ```
- **EXPECTED RESULT**:
  The second instance outputs:
  ```text
  FreeNetMeter is already running. Brought existing window to front.
  ```
  The second instance exits immediately with exit code 0. The first instance's widget is brought to the front.
- **IF IT FAILS**:
  Check if a second process remains in Task Manager. Check IPC named pipe connectivity.

---

### Step 13: Test Clean Exit and Tray Icon Hygiene
- **ACTION**:
  1. Right-click the system tray icon and select **Exit FreeNetMeter**.
  2. Hover your mouse over the system notification tray area.
- **EXPECTED RESULT**:
  The desktop widget closes immediately. The system tray icon disappears cleanly without leaving a "ghost" icon when hovered. All background threads terminate.
- **IF IT FAILS**:
  Check Windows Task Manager to confirm `python.exe` / `FreeNetMeter.exe` is no longer running.
