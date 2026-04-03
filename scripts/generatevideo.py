#!/usr/bin/env python3
"""
generatevideo.py - Generate video clips from prompts.txt and CREF images
Uses Wan 2.1 video model with character consistency (CREF)

Usage:
  python generatevideo.py                    # Generate all clips
  python generatevideo.py --clips 2          # Generate first 2 clips
  python generatevideo.py --clips 5          # Generate first 5 clips
"""

import os
import sys
import re
import random
import requests
import time
import shutil
import json
import base64
import argparse
from PIL import Image
import numpy as np

COMFYUI_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)


def load_project_config(project_dir=None):
    """Load project configuration from project.json."""
    config_path = os.path.join(project_dir or PARENT_DIR, "project.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


def read_prompts_file(prompts_path):
    """Read prompts.txt and return list of (number, prompt) tuples."""
    prompts = []

    with open(prompts_path, "r") as f:
        content = f.read()

    # Parse prompts like "Prompt 1: ..."
    pattern = r"Prompt (\d+):\s*(.*?)(?=\n\nPrompt \d+:|$)"
    matches = re.findall(pattern, content, re.DOTALL)

    for num, prompt in matches:
        prompt = prompt.strip()
        if prompt:
            prompts.append((int(num), prompt))

    return prompts


def get_reference_images(project_dir, input_dir):
    """Get reference images for the current project only (from project dir),
    and sync them into the ComfyUI input dir so they are ready to use."""
    ref_images = []
    for filename in os.listdir(project_dir):
        if filename.startswith("ref_") and filename.endswith(".png"):
            src = os.path.join(project_dir, filename)
            dst = os.path.join(input_dir, filename)
            shutil.copy2(src, dst)
            ref_images.append(filename)
    return ref_images


def pick_ref_images(prompt_text, ref_images, fallback):
    """Return ref images whose character name appears in the prompt, primary first.
    Filters out names that are substrings of a longer matched name."""
    prompt_lower = prompt_text.lower()
    matched = []
    for filename in ref_images:
        char_name = filename[len("ref_") : -len(".png")].replace("_", " ")
        if char_name in prompt_lower:
            matched.append((len(char_name), char_name, filename))
    matched.sort(reverse=True)  # longest first

    # Remove names that are substrings of a longer already-accepted name
    accepted = []
    accepted_names = []
    for length, char_name, filename in matched:
        if not any(char_name in longer for longer in accepted_names):
            accepted.append(filename)
            accepted_names.append(char_name)

    return accepted or [fallback]


def make_composite_ref(image_paths, output_path):
    """Average-blend multiple ref images into one and save to output_path."""
    arrays = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        arrays.append(np.array(img, dtype=np.float32))
    averaged = np.mean(arrays, axis=0).astype(np.uint8)
    Image.fromarray(averaged).save(output_path)
    return output_path


def generate_video_clip(prompt_text, clip_number, ref_image_names, output_dir):
    """Generate a single video clip using Wan 2.1 with CREF."""
    input_dir = "/home/henry/comfy/ComfyUI/input"

    # Primary image = start frame (most specific character match)
    primary_image = ref_image_names[0]

    # If multiple characters: composite all refs for CLIP vision encoding
    if len(ref_image_names) > 1:
        composite_name = f"ref_composite_clip_{clip_number:02d}.png"
        composite_path = os.path.join(input_dir, composite_name)
        source_paths = [os.path.join(input_dir, n) for n in ref_image_names]
        make_composite_ref(source_paths, composite_path)
        vision_image = composite_name
        print(f"  Composite CREF: {', '.join(ref_image_names)}")
    else:
        vision_image = primary_image

    print(f"Generating clip {clip_number:02d}...")

    output_prefix = f"clip_{clip_number:02d}"

    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": VIDEO_MODEL,
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
        },
        "10": {
            "class_type": "LoadImage",
            "inputs": {"image": primary_image},
        },
        "15": {
            "class_type": "LoadImage",
            "inputs": {"image": vision_image},
        },
        "11": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": "clip_vision_h.safetensors"},
        },
        "12": {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "clip_vision": ["11", 0],
                "image": ["15", 0],
                "crop": "none",
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": prompt_text,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": "blurry, deformed, ugly, scary, dark, violent, low quality, watermark, text, photorealistic, changing character appearance",
            },
        },
        "7": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["5", 0],
                "negative": ["6", 0],
                "vae": ["3", 0],
                "width": VIDEO_WIDTH,
                "height": VIDEO_HEIGHT,
                "length": VIDEO_LENGTH,
                "batch_size": 1,
                "start_image": ["10", 0],
                "clip_vision_output": ["12", 0],
            },
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["7", 0],
                "negative": ["7", 1],
                "latent_image": ["7", 2],
                "cfg": 6,
                "denoise": 1,
                "seed": random.randint(0, 2**32 - 1),
                "steps": 30,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["3", 0],
            },
        },
        "13": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["9", 0],
                "fps": 8,
            },
        },
        "14": {
            "class_type": "SaveVideo",
            "inputs": {
                "filename_prefix": output_prefix,
                "video": ["13", 0],
                "format": "mp4",
                "codec": "h264",
            },
        },
    }

    try:
        resp = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
        data = resp.json()

        if "error" in data:
            print(f"  Error: {data['error']}")
            return None

        prompt_id = data["prompt_id"]
        print(f"  Queued: {prompt_id}", flush=True)

        # Wait for completion (up to 10 minutes)
        for attempt in range(200):
            time.sleep(3)
            history = requests.get(f"{COMFYUI_URL}/history/{prompt_id}").json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_out in outputs.values():
                    # SaveVideo outputs under "images", others use "gifs" or "videos"
                    for key in ("images", "gifs", "videos"):
                        for item in node_out.get(key, []):
                            filename = item.get("filename", "")
                            if not filename.endswith(".mp4"):
                                continue
                            src = os.path.join(
                                "/home/henry/comfy/ComfyUI/output", filename
                            )
                            dst = os.path.join(output_dir, f"{output_prefix}.mp4")
                            if os.path.exists(src):
                                shutil.copy2(src, dst)
                                print(f"  Saved: {dst}", flush=True)
                                return dst
                break

            if attempt % 15 == 0 and attempt > 0:
                elapsed = attempt * 3
                print(f"  Waiting... {elapsed}s elapsed", flush=True)

        print(f"  Timeout for clip {clip_number}")
        return None

    except Exception as e:
        print(f"  Error generating clip {clip_number}: {e}")
        return None


