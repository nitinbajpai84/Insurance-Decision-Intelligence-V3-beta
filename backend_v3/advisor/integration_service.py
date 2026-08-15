"""
Integration Service boundary.

Stage 1 exposes the connection framework only. No provider is marked connected
unless a real implementation later writes that state.
"""
from __future__ import annotations

from typing import Any


CONNECTION_CATEGORIES: list[dict[str, Any]] = [
    {"category": "Customer Data", "providers": ["CRM", "CSV/Excel"]},
    {"category": "Calendar", "providers": ["Google Calendar", "Microsoft Outlook"]},
    {"category": "Communication", "providers": ["Microsoft 365/Outlook", "Gmail", "WhatsApp Business"]},
    {"category": "Meetings", "providers": ["Microsoft Teams", "Zoom", "Google Meet"]},
    {"category": "Files", "providers": ["OneDrive", "SharePoint", "Google Drive"]},
]


def list_connections() -> list[dict[str, Any]]:
    return [
        {
            "category": group["category"],
            "providers": [
                {
                    "provider": provider,
                    "status": "not_connected",
                    "sync_status": "not_configured",
                    "last_sync": None,
                }
                for provider in group["providers"]
            ],
        }
        for group in CONNECTION_CATEGORIES
    ]
