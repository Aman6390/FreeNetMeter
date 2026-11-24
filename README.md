# FreeNetMeter

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![UI: PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Platform: Windows 10 / 11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-lightgrey.svg)]()

**FreeNetMeter** is a complete, production-quality, free, open-source network throughput meter and bandwidth telemetry monitor engineered specifically for Windows 10 and Windows 11 (64-bit).

Written 100% from scratch with no copied code, assets, or telemetry, FreeNetMeter provides accurate real-time network speeds, an always-on-top desktop widget, system tray telemetry, detailed historical daily usage reporting, safe CSV exports, and seamless Windows system integration.

---

## Key Features

- **Live Speed Telemetry**: Download and upload throughput sampled once per second from 64-bit Windows kernel counters (`MIB_IF_ROW2` / `GetIfEntry2`).
- **Always-on-Top Floating Widget**: Minimalist, frameless, translucent desktop overlay with custom typography, direction glyphs, edge clamping, and zero-flicker dragging.
- **Master Dashboard (12 Modules)**: Complete desktop dashboard window with live traffic analytics, historical logs, WiFi diagnostics, interface inventory, and active process inspection.
- **Interactive Speed Test Suite**: Analog semicircular arc speedometer gauge with 60 FPS spring animation, dual-curve real-time throughput & latency graph, bufferbloat grading (A+ to F), and connection quality heuristics (Streaming, Gaming, Video calls).
- **Top Hardware Telemetry Bar**: Live detection of Hostname, clean CPU model name from Windows registry, installed RAM, Windows OS edition, and system uptime.
- **System Tray & 21+ Quick Tools**: Complete context menu with network stopwatch, active sockets monitor, ping diagnostics, quick Windows tool shortcuts, adapter selection, and position locking.
- **Dynamic Adapter Filtering**: Automatically monitors physical adapters that are operational (UP), while excluding virtual adapters (Hyper-V, Docker, WSL, VMware, VirtualBox, Bluetooth PAN) and loopbacks.
- **High-DPI Awareness**: Per-monitor DPI scaling ensures crisp rendering across all display scales (100%, 125%, 150%, 200%).
- **Data Usage Database**: SQLite WAL-mode local database aggregating daily, weekly, monthly, and all-time network usage broken down by interface in local calendar days.
- **Safe CSV Export**: One-click export encoded in UTF-8 with BOM (`utf-8-sig`) for Excel compatibility, with formula injection escaping.
- **Windows Autostart & Single-Instance**: Optional launch with Windows via `HKCU Run` without admin rights, and single-instance local socket IPC.
- **100% Free & Privacy First**: Zero telemetry, zero external tracking, zero ads, zero bloatware. Runs offline.

---

## Architecture Overview

FreeNetMeter is engineered with strict separation of concerns into distinct layers:

```text
freenetmeter/
├── core/                        # Pure business logic (100% testable)
│   ├── constants.py             # Centralized timing, limits, registry paths, defaults
│   ├── counter_source.py        # CounterSource interface, PsutilCounterSource & FakeCounterSource
│   ├── speed_calculator.py      # Monotonic timing, counter reset handling, 64-bit wrap safety, smoothing
│   ├── formatter.py             # Unit scaling (SI decimal vs IEC binary), bits vs bytes, arrow styles
│   ├── usage_accumulator.py     # Aggregates deltas into local calendar days (midnight & DST safe)
│   ├── interface_filter.py      # Adapter inclusion/exclusion rules, double-counting prevention
│   ├── speed_test_engine.py     # Multi-stage QThread speed test engine with bufferbloat grading
│   └── system_telemetry.py      # Hostname, CPU, RAM, OS edition, and uptime telemetry
├── storage/                     # Persistence subsystems
│   ├── settings_store.py        # Atomic JSON settings with schema versioning & migration
│   └── usage_database.py        # SQLite storage (WAL mode, busy timeout, speed test history, safe CSV)
├── platform/                    # Windows-specific integrations behind small interfaces
│   ├── autostart.py             # HKCU Run registry manager (no elevation required)
│   ├── single_instance.py       # Inter-process communication via QLocalServer / QLocalSocket
│   └── theme_listener.py        # Windows dark/light mode registry detector
├── ui/                          # GUI components
│   ├── assets.py                # Original programmatic vector icon generator (QPainter)
│   ├── worker.py                # Background QThread for counter sampling & database commits
│   ├── widget.py                # Frameless, draggable, always-on-top desktop overlay
│   ├── tray.py                  # System tray icon with live tooltips & 21+ context menu actions
│   ├── dashboard_window.py      # Flagship Master Dashboard window with 12 stacked module views
│   ├── settings_window.py       # Tabbed configuration dialog with live preview
│   ├── usage_window.py          # Network usage dashboard with summary cards & table
│   ├── stopwatch_dialog.py      # Session network timer and traffic counter
│   ├── connection_info_dialog.py# Detailed network IP, gateway, DNS, and MAC discovery
│   └── widgets/                 # Custom Apple-styled visual components
│       ├── analog_gauge.py      # Semicircular arc speedometer with spring needle animation
│       ├── live_graph.py        # Real-time speed fill underlay and latency curve canvas
│       ├── system_badges.py     # Top hardware badges header bar with auto-refresh
│       └── sidebar.py           # 12-item navigation sidebar with active pill highlights
├── tools/
│   ├── verify_counters.py       # Independent 30s cross-check tool against Windows PowerShell
│   ├── create_share_package.py  # Automated ZIP packaging script for distribution
│   └── capture_dashboard_preview.py # Headless high-DPI dashboard snapshot generator
├── tests/                       # Complete pytest suite (68 unit, property, and integration tests)
├── app.py                       # Subsystem wiring and lifecycle management
├── main.py                      # Application entry point and CLI argument parser
├── FreeNetMeter.spec            # PyInstaller build specification
└── WINDOWS_CHECKLIST.md         # Numbered beginner verification checklist
```

