#!/usr/bin/env python3
"""
generatevideo.py - Generate video clips from prompts.txt and CREF images
Uses Wan 2.1 video model with character consistency (CREF)

Usage:
  python generatevideo.py                    # Generate all clips
  python generatevideo.py --clips 2          # Generate first 2 clips
  python generatevideo.py --clips 5          # Generate first 5 clips
"""

import urllib.parse
import re

def refocus_web_app(cdp_port=9222):
    """Attempt to bring the user's web app tab back into focus."""
    import requests
    try:
        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=1)
        for tab in resp.json():
            url = tab.get("url", "")
            if tab.get("type") == "page" and "7070" in url:
                requests.get(f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=1)
                break
    except Exception:
        pass

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
import subprocess
from PIL import Image
import numpy as np

try:
    from prompts import STYLE_DESCRIPTIONS
except ImportError:
    # Fallback to avoid import issues if run from a different CWD
    import importlib.util
    _spec = importlib.util.spec_from_file_location("prompts", os.path.join(os.path.dirname(__file__), "prompts.py"))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    STYLE_DESCRIPTIONS = _mod.STYLE_DESCRIPTIONS

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
        lines = f.readlines()

    num = 1
    for line in lines:
        line = line.strip()
        if not line or "=" in line or "Video Generation" in line:
            continue
        
        # Extract just the prompt part before ||| if it exists
        prompt_text = line
        if "|||" in prompt_text:
            prompt_text = prompt_text.split("|||", 1)[0]
            
        # Clean up any leftover numbering or "Prompt X:" prefixes for backwards compatibility
        prompt_text = re.sub(r"^(?:Prompt\s*\d+[\.\:]\s*)?(?:\d+[\.\)]\s*)?", "", prompt_text).strip()
        
        if prompt_text:
            prompts.append((num, prompt_text))
            num += 1

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


def _is_ltx_model(model_name):
    return "ltx" in model_name.lower() or "ltxv" in model_name.lower()


