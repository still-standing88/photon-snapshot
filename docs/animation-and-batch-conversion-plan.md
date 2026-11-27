# How to implement animation editing, GIF creation, and batch conversion

Status: implemented; local verification and platform limitations are tracked in [the implementation checklist](implementation-checklist.md).

Prepared: 23 November 2026. Audience: developers implementing Photon Snapshot.

## Outcome and scope

Deliver one coherent image workflow:

- Open an existing animated GIF or WebP, inspect its frames, edit individual or multiple frames, preview playback, and export the animation.
- Create an animation from imported pictures or blank frames, including frame duplication, ordering, drawing, text, shapes, timing, and looping.
- Convert multiple image files or folders with presets, image encoding settings, optional edits and filters, destination controls, cancellable processing, and useful results.
- Preserve ordinary single-image editing and the application's keyboard access, themes, translations, preferences, and tray behavior.

The batch converter must reproduce Playform's interface structure: the preset row, **Source / Convert / Processing / Destination** tabs, **Begin** button, and progress window. Replace media-specific content with image content. Keep the Processing tab; image edits and filters are relevant. Consult the inspected-source mapping in [Playform batch converter reference](playform-batch-converter-reference.md) before implementing its widgets.

The first complete release covers static JPEG, PNG, BMP, TIFF, GIF, and WebP; animated GIF and animated WebP; and animation creation from images. APNG, multipage TIFF editing, video-to-GIF import, automatic in-between frames, transitions, and HEIC/SVG integrations are subsequent features. Detect excluded multiframe formats and report them or offer explicit frame extraction; do not silently turn them into still pictures.

Image-to-GIF creation does not automatically animate a still picture. Users supply, draw, or duplicate and modify successive frames.

## Starting conditions

The inspected Photon code stores one `PhotonImage` in `EditorState`. `Action` snapshots its pixels; `EditorState.load_image()` clears history. Neither method is suitable as the frame-navigation mechanism. `PhotonImage.from_file()` copies the currently decoded picture, and `save()` does not save an animation sequence.

`Save As` currently offers JPEG, PNG, BMP, TIFF, and WebP, using a hard-coded format list. It does not expose encoding settings. Subsequent `Save` uses the image's stored format, which is not updated by `Save As`; reconcile output format and path as part of this feature. JPEG flattening already exists, but its palette/grayscale-alpha branches need the same proper compositing behavior as RGBA.

The viewer's text and shape overlays are outside the saved image pixels. Grid, rulers, crosshair, and pixel information are editing aids. Animation text and shapes therefore need document ownership and export rendering; screen overlays alone are insufficient.

The project virtual environment contains Python 3.12.10, Pillow 12.3.0, and PySide6 6.11.1. JPEG, PNG/zlib, TIFF, and WebP codecs were detected there. The common static encoders were also exercised using the existing image layer. Verify animated encoding with round-trip fixtures before relying on it in the new UI. Runtime dependencies are unpinned except QDarkStyle, so available encoders must be checked at runtime and in packaged builds.

Use Pillow, PySide6, Peewee, and Python's standard library. FFmpeg is unnecessary for the specified image workflows.

## Delivery order

| Step | Deliverable | Prerequisite | Exit condition |
| --- | --- | --- | --- |
| 1 | Shared format and export services | Existing image layer | Still-image round trips and capability checks pass |
| 2 | Animation document and decoding | Step 1 | Imported frames reproduce source playback |
| 3 | Document history and edit scope | Step 2 | Frame operations and pixel edits undo correctly |
| 4 | Frame navigation and playback UI | Steps 2–3 | Keyboard navigation and variable-duration playback work |
| 5 | GIF creation and artwork rendering | Steps 3–4 | Imported/blank frames, text, and shapes survive export |
| 6 | Animation export and save integration | Steps 1–5 | GIF/WebP round trips and save prompts pass |
| 7 | Batch engine | Steps 1–2, 6 | Static and animation conversion jobs pass without Qt UI |
| 8 | Playform-style batch interface | Step 7 | All four tabs, presets, progress, and cancellation work |
| 9 | Application integration and regression QA | Steps 1–8 | Existing editor, accessibility, and lifecycle checks pass |
| 10 | Packaging, user documentation, and release | Step 9 | Installed builds complete the acceptance scenarios |