---

## Installation & Setup

### Option 1: Standalone Software Installation (Recommended)
You can install FreeNetMeter as a native Windows desktop app without running from the command line:

1. Double-click `install.bat` (or run `./Install-FreeNetMeter.ps1 -LaunchAfterInstall` in PowerShell).
2. It automatically:
   - Installs FreeNetMeter into `%LOCALAPPDATA%\Programs\FreeNetMeter` (no administrator privileges needed).
   - Creates a **Desktop shortcut** (`FreeNetMeter.lnk`) with the official high-resolution icon.
   - Creates a **Windows Start Menu shortcut** (`FreeNetMeter.lnk`).
3. To uninstall at any time, run `uninstall.bat` (or `./Uninstall-FreeNetMeter.ps1`).

---

### Option 2: Run from Python Source

#### Requirements
- Windows 10 or Windows 11 (64-bit)
- Python 3.11 or newer (Python 3.13 tested)

#### 1. Clone or Extract
```powershell
cd "e:\projects\internet speed meter"
```

#### 2. Install Runtime Dependencies
```powershell
pip install -r requirements.txt
```

#### 3. Install Development & Test Dependencies
```powershell
pip install -r requirements-dev.txt
```

---

## Running the Application

### Normal GUI Mode
```powershell
python main.py
```
Launches the floating desktop widget and system tray icon.

### Live Speed Debug Stream (Console Mode)
```powershell
python main.py --debug-speeds
```
Runs a headless console monitor displaying raw throughput in bytes per second and formatted units once per second. Ideal for side-by-side comparison with Windows Task Manager (Performance tab).

---

## Packaging into Standalone Windows Executable

FreeNetMeter is packaged using **PyInstaller**:

```powershell
python -m PyInstaller --name FreeNetMeter --windowed --noconfirm --clean main.py
```

### Expected Output
```text
INFO: PyInstaller: 6.22.3
INFO: Platform: Windows-10-10.0.19041-SP0
INFO: Processing standard module hooks...
INFO: Building PKG (CArchive) FreeNetMeter.pkg completed successfully.
INFO: Building EXE from EXE-00.toc completed successfully.
INFO: Building COLLECT COLLECT-00.toc completed successfully.
INFO: Build complete! The results are available in: E:\projects\internet speed meter\dist
```

The resulting standalone executable is located at:
`dist\FreeNetMeter\FreeNetMeter.exe`.

---

## Built-In Verification & Beginner Checklist

For a step-by-step verification protocol, see [WINDOWS_CHECKLIST.md](WINDOWS_CHECKLIST.md).

### Independent Windows Counter Cross-Check
FreeNetMeter includes an independent verification tool that compares byte counters sampled by `psutil` against Windows PowerShell kernel statistics (`Get-NetAdapterStatistics`) over a 30-second interval:

```powershell
python tools/verify_counters.py
```

**Expected Result**:
```text
=== FreeNetMeter Independent Counter Verification ===
Sampling byte counters for 30 seconds across two independent sources:
  Source 1: psutil.net_io_counters(pernic=True) [used by FreeNetMeter]
  Source 2: Windows PowerShell Get-NetAdapterStatistics [Windows Kernel]

Taking baseline snapshot (T=0s)...
Waiting 30 seconds...
Taking final snapshot...

--------------------------------------------------------------------------
Adapter Name         | Recv (psutil)  | Recv (Win)     | Diff %   | Status
--------------------------------------------------------------------------
Wi-Fi                | 2,154,820      | 2,155,012      | 0.01   % | PASS  
--------------------------------------------------------------------------

RESULT: PASS - the app's numbers match Windows
```

---

## Testing & Quality Assurance

FreeNetMeter includes comprehensive automated test suites:
- **Unit Tests**: Full test coverage of pure logic in `core/` and `storage/`.
- **Property-Based Tests**: Uses `hypothesis` to prove that speeds and data usage are strictly non-negative and finite across arbitrary counter sequences, resets, and wraps.
- **Format Verification**: Boundary tests for decimal SI and binary IEC unit scales, bits vs. bytes, precision clamps, and CSV formula injection neutralization.

Run all tests with coverage:
```powershell
python -m pytest --cov=core --cov=storage --cov=tools --cov-report=term-missing
```

