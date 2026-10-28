# Changelog

All notable changes to this project are documented in this file.

Format adapted from [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/lang/fr/).

## [1.0.1] - 2026-10-29

### Fixed

- **No more empty console window at launch**: the desktop app is a GUI
  binary, so every console child it starts (the engine, the service
  helpers) was getting its own - empty - console window. They now start
  with `CREATE_NO_WINDOW`.
- **The engine no longer outlives the app**: only the tray "Quit" used to
  stop the server, so any other exit (window closed while the tray was
  unavailable, a boot failure, a plain exit) left the Python process
  running. The child is now killed on every exit path. Closing the window
  still hides the app to the tray, as before.

### Changed

- **The installers ship offline wheels for Python 3.15** (Windows setup
  and Linux archive): a machine whose only Python is 3.15 now installs,
  where the offline pip step used to fail. The CI runs the engine suites
  on 3.10, 3.12 and 3.15.

## [1.0.0] - 2026-10-25

### Added

- **The desktop app is now built with Tauri 2** (Rust + React): system
  tray, one window per machine, close-to-hide, integrated title bar, and
  a round taskbar/tray icon.
- **The WhatsNew popup is back** (FR/EN, shown once per version).
- **Updates are verified**: the downloaded installer or tarball must
  match the SHA-256 digest published with the release, and only tags
  matching `vX.Y.Z` are offered (Windows setup, Linux tarball).

### Changed

- **The desktop app was rewritten from Avalonia/.NET to Tauri**: same
  engine, same configuration, same URLs; the Windows installer and the
  Linux archive now ship the Tauri binary.
- **The installed app finds its own Python**: venv first, then PATH,
  with `PYTHONPATH` pointing at the bundled `src/` (the engine starts on
  a clean machine).

### Removed

- **The Avalonia app and its 57 unit tests** (`desktop/OpenDrop`,
  `desktop/OpenDrop.Tests`).

### Fixed

- **The sun/moon theme glyphs** displayed as mojibake (`â˜€`/`â˜¾`);
  they are now the real characters (`U+2600`/`U+263E`).

## [0.16.1] - 2026-10-20

### Added

- **The web Settings panel joined the README screenshots** (dark +
  light): the local capture tool now pairs through the real `#pair=`
  overlay first, so the panel renders the paired-device block (token,
  IP, dissociate) instead of the paste field, and opens the gear after
  the Download shot. All eleven README images were regenerated from
  the current UI - the previous set still showed the old logo and the
  old drop zone.

### Removed

- **Releases no longer attach PNG screenshots**: the release
  workflow's `screenshots` job and the `tests/screenshots.py` script
  behind it are gone, and the four language x theme PNGs were dropped
  from the v0.16.0 release. Screenshots live in the README only -
  never in the changelog or the release notes.

### Fixed

- **Linux: the applications-menu entry launched nothing.** `install.sh`
  never copied the published binary's native libraries (`libSkiaSharp.so`,
  `libHarfbBuzzSharp.so`) into `/opt/opendrop`: the single-file publish
  keeps them next to the executable and .NET loads them from the app
  directory, so the installed app died at startup with a
  `DllNotFoundException` and no window - launching straight from the
  extracted folder worked, the menu entry did not. The installer now
  copies whatever `*.so` the bundle carries, which also heals the
  auto-update path (it relaunches `install.sh` over the existing
  install). Found by hand on Kali 2026-10-20.

## [0.16.0] - 2026-10-20

### Added

- **Downloads resume (HTTP Range)**: `/api/download` now understands a
  single `Range` header, so an interrupted download in the browser picks
  up where it stopped (`bytes=N-`) instead of starting over. A valid
  range is answered 206 with the exact slice and a proper
  `Content-Range`; a range past the end of the file gets a 416; anything
  malformed or multi-range still gets the whole file (plain 200), and
  every download advertises `Accept-Ranges: bytes`.
- **The tab shows the transfer, and leaving mid-flight asks first**: while
  a zip or a send is really on the way, the page title carries the
  percentage (`42% · OpenDrop` - language-neutral on purpose) and a single
  `beforeunload` guard makes the browser ask for confirmation instead of
  dropping the transfer. The plain `OpenDrop` title comes back on every
  exit - success, cancel, zip cancel, errors - so a finished transfer
  never leaves a "leave site?" prompt behind. No Notification API: the
  permission prompt is not worth the UI.
- **Installable as an app (PWA)**: a web manifest, proper icons
  (192 + 512 + maskable 512 + favicon) and a small service worker make
  OpenDrop installable on phones and desktops. The worker is
  network-first for the shell: the live server always answers and the
  cache is only the offline fallback, so a release can never leave
  users pinned on an old UI, and every old cache is dropped when a new
  worker activates. `/api` - uploads, downloads, Range responses - is
  never intercepted.
