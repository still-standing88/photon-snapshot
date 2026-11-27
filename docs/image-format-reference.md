# Image formats and resource limits

| Format | Output controls | Transparency | Animation |
| --- | --- | --- | --- |
| JPEG (`.jpg`, `.jpeg`) | Quality 1–95, optimize | Composited onto chosen background | No |
| PNG | Compression 0–9 | Full alpha | APNG editing excluded; explicit extraction available in batch |
| BMP | No quality control | Composited onto chosen background | No |
| TIFF (`.tif`, `.tiff`) | None/LZW/Deflate | Alpha where supported | Pages require explicit extraction |
| GIF | Palette 2–256, dithering, threshold/background | Binary alpha | Yes; 10 ms timing units |
| WebP | Quality 0–100, lossless, effort 0–6 | Full alpha | Yes |
| Photon Animation Project | Versioned ZIP manifest and lossless PNG frames | Full alpha | Editable frames, timings, loops and artwork |

Formats and animation encoding are checked against installed Pillow codecs at runtime. No FFmpeg is required.

Default decoded pixel cache: 256 MiB. Default undo-only pixel budget: 128 MiB, with at most 50 history entries. Estimated decoded import ceiling: 1 GiB, with at most 10,000 frames and 32,768 pixels per dimension for projects. Cached pixels spill into managed temporary PNG files. Source/import limits can be configured through the core service parameters/constants. Undo history is local to a session and is excluded from project files.

Images are decoded sequentially to reconstruct animation disposal and blend operations. Missing/zero animation durations normalize to 100 ms. Total plays is the user-facing model: 0 means infinite, 1 means once. Unsupported codecs and invalid colour profiles are reported. Supported preserved ICC/EXIF data is normalized for output, and stale orientation/size tags are removed.

Exports encode to a temporary sibling, decode every output frame for verification, and commit atomically. No-overwrite commits refuse existing destinations at commit time.
