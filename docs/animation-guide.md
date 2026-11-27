# Edit an animation or create a GIF

Open a GIF, animated WebP, or Photon Animation Project with **File → Open**. The animation panel shows frames in chronological order and their durations. Click a frame to edit it. Use **Previous**, **Next**, or the position field to move between frames. Moving between frames does not add an undo step.

Choose **Apply to → Current frame**, **Selected frames**, or **All frames** before applying brightness, contrast, filters, drawing, text, or shapes. Select multiple frames with Ctrl/Shift in the strip. Crop, resize and rotation change the canvas and therefore apply to all frames.

Use **Play** to preview the individual frame durations. **Total plays** counts complete plays; 1 plays once and 0 repeats indefinitely. **Onion skin** displays the previous frame faintly while paused. Grid, rulers, pixel information and onion skin are editing aids and are excluded from exports.

## Create an animation from pictures

1. Choose **File → New → New Animation** and set canvas dimensions, background, duration and total plays.
2. Choose **Import Frames** and select pictures. Use natural filename sorting when names contain sequence numbers. Fit with transparent padding preserves the whole picture; Fill crops the edges; Stretch changes its aspect ratio.
3. Right-click the frame strip to remove the initial blank frame if it is unnecessary. At least one frame must remain.
4. Set individual durations and reorder with the context menu's **Move Earlier/Later** or drag the frames.
5. Use **Duplicate** in the frame context menu, enable drawing, and change the duplicates to create motion. Duplicates have independent pixels and editable artwork.
6. Use **Edit → Edit Text and Shapes** to update artwork coordinates, colour, opacity or visibility. Text placed with Click to Place becomes anchored to image pixels.
7. Choose **File → Save As** to save an editable `.photonanim` project.
8. Choose **File → Export Animation**, select GIF or WebP, inspect **Preview Encoded Output**, then choose an output filename.

GIF stores binary transparency and rounds timing to 10 ms. Adjust its palette, dithering and transparency threshold in the export settings. WebP supports partial transparency and lossless encoding. Identical frames may merge during encoding while their total duration is retained.

**Save** updates the active document target. A new animation, animation Save As, or a document containing editable artwork uses a Photon project. An imported GIF/WebP without editable artwork can be saved directly to its animation format. **Export** writes a distribution copy and leaves the document's save path and dirty state unchanged. **Export Current Frame** explicitly writes a still; **Export Frames** creates padded numbered files and refuses to overwrite existing names.

## Keyboard controls

With the frame strip or canvas focused, Left/Right select the previous/next frame and Space plays or pauses. Home/End select the first/last frame in the strip. Shift selection, Ctrl+D duplication, Delete, and Alt+Left/Right ordering are available in the strip. F6 includes the animation panel when visible. Configure these in **Options → Hotkeys**, including remapping previous/next to Up/Down. Numeric fields, text inputs and Explorer keep their normal keys.

Use **View → Animation Panel** to reopen a hidden strip. Playback pauses before edits, on replacement and when hidden to the tray.