- **The desktop says what's new, in the window and in French**: after
  an update, the app offers the release notes once per version as a
  fixed popup INSIDE the main window (dimmed backdrop, closes on the ✕,
  Escape or a click outside, body always scrolls inside its frame) -
  headings and bullets keep their shape, and the notes' links are real
  links: a click opens them in the browser, the tooltip shows the URL
  and a right click copies it. Since GitHub only ever carries the
  English body, a French UI renders a bundled, hand-written translation
  of the notes (`whatsnew.fr.md`, rewritten at every version bump next
  to the changelog section it translates, its first line naming the
  version it belongs to); a missing bundle, a malformed header or a
  version drift all fall back to the English body - the dialog never
  dies over a translation, and it can never show another release's
  French notes. The title follows the language too (FR "Quoi de neuf",
  EN "What's new"). The first launch only records the version baseline
  in silence; the new version is remembered in `config.json` before
  anything is fetched, so with GitHub unreachable nothing pops up and
  the prompt can never loop or slow startup down. The desktop CI now
  runs the unit tests (`dotnet test`) before publishing.
- **The release pipeline tells the whole story**: every release now
  carries the matching `## [<version>]` section of this changelog as
  its GitHub release notes (set once when the release is created -
  existing release bodies are never rewritten, and a tag without a
  section keeps the auto-generated notes as the fallback), gets
  FR/EN x dark/light screenshots of the app attached by a dedicated CI
  job, and the repository is scanned by CodeQL (Python + JavaScript on
  every push to main, every pull request, and a weekly run).

### Security

- Eleven suites, 445 checks in total - the ten Python suites carry
  429 and the new `tests/test_e2e.py` carries 16: chromium, firefox
  and webkit drive the real UI against a real server (single-slice
  upload, two-slice upload and cancel, Range resume, the
  `beforeunload`/tab-title guard, the PWA service-worker reload), with
  webkit excluded only from the two-slice scenarios by a printed,
  documented driver limitation. `test_beta --large` adds 75 checks
  (75/75) and the desktop unit tests 57 (`dotnet test` in CI).

## [0.15.0] - 2026-10-16

### Added

- **Live zip progress with a Cancel button** on the transfer card: the
  silent "Preparing..." line became a real bar - `Compression... 42 %
  (6.0/14.0 GB)` - updated per chunk while the browser zips, and Cancel
  aborts the build at any point in the batch.
- **ZIP64 throughout the browser zip**: entry sizes, archive size and
  entry count all carry the extended headers, so the old 4 GB ceiling
  and its bare `tooLarge` error are gone - a 14 GB folder zips and
  uploads.
- **A password for folder zips**: a checkbox in the batch's options
  panel (unchecked by default) reveals a password field before any zip
  work starts; the archives are encrypted with classic ZipCrypto -
  hand-rolled in `web/zip.js`, no dependency - so Windows Explorer,
  7-Zip and the phone zip apps open them, with an honest hint that it
  keeps the curious out, not attackers.
- **Standard or Rapide, your choice**: the same panel offers *Standard*
  (streamed deflate) or *Rapide* (store - near-instant, same weight) for
  every folder of the batch, defaulting to Standard. Nothing is zipped
  or sent until *Commencer* is pressed; batches of plain files skip the
  panel and go straight up as before.
- **One clear refusal when the batch cannot fit**: right after the drop
  is walked (metadata only, before a single byte is read or zipped) the
  batch total is compared to the remaining quota; too big and a single
  error card names the batch's weight, the space left and the shortfall,
  and the whole batch is refused - nothing zipped, nothing sent. A
  failed quota fetch fails open; the server still enforces the exact
  quota at reservation anyway.
- **One honest button on the drop zone** - *Choisir des fichiers*,
  centered; the whole zone still accepts file AND folder drops (folders
  travel by drag-and-drop); the old "Choose a file" headline with its
  small hidden folder link - and then the interim two-button row - are
  both gone (the user's call, after testing).

### Changed

- **The zip engine streams**: files are read in 1-4 MB chunks
  (`file.stream()`), the CRC is computed as bytes pass, and deflated
  output lands in disk-backed Blob parts - one huge file no longer means
  one huge ArrayBuffer in memory. The Download tab's multi-select zip
  rides the same engine and gains ZIP64 for free (only the Send card
  gets a bar).
- **The server's 10 GB per-request cap is gone** (`MAX_UPLOAD_SIZE`
  deleted): the receive quota is the only ceiling, checked where it
  always was - at reservation, with the 507 that never changed. The
  client-side pre-check above is UX only, never a policy.

### Fixed

- **Multi-gigabyte sends now work in every browser, including Zen and
  Firefox**: a giant composed Blob in a single request is what Gecko
  refuses to drain - the bar reaches 100% and the server never sees the
  end of the body (a 5 GB plain file uploads fine, the same bytes as a
  browser-built zip do not). Every upload now travels as a sequence of
  128 MiB slices appended in order into a staging file
  (`<name>.<uploadId>.part`), which the server verifies, hashes and
  renames to its final name when the last slice lands. A slice that
  stalls, drops or loses its response retries itself (3 attempts) off
  the byte count the server actually committed, so the retry is
  idempotent; progress reports bytes acknowledged rather than bytes
  queued, cancel is immediate, and a same-name complete file is never
  clobbered (the final name uniquifies exactly as before). Legacy
  requests without the staging params keep the old code path unchanged.
  Found by the author's manual 4.75 GB folder test in Zen.
