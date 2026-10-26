"""Official FPL API client (HTTP only — no domain logic)."""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://fantasy.premierleague.com/api"


class FplApiError(Exception):
    """Raised when an FPL API request fails or returns an unexpected payload."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FplApi:
    """Thin HTTP wrapper around public Fantasy Premier League endpoints."""

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://fantasy.premierleague.com/",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FplApi:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise FplApiError(f"Network error fetching {url}: {exc}") from exc

        if response.status_code == 404:
            raise FplApiError(
                f"Team or resource not found. Check the Team ID.",
                status_code=404,
            )
        if response.status_code >= 400:
            raise FplApiError(
                f"FPL API HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise FplApiError(f"Invalid JSON from FPL API") from exc

    def bootstrap_static(self) -> dict[str, Any]:
        data = self._get("bootstrap-static/")
        if not isinstance(data, dict) or "elements" not in data:
            raise FplApiError("Unexpected bootstrap-static payload")
        return data

    def fixtures(self) -> list[dict[str, Any]]:
        data = self._get("fixtures/")
        if not isinstance(data, list):
            raise FplApiError("Unexpected fixtures payload")
        return data

    def entry(self, team_id: int) -> dict[str, Any]:
        data = self._get(f"entry/{team_id}/")
        if not isinstance(data, dict) or "id" not in data:
            raise FplApiError(f"Unexpected entry payload for team {team_id}")
        return data

    def entry_history(self, team_id: int) -> dict[str, Any]:
        data = self._get(f"entry/{team_id}/history/")
        if not isinstance(data, dict):
            raise FplApiError(f"Unexpected history payload for team {team_id}")
        return data

    def entry_transfers(self, team_id: int) -> list[dict[str, Any]]:
        data = self._get(f"entry/{team_id}/transfers/")
        if not isinstance(data, list):
            raise FplApiError(f"Unexpected transfers payload for team {team_id}")
        return data

    def entry_picks(self, team_id: int, event_id: int) -> dict[str, Any]:
        data = self._get(f"entry/{team_id}/event/{event_id}/picks/")
        if not isinstance(data, dict) or "picks" not in data:
            raise FplApiError(
                f"Unexpected picks payload for team {team_id} GW{event_id}"
            )
        return data
