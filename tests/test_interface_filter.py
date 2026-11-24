"""Unit tests for InterfaceFilter.

Verifies:
- Default exclusion of loopback, Hyper-V, Docker, WSL, VMware, VirtualBox, Bluetooth PAN.
- Default selection of physical adapters that are operational (UP).
- User selection preservation, filtering of unplugged adapters, and deduplication.
- Configurable exclusion list.
- Prevention of double-counting.
"""

from __future__ import annotations

from core.counter_source import InterfaceStatus
from core.interface_filter import InterfaceFilter


def test_default_exclusion_rules() -> None:
    """Verify common virtual adapters and loopbacks are identified."""
    filt = InterfaceFilter()

    # Excluded virtual interfaces
    assert filt.is_excluded("Loopback Pseudo-Interface 1") is True
    assert filt.is_excluded("vEthernet (Default Switch)") is True
    assert filt.is_excluded("vEthernet (WSL)") is True
    assert filt.is_excluded("docker0") is True
    assert filt.is_excluded("VMware Network Adapter VMnet1") is True
    assert filt.is_excluded("VirtualBox Host-Only Ethernet Adapter") is True
    assert filt.is_excluded("Bluetooth Network Connection") is True

    # Physical valid adapters
    assert filt.is_excluded("Ethernet") is False
    assert filt.is_excluded("Wi-Fi") is False
    assert filt.is_excluded("Ethernet 2") is False


def test_default_selection_physical_and_up() -> None:
    """Verify default selection picks physical adapters that are UP."""
    filt = InterfaceFilter()
    available = [
        "Ethernet",
        "Wi-Fi",
        "vEthernet (Default Switch)",
        "Loopback Pseudo-Interface 1",
        "Ethernet 2",
    ]
    statuses = {
        "Ethernet": InterfaceStatus(is_up=True, speed_mbps=1000),
        "Wi-Fi": InterfaceStatus(is_up=False, speed_mbps=0),  # Down
        "vEthernet (Default Switch)": InterfaceStatus(is_up=True, speed_mbps=10000),  # Excluded
        "Loopback Pseudo-Interface 1": InterfaceStatus(is_up=True, speed_mbps=1000),  # Excluded
        "Ethernet 2": InterfaceStatus(is_up=True, speed_mbps=1000),
    }

    selected = filt.get_default_selected(available, statuses)
    assert selected == ["Ethernet", "Ethernet 2"]


def test_resolve_active_selection_user_preference() -> None:
    """Verify user selection takes precedence, filters unplugged adapters, and deduplicates."""
    filt = InterfaceFilter()
    available = ["Ethernet", "Wi-Fi", "Cellular"]
    statuses = {
        "Ethernet": InterfaceStatus(is_up=True),
        "Wi-Fi": InterfaceStatus(is_up=True),
        "Cellular": InterfaceStatus(is_up=True),
    }

    # User selected Wi-Fi and an unplugged USB adapter, with duplicates
    user_pref = ["Wi-Fi", "USB-Ethernet", "Wi-Fi"]
    resolved = filt.resolve_active_selection(available, user_pref, statuses)

    # Only available Wi-Fi remains, exactly once
    assert resolved == ["Wi-Fi"]


def test_custom_exclusion_list() -> None:
    """Verify exclusion list can be customized."""
    filt = InterfaceFilter(excluded_keywords=["custom_vpn", "tailscale"])
    assert filt.is_excluded("custom_vpn_adapter") is True
    assert filt.is_excluded("Tailscale") is True
    # Standard default is replaced by custom list
    assert filt.is_excluded("vEthernet (WSL)") is False

    # Update dynamically
    filt.set_excluded_keywords(["docker", "wsl"])
    assert filt.is_excluded("docker0") is True
    assert filt.is_excluded("custom_vpn_adapter") is False
