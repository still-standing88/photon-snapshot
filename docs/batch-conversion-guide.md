# Convert files or a folder

Open **Tools → Batch Image Converter** (Ctrl+B). The tool retains settings when hidden and reopens the same window.

1. In **Source**, right-click the list and choose **Add Files** or **Add Folder**. Shift+F10 opens the same menu from the keyboard. Folder options select all supported formats or one format and optionally include subfolders. Discovery happens when Begin is pressed. Overlapping file/folder entries are deduplicated.
2. In **Convert**, select the output format and its encoding controls. Metadata is removed by default. Select Preserve supported metadata only when required. JPEG/BMP use the selected opaque background; GIF uses a transparency threshold or background.
3. Choose **Animation handling**. Preserve is the default. GIF/WebP animations remain animated when the output supports animation. Animated inputs targeting static formats are skipped unless First frame or Separate frames is selected. Explicit frame extraction also supports APNG/multipage TIFF with a common canvas; these sequences are not treated as timed animations.
4. In **Processing**, use the list's context menu to add edits or filters and edit their parameters. Effects run from top to bottom on every frame. Use Move Up/Down to change their order. Selection-dependent actions are disabled when unavailable. Resize supports exact dimensions, contain with padding, and fit without enlargement.
5. In **Destination**, choose original folders or an existing selected folder. Preserve subfolders uses `<selected-source-root-name>/<relative-subfolder>`. Overwrite and deletion are opt-in. Queued sources are protected even when overwrite is enabled. Two sources resolving to one output produce conflicts.
6. Enter a name in **Preset**, then right-click that field and choose **Save Preset** if these Convert/Processing settings will be reused. The same menu offers **Delete Preset** for an existing preset. Presets exclude source paths, destination paths, overwrite and original-deletion choices. Invalid presets must be corrected before Begin is available.
7. Press **Begin**. The progress window shows preparation, per-file activity, bounded Progress/Live Log views, and optional tray notification. Pause takes effect at processing boundaries. Cancel may wait for the current Pillow encoder to return, then discards its uncommitted temporary output.

Use the tool background's context menu to hide it or show progress without interrupting conversion. Reopen it from Tools. Closing an active tool offers background continuation or cancellation. Application exit waits or cancels jobs before cleanup.

## Result meanings

| Result | Meaning |
| --- | --- |
| Converted | The intended outputs were written and decoded successfully. An original-deletion error is reported separately. |
| Skipped | No conversion was performed, for example an existing destination, source collision, excluded sequence, or incompatible animation policy. |
| Failed | Decoding, processing, writing or verification failed. |
| Cancelled | Processing was cancelled or the input had not started when cancellation occurred. |

Completed earlier outputs remain available if another input fails or a job is cancelled. For separate frames, any frames already committed remain available; originals are deleted only when every intended output succeeds. Temporary files are always cleaned up.