def generate_ltx_clip(prompt_text, clip_number, primary_image, output_dir):
    """Generate a single video clip using LTX-Video I2V via ComfyUI."""
    output_prefix = f"clip_{clip_number:02d}"
    print(f"Generating LTX clip {clip_number:02d}...", flush=True)

    width, height = 768, 512
    frame_rate = 25

    # Two-step I2V: generate a scene PNG first (if not already done), then use it
    # as the I2V start frame. This ensures the video begins from the correct scene
    # rather than the CREF image (which causes "camera pans away from portrait" motion).
    png_clip_path = os.path.join(output_dir, f"clip_{clip_number:02d}.png")
    comfyui_input_dir = "/home/henry/comfy/ComfyUI/input"
    if not os.path.exists(png_clip_path):
        print(f"  Scene PNG not found — generating it first (T2I step)...", flush=True)
        if IMAGE_MODEL == "geminiproxy":
            generated = generate_image_clip_geminiproxy(prompt_text, clip_number, output_dir)
        elif IMAGE_MODEL == "google":
            generated = generate_image_clip_google(prompt_text, clip_number, output_dir)
        else:
            generated = generate_image_clip(prompt_text, clip_number, output_dir)
        if not generated:
            print(f"  T2I failed — falling back to CREF as start frame", flush=True)
    if os.path.exists(png_clip_path):
        start_image_name = f"scene_{clip_number:02d}.png"
        shutil.copy2(png_clip_path, os.path.join(comfyui_input_dir, start_image_name))
        print(f"  Using scene PNG as I2V start frame: {start_image_name}", flush=True)
    else:
        start_image_name = primary_image
        print(f"  Using CREF as start frame: {start_image_name}", flush=True)

    # Match video length to audio duration if audio file exists
    audio_path = os.path.join(os.path.dirname(output_dir), "audio", f"line_{clip_number:02d}.mp3")
    length = 97  # default ~3.9s
    if os.path.exists(audio_path):
        try:
            dur_str = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]).strip().decode()
            audio_dur = float(dur_str)
            # LTX length must satisfy: (length - 1) % 8 == 0, minimum 9
            raw_frames = audio_dur * frame_rate
            length = max(9, int(round(raw_frames / 8)) * 8 + 1)
            print(f"  Audio duration: {audio_dur:.2f}s → {length} frames", flush=True)
        except Exception as e:
            print(f"  Could not read audio duration, using default: {e}", flush=True)

    # LTX models live in diffusion_models, so use UNETLoader + separate VAELoader
    # T5 text encoder is loaded separately via CLIPLoader (type "ltxv")
    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": VIDEO_MODEL, "weight_dtype": "default"},
        },
        "15": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ltx-video-vae-v0.9.5.safetensors"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "ltxv"},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": start_image_name},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": prompt_text},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, fused fingers, bad anatomy, weird hand, ugly, blurry, watermark",
            },
        },
        # LTXVConditioning sets frame_rate metadata on conditioning
        "7": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": ["5", 0],
                "negative": ["6", 0],
                "frame_rate": frame_rate,
            },
        },
        # LTXVImgToVideo encodes the start image — VAE from dedicated VAELoader
        "8": {
            "class_type": "LTXVImgToVideo",
            "inputs": {
                "positive": ["7", 0],
                "negative": ["7", 1],
                "vae": ["15", 0],
                "image": ["4", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "strength": 1.0,
            },
        },
        # LTXVScheduler produces sigmas
        "9": {
            "class_type": "LTXVScheduler",
            "inputs": {
                "latent": ["8", 2],
                "steps": 30,
                "max_shift": 2.05,
                "base_shift": 0.95,
                "stretch": True,
                "terminal": 0.1,
            },
        },
        # SamplerCustom drives the denoise loop — model from UNETLoader output 0
        "10": {
            "class_type": "SamplerCustom",
            "inputs": {
                "model": ["1", 0],
                "add_noise": True,
                "noise_seed": random.randint(0, 2**32 - 1),
                "cfg": 3.0,
                "positive": ["8", 0],
                "negative": ["8", 1],
                "sampler": ["11", 0],
                "sigmas": ["9", 0],
                "latent_image": ["8", 2],
            },
        },
        "11": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["15", 0]},
        },
        "13": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["12", 0], "fps": frame_rate},
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
            print(f"  LTX Error: {data['error']}")
            return None

        prompt_id = data["prompt_id"]
        print(f"  Queued: {prompt_id}", flush=True)

        for attempt in range(200):
            time.sleep(3)
            history = requests.get(f"{COMFYUI_URL}/history/{prompt_id}").json()
            if prompt_id in history:
                job = history[prompt_id]
                # Check for execution error first
                status = job.get("status", {})
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    err_msgs = [m for m in msgs if m[0] == "execution_error"]
                    err_text = err_msgs[0][1] if err_msgs else str(msgs)
                    print(f"  ComfyUI error for LTX clip {clip_number}: {err_text}", flush=True)
                    return None
                # Only break if job is actually complete (has outputs or status done)
                if status.get("status_str") == "success" or status.get("completed"):
                    outputs = job.get("outputs", {})
                    for node_out in outputs.values():
                        for key in ("images", "gifs", "videos"):
                            for item in node_out.get(key, []):
                                filename = item.get("filename", "")
                                if not filename.endswith(".mp4"):
                                    continue
                                src = os.path.join("/home/henry/comfy/ComfyUI/output", filename)
                                dst = os.path.join(output_dir, f"{output_prefix}.mp4")
                                if os.path.exists(src):
                                    shutil.copy2(src, dst)
                                    print(f"  Saved: {dst}", flush=True)
                                    return dst
                    print(f"  LTX clip {clip_number}: job done but no mp4 output found", flush=True)
                    return None
            if attempt % 15 == 0 and attempt > 0:
                print(f"  Waiting... {attempt * 3}s elapsed", flush=True)

        print(f"  Timeout for LTX clip {clip_number}")
        return None

    except Exception as e:
        print(f"  Error generating LTX clip {clip_number}: {e}")
        return None


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

        # Clear textbox utilizing proper CDP dispatch keys
        focus_js = r"document.querySelector('textarea, [contenteditable=true], [role=textbox]')?.focus();"
        cdp_eval(ws, focus_js)
        time.sleep(0.2)
        for key, code, vk in (("a", "KeyA", 65), ("Backspace", "Backspace", 8)):
            mods = 2 if key == "a" else 0
            for ev in ("keyDown", "keyUp"):
                ws.send(json.dumps({"id": msg_id[0], "method": "Input.dispatchKeyEvent", "params": {
                    "type": ev, "key": key, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk, "modifiers": mods
                }}))
                ws.recv()
                msg_id[0] += 1
        time.sleep(0.1)

        count_js = f"document.querySelectorAll({json.dumps(img_selector)}).length"
        existing_count = int(cdp_eval(ws, count_js) or 0)
        print(f"  Existing images before prompt: {existing_count}", flush=True)

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
        time.sleep(0.5)

        # Wait for Send button to be enabled (GeminiProxy may still be busy from prior request)
        ready_deadline = time.monotonic() + 15
        while time.monotonic() < ready_deadline:
            ready = cdp_eval(ws, r"(function(){ var b=document.querySelector('button[aria-label*=\"Send\"]'); return (b && !b.disabled) ? 'yes' : 'no'; })()")
            if ready == 'yes':
                break
            print("  GeminiProxy: waiting for Send button to be ready...", flush=True)
            time.sleep(1)

        # Submit with retry — verify input cleared as confirmation submit worked
        submit_js = r"(function() { var b = document.querySelector('button[aria-label*=\"Send\"], button[data-testid*=\"send\"]'); if(b && !b.disabled) { b.click(); return 'click'; } var el = document.querySelector('rich-textarea textarea, [contenteditable=true], [role=textbox]'); if(el) { el.focus(); el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',code:'Enter',keyCode:13,bubbles:true,cancelable:true})); el.dispatchEvent(new KeyboardEvent('keypress', {key:'Enter',code:'Enter',keyCode:13,bubbles:true,cancelable:true})); el.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter',code:'Enter',keyCode:13,bubbles:true})); return 'key'; } return 'none'; })()"
        check_input_js = r"(function(){ var el=document.querySelector('rich-textarea textarea, [contenteditable=true], [role=textbox]'); return el ? (el.value||el.innerText||el.textContent||'').trim() : ''; })()"
        for attempt in range(3):
            cdp_eval(ws, submit_js)
            time.sleep(1.5)
            remaining = cdp_eval(ws, check_input_js)
            if not remaining:
                break
            print(f"  GeminiProxy: submit attempt {attempt + 1} input not cleared, retrying", flush=True)
            time.sleep(1)

        # Poll until image count increases
        found = False
        poll_deadline = time.monotonic() + 120
        while time.monotonic() < poll_deadline:
            time.sleep(2)
            new_count = int(cdp_eval(ws, count_js) or 0)
            if new_count > existing_count:
                print(f"  GeminiProxy: new image detected ({existing_count} -> {new_count})", flush=True)
                found = True
                break
        time.sleep(0.5)

        if not found:
            ws.close()
            print(f"  GeminiProxy: timed out waiting for image")
            return None

        # Screenshot the image element via CDP
        rect_val = cdp_eval(ws, f"""(function() {{
            var imgs = document.querySelectorAll({json.dumps(img_selector)});
            var img = imgs[imgs.length - 1];
            if (!img) return null;
            img.scrollIntoView({{block:'center'}});
            var r = img.getBoundingClientRect();
            var dpr = window.devicePixelRatio || 1;
            var nw = img.naturalWidth || r.width;
            return JSON.stringify({{x:r.left, y:r.top, width:r.width, height:r.height, scale:Math.max(dpr, nw/r.width)}});
        }})()""")
        if not rect_val:
            ws.close()
            print(f"  GeminiProxy: could not locate image element")
            return None
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
        screenshot_deadline = time.monotonic() + 30
        while time.monotonic() < screenshot_deadline:
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
    finally:
        try:
            ws.close()
        except:
            pass
        refocus_web_app(cdp_port)


