# ComfyUI VFX Seq2Video

Encodes an image batch (e.g. `Read`'s `sequence` output) into an `.mp4`,
for downstream nodes that only accept `VIDEO`.

## Inputs

| Input | Type | Description |
|---|---|---|
| `images` | IMAGE | The batch to encode. |
| `sequence_folder` | STRING | Where the source frames live — wire this straight from `Read`'s `sequence_folder` output, or type a path. |
| `frame_rate` | FLOAT | Default `24.0`. |
| `bitrate_kbps` | INT | Default `8000`. |

## Output path

The `.mp4` is written one level **above** `sequence_folder`, named after
that folder — e.g. frames in `.../shotA/v01/*.png` produce
`.../shotA/v01.mp4`. It's overwritten on every run: this is a derived
proxy of whatever frames currently exist, not a versioned deliverable.

## Outputs

| Output | Type | Description |
|---|---|---|
| `video` | VIDEO | Populated when ComfyUI's `VideoFromFile` is available. |
| `path` | STRING | The written `.mp4`'s absolute path. |

## Installation

From the ComfyUI root:

```bat
call venv\Scripts\activate.bat
python -m pip install -r custom_nodes\ComfyUI-VFX-Seq2Video\requirements.txt
```

Restart ComfyUI. Add **Image Sequence to Video** from the **VFX / IO**
category. Requires `ffmpeg` on your `PATH`.
