import subprocess
import tempfile
from pathlib import Path

import imageio.v3 as iio
import numpy as np
import torch

# ---------------------------------------------------------------------------
# VideoFromFile import — same multi-candidate approach as ComfyUI-VFX-Read
# and ComfyUI-VFX-Write (kept as a separate copy rather than a shared
# import; these are independent installed packages under custom_nodes/,
# not a shared library).
# ---------------------------------------------------------------------------
VideoFromFile = None
_VIDEO_IMPORT_ERROR = None
_VIDEO_IMPORT_PATH = None

_VIDEO_IMPORT_CANDIDATES = (
    ("comfy_api.input_impl.video_types", "VideoFromFile"),
    ("comfy_api.latest._input_impl.video_types", "VideoFromFile"),
    ("comfy_api.input_impl", "VideoFromFile"),
    ("comfy_api.latest._input_impl", "VideoFromFile"),
)

_video_import_attempts = []

for _module_name, _class_name in _VIDEO_IMPORT_CANDIDATES:
    try:
        _module = __import__(_module_name, fromlist=[_class_name])
        VideoFromFile = getattr(_module, _class_name)
        _VIDEO_IMPORT_PATH = f"{_module_name}.{_class_name}"
        break
    except Exception as _error:
        _video_import_attempts.append(f"  {_module_name}: {_error}")

if VideoFromFile is None:
    _VIDEO_IMPORT_ERROR = (
        "VFXSeq2Video could not import VideoFromFile. The 'video' output "
        "will not work until this is fixed.\n"
        "Attempted:\n" + "\n".join(_video_import_attempts)
    )
    print(f"[VFXSeq2Video] WARNING: {_VIDEO_IMPORT_ERROR}")
else:
    print(f"[VFXSeq2Video] VideoFromFile imported from {_VIDEO_IMPORT_PATH}")


# ---------------------------------------------------------------------------
# encoding
# ---------------------------------------------------------------------------

def _from_comfy_image(tensor):
    pixels = tensor.detach().cpu().numpy()
    pixels = np.clip(pixels, 0.0, 1.0)
    return (pixels * 255).astype(np.uint8)


def resolve_output_path(sequence_folder):
    """The .mp4 is placed one level up from the sequence's own folder,
    named after that folder — e.g. frames in .../shotA/v01/*.png produce
    .../shotA/v01.mp4. Deterministic and overwritten on every run (unlike
    Write's versioned outputs): this file is a derived proxy of whatever
    frames currently exist at that path, not a primary deliverable, so
    regenerating it in place when the source frames change is the
    expected behavior, not a hazard.
    """
    folder = Path(sequence_folder.strip().strip('"')).expanduser()

    if not folder.is_dir():
        raise ValueError(f"Sequence folder does not exist:\n{folder}")

    return folder.parent / f"{folder.name}.mp4"


def encode_video(images, output_path, frame_rate, bitrate_kbps):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame_count = images.shape[0]
    digits = max(6, len(str(frame_count)))

    with tempfile.TemporaryDirectory(prefix="vfx_seq2video_") as tmpdir:
        tmp_path = Path(tmpdir)

        for index in range(frame_count):
            array = _from_comfy_image(images[index])

            # Write RGB only — same as Write's _write_image, and libx264
            # (yuv420p below) cannot hold alpha either way.
            if array.ndim == 3 and array.shape[-1] == 4:
                array = array[..., :3]

            iio.imwrite(tmp_path / f"{index:0{digits}d}.png", array)

        command = [
            "ffmpeg", "-y",
            "-framerate", str(frame_rate),
            "-i", str(tmp_path / f"%0{digits}d.png"),
            "-c:v", "libx264",
            # libx264 + yuv420p requires even width/height; an odd source
            # (e.g. 1895x806) otherwise fails with "width not divisible by
            # 2". Pads rather than crops, so no source content is lost —
            # at most a 1px black edge on the right/bottom.
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0:black",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{int(bitrate_kbps)}k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        result = subprocess.run(command, capture_output=True, check=False)

        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"FFmpeg could not encode video:\n{output_path}\n\n{detail}"
            )

    return output_path


class VFXSeq2Video:
    CATEGORY = "VFX / IO"
    DESCRIPTION = (
        "Encodes an image sequence (e.g. Read's 'sequence' output) into an "
        ".mp4, for downstream nodes that only accept VIDEO."
    )

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "path")

    FUNCTION = "convert"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "sequence_folder": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": r"F:\shots\shotA\v01",
                    },
                ),
                "frame_rate": (
                    "FLOAT",
                    {"default": 24.0, "min": 1.0, "max": 240.0, "step": 0.001},
                ),
                "bitrate_kbps": (
                    "INT",
                    {"default": 8000, "min": 500, "max": 100000, "step": 100},
                ),
            }
        }

    def convert(self, images, sequence_folder, frame_rate, bitrate_kbps):
        if images is None or images.shape[0] == 0:
            raise ValueError("No images to encode.")

        if not sequence_folder or not sequence_folder.strip():
            raise ValueError(
                "sequence_folder is empty — connect Read's "
                "'sequence_folder' output, or type a folder path."
            )

        output_path = resolve_output_path(sequence_folder)
        encode_video(images, output_path, frame_rate, bitrate_kbps)

        if VideoFromFile is None:
            raise RuntimeError(_VIDEO_IMPORT_ERROR)

        video = VideoFromFile(str(output_path))

        return {
            "ui": {"vfx_seq2video": [{"path": str(output_path)}]},
            "result": (video, str(output_path)),
        }


NODE_CLASS_MAPPINGS = {
    "VFXSeq2Video": VFXSeq2Video,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VFXSeq2Video": "Image Sequence to Video",
}
