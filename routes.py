from pathlib import Path

from aiohttp import web

from server import PromptServer


routes = PromptServer.instance.routes


@routes.get("/vfx-seq2video/video")
async def video(request):
    raw_path = request.query.get("path", "").strip()

    if not raw_path:
        raise web.HTTPBadRequest(text="Missing 'path' query parameter.")

    source = Path(raw_path)

    if not source.is_file():
        raise web.HTTPNotFound(text=f"File does not exist:\n{source}")

    # FileResponse supports HTTP Range requests, which <video> needs for
    # seeking/scrubbing.
    return web.FileResponse(source)
