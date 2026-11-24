"""Network interface filtering and adapter selection.

Manages inclusion and exclusion rules to automatically select physical, active
network adapters while filtering out loopback interfaces and common virtual
adapters (Hyper-V, Docker, WSL, VMware, VirtualBox, Bluetooth PAN).

Ensures adapter names are sanitized and deduplicated so an adapter is never
double-counted.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from core.constants import DEFAULT_EXCLUDED_INTERFACE_KEYWORDS
from core.counter_source import InterfaceStatus


class InterfaceFilter:
    """Manages interface inclusion/exclusion rules and active interface discovery."""

    def __init__(
        self,
        excluded_keywords: Sequence[str] | None = None,
    ) -> None:
        """Initialize filter with keyword exclusion list.

        Args:
            excluded_keywords: Substrings (case-insensitive) that flag an adapter as virtual/loopback.
        """
        if excluded_keywords is None:
            self._excluded_keywords = list(DEFAULT_EXCLUDED_INTERFACE_KEYWORDS)
        else:
            self._excluded_keywords = [kw.strip().lower() for kw in excluded_keywords if kw.strip()]

    @property
    def excluded_keywords(self) -> list[str]:
        """Return the active list of exclusion keywords."""
        return list(self._excluded_keywords)

    def set_excluded_keywords(self, keywords: Sequence[str]) -> None:
        """Update exclusion keywords."""
        self._excluded_keywords = [kw.strip().lower() for kw in keywords if kw.strip()]

    def is_excluded(self, interface_name: str) -> bool:
        """Check if an adapter name matches any virtual/loopback exclusion rule.

        Args:
            interface_name: Interface name string (e.g. 'vEthernet (Default Switch)').

        Returns:
            True if interface matches an exclusion keyword, False otherwise.
        """
        name_lower = interface_name.strip().lower()
        for kw in self._excluded_keywords:
            if kw in name_lower:
                return True
        return False

    def get_default_selected(
        self,
        available_interfaces: Sequence[str],
        statuses: Mapping[str, InterfaceStatus],
    ) -> list[str]:
        """Determine default selected adapters: physical adapters that are up.

        Args:
            available_interfaces: List of all detected network adapter names.
            statuses: Operational statuses (is_up) keyed by adapter name.

        Returns:
            Deduplicated list of adapter names that are UP and not excluded.
        """
        selected: list[str] = []
        seen: set[str] = set()

        for name in available_interfaces:
            # Skip duplicates
            if name in seen:
                continue
            seen.add(name)

            # Check exclusion keywords
            if self.is_excluded(name):
                continue

            # Check if adapter is operational (UP)
            stat = statuses.get(name)
            if stat is not None and not stat.is_up:
                continue

            selected.append(name)

        # If all adapters were filtered out (e.g. offline machine), fallback to any non-excluded interface
        if not selected:
            for name in available_interfaces:
                if not self.is_excluded(name) and name not in selected:
                    selected.append(name)

        return selected

    def resolve_active_selection(
        self,
        available_interfaces: Sequence[str],
        user_selected: Sequence[str] | None,
        statuses: Mapping[str, InterfaceStatus],
    ) -> list[str]:
        """Resolve the final set of active interfaces to monitor.

        If user_selected is provided, filters it to only adapters currently present.
        If user_selected is None or empty, falls back to default selection.

        Args:
            available_interfaces: List of currently available adapter names.
            user_selected: User's explicitly chosen adapters from settings.
            statuses: Current interface link states.

        Returns:
            Deduplicated list of active adapter names to monitor.
        """
        available_set = set(available_interfaces)

        if user_selected is not None and len(user_selected) > 0:
            # Keep user-selected adapters that are currently available, preserving order and uniqueness
            resolved: list[str] = []
            seen: set[str] = set()
            for name in user_selected:
                if name in available_set and name not in seen:
                    seen.add(name)
                    resolved.append(name)
            if resolved:
                return resolved

        # Fallback to default physical up selection
        return self.get_default_selected(available_interfaces, statuses)