- **A stalled big upload no longer dies as "Cannot read the uploaded
  file"**: the connection carried a 30 s idle timeout on every read, so
  any real network gap in a multi-minute multi-gigabyte upload (Wi-Fi
  hiccup, the browser pacing a huge Blob) aborted it near the end - a
  4.7 GB folder zipped fine and then failed on the way up. While an
  upload body is being read a dedicated 120 s idle window now applies
  (the usual timeout is restored afterwards, keep-alive unchanged), and
  a genuine stall answers with an honest "Transfer interrupted (the
  connection stalled)" instead of the misleading read error. Found by
  the author's manual test, reproduced with a controlled mid-body stall.
- **The web Settings *Appareil* section now shows my own IP**: the
  answer to `/api/device/status` has always carried `my_ip`, the page
  simply ignored it - the line renders under the device token, FR and EN
  alike (caught by the 0.14.0 review, riding into this release).

### Security

- Ten suites, 416 checks in total - the new `tests/test_zip_web.py`
  alone carries 47: every archive the browser builds (both modes,
  password or not) is byte-compared after extraction by Python's
  independent `zipfile`, and wrong passwords are rejected; the security
  suite now proves the per-request cap is gone instead of enforcing it,
  and the server suite pins the chunked-upload staging rules (append,
  truncate-to-offset, 409 resync, uniquify-at-rename, cancel) that make
  multi-gigabyte sends survive a retry.

## [0.14.0] - 2026-10-15

### Added

- **Device pairing: pair once, open forever**. A phone that pairs once -
  by pasting the device token, by scanning the desktop's QR/link, or by
  accepting the pairing overlay the desktop used to push - has its IP
  registered in `devices.json`; from then on it opens the web app
  unlocked forever, with no code, no QR, and no live session needed. A
  device ID travels with every request, so a browser that lost its
  cookies heals the pairing by itself. The token itself changes only
  through an explicit *Reset* (see Changed).
- **An *Appareils* tab in the desktop Settings**: the device token with
  a copy button, a *Pour parrainer :* section holding the QR code and
  the pairing link of the moment (copy, or open it in the browser), one
  *Réinitialiser* button that regenerates QR + link + token together -
  with a confirmation whenever a device is registered - and the list of
  paired devices (IP, user agent, shared-info, pairing date) refreshing
  by itself while the tab is open, each row dissociable.
- **A Settings page in the web app** (gear button, unlocked devices
  only): *Appareil* - paired status, my own IP, the *Show what I send*
  choice, self-dissociation, or the token field when not yet paired;
  *Apparence* - light/dark; *Langue* - FR/EN. Both are pushed to the
  server and persisted in config.json - the theme also keeps a
  per-device override, the language is shared by every visitor.
- **Pairing links** (`#pair=<token>`): the QR and the link shown in the
  desktop tab open the web app locked with the pairing token already in
  the overlay's field - nothing is sent until the user validates, and
  the copied link carries no master key.

### Changed

- **Dissociating a device no longer rotates the token**: it removes the
  record and kills that IP's sessions only. Rotation is now the
  exclusive job of *Reset*, which regenerates the device token and
  clears every registered device at once (with their sessions) -
  breaking the pairing of all of them, which is exactly what a reset is
  for.

### Security

- **SECURITY.md tells the whole truth**: truth-table rows for every
  pairing route (`/api/devices`, `/api/device/status`, `pair`,
  `pairing`, `prefs`, `dissociate`, `reset`) with their auth rules and
  quotas, and the `devices.json` data model - what the registry stores
  and what may (and may not) rewrite it.
- Nine suites, 356 checks in total - the new `tests/test_devices.py`
  alone carries 62 (registry, trust chain, quotas, dissociate vs reset).

## [0.13.0] - 2026-10-14

### Added

- **Folders in the web *Send* tab**: drop a folder (or pick *Choose a
  folder*) and it travels as a single `name.zip`, zipped right in the
  browser by a new dependency-free writer (`web/zip.js`: CRC-32, deflate
  through `CompressionStream` with a store fallback, UTF-8 names). The
  PC's share folder only ever receives a plain `.zip`, never a folder
  tree.
- **Several files per send**: a drop, a multi-select or a folder pick
  queues every file; they upload one after the other behind an `n / total`
  badge, and the batch ends on a single result ("N files sent", total
  size). Cancelling also drops the zips still being prepared.
- **A real workspace in the web *Download* tab**:
  - live search over the share folder;
  - three display densities - one, two or four files per row - remembered
    per device;
  - **virtual folders**: create, rename and delete folders that live only
    in the browser (`localStorage`); files are moved in by drag & drop,
    or with *Move to…* on touch where dragging does not exist, and the
    share folder on the PC is never touched - deleting a folder puts its
    files back Home;
  - selection with per-file checkboxes and a select-all box, then
    **Download (n)**: several files arrive as one
    `OpenDrop-n-files.zip` built in the browser (a single file still
    downloads directly).
- **"Drop files here" hint** under *SHARED FILES* in the desktop window,
  so the drop panel reads as a drop target before anything is dragged
  over it.

### Changed

- **Liquid Glass, end to end**: the web page, the main window and the
  Settings window are rebuilt on translucent layers - tinted blur,
  hairline rims, accent gradients, soft inner light, refraction
  highlights on the cards - over an aurora that stays in the background.
  Dark remains the default and the light theme got the same treatment.
  System fonts, monospace codes, and the logo are untouched.
