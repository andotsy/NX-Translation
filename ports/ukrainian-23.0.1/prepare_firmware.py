#!/usr/bin/env python3
"""Prepare owner-supplied firmware archives locally, validating content IDs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
from port_config import WORK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', choices=['22.5.0', '23.0.1'], required=True)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--sha256', help='Expected archive SHA-256 from a trusted local manifest')
    args = parser.parse_args()
    archive_hash = hashlib.sha256()
    with args.zip.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            archive_hash.update(chunk)
    if args.sha256:
        assert archive_hash.hexdigest() == args.sha256.lower(), 'Archive SHA-256 mismatch'
    output = WORK / ('firmware-nca' if args.version == '23.0.1' else 'firmware-22.5.0-nca')
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    seen = set()
    with zipfile.ZipFile(args.zip) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = Path(entry.filename).name
            assert re.fullmatch(r'[0-9a-fA-F]{32}(?:\.cnmt)?\.nca', name), 'Unexpected archive entry'
            assert '..' not in Path(entry.filename).parts and name not in seen
            seen.add(name)
            data = archive.read(entry)
            digest = hashlib.sha256(data).hexdigest()
            assert digest.startswith(name.split('.')[0].lower()), 'NCA content ID mismatch'
            target = output / name
            if target.exists():
                assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, 'Existing NCA differs'
            else:
                target.write_bytes(data)
            manifest.append({'name': name, 'bytes': len(data), 'sha256': digest})
    assert len(manifest) >= 200, 'Incomplete system-firmware archive'
    (WORK / ('firmware-' + args.version + '-archive-manifest.json')).write_text(
        json.dumps({'archive_sha256': archive_hash.hexdigest(), 'files': manifest}, indent=2) + '\n')
    print('Prepared', len(manifest), 'validated firmware files locally.')


if __name__ == '__main__':
    main()