Code quality and linting verification:
```powershell
python -m black --check .
python -m ruff check .
python -m mypy .
```

---

## Configuration Reference

Settings are persisted in `%APPDATA%\FreeNetMeter\settings.json`:

| Setting | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `schema_version` | `int` | `1` | Schema version identifier for automated migrations |
| `widget_x`, `widget_y` | `int` | `null` | Desktop coordinate position (clamped to active monitors) |
| `locked_position` | `bool` | `false` | When true, prevents dragging the widget |
| `widget_visible` | `bool` | `true` | Visibility state of the floating desktop overlay |
| `selected_interfaces` | `list` | `[]` | Explicit adapter names to include in totals |
| `excluded_keywords` | `list` | *virtuals* | Adapter name substrings filtered out by default |
| `unit_system` | `str` | `"decimal"` | `"decimal"` (1 KB = 1000 B) or `"binary"` (1 KiB = 1024 B) |
| `unit_type` | `str` | `"bytes"` | `"bytes"` (B/s, KB/s) or `"bits"` (bps, Kbps) |
| `fixed_unit` | `str` | `"auto"` | `"auto"` or specific scale override (e.g. `"MB/s"`) |
| `decimal_precision` | `int` | `1` | Number of decimal places: `0`, `1`, or `2` |
| `arrow_style` | `str` | `"triangle"` | Glyph style: `"triangle"`, `"arrow"`, `"letters"`, `"none"` |
| `theme_mode` | `str` | `"system"` | `"system"` (reads Windows registry), `"dark"`, or `"light"` |
| `font_family` | `str` | `"Segoe UI"`| Font family for speed numbers |
| `font_size` | `int` | `10` | Font size in points (clamped between 8 and 24) |
| `color_download` | `str` | `"#00E676"`| Hex color string for download rate |
| `color_upload` | `str` | `"#29B6F6"`| Hex color string for upload rate |
| `background_opacity` | `int` | `85` | Overlay opacity percentage (20 to 100) |
| `start_with_windows` | `bool` | `false` | Autostart via HKCU Run key |
| `retention_days` | `int` | `0` | Number of days to retain usage records (`0` = forever) |
| `rolling_window_size`| `int` | `3` | Number of samples in rolling average smoothing |

---

## Assumptions & Design Decisions

Where system or technical specifications allowed multiple interpretations, conservative engineering choices were implemented:

1. **64-Bit Counter Wrap Handling**: Windows 10/11 IP Helper API (`GetIfEntry2` / `MIB_IF_ROW2`) provides 64-bit unsigned integer byte counters (`ULONG64`), which will not naturally overflow under normal operating conditions. However, network adapter resets, VPN reconnections, or device reboots cause counters to reset to zero. FreeNetMeter strictly treats any situation where `current_counter < previous_counter` as an adapter reset: delta is clamped to 0, speed is 0, and the baseline is re-anchored to prevent negative speeds or traffic spikes.
2. **Sleep & Resume Gap Threshold**: If the monotonic time elapsed between two consecutive samples exceeds 5.0 seconds (e.g. system suspended to sleep), FreeNetMeter discards the interval, attributes 0 bytes of usage across the gap, and re-baselines.
3. **Data Usage Attribution**: Daily usage is attributed strictly to the **local calendar date** (`YYYY-MM-DD`) active at the moment the sample is processed. Midnight rollovers and DST clock shifts are handled gracefully without duplicate dates or dropped hours.
4. **Formula Injection Sanitization**: When exporting usage to CSV, any field value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is prepended with a single quote `'` to prevent spreadsheet applications (e.g. Microsoft Excel) from interpreting values as executable formulas.
5. **Single-Instance IPC**: Single-instance mutual exclusion is managed via a user-scoped `QLocalServer` named pipe (`FreeNetMeter_SingleInstance_IPC_<username>`). Stale socket pipes left behind by power loss or unclean termination are automatically detected, removed, and recovered.

---

## Known Limitations

- **Throughput vs. Link Capacity**: FreeNetMeter measures actual network data throughput currently traversing the selected adapters; it does not measure maximum theoretical ISP link bandwidth (such as an external speed test).
- **Virtual Adapters & VPNs**: When a full-tunnel VPN is connected, packets may traverse both the virtual VPN tunnel adapter and the underlying physical adapter. To prevent double-counting, virtual adapter keywords (`hyper-v`, `wsl`, `tailscale`, etc.) are excluded by default. Users can adjust adapter selection in Settings.
- **ISP Accounting Differences**: Internet Service Providers often measure traffic at external gateway interfaces including ISP framing, packet headers, or billing cycles that differ slightly from endpoint operating system socket counters.

---

## Privacy Statement

FreeNetMeter is completely private:
- It makes **no network connections of its own** whatsoever.
- It contains **zero telemetry**, tracking, advertising, analytics, or cloud synchronization.
- All configuration and usage history files are stored exclusively on your local hard drive in `%APPDATA%\FreeNetMeter`.

---

## License

FreeNetMeter is licensed under the permissive [MIT License](LICENSE).
Copyright (c) 2026 FreeNetMeter Contributors.
