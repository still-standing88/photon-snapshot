# Playform batch converter: interface and implementation reference

Inspected: 23 November 2026. This document records the local source, not a live UI screenshot. Implementation instructions are in [the feature plan](animation-and-batch-conversion-plan.md).

Reference checkout: `E:\Users\earsv\OneDrive\Documents\PlayForm`. Its reported HEAD was `27afdfcf7ff65c617f6242fe6d4e78a41a2ce7f4`; findings below refer to the inspected working files. Photon also contains an ignored `playform-imports/` reference snapshot; the sibling PlayForm checkout was used for this inspection.

## Tool layout

The converter is a QWidget hosted inside Playform's generic ToolDialog. The tool has an editable preset combo and Save/Delete buttons, followed by four tabs in this exact order, and a bottom-right Begin button:

```text
Preset: [ editable preset name                         ] [Save] [Delete]
[ Source ] [ Convert ] [ Processing ] [ Destination ]
| Content of selected tab                                             |
|                                                                    |
|                                                            [Begin] |
```

The outer ToolDialog adds a title, Hide, and Close, and scrolls oversized tool content. The conversion progress is a separate window with overall progress, current-file detail, Progress and Live Log tabs, completion-notification choice, Pause/Resume, and Cancel changing to Close after completion.

## Source-to-Photon mapping

| Inspected source | Existing behavior | Photon mapping |
| --- | --- | --- |
| [BatchConverterUI](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/ui.py:23) | Preset row; four tabs; Begin; validation; job/progress wiring | Preserve layout and orchestration, using image options and structured results |
| [SourceTab](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/source_tab.py:6) | Add Files/Add Folder above a source tree | Preserve layout; image-filtered dialogs |
| [AddFolderDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui_controls/path_tree_widget.py:21) | Path/Browse; Include all subfolders; Audio/Video/All/Custom formats | Preserve path/recursion; replace format scopes with All supported images/Custom image format |
| [PathTreeWidget](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui_controls/path_tree_widget.py:99) | Path/Formats columns, nested folders, extended selection, context menus, Delete removal | Recreate with image format IDs and lazy/background folder discovery |
| [ConvertTab](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/convert_tab.py:215) | Audio/Video mode radio buttons and stacked format panels | One image conversion panel; no media mode selector |
| [AudioConvertPanel](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/convert_tab.py:12) | Format, sample rate, bit rate, VBR, bit depth, conditional codec options | Reuse the conditional-form pattern; supply image quality/compression/transparency options |
| [VideoConvertPanel](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/convert_tab.py:156) | Format, resolution, video bit rate, frame rate | Remove these controls; animation timing belongs to frames, dimensions to the Resize effect |
| [ProcessingTab](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/processing_tab.py:12) | Applied effects in order; Add Edit/Add Filter; editing/removal/reordering | Preserve interaction; use image edits and filters |
| [EffectPickerDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/effect_picker_dialog.py:11) | Branch-specific categorized picker | Image-specific Transform/Adjustments/Colour catalog |
| [EffectSelectionDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui_controls/effect_dialogs.py:13) | Categorized tree, OK/Cancel; picking produces default parameters | Preserve selection flow; separate image parameter editor |
| [EffectEditDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui_controls/effect_dialogs.py:91) | Parameter form for one effect, optional per-effect presets | Image parameter form; top-level batch presets are sufficient initially |
| [DestinationTab](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/destination_tab.py:7) | Original/target folder; subfolder preservation; overwrite/delete/log controls | Retain these conversion-relevant controls and enabled-state behavior |
| [JobProgressDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui_controls/job_progress_dialog.py:11) | Results/live output; overall progress; pause/cancel; notify selection | Preserve layout; image phase/frame events replace FFmpeg output |
| [ToolDialog](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui/dialogs/tool_dialog.py:10) | Hide/Close wrapper, scroll area, screen fitting, activity guard | Recreate useful shell behavior; explicitly track batch `job` lifecycle |
| [ToolWindowManager](E:/Users/earsv/OneDrive/Documents/PlayForm/src/gui/managers/tool_window_manager.py:12) | Opens/reopens registered tools; requires FFmpeg for batch conversion | Small image-tool owner; no FFmpeg dependency check |

## Controls and serialized state

### Source

The tree keeps `(path, entry_type, entry_formats)` entries with `file` or `folder` types. Individual files display their basename and full-path tooltip. Folder rows display basename and selected extensions. It normalizes paths for duplicate tree entries. Include all subfolders eagerly adds nested folder rows; `iter_entries()` walks those rows recursively.

Remove/Clear are in the context menu, and Delete removes selected rows. The source file has no drag/drop handler; drag/drop in Photon would be an addition, not a feature observed here.

### Convert