GOOGLE_API_KEY = "AIzaSyCOB6-ofEbthCY9Igt0VD3ddm2qjWiUtws"


class _GoogleImageGenerator:
    """Google Imagen image generator — mirrors ContentCreator's GoogleImageGenerator."""

    def __init__(self):
        from google import genai
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model = "imagen-3.0-generate-001"
        self.discovered = False

    def _discover_model(self):
        if self.discovered:
            return
        try:
            models = list(self.client.models.list())
            imagen_models = [m.name for m in models if "imagen" in m.name.lower()]
            if imagen_models:
                preferences = [
                    "imagen-4.0-generate-001", "imagen-4.0-ultra-generate-001", "imagen-4.0-fast-generate-001",
                    "imagen-3.0-generate-001", "imagen-3.0-generate", "imagen-3.0", "imagen",
                ]
                found = False
                for pref in preferences:
                    for m in imagen_models:
                        if pref == m.replace("models/", ""):
                            self.model = pref
                            found = True
                            break
                    if found:
                        break
                if not found:
                    self.model = imagen_models[0].replace("models/", "")
        except Exception:
            pass
        self.discovered = True

    def generate_image(self, prompt, output_path):
        from google.genai import types
        if not self.discovered:
            self._discover_model()
        try:
            response = self.client.models.generate_images(
                model=self.model,
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/jpeg"),
            )
            if not response.generated_images:
                raise Exception("No images generated by Google Imagen (check safety filters)")
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
            return True
        except Exception as e:
            if "404" in str(e) and self.model in ["imagen-3.0-generate-001", "imagen-4.0-generate-001"]:
                self.discovered = False
                self._discover_model()
                if self.model not in ["imagen-3.0-generate-001", "imagen-4.0-generate-001"]:
                    return self.generate_image(prompt, output_path)
            print(f"  Google Imagen error: {e}", flush=True)
            return False