- **The interface does more work for less cost**: the background orbs
  carry their softness inside the gradient instead of a live blur, are
  frozen outright on touch devices, small controls no longer run their
  own `backdrop-filter`, and the SVG refraction layer is only built for
  fine pointers.
- **The web page no longer jumps on a tab switch**: the column is
  top-aligned and the container padding follows the viewport, so *Send*
  and *Download* always sit at the same height.
- The desktop theme glyph is drawn in Segoe UI Symbol: the sun's rays
  were clipped by the colour-emoji font.

### Removed

- **The specular sheen** (`Services/Shine.cs` and its CSS twin): the
  light that followed the pointer over buttons and tabs is gone
  everywhere, on request. The spring tab indicators, entry animations,
  aurora and scrollbar pill all stay.

### Fixed

- **Deleting a virtual folder could do nothing at all**: the cross relied
  on `window.confirm()`, and a browser told to stop asking for
  confirmations answers "no" on the spot. The confirmation is now inline
  - the first tap arms the cross (red tick), the second deletes, three
  seconds to change your mind - with no dialog anywhere.
- **The web theme toggle could sit off the corner** and drag the whole
  column sideways: a `position: fixed` button was captured by a list
  that created a positioning context.
- **The Settings aurora collapsed its own window**: the drifting ellipses
  were laid out inside the very rows they were meant to float behind;
  they now sit in a dedicated background layer, like the main window.

## [0.12.1] - 2026-10-07

### Fixed

- **QR scanning inside the browser on phones**: the *Scan QR code*
  button refused to start on Safari (iPhone), Brave and Firefox - "QR
  reading is not supported by this browser" - because those browsers
  ship `getUserMedia` but not the Shape Detection API the scanner
  relied on. The camera frames are now decoded by the bundled jsQR
  (MIT, `web/jsqr.min.js`, fetched only when needed) whenever the
  native `BarcodeDetector` is missing, so every phone scans the code
  without leaving the page. Chrome and Edge on Android keep the native
  detector (no extra cost); the old message remains only as a last
  resort if the decoder cannot load.

## [0.12.0] - 2026-10-07

### Added

- **Motion layer** (reactbits-inspired) across the desktop window and the
  web interface, in both themes, all of it switching itself off when the
  system asks for reduced motion:
  - **Specular sheen**: buttons and tabs catch a light that follows the
    pointer and fades with the distance (`Shine.cs` on every desktop
    window - the shared-files list is rewired after each refresh - and a
    CSS-variable twin on the web). Phones and tablets get no sheen at
    all: a tap is a one-shot pointermove, so the white glow would freeze
    on the button you just pressed.
  - **Spring tab indicators**: the web Send/Download pill slides with a
    spring (slight overshoot, then settle), and the Settings sidebar
    highlight does the same in Avalonia.
  - **Entry animations** on the web: content settles in when a tab
    changes and file cards slide in, removed ones slide out.
  - **Aurora background** in the desktop window: three soft ellipses
    drifting on a slow margin cycle behind the content, light and dark
    alike.
  - **OPENDROP wordmark** replacing the header's download glyph: every
    letter springs up and glows when the pointer comes over it.
- **Scrollbar pill**: the web page hides its native bar and rides a
  12 px gradient pill (fade in while scrolling or when the pointer nears
  the right edge, bloom on hover, draggable); the desktop scrollbar is
  restyled to match (gradient thumb, rounded track, hover scale and
  glow) instead of the stock Fluent one.
- **Theme toggle in the main window**: a sun/moon button flips
  light/dark in one click, the choice is written to config.json, and the
  glyph refreshes when Settings changed the theme meanwhile. The web
  button keeps its own per-device switch.
- **Copy the session code**: one click puts the code on the clipboard
  (Avalonia 12 `DataTransfer` API) and the button confirms with
  *Copied ✓* for a second and a half.
- **Quota bar on the web**: a real fill with eased width transitions,
  plus the same indeterminate sweep as the desktop app when the server
  sends no numbers.

### Changed

- The desktop quota fill glides to its value instead of jumping, and
  shows the sweeping placeholder rather than a blank track while quota
  is unknown.
- The web theme toggle no longer slides halfway off the corner
  (positioning context fixed).

### Fixed

- **Desktop quota bar over-reported the usage**: the fill measured the
  status text above it (centred and narrower than the track), so a full
  quota rendered as about four fifths of the bar. It now measures the
  track itself, with one layout-pass retry, and keeps the `full` state
  in sync.
- **Web build failed on Avalonia 12**: `IClipboard.SetTextAsync` no
  longer exists; the copy button now goes through
  `SetDataAsync(DataTransfer)`.
- **White glow stuck on buttons on phones**: the sheen's frozen light is
  gone (CSS `(pointer: coarse)` guard plus a `pointer: fine` check in
  app.js).

### Removed

- **The coloured aurora background on the web** (PC and phone): the page
  sits on its flat background again. It was introduced this session,
  sized in `vw` but offset in `vh` (invisible on portrait screens even
  after the geometry was corrected to `%`), and is dropped on request;
  the desktop window keeps its own animated version.

## [0.11.0] - 2026-10-07

