from __future__ import annotations

from dataclasses import dataclass

import requests

# The v3 path layout and response schema are implemented in this module, so the
# version lives here next to the code that depends on it rather than in config.
API_VERSION = 'v3'


@dataclass
class DevinSession:
    session_id: str
    url: str


@dataclass
class DevinSessionStatus:
    """Snapshot of an existing Devin session.

    The v3 API splits the lifecycle into a coarse ``status`` (for example
    ``running`` or ``exit``) and a finer ``status_detail`` (for example
    ``finished``). Both are kept so callers can decide how to interpret them.
    """

    status: str | None
    status_detail: str | None
    pr_url: str
    raw: dict


class DevinClient:
    """Minimal wrapper for the Devin v3 session endpoints used by the bot."""

    def __init__(
        self,
        api_key: str,
        org_id: str,
        base_url: str = 'https://api.devin.ai',
        timeout: int = 30,
    ) -> None:
        self._timeout = timeout
        # v3 endpoints are scoped under the organization id.
        self._sessions_url = f'{base_url.rstrip("/")}/{API_VERSION}/organizations/{org_id}/sessions'
        self._session = requests.Session()
        self._session.headers.update(
            {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
        )

    def create_session(self, prompt: str, title: str | None = None) -> DevinSession:
        payload: dict = {'prompt': prompt}
        if title is not None:
            payload['title'] = title
        response = self._session.post(self._sessions_url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return DevinSession(
            session_id=data['session_id'],
            url=data.get('url', ''),
        )

    def get_session(self, session_id: str) -> DevinSessionStatus:
        """Fetch the current status and any pull request for a session."""
        response = self._session.get(f'{self._sessions_url}/{session_id}', timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return DevinSessionStatus(
            status=data.get('status'),
            status_detail=data.get('status_detail'),
            pr_url=_first_pull_request_url(data),
            raw=data,
        )

    def send_message(self, session_id: str, message: str) -> None:
        response = self._session.post(
            f'{self._sessions_url}/{session_id}/messages',
            json={'message': message},
            timeout=self._timeout,
        )
        response.raise_for_status()


def _first_pull_request_url(data: dict) -> str:
    # v3 returns pull_requests as a list of {pr_url, pr_state}; it is empty until a PR is opened.
    pull_requests = data.get('pull_requests') or []
    for pull_request in pull_requests:
        url = pull_request.get('pr_url')
        if url:
            return url
    return ''
