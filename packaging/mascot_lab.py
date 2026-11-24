"""Mascot design lab: local and hosted models that draw design references of the mascot Kiri.

    python packaging/mascot_lab.py setup                    # the lab, outside the repository: its own Python, packages, models
    python packaging/mascot_lab.py angle back -o back.png   # hosted: another camera angle (Qwen-Image-Edit-2511, Multiple-Angles LoRA)
    python packaging/mascot_lab.py edit "PROMPT" -o x.png   # hosted: an expression or outfit edit of the same character
    python packaging/mascot_lab.py trellis -o kiri.glb      # hosted: a textured 3D model from the turnaround (TRELLIS)
    python packaging/mascot_lab.py sketch "PROMPT" -o x.png # local: loose variations on the Intel GPU (LCM Dreamshaper v7, OpenVINO)
    python packaging/mascot_lab.py mesh -o kiri_local.glb   # local: a rough 3D shape on the CPU (TripoSR)
    python packaging/mascot_lab.py views kiri.glb           # pictures of a 3D model from the front, side, back and above

The lab lives in ``~/.cache/stream2clip/mascot`` (``STREAM2CLIP_MASCOT_LAB`` names another folder): a Python 3.13
virtual environment, the Hugging Face cache with the two local models, and TripoSR's code. Commands other than
``setup`` run there by themselves. Every picture or model they write is recorded with its tool, model, licence,
input, prompt and seed in ``assets/brand/mascot/design/manifest.json``, so a reference can be made again.

Hosted models run on Hugging Face Spaces (ZeroGPU) with the Hugging Face login of this PC, if there is one
(``huggingface-cli login``); a free account has a small daily GPU allowance. The input pictures are the mascot's
own files, which are public in this repository already. Hunyuan3D-2 is not used: its licence excludes South Korea.
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASCOT = ROOT / "assets" / "brand" / "mascot"
DESIGN = MASCOT / "design"
MANIFEST = DESIGN / "manifest.json"
REFERENCE = MASCOT / "source" / "reference" / "kiri_wink_green.png"

#: Local models, pinned to one revision each (the bytes cannot change under the same name).
LOCAL_MODELS = {
    "sketch": {"repo": "rupeshs/LCM-dreamshaper-v7-openvino", "revision": "d12d3648e9a75210ce33974521d597336ab28f9c",
               "ignore": ["sample.png"], "licence": "CreativeML OpenRAIL-M", "size_gb": 4.3},
    "mesh": {"repo": "stabilityai/TripoSR", "revision": "5b521936b01fbe1890f6f9baed0254ab6351c04a",
             "allow": ["config.yaml", "model.ckpt"], "licence": "MIT", "size_gb": 1.7},
}
TRIPOSR_CODE = ("https://github.com/VAST-AI-Research/TripoSR", "107cefdc244c39106fa830359024f6a2f1c78871")  # MIT
REMBG_MODEL = "isnet-anime"  # background removal for an opaque picture before TripoSR (176 MB, fetched by rembg on first use)
#: The lab's packages. torch comes from PyTorch's CPU index; TripoSR's marching cubes come from scikit-image
#: (its own torchmcubes needs a C++ compiler on Windows).
PACKAGES = ["optimum-intel[openvino]", "diffusers", "transformers", "accelerate", "huggingface_hub", "gradio_client",
            "omegaconf", "einops", "trimesh", "scikit-image", "pillow", "numpy", "websockets", "rembg", "onnxruntime"]

#: Hosted models. The edit Space runs Qwen-Image-Edit-2511 (Apache-2.0) with a LoRA per call.
EDIT_SPACE = "prithivMLmods/Qwen-Image-Edit-2511-LoRAs-Fast"
EDIT_MODEL = "Qwen-Image-Edit-2511 (Rapid-AIO, 4 steps)"
ANGLE_LORA = ("Fal-Multiple-Angles", "fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA (Apache-2.0)")
EDIT_LORA = ("Anime-V2", "prithivMLmods/Qwen-Image-Edit-2511-Anime")
TRELLIS_SPACE = "trellis-community/TRELLIS"  # microsoft/TRELLIS-image-large, MIT
#: Camera positions of the Multiple-Angles LoRA (azimuth names of its prompt format).
ANGLES = {
    "front": "front view", "front-right": "front-right quarter view", "right": "right side view", "back-right": "back-right quarter view",
    "back": "back view", "back-left": "back-left quarter view", "left": "left side view", "front-left": "front-left quarter view",
}
#: three.js for the pictures of a 3D model (a headless browser draws them).
THREE = "https://cdn.jsdelivr.net/npm/three@0.170.0"


def lab_dir() -> Path:
    return Path(os.environ.get("STREAM2CLIP_MASCOT_LAB") or Path.home() / ".cache" / "stream2clip" / "mascot")


def lab_python() -> Path:
    return lab_dir() / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def in_lab() -> bool:
    return Path(sys.prefix).resolve() == (lab_dir() / ".venv").resolve()


# --------------------------------------------------------------------------------------------- setup


def setup(python: str | None = None) -> None:
    """Create the lab: a virtual environment, its packages, TripoSR's code at one commit, the two local models."""
    lab = lab_dir()
    lab.mkdir(parents=True, exist_ok=True)
    if not lab_python().exists():
        base = python or (["py", "-3.13"] if os.name == "nt" and shutil.which("py") else [sys.executable])
        subprocess.run([*(base if isinstance(base, list) else [base]), "-m", "venv", str(lab / ".venv")], check=True)
    py = str(lab_python())
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([py, "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    subprocess.run([py, "-m", "pip", "install", *PACKAGES], check=True)
    code = lab / "TripoSR"
    if not code.exists():
        subprocess.run(["git", "clone", "--quiet", TRIPOSR_CODE[0], str(code)], check=True)
    subprocess.run(["git", "-C", str(code), "checkout", "--quiet", TRIPOSR_CODE[1]], check=True)
    fetch = ("import json, sys\nfrom huggingface_hub import snapshot_download\n"
             "for m in json.loads(sys.argv[1]).values():\n"
             "    print(snapshot_download(m['repo'], revision=m['revision'], allow_patterns=m.get('allow'), ignore_patterns=m.get('ignore')))\n")
    total = sum(m["size_gb"] for m in LOCAL_MODELS.values())
    print(f"models: {total:.1f} GB from Hugging Face ({', '.join(m['repo'] for m in LOCAL_MODELS.values())})", flush=True)
    subprocess.run([py, "-I", "-c", fetch, json.dumps(LOCAL_MODELS)], check=True, env={**os.environ, "HF_HUB_CACHE": str(lab / "hf" / "hub")})
    print(f"lab ready: {lab}")


def local_model(name: str) -> Path:
    from huggingface_hub import snapshot_download

    model = LOCAL_MODELS[name]
    return Path(snapshot_download(model["repo"], revision=model["revision"], allow_patterns=model.get("allow"),
                                  ignore_patterns=model.get("ignore"), local_files_only=True))


# --------------------------------------------------------------------------------------------- the record


def record(output: Path, **facts) -> None:
    """Note how ``output`` was made in the design manifest (one entry per file, the newest kept)."""
    DESIGN.mkdir(parents=True, exist_ok=True)
    data = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"character": "kiri", "files": {}}
    try:
        key = output.resolve().relative_to(DESIGN.resolve()).as_posix()
    except ValueError:
        key = output.name
    data["files"][key] = {k: v for k, v in {**facts, "made": _dt.date.today().isoformat()}.items() if v not in (None, [], "")}
    data["files"] = {name: entry for name, entry in sorted(data["files"].items()) if (DESIGN / name).exists() or name == key}  # removed files leave
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


# --------------------------------------------------------------------------------------------- hosted models


def _client(space: str):
    from gradio_client import Client
    from huggingface_hub import get_token

    return Client(space, token=get_token(), verbose=False, httpx_kwargs={"timeout": 600})


def _data_url(path: Path, size: int = 768) -> str:
    from PIL import Image

    image = Image.open(path)
    if image.mode in ("RGBA", "LA"):  # a transparent picture goes onto the green the mascot's sources use
        back = Image.new("RGB", image.size, (0, 255, 0))
        back.paste(image, mask=image.getchannel("A"))
        image = back
    image = image.convert("RGB")
    image.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def hosted_edit(inputs: list[Path], prompt: str, output: Path, *, lora: tuple[str, str], seed: int, steps: int = 4) -> Path:
    """One edit on the hosted Qwen-Image-Edit-2511 with ``lora``; the result is written to ``output``."""
    started = time.time()
    answer = _client(EDIT_SPACE).predict(json.dumps([_data_url(p) for p in inputs]), prompt, lora[0], seed, False, 1.0, steps, api_name="/edit_image")
    if answer.get("status") != "success":
        raise RuntimeError(f"{EDIT_SPACE}: {answer.get('message') or answer.get('status')}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(answer["image"].split(",", 1)[1]))
    record(output, tool=f"Hugging Face Space {EDIT_SPACE}", model=EDIT_MODEL, licence="Apache-2.0", lora=lora[1],
           input=[_shown(p) for p in inputs], prompt=prompt, seed=seed, steps=steps)
    print(f"{_shown(output)}  ({time.time() - started:.0f} s)")
    return output


def hosted_3d(inputs: list[Path], output: Path, *, seed: int = 7) -> Path:
    """A textured GLB from one or more views on the hosted TRELLIS (several views: its multi-image mode)."""
    from gradio_client import handle_file

    started = time.time()
    client = _client(TRELLIS_SPACE)
    client.predict(api_name="/start_session")
    uploads = []
    for path in inputs:  # no green screen for TRELLIS to model; other backgrounds it removes itself
        if not _green_screen(path):
            uploads.append(path)
            continue
        upload = lab_dir() / "tmp" / f"{path.stem}_cut.png"
        upload.parent.mkdir(parents=True, exist_ok=True)
        cutout(path).save(upload)
        uploads.append(upload)
    files = [handle_file(str(p)) for p in uploads]
    _video, _preview, glb = client.predict(files[0], [{"image": f, "caption": None} for f in files] if len(files) > 1 else [], seed,
                                           7.5, 12, 3.0, 12, "stochastic", 0.95, 1024, api_name="/generate_and_extract_glb")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(glb, output)
    record(output, tool=f"Hugging Face Space {TRELLIS_SPACE}", model="microsoft/TRELLIS-image-large", licence="MIT",
           input=[_shown(p) for p in inputs], seed=seed, settings="ss 7.5/12, slat 3.0/12, stochastic, simplify 0.95, texture 1024")
    print(f"{_shown(output)}  ({time.time() - started:.0f} s)")
    return output


# --------------------------------------------------------------------------------------------- local models


def local_sketch(prompt: str, output: Path, *, image: Path | None, strength: float, seed: int, steps: int = 6, device: str = "GPU") -> Path:
    """A loose variation on the Intel GPU (or the CPU): LCM Dreamshaper v7 in OpenVINO, from a picture or from text."""
    import torch
    import transformers
    from optimum.intel import OVLatentConsistencyModelImg2ImgPipeline, OVLatentConsistencyModelPipeline
    from PIL import Image

    started = time.time()
    folder = local_model("sketch")
    # The model's index names CLIPFeatureExtractor, which transformers 5 no longer has: the processor is handed over.
    parts = {"feature_extractor": transformers.CLIPImageProcessor.from_pretrained(folder / "feature_extractor"),
             "ov_config": {"CACHE_DIR": str(lab_dir() / "ov-cache")}}  # the GPU build of the model is kept: later runs start at once
    generator = torch.Generator().manual_seed(seed)
    output, image = output.resolve(), image.resolve() if image is not None else None
    work = lab_dir() / "tmp"
    work.mkdir(parents=True, exist_ok=True)
    os.chdir(work)  # the Intel graphics compiler leaves a kernel.errors.txt where it runs: in the lab, not the repository
    pipe_class = OVLatentConsistencyModelImg2ImgPipeline if image is not None else OVLatentConsistencyModelPipeline
    pipe = pipe_class.from_pretrained(folder, device=device, compile=True, **parts)
    if getattr(pipe.unet.config, "time_cond_proj_dim", None) is None:
        # This export takes no guidance embedding (the UNet has no timestep_cond input), but the LCM pipeline
        # always makes one: it is dropped, and the UNet runs as it was exported.
        class _Dropped:
            def to(self, *args, **kwargs):
                return None

        pipe.get_guidance_scale_embedding = lambda *args, **kwargs: _Dropped()
    if image is not None:
        source = Image.open(_flatten(image)).convert("RGB").resize((512, 512), Image.LANCZOS)
        result = pipe(prompt=prompt, image=source, strength=strength, num_inference_steps=steps, guidance_scale=1.0, generator=generator).images[0]
    else:
        result = pipe(prompt=prompt, num_inference_steps=steps, guidance_scale=8.0, height=512, width=512, generator=generator).images[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output)
    record(output, tool=f"local OpenVINO ({device})", model=f"{LOCAL_MODELS['sketch']['repo']}@{LOCAL_MODELS['sketch']['revision'][:7]}",
           licence=LOCAL_MODELS["sketch"]["licence"], input=[_shown(image)] if image else [], prompt=prompt, seed=seed, steps=steps,
           strength=strength if image else None)
    print(f"{_shown(output)}  ({time.time() - started:.0f} s)")
    return output


def _flatten(path: Path) -> Path:
    """A transparent picture on white (what the sketch model expects); other pictures as they are."""
    from PIL import Image

    image = Image.open(path)
    if image.mode not in ("RGBA", "LA"):
        return path
    back = Image.new("RGB", image.size, (255, 255, 255))
    back.paste(image, mask=image.getchannel("A"))
    flat = lab_dir() / "tmp" / (path.stem + "_flat.png")
    flat.parent.mkdir(parents=True, exist_ok=True)
    back.save(flat)
    return flat


def _marching_cubes_from_skimage() -> None:
    """TripoSR imports ``torchmcubes.marching_cubes``; the same surface from scikit-image, in the same axis order."""
    import types

    import numpy as np
    import torch
    from skimage.measure import marching_cubes

    def cubes(level: torch.Tensor, threshold: float):
        volume = level.detach().cpu().numpy().astype(np.float32)
        verts, faces, _normals, _values = marching_cubes(volume, threshold)
        # torchmcubes gives (x, y, z) = (last, middle, first) array axis; TripoSR turns them back itself.
        return torch.from_numpy(verts[:, ::-1].copy()).float(), torch.from_numpy(faces[:, ::-1].astype(np.int64).copy())

    sys.modules["torchmcubes"] = types.SimpleNamespace(marching_cubes=cubes)


def gltf_ready(mesh):
    """A TripoSR mesh as glTF expects it: y up and facing +z (TripoSR's is z up, facing +x), colours in linear light."""
    import numpy as np

    mesh.apply_transform(np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]], dtype=float))
    if getattr(mesh.visual, "kind", None) == "vertex":
        colours = mesh.visual.vertex_colors.astype(np.float64) / 255.0
        colours[:, :3] **= 2.2  # TripoSR's colours are sRGB values; glTF vertex colours are linear
        mesh.visual.vertex_colors = np.round(colours * 255).astype(np.uint8)
    return mesh


