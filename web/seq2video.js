import { app } from "/scripts/app.js";

// ---------------------------------------------------------------------------
// Image Sequence to Video — preview widget.
//
// This is the same real embedded <video controls loop> element as
// ComfyUI-VFX-Write's write_stage1.js (VIDEO_WIDGET there), stripped down
// to just that: this node only ever produces a video, so there's no
// image/video mode-switch to manage, no fullscreen button, no path-pattern
// browsing — just one DOM widget that shows whatever was last encoded.
//
// computeSize() is a genuine constant (PREVIEW_MIN_H) — never derived from
// node.size — for the same reason documented at the top of write_stage1.js:
// a live-derived computeSize() becomes self-referential during a resize
// drag (LiteGraph checks the new size against computeSize()'s report, but
// that report was itself just computed FROM the old size), which blocks
// shrinking. The container/video element are plain width:100%/height:100%
// and are NOT synced from any per-frame draw() call — confirmed live this
// session (via ComfyUI-VFX-Write's identical video widget) that the
// Vue-based ComfyUI frontend's own DOM-widget wrapper already tracks live
// node resize on its own, independent of computeSize()'s returned value.
// ---------------------------------------------------------------------------

const NODE_TYPE = "VFXSeq2Video";
const VIDEO_WIDGET = "$$vfx-seq2video-video";
const PREVIEW_MIN_H = 120;
const PREVIEW_DEFAULT_H = 240;

function el(tag, style, props) {
  const node = document.createElement(tag);
  if (style) Object.assign(node.style, style);
  if (props) Object.assign(node, props);
  return node;
}

function videoUrl(sourcePath) {
  const url = new URL("/vfx-seq2video/video", window.location.origin);
  url.searchParams.set("path", sourcePath || "");
  return url.toString();
}

function buildVideoWidget(node) {
  const container = el("div", {
    width: "100%",
    height: "100%",
    background: "#000",
    borderRadius: "4px",
    overflow: "hidden",
  });

  const videoEl = document.createElement("video");
  videoEl.controls = true;
  videoEl.loop = true;
  videoEl.playsInline = true;
  Object.assign(videoEl.style, {
    width: "100%",
    height: "100%",
    display: "block",
    objectFit: "contain",
    background: "#000",
  });

  container.appendChild(videoEl);

  const widget = node.addDOMWidget(VIDEO_WIDGET, "video", container, {
    serialize: false,
  });
  widget.computeSize = (width) => [width, PREVIEW_MIN_H];

  node.__vfxSeq2VideoEl = videoEl;
  return widget;
}

function showResult(node, path) {
  const v = node.__vfxSeq2VideoEl;
  if (!v || !path) return;
  node.__vfxSeq2VideoLastPath = path;
  v.src = videoUrl(path);
  v.load();
}

app.registerExtension({
  name: "vfx.seq2video.stage1",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;

    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);

      buildVideoWidget(this);

      // Same initial-fit trick as ComfyUI-VFX-Write: LiteGraph's
      // node-creation default size does not consult a custom widget's own
      // computeSize(), so without this a fresh node stays at the generic
      // default, well short of a usable preview area. this.computeSize()
      // here is safe because the video widget's own computeSize() is
      // still the fixed PREVIEW_MIN_H constant at this point — nothing
      // has touched this.size yet.
      const chrome = this.computeSize()[1] - PREVIEW_MIN_H;
      this.setSize([this.size[0], chrome + PREVIEW_DEFAULT_H]);

      return result;
    };

    const onExecuted = nodeType.prototype.onExecuted;

    nodeType.prototype.onExecuted = function (message) {
      const result = onExecuted?.apply(this, arguments);

      const entries = message?.vfx_seq2video;
      if (entries && entries.length) {
        showResult(this, entries[0].path);
      }

      return result;
    };

    const onRemoved = nodeType.prototype.onRemoved;

    nodeType.prototype.onRemoved = function () {
      if (this.__vfxSeq2VideoEl) {
        this.__vfxSeq2VideoEl.pause();
      }
      return onRemoved?.apply(this, arguments);
    };

    // The result (last-encoded video) previously had no persistence at
    // all — it showed after a run but vanished on reload, since nothing
    // wrote it into the saved workflow or restored it. Same name-keyed
    // pattern as ComfyUI-VFX-Read/Write's own value persistence.
    const onSerialize = nodeType.prototype.onSerialize;

    nodeType.prototype.onSerialize = function (o) {
      const r = onSerialize?.apply(this, arguments);
      o.vfx_seq2video_path = this.__vfxSeq2VideoLastPath || null;
      return r;
    };

    const onConfigure = nodeType.prototype.onConfigure;

    nodeType.prototype.onConfigure = function (o) {
      const r = onConfigure?.apply(this, arguments);
      const path = o?.vfx_seq2video_path;
      if (path) showResult(this, path);
      return r;
    };
  },
});
