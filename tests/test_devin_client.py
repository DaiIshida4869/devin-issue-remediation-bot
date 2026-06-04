"""Tests for the Devin v3 API client with mocked HTTP."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from app.devin_client import DevinClient

ORG_ID = 'org-test'


def _client() -> DevinClient:
    """Build a client pointed at a deterministic org and base URL."""
    return DevinClient(api_key='cog_test', org_id=ORG_ID, base_url='https://api.devin.ai')


def _mock_response(mocker: MockerFixture, payload: dict) -> object:
    """Build a fake requests response returning the given payload."""
    response = mocker.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_create_session_should_post_to_v3_org_url_and_parse_response(mocker: MockerFixture) -> None:
    client = _client()
    post = mocker.patch.object(
        client._session,
        'post',
        return_value=_mock_response(
            mocker,
            {'session_id': 'devin-123', 'url': 'https://app.devin.ai/sessions/123', 'status': 'new'},
        ),
    )

    session = client.create_session(prompt='do the thing', title='My title')

    assert session.session_id == 'devin-123'
    assert session.url == 'https://app.devin.ai/sessions/123'
    args, kwargs = post.call_args
    assert args[0] == 'https://api.devin.ai/v3/organizations/org-test/sessions'
    assert kwargs['json']['prompt'] == 'do the thing'
    assert kwargs['json']['title'] == 'My title'


def test_get_session_should_extract_status_detail_and_pr(mocker: MockerFixture) -> None:
    client = _client()
    get = mocker.patch.object(
        client._session,
        'get',
        return_value=_mock_response(
            mocker,
            {
                'status': 'exit',
                'status_detail': 'finished',
                'pull_requests': [{'pr_url': 'https://github.com/x/y/pull/9', 'pr_state': 'open'}],
            },
        ),
    )

    status = client.get_session('devin-123')

    assert status.status == 'exit'
    assert status.status_detail == 'finished'
    assert status.pr_url == 'https://github.com/x/y/pull/9'
    args, _ = get.call_args
    assert args[0] == 'https://api.devin.ai/v3/organizations/org-test/sessions/devin-123'


def test_get_session_should_handle_empty_pull_requests(mocker: MockerFixture) -> None:
    client = _client()
    mocker.patch.object(
        client._session,
        'get',
        return_value=_mock_response(mocker, {'status': 'running', 'status_detail': 'working', 'pull_requests': []}),
    )

    status = client.get_session('devin-123')

    assert status.pr_url == ''


def test_list_sessions_should_follow_pagination(mocker: MockerFixture) -> None:
    client = _client()
    page1 = _mock_response(
        mocker,
        {
            'items': [
                {'session_id': 's1', 'url': 'u1', 'title': 'Remediate #1: a', 'status': 'running', 'pull_requests': []},
            ],
            'has_next_page': True,
            'end_cursor': 'cur1',
        },
    )
    page2 = _mock_response(
        mocker,
        {
            'items': [
                {
                    'session_id': 's2',
                    'url': 'u2',
                    'title': 'Remediate #2: b',
                    'status': 'exit',
                    'status_detail': 'finished',
                    'pull_requests': [{'pr_url': 'https://github.com/x/y/pull/2', 'pr_state': 'open'}],
                },
            ],
            'has_next_page': False,
            'end_cursor': None,
        },
    )
    get = mocker.patch.object(client._session, 'get', side_effect=[page1, page2])

    sessions = client.list_sessions(page_size=1)

    assert [s.session_id for s in sessions] == ['s1', 's2']
    assert sessions[1].pr_url == 'https://github.com/x/y/pull/2'
    assert get.call_count == 2
    _, kwargs = get.call_args
    assert kwargs['params']['after'] == 'cur1'


def test_list_sessions_should_raise_when_more_pages_but_no_cursor(mocker: MockerFixture) -> None:
    client = _client()
    bad_page = _mock_response(mocker, {'items': [], 'has_next_page': True, 'end_cursor': None})
    mocker.patch.object(client._session, 'get', return_value=bad_page)

    with pytest.raises(RuntimeError):
        client.list_sessions()


def test_send_message_should_post_to_v3_messages_endpoint(mocker: MockerFixture) -> None:
    client = _client()
    post = mocker.patch.object(client._session, 'post', return_value=_mock_response(mocker, {}))

    client.send_message('devin-123', 'hello')

    args, kwargs = post.call_args
    assert args[0] == 'https://api.devin.ai/v3/organizations/org-test/sessions/devin-123/messages'
    assert kwargs['json'] == {'message': 'hello'}