Steps 7–8 can begin for static files after Step 1, but animated batch conversion must wait for the shared animation export service. Keep the shared services as the dependency boundary; do not implement separate animation encoders for the editor and batch tool.

## Step 1: Establish shared format, processing, and export services

1. Add `src/core/formats.py` with stable format IDs, canonical extensions, extension aliases, readable labels, runtime read/write availability, transparency support, and animation support.
2. Make open/save dialogs, Explorer filters, `is_image_file()`, batch folder filters, and encoding controls consume that registry. Offer GIF as an output. Use stable IDs in widget data and presets, not translated display text.
3. Add `src/core/export.py` with `ExportOptions` and common still-image preparation/encoding functions. Keep `PhotonImage.save()` and `to_bytes()` as compatibility wrappers where practical. Capture the decoded source format before pixel copies or EXIF transposition can discard Pillow's format attribute; keep source format separate from the chosen output format.
4. Support JPEG quality 1–95 and optimize; PNG compression 0–9; WebP quality 0–100, lossless mode, and effort; TIFF none/LZW/Deflate compression when available; GIF palette size 2–256 and dithering. Hide entire unsupported form rows, including their labels. BMP has no quality slider.
5. Define transparency behavior per target: preserve full alpha for PNG/WebP/TIFF where supported; composite onto a selected background for JPEG/BMP; use an explicit transparency threshold or background for GIF. Correctly handle RGBA, LA, palette transparency, and CMYK/grayscale inputs. Describe GIF's binary transparency in the preview.
6. Default metadata handling to **Remove metadata**, with an explicit **Preserve supported metadata** option. When preserving, carry valid ICC/EXIF data only where supported, remove the EXIF orientation after transposition, and update or remove stale size fields. A mode conversion alone is not an ICC colour-space conversion; use Pillow ImageCms when profile conversion is required, and report unsupported/invalid profiles.
7. Write exports to a temporary sibling file with an explicit encoder format, close it, reopen and decode it for validation, then commit it to the final path. For overwrite-disabled jobs use a commit method that refuses existing destinations; an earlier existence check alone is insufficient. Cleanup temporary outputs on failure/cancel. Destination files must never contain half an encoding.
8. Extract Qt-independent pixel operations into `src/core/processing.py` and image effect definitions into `src/core/effects_catalog.py`. Existing editor actions should delegate to these operations; batch processing must not create an editor, undo history, or QPixmap.

Initial batch effects: resize, crop, rotate, horizontal/vertical flip, brightness, contrast, grayscale, invert, and sepia. Match existing editor results, preserve alpha where meaningful, and define resize as exact dimensions, contain-with-padding, or bounded fit without enlargement. The existing thumbnail-based resize cannot enlarge; do not reuse it as an exact-size implementation.

Verify RGB and transparent PNG-to-JPEG, JPEG-to-WebP, grayscale/palette/CMYK inputs, metadata policies, extension aliases, format/path agreement, absent codecs, and output failure cleanup. Keep Qt imports out of these services; simplify `src/core/__init__.py` if its eager re-exports prevent headless imports.

## Step 2: Add an animation document and reliable decoding

