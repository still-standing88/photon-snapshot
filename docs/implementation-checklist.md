# Animation and batch conversion implementation checklist

Started: 24 November 2026. Source: [feature plan](animation-and-batch-conversion-plan.md).

Status: implementation and available Windows acceptance checks completed on 24 November 2026. Platform and accessibility limits are recorded below.

## Implementation

- [x] Follow-up interface changes: Photon name, New submenu, Tools before Options, context actions with selection-aware enabled states.

- [x] Locate and inspect the feature plan and Playform interface reference.
- [x] Record baseline regression results and repository constraints.
- [x] Shared format registry, pixel processing, encoding controls, and verified atomic exports.
- [x] Animation decoding, bounded frame storage, timing and loop policies, and project serialization.
- [x] Document history, save checkpoints, current/selected/all edit scope, and frame operations.
- [x] Frame strip, keyboard navigation, playback, import/new animation, and onion skin.
- [x] Document-owned text/shapes and native-resolution artwork export.
- [x] Save/export dialogs, immutable worker snapshots, and unsaved-document protection.
- [x] Qt-independent batch discovery, processing, source protection, cancellation, and results.
- [x] Four-tab batch interface, presets, effect editing, progress, and job lifecycle.
- [x] Shortcut/focus/theme/translation integration and regression tests.
- [x] User documentation, release notes, and Windows packaging verification.

## Acceptance checks

- [x] Still-image open/edit/undo/redo/Save As/Save.
- [x] GIF/WebP decode, frame edit, reorder, undo/redo, timing, and loops.
- [x] New/imported animation, independent duplicates, scoped drawing/text/shapes.
- [x] Project save/reopen and export at different zoom levels.
- [x] Keyboard navigation and normal typing in numeric/text fields.
- [x] Batch files/folders/effects/settings/destinations/presets.
- [x] Batch corrupt inputs, collisions, skips, pause/resume/cancel, and reopening progress.
- [x] Real desktop clicks and demo-image save/reopen flows.
- [x] Large-input measurements and resource cleanup.
- [x] Packaged and installed Windows smoke tests; record unavailable platform checks honestly.

## Evidence and constraints

Results, fixes, and platform limitations are recorded here as checks finish.


### Completed verification

- Baseline: 30 existing tests passed.
- Final complete regression/core/UI run: **59 tests passed** in 19.638 seconds. Includes new/imported animation, natural ordering, scoped drawing/text, project/export, drag ordering, worker responsiveness, cancellation, metadata, disposal and batch partial failures.
- Translation pipeline: 496/496 strings translated for French, Spanish and Arabic; PO/MO compilation succeeded.
- Desktop checks: selected the middle GIF frame, exercised finite playback, opened the four-tab converter, selected a downloaded JPEG through the native file dialog, selected PNG and pressed Begin. Result: 1 converted, 0 skipped, 0 failed, 0 cancelled; output decoded at 640×480.
- Desktop project save: saved desktop-saved.photonanim. Core reopen verified 3 frames, 3 total plays, and 100/250/400 ms durations.
- Desktop testing found and fixed expanding accordion headers, Save As defaulting to a still format for animations, thumbnail captions, and project-file dialog filtering.
- Performance: 100 frames at 512×512 imported in 0.476 s with 100 MiB cached. 100 frames at 1920×1080 imported in 6.267 s with 265,420,800 bytes cached and 722,370 bytes spilled. Reading/resizing all 1080p frames took 5.701 s.
- 1,000 small PNG→JPEG conversions: 19.04 s; all 1,000 converted without failures. Configured decoded-resource rejection also passed.
- Final Nuitka Windows build succeeded with version **1.2.0.0**. The current distribution passed GIF/WebP timing/loop round trips, editable project artwork/save and three-file batch conversion.
- The normal packaged application was reopened visibly with the saved project. Maximize/restore worked and Fit to Window adjusted from 88% to 91% and back. The app was left open for use.
- Real desktop continuation: opened the saved project through the native dialog; verified all three frame durations and total plays; previewed and exported GIF; opened the downloaded JPEG; applied grayscale, undo and redo; saved a WebP copy; edited it and used Save. The saved GIF decoded at 320×240 with 100/250/400 ms frames and three plays. The WebP decoded at 640×480.
- Real batch context menu: Add Files/Add Folder remained available for an empty list; Remove/Clear were disabled. Automated checks also verify effect/frame menu selection and boundary states.
- Layout verification: English, French, Spanish and Arabic main windows and all four batch tabs fit within 900×700 logical pixels in light/dark themes. Arabic was rendered at 150% display scale with chronological left-to-right frame order. Long adjustment labels now use separate button rows. Documentation screenshots were rendered with the application's fonts and reviewed.
- Windows locked and read-only destination checks preserved old bytes and removed temporary output. Separate-frame collisions and simulated partial write failures retained the source and reported the correct result.
- Final x64 MSI built successfully. Installation into `Installed Photon é` returned 0; the installed application passed all codec/project/batch smoke checks; its executable SHA-256 matched the distribution. Uninstall returned 0 and removed the executable, installation folder and registry registration.
- Packaging fixes: valid WiX metadata, x64 component authoring, HKCU key paths/folder cleanup, supported-format Open With registrations, optional desktop shortcut, and remembered custom installation paths. Build failures now propagate a nonzero exit code.
- User guides, format reference, release notes and README links/screenshots are current. `scripts/verify_windows_package.ps1` repeats the isolated install/smoke/uninstall check and refuses to replace an existing registered installation.

### Platform limits and release status

- macOS installed-build checks require a macOS host; the workflow retains packaged checks for both macOS architectures.
- Windows accessibility trees and keyboard controls were checked. Screen-reader speech output has not been manually audited.
- Pause/cancel takes effect at safe processing boundaries; a running native Pillow encoder must return before cancellation completes. Already committed separate-frame outputs are retained after a later failure, as documented.
- Distributables: `dist/app.dist/PhotonSnapshot.exe` and `dist/installer/PhotonSnapshot-1.2.0.msi`. Evidence/logs are in ignored `qa-artifacts/`; reviewed English screenshots are in `assets/screenshots/`.
- No release has been published.

Existing unrelated working-tree edits were preserved. Git status requires --ignore-submodules=all because the pre-existing .claude worktree entry points at an unavailable H: path.