def local_mesh(image: Path, output: Path, *, resolution: int = 256, foreground: float = 0.85) -> Path:
    """A rough 3D shape with vertex colours from one transparent picture, on the CPU (TripoSR)."""
    import numpy as np
    import torch
    from PIL import Image

    started = time.time()
    sys.path.insert(0, str(lab_dir() / "TripoSR"))
    _marching_cubes_from_skimage()
    from tsr.system import TSR
    from tsr.utils import resize_foreground

    model = TSR.from_pretrained(str(local_model("mesh")), config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(8192)
    picture = Image.open(image).convert("RGBA")
    if picture.getextrema()[3][0] == 255:  # no transparency: the background is removed first
        import rembg

        # Named, not rembg's default: that is BRIA RMBG 2.0 (1 GB, CC BY-NC). isnet-anime (176 MB) is made for drawn characters.
        picture = rembg.remove(picture, session=rembg.new_session(REMBG_MODEL))
    picture = resize_foreground(picture, foreground)
    pixels = np.asarray(picture).astype(np.float32) / 255.0
    pixels = pixels[:, :, :3] * pixels[:, :, 3:4] + (1 - pixels[:, :, 3:4]) * 0.5  # on grey, as TripoSR was trained
    with torch.no_grad():
        codes = model([Image.fromarray((pixels * 255).astype(np.uint8))], device="cpu")
        mesh = model.extract_mesh(codes, True, resolution=resolution)[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    gltf_ready(mesh).export(output)
    record(output, tool="local TripoSR (CPU)", model=f"{LOCAL_MODELS['mesh']['repo']}@{LOCAL_MODELS['mesh']['revision'][:7]}",
           licence=LOCAL_MODELS["mesh"]["licence"], input=[_shown(image)], settings=f"marching cubes {resolution}, foreground {foreground}")
    print(f"{_shown(output)}  ({time.time() - started:.0f} s, {len(mesh.vertices)} vertices)")
    return output


# --------------------------------------------------------------------------------------------- pictures of a 3D model


VIEWER = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:{bg}}}canvas{{display:block}}</style></head>
<body><script type="importmap">{{"imports":{{"three":"{three}/build/three.module.js","three/addons/":"{three}/examples/jsm/"}}}}</script>
<script type="module">
import * as THREE from "three";
import {{ GLTFLoader }} from "three/addons/loaders/GLTFLoader.js";
const size = {size}, views = {views};
const renderer = new THREE.WebGLRenderer({{antialias: true, preserveDrawingBuffer: true}});
renderer.setSize(size * views.length, size); renderer.setScissorTest(true); renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color("{bg}");
scene.add(new THREE.AmbientLight(0xffffff, 1.6)); scene.add(new THREE.HemisphereLight(0xffffff, 0x9a93ad, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(1, 2, 3); scene.add(sun);
new GLTFLoader().load("data:model/gltf-binary;base64,{glb}", (gltf) => {{
  const model = gltf.scene; const box = new THREE.Box3().setFromObject(model); const centre = box.getCenter(new THREE.Vector3());
  const span = box.getSize(new THREE.Vector3()).length(); model.position.sub(centre); scene.add(model);
  model.traverse((o) => {{
    if (!o.isMesh) return;
    o.material.metalness = 0; o.material.roughness = 1;  // a matte figure: the colours as painted, not a mirror
    if (o.geometry.attributes.color && !o.material.map) o.material.vertexColors = true;
  }});
  const camera = new THREE.PerspectiveCamera(30, 1, span / 100, span * 10);
  views.forEach(([x, y, z], i) => {{
    camera.position.set(x, y, z).normalize().multiplyScalar(span * 1.9); camera.lookAt(0, 0, 0);
    renderer.setViewport(i * size, 0, size, size); renderer.setScissor(i * size, 0, size, size); renderer.render(scene, camera);
  }});
  document.title = "done";
}}, undefined, (error) => {{ document.title = "error " + error; }});
window.addEventListener("error", (event) => {{ document.title = "error " + event.message; }});
</script></body></html>"""

#: Camera directions: front, front-right, right side, back, above (y is up, the model faces +z).
VIEW_DIRECTIONS = {"front": (0, 0.15, 1), "front-right": (0.7, 0.15, 0.7), "right": (1, 0.15, 0), "back": (0, 0.15, -1), "above": (0, 1, 0.35)}


def views(model: Path, output: Path, *, size: int = 512, background: str = "#F7F4FA", yaw: float = 0.0) -> Path:
    """The model from the front, the front-right, the side, the back and above, side by side in one picture."""
    import math

    sys.path.insert(0, str(ROOT / "packaging"))
    from build_site import find_browser

    browser = find_browser()
    if not browser:
        raise RuntimeError("No Chrome or Edge to draw the model with (set STREAM2CLIP_BROWSER)")
    turn = math.radians(yaw)
    directions = [[x * math.cos(turn) + z * math.sin(turn), y, -x * math.sin(turn) + z * math.cos(turn)] for x, y, z in VIEW_DIRECTIONS.values()]
    page = lab_dir() / "tmp" / "viewer.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(VIEWER.format(bg=background, three=THREE, size=size, views=json.dumps(directions),
                                  glb=base64.b64encode(model.read_bytes()).decode()), encoding="utf-8")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_screenshot(browser, page, size * len(directions), size))
    record(output, tool=f"packaging/mascot_lab.py views (three.js {THREE.rsplit('@', 1)[1]} in a headless browser)", input=[_shown(model)],
           settings=f"{', '.join(VIEW_DIRECTIONS)}; yaw {yaw:g}")
    print(f"{_shown(output)}  ({', '.join(VIEW_DIRECTIONS)})")
    return output


def _screenshot(browser: str, page: Path, width: int, height: int, *, wait: float = 120.0) -> bytes:
    """Open ``page`` in a headless browser, wait until it sets its title to "done", and take the picture.

    Through the DevTools protocol: the browser's own --screenshot does not wait for the model and its
    texture, which are decoded after the page has loaded."""
    import socket
    import urllib.request

    from websockets.sync.client import connect

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    profile = lab_dir() / "tmp" / "chrome-profile"
    process = subprocess.Popen([browser, "--headless=new", "--hide-scrollbars", "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                                f"--remote-debugging-port={port}", "--remote-allow-origins=*", f"--user-data-dir={profile}",
                                f"--window-size={width},{height}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 30
        while True:
            try:
                targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2).read())
                target = next(t for t in targets if t.get("type") == "page")
                break
            except (OSError, StopIteration, ValueError):
                if time.time() > deadline:
                    raise RuntimeError("The headless browser did not start") from None
                time.sleep(0.3)
        with connect(target["webSocketDebuggerUrl"], max_size=None) as ws:
            counter = 0

            def call(method: str, **params):
                nonlocal counter
                counter += 1
                ws.send(json.dumps({"id": counter, "method": method, "params": params}))
                while True:
                    message = json.loads(ws.recv())
                    if message.get("id") == counter:
                        if "error" in message:
                            raise RuntimeError(f"{method}: {message['error']}")
                        return message.get("result", {})

            call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
            call("Page.navigate", url=page.as_uri())
            deadline = time.time() + wait
            title = ""
            while time.time() < deadline:
                title = call("Runtime.evaluate", expression="document.title", returnByValue=True)["result"].get("value", "")
                if title == "done" or title.startswith("error"):
                    break
                time.sleep(0.5)
            if title != "done":
                raise RuntimeError(f"The model was not drawn: {title or 'no answer'}")
            shot = call("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": width, "height": height, "scale": 1})
            return base64.b64decode(shot["data"])
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


# --------------------------------------------------------------------------------------------- reference sheets

#: The character's colours, sampled from the front reference (source/reference/kiri_wink_green.png).
PALETTE = [
    ("머리", "#FC70B7"), ("귀 안쪽, 머리핀, 끈 끝", "#FFE101"), ("헤드폰", "#0A0A0F"), ("헤드폰 회색", "#636382"),
    ("이어컵, 눈", "#FE01CC"), ("피부", "#FDDDD9"), ("볼", "#FBC2C5"), ("후드", "#FCF6ED"), ("후드 끈", "#362D49"),
]
#: Each sheet: a title, the columns, and the pictures (label, file relative to the mascot folder).
SHEETS: dict[str, dict] = {
    "turnaround": {
        "title": "키리 턴어라운드", "columns": 5, "palette": True,
        "items": [("정면", "kiri_wink_512.png"), ("3/4 정면", "kiri_turn_left_512.png"), ("옆", "design/turnaround/raw_right.png"),
                  ("3/4 뒤", "design/turnaround/raw_back-right.png"), ("뒤", "design/turnaround/raw_back.png")],
    },
    "expressions": {
        "title": "키리 표정", "columns": 4,
        "items": [("윙크", "kiri_wink_512.png"), ("빵 터짐", "kiri_laugh_512.png"), ("깜짝", "kiri_surprised_512.png"), ("컷", "kiri_cut_512.png"),
                  ("집중", "kiri_focus_512.png"), ("슬픔", "design/expressions/raw_sad.png"), ("화남", "design/expressions/raw_angry.png")],
    },
}


def _font(size: int):
    from PIL import ImageFont

    for name in ("C:/Windows/Fonts/malgunbd.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/System/Library/Fonts/AppleSDGothicNeo.ttc"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _green_screen(path: Path) -> bool:
    """Whether a picture stands on the mascot sources' green (a white background is left alone: the hoodie is cream)."""
    from PIL import Image

    sys.path.insert(0, str(ROOT / "packaging"))
    from build_mascot import border_colour, has_transparency

    image = Image.open(path).convert("RGBA")
    if has_transparency(image):
        return False
    r, g, b = border_colour(image)
    return g > 180 and r < 100 and b < 100


def cutout(path: Path):
    """The character without its background: transparent files as they are, green-screen pictures keyed out."""
    from PIL import Image

    sys.path.insert(0, str(ROOT / "packaging"))
    from build_mascot import cut_out, has_transparency

    image = Image.open(path).convert("RGBA")
    picture = image if has_transparency(image) else cut_out(image, "auto", shrink=3)  # 3 px: no green left at the neck
    return picture.crop(picture.getbbox())


def sheet(name: str) -> Path:
    """One reference sheet (``SHEETS``) on the brand's paper colour, with the palette when the sheet asks for it."""
    from PIL import Image, ImageDraw

    spec = SHEETS[name]
    items = [(label, MASCOT / file) for label, file in spec["items"] if (MASCOT / file).exists()]
    cell, pad, columns = 420, 36, spec["columns"]
    rows = (len(items) + columns - 1) // columns
    palette_height = 150 if spec.get("palette") else 0
    width, height = pad * 2 + columns * cell, 110 + rows * (cell + 56) + palette_height + pad
    page = Image.new("RGB", (width, height), "#F7F4FA")
    draw = ImageDraw.Draw(page)
    draw.text((pad, 34), spec["title"], fill="#15131F", font=_font(44))
    for i, (label, path) in enumerate(items):
        x, y = pad + (i % columns) * cell, 110 + (i // columns) * (cell + 56)
        picture = cutout(path)
        picture.thumbnail((cell - 40, cell - 40), Image.LANCZOS)
        page.paste(picture, (x + (cell - picture.width) // 2, y + cell - 20 - picture.height), picture)
        box = draw.textbbox((0, 0), label, font=_font(26))
        draw.text((x + (cell - box[2]) // 2, y + cell + 6), label, fill="#15131F", font=_font(26))
    if palette_height:
        y = height - pad - palette_height + 30
        swatch = (width - pad * 2) // len(PALETTE)
        for i, (label, colour) in enumerate(PALETTE):
            x = pad + i * swatch
            draw.rounded_rectangle((x, y, x + swatch - 12, y + 56), radius=10, fill=colour, outline="#15131F", width=2)
            draw.text((x, y + 64), colour, fill="#15131F", font=_font(18))
            draw.text((x, y + 88), label, fill="#5A5468", font=_font(16))
    out = DESIGN / f"sheet_{name}.png"
    page.save(out, optimize=True)
    record(out, tool="packaging/mascot_lab.py sheets", input=[_shown(p) for _label, p in items])
    print(f"{_shown(out)}  ({len(items)} pictures)")
    return out


# --------------------------------------------------------------------------------------------- command line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup", help="create the lab (packages about 1 GB, models about 6 GB)")
    s.add_argument("--python", help="the Python to make the lab with (default: py -3.13)")
    a = sub.add_parser("angle", help="hosted: the mascot from another camera angle")
    a.add_argument("angle", choices=list(ANGLES))
    a.add_argument("--input", type=Path, default=REFERENCE)
    a.add_argument("--elevation", default="eye-level shot", choices=["low-angle shot", "eye-level shot", "elevated shot", "high-angle shot"])
    a.add_argument("--seed", type=int, default=7)
    a.add_argument("-o", "--output", type=Path, required=True)
    e = sub.add_parser("edit", help="hosted: an expression, outfit or prop on the same character")
    e.add_argument("prompt")
    e.add_argument("--input", type=Path, action="append", help="input picture (repeat for several; default: the wink reference)")
    e.add_argument("--seed", type=int, default=7)
    e.add_argument("--lora", choices=["anime", "angles"], default="anime")
    e.add_argument("-o", "--output", type=Path, required=True)
    t = sub.add_parser("trellis", help="hosted: a textured 3D model (GLB) from one or more views")
    t.add_argument("inputs", type=Path, nargs="+")
    t.add_argument("--seed", type=int, default=7)
    t.add_argument("-o", "--output", type=Path, required=True)
    k = sub.add_parser("sketch", help="local: a loose variation on the Intel GPU")
    k.add_argument("prompt")
    k.add_argument("--input", type=Path, help="start from this picture (img2img)")
    k.add_argument("--strength", type=float, default=0.55)
    k.add_argument("--seed", type=int, default=7)
    k.add_argument("--steps", type=int, default=6)
    k.add_argument("--device", default="GPU", choices=["GPU", "CPU"])
    k.add_argument("-o", "--output", type=Path, required=True)
    m = sub.add_parser("mesh", help="local: a rough 3D shape on the CPU")
    m.add_argument("--input", type=Path, default=MASCOT / "kiri_wink_512.png")
    m.add_argument("--resolution", type=int, default=256)
    m.add_argument("-o", "--output", type=Path, required=True)
    v = sub.add_parser("views", help="pictures of a 3D model from five directions")
    v.add_argument("model", type=Path)
    v.add_argument("--yaw", type=float, default=0.0, help="turn the model first (degrees) when it does not face the front")
    v.add_argument("-o", "--output", type=Path)
    h = sub.add_parser("sheets", help="the reference sheets in assets/brand/mascot/design")
    h.add_argument("names", nargs="*", help=f"only these sheets ({', '.join(SHEETS)}; default: all)")
    args = parser.parse_args(argv)

    if args.command == "setup":
        setup(args.python)
        return 0
    if not in_lab():  # everything else runs with the lab's own Python and models
        if not lab_python().exists():
            print("No mascot lab yet: python packaging/mascot_lab.py setup", file=sys.stderr)
            return 2
        env = {**os.environ, "HF_HUB_CACHE": str(lab_dir() / "hf" / "hub")}  # the models; the login stays where it is
        return subprocess.run([str(lab_python()), "-I", str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])], env=env).returncode
    os.environ.setdefault("HF_HUB_CACHE", str(lab_dir() / "hf" / "hub"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "angle":
        hosted_edit([args.input], f"<sks> {ANGLES[args.angle]} {args.elevation} medium shot", args.output, lora=ANGLE_LORA, seed=args.seed)
    elif args.command == "edit":
        hosted_edit(args.input or [REFERENCE], args.prompt, args.output, lora=EDIT_LORA if args.lora == "anime" else ANGLE_LORA, seed=args.seed)
    elif args.command == "trellis":
        hosted_3d(args.inputs, args.output, seed=args.seed)
    elif args.command == "sketch":
        local_sketch(args.prompt, args.output, image=args.input, strength=args.strength, seed=args.seed, steps=args.steps, device=args.device)
    elif args.command == "mesh":
        local_mesh(args.input, args.output, resolution=args.resolution)
    elif args.command == "views":
        views(args.model, args.output or args.model.with_suffix(".png"), yaw=args.yaw)
    elif args.command == "sheets":
        unknown = [name for name in args.names if name not in SHEETS]
        if unknown:
            print(f"No such sheet: {', '.join(unknown)} (sheets: {', '.join(SHEETS)})", file=sys.stderr)
            return 2
        for name in args.names or SHEETS:
            sheet(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