### Added

- **Drag & drop onto the share panel**: files or folders dragged from the
  Explorer onto the *Shared files* card are copied into the share folder,
  folders being added file by file. The card outlines itself with the
  accent colour while it is the drop target. A drop always copies, never
  moves, so a drag can never empty a folder by surprise.
- **Windows-style selection** in the shared-files list: dragging the left
  button over the empty area draws a rubber band and selects everything it
  touches (holding Ctrl keeps the current selection), **Ctrl+A** selects
  everything, and the **Delete** key deletes the selection after the usual
  confirmation.
- **Batch rename**: renaming a selection of several files asks for one
  base name and numbers the result like the Explorer (`report.pdf`,
  `report (2).pdf`, `report (3).pdf`...). Every file keeps its own
  extension and an existing file is never overwritten.

### Changed

- *Add files* and a drop now share the same import path: same progress
  hint, same busy state, same copy/skip/failure report.
- The *Rename* button accepts any number of selected files instead of
  demanding exactly one.

## [0.10.0] - 2026-10-07

### Added

- **Depth**: the surfaces are layered instead of flat. The window
  background becomes a gradient, every card carries a two-part box
  shadow (wide and soft, plus a tighter contact one) finished by an
  inset highlight along its top edge, and the settings fields are
  pressed into their card with an inner shadow and a hairline rim.
- The title bar gets its own surface (`Brush.Surface2`) closed by a
  rim, so the chrome reads as a plane above the content.
- The primary buttons (Start server, Save) sit above the cards with a
  coloured drop shadow: a Button cannot take a BoxShadow in Avalonia,
  the effect is its equivalent.

### Changed

- Depth lives in the theme dictionaries as `Surface.Window`,
  `Shadow.Card`, `Shadow.Recessed`, `Brush.Rim` and `Shadow.Accent` -
  one definition per level, both variants sharing the keys, so the
  light and dark passes only differ in colour. The brushes reserved by
  0.9.0 now have their first readers.
- Verified at runtime in both themes: gradient background, three box
  shadows per card, recessed fields with their rim, drop shadow on the
  accent buttons. Screenshots in the README are redone in the final
  pass (0.14.0).

## [0.9.0] - 2026-10-07

### Added

- **Tabbed Settings window**: the single scrolling form is replaced by a
  sidebar of six tabs (General, Storage, Security, Network, Appearance,
  Updates) built from styled `RadioButton`s plus a content area that
  shows only the selected page. The window keeps its fixed height, every
  page scrolls on its own, and the controls and save logic are exactly
  the ones the old form used.
- **Reserved palette keys** in both themes: `Brush.Surface2`,
  `Brush.ShadowColor`, `Brush.Glow`, `Brush.GlowSoft`, `Brush.IconFar`,
  `Brush.IconNear` and `Brush.IconHover`. Nothing reads them yet - they
  are the hooks the depth and proximity effects will use, so they exist
  (with quiet values) before anything depends on them.
- `src/opendrop/themes.py`: the theme catalogue (`THEMES`, plus
  `normalize_theme`) now has a single home on the server side.

### Changed

- `ThemeManager` exposes the themes as an extensible list of
  `ThemeDefinition` (config id + translation key) instead of two
  constants, and the settings combo box is built from that list in the
  current language instead of hardcoded `ComboBoxItem`s.
- `main.py` and `server.py` validate the theme through `opendrop.themes`
  instead of a hardcoded `("light", "dark")`; `config.py` takes its
  default from the same module.
- The web page validates `data-theme` against the same list
  (`VALID_THEMES` in `app.js`); `style.css` still ships only the light
  and dark blocks.
- `tests/test_server.py`: `/api/info` must publish a known theme and an
  unknown theme in the config falls back to `dark` (16/16).

## [0.8.1] - 2026-10-04

### Changed

- **New app icon**: the window, tray and installer icon on Windows and the
  menu icon on Linux now use the project logo instead of a generated QR
  code pointing at the repository. `tools/make_icon.py` reads
  `docs/screenshots/OpenDrop_Logo.webp` and writes `app.ico` (seven sizes,
  16 → 256) plus `packaging/linux/opendrop.png`; the unused
  `desktop/OpenDrop/app.png` by-product is dropped.
- Dependencies: `QRCoder` 1.4.3 → 1.8.0 (desktop),
  `actions/upload-artifact` 4 → 7 (workflow).

## [0.8.0] - 2026-10-04

### Added

- **Discord button** in the desktop title bar: it opens the OpenDrop
  server invite (`https://discord.gg/vREBPZuvhV`) in the default browser,
  with a tooltip translated in both languages (123 → 126 strings per
  language). The README gained a Discord badge and a *Community* section,
  and `CONTRIBUTING.md` sends questions there.
- **Updates can be cancelled and resumed**: the progress window has a
  *Cancel* button (closing the window cancels as well), and an interrupted
  download picks up where it stopped with an HTTP `Range: bytes=N-`
  request instead of starting over — a `416`, or a response that ignores
  the range, purges the cached file and downloads it again from scratch.
- **A release without a published `sha256:` digest is refused** before any
  transfer (`Up.NoDigest`): the updater never falls back to an unverified
  download, whatever the GitHub response looks like.
