from __future__ import annotations

from dataclasses import asdict

from apartment_bot.config import Settings
from apartment_bot.core.models import DashboardRow


class GoogleSheetsWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upsert_rows(self, rows: list[DashboardRow]) -> list[dict[str, str]]:
        # TODO: Use GOOGLE_SERVICE_ACCOUNT_JSON to authenticate to Google Sheets.
        # TODO: Use GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SHEET_TAB to target the dashboard sheet.
        # TODO: Decide whether to identify rows by listing_id and update in place or rewrite the tab in n8n.
        return [asdict(row) for row in rows]
