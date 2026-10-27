# Health and Safety Information

System Settings opens a bundled HTML page rather than a message table for Health
and Safety Information. Firmware 23.0.1 stores the Russian page in the Help data
archive, 0100000000000804, at `safe.htdocs/html/EUru/index.html`.

This optional overlay translates all 69 nonempty linguistic spans and the page
title into Ukrainian. It preserves the native HTML shell, scripts, stylesheets,
images, line-break markup, message IDs, empty spans and document version marker.
All numeric values and product identifiers are checked against the original.

Build using the owner's extracted Help RomFS:

```sh
python3 safety/build_overlay.py \
  --romfs /path/to/owner-extracted/Help/romfs \
  --output /path/to/new-output-directory
```

The builder requires exact hashes of the 23.0.1 Russian and English sources.
It distributes only the translation map and builder in this source tree; native
HTML, CSS, scripts, images, firmware and keys are supplied locally by the owner.
The output contains one translated HTML file, a hash manifest and catalog entries.

Copy the generated atmosphere folder onto the SD and reboot. Open System Settings
→ Safety Information and scroll through the full document to check rendering.
The current build was installed with byte-for-byte SD readback verification,
and the user confirmed that the page displays Ukrainian on firmware 23.0.1.
No helper application is needed.

To remove this optional page overlay, remove only
`atmosphere/contents/0100000000000804/romfs/safe.htdocs/html/EUru/index.html`.

[Help system data archive](https://switchbrew.org/wiki/Title_list#System_Data_Archives)