_google_generator = None


def generate_image_clip_google(prompt_text, clip_number, output_dir):
    """Generate a single image via Google Imagen API. Returns output path or None."""
    global _google_generator
    if _google_generator is None:
        _google_generator = _GoogleImageGenerator()
    dst = os.path.join(output_dir, f"clip_{clip_number:02d}.png")
    ok = _google_generator.generate_image(prompt_text, dst)
    if ok:
        print(f"  Saved: {dst}", flush=True)
        return dst
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

    # Load style description
    image_style = config.get("image_style", "Stick Figure")
    style_desc = STYLE_DESCRIPTIONS.get(image_style, "")
    if style_desc:
        print(f"Applying style: {image_style}", flush=True)

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

        # Prepend style right before generation
        full_prompt_text = f"{style_desc}, {prompt_text}" if style_desc else prompt_text

        if generate_video and _is_ltx_model(VIDEO_MODEL):
            primary_ref = matched_refs[0] if matched_refs else None
            if not primary_ref:
                print(f"  Skipping LTX clip {clip_num}: no reference image found")
                results.append((clip_num, False))
                continue
            clip_path = generate_ltx_clip(full_prompt_text, clip_num, primary_ref, clips_dir)
        elif generate_video:
            clip_path = generate_video_clip(
                full_prompt_text, clip_num, matched_refs, clips_dir
            )
        elif IMAGE_MODEL == "geminiproxy":
            clip_path = generate_image_clip_geminiproxy(
                full_prompt_text, clip_num, clips_dir
            )
        elif IMAGE_MODEL == "google":
            clip_path = generate_image_clip_google(full_prompt_text, clip_num, clips_dir)
        else:
            clip_path = generate_image_clip(full_prompt_text, clip_num, clips_dir)
        results.append((clip_num, clip_path is not None))

        # Brief pause between generations
        time.sleep(2)

    successful = sum(1 for _, success in results if success)
    print(f"Generated {successful}/{len(prompts)} clips → {clips_dir}")


if __name__ == "__main__":
    main()
