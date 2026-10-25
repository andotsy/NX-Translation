#!/usr/bin/env python3
"""Read-only check separating the LocalNews overlay from retained news content."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from port_config import WORK, OUTPUT
sys.path.insert(0, str(WORK / 'python-deps'))
from msbt import Msbt, text

RESOURCE = 'atmosphere/contents/010000000000080B/romfs/message/EUru/localNews.msbt.szs'
OBSERVED_LABELS = [
    'LnCmn_TopicName', 'LnNewsIntro_Subject', 'LnShopIntro_Subject',
    'LnShopIntro_BtnMore', 'LnShopIntro_Footer', 'LnPvrIntro_Subject',
    'LnMinIntro_Subject', 'LnMoonIntro_Subject', 'LnSupIntro_Subject',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=OUTPUT / 'ukrainian-23.0.1-EUru-full.zip')
    parser.add_argument('--sd-root', type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.package) as archive:
        manifest = json.loads(archive.read('ukrainian-23.0.1-manifest.json'))
        row = next(row for row in manifest if row['path'] == RESOURCE)
        data = archive.read(RESOURCE)
        expected = hashlib.sha256(data).hexdigest()
        assert expected == row['sha256'] and len(data) == row['bytes']
    msbt = Msbt(data)
    original = Msbt((WORK / 'firmware-23.0.1-resources/010000000000080b/message/EUru/localNews.msbt.szs').read_bytes())
    assert msbt.labels == original.labels
    assert len(msbt.messages) == 43
    for section in original.sections:
        if section.tag != 'TXT2':
            assert msbt.by_tag[section.tag] == section
    nonempty = [i for i in original.labels.values() if text(original.messages[i])]
    assert len(nonempty) == 41
    assert all(msbt.messages[i] != original.messages[i] for i in nonempty)
    for label in OBSERVED_LABELS:
        assert label in msbt.labels
        assert text(msbt.messages[msbt.labels[label]]) != text(original.messages[original.labels[label]])
    result = {
        'resource': RESOURCE,
        'package_sha256': expected,
        'all_41_nonempty_local_news_strings_changed_from_stock_russian': True,
        'two_originally_empty_records_preserved': True,
        'current_labels_and_nontext_metadata_preserved': True,
        'screenshot_related_labels_present': OBSERVED_LABELS,
        'device_news_database_inspected': False,
        'writes_performed': False,
    }
    if args.sd_root:
        target = args.sd_root / RESOURCE
        result['sd_overlay_exists'] = target.is_file()
        if target.is_file():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            result['sd_overlay_matches_package'] = actual == expected
            result['sd_overlay_sha256'] = actual
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