1. Add `src/core/document.py`. Represent a still image as a document with one frame, using the same save and history rules as animations.
2. Store a document ID, common canvas size, ordered frames, source format, loop policy, supported metadata, and content revision. Store each frame's stable ID, pixel reference, duration in milliseconds, and exportable artwork.
3. Keep active frame ID, frame selection, zoom, and playback position in editor/view state. Moving the active frame or changing selection is not a document modification.
4. Expose `Editor.current_image` as the active frame's image while adapting existing consumers. Switch frames by stable ID without invoking `load_image()`, resetting history, or losing edits.
5. Add `src/core/animation_io.py`. Decode GIF/WebP sequentially using Pillow's frame seeking/compositing. Copy each fully reconstructed canvas before advancing. Confirm disposal, restore-to-background, restore-to-previous, frame offsets, and WebP blending with fixtures; naive copies of stored delta rectangles will produce incorrect pictures.
6. Preserve variable frame durations and source loop intent. Treat absent loop data as play once, zero/infinite loop data as repeat indefinitely, and positive loop data through a tested adapter to a user-facing total-play-count model. Avoid displaying an encoder's ambiguous raw loop count directly.
7. For new frames use 100 ms by default. For missing/zero source duration use a documented 100 ms preview fallback and expose the normalization in import results. Keep timing decisions centralized. Do not interpret multipage TIFF pages as timed animation frames.
8. Load images in a worker with a document generation token; publish a complete successful document on the GUI thread. Failed or cancelled imports leave the current document intact. Ignore results belonging to a superseded load.
9. Estimate decoded memory from canvas dimensions and frame count before allocation. Add explicit byte budgets, initially 256 MiB decoded cache, 128 MiB undo storage, and a 1 GiB estimated import ceiling. Spill cached frames/snapshots to a managed temporary store rather than keeping unlimited full-size copies. Raise a clear resource-limit error if the ceiling or available disk is exceeded. Make limits configurable and tune them during Step 9.

Verify disposal-heavy GIFs, partial frames, transparent animations, variable timing, finite/absent/infinite loops, corrupt later frames, very large animations, cancellation, and ordinary still-image loading. Use tiny hand-checked fixtures; Pillow-generated round trips alone are insufficient to validate every decoder case.

## Step 3: Extend undo, dirty state, and edit scope

1. Replace actions that implicitly operate on `state.current_image` with document commands that capture stable target frame IDs and before/after state for affected content only.
2. Add compound commands for effects applied to multiple frames, canvas transforms, add/duplicate/delete/reorder frames, duration changes, loop changes, and artwork edits. One user operation creates one history entry, including edits applied to all frames.
3. Coalesce slider gestures only when tool, target frame set, and gesture/session match. End a gesture on frame navigation or scope changes. Reordered frames must not redirect an old command to a new frame index.
4. Use a save checkpoint based on history-state identity. Full undo is not automatically clean after an intermediate save; undo/redo must recognize the actual saved state, including history branching and eviction. If an asynchronous save finishes after later edits, only the saved snapshot becomes the checkpoint.
5. Provide **Apply to: Current frame / Selected frames / All frames**, defaulting to Current frame. Resolve target IDs at command creation. Disable Selected frames when no valid selection exists.
6. Brightness, contrast, filters, flips, freehand strokes, and artwork can use the chosen scope. Apply identical image coordinates for multi-frame drawing/artwork. Crop, resize, and quarter-turn rotation change the document canvas and therefore operate on all frames; show that rule in the controls instead of producing mismatched frame sizes.
7. Preserve at least one frame. Disable deletion of the last frame, preserve relative order when duplicating/deleting multiple frames, and select a neighboring surviving frame after deletion.
8. Separate **Reset Current Frame** from **Reset Document**. Capture a document baseline at successful load/creation and reset through undoable commands. Keep single-frame behavior understandable and route the existing reset action appropriately.
9. Perform large multi-frame effects on an immutable captured state in a worker. Publish the compound command atomically if its document/revision is still current; cancel or discard stale results. Do not partially apply a cancelled all-frame edit.

Verify navigation between edit/undo/redo; edits after frame reordering; multi-frame scope; slider gesture boundaries; deleting/undoing frames; clean state after save/undo/redo; and history-budget eviction. These checks cover behavior the current single-image implementation cannot safely provide.

## Step 4: Implement frame navigation and playback

