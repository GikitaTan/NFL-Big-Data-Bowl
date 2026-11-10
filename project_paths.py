"""Portable project paths shared by the command-line tools and local app."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'examples' / 'results'


def data_directory(value=None):
    """Prefer explicit paths, then the environment, data/, and the original download."""
    if value is not None:
        return Path(value).expanduser().resolve()
    if os.environ.get('ATTENTION_DATA_DIR'):
        return Path(os.environ['ATTENTION_DATA_DIR']).expanduser().resolve()
    canonical = ROOT / 'data'
    legacy = ROOT / 'nfl-big-data-bowl-regional-event-data-main' / 'data'
    return canonical if (canonical / 'games.csv').is_file() or not legacy.exists() else legacy


def result_file(generated, bundled_name):
    """Use local regenerated results when present, otherwise the published snapshot."""
    generated = ROOT / generated
    return generated if generated.is_file() else RESULTS / bundled_name
