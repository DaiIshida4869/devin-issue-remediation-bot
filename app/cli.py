from __future__ import annotations

import argparse
import sys

from app.config import Settings
from app.config import load_settings
from app.devin_client import DevinClient
from app.event import has_trigger_label
from app.event import load_issue_event
from app.orchestrator import Orchestrator
from app.report import render_report
from app.task_store import TaskStore

TRIGGER_LABEL = 'devin-remediate'


def _require_settings(settings: Settings) -> None:
    """Fail fast with a clear message when required environment variables are missing."""
    missing: list[str] = []
    if not settings.devin_api_key:
        missing.append('DEVIN_API_KEY')
    if not settings.devin_org_id:
        missing.append('DEVIN_ORG_ID')
    if missing:
        raise SystemExit(f'Missing required environment variables: {", ".join(missing)}')


def _build_orchestrator(settings: Settings) -> Orchestrator:
    devin = DevinClient(
        api_key=settings.devin_api_key,
        org_id=settings.devin_org_id,
        base_url=settings.devin_base_url,
    )
    store = TaskStore(settings.tasks_path)
    return Orchestrator(devin=devin, store=store, report_path=settings.report_path)


def _cmd_remediate(args: argparse.Namespace, settings: Settings) -> int:
    _require_settings(settings)
    issue = load_issue_event(args.event)
    if args.require_label and not has_trigger_label(issue, TRIGGER_LABEL):
        print(f'Issue #{issue.number} is missing the "{TRIGGER_LABEL}" label; skipping.')
        return 0
    orchestrator = _build_orchestrator(settings)
    task = orchestrator.remediate_issue(issue)
    print(f'Created Devin session {task.devin_session_id} for issue #{issue.number}')
    print(f'Session URL: {task.devin_session_url}')
    return 0


def _cmd_poll(_args: argparse.Namespace, settings: Settings) -> int:
    _require_settings(settings)
    orchestrator = _build_orchestrator(settings)
    tasks = orchestrator.poll()
    for task in tasks:
        print(f'#{task.issue_number}: {task.status.value} (PR: {task.pr_url or "-"})')
    return 0


def _cmd_report(_args: argparse.Namespace, settings: Settings) -> int:
    store = TaskStore(settings.tasks_path)
    print(render_report(store.load()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Devin issue remediation bot')
    subparsers = parser.add_subparsers(dest='command', required=True)

    remediate = subparsers.add_parser('remediate', help='Delegate an issue to Devin')
    remediate.add_argument('--event', required=True, help='Path to a GitHub issue event JSON payload')
    remediate.add_argument(
        '--require-label',
        action='store_true',
        help=f'Only remediate when the issue carries the "{TRIGGER_LABEL}" label',
    )
    remediate.set_defaults(func=_cmd_remediate)

    poll = subparsers.add_parser('poll', help='Refresh active tasks from Devin')
    poll.set_defaults(func=_cmd_poll)

    report = subparsers.add_parser('report', help='Print the current Markdown report')
    report.set_defaults(func=_cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_settings()
    return args.func(args, settings)