def _is_flux_model(model_name):
    return "flux" in model_name.lower()


def _is_flux2_model(model_name):
    return "flux2" in model_name.lower()


def _build_checkpoint_workflow(prompt_text, output_prefix):
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": IMAGE_MODEL},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": prompt_text},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 1],
                "text": "blurry, deformed, ugly, dark, violent, low quality, watermark",
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "cfg": 7,
                "denoise": 1,
                "seed": random.randint(0, 2**32 - 1),
                "steps": 20,
                "sampler_name": "euler",
                "scheduler": "sgm_uniform",
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": output_prefix, "images": ["6", 0]},
        },
    }


def _build_flux_workflow(prompt_text, output_prefix):
    vae = "flux2-vae.safetensors" if _is_flux2_model(IMAGE_MODEL) else "ae.safetensors"
    clip2 = (
        "mistral_3_small_flux2_bf16.safetensors"
        if _is_flux2_model(IMAGE_MODEL)
        else "t5xxl_fp8_e4m3fn.safetensors"
    )
    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": IMAGE_MODEL, "weight_dtype": "fp8_e4m3fn"},
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": clip2,
                "type": "flux",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": prompt_text},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
        },
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "cfg": 1,
                "denoise": 1,
                "seed": random.randint(0, 2**32 - 1),
                "steps": 20,
                "sampler_name": "euler",
                "scheduler": "simple",
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["3", 0]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": output_prefix, "images": ["8", 0]},
        },
    }
    return workflow