1. Add `src/gui/animation_panel.py` and `src/gui/animation_playback.py`. Wrap the viewer and animation panel in a vertical splitter, retaining the current horizontal splitter between canvas and editing tools.
2. Show the panel for animated documents or newly created animations, including a new animation that currently has one frame. Hide it for ordinary still documents. Provide a View action to reopen a manually hidden panel.
3. Use a model-backed horizontal thumbnail strip with active frame, extended selection, frame number, and duration. Generate and cache thumbnails off the GUI thread; create QPixmaps only on the GUI thread. Provide a text/list mode for accessible inspection of large frame sets.
4. Add Previous, Next, Play/Pause, frame-position entry, duration entry, loop controls, Add/Import, Duplicate, Delete, and Move Earlier/Later. Support drag reordering and equivalent keyboard/menu actions.
5. Default Left/Right to previous/next and Space to playback when the frame strip has focus. Home/End select first/last; Shift+Left/Right extend selection. Offer remappable previous/next bindings so users can choose Up/Down. On the canvas use scoped previous/next/playback commands; retain normal scrolling when unmodified arrows are not assigned there.
6. Never intercept arrows or Space in duration fields, text inputs, combo boxes, editor tools, or Explorer. Integrate shortcut scope and conflict detection with `key_config`; window-level shortcuts must not accidentally run while a tool dialog is active.
7. Announce a focused frame as, for example, **Frame 3 of 12, 100 milliseconds, selected**. Report frame navigation and playback start/stop, without announcing every playback tick. Set accessible names, buddies, tab order, and text alternatives for icons.
8. Schedule playback from a monotonic clock with a QTimer and cumulative frame deadlines. Respect each duration; avoid adding encoding/painting latency to every interval. Stop finite loops correctly, pause on editing/navigation, and retain zoom/pan. Playback navigation does not modify content or history.
9. Stop timers on replacement/close and pause when the app is hidden to the tray. Ignore late thumbnail/playback results belonging to an old document. Do not make a new timer or reconvert every full-resolution frame for every repaint.
10. Update F6 pane navigation so the frame panel is reachable only when visible, including its first usable control. Preserve the existing floated Explorer behavior and screen-fitting rules.

Verify keyboard-only navigation, remapping to Up/Down, range selection, duration typing, Explorer arrow behavior, playback timing, hidden panel restoration, resize, high DPI, theme changes, and stale worker results after opening another image.

## Step 5: Add GIF creation and exportable text/shapes

1. Add **File > New Animation...** and a `src/gui/dialogs/new_animation_dialog.py` with canvas dimensions, transparent/background colour, initial duration, and loop choice. Create one blank RGBA frame and an unsaved animation document.
2. Add **Import Frames...** for ordered multi-file selection. Preserve selection order and offer natural filename sorting; drag/drop uses the same importer. Importing an existing GIF/WebP appends its decoded frames and durations.
3. For different input dimensions offer Fit with padding, Fill with cropping, or Stretch to the existing canvas. Fit with transparent padding is the default. Keep aspect-ratio behavior visible before applying it. Normalize EXIF orientation before sizing.
4. Duplicate pixels and exportable artwork into independent frame content. Changes to a duplicate must not change its source frame. Add/delete/reorder/timing operations reuse Step 3 commands.
5. Add an optional **Onion skin** toggle showing the previous frame faintly while paused. Treat it as a view aid, never export it, and keep it out of playback. It assists hand-drawn frame changes without requiring automated motion generation.
6. Convert artwork storage to document-owned text/shape specifications with image-space coordinates, colours, font settings, visibility, and opacity. Viewer grid/rulers/crosshair/pixel information remain separate. Offer editing existing text and shapes and apply the frame-scope control to artwork creation/changes.
7. Add `src/core/artwork.py` and a Qt raster rendering adapter using QImage/QPainter. Render offscreen at native canvas resolution for both preview and export; initialize fonts through QGuiApplication and keep QPixmap out of workers. This preserves font/layout agreement better than independently reproducing Qt text with Pillow. Headless conversion without artwork must remain Qt-independent.
8. Resolve cursor-relative/viewport-relative artwork anchors to persistent image coordinates when created. Canvas transformations must transform artwork consistently with pixels. Exports must not bake the screen's current zoom, rulers, selection handles, or onion skin.

Verify a three-frame hand-drawn animation, imported photographs with different dimensions, editing a duplicate, frame-scoped text/shape changes, opacity, transformed artwork, and exports at multiple viewer zoom levels. GIF creation is complete when the exported animation contains the intended pictures, timing, text, and shapes.

## Step 6: Export animations and integrate save behavior

