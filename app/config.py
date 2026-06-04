from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATA_DIR = Path('data')


@dataclass(frozen=True)
class Settings:
    devin_api_key: str
    devin_org_id: str
    devin_base_url: str
    data_dir: Path

    @property
    def tasks_path(self) -> Path:
        """Path to the JSON file that stores delegated tasks."""
        return self.data_dir / 'tasks.json'

    @property
    def report_path(self) -> Path:
        """Path to the generated Markdown report."""
        return self.data_dir / 'report.md'


def load_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    data_dir = Path(os.environ.get('DATA_DIR', str(DEFAULT_DATA_DIR)))
    return Settings(
        devin_api_key=os.environ.get('DEVIN_API_KEY', ''),
        devin_org_id=os.environ.get('DEVIN_ORG_ID', ''),
        devin_base_url=os.environ.get('DEVIN_BASE_URL', 'https://api.devin.ai'),
        data_dir=data_dir,
    )
