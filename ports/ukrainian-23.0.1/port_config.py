"""Explicit local input/output paths; firmware and keys never belong in Git."""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent
WORK = Path(os.environ.get('NX_TRANSLATION_WORKDIR', CODE / 'work')).resolve()
OLD_CONTENTS = Path(os.environ.get('NX_TRANSLATION_OLD_CONTENTS', WORK / 'old-ukrainian/contents')).resolve()
YAML_SOURCE = Path(os.environ.get('NX_TRANSLATION_YAML', CODE.parents[1] / 'translation/ukrainian.yaml')).resolve()
OUTPUT = Path(os.environ.get('NX_TRANSLATION_OUTPUT', WORK / 'output')).resolve()