- The Windows setup helper reports its exit code back to the app, so a
  failed installation is surfaced at the next start (`Up.InstallFailed`)
  instead of staying silent.
- README: *FAQ*, *Troubleshooting*, *Known limitations* and *Release
  process* sections.

### Fixed

- **An older setup could be installed over a newer version**: the Windows
  installer now compares the installed release and refuses to downgrade,
  instead of silently replacing a newer build by an older one.
- The token countdown was still in English and clipped on its left edge
  in French.

### Changed

- Installer message boxes are skipped in silent mode (they used to block
  `/VERYSILENT` forever) and the setup reports `1`/`2`/`3` instead of a
  uniform `0`, which made every failure look like a success.
- Dead `Console.WriteLine` output removed from the desktop entry point and
  the Python server; test identifiers renamed to English.
- Dependabot watches the desktop project (NuGet) alongside Python, and the
  private checklist is now ignored.
- Release numbers follow semantic versioning (the `0.1.x` line became
  `0.2.0` … `0.7.0`).

## [0.7.0] - 2026-10-04

### Added

- **Automatic updates**: OpenDrop now looks for a newer release when it
  starts (three seconds after the window is up, never before, and
  without a word if GitHub cannot be reached) and from
  *Settings → Updates*, which also shows the running version and the
  outcome of the check.
  - Windows: the matching `setup.exe` is downloaded, checked against the
    SHA-256 digest GitHub publishes with the asset, and handed to a
    detached helper that waits for OpenDrop to exit and runs it with
    `/VERYSILENT`. Same `AppId`, so the new version replaces the old one
    in place: a single entry in *Programs and features*, the previous
    installation is overwritten rather than uninstalled (an uninstaller
    would delete the settings), and `%LOCALAPPDATA%\OpenDrop` is outside
    `{app}` so the configuration survives untouched.
  - Linux: the `tar.gz` is verified the same way, then applied either in
    place (archive unpacked by hand: the running binary is renamed first
    to dodge `ETXTBSY`, dependencies are refreshed from the bundled
    wheels, no network needed) or through the bundled `install.sh` run
    with `pkexec` when the installation lives in `/opt`.
  - The new process starts only once the old one is gone, through a
    helper waiting on its PID: the single-instance lock would otherwise
    make it hand the signal back and quit.
  - *Skip this version* is remembered in `config.json` (`skip_version`)
    and silenced for that version only; *Later* keeps the offer for the
    next start. Drafts, pre-releases and releases without a `vX.Y.Z` tag
    are never offered.
- The new dialogue, the progress bar and the *Updates* section are
  translated in both languages (105 → 123 strings per language).

### Fixed

- **Installing over a running copy could fail with "Text file busy"**:
  `install.sh` now moves the running binary aside before replacing it,
  so an update can be applied while the previous version is still up.

## [0.6.1] - 2026-10-03

### Fixed

- **The port crept up on every reset (Linux)**: restarting the server
  moved it from 8080 to 8081, then 8082 and so on, while `config.json`
  still said 8080 — a manually entered port never stayed either. The
  server closes every response, so its own connections linger in
  `TIME_WAIT` on that port for ~60 s after a restart; the "is this port
  free?" probe bound *without* `SO_REUSEADDR` and read those leftovers as
  another program holding the port, so `find_available_port` stepped to
  the next one. Windows was unaffected, because a plain bind succeeds
  over `TIME_WAIT` there. The probe now sets `SO_REUSEADDR` on POSIX: it
  ignores the leftovers but still refuses to bind while a socket is
  really listening (that needs `SO_REUSEPORT`), which is the case it has
  to detect — and it now matches what the real server does
  (`allow_reuse_address`), so probe and server finally agree.

### Added

- Three port-probe checks in `tests.test_server` (11 → 14): `TIME_WAIT`
  leftovers do not hide a port, the preferred port survives a restart,
  a live listener is still reported as busy.

## [0.6.0] - 2026-10-03

### Added

- **Light / dark appearance**: *Settings → Appearance* now offers two
  themes, Light and Dark, applied instantly and persisted in the `theme`
  key of `config.json`. Default: dark.
- **The phone page follows it too**: `style.css` was rewritten on CSS
  variables with a light and a dark palette, `/api/info` reports the
  desktop choice, and a ☀/☾ button in the corner switches this device
  only. The local override is dropped on its own as soon as the PC theme
  changes, so the page never stays out of sync.

### Changed

- The whole desktop palette moved to theme resources (`Brush.*` in
  `App.axaml`), with a dedicated Light and Dark dictionary: the main
  window, the settings dialog and the message boxes resolve the same keys,
  so a surface can no longer keep a hard-coded colour that ignores the
  theme.
- The saved preference is applied before the main window is created, so
  the first frame is already in the right theme.
- The web page declares `color-scheme` and `theme-color` for both themes,
  so native widgets and the browser chrome follow the palette.

### Fixed

- **Random black / frozen page on the phone**: the TLS handshake used to
  run on the *listening* socket, i.e. inside the single accept loop. One
  client frozen mid-handshake (browser pre-connect abandoned when the
  phone locks, a Wi-Fi drop in the middle of the ClientHello, a port
  probe) stopped the server from accepting anything else, and every other
  client was left waiting on an unresponsive page. The handshake now
  happens in the worker thread that owns the connection and is bounded to
  10 s; the accept loop never waits on a client.