def generate_image_clip_geminiproxy(prompt_text, clip_number, output_dir):
    """Generate a single image via GeminiProxy (CDP browser). Returns output path or None."""
    import websocket as _ws

    cdp_port = 9222
    tab_url = "gemini.google.com"
    img_selector = "img.image"
    output_prefix = f"clip_{clip_number:02d}"
    output_path = os.path.join(output_dir, f"{output_prefix}.png")

    print(f"  Using GeminiProxy for clip {clip_number:02d}...", flush=True)

    try:
        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            print(
                f"  GeminiProxy: no tab found for {tab_url} — open it and log in first"
            )
            return None

        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)

        msg_id = [1]

        def cdp_eval(ws, js):
            pid = msg_id[0]
            msg_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js, "awaitPromise": True},
                    }
                )
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        ws = _ws.create_connection(ws_url, timeout=60, suppress_origin=True)

        # Snapshot existing image srcs before sending
        snap_js = f"(function(){{var imgs=document.querySelectorAll({json.dumps(img_selector)}),srcs=[];for(var i=0;i<imgs.length;i++){{var s=imgs[i].currentSrc||imgs[i].src||'';if(s)srcs.push(s);}}return JSON.stringify(srcs);}})()"
        snap_val = cdp_eval(ws, snap_js)
        existing_srcs = set(json.loads(snap_val)) if snap_val else set()
        print(f"  Existing images before prompt: {len(existing_srcs)}", flush=True)

        full_prompt = "generate an image of: " + prompt_text
        ws.send(
            json.dumps(
                {
                    "id": msg_id[0],
                    "method": "Input.insertText",
                    "params": {"text": full_prompt},
                }
            )
        )
        ws.recv()
        msg_id[0] += 1
        time.sleep(0.2)

        for ev in ("keyDown", "keyUp"):
            ws.send(
                json.dumps(
                    {
                        "id": msg_id[0],
                        "method": "Input.dispatchKeyEvent",
                        "params": {
                            "type": ev,
                            "key": "Enter",
                            "code": "Enter",
                            "windowsVirtualKeyCode": 13,
                            "nativeVirtualKeyCode": 13,
                        },
                    }
                )
            )
            ws.recv()
            msg_id[0] += 1

        # Poll for new image
        img_src = None
        deadline = time.monotonic() + 120
        existing_srcs_list = list(existing_srcs)
        time.sleep(10)
        while time.monotonic() < deadline:
            poll_js = f"""(function() {{
                var known = new Set({json.dumps(existing_srcs_list)});
                var imgs = document.querySelectorAll({json.dumps(img_selector)});
                for (var i = 0; i < imgs.length; i++) {{
                    var img = imgs[i];
                    var src = img.currentSrc || img.src || img.getAttribute('src') || '';
                    if (src && !known.has(src) && img.complete && img.naturalWidth >= 100 && img.naturalHeight >= 100)
                        return src;
                }}
                return null;
            }})()"""
            val = cdp_eval(ws, poll_js)
            if val:
                img_src = val
                print(f"  Found image: {img_src[:80]}", flush=True)
                break
            time.sleep(5)

        if not img_src:
            ws.close()
            print(f"  GeminiProxy: timed out waiting for image")
            return None

        # Screenshot the image element via CDP
        rect_js = f"""(function() {{
            var imgs = document.querySelectorAll({json.dumps(img_selector)});
            var img = null;
            for (var i = imgs.length - 1; i >= 0; i--) {{
                if ((imgs[i].currentSrc || imgs[i].src || '') === {json.dumps(img_src)}) {{ img = imgs[i]; break; }}
            }}
            if (!img) img = imgs[imgs.length - 1];
            img.scrollIntoView({{block:'center'}});
            var r = img.getBoundingClientRect();
            var dpr = window.devicePixelRatio || 1;
            var nw = img.naturalWidth || r.width;
            return JSON.stringify({{x:r.left, y:r.top, width:r.width, height:r.height, scale:Math.max(dpr, nw/r.width)}});
        }})()"""
        rect_val = cdp_eval(ws, rect_js)
        time.sleep(0.4)
        rect = json.loads(rect_val)

        pid = msg_id[0]
        msg_id[0] += 1
        ws.send(
            json.dumps(
                {
                    "id": pid,
                    "method": "Page.captureScreenshot",
                    "params": {
                        "format": "png",
                        "clip": {
                            "x": max(0, rect["x"]),
                            "y": max(0, rect["y"]),
                            "width": rect["width"],
                            "height": rect["height"],
                            "scale": rect["scale"],
                        },
                    },
                }
            )
        )
        screenshot_data = None
        for _ in range(2000):
            msg = json.loads(ws.recv())
            if msg.get("id") == pid:
                screenshot_data = msg.get("result", {}).get("data")
                break
        ws.close()

        if screenshot_data:
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(screenshot_data))
            print(f"  Saved: {output_path}", flush=True)
            return output_path

        print(f"  GeminiProxy: screenshot returned no data")
        return None

    except Exception as e:
        print(f"  GeminiProxy error for clip {clip_number}: {e}")
        return None


