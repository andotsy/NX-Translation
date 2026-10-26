#!/usr/bin/env python3
"""Build a partial Ukrainian ErrorMessage overlay from owner-extracted data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from msbt import commands
from prepare_translations import compile_template, render, runtime, printf_args
import yaml

ALIASES = {
    'L_NSO': 'Nintendo Switch Online', 'L_NS': 'Nintendo Switch',
    'L_NEP': 'Nintendo eShop', 'L_N10': 'Nintendo', 'L_TGS': 'GameShare',
    'L_SWT2': 'Switch 2', 'L_JC': 'Joy-Con', 'L_ROMB': '◆',
    'L_DOT3': '...', 'L_VS': '%s', 'L_WIFI': 'Wi-Fi', 'L_BT': 'Bluetooth',
    'L_MSD': 'microSD', 'L_DLC': 'DLC', 'L_DOT1': '・', 'L_SQR': '■',
}


def expand(value):
    for name, literal in ALIASES.items():
        value = value.replace('<' + name + '/>', literal)
    value = re.sub(r'<0x([0-9A-Fa-f]+)/>', lambda m: chr(int(m[1], 16)), value)
    return value.replace('<NL/>', '\n').replace('<RN/>', '\r\n')


def template(raw):
    return re.sub(r'<C(\d+)/>', lambda m: '<TAG' + str(int(m[1]) + 1) + '/>',
                  render(raw + b'\0\0'))


def build(romfs, catalog, output):
    if output.exists():
        raise ValueError('Output directory already exists')
    rows = yaml.safe_load(catalog.read_text())['translations']
    translations = {expand(row['source']): expand(row['target']) for row in rows}
    translations.update(json.loads(Path(__file__).with_name('ukrainian.json').read_text()))
    translations['OK'] = 'OK'
    entries, skipped, unchanged = [], [], 0
    ready = []
    for source in sorted(romfs.rglob('en-GB_*')):
        original = source.with_name(source.name.replace('en-GB_', 'ru_'))
        path = original.relative_to(romfs)
        en, ru = source.read_bytes(), original.read_bytes()
        key = template(en)
        if key not in translations:
            skipped.append(str(path))
            continue
        target = translations[key]
        if re.search(r'<(?!TAG\d+/>)', target):
            skipped.append(str(path))
            continue
        if re.findall(r'<TAG\d+/>', target) != re.findall(r'<TAG\d+/>', template(ru)):
            skipped.append(str(path))
            continue
        # Use Russian formatting bytes, but require English/Russian runtime
        # substitutions to agree before transplanting the Ukrainian prose.
        if runtime(en + b'\0\0') != runtime(ru + b'\0\0'):
            skipped.append(str(path))
            continue
        compiled = compile_template(re.sub(r'<TAG(\d+)/>', lambda m: '<C' + str(int(m[1]) - 1) + '/>', target), ru + b'\0\0')
        assert commands(compiled) == commands(ru + b'\0\0')
        assert printf_args(compiled) == printf_args(ru + b'\0\0')
        assert Counter(re.findall('[\ue000-\uf8ff]', render(compiled))) == Counter(re.findall('[\ue000-\uf8ff]', render(ru + b'\0\0')))
        raw = compiled[:-2]  # ErrorMessage files have no terminating NUL.
        if raw == ru:
            unchanged += 1
            continue
        ready.append((path, raw))
        entries.append({'path': str(path), 'source_sha256': hashlib.sha256(ru).hexdigest(),
                        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    if not any(str(p) == '2110/1111/ru_DlgMsg' for p, _ in ready):
        raise ValueError('Required flight-mode popup was not generated')
    destination = output / 'atmosphere/contents/0100000000000801/romfs'
    for path, raw in ready:
        p = destination / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    report = {'firmware': '23.0.1', 'data_id': '0100000000000801', 'locale': 'ru',
              'scope': 'partial; unmatched messages retain stock text', 'console_tested': False,
              'catalog_sha256': hashlib.sha256(catalog.read_bytes()).hexdigest(),
              'files': entries, 'already_identical': unchanged, 'untranslated_or_unmatched': skipped}
    (output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Created {len(entries)} translated files; {unchanged} identical; {len(skipped)} left to stock')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.romfs, args.catalog, args.output)