1. Extend the common export service with animation encoding using Pillow `save_all`, appended frames, durations, and loop adapters. Support GIF and WebP only when their installed encoders pass capability and round-trip checks.
2. GIF: sample colours across the sequence to build a bounded shared palette, reserve a transparency index where required, and provide palette size/dithering/transparency controls. Quantize consistently to reduce colour flicker. Preview the actual decoded encoded output, not only unquantized source frames.
3. Encode reconstructed full frames with an explicit tested disposal strategy. Reopen every output frame to verify displayed composition and timing. Encoders may merge identical frames; verify visual sequence and total durations, and document merging rather than requiring identical frame counts in every optimized GIF.
4. Preserve requested WebP alpha, quality/lossless settings, variable duration, and loop intent. Keep document timing in milliseconds. Round GIF durations to its 10 ms units using cumulative rounding to minimize drift, with a practical 10 ms minimum; show effective timing in export preview.
5. Provide **Export Animation...** with GIF/WebP encoding settings, loop/timing summary, dimensions, estimated/actual output size, and preview. Provide **Export Current Frame...** and **Export Frames...** for still outputs, with padded frame-number names.
6. Animated document to JPEG/PNG/BMP/static TIFF requires an explicit choice: Current frame or Separate files for all frames. Never silently export only the first frame. Animated document to GIF/WebP preserves animation by default.
7. Add a native **Photon Animation Project** file (`.photonanim`): a versioned ZIP manifest, lossless frame pixels, timings, loop settings, and text/shape specifications. Save only document content; undo history is session-local. Load with validated archive paths, frame-count/dimension limits, and bounded decompression; do not extract arbitrary archive paths to disk.
8. **Save/Save As** saves the editable project for newly created animations or documents with editable artwork. For imported GIF/WebP, Save can update that animation when no unsupported editable state would be lost; direct users to a project save when required. **Export** writes a distribution copy without changing the document path or clearing its unsaved state. Show the active save target clearly.
9. Update still-image Save As to retain the chosen format and settings for later Save. Changing the filename extension updates format selection or requires reconciliation before writing. Save checkpoints advance only on a successful complete save.
10. Save/export uses a captured immutable document revision and a worker. Subsequent edits cannot change the file being encoded. On cancellation leave prior destinations and dirty state intact. Apply the same unsaved-document check to New, Open, Explorer opening, IPC file opening, and application exit.

Verify GIF/WebP visual/timing/loop round trips, palette transparency, duplicate-frame merging, project save/reopen with editable artwork, failed saves, cancelled Save As, edits during saving, and unsaved prompts when replacing or exiting a document.

## Step 7: Build a batch engine independent of the interface

1. Add `src/core/batch_conversion.py` with immutable source entries, conversion settings, ordered processing effects, destination settings, a resolved work plan, per-file results, and an aggregate run result.
2. Resolve files once in the worker. Preserve explicit source order; use deterministic sorting within folders. Apply image filters, normalize path case/aliases, and deduplicate resolved files even when a file is separately queued alongside its containing folder. Do not reject repeated frames in animation creation; batch deduplication is a different workflow.
3. Support recursive folders without following directory symlinks/junctions into loops. Report unreadable folders. Keep a stable source-root identity for each input. Preserve subfolders under the destination as `<selected-root-name>/<relative-path>` to match Playform's root-folder convention. Exclude the output subtree when it is inside a recursive source, and finish discovery before conversion starts.
4. Preflight empty queues, unsupported encoders, invalid effect values, destination/log writability, same-source outputs, and destination collisions. Default to skipping existing outputs unless Overwrite is selected. Never overwrite any queued source, even when Overwrite is enabled. Two queued inputs resolving to one output remain conflicts; do not let queue order determine which silently wins. Report the conflict and let users change destination structure or source selection.
5. Decode one document at a time; apply the Processing list in order and encode through the shared export service. Processing applies to all decoded animation frames and maintains a common canvas. Do not retain the entire batch's pixels or create per-file undo histories.
6. Provide **Animation handling** in Convert: Preserve animation, First frame, or Separate frames. Preserve is the default: GIF/WebP inputs remain animated for GIF/WebP outputs; for static outputs, incompatible animated files are skipped with a specific result unless First frame or Separate frames is selected. Stills always produce one still output. Separate frames writes numbered still files into a per-source folder and treats all outputs as one input result.
7. Treat multipage TIFF/APNG as excluded sequence types for this release: skip with a clear result by default; explicit First frame or Separate frames may use a tested extraction path. Never guess animation timing for document pages. A normal single-page TIFF still converts.
8. Implement a runner with plain callbacks for preparation, overall input progress, current phase/frame progress, per-file result, log events, and final aggregate result. Model results as Converted / Skipped / Failed / Cancelled, including output paths and explanatory messages.
9. Add `src/tools/image_batch_converter/job.py` as a thin QThread wrapper. Pass a cancellation token and pause event to the runner. Pause/cancel checks occur at discovery, file, frame, and effect boundaries; cancel wakes a paused job. Pillow's current codec call may finish before cancellation is observed; show **Cancelling...** truthfully and discard its temporary output before final commit.
10. Retain Playform's Destination option **Delete original files**, off by default. Delete only after every intended output for that input is committed and successfully reopened, only when outputs differ from the source, and never for skipped/failed/cancelled/partially exported inputs. A deletion failure is reported separately from a successful conversion. Capture this opt-in in the immutable run settings.
11. Preserve successful earlier outputs if later inputs fail or the batch is cancelled. Cleanup only this job's uncommitted temporary files. A log-file failure must not erase valid conversions. Generate the aggregate summary from actual results rather than a single finished boolean.