- A rejected POST could lose its own status code: the server answered
  while the request body was still queued, the kernel then reset the
  connection, and the client saw a cut connection instead of the
  400/429/507 (it showed up as `RemoteDisconnected` in the Linux CI).
  The unread body is now absorbed first, bounded in size and time, and
  only until the upload parser starts consuming it.
- The TLS connection is released in the handler instead of by the garbage
  collector: `wrap_socket()` hands the descriptor to a new object, so the
  framework's `shutdown_request()` could no longer close anything and the
  response used to depend on when the collector showed up. A handshake
  that fails is closed on the spot as well.
- The theme preference now goes through the same config path as every
  other component: `ThemeManager` resolved the shell folder instead of the
  `LOCALAPPDATA` environment variable, so a redirected profile (tests,
  sandboxed runs) saw its real `config.json` rewritten while the rest of
  the app wrote to the redirected one.
- The receive-folder quota scan no longer runs while holding the quota
  lock. The phone polls usage every 5 s, and a slow folder (large tree,
  OneDrive placeholders, antivirus) could previously block uploads and
  every other quota call for as long as the scan lasted.
- Listen backlog raised from 5 (the `http.server` default) to 128: a cold
  page load opens several connections at once and the default could drop
  them, which looks like a blank page.
- Idle connection timeout raised from 10 s to 30 s, so a short screen-off
  hiccup no longer kills an upload mid-transfer.
- Mobile page: every API request now carries a deadline (8–20 s) and
  repeated failures display *Server unreachable* instead of leaving the
  screen stuck on *Loading...*. A quota poll answered 401/403 (rotated
  token) now locks the session instead of keeping a dead page alive.
- Mobile page: the QR scanner no longer stacks `detect()` calls, which
  could starve the UI on a slow phone.
- Mobile page declares `color-scheme` and `theme-color`, so the
  background is deterministic while loading or when the browser shows its
  own error page.

### Removed

- **Update system**: startup check, *Settings → Updates → Check now*,
  in-place installer, `update.xml` manifest, release-workflow entry and
  the related documentation. The desktop application downloads and
  installs nothing.
- **9 fancy themes** (Neon, Midnight, Forest, Sunset, Monochrome, Rose,
  Amber, …) and the *System* option: only Light and Dark remain, and both
  language files dropped the unused names and descriptions.
- Debug log files (`theme.log`, `crash.log`, and their `.err`
  counterparts).

## [0.5.1] - 2026-09-28

### Changed

- **In-place updates**: the application now downloads a payload zip, verifies it, extracts it, and atomically replaces its own files before restarting. Configuration, sessions, certificates and the moved-files registry (`moves.json`) are preserved.
- **Elevation only when needed**: if the application folder is writable (typical user install), the update runs without UAC. For Program Files installs the worker requests elevation once; the restarted application drops back to standard rights.
- **Specific UAC decline message**: if the elevation prompt is dismissed, a clear message is shown and the current version keeps running.

## [0.5.0] - 2026-09-28

### Added

- **Put back**: a file added to the share folder with *Add files…* → *Move*
  now remembers where it came from and shows a **Put back** button on its
  row. One click (after a confirmation) moves it back to its original
  folder, even after a restart: the remembered origins are stored in
  `%LOCALAPPDATA%\OpenDrop\moves.json`. Files that are copied, renamed or
  deleted no longer point anywhere and their button disappears.
- **Open** button next to each folder line of the **FOLDERS** card
  (received and shared) to open that folder in File Explorer.
- **Double-click a file in the share folder to open it** (rename stays on
  the *Rename* button). A file that disappeared in the meantime is reported
  instead of failing silently.

## [0.4.0] - 2026-09-28

### Added

- **Share folder browser** in the main window: the right-hand panel lists
  every file of the share folder (name and size) with **Add files…**,
  **Rename**, **Delete** and **Refresh**, multiple selection, the folder path
  always visible, and a refresh whenever the window regains focus.
  - *Add files…* opens a file picker (several files at once) and then asks
    whether to **copy** or **move** them into the share folder: an existing
    file is never overwritten (a numbered name is used instead) and the
    result reports how many files were added, skipped or failed.
  - *Delete* confirms first and lists the files it removes from the disk;
    *Rename* refuses a name that is already used or invalid.
- **Close to tray (Windows)**: the close button now hides the window instead
  of stopping the server. The tray icon offers *Show* and *Quit*; the server
  keeps serving while the window is hidden, and *Quit* is the only way to
  really exit.
- **Download progress for updates**: while downloading, a dialog shows the
  percentage and the transferred / total size with a working **Cancel**, then
  a "verifying" state while the SHA-256 is checked. A failed, cancelled or
  corrupted download is reported instead of failing silently.
- **Manual update check** in *Settings → Updates* (**Check now**): reports
  "you are up to date" or offers the newer version, without restarting the
  app.
- `"check_updates": false` in `config.json` is now actually honoured
  (documented since 0.3.0 but not read yet).

### Changed

- Main window widened (880×720, minimum 760) with a two-column layout:
  connection information on the left, share folder on the right.