Audio mode returns `mode`, `format_id`, sample rate, bitrate, VBR/quality, bit depth, and format-specific codec options. Video mode returns `mode`, format label, codec, resolution, video bitrate, and framerate. The audio panel hides complete form rows and builds only relevant codec inputs.

Photon should retain stable IDs and conditional controls, but none of these audio/video fields belong in its conversion payload. Its replacement payload contains image format, encoder options, alpha/background policy, metadata policy, and animation handling.

### Processing

The list stores `(effect_id, values)` pairs in application order. Available effects are not permanently displayed in this tab. Add Edit/Add Filter opens a categorized selector; the inspected selector returns that effect's default values. Editing its parameters is a separate double-click/context-menu action. Context menus provide Edit, Remove, Move Up, Move Down, and Clear All. Delete removes selected effects.

Playform's referenced catalog contains audio operations such as loudness normalization, silence removal, EQ, reverb, and phaser. It is not a usable image-filter catalog. Preserve the interface and ordered-data shape while implementing Photon operations.

### Destination

The exact option keys are:

| Key | Meaning | Default/UI state |
| --- | --- | --- |
| `store_in_original_folder` | Put each output beside its source | Selected initially |
| `target_folder` | Common chosen output folder | Empty; enabled in target mode |
| `preserve_subfolders` | Preserve source-root/subfolder layout | Unchecked; enabled in target mode |
| `overwrite_existing` | Allow replacing existing outputs | Unchecked |
| `delete_originals` | Remove originals after conversion | Unchecked |
| `create_log_file` | Write an additional run log | Unchecked |
| `log_file_path` | Chosen log filename | Empty; controls enabled only when logging is selected |

The actual runner includes the selected source root's basename when preserving subfolders, because it computes paths relative to the parent of that root. Photon should use that explicit convention and detect root-name collisions.

### Presets

The top-level preset payload is `{convert: ..., processing: ...}`. Source and Destination are not saved. Presets now live in Playform's user-presets database with kind `ffmpeg_batch`; older on-disk JSON presets are migrated once and removed.

Photon needs its own image-preset namespace and database facade. It does not need this migration, Playform database access, or paths to legacy Playform data.

## Execution implementation

[BatchConverterJob](E:/Users/earsv/OneDrive/Documents/PlayForm/src/tools/ffmpeg/batch_converter/job.py:9) is a QThread wrapper. It resolves FFmpeg executables and passes callbacks to [ConversionRunner](E:/Users/earsv/OneDrive/Documents/PlayForm/src/media_core/ffmpeg/conversion_job.py:61), which is independent of Qt. That separation is the useful backend pattern for Photon.

The job signals are `overall_progress(int, int, str)`, `file_progress(str)`, `file_completed(str, bool, str)`, `log_line(str)`, and `finished_all(bool)`. Pause/resume uses a threading event; stop sets the running flag false and wakes a paused runner. Pause takes effect at file boundaries in this runner.

The resolver visits explicitly queued files and lists immediate files for each folder entry. Recursion comes from the tree having separately supplied nested folder entries. The runner checks same-source output paths, skips existing destinations unless overwrite is enabled, converts, optionally deletes originals, logs per-file outcomes, and continues after individual failures. A finished `True` means it was not stopped, not that every file succeeded.

## Behaviors to adapt during implementation

| Observed behavior | Required Photon adaptation |
| --- | --- |
| Recursive folder-tree construction runs synchronously | Discover/build asynchronously or lazily; keep UI responsive |
| UI resolves inputs to get a total and runner resolves them again | Resolve once in worker, publish a prepared work plan and total |
| Tree duplicates are normalized, but file/folder overlap can still resolve the same file twice | Deduplicate final batch inputs by canonical identity |
| Folder enumeration catches OSError and silently continues | Report unreadable/skipped source folders |
| Same-source output is skipped | Retain source protection, including aliases and any other queued source |
| Existing-output checks precede writes | Use temporary output and commit-time no-overwrite enforcement |
| Encodes directly to final destinations | Reopen/verify temporary output, then commit and cleanup on failure |
| Completion is one boolean; skips can be reported as success | Use converted/skipped/failed/cancelled counts and typed results |
| Live Log description says raw FFmpeg output | Replace with useful image preparation/encoding events |
| ToolDialog activity guard looks for `thread`, while batch UI stores `job` | Track explicit active jobs; do not destroy a running worker |
| Notify path looks up Playform's QApplication tray field | Use Photon TaskbarIcon/show_message integration |
| Preset helpers depend on Playform's database and migration | Use Photon Peewee model/facade/write queue with kind `image_batch` |

## Provenance

Playform's [app metadata](E:/Users/earsv/OneDrive/Documents/PlayForm/src/app_info.py:9) declares GPL-3.0. Photon declares MIT. This is an interface/architecture reference; reproduce the layout and interactions in Photon code. Direct copying of implementation source requires appropriate reuse rights or compatible licensing treatment before shipping.