Verify duplicate sources, extension filtering, recursive paths, junctions, destination inside source, colliding basenames, case-insensitive aliases, overwrite races, locked destinations, disk-full failures, corrupted pictures, processing order, animation policies, separate-frame output failures, pause/cancel, deletion conditions, and no Qt dependency for pixel-only conversion.

## Step 8: Reproduce Playform's batch interface with image content

1. Create `src/tools/image_batch_converter/` with `ui.py`, `source_tab.py`, `convert_tab.py`, `processing_tab.py`, `destination_tab.py`, `effect_picker_dialog.py`, `job.py`, and `presets.py`. Add a small package initializer with no eager tool imports.
2. Preserve the top row **Preset: [editable name] [Save] [Delete]**, tab order **Source / Convert / Processing / Destination**, and bottom-right **Begin**. Use native Photon widgets, inherited theme styling, stretchable layouts, and screen-limited dialog sizing.
3. Source: reproduce Add Files/Add Folder, the Path/Formats tree, extended selection, context-menu Add/Remove/Clear, and Delete removal. Adapt `AddFolderDialog` to All supported image formats or Custom image format plus Include all subfolders. Remove Audio/Video scopes. Retain the visual folder hierarchy but build it asynchronously/lazily; Playform currently performs recursive enumeration in the GUI thread.
4. Convert: replace Audio/Video radio buttons and stacked media panels with one image panel. Show Format, the Step 1 format-specific controls, transparency background, metadata policy, and animation handling. Remove sample rate, audio/video bit rate, audio bit depth/VBR, video frame rate/resolution, and FFmpeg codec controls. Put image dimensions in the Resize processing effect to avoid two competing resizing settings.
5. Processing: reproduce the ordered applied-effects list and **Add Edit... / Add Filter...** buttons. Preserve categorized pickers, double-click/context-menu Edit, Remove, Move Up/Down, Clear All, and Delete removal. The picker selects an effect; a parameter dialog edits it. Replace Playform's audio-oriented effect catalog with Photon image effects. Store effect IDs and validated parameter dictionaries, not translated labels.
6. Destination: keep Original folders / Selected folder radio choices, path/Browse, Preserve subfolders, Overwrite existing files, Delete original files, Create log file, and Set Log File. Retain conditional enabled states. Use concise image-specific labels and the Step 7 source-protection/deletion rules.
7. Presets: reproduce named Save/Load/Delete for Convert and Processing, as Playform does. Do not save source paths, destination paths, deletion opt-in, or overwrite opt-in in presets. Add a versioned `UserPreset` model and database facade methods, routed through the existing write queue. Use kind `image_batch`; do not copy Playform's legacy migration or access its user database.
8. Loading a preset validates codec availability, effect IDs, and value ranges. Report missing/obsolete options and disable Begin until resolved; do not silently omit effects. Prevent programmatic widget loading from executing editor commands or launching jobs.
9. Add `src/gui_controls/job_progress_dialog.py` with Playform's overall progress, Progress/Live Log tabs, current-file detail, Pause/Resume, Cancel/Close, and When finished notification selection. Replace raw FFmpeg descriptions with image preparation/encoding events. Bound both log views to avoid unbounded memory use. During source discovery show indeterminate **Preparing...**; afterwards use the single resolved work plan's total.
10. Disable Begin and capture all settings for the run. Keep the job alive through a job manager, irrespective of tool/progress visibility. On finish show converted/skipped/failed/cancelled totals; zero failures is distinct from merely reaching the end. Use Photon's tray notification API when requested and available.
11. Reopening the tool raises its existing window. Offer Hide and reopen without losing settings/progress. Close/Escape on a running job must offer continued background work or cancellation and defer destruction until the worker finishes. Do not copy Playform's `ToolDialog.is_tool_active()` check, which checks `thread` while its batch widget stores `job`.