- Update downloads stream to disk instead of holding the whole file in
  memory, and the SHA-256 is computed off the UI thread.

### Fixed

- The update check follows HTTP redirects again: GitHub serves release assets
  with a `302`, so without redirects every download failed right away.
- The desktop app reads `update.xml` from this repository; the 0.3.0 build
  still pointed at the retired updates mirror and could not see newer
  releases.
- The left column no longer jumps down when the QR code appears at startup.
- The startup check runs only once, even when the window is hidden to the
  tray and shown again later.

## [0.3.0] - 2026-09-27

### Added

- **Automatic updates (Windows)**: at startup the desktop app reads a public
  `update.xml` manifest, and offers to download and install a newer release
  in one click. The setup is verified against a SHA-256 digest before it is
  launched. The installer reinstalls the application into `Program Files`
  only and **never touches** `%LOCALAPPDATA%` (config, session, certificate),
  so your settings survive an update. Opt out with `"check_updates": false`
  in `config.json`.
- **English/French language choice**, English everywhere by default:
  - full English rewrite of the code, comments, web interface and
    documentation; French kept as a second language
  - new `language` setting in `config.json` (`en` by default, `fr`
    optional); translated error messages on every API route, `/api/info`
    reports the active language
  - web interface picks the language from the server at startup
  - desktop app: language selector in *Settings* (English/French), applied
    live and persisted, English on first launch
  - Windows installer: *Application language* task (English/French) that
    seeds `config.json` on first install only
- Server: `format_size` and quota messages localized (`GB/MB` vs `Go/Mo`),
  banner and status lines in the selected language

### Fixed

- CI: `test_routes` failed intermittently on Windows with
  `PermissionError: [WinError 32]` while removing a file the server had just
  sent; the cleanup now retries briefly
- The update manifest now uses the real release asset name (`v` prefix) and
  embeds the SHA-256 of the setup; it is committed on `main` and served from
  this public repository, so the app needs no token
- Versions aligned on 0.3.0 (`pyproject.toml` was still 0.1.0)

## [0.2.0] - 2026-09-27

### Added

- Cross-platform desktop app: ported from WPF to **Avalonia** (.NET 8), one
  codebase for Windows (`win-x64`) and Linux (`linux-x64`), published as a
  single self-contained file
- **Windows installer** (Inno Setup): admin rights, installs into
  `Program Files (x86)`, Python dependencies installed locally from the
  bundled wheels (offline, `venv` in the install folder), start menu/desktop
  shortcuts, French/English interface, uninstaller that cleans up app data
  **without ever touching** the receive and share folders
- **Linux scripts** (`install.sh` / `uninstall.sh`): install into
  `/opt/opendrop` with a local `venv` and a menu entry
  (`opendrop-desktop`), equivalent uninstall that keeps the received and
  shared files
- Automated releases: on every `v*` tag, GitHub Actions generates
  `*-win-x64-setup.exe`, `*-win-x64.zip` and `*-linux-x64.tar.gz` (offline
  wheels included)
- App and menu icons generated by `tools/make_icon.py` (QR code)
- Linux launch: the QR code opens through `xdg-open` (and `open` on macOS)
  instead of being ignored (`os.startfile` only exists on Windows)
- README: *Linux (no desktop available)* section, *Downloads* section,
  cross-platform requirements, Linux badge
- `Operating System :: POSIX :: Linux` classifier in pyproject

### Changed

- `main.py` version string aligned with the release tag (`v0.2.0`)

### Fixed

- `server.pid`: the config folder didn't exist on the very first launch, the
  write failed silently, and an orphaned server could hold the port on the
  next start
- The desktop app now uses the `venv` created by the installer
  (`venv/Scripts/python.exe`, `venv/bin/python3`) before `python`/`python3`
  from PATH: dependencies guaranteed whatever the setup
- Desktop config path aligned with the Python server: `LOCALAPPDATA` read
  the way Python does, `~/.opendrop` fallback on Linux (desktop and server
  read the same `config.json` on both systems)
- Server launch on Linux: `python3` first (Debian/Kali have no `python`
  alias)

## [0.1.0] - 2026-09-27

First public release.

### Added

- Local HTTP(S) server: self-signed EC P-256 certificate (397 days), HTTPS
  enforced on every route, TLS 1.2+
- Session based on a random 32-character token, configurable expiration,
  manual rotation (`--rotate-token`, Reset button) or automatic, 6-character
  backup code (31^6, 5 tries/min/IP)
- Install-free web interface: *Send* / *Download* tabs, session lock, live
  quota bar (green/red)
- *Share* folder: files offered to other devices, one-click download
- Global receive quota: 507 rejection before writing, atomic reservations
  (simultaneous sends), negative values reset to 0 (unlimited)
- Safety limits: 10 GB per file, per-IP rate limits, sanitized file names,
  validated paths, no server path leaks, logs with no secrets
  (`token=***`, `code=***`)
- Windows desktop app (WPF, .NET 8): QR code, address, session code, quota,
  folders, settings, server start/stop
- Homegrown tests: 8 suites, 287 checks (299 with `--large`)
- GitHub Actions continuous integration (tests + desktop build) and
  Dependabot