def generate_image_clip(prompt_text, clip_number, output_dir):
    """Generate a single image using ComfyUI (checkpoint or Flux workflow)."""
    output_prefix = f"clip_{clip_number:02d}"
    if _is_flux_model(IMAGE_MODEL):
        workflow = _build_flux_workflow(prompt_text, output_prefix)
        print(f"  Using Flux workflow: {IMAGE_MODEL}", flush=True)
    else:
        workflow = _build_checkpoint_workflow(prompt_text, output_prefix)
        print(f"  Using checkpoint workflow: {IMAGE_MODEL}", flush=True)
    try:
        resp = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
        data = resp.json()
        if "error" in data:
            print(f"  Error: {data['error']}")
            return None
        prompt_id = data["prompt_id"]
        print(f"  Queued: {prompt_id}", flush=True)
        for attempt in range(100):
            time.sleep(3)
            history = requests.get(f"{COMFYUI_URL}/history/{prompt_id}").json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_out in outputs.values():
                    for item in node_out.get("images", []):
                        filename = item.get("filename", "")
                        if not filename.endswith(".png"):
                            continue
                        src = os.path.join("/home/henry/comfy/ComfyUI/output", filename)
                        dst = os.path.join(output_dir, f"{output_prefix}.png")
                        if os.path.exists(src):
                            shutil.copy2(src, dst)
                            print(f"  Saved: {dst}", flush=True)
                            return dst
                break
            if attempt % 15 == 0 and attempt > 0:
                print(f"  Waiting... {attempt * 3}s elapsed", flush=True)
        print(f"  Timeout for clip {clip_number}")
        return None
    except Exception as e:
        print(f"  Error generating clip {clip_number}: {e}")
        return None


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate video clips from prompts.txt"
    )
    parser.add_argument(
        "--clips",
        type=int,
        default=None,
        help="Number of clips to generate (default: all)",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=PARENT_DIR,
        help="Project directory containing prompts.txt and project.json",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)

    config = load_project_config(project_dir)
    global VIDEO_MODEL, IMAGE_MODEL, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_LENGTH, VIDEO_FPS
    VIDEO_MODEL = config.get("video_model", "wan2.1_t2v_14B_fp8_e4m3fn.safetensors")
    IMAGE_MODEL = config.get(
        "image_model", "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
    )
    VIDEO_WIDTH = config.get("video_width", 832)
    VIDEO_HEIGHT = config.get("video_height", 480)
    VIDEO_LENGTH = config.get("video_length", 17)
    VIDEO_FPS = config.get("video_fps", 8)
    generate_video = config.get("generate_video", True)

    # Find prompts.txt and reference images
    prompts_path = os.path.join(project_dir, "prompts.txt")
    input_dir = "/home/henry/comfy/ComfyUI/input"
    output_dir = project_dir

    if not os.path.exists(prompts_path):
        print(f"Error: prompts.txt not found at {prompts_path}")
        sys.exit(1)

    # Read prompts
    prompts = read_prompts_file(prompts_path)
    print(f"Found {len(prompts)} prompts")

    # Get reference images — project dir only, synced into ComfyUI input
    ref_images = get_reference_images(project_dir, input_dir)

    if not ref_images and generate_video:
        sys.exit(1)

    # Create clips directory
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    print(f"{'VIDEO' if generate_video else 'IMAGE'} GENERATION PIPELINE")
    print(f"Prompts: {len(prompts)}")
    print(f"Clips to generate: {args.clips if args.clips else 'all'}")
    print(f"Output: {clips_dir}")

    # Limit number of clips if specified
    if args.clips:
        prompts = prompts[: args.clips]

    # Generate clips
    results = []
    for i, (clip_num, prompt_text) in enumerate(prompts):
        ext = "mp4" if generate_video else "png"
        clip_file = os.path.join(clips_dir, f"clip_{clip_num:02d}.{ext}")
        if os.path.exists(clip_file):
            print(
                f"[{i + 1}/{len(prompts)}] clip_{clip_num:02d}.{ext} already exists — skipping"
            )
            results.append((clip_num, True))
            continue

        print(f"[{i + 1}/{len(prompts)}] Processing prompt {clip_num}")

        matched_refs = (
            pick_ref_images(prompt_text, ref_images, fallback=ref_images[0])
            if ref_images
            else []
        )
        if matched_refs:
            print(f"  Using ref(s): {', '.join(matched_refs)}")

        if generate_video:
            clip_path = generate_video_clip(
                prompt_text, clip_num, matched_refs, clips_dir
            )
        elif IMAGE_MODEL == "geminiproxy":
            clip_path = generate_image_clip_geminiproxy(
                prompt_text, clip_num, clips_dir
            )
        else:
            clip_path = generate_image_clip(prompt_text, clip_num, clips_dir)
        results.append((clip_num, clip_path is not None))

        # Brief pause between generations
        time.sleep(2)

    successful = sum(1 for _, success in results if success)
    print(f"Generated {successful}/{len(prompts)} clips → {clips_dir}")


if __name__ == "__main__":
    main()