Verify visual tab/order parity against the reference, conditional encoding controls, keyboard context menus, filter ordering, preset persistence, invalid preset recovery, preparation progress, pause/cancel, summary counts, hidden/reopened progress, repeated runs, and unavailable tray notifications.

## Step 9: Integrate and run application-level QA

1. Add Tools > Batch Image Converter and File > New Animation / Import Frames / Export Animation / Export Current Frame / Export Frames actions. Enable them according to document type, selection, codec availability, and active job state.
2. Register all new actions with the configurable shortcut system. Account for lazily created tool dialogs in shortcut registration tests; do not weaken the existing requirement that applicable controls receive their configured bindings. Merge new defaults without resetting saved bindings.
3. Extend focus navigation, status information, window title/dirty marker, recent-file handling, Explorer thumbnails, and format filters. Explorer thumbnails use a representative first reconstructed frame; inspecting a folder must not start many full animation decodes.
4. Add a small `src/gui/managers/job_manager.py` for load/edit/export/batch ownership, cancellation, progress reopening, and final cleanup. Keep pure core services outside this manager.
5. On tray hide stop animation playback while batch conversion may continue. On application exit offer waiting or cancel-and-exit for active jobs, then close windows, finish worker cleanup, remove managed frame-store files, and close the database last. Avoid destroying a running QThread or blocking the GUI with an unbounded `wait()`.
6. Use literal translatable strings compatible with `scripts/extract_strings.py`; retain stable internal IDs. Update translation data and PO/MO generation through the current tasks. Check English, French, Spanish, and Arabic layouts, including right-to-left frame ordering/controls without changing chronological document order.
7. Add meaningful unit and integration tests in `tests/test_image_export.py`, `test_animation_io.py`, `test_document_history.py`, `test_animation_ui.py`, `test_batch_conversion.py`, and `test_batch_converter_ui.py`. Reuse unittest, QTest/QSignalSpy, offscreen Qt, and temporary databases/files. Do not require new test frameworks.
8. Run the existing startup and regression suites alongside the new tests. For real rendering/accessibility behavior also run manual desktop checks; offscreen tests do not validate screen-reader announcements or installed-window behavior.
9. Measure 100-frame 512×512 and 1920×1080 imports/playback, a 1,000-small-file batch, cancellation during long discovery/encoding, and a file near the configured memory ceiling. Record RAM/cache/disk use and UI responsiveness; tune budgets before release. Use throttled progress and bounded thumbnail/undo caches rather than adding uncontrolled worker concurrency.

Suggested development verification command from the repository root:

```powershell
& .\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Step 10: Package, document, and release

1. Build with the existing Nuitka script and installer workflows. Verify Pillow plugins/native codecs, ImageCms where needed, Qt offscreen/font rendering, and new modules are included. Do not add FFmpeg discovery/download/bundling to Photon.
2. Test installed Windows and macOS builds, including Unicode/space-containing paths, protected/read-only folders, source files open in other programs, tray behavior, and packaged GIF/WebP encoding. The source virtual environment's successful codecs do not establish installed-build support.
3. Add user how-to guides for editing an animation, creating a GIF from pictures, exporting GIF/WebP, and converting a folder. Add a compact reference for supported formats, timing/transparency limits, shortcuts, and batch result meanings. Update the main README with links and screenshots after the UI exists.
4. Preserve the application's license/provenance correctly. The inspected Playform metadata declares GPL-3.0 and Photon declares MIT. Reproduce the observed layout and interactions using Photon code; any direct source transplant needs appropriate reuse rights or license handling before distribution. This plan does not change either project's license.
5. Run the complete acceptance list below in an installed build, resolve failures, record platform/codec limitations, update app version and release notes, and create distributable artifacts. Publishing a release is a separate action when requested.

## Completion checklist

- [ ] Ordinary still-image editing, Save/Save As, undo/redo, Explorer, startup, and tray behavior continue working.
- [ ] A disposal-heavy GIF opens correctly; editing a middle frame, navigating away/back, and undo/redo preserves all frames.
- [ ] Variable timing and play-once/finite/infinite loops survive GIF/WebP export within documented format rounding.
- [ ] Previous/next is remappable to Up/Down; arrows in Explorer and numeric/text fields retain their normal behavior.
- [ ] Current/selected/all-frame edits have explicit scope and one undo step; canvas-changing edits keep frames aligned.
- [ ] Imported pictures and duplicated blank/drawn frames create a playable GIF with ordered frames, text, shapes, and correct timing.
- [ ] Export excludes grid/rulers/onion skin and reproduces artwork at native resolution independently of zoom.
- [ ] `.photonanim` save/reopen preserves editable frames, timings, loops, and artwork; failed/cancelled saves preserve dirty state.
- [ ] Animation-to-still output requires an explicit frame choice; batch defaults never discard animation silently.
- [ ] The batch interface matches Playform's preset row, four tabs, applied-effects workflow, Begin button, and progress layout with media-specific fields removed.
- [ ] Files/folders, recursion, filters, ordered effects, supported format settings, destinations, and presets work together.
- [ ] Existing-output skips, source/output collisions, permission failures, corrupt inputs, and codec absence produce accurate results.
- [ ] Pause/resume/cancel, hiding/reopening progress, closing the tool, and app exit do not leak workers or partial output files.
- [ ] Delete originals is opt-in and happens only after the complete output for that input has been verified.
- [ ] Keyboard, screen-reader, theme, high-DPI, translation, and large-input checks pass.
- [ ] Installed builds pass GIF/WebP and batch conversion smoke tests and ship the required codecs.
- [ ] User documentation, release notes, provenance, and packaging checks are complete.

## Proposed file changes

| Area | New files | Existing files to adapt |
| --- | --- | --- |
| Shared image services | `core/formats.py`, `export.py`, `processing.py`, `effects_catalog.py` | `core/image.py`, `utils.py`, `__init__.py` |
| Animation content | `core/document.py`, `animation_io.py`, `artwork.py`, `frame_store.py`, `history.py` | `core/editor.py`, `actions.py`, `overlays.py` |
| Animation interface | `gui/animation_panel.py`, `animation_playback.py`, `artwork_renderer.py`; new-animation, import-frames, export dialogs | `gui/main_window.py`, `viewer.py`, `editor_panel.py`, `overlay_panel.py` |
| Batch conversion | `core/batch_conversion.py`; `tools/image_batch_converter/` modules from Step 8 | `core/utils.py` compatibility helpers |
| Shared interface/lifecycle | `gui_controls/path_tree_widget.py`, `job_progress_dialog.py`; `gui/managers/job_manager.py` | dock/focus managers, `taskbar_icon.py`, app exit handling |
| Persistence and integration | UserPreset facade/model additions; versioned project serializer in animation I/O | `app_db/models.py`, `database.py`, `app_config/prefs.py`, `key_config.py`, `app_constance/default_keys.py` |
| Verification and delivery | New tests/fixtures, user guides, screenshots | existing regression tests, language sources/scripts, `build.py`, release workflow, README |

All paths in this table are relative to `src/` unless identified as tests, documentation, or build files. Names are proposed module boundaries; small components may be combined if separation would add needless complexity, but shared export logic and the Qt-independent batch runner must remain reusable.
