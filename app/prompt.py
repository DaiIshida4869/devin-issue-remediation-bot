from __future__ import annotations

from app.models import Issue

_PROMPT_TEMPLATE = """\
You are assigned to remediate a GitHub issue in a fork of Apache Superset.

Repository: {repo_url}
Issue: {issue_url}

Issue title:
{issue_title}

Issue description:
{issue_body}

Please:
1. Inspect the issue and the relevant files in the repository.
2. Make the smallest safe change that resolves the issue.
3. Run relevant checks or tests if practical.
4. Open a pull request with a clear summary of what changed and how it was validated.

Focus on a low-risk remediation suitable for an automated issue-to-PR workflow.
Keep the change tightly scoped to the issue; do not refactor unrelated code.
"""


def build_remediation_prompt(issue: Issue) -> str:
    repo_url = f'https://github.com/{issue.repo}'
    body = issue.body.strip() or '(no description provided)'
    return _PROMPT_TEMPLATE.format(
        repo_url=repo_url,
        issue_url=issue.url,
        issue_title=issue.title,
        issue_body=body,
    )


def build_session_title(issue: Issue) -> str:
    return f'Remediate #{issue.number}: {issue.title}'
