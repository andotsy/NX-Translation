#!/usr/bin/env python3
"""Extract only localization inputs locally; never print keys or raw tool logs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from port_config import WORK, OLD_CONTENTS

ROOT = WORK
TOOL = ROOT / 'tools/hactool/hactool'
NCAS = ROOT / 'firmware-nca'
OLD = OLD_CONTENTS
OUT = ROOT / 'firmware-23.0.1-resources'


def run(keys, nca, *options):
    result = subprocess.run([str(TOOL), '--disablekeywarns', '--suppresskeys',
                             '-k', str(keys), *options, str(nca)],
                            capture_output=True, text=True, timeout=120)
    # Output stays in memory. Persist only explicitly selected public metadata.
    return result


def metadata(keys, nca):
    result = run(keys, nca, '-i')
    row = {'nca': nca.name, 'exit_code': result.returncode}
    for name, field, pattern in [
        ('title_id', 'Title ID', r'[0-9a-fA-F]{16}'),
        ('content_type', 'Content Type', r'[A-Za-z]+'),
        ('magic', 'Magic', r'NCA[0-9]'),
        ('key_revision', 'Master Key Revision', r'0x[0-9A-Fa-f]+'),
    ]:
        match = re.search(r'^' + field + r':\s+(' + pattern + r')', result.stdout, re.M)
        if match:
            row[name] = match.group(1).lower() if name == 'title_id' else match.group(1)
    return row


def main():
    global ROOT, NCAS, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--keys', required=True, type=Path)
    parser.add_argument('--version', choices=['22.5.0', '23.0.1'], default='23.0.1')
    args = parser.parse_args()
    if args.version == '22.5.0':
        NCAS = ROOT / 'firmware-22.5.0-nca'
        OUT = ROOT / 'firmware-22.5.0-resources'
        ROOT = ROOT / 'baseline-22.5.0-metadata'
        ROOT.mkdir(exist_ok=True)
    assert args.keys.is_file() and TOOL.is_file()
    files = sorted(NCAS.glob('*.nca'))
    assert len(files) >= 200
    titles = sorted(p.name.lower() for p in OLD.iterdir() if p.is_dir())
    assert len(titles) == 19
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda p: metadata(args.keys, p), files))
    (ROOT / 'nca-public-inventory.json').write_text(json.dumps(rows, indent=2) + '\n')
    assert all(r['exit_code'] == 0 and 'title_id' in r for r in rows), 'NCA inspection failed'
    print('Inspected ' + str(len(files)) + ' NCA headers without exposing key data.', flush=True)
    output = []
    title_map = []
    for title in titles:
        matches = [r for r in rows if r['title_id'] == title and r['content_type'] in {'Program', 'Data', 'PublicData'}]
        assert matches, 'Required system title absent: ' + title
        for row in matches:
            temp = ROOT / 'romfs-temporary' / title / row['nca']
            assert not temp.exists(), 'Existing temporary extraction; inspect before retry'
            temp.mkdir(parents=True)
            result = run(args.keys, NCAS / row['nca'], '-i', '-x', '-y', '--romfsdir=' + str(temp))
            failure_lines = [line for line in (result.stdout + '\n' + result.stderr).splitlines()
                             if '(FAIL)' in line or re.search(r'\b(invalid|failed|unable)\b', line, re.I)]
            assert result.returncode == 0 and not failure_lines, 'Extraction or integrity check failed for ' + title
            paths = sorted(p for p in temp.rglob('*') if p.is_file())
            assert paths, 'No decrypted RomFS files for ' + title
            listing = [str(p.relative_to(temp)) for p in paths]
            dest = OUT / title
            copied = 0
            for p, relative in zip(paths, listing):
                if not any(part in {'EUru', 'EUen'} for part in Path(relative).parts):
                    continue
                target = dest / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                data = p.read_bytes()
                if target.exists():
                    assert target.read_bytes() == data, 'Conflicting resource in same title'
                else:
                    target.write_bytes(data)
                output.append({'title_id': title, 'path': relative, 'bytes': len(data),
                               'sha256': hashlib.sha256(data).hexdigest(), 'nca': row['nca']})
                copied += 1
            assert copied, 'Expected language directories absent: ' + title
            title_map.append({**row, 'all_romfs_paths': listing,
                              'collected_language_files': copied, 'integrity_check_passed': True})
            shutil.rmtree(temp)  # Only this script's freshly created extraction.
            print(title + ': verified, collected ' + str(copied) + ' language resources', flush=True)
    (ROOT / 'system-title-resource-map.json').write_text(json.dumps(title_map, indent=2) + '\n')
    (ROOT / ('firmware-' + args.version + '-resource-manifest.json')).write_text(json.dumps(output, indent=2) + '\n')
    print('Collection complete: ' + str(len(output)) + ' files, ' + str(sum(r['bytes'] for r in output)) + ' bytes.', flush=True)


if __name__ == '__main__':
    main()
