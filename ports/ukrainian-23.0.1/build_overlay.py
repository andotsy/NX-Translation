#!/usr/bin/env python3
"""Build and validate EUru-only overlays from the current firmware structure."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
from port_config import CODE, WORK, OUTPUT

ROOT = WORK
sys.path.insert(0, str(ROOT / 'python-deps'))
import oead
from compare_resources import parse
from msbt import Msbt, commands, decompress, text
from prepare_translations import compile_template, printf_args, runtime, render

CURRENT = ROOT / 'firmware-23.0.1-resources'


def main():
    rows = json.loads((ROOT / 'translation-catalog.json').read_text())
    manual = json.loads((CODE / 'manual-ukrainian.json').read_text())
    by_file = defaultdict(dict)
    for row in rows:
        key = (row['title'], row['path'])
        assert row['index'] not in by_file[key]
        by_file[key][row['index']] = row
    assert len(by_file) == 53
    missing = sorted({r['manual_key'] for r in rows
                      if r['method'] == 'manual_required' and r['manual_key'] not in manual})
    assert not missing, 'Untranslated manual messages: ' + str(missing)
    files = []
    metrics = Counter()
    payload = {}
    for (title, path), entries in sorted(by_file.items()):
        original = Msbt((CURRENT / title / path).read_bytes())
        assert set(entries) == set(range(len(original.messages)))
        messages = []
        for index, before in enumerate(original.messages):
            row = entries[index]
            assert hashlib.sha256(before).hexdigest() == row['russian_sha256']
            if row['method'] == 'manual_required':
                after = compile_template(manual[row['manual_key']], before)
                assert printf_args(after) == printf_args(before), 'Printf arguments changed'
                assert Counter(c for c in text(after) if '\ue000' <= c <= '\uf8ff') == Counter(
                    c for c in text(before) if '\ue000' <= c <= '\uf8ff'), 'UI glyph identity changed'
                assert runtime(after) == runtime(before)
            else:
                after = bytes.fromhex(row['translated_hex'])
            # ErrorMessage popups select the explicit locale variant, rather
            # than the generic label. This literal is Russian even in EUen.
            if (title == '0100000000001005' and path == 'message/EUru/error.msbt.szs'
                    and 'ErrCmn_LblErrCode_EUru' in row['labels']):
                assert render(before) == 'Код ошибки: <C0/>'
                after = compile_template('Код помилки: <C0/>', before)
                assert commands(after) == commands(before)
                metrics['locale_variant_overrides'] += 1
            assert not re.search(r'<(?:C\d+|TAG\d+|LIST\d+|NL)/>', text(after)), 'Exporter marker leaked'
            messages.append(after)
            metrics['manual_translation' if row['method'] == 'manual_required' else row['method']] += 1
        raw = original.build(messages)
        independent = parse(raw)
        assert independent['labels'] == original.labels
        assert independent['messages'] == messages
        rebuilt = Msbt(raw)
        for section in original.sections:
            if section.tag != 'TXT2':
                assert rebuilt.by_tag[section.tag] == section
        encoded = bytes(oead.yaz0.compress(raw)) if path.endswith('.szs') else raw
        assert decompress(encoded) == raw
        if path.endswith('.szs'):
            assert bytes(oead.yaz0.decompress(encoded)) == raw
        relative = 'atmosphere/contents/' + title.upper() + '/romfs/' + path
        assert '/EUru/' in relative and '..' not in Path(relative).parts
        payload[relative] = encoded
        files.append({'path': relative, 'bytes': len(encoded),
                      'sha256': hashlib.sha256(encoded).hexdigest(),
                      'base_sha256': hashlib.sha256((CURRENT / title / path).read_bytes()).hexdigest(),
                      'messages': len(messages), 'nontext_sections_identical_to_23_0_1': True})
    report = {'firmware': '23.0.1', 'locale_replaced': 'EUru', 'titles': len({r['title'] for r in rows}),
              'files': len(files), 'message_records': len(rows), 'translation_methods': dict(metrics),
              'manual_unresolved': 0, 'base_sections_preserved': True,
              'console_tested': False, 'keys_included': False,
              'unofficial_personal_test_build': True}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'manifest.json').write_text(json.dumps(files, indent=2) + '\n')
    (OUTPUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    readme = '''# Ukrainian system translation — firmware 23.0.1

Unofficial personal test build based on NX-Family/NX-Translation 22.5.0-TR2.01.
Replaces Russian (EUru). Keep the system language set to Russian. Games may follow that underlying language.
This is an SD LayeredFS overlay. No firmware/NAND update or game-save changes are involved.
Offline binary checks passed. CONSOLE TESTING IS STILL REQUIRED.

Start with the pilot ZIP: it changes only user-selection text (title 0100000000001007).
Back up any existing files at the exact manifest paths before copying. Merge atmosphere into the SD root;
do not replace/delete the entire atmosphere/contents directory. Boot Atmosphere, open user selection,
cancel it, and select your existing user. Check Ukrainian glyphs, then test HOME, Settings and a known working game.
Use the full ZIP only after the pilot works; add HOME/Settings and other title groups in stages.

Rollback: enter Hekate USB SD storage or power off and use a card reader. Remove only newly installed
translation files listed in the manifest and restore any replaced files from their backup. Reboot.
The stock Russian resources will be used again. Do not delete NAND files or unrelated title folders.

Do not test text by deleting users, resetting/erasing the console or transferring saves.
Keep existing exosphere, hosts, system_settings.ini and sysmodules unchanged.
This build does not add a Ukrainian OS locale or guarantee a Ukrainian keyboard layout.
Source project: https://github.com/NX-Family/NX-Translation
'''
    (OUTPUT / 'README.md').write_text(readme)
    for name, selected in [
        ('ukrainian-23.0.1-EUru-full.zip', payload),
        ('ukrainian-23.0.1-EUru-pilot-user-selection.zip',
         {k: v for k, v in payload.items() if '/0100000000001007/' in k}),
    ]:
        assert selected
        manifest = [r for r in files if r['path'] in selected]
        with zipfile.ZipFile(OUTPUT / name, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for path, data in selected.items():
                item = zipfile.ZipInfo(path, (2026, 10, 25, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                z.writestr(item, data)
            for path, data in [('ukrainian-23.0.1-README.md', readme),
                               ('ukrainian-23.0.1-manifest.json', json.dumps(manifest, indent=2) + '\n')]:
                item = zipfile.ZipInfo(path, (2026, 10, 25, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                z.writestr(item, data)
        with zipfile.ZipFile(OUTPUT / name) as z:
            assert z.testzip() is None
            for row in manifest:
                assert hashlib.sha256(z.read(row['path'])).hexdigest() == row['sha256']
            assert not any('.keys' in p.lower() or p.endswith('.nca') for p in z.namelist())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
