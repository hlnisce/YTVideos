#!/usr/bin/env python3
"""
main.py - Web interface for video generation pipeline
Runs on port 7070 with Config editor
"""

import os
import re
import json
import random
import subprocess
import threading
import time
from collections import deque
from flask import Flask, render_template_string, jsonify, request, send_file
import requests

app = Flask(__name__)

VIDEOS_DIR = "/home/henry/APPS/YTVideos/videos"
VERSION = "v4.86"

STYLE_DESCRIPTIONS = {
    "3D Render": "Clean, modern 3D CGI render. Smooth surfaces, precise geometry, studio-quality lighting with soft shadows. Polished and professional digital art look.",
    "Anime": "Japanese animation style. Large expressive eyes, clean linework, vibrant colors, dramatic lighting.",
    "Cartoon": "Expressive, vibrant character designs suitable for animation. Clear silhouettes, appealing features. Modern 2D style. Bright, saturated colors.",
    "Cartoon Reality": "Stylized, expressive proportions (3D animated film look) with photorealistic skins/textures. Cinematic lighting.",
    "Chinese": "Simple Chinese stick figure illustration. Circular head (light yellow skin, two short angled eyebrows, NO eyes, small U-shaped smile). Red square body. Thin black lines for arms and legs. No shading, no textures, no detail. Always populate the scene with multiple Chinese stick figure characters doing relevant actions. Background MUST feature distinctly Chinese cultural elements: curved-roof pagodas, red paper lanterns, bamboo stalks, cherry blossom trees, Great Wall silhouette. Use warm red and gold color palette. Keep everything minimal and flat.",
    "Cinematic": "Dramatic film-grade photography. Moody, high-contrast lighting with deep shadows and rich color grading. Widescreen cinematic composition, shallow depth of field.",
    "Comic Book": "Bold black ink outlines, halftone dot shading, high-contrast colors. Classic American comic book panel style. Dynamic action poses and strong visual drama.",
    "Dark Fantasy": "Moody, painterly dark fantasy art. Rich deep tones, atmospheric fog, dramatic lighting. Detailed textures with an epic, otherworldly feel.",
    "Doodle": "Hand-drawn doodle style. Simple round heads, basic body shapes with loose outlines, minimal detail. Black ink lines with optional soft color fills. Casual notebook sketch look.",
    "Flat Design": "Minimalist flat design illustration. Clean geometric shapes, bold solid colors, no gradients or shadows. Simple, modern, and iconographic.",
    "Infrared Photo": "Infrared photography style. Foliage glows white, skies turn deep black or magenta, skin appears luminous. Ethereal, otherworldly atmosphere with high contrast.",
    "Low Poly": "Geometric low-polygon art style. Angular faceted surfaces, flat-shaded triangular planes, bold clean colors. Modern digital art with a crystalline structure.",
    "Minimalist": "Ultra-clean minimalist design. Vast negative space, single focal subject, muted or monochrome palette with one accent color. Simple, elegant, and modern.",
    "Neon/Cyberpunk": "Futuristic cyberpunk aesthetic. Glowing neon lights in vivid purples, blues, and pinks against dark rain-slicked urban environments. High contrast, electric atmosphere.",
    "Oil Painting": "Classical oil painting style. Rich impasto brushstrokes, deep saturated colors, warm dramatic lighting. Museum-quality fine art composition.",
    "Pencil Sketch": "Detailed monochrome pencil sketch. Fine crosshatching, expressive line weight variation, realistic shading. Classic hand-drawn illustration feel.",
    "Pixel Art": "Retro pixel art style. Chunky pixels, limited color palette, nostalgic 8-bit or 16-bit aesthetic.",
    "Real Person": "Highly detailed, photorealistic. Cinematic lighting, photograph quality. Natural skin textures.",
    "Retro/Vintage": "Warm retro aesthetic inspired by 1970s-80s print design. Faded colors, grain texture, sun-bleached tones, vintage typography feel. Nostalgic and warm.",
    "Stick Figure": "Simple stick figure illustration. Circular head (peach skin, two dot eyes, U-shaped smile). Blue rectangle body. Thin black lines for arms and legs. No shading, no textures, no detail. Always populate the scene with multiple stick figure characters doing relevant actions. Background figures must have a white rectangle body. Background should reflect the scene with simple flat shapes only. Keep backgrounds minimal and flat.",
    "Surrealist": "Dream-like surrealist imagery. Impossible scenes, melting or morphing objects, unexpected scale, hyper-detailed textures in illogical combinations. Thought-provoking and strange.",
    "Synthwave": "Retro 80s synthwave aesthetic. Purple and pink gradient skies, glowing grid lines, chrome text, sunset silhouettes. Nostalgic futurism with neon glow effects.",
    "Ukiyo-e": "Traditional Japanese ukiyo-e woodblock print style. Bold outlines, flat areas of color, decorative patterns, stylized waves and nature motifs. Elegant and timeless.",
    "Watercolor": "Soft watercolor illustration style. Gentle washes of color, visible brushstrokes, dreamy atmosphere.",
}

CAMERA_MOTIONS = {"zoom_in", "zoom_out", "pan_down", "pan_up"}
XFADE_TRANSITIONS = {
    "fade",
    "fadewhite",
    "dissolve",
    "wipeleft",
    "wiperight",
    "wipeup",
    "wipedown",
    "slideleft",
    "slideright",
    "slideup",
    "slidedown",
    "circlecrop",
    "rectcrop",
    "distance",
    "pixelize",
    "radial",
    "zoomin",
    "diagbl",
    "diagbr",
    "diagtl",
    "diagtr",
    "hlslice",
    "hrslice",
    "vuslice",
    "vdslice",
    "smoothleft",
    "smoothright",
    "smoothup",
    "smoothdown",
}


HTML = r"""
<!DOCTYPE html>
<html>
<head>
    <title>Video Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
        .container { display: flex; height: 100vh; overflow: hidden; }
        .main-panel { flex: 2; padding: 15px 20px; display: flex; flex-direction: column; overflow: hidden; }
        .log-panel { width: 320px; background: #1e1e1e; color: #0f0; padding: 10px; display: flex; flex-direction: column; font-family: monospace; font-size: 10px; border-left: 3px solid #333; overflow: hidden; }
        #logContent { flex: 1; overflow-y: auto; overflow-x: hidden; }
        #logContent::-webkit-scrollbar { width: 8px; }
        #logContent::-webkit-scrollbar-track { background: #111; }
        #logContent::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
        #logContent::-webkit-scrollbar-thumb:hover { background: #777; }
        .log-entry { margin-bottom: 3px; padding: 2px 0; border-bottom: 1px solid #333; }
        .log-time { color: #888; }
        .log-info { color: #0f0; }
        .log-error { color: #f55; }
        .log-success { color: #5f5; }
        h1 { color: #333; font-size: 20px; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .btn { padding: 6px 14px; font-size: 13px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        .btn:hover { background: #0056b3; }
        .tab-bar { display: flex; gap: 0; border-bottom: 2px solid #ccc; margin-bottom: 0; align-items: flex-end; }
        .tab { padding: 6px 16px; font-size: 13px; cursor: pointer; background: #e9ecef; border: 1px solid #ccc; border-bottom: none; border-radius: 4px 4px 0 0; color: #555; margin-right: 3px; }
        .tab:hover { background: #dee2e6; }
        .tab.active { background: white; color: #333; font-weight: bold; border-bottom: 2px solid white; margin-bottom: -2px; }
        .tab-content { flex: 1; background: white; border: 1px solid #ccc; border-top: none; padding: 15px; overflow-y: auto; }
        .form-group { margin-bottom: 7px; display: flex; align-items: center; gap: 8px; }
        .form-group label { font-weight: bold; font-size: 12px; width: 110px; flex-shrink: 0; }
        .form-group input, .form-group select { flex: 1; padding: 4px 6px; font-size: 12px; box-sizing: border-box; }
        .btn-save { background: #28a745; color: white; border: none; padding: 6px 14px; font-size: 12px; cursor: pointer; border-radius: 4px; }
        .prompts-content { font-family: monospace; font-size: 11px; white-space: pre-wrap; color: #333; line-height: 1.6; }
        .clips-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; padding: 4px 0; }
        .clip-card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 6px; cursor: pointer; }
        .clip-card:hover { border-color: #007bff; }
        .clip-card img { width: 100%; border-radius: 4px; display: block; }
        .clip-card video { width: 100%; border-radius: 4px; display: block; }
        .clip-card .clip-label { font-size: 11px; color: #666; padding: 4px 2px 0; text-align: center; }
        .cref-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px; padding: 4px 0; }
        .cref-card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 8px; }
        .cref-card h4 { margin: 0 0 6px 0; font-size: 14px; color: #333; }
        .cref-card p { margin: 0; font-size: 12px; color: #666; line-height: 1.5; }
        .cref-card img { width: 100%; border-radius: 6px; margin-bottom: 8px; object-fit: cover; max-height: 200px; }
        .cref-card .no-image { width: 100%; height: 120px; background: #e9ecef; border-radius: 6px; margin-bottom: 8px; display: flex; align-items: center; justify-content: center; color: #adb5bd; font-size: 11px; }
        .cref-desc-editor { width: 100%; min-height: 130px; font-size: 11px; padding: 6px; border: 1px solid #ddd; border-radius: 4px; resize: vertical; box-sizing: border-box; font-family: inherit; color: #333; line-height: 1.4; }
        .cref-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
        .cref-card-header h4 { margin: 0; font-size: 14px; color: #333; flex: 1; }
        .cref-name-input { flex: 1; font-size: 14px; font-weight: 600; color: #333; border: 1px solid transparent; background: transparent; padding: 2px 4px; border-radius: 4px; }
        .cref-name-input:hover { border-color: #ddd; background: #fff; }
        .cref-name-input:focus { border-color: #0366d6; background: #fff; outline: none; }
        .cref-save-icon { background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 4px; border-radius: 4px; }
        .cref-save-icon:hover { background: #e9ecef; }
        .cref-delete-icon { background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 4px; border-radius: 4px; color: #dc3545; }
        .cref-delete-icon:hover { background: #f8d7da; }
        .cref-words { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }
        .cref-tag { background: #e7f1ff; color: #0366d6; font-size: 11px; padding: 2px 8px; border-radius: 10px; }
        .prompts-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .prompts-table th { background: #f1f3f5; text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6; font-size: 11px; text-transform: uppercase; color: #666; }
        .prompts-table td { padding: 0 8px; border-bottom: 1px solid #eee; vertical-align: top; }
        .prompts-table tr:hover { background: #f8f9fa; }
        .prompt-num { width: 30px; text-align: center; color: #999; }
        .prompt-sentence { width: 30%; color: #333; line-height: 1.5; }
        .prompts-table .prompt-text { width: 40%; font-family: monospace; font-size: 11px; color: #555; line-height: 0; padding: 0 !important; }
        .prompt-text-content { font-size: 11px; white-space: pre-wrap; word-break: break-word; }
        .prompts-table .prompt-img { width: 160px; text-align: center; vertical-align: middle; }
        .prompt-img img { max-height: 150px; border-radius: 4px; cursor: pointer; }
        .prompt-img img:hover { opacity: 0.85; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-panel">
             <h1>🎬 Video Generator <span style="font-size:13px; color:#888; font-weight:normal;">{{ version }}</span>
                <button class="btn" id="runBtn" onclick="handleRunStop()" style="background: #28a745;">▶️ Run</button>
                <button class="btn" onclick="resetProject()" style="background: #dc3545;">🗑️ Reset</button>
                <select id="projectSelect" onchange="loadProject()" style="padding: 5px 8px; font-size: 13px;">
                    <option value="">-- Select Project --</option>
                </select>
                <button class="btn" onclick="resetPipelineFlag()" style="background: #6c757d; font-size:12px; padding: 5px 10px;" title="Reset pipeline running flag">🔄</button>
                <button class="btn" onclick="checkComfyQueue()" style="background: #6c757d; font-size:12px; padding: 5px 10px;" title="Check ComfyUI Queue">Confy</button>
                <select id="ai_helper" style="padding:5px 8px; font-size:12px; border-radius:4px; border:1px solid #ccc;">
                    <option value="opencode">OpenCode</option>
                    <option value="claude">Claude</option>
                    <option value="copilotproxy">CopilotProxy</option>
                    <option value="deepseekproxy">DeepSeekProxy</option>
                    <option value="geminiproxy">GeminiProxy</option>
                    <option value="chatgptproxy">ChatGPTProxy</option>
                    <option value="perplexityproxy">PerplexityProxy</option>
                    <option value="xiaomiproxy">XiaomiProxy</option>
                    <option value="google">Google</option>
                </select>
                <select id="image_model" style="padding:5px 8px; font-size:12px; border-radius:4px; border:1px solid #ccc;">
                    <option value="Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors">Juggernaut XL v9</option>
                    <option value="RealVisXL_V5.0_Lightning_fp16.safetensors">RealVisXL V5 Lightning</option>
                    <option value="sd_xl_base_1.0.safetensors">SDXL Base 1.0</option>
                    <option value="v1-5-pruned-emaonly.safetensors">SD 1.5</option>
                    <option value="flux1-dev.safetensors">Flux 1 Dev</option>
                    <option value="flux1-schnell.safetensors">Flux 1 Schnell</option>
                    <option value="flux1-schnell-fp8.safetensors">Flux 1 Schnell fp8</option>
                    <option value="geminiproxy">GeminiProxy</option>
                </select>
            </h1>
            <div class="tab-bar">
                <div class="tab active" id="tab-config" onclick="switchTab('config')">⚙️ Config</div>
                <div class="tab" id="tab-narration" onclick="switchTab('narration')">🎙️ Narration</div>
                <div class="tab" id="tab-cref" onclick="switchTab('cref')">👥 CREF</div>
                <div class="tab" id="tab-prompts" onclick="switchTab('prompts')">📝 Prompts</div>
                <div class="tab" id="tab-clips" onclick="switchTab('clips')">🎬 Clips</div>
                <div class="tab" id="tab-thumbnail" onclick="switchTab('thumbnail')">🖼️ Thumbnail</div>
                <div class="tab" id="tab-browse" onclick="switchTab('browse')">📁 Browse</div>
                <div style="flex:1;"></div>
                <div class="tab" id="tab-play" onclick="switchTab('play')" style="display:none; background:#1a472a; color:#90ee90; border-color:#2d6a4f;">▶ Play</div>
            </div>
            <div class="tab-content" id="tabContent">
                <!-- Config tab (default) -->
                <div id="panel-config">
                    <div class="form-group">
                        <label>Title:</label>
                        <input type="text" id="title" style="flex:1;">
                        <button onclick="suggestTitle()" style="margin-left:6px; padding:4px 10px; background:#2a6496; color:#fff; border:none; border-radius:4px; cursor:pointer; font-size:12px; white-space:nowrap;">💡 Suggest</button>
                    </div>
                    <div class="form-group">
                        <label>Story Type:</label>
                        <select id="story_type">
                            <option value="children_story">Children Story</option>
                            <option value="fairy_tale">Fairy Tale</option>
                            <option value="adventure">Adventure</option>
                            <option value="educational">Educational</option>
                            <option value="fantasy">Fantasy</option>
                            <option value="comedy">Comedy</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Image Style:</label>
                        <select id="image_style">
                            <option value="3D Render">3D Render</option>
                            <option value="Anime">Anime</option>
                            <option value="Cartoon">Cartoon</option>
                            <option value="Cartoon Reality">Cartoon Reality</option>
                            <option value="Chinese">Chinese</option>
                            <option value="Cinematic">Cinematic</option>
                            <option value="Comic Book">Comic Book</option>
                            <option value="Dark Fantasy">Dark Fantasy</option>
                            <option value="Doodle">Doodle</option>
                            <option value="Flat Design">Flat Design</option>
                            <option value="Infrared Photo">Infrared Photo</option>
                            <option value="Low Poly">Low Poly</option>
                            <option value="Minimalist">Minimalist</option>
                            <option value="Neon/Cyberpunk">Neon/Cyberpunk</option>
                            <option value="Oil Painting">Oil Painting</option>
                            <option value="Pencil Sketch">Pencil Sketch</option>
                            <option value="Pixel Art">Pixel Art</option>
                            <option value="Real Person">Real Person</option>
                            <option value="Retro/Vintage">Retro/Vintage</option>
                            <option value="Stick Figure">Stick Figure</option>
                            <option value="Surrealist">Surrealist</option>
                            <option value="Synthwave">Synthwave</option>
                            <option value="Ukiyo-e">Ukiyo-e</option>
                            <option value="Watercolor">Watercolor</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Transition:</label>
                        <select id="transition_style">
                            <option value="None">None</option>
                            <option value="zoom_in">zoom_in</option>
                            <option value="zoom_out">zoom_out</option>
                            <option value="pan_down">pan_down</option>
                            <option value="pan_up">pan_up</option>
                            <option value="fade">fade</option>
                            <option value="fadewhite">fadewhite</option>
                            <option value="dissolve">dissolve</option>
                            <option value="wipeleft">wipeleft</option>
                            <option value="wiperight">wiperight</option>
                            <option value="wipeup">wipeup</option>
                            <option value="wipedown">wipedown</option>
                            <option value="slideleft">slideleft</option>
                            <option value="slideright">slideright</option>
                            <option value="slideup">slideup</option>
                            <option value="slidedown">slidedown</option>
                            <option value="circlecrop">circlecrop</option>
                            <option value="rectcrop">rectcrop</option>
                            <option value="distance">distance</option>
                            <option value="pixelize">pixelize</option>
                            <option value="radial">radial</option>
                            <option value="zoomin">zoomin</option>
                            <option value="diagbl">diagbl</option>
                            <option value="diagbr">diagbr</option>
                            <option value="diagtl">diagtl</option>
                            <option value="diagtr">diagtr</option>
                            <option value="hlslice">hlslice</option>
                            <option value="hrslice">hrslice</option>
                            <option value="vuslice">vuslice</option>
                            <option value="vdslice">vdslice</option>
                            <option value="smoothleft">smoothleft</option>
                            <option value="smoothright">smoothright</option>
                            <option value="smoothup">smoothup</option>
                            <option value="smoothdown">smoothdown</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Trans Duration (s):</label>
                        <input type="number" id="transition_duration" step="0.1" min="0" value="1.0" style="width:60px; flex:none;">
                    </div>
                    <div class="form-group">
                        <label>Voice:</label>
                        <select id="voice_model">
                            <option value="en-US-AnaNeural">Ana (Female, Young)</option>
                            <option value="en-US-JennyNeural">Jenny (Female)</option>
                            <option value="en-US-AriaNeural">Aria (Female, Expressive)</option>
                            <option value="en-US-GuyNeural">Guy (Male)</option>
                            <option value="en-US-DavisNeural">Davis (Male, Casual)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Voice Rate:</label>
                        <select id="voice_rate">
                            <option value="-30%">Slow (-30%)</option>
                            <option value="-20%">Slower (-20%)</option>
                            <option value="-10%">Slightly Slow (-10%)</option>
                            <option value="+0%">Normal</option>
                        </select>
                    </div>
                    <div class="form-group" id="videoModelGroup">
                        <label>Video Model:</label>
                        <select id="video_model">
                            <option value="wan2.1_i2v_480p_14B_fp8_scaled.safetensors">WAN 2.1 i2v 480p fp8 (fast)</option>
                            <option value="wan2.1_i2v_480p_14B_fp16.safetensors">WAN 2.1 i2v 480p fp16</option>
                            <option value="wan2.1_i2v_720p_14B_fp8_scaled.safetensors">WAN 2.1 i2v 720p fp8</option>
                            <option value="wan2.1_i2v_720p_14B_fp16.safetensors">WAN 2.1 i2v 720p fp16</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Clip Count <span style="color:#888;font-weight:normal;">(0 = all)</span>:</label>
                        <input type="number" id="clip_count" min="0" value="0" style="width:60px; flex:none;">
                    </div>
                    <div class="form-group">
                        <label>Video:</label>
                        <input type="checkbox" id="generate_video" checked style="width:auto; flex:none;" onchange="toggleImageModel()">
                        <span style="font-size:12px; color:#888;">unchecked = image only</span>
                    </div>
                    <div class="form-group">
                        <label>Pipeline Steps:</label>
                        <div style="display:flex; flex-wrap:wrap; gap:12px; margin-top:4px;">
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_narration" checked style="width:auto;" /> Narration
                            </label>
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_prep_cref" checked style="width:auto;" /> Prep CREF
                            </label>
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_prompts" checked style="width:auto;" /> Prompts
                            </label>
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_thumbnail" checked style="width:auto;" /> Thumbnail
                            </label>
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_clips" checked style="width:auto;" /> Clips
                            </label>
                            <label style="font-size:13px; cursor:pointer; display:flex; align-items:center; gap:4px;">
                                <input type="checkbox" id="step_assemble" checked style="width:auto;" /> Assemble
                            </label>
                        </div>
                    </div>
                    <br>
                    <button class="btn-save" onclick="saveConfig()">Save</button>
                </div>
                <!-- Prompts tab -->
                <div id="panel-prompts" style="display:none;">
                    <div id="promptsContent" class="prompts-content">Select a project to view prompts.</div>
                </div>
                <!-- Clips tab -->
                <div id="panel-clips" style="display:none;">
                    <div class="clips-grid" id="clipsList"><p style="color:#888;">Select a project to view clips.</p></div>
                </div>
                <!-- Narration tab -->
                <div id="panel-narration" style="display:none;">
                    <textarea id="narrationEditor" style="width:100%; height:500px; font-family:monospace; font-size:12px; padding:8px; box-sizing:border-box; resize:vertical;" placeholder="Narration will appear here..."></textarea>
                    <br>
                    <button class="btn-save" onclick="saveNarration()" style="margin-top:8px;">💾 Save Narration</button>
                </div>
                <!-- CREF tab -->
                <div id="panel-cref" style="display:none;">
                    <div id="crefContent" class="cref-grid">Select a project to view characters.</div>
                </div>
                <!-- Thumbnail tab -->
                <div id="panel-thumbnail" style="display:none;">
                    <div style="display:flex; gap:16px; flex-wrap:wrap;">
                        <!-- Left: image preview + regenerate -->
                        <div style="flex:1; min-width:260px;">
                            <div id="thumbPreviewWrap" style="background:#111; border:1px solid #444; border-radius:6px; overflow:hidden; min-height:160px; display:flex; align-items:center; justify-content:center; cursor:pointer;" onclick="regenerateThumbnail()" title="Click to regenerate">
                                <img id="thumbPreview" src="" alt="" style="max-width:100%; max-height:340px; display:none; object-fit:contain; border-radius:6px; cursor:pointer;" onclick="regenerateThumbnail()" title="Click to regenerate">
                                <span id="thumbNoImage" style="color:#666; font-size:12px;">No thumbnail yet</span>
                            </div>
                        </div>
                        <!-- Right: controls -->
                        <div style="flex:1.4; min-width:260px; display:flex; flex-direction:column; gap:8px;">
                            <!-- Caption Position -->
                            <div class="form-group">
                                <label style="width:90px;">Caption Pos:</label>
                                <div style="display:flex; gap:3px;">
                                    <button id="cappos-top"    onclick="setCapPos('top')"    style="padding:2px 7px; font-size:11px; border-radius:3px; border:1px solid #ccc; background:#e9ecef; cursor:pointer;">top</button>
                                    <button id="cappos-middle" onclick="setCapPos('middle')" style="padding:2px 7px; font-size:11px; border-radius:3px; border:1px solid #ccc; background:#e9ecef; cursor:pointer;">middle</button>
                                    <button id="cappos-bottom" onclick="setCapPos('bottom')" style="padding:2px 7px; font-size:11px; border-radius:3px; border:1px solid #ccc; background:#e9ecef; cursor:pointer;">bottom</button>
                                    <button id="cappos-none"   onclick="setCapPos('none')"   style="padding:2px 7px; font-size:11px; border-radius:3px; border:1px solid #ccc; background:#e9ecef; cursor:pointer;">none</button>
                                </div>
                            </div>
                            <!-- Font -->
                            <div class="form-group">
                                <label style="width:90px;">Font:</label>
                                <select id="thumb_font_name" style="flex:1;">
                                    <option>Comic Sans MS</option>
                                    <option>DejaVu Sans</option>
                                    <option>DejaVu Serif</option>
                                    <option>Liberation Sans</option>
                                    <option>Liberation Serif</option>
                                    <option>Noto Sans</option>
                                </select>
                                <input type="range" id="thumb_font_size" min="0.2" max="2.75" step="0.05" value="1.0"
                                    oninput="document.getElementById('thumb_font_size_lbl').textContent=Math.round(this.value*100)+'%'"
                                    style="width:80px; margin-left:8px;" title="Font size multiplier">
                                <span id="thumb_font_size_lbl" style="font-size:11px; color:#666; width:36px; text-align:right;">100%</span>
                            </div>
                            <!-- BG / Shadow -->
                            <div class="form-group">
                                <label style="width:90px;">BG/Shadow:</label>
                                <input type="range" id="thumb_bg_opacity" min="0" max="255" value="180"
                                    oninput="document.getElementById('thumb_bg_lbl').textContent=this.value"
                                    style="flex:1;" title="Background opacity (0=transparent)">
                                <span id="thumb_bg_lbl" style="font-size:11px; color:#666; width:28px; margin:0 6px; text-align:right;">180</span>
                                <input type="range" id="thumb_shadow" min="0" max="10" value="0"
                                    oninput="document.getElementById('thumb_shadow_lbl').textContent=this.value+'px'"
                                    style="width:60px;" title="Shadow offset (px)">
                                <span id="thumb_shadow_lbl" style="font-size:11px; color:#666; width:30px; text-align:right;">0px</span>
                            </div>
                            <!-- Rebake button -->
                            <button onclick="rebakeThumbnail()" style="padding:5px 12px; background:#555; color:#fff; border:none; border-radius:4px; cursor:pointer; font-size:12px; align-self:flex-start;">
                                🎨 Rebake Caption
                            </button>
                            <hr style="border:none; border-top:1px solid #444; margin:4px 0;">
                            <!-- Description -->
                            <div style="position:relative; border-left:2px solid #4fc3f7; padding-left:10px;">
                                <span style="font-size:10px; text-transform:uppercase; color:#4fc3f7; letter-spacing:1px;">Description</span>
                                <button onclick="copyField('thumbDescText', 'Description')" title="Copy description"
                                    style="position:absolute; top:0; right:0; background:none; border:none; cursor:pointer; color:#4fc3f7; font-size:13px; padding:0; opacity:0.6; line-height:1;"
                                    onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.6">📋</button>
                                <div id="thumbDescText" style="background:#1a2a30; color:#e0f4ff; font-size:12px; line-height:1.6; margin-top:4px; padding:6px 8px; border-radius:4px; white-space:pre-wrap;"></div>
                            </div>
                            <!-- Tags -->
                            <div style="position:relative; border-left:2px solid #8be9fd; padding-left:10px;">
                                <span style="font-size:10px; text-transform:uppercase; color:#8be9fd; letter-spacing:1px;">Tags</span>
                                <button onclick="copyField('thumbTagsText', 'Tags')" title="Copy tags"
                                    style="position:absolute; top:0; right:0; background:none; border:none; cursor:pointer; color:#4fc3f7; font-size:13px; padding:0; opacity:0.6; line-height:1;"
                                    onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.6">📋</button>
                                <div id="thumbTagsText" style="background:#1a2a1a; color:#c8f5c8; font-size:12px; margin-top:4px; padding:6px 8px; border-radius:4px;"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- Browse tab -->
                <div id="panel-browse" style="display:none;">
                    <div id="browseGrid" style="display:grid; grid-template-columns:1fr; gap:2px;"></div>
                </div>
                <!-- Play tab -->
                <div id="panel-play" style="display:none; text-align:center;">
                    <video id="playVideo" controls style="max-width:100%; max-height:480px; border-radius:6px; background:#000;"></video>
                </div>
            </div>
        </div>

        <div class="log-panel" id="logPanel">
            <div style="display:flex; gap:0; margin-bottom:8px; border-bottom:1px solid #444;">
                <div id="logSubTab-activity" class="log-subtab active" onclick="switchLogSubTab('activity')" style="flex:1; text-align:center; padding:6px 8px; font-size:11px; cursor:pointer; background:#333; color:#fff; border-radius:4px 4px 0 0;">📋 Activity</div>
                <div id="logSubTab-prompt" class="log-subtab" onclick="switchLogSubTab('prompt')" style="flex:1; text-align:center; padding:6px 8px; font-size:11px; cursor:pointer; background:#222; color:#888; border-radius:4px 4px 0 0;">💬 Prompts</div>
            </div>
            <div id="logPanelActivity" style="flex:1; display:flex; flex-direction:column; overflow:hidden;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="color:#fff; font-size:12px; font-weight:bold;">Activity Log</span>
                    <button onclick="clearLog()" style="background:#555; color:#ccc; border:none; padding:2px 8px; font-size:10px; border-radius:3px; cursor:pointer;">Clear</button>
                </div>
                <div id="logContent" style="flex:1; overflow-y:auto; overflow-x:hidden;"></div>
            </div>
            <div id="logPanelPrompt" style="flex:1; display:none; flex-direction:column; overflow:hidden;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="color:#fff; font-size:12px; font-weight:bold;">Prompt Log</span>
                    <button onclick="clearPromptLog()" style="background:#555; color:#ccc; border:none; padding:2px 8px; font-size:10px; border-radius:3px; cursor:pointer;">Clear</button>
                </div>
                <div id="promptLogContent" style="flex:1; overflow-y:auto; overflow-x:hidden;"></div>
            </div>
        </div>
        <div id="logToggle" style="position:fixed; right:0; top:50%; transform:translateY(-50%); background:#333; color:#fff; padding:12px 6px; cursor:pointer; border-radius:6px 0 0 6px; font-size:14px; z-index:1000;" onclick="toggleLogPanel()" title="Toggle Logs">◀</div>
    </div>
    
    <script>
        function toggleImageModel() {
            const videoModelGroup = document.getElementById('videoModelGroup');
            const isVideo = document.getElementById('generate_video').checked;
            videoModelGroup.style.opacity = isVideo ? '1' : '0.4';
            videoModelGroup.style.pointerEvents = isVideo ? 'auto' : 'none';
        }

        function log(message, type = 'info') {
            const logContent = document.getElementById('logContent');
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-${type}">${message}</span>`;
            logContent.appendChild(entry);
            requestAnimationFrame(() => { logContent.scrollTop = logContent.scrollHeight; });
            fetch('/api/log', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({time, message, type})
            });
        }

        function clearLog() {
            document.getElementById('logContent').innerHTML = '';
            fetch('/api/log/clear', {method: 'POST'});
        }

        function logPrompt(helper, prompt) {
            const promptLogContent = document.getElementById('promptLogContent');
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-info">${helper}:</span> <span style="color:#ccc;">${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`;
            promptLogContent.appendChild(entry);
            requestAnimationFrame(() => { promptLogContent.scrollTop = promptLogContent.scrollHeight; });
            fetch('/api/log/prompt', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({time, helper, prompt})
            });
        }

        function clearPromptLog() {
            document.getElementById('promptLogContent').innerHTML = '';
            fetch('/api/log/prompt/clear', {method: 'POST'});
        }

        function loadPromptLog() {
            const promptLogContent = document.getElementById('promptLogContent');
            fetch('/api/log/prompt/load')
                .then(r => r.json())
                .then(data => {
                    promptLogContent.innerHTML = '';
                    (data.lines || []).forEach(entry => {
                        const div = document.createElement('div');
                        div.className = 'log-entry';
                        div.innerHTML = `<span class="log-time">[${entry.time}]</span> <span class="log-info">${entry.helper}:</span> <span style="color:#ccc;">${entry.prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`;
                        promptLogContent.appendChild(div);
                    });
                    requestAnimationFrame(() => { promptLogContent.scrollTop = promptLogContent.scrollHeight; });
                });
        }

        function checkComfyQueue() {
            log('Checking ComfyUI queue...');
            fetch('/api/comfy/queue')
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        log('ComfyUI error: ' + data.error, 'error');
                    } else {
                        const pending = (data.queue_pending || []).length;
                        const running = (data.queue_running || []).length;
                        log(`Comfy : Pending ${pending}, Running - ${running}`, 'info');
                    }
                })
                .catch(err => {
                    log('Failed to reach ComfyUI: ' + err, 'error');
                });
        }
        
        const TABS = ['config', 'narration', 'cref', 'prompts', 'clips', 'thumbnail', 'browse', 'play'];

        function switchTab(name) {
            TABS.forEach(t => {
                const tabEl = document.getElementById('tab-' + t);
                if (tabEl) tabEl.classList.toggle('active', t === name);
                const panelEl = document.getElementById('panel-' + t);
                if (panelEl) panelEl.style.display = t === name ? 'block' : 'none';
            });
            const title = document.getElementById('projectSelect').value;
            if (name === 'config') loadConfig(title);
            if (name === 'narration') loadNarration(title);
            if (name === 'cref') loadCref(title);
            if (name === 'prompts') loadPrompts(title);
            if (name === 'clips') loadClips(title);
            if (name === 'thumbnail') loadThumbnail(title);
            if (name === 'browse') loadBrowse(title);
            if (name === 'play') loadPlay(title);
        }

        function switchLogSubTab(name) {
            const activityTab = document.getElementById('logSubTab-activity');
            const promptTab = document.getElementById('logSubTab-prompt');
            if (name === 'activity') {
                activityTab.style.background = '#333';
                activityTab.style.color = '#fff';
                promptTab.style.background = '#222';
                promptTab.style.color = '#888';
            } else {
                promptTab.style.background = '#333';
                promptTab.style.color = '#fff';
                activityTab.style.background = '#222';
                activityTab.style.color = '#888';
            }
            document.getElementById('logPanelActivity').style.display = name === 'activity' ? 'flex' : 'none';
            document.getElementById('logPanelPrompt').style.display = name === 'prompt' ? 'flex' : 'none';
            if (name === 'activity') {
                const logContent = document.getElementById('logContent');
                if (logContent) logContent.scrollTop = logContent.scrollHeight;
            } else {
                const promptLogContent = document.getElementById('promptLogContent');
                if (promptLogContent) promptLogContent.scrollTop = promptLogContent.scrollHeight;
            }
        }

        function toggleLogPanel() {
            const logPanel = document.getElementById('logPanel');
            const logToggle = document.getElementById('logToggle');
            if (logPanel.style.display === 'none') {
                logPanel.style.display = 'flex';
                logToggle.innerHTML = '▶';
            } else {
                logPanel.style.display = 'none';
                logToggle.innerHTML = '◀';
            }
        }

        let _browseSubpath = '';

        function loadBrowse(title, subpath) {
            if (subpath === undefined) subpath = '';
            _browseSubpath = subpath;
            const grid = document.getElementById('browseGrid');
            grid.innerHTML = '<div style="color:#888; font-size:12px;">Loading...</div>';
            if (!title) { grid.innerHTML = '<div style="color:#888; font-size:12px;">No project selected.</div>'; return; }
            let url = `/api/browse?title=${encodeURIComponent(title)}`;
            if (subpath) url += `&subpath=${encodeURIComponent(subpath)}`;
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    grid.innerHTML = '';
                    // Up button
                    if (subpath) {
                        const upRow = document.createElement('div');
                        upRow.style.cssText = 'display:flex; align-items:center; gap:8px; padding:4px 6px; border-radius:4px; background:#e8f0fe; font-size:12px; font-family:monospace; cursor:pointer;';
                        upRow.title = 'Go up';
                        upRow.innerHTML = '<span style="font-size:14px;">⬆️</span><span style="flex:1;">.. (up)</span>';
                        upRow.onclick = () => {
                            const parts = subpath.split('/').filter(Boolean);
                            parts.pop();
                            loadBrowse(title, parts.join('/'));
                        };
                        grid.appendChild(upRow);
                    }
                    if (!data.files || data.files.length === 0) {
                        const empty = document.createElement('div');
                        empty.style.cssText = 'color:#888; font-size:12px; padding:4px 6px;';
                        empty.textContent = 'Empty folder.';
                        grid.appendChild(empty);
                        return;
                    }
                    data.files.forEach(f => {
                        const row = document.createElement('div');
                        row.style.cssText = 'display:flex; align-items:center; gap:8px; padding:4px 6px; border-radius:4px; background:#f8f9fa; font-size:12px; font-family:monospace;';
                        const icon = f.is_dir ? '📁' : fileIcon(f.name);
                        const nameSpan = document.createElement('span');
                        nameSpan.style.cssText = 'font-size:14px;';
                        nameSpan.textContent = icon;
                        const labelSpan = document.createElement('span');
                        labelSpan.style.cssText = 'flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;';
                        labelSpan.title = f.name;
                        labelSpan.textContent = f.name;
                        const sizeSpan = document.createElement('span');
                        sizeSpan.style.cssText = 'color:#888; white-space:nowrap;';
                        sizeSpan.textContent = f.size;
                        const delBtn = document.createElement('button');
                        delBtn.style.cssText = 'background:none; border:none; color:#c00; cursor:pointer; font-size:13px; line-height:1; padding:0 2px;';
                        delBtn.title = 'Delete';
                        delBtn.textContent = '✕';
                        delBtn.setAttribute('type', 'button');
                        delBtn.setAttribute('data-action', 'delete');
                        delBtn.setAttribute('data-name', f.name);
                        delBtn.setAttribute('data-subpath', subpath || '');
                        row.appendChild(nameSpan);
                        row.appendChild(labelSpan);
                        if (f.size) {
                        row.appendChild(sizeSpan);
                        }
                        row.appendChild(delBtn);
                        if (f.is_dir) {
                            row.style.cursor = 'pointer';
                            row.title = 'Click to open';
                            row.onclick = (e) => {
                                if (e.target === delBtn) return;
                                const newPath = subpath ? subpath + '/' + f.name : f.name;
                                loadBrowse(title, newPath);
                            };
                        } else {
                            row.style.cursor = 'pointer';
                            row.title = 'Click to view';
                            row.onclick = (e) => {
                                if (e.target === delBtn) return;
                                openBrowseFile(title, subpath, f.name);
                            };
                        }
                        grid.appendChild(row);
                    });
                })
                .catch(() => { grid.innerHTML = '<div style="color:red; font-size:12px;">Failed to load.</div>'; });
        }

        function fileIcon(name) {
            const ext = name.split('.').pop().toLowerCase();
            const map = {mp4:'🎬', mp3:'🎵', wav:'🎵', png:'🖼️', jpg:'🖼️', jpeg:'🖼️', webp:'🖼️', txt:'📄', json:'📋', py:'🐍'};
            return map[ext] || '📄';
        }

        function deleteBrowseEntry(btn, title, name, subpath) {
            if (!confirm(`Delete "${name}"?`)) return;
            fetch('/api/browse/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, name, subpath: subpath || ''})
            })
            .then(r => r.json())
            .then(d => { if (d.ok) btn.closest('div[style]').remove(); else alert(d.error); });
        }

        function openBrowseFile(title, subpath, name) {
            const grid = document.getElementById('browseGrid');
            const url = `/api/browse/file?title=${encodeURIComponent(title)}&subpath=${encodeURIComponent(subpath||'')}&name=${encodeURIComponent(name)}`;
            const ext = name.split('.').pop().toLowerCase();
            const closeBtn = `<button onclick="loadBrowse('${title.replace(/'/g,"\\'")}','${(subpath||'').replace(/'/g,"\\'")}');" style="margin-bottom:8px; padding:3px 12px; background:#555; color:#fff; border:none; border-radius:4px; cursor:pointer; font-size:12px;">✕ Close</button>`;
            const label = `<div style="font-size:11px; color:#888; margin-bottom:6px; font-family:monospace;">${name}</div>`;
            let viewer = '';
            if (['png','jpg','jpeg','webp','gif'].includes(ext)) {
                viewer = `<img src="${url}" style="max-width:100%; max-height:70vh; border-radius:4px; display:block;">`;
            } else if (['mp4','webm'].includes(ext)) {
                viewer = `<video src="${url}" controls autoplay style="max-width:100%; max-height:70vh; border-radius:4px; display:block;"></video>`;
            } else if (['mp3','wav','ogg'].includes(ext)) {
                viewer = `<audio src="${url}" controls style="width:100%; margin-top:8px;"></audio>`;
            } else {
                // text-based: fetch and display
                grid.innerHTML = closeBtn + label + '<pre style="background:#f4f4f4; padding:10px; border-radius:4px; font-size:11px; overflow:auto; max-height:70vh; white-space:pre-wrap; word-break:break-all;">Loading...</pre>';
                fetch(url).then(r => r.text()).then(text => {
                    grid.querySelector('pre').textContent = text;
                }).catch(() => { grid.querySelector('pre').textContent = 'Failed to load.'; });
                return;
            }
            grid.innerHTML = closeBtn + label + viewer;
        }

        function loadPlay(title) {
            if (!title) return;
            window.open(`/api/video?title=${encodeURIComponent(title)}&t=${Date.now()}`, '_blank');
        }

        function checkPlayTab(title) {
            const tab = document.getElementById('tab-play');
            if (!title) { tab.style.display = 'none'; return; }
            fetch(`/api/video/exists?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => { tab.style.display = data.exists ? 'block' : 'none'; });
        }

        function loadThumbnail(title) {
            if (!title) return;
            const img = document.getElementById('thumbPreview');
            const noImg = document.getElementById('thumbNoImage');
            const ts = Date.now();
            img.src = `/api/thumbnail?title=${encodeURIComponent(title)}&t=${ts}`;
            img.onload = () => { img.style.display = 'block'; noImg.style.display = 'none'; };
            img.onerror = () => { img.style.display = 'none'; noImg.style.display = 'block'; };

            fetch(`/api/description?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    const content = data.content || '';
                    const descMatch = content.match(/Description:\n([\s\S]*?)\n\nTags:/);
                    const tagsMatch = content.match(/Tags:\s*(.+)/);
                    document.getElementById('thumbDescText').textContent = descMatch ? descMatch[1].trim() : '';
                    document.getElementById('thumbTagsText').textContent = tagsMatch ? tagsMatch[1].trim() : '';
                });

            // Sync controls from project config
            fetch(`/api/config?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    const thumbModel = data.thumb_image_model || data.image_model;
                    if (thumbModel) document.getElementById('image_model').value = thumbModel;
                    if (data.image_style) document.getElementById('image_style').value = data.image_style;
                    const capPos = data.thumb_caption_position || 'bottom';
                    setCapPos(capPos, false);
                    if (data.thumb_font_name) document.getElementById('thumb_font_name').value = data.thumb_font_name;
                    if (data.thumb_font_size !== undefined) {
                        document.getElementById('thumb_font_size').value = data.thumb_font_size;
                        document.getElementById('thumb_font_size_lbl').textContent = Math.round(data.thumb_font_size * 100) + '%';
                    }
                    if (data.thumb_bg_opacity !== undefined) {
                        document.getElementById('thumb_bg_opacity').value = data.thumb_bg_opacity;
                        document.getElementById('thumb_bg_lbl').textContent = data.thumb_bg_opacity;
                    }
                    if (data.thumb_shadow !== undefined) {
                        document.getElementById('thumb_shadow').value = data.thumb_shadow;
                        document.getElementById('thumb_shadow_lbl').textContent = data.thumb_shadow + 'px';
                    }
                });
        }

        let _capPos = 'bottom';
        function setCapPos(pos, save = true) {
            _capPos = pos;
            ['top','middle','bottom','none'].forEach(p => {
                const btn = document.getElementById('cappos-' + p);
                if (btn) btn.style.background = p === pos ? '#4a90d9' : '#e9ecef';
                if (btn) btn.style.color = p === pos ? '#fff' : '#333';
            });
        }

        function rebakeThumbnail() {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            log('Rebaking caption...');
            fetch('/api/thumbnail/rebake', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title,
                    caption_position: _capPos,
                    font_name: document.getElementById('thumb_font_name').value,
                    font_size: parseFloat(document.getElementById('thumb_font_size').value),
                    bg_opacity: parseInt(document.getElementById('thumb_bg_opacity').value),
                    shadow_offset: parseInt(document.getElementById('thumb_shadow').value),
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') { log('✓ Caption rebaked', 'success'); loadThumbnail(title); }
                else log('✗ ' + (data.error || 'Failed'), 'error');
            });
        }

        function regenerateThumbnail() {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            const imageModel = document.getElementById('image_model').value;
            const imageStyle = document.getElementById('image_style').value;
            const aiHelper = document.getElementById('ai_helper').value;
            const wrap = document.getElementById('thumbPreviewWrap');
            wrap.style.cursor = 'wait';
            document.body.style.cursor = 'wait';
            log('Regenerating thumbnail...');
            startPolling();
            fetch('/api/thumbnail/regenerate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, image_model: imageModel, image_style: imageStyle, ai_helper: aiHelper})
            })
            .then(r => r.json())
            .then(data => {
                wrap.style.cursor = 'pointer';
                document.body.style.cursor = '';
                if (data.status === 'ok') {
                    log('✓ Thumbnail regenerated', 'success');
                    loadThumbnail(title);
                } else {
                    log('✗ ' + (data.error || 'Failed'), 'error');
                }
            })
            .catch(() => { wrap.style.cursor = 'pointer'; document.body.style.cursor = ''; });
        }

        function captureThumbnail() {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            log('Capturing thumbnail from browser...');
            fetch('/api/thumbnail/capture', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    log('✓ Thumbnail captured', 'success');
                    loadThumbnail(title);
                } else {
                    log('✗ ' + (data.error || 'Failed'), 'error');
                }
            });
        }

        function copyField(elementId, label) {
            const text = document.getElementById(elementId).textContent.trim();
            if (!text) return;
            navigator.clipboard.writeText(text).then(() => log(`✓ ${label} copied`, 'success'));
        }

        function suggestTitle() {
            const aiHelper = document.getElementById('ai_helper').value;
            const storyType = document.getElementById('story_type').value;
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = '⏳ Suggesting...';
            document.body.style.cursor = 'wait';
            fetch('/api/suggest-title', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ai_helper: aiHelper, story_type: storyType})
            })
            .then(r => r.json())
            .then(data => {
                btn.disabled = false;
                btn.textContent = '💡 Suggest';
                document.body.style.cursor = '';
                if (data.title) {
                    document.getElementById('title').value = data.title;
                    log(`💡 Suggested: ${data.title}`, 'success');
                } else {
                    log('✗ ' + (data.error || 'No suggestion returned'), 'error');
                }
            })
            .catch(e => {
                btn.disabled = false;
                btn.textContent = '💡 Suggest';
                document.body.style.cursor = '';
                log('✗ Suggest failed: ' + e.message, 'error');
            });
        }

        function loadConfig(title) {
            if (!title) return;
            fetch(`/api/config?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('title').value = title;
                    document.getElementById('story_type').value = data.story_type || 'children_story';
                    document.getElementById('image_style').value = data.image_style || 'cartoon';
                    document.getElementById('voice_model').value = data.voice_model || 'en-US-AnaNeural';
                    document.getElementById('voice_rate').value = data.voice_rate || '-20%';
                    document.getElementById('video_model').value = data.video_model || 'wan2.1_i2v_480p_14B_fp8_scaled.safetensors';
                    document.getElementById('clip_count').value = data.clip_count !== undefined ? data.clip_count : 0;
                    document.getElementById('ai_helper').value = data.ai_helper || 'opencode';
                    document.getElementById('generate_video').checked = data.generate_video !== false;
                    document.getElementById('image_model').value = data.image_model || 'Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors';
                    document.getElementById('transition_style').value = data.transition_style || 'None';
                    document.getElementById('transition_duration').value = data.transition_duration !== undefined ? data.transition_duration : 1.0;
                    document.getElementById('step_narration').checked = data.step_narration !== false;
                    document.getElementById('step_prep_cref').checked = data.step_prep_cref !== false;
                    document.getElementById('step_prompts').checked = data.step_prompts !== false;
                    document.getElementById('step_thumbnail').checked = data.step_thumbnail !== false;
                    document.getElementById('step_clips').checked = data.step_clips !== false;
                    document.getElementById('step_assemble').checked = data.step_assemble !== false;
                    toggleImageModel();
                });
        }

        function loadPrompts(title) {
            if (!title) return;
            const container = document.getElementById('promptsContent');
            Promise.all([
                fetch(`/api/prompts?title=${encodeURIComponent(title)}`).then(r => r.json()),
                fetch(`/api/clips?title=${encodeURIComponent(title)}`).then(r => r.json()),
                fetch(`/api/cref?title=${encodeURIComponent(title)}`).then(r => r.json())
            ]).then(([promptData, clipData, crefData]) => {
                    if (!promptData.prompts || promptData.prompts.length === 0) {
                        container.innerHTML = '<p style="color:#888;">No prompts found. Run the pipeline first.</p>';
                        return;
                    }
                    const clips = clipData.clips || [];
                    const characters = crefData.characters || [];
                    container.innerHTML = `
                        <table class="prompts-table">
                            <thead><tr><th>#</th><th>Sentence</th><th>Raw Prompt</th><th>CREF</th><th>Final Prompt</th><th>Image</th></tr></thead>
                            <tbody>${promptData.prompts.map((p, i) => {
                                const clipName = `clip_${String(i + 1).padStart(2, '0')}.png`;
                                const hasClip = clips.includes(clipName);
                                const imgCell = hasClip
                                    ? `<img src="/api/clip-image?title=${encodeURIComponent(title)}&name=${encodeURIComponent(clipName)}" 
                                            alt="${clipName}" 
                                            onclick="regenerateClipImage(${i}, '${clipName}')"
                                            style="cursor: pointer; transition: opacity 0.2s;"
                                            title="Click to regenerate image">`
                                    : `<div style="padding:10px; color:#999; cursor:pointer;" onclick="regenerateClipImage(${i}, '${clipName}')">Click to generate</div>`;
                                const crefCheckboxes = characters.map(c => {
                                    const fullDesc = c.description ? `${c.name}, ${c.description}` : c.name;
                                    const isChecked = p.prompt.includes(c.name);
                                    return `<label style="display:block; margin:2px 0; font-size:11px; cursor:pointer;">
                                        <input type="checkbox" 
                                               ${isChecked ? 'checked' : ''} 
                                               onchange="toggleCref(${i}, '${c.name.replace(/'/g, "\\'")}', '${fullDesc.replace(/'/g, "\\'")}', this.checked)"
                                               style="margin-right:4px;">
                                        ${c.name}
                                    </label>`;
                                }).join('');
                                return `<tr>
                                    <td class="prompt-num">${i + 1}</td>
                                    <td class="prompt-sentence">${p.sentence || ''}</td>
                                    <td class="prompt-sentence">${p.raw || p.sentence}</td>
                                    <td style="white-space:nowrap; padding:8px;">${crefCheckboxes}</td>
                                    <td class="prompt-text">
                                        <textarea id="prompt-txt-${i}" style="width:100%; height:100%; min-height:185px; font-size:11px; font-family:monospace; padding:4px; margin:0; display:block; box-sizing:border-box; border:1px solid #eee; border-radius:4px; resize:none; overflow-y:auto;">${p.prompt}</textarea>
                                    </td>
                                    <td class="prompt-img" id="prompt-img-cell-${i}">${imgCell}</td>
                                </tr>`;
                            }).join('')}</tbody>
                        </table>
                    `;
                });
        }

        function toggleCref(idx, charName, fullDesc, isChecked) {
            const textarea = document.getElementById(`prompt-txt-${idx}`);
            if (!textarea) return;
            let prompt = textarea.value;
            if (isChecked) {
                const firstPeriod = prompt.indexOf('. ');
                if (firstPeriod !== -1) {
                    prompt = prompt.substring(0, firstPeriod + 2) + fullDesc + ', ' + prompt.substring(firstPeriod + 2);
                } else {
                    prompt = fullDesc + ', ' + prompt;
                }
            } else {
                // Extract just the description part (after "Name, ")
                const descOnly = fullDesc.includes(',') ? fullDesc.substring(fullDesc.indexOf(',') + 1).trim() : fullDesc;
                
                // Try removing fullDesc first, then just description
                const patterns = [fullDesc, descOnly];
                for (const p of patterns) {
                    if (!p) continue;
                    // Escape regex special chars, but keep commas as literal
                    const escaped = p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    // Match with optional surrounding commas and spaces
                    const regex = new RegExp(',?\\s*' + escaped + '\\s*,?', 'g');
                    prompt = prompt.replace(regex, ', ');
                }
                
                // Clean up: remove double commas, leading/trailing commas, extra spaces
                prompt = prompt.replace(/,\s*,/g, ',').replace(/^,\s*/, '').replace(/,\s*$/, '');
                prompt = prompt.replace(/\.  /g, '. ');
            }
            textarea.value = prompt;
        }

        function regenerateClipImage(idx, clipName) {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            const textarea = document.getElementById(`prompt-txt-${idx}`);
            if (!textarea) {
                // Prompts tab not loaded — fetch prompt from API then proceed
                fetch(`/api/prompts?title=${encodeURIComponent(title)}`)
                    .then(r => r.json())
                    .then(data => {
                        const p = data.prompts && data.prompts[idx];
                        if (!p || !p.prompt) return log('Prompt not found', 'error');
                        _doRegenerateClip(title, idx, clipName, p.prompt.trim(), null);
                    })
                    .catch(() => log('Failed to fetch prompt', 'error'));
                return;
            }
            const editedPrompt = textarea.value.trim();
            if (!editedPrompt) return log('Prompt cannot be empty', 'error');
            _doRegenerateClip(title, idx, clipName, editedPrompt, document.getElementById(`prompt-img-cell-${idx}`));
        }

        function _doRegenerateClip(title, idx, clipName, prompt, cell) {
            let _waitStyle = document.getElementById('_waitCursorStyle');
            if (!_waitStyle) {
                _waitStyle = document.createElement('style');
                _waitStyle.id = '_waitCursorStyle';
                document.head.appendChild(_waitStyle);
            }
            _waitStyle.textContent = '* { cursor: wait !important; }';
            log(`Regenerating ${clipName}...`);

            fetch('/api/clip/regenerate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, clip_name: clipName, prompt, index: idx})
            })
            .then(r => {
                if (!r.ok) return r.text().then(t => { throw new Error(`Server error ${r.status}: ${t.substring(0, 200)}`); });
                return r.json();
            })
            .then(data => {
                document.getElementById('_waitCursorStyle').textContent = '';
                if (data.status === 'ok') {
                    log('✓ Image regenerated', 'success');
                    const newSrc = `/api/clip-image?title=${encodeURIComponent(title)}&name=${encodeURIComponent(clipName)}&_=${Date.now()}`;
                    // Update prompts-table cell if present
                    if (cell) {
                        const imgEl = cell.querySelector('img');
                        if (imgEl) imgEl.src = newSrc;
                        else cell.innerHTML = `<img src="${newSrc}" alt="${clipName}" onclick="regenerateClipImage(${idx}, '${clipName}')" style="cursor:pointer;" title="Click to regenerate image">`;
                    }
                    // Update clips grid card if present
                    document.querySelectorAll('.clip-card img').forEach(img => {
                        if (img.alt === clipName) img.src = newSrc;
                    });
                } else {
                    log('✗ ' + (data.error || 'Failed to regenerate'), 'error');
                }
            })
            .catch(err => {
                document.getElementById('_waitCursorStyle').textContent = '';
                log('✗ ' + err.message, 'error');
            });
        }

        function loadClips(title) {
            if (!title) return;
            fetch(`/api/clips?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('clipsList');
                    container.innerHTML = '';
                    if (!data.clips || data.clips.length === 0) {
                        container.innerHTML = '<p style="color:#888;">No clips found.</p>';
                        return;
                    }
                    data.clips.forEach(c => {
                        const card = document.createElement('div');
                        card.className = 'clip-card';
                        const url = `/api/clip-image?title=${encodeURIComponent(title)}&name=${encodeURIComponent(c)}`;
                        if (c.endsWith('.mp4')) {
                            card.innerHTML = `<video src="${url}" muted></video><div class="clip-label">${c}</div>`;
                            card.querySelector('video').addEventListener('mouseenter', e => e.target.play());
                            card.querySelector('video').addEventListener('mouseleave', e => { e.target.pause(); e.target.currentTime = 0; });
                        } else {
                            const m = c.match(/clip_(\d+)\.png/);
                            const idx = m ? parseInt(m[1], 10) - 1 : -1;
                            card.innerHTML = `<img src="${url}" alt="${c}" style="cursor:pointer;" title="Click to regenerate"><div class="clip-label">${c}</div>`;
                            if (idx >= 0) card.querySelector('img').onclick = () => regenerateClipImage(idx, c);
                        }
                        container.appendChild(card);
                    });
                });
        }

        function loadNarration(title) {
            if (!title) return;
            fetch(`/api/narration?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('narrationEditor').value = data.content || '';
                });
        }

        function saveNarration() {
            const title = document.getElementById('projectSelect').value;
            if (!title) { log('No project selected', 'error'); return; }
            const content = document.getElementById('narrationEditor').value;
            fetch('/api/narration/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, content})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') log('Narration saved', 'success');
                else log('Save failed: ' + (data.error || ''), 'error');
            });
        }

        function loadCref(title) {
            if (!title) return;
            const container = document.getElementById('crefContent');
            fetch(`/api/cref?title=${encodeURIComponent(title)}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.characters || data.characters.length === 0) {
                        container.innerHTML = '<p style="color:#888;">No characters found. Run the pipeline first.</p>';
                        return;
                    }
                    container.innerHTML = data.characters.map((c, i) => `
                        <div class="cref-card">
                            <div id="cref-img-wrap-${i}">
                                ${c.image
                                    ? `<img src="${c.image}" alt="${c.name}" onclick="regenerateCrefImage(${i}, '${c.safe_name}', '${c.name}')" style="cursor:pointer;" title="Double click to regenerate">`
                                    : `<div class="no-image" onclick="regenerateCrefImage(${i}, '${c.safe_name}', '${c.name}')" style="cursor:pointer;" title="Click to generate">No reference image yet</div>`}
                            </div>
                            <div class="cref-card-header">
                                <input class="cref-name-input" id="cref-name-${i}" value="${c.name}" data-original="${c.name}" />
                                <button class="cref-save-icon" onclick="saveCrefDesc(${i})" title="Save">💾</button>
                                <button class="cref-delete-icon" onclick="deleteCrefEntry(${i}, '${c.safe_name}', '${c.name}')" title="Delete">✕</button>
                            </div>
                            <textarea class="cref-desc-editor" id="cref-desc-${i}" data-name="${c.name}">${c.description}</textarea>
                            ${c.narration_words.length ? `<div class="cref-words">${c.narration_words.map(w => `<span class="cref-tag">${w}</span>`).join('')}</div>` : ''}
                        </div>
                    `).join('');
                });
        }

        function saveCrefDesc(index) {
            const title = document.getElementById('projectSelect').value;
            if (!title) { log('No project selected', 'error'); return; }
            const textarea = document.getElementById('cref-desc-' + index);
            const nameInput = document.getElementById('cref-name-' + index);
            const name = nameInput.value.trim();
            const originalName = nameInput.dataset.original;
            const description = textarea.value;
            fetch('/api/cref/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, name, original_name: originalName, description})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    nameInput.dataset.original = name;
                    textarea.dataset.name = name;
                    log(`Saved ${name}`, 'success');
                }
                else log('Save failed: ' + (data.error || ''), 'error');
            });
        }

        function deleteCrefEntry(index, safeName, charName) {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            if (!confirm(`Delete "${charName}" from CREF?`)) return;
            log(`Deleting ${charName}...`);
            fetch('/api/cref/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, name: charName, safe_name: safeName})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    log(`✓ ${charName} deleted`, 'success');
                    loadCref(title);
                } else {
                    log('✗ ' + (data.error || 'Failed to delete'), 'error');
                }
            })
            .catch(err => log('✗ ' + err.message, 'error'));
        }

        function regenerateCrefImage(idx, safeName, charName) {
            const title = document.getElementById('projectSelect').value;
            if (!title) return log('Select a project first', 'error');
            const textarea = document.getElementById(`cref-desc-${idx}`);
            if (!textarea) return log('Description not found', 'error');
            const description = textarea.value.trim();
            if (!description) return log('Description cannot be empty', 'error');

            let _waitStyle = document.getElementById('_waitCursorStyle');
            if (!_waitStyle) {
                _waitStyle = document.createElement('style');
                _waitStyle.id = '_waitCursorStyle';
                document.head.appendChild(_waitStyle);
            }
            _waitStyle.textContent = '* { cursor: wait !important; }';
            log(`Regenerating ${charName}...`);

            fetch('/api/cref/regenerate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, safe_name: safeName, description})
            })
            .then(r => {
                if (!r.ok) return r.text().then(t => { throw new Error(`Server error ${r.status}: ${t.substring(0, 200)}`); });
                return r.json();
            })
            .then(data => {
                document.getElementById('_waitCursorStyle').textContent = '';
                if (data.status === 'ok') {
                    log(`✓ ${charName} regenerated`, 'success');
                    const wrap = document.getElementById(`cref-img-wrap-${idx}`);
                    wrap.innerHTML = `<img src="/api/ref-image?title=${encodeURIComponent(title)}&name=${encodeURIComponent(safeName)}&_=${Date.now()}"
                        alt="${charName}" onclick="regenerateCrefImage(${idx}, '${safeName}', '${charName}')"
                        style="cursor:pointer;" title="Double click to regenerate">`;
                } else {
                    log('✗ ' + (data.error || 'Failed'), 'error');
                }
            })
            .catch(err => {
                document.getElementById('_waitCursorStyle').textContent = '';
                log('✗ ' + err.message, 'error');
            });
        }

        function saveConfig() {
            const config = {
                title: document.getElementById('title').value,
                story_type: document.getElementById('story_type').value,
                image_style: document.getElementById('image_style').value,
                voice_model: document.getElementById('voice_model').value,
                voice_rate: document.getElementById('voice_rate').value,
                video_model: document.getElementById('video_model').value,
                clip_count: parseInt(document.getElementById('clip_count').value) || 0,
                ai_helper: document.getElementById('ai_helper').value,
                generate_video: document.getElementById('generate_video').checked,
                image_model: document.getElementById('image_model').value,
                transition_style: document.getElementById('transition_style').value,
                transition_duration: parseFloat(document.getElementById('transition_duration').value) || 1.0,
                step_narration: document.getElementById('step_narration').checked,
                step_prep_cref: document.getElementById('step_prep_cref').checked,
                step_prompts: document.getElementById('step_prompts').checked,
                step_thumbnail: document.getElementById('step_thumbnail').checked,
                step_clips: document.getElementById('step_clips').checked,
                step_assemble: document.getElementById('step_assemble').checked,
            };
            
            log(`Saving config for: ${config.title}`);
            
            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            })
            .then(r => r.json())
            .then(data => {
                log(`✓ Config saved: ${data.folder}`, 'success');
                loadProjects(data.folder);
            })
            .catch(err => {
                log(`✗ Error: ${err}`, 'error');
            });
        }
        
        // Initial log
        log('Video Generator ready', 'success');

        // Event delegation for browse delete buttons
        document.getElementById('browseGrid').addEventListener('click', function(e) {
            const btn = e.target.closest('[data-action="delete"]');
            if (btn) {
                e.preventDefault();
                e.stopPropagation();
                const title = document.getElementById('projectSelect').value;
                const name = btn.getAttribute('data-name');
                const subpath = btn.getAttribute('data-subpath');
                if (confirm(`Delete "${name}"?`)) {
                    deleteBrowseEntry(btn, title, name, subpath);
                }
            }
        });
        
        function loadProjects(selectTitle) {
            fetch('/api/projects')
                .then(r => r.json())
                .then(projects => {
                    const select = document.getElementById('projectSelect');
                    const current = selectTitle || select.value || localStorage.getItem('lastProject');
                    select.innerHTML = '<option value="">-- Select Project --</option>';
                    projects.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.textContent = p;
                        select.appendChild(opt);
                    });
                    if (current && projects.includes(current)) {
                        select.value = current;
                        localStorage.setItem('lastProject', current);
                        if (selectTitle) loadProject();
                    }
                });
        }

        // Load projects on page load
        loadProjects();
        const _initLast = localStorage.getItem('lastProject');
        if (_initLast) {
            setTimeout(() => {
                const sel = document.getElementById('projectSelect');
                if (sel.value === _initLast) { log(`Loaded project: ${_initLast}`); loadConfig(_initLast); checkPlayTab(_initLast); }
            }, 300);
        }

        function resetProject() {
            const title = document.getElementById('projectSelect').value;
            if (!title) { log('⚠ No project selected', 'error'); return; }
            if (!confirm(`Reset "${title}"? All files except project.json will be deleted.`)) return;
            fetch('/api/reset', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    log(`🗑️ Reset complete — removed ${data.removed} file(s)`, 'success');
                    const activeTab = document.querySelector('.tab.active').id.replace('tab-', '');
                    switchTab(activeTab);
                } else {
                    log(`✗ Reset failed: ${data.error}`, 'error');
                }
            });
        }

        function resetPipelineFlag() {
            const title = document.getElementById('projectSelect').value;
            if (!title) { log('⚠ No project selected', 'error'); return; }
            fetch('/api/reset-pipeline', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    log(`🔄 Pipeline flag reset for "${title}"`, 'success');
                } else {
                    log(`✗ Failed: ${data.error}`, 'error');
                }
            });
        }

        function loadProject() {
            const title = document.getElementById('projectSelect').value;
            if (title) {
                localStorage.setItem('lastProject', title);
                log(`Selected project: ${title}`);
                checkPlayTab(title);
                _browseSubpath = '';
                const activeTab = document.querySelector('.tab.active').id.replace('tab-', '');
                switchTab(activeTab);
            }
        }
        
        let _running = false;

        function setRunning(running) {
            _running = running;
            const btn = document.getElementById('runBtn');
            const cfgBtn = document.getElementById('configBtn');
            if (running) {
                btn.textContent = '⏹ Stop';
                btn.style.background = '#dc3545';
                document.getElementById('projectSelect').disabled = true;
            } else {
                btn.textContent = '▶️ Run';
                btn.style.background = '#28a745';
                document.getElementById('projectSelect').disabled = false;
            }
        }

        function handleRunStop() {
            if (_running) {
                fetch('/api/stop', {method: 'POST'})
                    .then(r => r.json())
                    .then(() => {
                        if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
                        log('⏹ Run aborted', 'error');
                        setRunning(false);
                    });
                return;
            }
            runGeneration();
        }

        let _pollTimer = null;

        function startPolling() {
            _pollTimer = setInterval(() => {
                fetch('/api/pipeline-logs')
                    .then(r => r.json())
                    .then(data => {
                        data.lines.forEach(e => log(e.message, e.type));
                        loadPromptLog();
                        if (!data.running) {
                            clearInterval(_pollTimer);
                            _pollTimer = null;
                            setRunning(false);
                            checkPlayTab(document.getElementById('projectSelect').value);
                        }
                    })
                    .catch(() => {
                        clearInterval(_pollTimer);
                        _pollTimer = null;
                        setRunning(false);
                    });
            }, 1000);
        }

        function runGeneration() {
            const title = document.getElementById('projectSelect').value;
            if (!title) {
                log('⚠ Please select a project first', 'error');
                return;
            }

            clearLog();
            setRunning(true);
            log(`Running pipeline for: ${title}`);

            fetch('/api/generate-narration', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title: title})
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'started') {
                    startPolling();
                } else {
                    log(`✗ Error: ${data.error}`, 'error');
                    setRunning(false);
                }
            })
            .catch(err => {
                log(`✗ Error: ${err}`, 'error');
                setRunning(false);
            });
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML, version=VERSION)


def safe_title(title):
    """Strip path components to prevent directory traversal."""
    return os.path.basename(title.replace("..", "").strip("/\\"))


@app.route("/api/config", methods=["GET"])
def get_config():
    title = safe_title(request.args.get("title", ""))
    if title:
        config_path = os.path.join(VIDEOS_DIR, title, "project.json")
    else:
        config_path = os.path.join(VIDEOS_DIR, "LittleRedRidingHood", "project.json")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return jsonify(json.load(f))
    return jsonify({"title": title or "LittleRedRidingHood"})


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json
    title = safe_title(data.get("title", "Untitled"))

    # Create folder for this title
    project_dir = os.path.join(VIDEOS_DIR, title)
    os.makedirs(project_dir, exist_ok=True)

    config_path = os.path.join(project_dir, "project.json")

    # Load existing config or create new
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        config.update(data)
    else:
        config = data
        config["created"] = "2026-03-31"

    # Save config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return jsonify({"status": "ok", "folder": os.path.basename(project_dir)})


APP_LOG = os.path.join(os.path.dirname(__file__), "app.log")
APP_PROMPT_LOG = os.path.join(os.path.dirname(__file__), "prompt.log")


@app.route("/api/log", methods=["POST"])
def write_log():
    data = request.json
    line = f"[{data.get('time', '')}] [{data.get('type', 'info').upper()}] {data.get('message', '')}\n"
    with open(APP_LOG, "a") as f:
        f.write(line)
    return jsonify({"status": "ok"})


@app.route("/api/log/clear", methods=["POST"])
def clear_log():
    open(APP_LOG, "w").close()
    return jsonify({"status": "ok"})


@app.route("/api/log/prompt", methods=["POST"])
def write_prompt_log():
    data = request.json
    line = (
        f"[{data.get('time', '')}] {data.get('helper', '')}: {data.get('prompt', '')}\n"
    )
    with open(APP_PROMPT_LOG, "a") as f:
        f.write(line)
    return jsonify({"status": "ok"})


@app.route("/api/log/prompt/clear", methods=["POST"])
def clear_prompt_log():
    open(APP_PROMPT_LOG, "w").close()
    return jsonify({"status": "ok"})


@app.route("/api/log/prompt/load", methods=["GET"])
def load_prompt_log():
    if not os.path.exists(APP_PROMPT_LOG):
        return jsonify({"lines": []})
    with open(APP_PROMPT_LOG, "r") as f:
        lines = f.readlines()
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[([^\]]*)\]\s*(.*?):\s*(.*)", line)
        if m:
            result.append(
                {"time": m.group(1), "helper": m.group(2), "prompt": m.group(3)}
            )
    return jsonify({"lines": result})


@app.route("/api/projects", methods=["GET"])
def list_projects():
    """List all project folders under videos directory."""
    projects = []
    if os.path.exists(VIDEOS_DIR):
        for item in os.listdir(VIDEOS_DIR):
            item_path = os.path.join(VIDEOS_DIR, item)
            if os.path.isdir(item_path):
                projects.append(item)
    return jsonify(sorted(projects))


PREPARE_SCRIPT = os.path.join(os.path.dirname(__file__), "scripts", "prepare.py")
PROMPTS_SCRIPT = os.path.join(os.path.dirname(__file__), "scripts", "prompts.py")
GENERATEVIDEO_SCRIPT = os.path.join(
    os.path.dirname(__file__), "scripts", "generatevideo.py"
)

_active_proc = None  # currently running subprocess


# Pipeline state for threaded runs
class _PipelineState:
    def __init__(self):
        self.running = False
        self.logs = deque()
        self.lock = threading.Lock()

    def push(self, message, type="info"):
        with self.lock:
            self.logs.append({"message": message, "type": type})

    def drain(self):
        with self.lock:
            lines = list(self.logs)
            self.logs.clear()
        return lines


_pipeline = _PipelineState()


def run_script(cmd, timeout=600):
    """Run a script, stream output line-by-line to pipeline log, return combined output."""
    global _active_proc
    lines = []
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        _active_proc = proc

        deadline = time.time() + timeout
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                lines.append(line)
                _pipeline.push(line)
            if time.time() > deadline:
                proc.kill()
                _pipeline.push(f"{cmd[1]} timed out", "error")
                break

        proc.wait()
        return "\n".join(lines)
    except Exception as e:
        msg = f"{cmd[1]} error: {e}"
        _pipeline.push(msg, "error")
        return msg
    finally:
        _active_proc = None


def run_prepare(narration_path):
    return run_script(["python", PREPARE_SCRIPT, narration_path], timeout=600)


def run_prompts(narration_path):
    return run_script(["python", PROMPTS_SCRIPT, narration_path], timeout=1800)


def run_generate_video(project_dir):
    config_path = os.path.join(project_dir, "project.json")
    clip_count = 0
    if os.path.exists(config_path):
        with open(config_path) as f:
            clip_count = json.load(f).get("clip_count", 0)
    cmd = ["python", GENERATEVIDEO_SCRIPT, "--project-dir", project_dir]
    if clip_count and clip_count > 0:
        cmd += ["--clips", str(clip_count)]
    return run_script(cmd, timeout=3600)


@app.route("/api/stop", methods=["POST"])
def stop_run():
    global _active_proc
    if _active_proc and _active_proc.poll() is None:
        _active_proc.kill()
        return jsonify({"status": "stopped"})
    return jsonify({"status": "nothing_running"})


KEY_SERVICE_URL = "http://localhost:7755"
KEY_SERVICE_SCRIPT = "/home/henry/APPS/Key/key_sender.py"


def _ensure_key_service():
    """Check if key-service is up; start it if not."""
    try:
        requests.get(f"{KEY_SERVICE_URL}/tmux/panes", timeout=2)
        return  # already running
    except Exception:
        pass
    subprocess.Popen(
        ["python", KEY_SERVICE_SCRIPT, "--api", "--port", "7755"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        time.sleep(1)
        try:
            requests.get(f"{KEY_SERVICE_URL}/tmux/panes", timeout=2)
            return
        except Exception:
            pass
    raise RuntimeError("key-service failed to start after 10 seconds")


def _call_ai(prompt, ai_helper, timeout=120):
    """Send a prompt to the configured AI helper and return the text reply."""
    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    with open(APP_PROMPT_LOG, "a") as f:
        f.write(f"[{ts}] {ai_helper}: {prompt}\n")

    if ai_helper == "claude":
        _ensure_key_service()
        resp = requests.post(
            f"{KEY_SERVICE_URL}/tmux/chat",
            json={"text": f"claude: {prompt}", "timeout": timeout},
            timeout=timeout + 10,
        )
        resp.raise_for_status()
        return resp.json().get("reply", "").strip()

    if ai_helper == "chatgptproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "chatgpt.com"
        selector = '[data-message-author-role="assistant"]'

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"ChatGPTProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('textarea, [contenteditable="true"], [role="textbox"], input[type="text"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)

        existing_count = cdp_eval(f"""(function() {{
            return document.querySelectorAll({json.dumps(selector)}).length;
        }})()""")
        existing_count = int(existing_count) if existing_count else 0

        # Insert text via Input.insertText
        ws.send(
            json.dumps(
                {
                    "id": poll_id[0],
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                }
            )
        )
        ws.recv()
        poll_id[0] += 1
        time.sleep(0.2)

        # Submit via Enter
        for ev in ("keyDown", "keyUp"):
            ws.send(
                json.dumps(
                    {
                        "id": poll_id[0],
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
            poll_id[0] += 1
        ws.close()

        # Re-fetch tab for polling (ChatGPT may navigate)
        time.sleep(1)
        for _ in range(5):
            resp2 = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
            tabs2 = [
                t
                for t in resp2.json()
                if t.get("type") == "page" and tab_url in t.get("url", "")
            ]
            if tabs2 and tabs2[0]["webSocketDebuggerUrl"] != ws_url:
                ws_url = tabs2[0]["webSocketDebuggerUrl"]
                break
            time.sleep(0.5)

        # Poll with new WebSocket
        pw = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)
        pw_poll_id = [1]

        def pw_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = pw_poll_id[0]
            pw_poll_id[0] += 1
            pw.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(100):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(pw.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        reply = None
        prev_text = None
        time.sleep(1)
        while time.monotonic() < deadline:
            text = pw_eval(f"""(function() {{
                var els = document.querySelectorAll({json.dumps(selector)});
                if (els.length <= {existing_count}) return null;
                var last = els[els.length - 1];
                return last.innerText.trim() || null;
            }})()""")
            if text and text == prev_text:
                reply = text
                break
            prev_text = text
            time.sleep(1)
        pw.close()
        if not reply and prev_text:
            reply = prev_text
        if not reply:
            raise RuntimeError("ChatGPTProxy: timed out waiting for response")
        return reply.strip()

    if ai_helper == "copilotproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "copilot.microsoft.com"

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"CopilotProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        existing_count = cdp_eval("""(function() {
            return document.querySelectorAll('[data-testid="ai-message"]').length;
        })()""")
        existing_count = int(existing_count) if existing_count else 0

        cdp_eval("""(function() {
            var el = document.querySelector('textarea, [contenteditable="true"], [role="textbox"]');
            if (!el) return;
            el.focus(); el.click();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
        })()""")
        time.sleep(0.2)

        ws.send(
            json.dumps(
                {
                    "id": poll_id[0],
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                }
            )
        )
        ws.recv()
        poll_id[0] += 1
        time.sleep(0.3)

        sent = cdp_eval("""(function() {
            var btn = document.querySelector('button[aria-label*="Send"], button[aria-label*="Submit"], button[type="submit"]');
            if (btn && !btn.disabled) { btn.click(); return 'btn'; }
            return 'enter';
        })()""")
        if sent == "enter":
            for ev in ("keyDown", "keyUp"):
                ws.send(
                    json.dumps(
                        {
                            "id": poll_id[0],
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
                poll_id[0] += 1

        ws.close()
        time.sleep(1)

        pw = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)
        pw_poll_id = [1]

        def pw_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = pw_poll_id[0]
            pw_poll_id[0] += 1
            pw.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(100):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(pw.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        reply = None
        prev_text = None
        time.sleep(1)
        while time.monotonic() < deadline:
            text = pw_eval(f"""(function() {{
                var els = document.querySelectorAll('[data-testid="ai-message"]');
                if (els.length <= {existing_count}) return null;
                var last = els[els.length - 1];
                return last.innerText.trim() || null;
            }})()""")
            if text and text == prev_text:
                reply = text
                break
            prev_text = text
            time.sleep(1)
        pw.close()
        if not reply and prev_text:
            reply = prev_text
        if not reply:
            raise RuntimeError("CopilotProxy: timed out waiting for response")
        import re as _re

        reply = _re.sub(r"^Copilot said\s*", "", reply).strip()
        return reply.strip()

    if ai_helper == "deepseekproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "chat.deepseek.com"

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"DeepSeekProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        existing_count = cdp_eval("""(function() {
            var els = document.querySelectorAll('.ds-markdown, .message-assistant, [class*="assistant"], [class*="response"], .chat-message-assistant');
            return els.length;
        })()""")
        existing_count = int(existing_count) if existing_count else 0

        cdp_eval("""(function() {
            var el = document.querySelector('textarea, [contenteditable="true"], [role="textbox"]');
            if (!el) return;
            el.focus(); el.click();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
        })()""")
        time.sleep(0.2)

        ws.send(
            json.dumps(
                {
                    "id": poll_id[0],
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                }
            )
        )
        ws.recv()
        poll_id[0] += 1
        time.sleep(0.3)

        sent = cdp_eval("""(function() {
            var btn = document.querySelector('button[aria-label*="Send"], button[aria-label*="Submit"], button[type="submit"], #send-button, [class*="send"]');
            if (btn && !btn.disabled) { btn.click(); return 'btn'; }
            return 'enter';
        })()""")
        if sent == "enter":
            for ev in ("keyDown", "keyUp"):
                ws.send(
                    json.dumps(
                        {
                            "id": poll_id[0],
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
                poll_id[0] += 1

        ws.close()
        time.sleep(1)

        pw = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)
        pw_poll_id = [1]

        def pw_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = pw_poll_id[0]
            pw_poll_id[0] += 1
            pw.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(100):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(pw.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        reply = None
        prev_text = None
        time.sleep(1)
        while time.monotonic() < deadline:
            text = pw_eval(f"""(function() {{
                var els = document.querySelectorAll('.ds-markdown, .message-assistant, [class*="assistant"], [class*="response"], .chat-message-assistant');
                if (els.length <= {existing_count}) return null;
                var last = els[els.length - 1];
                return last.innerText.trim() || null;
            }})()""")
            if text and text == prev_text:
                reply = text
                break
            prev_text = text
            time.sleep(1)
        pw.close()
        if not reply and prev_text:
            reply = prev_text
        if not reply:
            raise RuntimeError("DeepSeekProxy: timed out waiting for response")
        return reply.strip()

    if ai_helper == "perplexityproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "perplexity.ai"
        selector = ".prose"

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"PerplexityProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('textarea, [contenteditable="true"], [role="textbox"], input[type="text"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)

        existing_count = cdp_eval(f"""(function() {{
            return document.querySelectorAll({json.dumps(selector)}).length;
        }})()""")
        existing_count = int(existing_count) if existing_count else 0

        ws.send(
            json.dumps(
                {
                    "id": poll_id[0],
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                }
            )
        )
        ws.recv()
        poll_id[0] += 1
        time.sleep(0.2)

        for ev in ("keyDown", "keyUp"):
            ws.send(
                json.dumps(
                    {
                        "id": poll_id[0],
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
            poll_id[0] += 1
        ws.close()

        time.sleep(1)
        for _ in range(5):
            resp2 = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
            tabs2 = [
                t
                for t in resp2.json()
                if t.get("type") == "page" and tab_url in t.get("url", "")
            ]
            if tabs2 and tabs2[0]["webSocketDebuggerUrl"] != ws_url:
                ws_url = tabs2[0]["webSocketDebuggerUrl"]
                break
            time.sleep(0.5)

        pw = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)
        pw_poll_id = [1]

        def pw_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = pw_poll_id[0]
            pw_poll_id[0] += 1
            pw.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(100):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(pw.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        reply = None
        prev_text = None
        time.sleep(1)
        while time.monotonic() < deadline:
            text = pw_eval(f"""(function() {{
                var els = document.querySelectorAll({json.dumps(selector)});
                if (els.length <= {existing_count}) return null;
                var last = els[els.length - 1];
                return last.innerText.trim() || null;
            }})()""")
            if text and text == prev_text:
                reply = text
                break
            prev_text = text
            time.sleep(1)
        pw.close()
        if not reply and prev_text:
            reply = prev_text
        if not reply:
            raise RuntimeError("PerplexityProxy: timed out waiting for response")
        return reply.strip()

    if ai_helper == "xiaomiproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "aistudio.xiaomimimo.com"

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"XiaomiProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('textarea, [contenteditable="true"], [role="textbox"], input[type="text"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)

        pre_len = cdp_eval("""(function() {
            return document.body ? document.body.innerText.length : 0;
        })()""")
        pre_len = int(pre_len) if pre_len else 0

        ws.send(
            json.dumps(
                {
                    "id": poll_id[0],
                    "method": "Input.insertText",
                    "params": {"text": prompt},
                }
            )
        )
        ws.recv()
        poll_id[0] += 1
        time.sleep(0.2)

        for ev in ("keyDown", "keyUp"):
            ws.send(
                json.dumps(
                    {
                        "id": poll_id[0],
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
            poll_id[0] += 1
        ws.close()

        time.sleep(3)
        for _ in range(10):
            resp2 = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
            tabs2 = [
                t
                for t in resp2.json()
                if t.get("type") == "page" and tab_url in t.get("url", "")
            ]
            if tabs2 and tabs2[0]["webSocketDebuggerUrl"] != ws_url:
                ws_url = tabs2[0]["webSocketDebuggerUrl"]
                break
            time.sleep(1)

        pw = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)
        pw_poll_id = [1]

        def pw_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = pw_poll_id[0]
            pw_poll_id[0] += 1
            pw.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(100):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(pw.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        reply = None
        prev_len = 0
        time.sleep(3)
        while time.monotonic() < deadline:
            val = pw_eval("""(function() {
                return document.body ? document.body.innerText : '';
            })()""")
            if val and len(val) > prev_len:
                prev_len = len(val)
                reply = val
            elif val and len(val) == prev_len and prev_len > 0:
                break
            time.sleep(2)
        pw.close()
        if not reply:
            raise RuntimeError("XiaomiProxy: timed out waiting for response")
        import re as _re

        matches = list(
            _re.finditer(
                r"Thought for [\d.]+ seconds?\s*(.+?)(?=\s*(?:MiMo-V2-Pro|Developer demo|Citation sources|$))",
                reply,
                _re.DOTALL,
            )
        )
        if matches:
            return matches[-1].group(1).strip()
        return reply.strip()

    if ai_helper == "geminiproxy":
        cdp_port = 9222
        tab_url = "gemini.google.com"
        selector = "structured-content-container"
        import websocket as _ws

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"GeminiProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('[contenteditable="true"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)
        existing_count = cdp_eval(f"""(function() {{
            return document.querySelectorAll({json.dumps(selector)}).length;
        }})()""")
        existing_count = int(existing_count) if existing_count else 0
        mid = poll_id[0]
        poll_id[0] += 1
        ws.send(
            json.dumps(
                {"id": mid, "method": "Input.insertText", "params": {"text": prompt}}
            )
        )
        ws.recv()
        time.sleep(0.2)
        for ev in ("keyDown", "keyUp"):
            mid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": mid,
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
        reply = None
        prev_text = None
        time.sleep(1)
        while time.monotonic() < deadline:
            val = cdp_eval(f"""(function() {{
                var els = document.querySelectorAll({json.dumps(selector)});
                if (els.length <= {existing_count}) return null;
                return els[els.length - 1].innerText.trim() || null;
            }})()""")
            if val and val == prev_text:
                reply = val
                break
            prev_text = val
            time.sleep(1)
        ws.close()
        if not reply and prev_text:
            reply = prev_text
        if not reply:
            raise RuntimeError("GeminiProxy: timed out waiting for response")
        return reply.strip()

    if ai_helper == "google":
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            try:
                import importlib.util

                _spec = importlib.util.spec_from_file_location(
                    "api_keys",
                    "/home/henry/APPS/ContentCreator/Imager/core/api_keys.py",
                )
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                api_key = _mod.GOOGLE_API_KEY
            except Exception:
                raise RuntimeError(
                    "GOOGLE_API_KEY environment variable not set and ContentCreator api_keys.py not found"
                )

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ],
            ),
        )
        return response.text.strip()

    # Default: opencode
    import subprocess as _sp

    result = _sp.run(
        ["/home/henry/.opencode/bin/opencode", "run", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", result.stdout).strip()


def _capture_current_geminiproxy_image(output_path):
    """Grab the most recent visible image from the Gemini tab without sending a prompt."""
    import websocket as _ws
    import base64 as _b64

    cdp_port = 9222
    tab_url = "gemini.google.com"
    img_selector = "img.image"
    try:
        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            return False
        ws_url = tabs[0]["webSocketDebuggerUrl"]
        msg_id = [1]
        ws = _ws.create_connection(ws_url, timeout=60, suppress_origin=True)

        def cdp_eval(js):
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

        img_src = cdp_eval(f"""(function() {{
            var imgs = document.querySelectorAll({json.dumps(img_selector)});
            for (var i = imgs.length - 1; i >= 0; i--) {{
                var src = imgs[i].currentSrc || imgs[i].src || '';
                if (src && imgs[i].complete && imgs[i].naturalWidth >= 100) return src;
            }}
            return null;
        }})()""")

        if not img_src:
            ws.close()
            return False

        rect_val = cdp_eval(f"""(function() {{
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
        }})()""")
        time.sleep(0.3)
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
                f.write(_b64.b64decode(screenshot_data))
            return True
        return False
    except Exception as e:
        print(f"  Capture error: {e}")
        return False


def _generate_thumbnail_image_geminiproxy(prompt, output_path):
    """Generate a thumbnail image via GeminiProxy CDP. Returns True on success."""
    import websocket as _ws
    import base64 as _b64

    cdp_port = 9222
    tab_url = "gemini.google.com"
    img_selector = "img.image"
    try:
        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"No Chrome tab found for {tab_url}")
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
        snap_js = f"(function(){{var imgs=document.querySelectorAll({json.dumps(img_selector)}),srcs=[];for(var i=0;i<imgs.length;i++){{var s=imgs[i].currentSrc||imgs[i].src||'';if(s)srcs.push(s);}}return JSON.stringify(srcs);}})()"
        snap_val = cdp_eval(ws, snap_js)
        existing_srcs = set(json.loads(snap_val)) if snap_val else set()

        # Focus the input box before inserting text
        cdp_eval(
            ws,
            """(function() {
            var el = document.querySelector('[contenteditable="true"]');
            if (el) { el.focus(); el.click(); }
        })()""",
        )
        time.sleep(0.3)

        full_prompt = "generate an image of: " + prompt
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

        img_src = None
        deadline = time.monotonic() + 120
        existing_list = json.dumps(list(existing_srcs))
        time.sleep(10)
        while time.monotonic() < deadline:
            val = cdp_eval(
                ws,
                f"""(function() {{
                var known = new Set({existing_list});
                var imgs = document.querySelectorAll({json.dumps(img_selector)});
                for (var i = 0; i < imgs.length; i++) {{
                    var img = imgs[i];
                    var src = img.currentSrc || img.src || img.getAttribute('src') || '';
                    if (src && !known.has(src) && img.complete && img.naturalWidth >= 100)
                        return src;
                }}
                return null;
            }})()""",
            )
            if val:
                img_src = val
                break
            time.sleep(5)

        if not img_src:
            ws.close()
            _pipeline.push("⚠ GeminiProxy: no image appeared within timeout", "error")
            return False

        # Locate the exact image element and screenshot it
        rect_val = cdp_eval(
            ws,
            f"""(function() {{
            var imgs = document.querySelectorAll({json.dumps(img_selector)});
            var img = null;
            for (var i = imgs.length - 1; i >= 0; i--) {{
                if ((imgs[i].currentSrc || imgs[i].src || '') === {json.dumps(img_src)}) {{ img = imgs[i]; break; }}
            }}
            if (!img) return null;
            img.scrollIntoView({{block:'center'}});
            var r = img.getBoundingClientRect();
            var dpr = window.devicePixelRatio || 1;
            var nw = img.naturalWidth || r.width;
            return JSON.stringify({{x:r.left, y:r.top, width:r.width, height:r.height, scale:Math.max(dpr, nw/r.width)}});
        }})()""",
        )
        if not rect_val:
            ws.close()
            _pipeline.push("⚠ GeminiProxy: could not locate image element", "error")
            return False
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
                f.write(_b64.b64decode(screenshot_data))
            return True
        return False
    except Exception as e:
        _pipeline.push(f"⚠ GeminiProxy error: {e}", "error")
        return False


def _generate_thumbnail_and_metadata(
    title, project_dir, narration_text, ai_helper, image_model, image_style=""
):
    """Generate thumbnail.png and description.txt for the project."""
    p = _pipeline

    # Step 1: description + YouTube tags
    desc_path = os.path.join(project_dir, "description.txt")
    if os.path.exists(desc_path):
        p.push("description.txt already exists — skipping", "info")
    else:
        p.push("Generating story description and YouTube tags...")
        desc_prompt = (
            f"Provide a YouTube video description in exactly three sentences for a story titled '{title}'. "
            f"After the sentences, on a new line, provide exactly 5 relevant keywords/hashtags separated by commas, "
            f"but do NOT include the '#' symbol. Output ONLY the description text and the hashtag line."
        )
        try:
            desc_reply = _call_ai(desc_prompt, ai_helper, timeout=60)
            if desc_reply:
                lines = [
                    l.strip() for l in desc_reply.strip().splitlines() if l.strip()
                ]
                tags_line = lines[-1] if lines else ""
                desc_lines = lines[:-1] if len(lines) > 1 else lines
                description = " ".join(desc_lines)
                tags = [
                    t.strip().lstrip("#") for t in tags_line.split(",") if t.strip()
                ]
                with open(desc_path, "w") as f:
                    f.write(f"Title: {title}\n\n")
                    f.write(f"Description:\n{description}\n\n")
                    f.write(f"Tags: {', '.join(tags)}\n")
                p.push(
                    f"✓ Saved description.txt (title + description + {len(tags)} tags)",
                    "success",
                )
        except Exception as e:
            p.push(f"⚠ Description generation failed: {e}", "info")

    # Step 2: thumbnail image prompt
    thumb_path = os.path.join(project_dir, "thumbnail.png")
    if os.path.exists(thumb_path):
        p.push("thumbnail.png already exists — skipping", "info")
        return
    p.push("Generating thumbnail image prompt...")
    style_desc = STYLE_DESCRIPTIONS.get(image_style, "")
    style_clause = (
        f" The image must be in {image_style} style: {style_desc}" if style_desc else ""
    )
    thumb_prompt_text = (
        f"Create a short, vivid image generation prompt for a YouTube thumbnail for a story titled '{title}'. "
        f"Describe only the visual scene — characters, colors, lighting, composition, and mood. "
        f"Make it high-contrast and visually striking. Do not include any text or words in the image.{style_clause} "
        f"Output ONLY the image prompt."
    )
    try:
        image_prompt = _call_ai(thumb_prompt_text, ai_helper, timeout=60)
        if not image_prompt:
            image_prompt = f"A colorful, vibrant scene from the children's story '{title}', high contrast, storybook illustration"
    except Exception as e:
        p.push(f"⚠ Thumbnail prompt generation failed: {e}", "info")
        image_prompt = f"A colorful, vibrant scene from the children's story '{title}', high contrast, storybook illustration"

    p.push(f"Thumbnail prompt: {image_prompt}")

    # Step 3: generate thumbnail image
    p.push(f"Generating thumbnail via {image_model}...")
    try:
        if image_model == "geminiproxy":
            ok = _generate_thumbnail_image_geminiproxy(image_prompt, thumb_path)
            if ok:
                p.push(f"✓ Saved thumbnail.png", "success")
            else:
                p.push("⚠ Thumbnail image generation failed", "info")
        else:
            # ComfyUI path — create a temp project dir with prompts.txt and project.json
            import shutil

            thumb_dir = os.path.join(project_dir, "_thumb_tmp")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_cfg = {}
            if os.path.exists(os.path.join(project_dir, "project.json")):
                with open(os.path.join(project_dir, "project.json")) as _f:
                    thumb_cfg = json.load(_f)
            thumb_cfg["image_model"] = image_model
            if image_style:
                thumb_cfg["image_style"] = image_style
            with open(os.path.join(thumb_dir, "project.json"), "w") as _f:
                json.dump(thumb_cfg, _f, indent=2)
            with open(os.path.join(thumb_dir, "prompts.txt"), "w") as f:
                f.write(f"Prompt 1: {image_prompt}|||{title}\n\n")
            run_script(
                [
                    "python",
                    GENERATEVIDEO_SCRIPT,
                    "--project-dir",
                    thumb_dir,
                    "--clips",
                    "1",
                ],
                timeout=300,
            )
            generated = os.path.join(thumb_dir, "clips", "clip_01.png")
            if os.path.exists(generated):
                shutil.copy2(generated, thumb_path)
                p.push(f"✓ Saved thumbnail.png", "success")
            else:
                p.push("⚠ ComfyUI thumbnail not generated", "info")
            shutil.rmtree(thumb_dir, ignore_errors=True)
    except Exception as e:
        p.push(f"⚠ Thumbnail generation error: {e}", "info")


def _generate_audio_and_assemble(project_dir, narration_path, voice_model, voice_rate):
    """Generate TTS audio per narration line then assemble final video with ffmpeg."""
    import glob as _glob

    p = _pipeline

    # Load transition settings from project.json
    config_path = os.path.join(project_dir, "project.json")
    transition_style = "None"
    transition_duration = 1.0
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
                transition_style = config_data.get("transition_style", "None")
                transition_duration = float(config_data.get("transition_duration", 1.0))
        except:
            pass

    if transition_style in XFADE_TRANSITIONS:
        _assemble_with_xfade(
            project_dir,
            narration_path,
            voice_model,
            voice_rate,
            transition_style,
            transition_duration,
        )
        return

    output_path = os.path.join(project_dir, "output.mp4")
    if os.path.exists(output_path):
        p.push("output.mp4 already exists — skipping assembly", "info")
        return

    with open(narration_path) as f:
        lines = [l.strip() for l in f if l.strip()]

    clips_dir = os.path.join(project_dir, "clips")
    audio_dir = os.path.join(project_dir, "audio")
    segments_dir = os.path.join(project_dir, "segments")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(segments_dir, exist_ok=True)

    # --- Step 1: TTS audio per line ---
    p.push(f"Generating audio ({voice_model}, rate {voice_rate})...")
    for i, line in enumerate(lines, 1):
        audio_path = os.path.join(audio_dir, f"line_{i:02d}.mp3")
        if os.path.exists(audio_path):
            p.push(f"  line_{i:02d}.mp3 exists — skipping", "info")
            continue
        p.push(f"  TTS line {i}/{len(lines)}...")
        try:
            subprocess.run(
                [
                    "/home/henry/.local/bin/edge-tts",
                    "--voice",
                    voice_model,
                    f"--rate={voice_rate}",
                    "--text",
                    line,
                    "--write-media",
                    audio_path,
                ],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            p.push(f"  ⚠ TTS failed for line {i}: {e}", "info")

    # --- Step 2: combine each clip with its audio into a segment ---
    all_clips = sorted(
        _glob.glob(os.path.join(clips_dir, "clip_*.png"))
        + _glob.glob(os.path.join(clips_dir, "clip_*.mp4"))
    )
    if not all_clips:
        p.push("⚠ No clips found — skipping assembly", "error")
        return

    segment_files = []
    for clip_path in all_clips:
        m = re.search(r"clip_(\d+)", os.path.basename(clip_path))
        if not m:
            continue
        num = m.group(1)
        audio_path = os.path.join(audio_dir, f"line_{num}.mp3")
        segment_path = os.path.join(segments_dir, f"segment_{num}.mp4")

        if not os.path.exists(audio_path):
            p.push(f"  ⚠ No audio for clip_{num} — skipping segment", "info")
            continue

        if os.path.exists(segment_path):
            p.push(f"  {os.path.basename(segment_path)} exists — skipping", "info")
            segment_files.append(segment_path)
            continue

        p.push(f"  Building segment {num}...")
        ext = os.path.splitext(clip_path)[1].lower()
        try:
            if ext == ".png":
                # Determine duration for zoompan
                try:
                    probecmd = [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        audio_path,
                    ]
                    dur_str = subprocess.check_output(probecmd).strip().decode()
                    seg_dur = float(dur_str)
                except:
                    seg_dur = 5.0  # fallback

                fps = 25
                nf = max(int(seg_dur * fps), 2)
                res_w, res_h = 1280, 720  # Target resolution

                # Camera motions from ContentCreator
                if transition_style == "zoom_in":
                    zpf = f"zoompan=z='min(1.1+(0.0005*on),1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={res_w}x{res_h}:fps={fps}"
                elif transition_style == "zoom_out":
                    zpf = f"zoompan=z='max(1.5-(0.0005*on),1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={res_w}x{res_h}:fps={fps}"
                elif transition_style == "pan_down":
                    zpf = f"zoompan=z=1.3:y='min(y+1,ih-ih/zoom)':x='iw/2-(iw/zoom/2)':d={nf}:s={res_w}x{res_h}:fps={fps}"
                elif transition_style == "pan_up":
                    zpf = f"zoompan=z=1.3:y='max((ih-ih/zoom)-(on*1),0)':x='iw/2-(iw/zoom/2)':d={nf}:s={res_w}x{res_h}:fps={fps}"
                else:
                    zpf = None

                if zpf:
                    # Apply camera motion: loop image, apply scale + zoompan, then format
                    vf = f"scale=2560:1440,{zpf},format=yuv420p"
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-r",
                        str(fps),
                        "-t",
                        f"{seg_dur:.3f}",
                        "-i",
                        clip_path,
                        "-i",
                        audio_path,
                        "-vf",
                        vf,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-shortest",
                        "-pix_fmt",
                        "yuv420p",
                        segment_path,
                    ]
                else:
                    # Default static stillimage
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        clip_path,
                        "-i",
                        audio_path,
                        "-c:v",
                        "libx264",
                        "-tune",
                        "stillimage",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-shortest",
                        "-pix_fmt",
                        "yuv420p",
                        segment_path,
                    ]
            else:  # .mp4 video clip
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    clip_path,
                    "-i",
                    audio_path,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-shortest",
                    "-pix_fmt",
                    "yuv420p",
                    segment_path,
                ]
            subprocess.run(cmd, check=True, capture_output=True)
            segment_files.append(segment_path)
        except Exception as e:
            p.push(f"  ⚠ Segment {num} failed: {e}", "info")

    if not segment_files:
        p.push("⚠ No segments built — skipping final assembly", "error")
        return

    # --- Step 3: concatenate all segments ---
    concat_list = os.path.join(audio_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    p.push(f"Assembling {len(segment_files)} segments → output.mp4...")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        p.push(f"✓ output.mp4 assembled ({len(segment_files)} clips)", "success")
    except Exception as e:
        p.push(f"✗ Assembly failed: {e}", "error")


def _build_narration_prompt(title, story_type, sentence_count=30):
    """Build the narration+prompts prompt text. Shared by all AI helpers."""
    story_type_display = story_type.replace("_", " ").title()
    return (
        f"Write a {sentence_count}-sentence {story_type_display} narration script for a "
        f"YouTube video titled '{title}'. Output only the story text — one sentence per "
        f"line, no numbering, no headers, no extra commentary. "
        f"IMPORTANT: The very last sentence of the narration must always be a SINGLE CTA asking viewers "
        f"to like, share and subscribe. Limit this to exactly one sentence.\n\n"
        f"Then after the narration, write a section called [Prompts] and for EACH sentence above, "
        f"write a detailed image generation prompt. Each prompt should describe the scene vividly: "
        f"setting, background, lighting, camera angle (close-up, wide shot, etc.), character positions, "
        f"mood, and colors. "
        f"One prompt per line, no numbering.\n\n"
        f"Format your entire output as:\n"
        f"<narration sentences>\n\n[Prompts]\n<prompt sentences>"
    )


def _parse_narration_response(full_content, narration_path, rawprompt_path):
    """Split AI response into narration and prompts, write files."""
    if "[Prompts]" in full_content:
        parts = full_content.split("[Prompts]", 1)
        narration_content = parts[0].strip()
        prompts_content = parts[1].strip()
    else:
        narration_content = full_content
        prompts_content = ""

    with open(narration_path, "w") as f:
        f.write(narration_content + "\n")
    if prompts_content:
        with open(rawprompt_path, "w") as f:
            f.write(prompts_content + "\n")


def _generate_narration(
    title, story_type, narration_path, ai_helper, project_dir=None, sentence_count=30
):
    """Generate narration.txt and RawPrompt.txt using the configured AI helper. Returns prompt or raises."""
    prompt = _build_narration_prompt(title, story_type, sentence_count)
    project_dir = project_dir or os.path.dirname(narration_path)
    rawprompt_path = os.path.join(project_dir, "RawPrompt.txt")

    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    with open(APP_PROMPT_LOG, "a") as f:
        f.write(f"[{ts}] {ai_helper}: {prompt}\n")

    if ai_helper == "claude":
        _ensure_key_service()
        resp = requests.post(
            f"{KEY_SERVICE_URL}/tmux/chat",
            json={"text": f"claude: {prompt}", "timeout": 180},
            timeout=190,
        )
        resp.raise_for_status()
        full_content = resp.json().get("reply", "").strip()
        if not full_content:
            raise RuntimeError("key-service returned empty reply")
        _parse_narration_response(full_content, narration_path, rawprompt_path)
        return prompt

    if ai_helper == "geminiproxy":
        import websocket as _ws

        cdp_port = 9222
        tab_url = "gemini.google.com"
        selector = "structured-content-container"

        resp = requests.get(f"http://localhost:{cdp_port}/json", timeout=3)
        tabs = [
            t
            for t in resp.json()
            if t.get("type") == "page" and tab_url in t.get("url", "")
        ]
        if not tabs:
            raise RuntimeError(f"GeminiProxy: no Chrome tab found for {tab_url}")
        tab = tabs[0]
        ws_url = tab["webSocketDebuggerUrl"]
        requests.get(
            f"http://localhost:{cdp_port}/json/activate/{tab['id']}", timeout=3
        )
        time.sleep(0.5)

        deadline = time.monotonic() + 180
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": pid,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js},
                    }
                )
            )
            for _ in range(200):
                if time.monotonic() > deadline:
                    return None
                msg = json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('[contenteditable="true"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)
        pre_last = cdp_eval(f"""(function() {{
            var els = document.querySelectorAll({json.dumps(selector)});
            return els.length ? els[els.length - 1].innerText : null;
        }})()""")
        mid = poll_id[0]
        poll_id[0] += 1
        ws.send(
            json.dumps(
                {"id": mid, "method": "Input.insertText", "params": {"text": prompt}}
            )
        )
        ws.recv()
        time.sleep(0.2)
        for ev in ("keyDown", "keyUp"):
            mid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": mid,
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

        reply = None
        prev_reply = None
        time.sleep(3)
        while time.monotonic() < deadline:
            val = cdp_eval(f"""(function() {{
                var els = document.querySelectorAll({json.dumps(selector)});
                if (!els.length) return null;
                return els[els.length - 1].innerText || null;
            }})()""")
            if val and val == pre_last:
                val = None
            if val and val == prev_reply:
                reply = val
                break
            prev_reply = val
            time.sleep(2)
        ws.close()
        if not reply:
            raise RuntimeError("GeminiProxy: timed out waiting for response")
        full_content = reply.strip()
        if not full_content:
            raise RuntimeError("GeminiProxy returned empty reply")
        _parse_narration_response(full_content, narration_path, rawprompt_path)
        return prompt

    if ai_helper == "google":
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            try:
                import importlib.util

                _spec = importlib.util.spec_from_file_location(
                    "api_keys",
                    "/home/henry/APPS/ContentCreator/Imager/core/api_keys.py",
                )
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                api_key = _mod.GOOGLE_API_KEY
            except Exception:
                raise RuntimeError(
                    "GOOGLE_API_KEY environment variable not set and ContentCreator api_keys.py not found"
                )

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ],
            ),
        )
        full_content = response.text.strip()
        if not full_content:
            raise RuntimeError("Google returned empty reply")
        _parse_narration_response(full_content, narration_path, rawprompt_path)
        return prompt

    # Proxy helpers delegate to _call_ai (CDP-based)
    if ai_helper in (
        "chatgptproxy",
        "copilotproxy",
        "deepseekproxy",
        "perplexityproxy",
        "xiaomiproxy",
    ):
        full_content = _call_ai(prompt, ai_helper, timeout=180)
        if not full_content:
            raise RuntimeError(f"{ai_helper} returned empty reply")
        _parse_narration_response(full_content, narration_path, rawprompt_path)
        return prompt

    # Default: opencode
    pre_mtime = (
        os.path.getmtime(narration_path) if os.path.exists(narration_path) else None
    )
    result = subprocess.run(
        ["/home/henry/.opencode/bin/opencode", "run", prompt],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=project_dir,
    )
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    post_mtime = (
        os.path.getmtime(narration_path) if os.path.exists(narration_path) else None
    )
    if post_mtime is not None and post_mtime != pre_mtime:
        with open(narration_path, "r") as f:
            if f.read().strip():
                return prompt
    full_content = ansi_escape.sub("", result.stdout).strip()
    if not full_content:
        stderr = ansi_escape.sub("", result.stderr).strip()
        raise RuntimeError(stderr or "opencode returned empty output")
    _parse_narration_response(full_content, narration_path, rawprompt_path)
    return prompt


def _run_pipeline(
    title,
    project_dir,
    narration_path,
    story_type,
    ai_helper,
    sentence_count=30,
    step_narration=True,
    step_prep_cref=True,
    step_prompts=True,
    step_thumbnail=True,
    step_clips=True,
    step_assemble=True,
):
    """Background thread: generate narration → prepare → prompts → video."""
    p = _pipeline
    try:
        proj_cfg = {}
        proj_cfg_path = os.path.join(project_dir, "project.json")
        if os.path.exists(proj_cfg_path):
            with open(proj_cfg_path) as f:
                proj_cfg = json.load(f)

        # Step 1: Narration
        if step_narration:
            if os.path.exists(narration_path):
                p.push(
                    "⚠ narration.txt already exists — skipping AI generation", "info"
                )
            else:
                p.push(
                    f"Generating narration via {ai_helper} ({sentence_count} sentences)..."
                )
                prompt = _generate_narration(
                    title,
                    story_type,
                    narration_path,
                    ai_helper,
                    project_dir,
                    sentence_count,
                )
                p.push(f"Prompt → {prompt}")
                p.push(f"✓ Narration created: {narration_path}", "success")
        else:
            p.push("⊘ Skipping Narration", "info")

        # Step 2: Prep CREF
        if step_prep_cref:
            p.push("Running prepare script...")
            run_prepare(narration_path)
        else:
            p.push("⊘ Skipping Prep CREF", "info")

        # Step 3: Prompts + CREF images
        if step_prompts:
            p.push("Running prompts script...")
            run_prompts(narration_path)
        else:
            p.push("⊘ Skipping Prompts", "info")

        # Step 4: Thumbnail
        if step_thumbnail:
            with open(narration_path, "r") as f:
                narration_text = f.read()
            thumb_image_model = proj_cfg.get("image_model", "geminiproxy")
            _generate_thumbnail_and_metadata(
                title,
                project_dir,
                narration_text,
                ai_helper,
                thumb_image_model,
                proj_cfg.get("image_style", ""),
            )
        else:
            p.push("⊘ Skipping Thumbnail", "info")

        # Step 5: Clips
        if step_clips:
            p.push("Running video generation...")
            run_generate_video(project_dir)
        else:
            p.push("⊘ Skipping Clips", "info")

        # Step 6: Assemble
        if step_assemble:
            voice_model = proj_cfg.get("voice_model", "en-US-AnaNeural")
            voice_rate = proj_cfg.get("voice_rate", "+0%")
            _generate_audio_and_assemble(
                project_dir, narration_path, voice_model, voice_rate
            )
        else:
            p.push("⊘ Skipping Assemble", "info")

        p.push("✓ Pipeline complete", "success")
    except Exception as e:
        p.push(f"✗ Error: {e}", "error")
    finally:
        p.running = False


@app.route("/api/generate-narration", methods=["POST"])
def generate_narration():
    """Start the pipeline in a background thread."""
    if _pipeline.running:
        return jsonify({"status": "error", "error": "Pipeline already running"})

    data = request.json
    title = data.get("title", "")
    if not title:
        return jsonify({"status": "error", "error": "No title provided"})

    project_dir = os.path.join(VIDEOS_DIR, title)
    if not os.path.exists(project_dir):
        return jsonify({"status": "error", "error": "Project folder not found"})

    config_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(config_path):
        return jsonify({"status": "error", "error": "project.json not found"})

    with open(config_path, "r") as f:
        config = json.load(f)

    story_type = config.get("story_type", "children_story")
    ai_helper = config.get("ai_helper", "opencode")
    clip_count = config.get("clip_count", 0)
    sentence_count = clip_count if clip_count and clip_count > 0 else 30
    narration_path = os.path.join(project_dir, "narration.txt")
    step_narration = config.get("step_narration", True)
    step_prep_cref = config.get("step_prep_cref", True)
    step_prompts = config.get("step_prompts", True)
    step_thumbnail = config.get("step_thumbnail", True)
    step_clips = config.get("step_clips", True)
    step_assemble = config.get("step_assemble", True)

    _pipeline.running = True
    _pipeline.logs.clear()

    t = threading.Thread(
        target=_run_pipeline,
        args=(
            title,
            project_dir,
            narration_path,
            story_type,
            ai_helper,
            sentence_count,
            step_narration,
            step_prep_cref,
            step_prompts,
            step_thumbnail,
            step_clips,
            step_assemble,
        ),
        daemon=True,
    )
    t.start()

    return jsonify({"status": "started"})


@app.route("/api/suggest-title", methods=["POST"])
def suggest_title():
    data = request.json
    ai_helper = data.get("ai_helper", "opencode")
    story_type = data.get("story_type", "children_story")
    prompt = (
        f"Suggest one creative, catchy title for a {story_type.replace('_', ' ')}. "
        f"Output ONLY the title, no quotes, no explanation."
    )
    try:
        title = _call_ai(prompt, ai_helper, timeout=60)
        if not title:
            return jsonify({"error": "No title returned"})
        return jsonify({"title": title.strip().strip('"').strip("'")})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/reset", methods=["POST"])
def reset_project():
    title = safe_title(request.json.get("title", ""))
    if not title:
        return jsonify({"status": "error", "error": "No title provided"})
    project_dir = os.path.join(VIDEOS_DIR, title)
    if not os.path.exists(project_dir):
        return jsonify({"status": "error", "error": "Project folder not found"})
    removed = 0
    for item in os.listdir(project_dir):
        if item == "project.json":
            continue
        item_path = os.path.join(project_dir, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
            removed += 1
        elif os.path.isdir(item_path):
            import shutil

            shutil.rmtree(item_path)
            removed += 1
    return jsonify({"status": "ok", "removed": removed})


@app.route("/api/reset-pipeline", methods=["POST"])
def reset_pipeline_flag():
    title = safe_title(request.json.get("title", ""))
    if not title:
        return jsonify({"status": "error", "error": "No title provided"})
    _pipeline.running = False
    _pipeline.logs.clear()
    return jsonify({"status": "ok"})


@app.route("/api/comfy/queue", methods=["GET"])
def get_comfy_queue():
    try:
        # Check if ComfyUI is reachable
        resp = requests.get("http://127.0.0.1:8188/queue", timeout=2)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompts", methods=["GET"])
def get_prompts():
    title = safe_title(request.args.get("title", ""))
    path = os.path.join(VIDEOS_DIR, title, "prompts.txt")
    if not os.path.exists(path):
        return jsonify({"prompts": []})

    # Load raw prompts if available
    rawprompts = []
    rawprompt_path = os.path.join(VIDEOS_DIR, title, "RawPrompt.txt")
    if os.path.exists(rawprompt_path):
        with open(rawprompt_path) as f:
            rawprompts = [l.strip() for l in f if l.strip()]

    prompts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or "=" in line or "Video Generation" in line:
                continue
            if "|||" in line:
                full_prompt, sentence = line.split("|||", 1)
                raw = rawprompts[len(prompts)] if len(prompts) < len(rawprompts) else ""
                prompts.append(
                    {
                        "sentence": sentence.strip(),
                        "prompt": full_prompt.strip(),
                        "raw": raw,
                    }
                )
            elif line.startswith("Prompt"):
                raw = rawprompts[len(prompts)] if len(prompts) < len(rawprompts) else ""
                prompts.append({"sentence": "", "prompt": line, "raw": raw})
    return jsonify({"prompts": prompts})


@app.route("/api/narration", methods=["GET"])
def get_narration():
    title = safe_title(request.args.get("title", ""))
    path = os.path.join(VIDEOS_DIR, title, "narration.txt")
    if not os.path.exists(path):
        return jsonify({"content": None})
    with open(path) as f:
        return jsonify({"content": f.read()})


@app.route("/api/narration/save", methods=["POST"])
def save_narration():
    data = request.json
    title = safe_title(data.get("title", ""))
    content = data.get("content", "")
    if not title:
        return jsonify({"status": "error", "error": "No title"})
    project_dir = os.path.join(VIDEOS_DIR, title)
    os.makedirs(project_dir, exist_ok=True)
    path = os.path.join(project_dir, "narration.txt")
    with open(path, "w") as f:
        f.write(content)
    return jsonify({"status": "ok"})


@app.route("/api/cref", methods=["GET"])
def get_cref():
    title = safe_title(request.args.get("title", ""))
    cref_path = os.path.join(VIDEOS_DIR, title, "CREF.txt")
    if not os.path.exists(cref_path):
        return jsonify({"characters": []})

    characters = []
    with open(cref_path) as f:
        for line in f:
            line = line.strip()
            if not line or "=" in line or "CHARACTER" in line.upper():
                continue

            pipe_parts = line.split("|")
            desc_part = pipe_parts[0].rstrip(".")
            words_part = pipe_parts[1].strip() if len(pipe_parts) > 1 else ""

            comma_parts = desc_part.split(",", 1)
            name = comma_parts[0].strip()
            description = comma_parts[1].strip() if len(comma_parts) > 1 else ""
            narration_words = [w.strip() for w in words_part.split(",") if w.strip()]

            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", name).lower()
            ref_img = os.path.join(VIDEOS_DIR, title, f"ref_{safe_name}.png")
            image_url = (
                f"/api/ref-image?title={safe_title(title)}&name={safe_name}"
                if os.path.exists(ref_img)
                else None
            )

            characters.append(
                {
                    "name": name,
                    "safe_name": safe_name,
                    "description": description,
                    "image": image_url,
                    "narration_words": narration_words,
                }
            )

    return jsonify({"characters": characters})


@app.route("/api/cref/save", methods=["POST"])
def save_cref():
    data = request.json
    title = safe_title(data.get("title", ""))
    char_name = data.get("name", "")
    original_name = data.get("original_name", "")
    new_desc = data.get("description", "")
    if not title or not char_name:
        return jsonify({"status": "error", "error": "Missing title or name"})

    cref_path = os.path.join(VIDEOS_DIR, title, "CREF.txt")
    if not os.path.exists(cref_path):
        return jsonify({"status": "error", "error": "CREF.txt not found"})

    renamed = False
    if original_name and original_name != char_name:
        old_safe = re.sub(r"[^a-zA-Z0-9]", "_", original_name).lower()
        new_safe = re.sub(r"[^a-zA-Z0-9]", "_", char_name).lower()
        old_img = os.path.join(VIDEOS_DIR, title, f"ref_{old_safe}.png")
        new_img = os.path.join(VIDEOS_DIR, title, f"ref_{new_safe}.png")
        if os.path.exists(old_img):
            os.rename(old_img, new_img)
            comfy_input = "/home/henry/comfy/ComfyUI/input"
            old_ci = os.path.join(comfy_input, f"ref_{old_safe}.png")
            new_ci = os.path.join(comfy_input, f"ref_{new_safe}.png")
            if os.path.exists(old_ci):
                os.rename(old_ci, new_ci)
        renamed = True

    lines = []
    with open(cref_path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or "=" in stripped or "CHARACTER" in stripped.upper():
                lines.append(line)
                continue
            pipe_parts = stripped.split("|")
            desc_part = pipe_parts[0].rstrip(".")
            words_part = pipe_parts[1] if len(pipe_parts) > 1 else ""
            comma_parts = desc_part.split(",", 1)
            name = comma_parts[0].strip()
            if name == original_name or (not original_name and name == char_name):
                updated = f"{char_name}, {new_desc}"
                if words_part:
                    updated += f"|{words_part}"
                lines.append(updated + "\n")
            else:
                lines.append(line)

    with open(cref_path, "w") as f:
        f.writelines(lines)

    return jsonify({"status": "ok", "renamed": renamed})


@app.route("/api/cref/delete", methods=["POST"])
def delete_cref():
    import shutil

    data = request.json
    title = safe_title(data.get("title", ""))
    char_name = data.get("name", "")
    safe_name = data.get("safe_name", "")
    if not title or not char_name:
        return jsonify({"status": "error", "error": "Missing title or name"})

    cref_path = os.path.join(VIDEOS_DIR, title, "CREF.txt")
    if not os.path.exists(cref_path):
        return jsonify({"status": "error", "error": "CREF.txt not found"})

    lines = []
    with open(cref_path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or "=" in stripped or "CHARACTER" in stripped.upper():
                lines.append(line)
                continue
            pipe_parts = stripped.split("|")
            desc_part = pipe_parts[0].rstrip(".")
            comma_parts = desc_part.split(",", 1)
            name = comma_parts[0].strip()
            if name == char_name:
                continue
            lines.append(line)

    with open(cref_path, "w") as f:
        f.writelines(lines)

    ref_img = os.path.join(VIDEOS_DIR, title, f"ref_{safe_name}.png")
    if os.path.exists(ref_img):
        os.remove(ref_img)
    comfy_input = "/home/henry/comfy/ComfyUI/input"
    ci_img = os.path.join(comfy_input, f"ref_{safe_name}.png")
    if os.path.exists(ci_img):
        os.remove(ci_img)

    return jsonify({"status": "ok"})


@app.route("/api/cref/regenerate", methods=["POST"])
def regenerate_cref():
    import shutil

    data = request.json
    if not data:
        return jsonify({"status": "error", "error": "Invalid or missing JSON body"})
    title = safe_title(data.get("title", ""))
    safe_name = data.get("safe_name", "")
    description = data.get("description", "")
    if not title or not safe_name or not description:
        return jsonify({"status": "error", "error": "Missing parameters"})

    project_dir = os.path.join(VIDEOS_DIR, title)
    config_path = os.path.join(project_dir, "project.json")
    image_model = "geminiproxy"
    image_style = "Stick Figure"
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
            image_model = config.get("image_model", "geminiproxy")
            image_style = config.get("image_style", "Stick Figure")

    style_desc = STYLE_DESCRIPTIONS.get(image_style, STYLE_DESCRIPTIONS["Stick Figure"])
    prompt = f"{style_desc}, {description}"
    output_path = os.path.join(project_dir, f"ref_{safe_name}.png")
    comfy_input = "/home/henry/comfy/ComfyUI/input"

    try:
        if image_model == "geminiproxy":
            ok = _generate_thumbnail_image_geminiproxy(prompt, output_path)
            if not ok:
                return jsonify({"status": "error", "error": "GeminiProxy failed"})
            if os.path.exists(output_path) and os.path.isdir(comfy_input):
                shutil.copy2(
                    output_path, os.path.join(comfy_input, f"ref_{safe_name}.png")
                )
        else:

            def _is_flux(m):
                return "flux" in m.lower()

            if _is_flux(image_model):
                clip2 = "t5xxl_fp8_e4m3fn.safetensors"
                vae = "ae.safetensors"
                workflow = {
                    "1": {
                        "class_type": "UNETLoader",
                        "inputs": {
                            "unet_name": image_model,
                            "weight_dtype": "fp8_e4m3fn",
                        },
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
                        "inputs": {"clip": ["2", 0], "text": prompt},
                    },
                    "5": {
                        "class_type": "CLIPTextEncode",
                        "inputs": {"clip": ["2", 0], "text": ""},
                    },
                    "6": {
                        "class_type": "EmptySD3LatentImage",
                        "inputs": {"width": 832, "height": 480, "batch_size": 1},
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
                        "inputs": {
                            "filename_prefix": f"ref_{safe_name}",
                            "images": ["8", 0],
                        },
                    },
                }
            else:
                workflow = {
                    "3": {
                        "class_type": "KSampler",
                        "inputs": {
                            "cfg": 2,
                            "denoise": 1,
                            "latent_image": ["5", 0],
                            "model": ["4", 0],
                            "negative": ["7", 0],
                            "positive": ["6", 0],
                            "sampler_name": "euler",
                            "scheduler": "sgm_uniform",
                            "seed": random.randint(0, 999999),
                            "steps": 30,
                        },
                    },
                    "4": {
                        "class_type": "CheckpointLoaderSimple",
                        "inputs": {"ckpt_name": image_model},
                    },
                    "5": {
                        "class_type": "EmptyLatentImage",
                        "inputs": {"width": 832, "height": 480, "batch_size": 1},
                    },
                    "6": {
                        "class_type": "CLIPTextEncode",
                        "inputs": {"clip": ["4", 1], "text": prompt},
                    },
                    "7": {
                        "class_type": "CLIPTextEncode",
                        "inputs": {
                            "clip": ["4", 1],
                            "text": "blurry, deformed, ugly, scary, dark, violent, low quality, watermark, text",
                        },
                    },
                    "8": {
                        "class_type": "VAEDecode",
                        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                    },
                    "9": {
                        "class_type": "SaveImage",
                        "inputs": {
                            "filename_prefix": f"ref_{safe_name}",
                            "images": ["8", 0],
                        },
                    },
                }
            resp = requests.post(
                "http://127.0.0.1:8188/prompt", json={"prompt": workflow}
            )
            resp_data = resp.json()
            if "error" in resp_data:
                return jsonify({"status": "error", "error": resp_data["error"]})
            prompt_id = resp_data["prompt_id"]
            for _ in range(60):
                time.sleep(3)
                history = requests.get(
                    f"http://127.0.0.1:8188/history/{prompt_id}"
                ).json()
                if prompt_id in history:
                    for node_out in history[prompt_id].get("outputs", {}).values():
                        for img in node_out.get("images", []):
                            src = os.path.join(
                                "/home/henry/comfy/ComfyUI/output", img["filename"]
                            )
                            if os.path.exists(src):
                                shutil.copy2(src, output_path)
                                shutil.copy2(
                                    src,
                                    os.path.join(comfy_input, f"ref_{safe_name}.png"),
                                )
                    break
            else:
                return jsonify({"status": "error", "error": "ComfyUI timeout"})
        return jsonify({"status": "ok", "prompt": prompt, "image_model": image_model})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/ref-image", methods=["GET"])
def get_ref_image():
    title = safe_title(request.args.get("title", ""))
    name = request.args.get("name", "")
    path = os.path.join(VIDEOS_DIR, title, f"ref_{name}.png")
    if not os.path.exists(path):
        return "", 404
    return send_file(path, mimetype="image/png")


@app.route("/api/clip-image", methods=["GET"])
def get_clip_image():
    title = safe_title(request.args.get("title", ""))
    name = os.path.basename(request.args.get("name", ""))
    path = os.path.join(VIDEOS_DIR, title, "clips", name)
    if not os.path.exists(path):
        return "", 404
    mime = "video/mp4" if name.endswith(".mp4") else "image/png"
    return send_file(path, mimetype=mime)


@app.route("/api/clips", methods=["GET"])
def get_clips():
    title = safe_title(request.args.get("title", ""))
    clips_dir = os.path.join(VIDEOS_DIR, title, "clips")
    if not os.path.exists(clips_dir):
        return jsonify({"clips": []})
    clips = sorted(f for f in os.listdir(clips_dir) if f.endswith((".mp4", ".png")))
    return jsonify({"clips": clips})


@app.route("/api/clip/regenerate", methods=["POST"])
def regenerate_clip():
    data = request.json
    if not data:
        return jsonify({"status": "error", "error": "Invalid or missing JSON body"})
    title = safe_title(data.get("title", ""))
    clip_name = data.get("clip_name", "")
    new_prompt = data.get("prompt", "")
    idx = data.get("index")

    if not title or not clip_name or idx is None:
        return jsonify({"status": "error", "error": "Missing parameters"})

    project_dir = os.path.join(VIDEOS_DIR, title)
    prompts_path = os.path.join(project_dir, "prompts.txt")
    if not os.path.exists(prompts_path):
        return jsonify({"status": "error", "error": "prompts.txt not found"})

    # Update the matching prompt line in prompts.txt
    try:
        with open(prompts_path, "r") as f:
            lines = f.readlines()

        # Find the nth non-header prompt line and update it
        prompt_count = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or "=" in stripped or "Video Generation" in stripped:
                continue
            if "|||" in stripped or stripped.startswith("Prompt"):
                if prompt_count == idx:
                    # Preserve the sentence part if present
                    if "|||" in stripped:
                        _, sentence = stripped.split("|||", 1)
                        lines[i] = new_prompt.strip() + "|||" + sentence.strip() + "\n"
                    else:
                        lines[i] = new_prompt.strip() + "\n"
                    break
                prompt_count += 1

        with open(prompts_path, "w") as f:
            f.writelines(lines)
    except Exception as e:
        return jsonify(
            {"status": "error", "error": f"Failed to update prompts.txt: {e}"}
        )

    # Load config to know which model and style to use
    config_path = os.path.join(project_dir, "project.json")
    image_model = "geminiproxy"
    image_style = "Stick Figure"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            image_model = config.get("image_model", "geminiproxy")
            image_style = config.get("image_style", "Stick Figure")

    # Prepend style description if not already present
    style_desc = STYLE_DESCRIPTIONS.get(image_style, STYLE_DESCRIPTIONS["Stick Figure"])
    if style_desc.lower() not in new_prompt.lower():
        gen_prompt = f"{style_desc}, {new_prompt}"
    else:
        gen_prompt = new_prompt

    clip_path = os.path.join(project_dir, "clips", clip_name)
    os.makedirs(os.path.dirname(clip_path), exist_ok=True)

    try:
        if image_model == "geminiproxy":
            ok = _generate_thumbnail_image_geminiproxy(gen_prompt, clip_path)
            if not ok:
                return jsonify({"status": "error", "error": "GeminiProxy failed"})
        else:
            # ComfyUI path
            import shutil

            tmp_dir = os.path.join(project_dir, f"_regen_{idx}")
            os.makedirs(tmp_dir, exist_ok=True)
            shutil.copy2(config_path, os.path.join(tmp_dir, "project.json"))
            with open(os.path.join(tmp_dir, "prompts.txt"), "w") as f:
                f.write(f"Prompt 1: {gen_prompt}|||{title}\n")
            # Copy reference images so generatevideo.py can find them
            for fname in os.listdir(project_dir):
                if fname.startswith("ref_") and fname.endswith(".png"):
                    shutil.copy2(
                        os.path.join(project_dir, fname), os.path.join(tmp_dir, fname)
                    )

            # Use generate_video.py logic for single clip
            GEN_SCRIPT = "/home/henry/APPS/YTVideos/scripts/generatevideo.py"
            subprocess.run(
                ["python", GEN_SCRIPT, "--project-dir", tmp_dir, "--clips", "1"],
                timeout=300,
                check=True,
            )

            generated = os.path.join(tmp_dir, "clips", "clip_01.png")
            if os.path.exists(generated):
                shutil.copy2(generated, clip_path)
            else:
                return jsonify(
                    {"status": "error", "error": "ComfyUI failed to generate clip"}
                )
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return jsonify(
            {"status": "ok", "prompt": gen_prompt, "image_model": image_model}
        )
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/pipeline-logs", methods=["GET"])
def pipeline_logs():
    """Poll for new log lines and running state."""
    return jsonify({"running": _pipeline.running, "lines": _pipeline.drain()})


@app.route("/api/thumbnail", methods=["GET"])
def get_thumbnail():
    title = safe_title(request.args.get("title", ""))
    if not title:
        return "No title", 400
    thumb_path = os.path.join(VIDEOS_DIR, title, "thumbnail.png")
    if not os.path.exists(thumb_path):
        return "Not found", 404
    return send_file(thumb_path, mimetype="image/png")


@app.route("/api/video", methods=["GET"])
def get_video():
    from flask import Response

    title = safe_title(request.args.get("title", ""))
    if not title:
        return "No title", 400
    video_path = os.path.join(VIDEOS_DIR, title, "output.mp4")
    if not os.path.exists(video_path):
        return "Not found", 404
    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("Range")
    if range_header:
        byte_start, byte_end = 0, file_size - 1
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            byte_start = int(m.group(1))
            if m.group(2):
                byte_end = int(m.group(2))
        length = byte_end - byte_start + 1
        with open(video_path, "rb") as f:
            f.seek(byte_start)
            data = f.read(length)
        resp = Response(data, 206, mimetype="video/mp4", direct_passthrough=True)
        resp.headers["Content-Range"] = f"bytes {byte_start}-{byte_end}/{file_size}"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Length"] = length
        return resp
    resp = Response(
        open(video_path, "rb"), 200, mimetype="video/mp4", direct_passthrough=True
    )
    resp.headers["Accept-Ranges"] = "bytes"
    resp.headers["Content-Length"] = file_size
    return resp


@app.route("/api/video/exists", methods=["GET"])
def video_exists():
    title = safe_title(request.args.get("title", ""))
    if not title:
        return jsonify({"exists": False})
    video_path = os.path.join(VIDEOS_DIR, title, "output.mp4")
    return jsonify({"exists": os.path.exists(video_path)})


@app.route("/api/description", methods=["GET"])
def get_description():
    title = safe_title(request.args.get("title", ""))
    if not title:
        return jsonify({"content": ""})
    desc_path = os.path.join(VIDEOS_DIR, title, "description.txt")
    if not os.path.exists(desc_path):
        return jsonify({"content": ""})
    with open(desc_path, "r") as f:
        return jsonify({"content": f.read()})


@app.route("/api/description", methods=["POST"])
def save_description_api():
    data = request.json
    title = safe_title(data.get("title", ""))
    content = data.get("content", "")
    if not title:
        return jsonify({"status": "error", "error": "No title"})
    desc_path = os.path.join(VIDEOS_DIR, title, "description.txt")
    with open(desc_path, "w") as f:
        f.write(content)
    return jsonify({"status": "ok"})


@app.route("/api/thumbnail/regenerate", methods=["POST"])
def regenerate_thumbnail():
    data = request.json
    title = safe_title(data.get("title", ""))
    image_model = data.get("image_model", "geminiproxy")
    image_style = data.get("image_style", "")
    ai_helper = data.get("ai_helper", "")
    if not title:
        return jsonify({"status": "error", "error": "No title"})
    project_dir = os.path.join(VIDEOS_DIR, title)
    narration_path = os.path.join(project_dir, "narration.txt")
    if not os.path.exists(narration_path):
        return jsonify({"status": "error", "error": "narration.txt not found"})

    config_path = os.path.join(project_dir, "project.json")
    proj_cfg = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            proj_cfg = json.load(f)
    if not ai_helper:
        ai_helper = proj_cfg.get("ai_helper", "opencode")
    if image_style:
        proj_cfg["image_style"] = image_style
        with open(config_path, "w") as f:
            json.dump(proj_cfg, f, indent=2)

    with open(narration_path) as f:
        narration_text = f.read()

    thumb_path = os.path.join(project_dir, "thumbnail.png")
    thumb_backup = thumb_path + ".bak"
    if os.path.exists(thumb_path):
        import shutil as _shutil

        _shutil.copy2(thumb_path, thumb_backup)
        os.remove(thumb_path)

    _pipeline.running = True
    _pipeline.logs.clear()
    try:
        _generate_thumbnail_and_metadata(
            title, project_dir, narration_text, ai_helper, image_model, image_style
        )
        _pipeline.running = False
        if os.path.exists(thumb_path):
            if os.path.exists(thumb_backup):
                os.remove(thumb_backup)
            return jsonify({"status": "ok"})
        _pipeline.running = False
        if os.path.exists(thumb_backup):
            _shutil.copy2(thumb_backup, thumb_path)
            os.remove(thumb_backup)
        return jsonify({"status": "error", "error": "Thumbnail not generated"})
    except Exception as e:
        _pipeline.running = False
        if os.path.exists(thumb_backup):
            _shutil.copy2(thumb_backup, thumb_path)
            os.remove(thumb_backup)
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/thumbnail/rebake", methods=["POST"])
def rebake_thumbnail():
    """Re-apply caption overlay to thumbnail_raw.png → thumbnail.png."""
    import shutil

    data = request.json
    title = safe_title(data.get("title", ""))
    if not title:
        return jsonify({"status": "error", "error": "No title"})

    project_dir = os.path.join(VIDEOS_DIR, title)
    thumb_raw = os.path.join(project_dir, "thumbnail_raw.png")
    thumb_out = os.path.join(project_dir, "thumbnail.png")

    if not os.path.exists(thumb_raw):
        # No raw saved — use current thumbnail as the raw source
        if not os.path.exists(thumb_out):
            return jsonify({"status": "error", "error": "No thumbnail found"})
        shutil.copy2(thumb_out, thumb_raw)

    caption_position = data.get("caption_position", "bottom")
    font_name = data.get("font_name", "DejaVu Sans")
    font_size = float(data.get("font_size", 1.0))
    bg_opacity = int(data.get("bg_opacity", 180))
    shadow_offset = int(data.get("shadow_offset", 0))

    # Save caption settings to project.json
    config_path = os.path.join(project_dir, "project.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            proj_cfg = json.load(f)
        proj_cfg.update(
            {
                "thumb_caption_position": caption_position,
                "thumb_font_name": font_name,
                "thumb_font_size": font_size,
                "thumb_bg_opacity": bg_opacity,
                "thumb_shadow": shadow_offset,
            }
        )
        with open(config_path, "w") as f:
            json.dump(proj_cfg, f, indent=2)

    if caption_position == "none":
        shutil.copy2(thumb_raw, thumb_out)
        return jsonify({"status": "ok"})

    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        img = Image.open(thumb_raw).convert("RGBA")
        W, H = img.size
        draw = ImageDraw.Draw(img)

        # Load font
        font_size_px = max(18, int(H * 0.065 * font_size))
        font = None
        for path in [
            f"/usr/share/fonts/truetype/{font_name}.ttf",
            f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            f"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            if os.path.exists(path):
                font = ImageFont.truetype(path, font_size_px)
                break
        if not font:
            font = ImageFont.load_default()

        text = title
        lines = textwrap.wrap(text, width=max(10, int(W / font_size_px * 1.5)))
        line_h = font_size_px + 6
        block_h = line_h * len(lines) + 16

        if caption_position == "top":
            y0 = 0
        elif caption_position == "middle":
            y0 = (H - block_h) // 2
        else:  # bottom
            y0 = H - block_h

        # Draw background bar
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([0, y0, W, y0 + block_h], fill=(0, 0, 0, bg_opacity))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Draw text
        y = y0 + 8
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (W - tw) // 2
            if shadow_offset > 0:
                draw.text(
                    (x + shadow_offset, y + shadow_offset),
                    line,
                    font=font,
                    fill=(0, 0, 0, 200),
                )
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_h

        img.convert("RGB").save(thumb_out, "PNG")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/thumbnail/capture", methods=["POST"])
def capture_thumbnail():
    data = request.json
    title = safe_title(data.get("title", ""))
    if not title:
        return jsonify({"status": "error", "error": "No title"})
    project_dir = os.path.join(VIDEOS_DIR, title)
    thumb_path = os.path.join(project_dir, "thumbnail.png")
    try:
        ok = _capture_current_geminiproxy_image(thumb_path)
        if ok:
            return jsonify({"status": "ok"})
        return jsonify({"status": "error", "error": "No image found in Gemini tab"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


def _assemble_with_xfade(
    project_dir,
    narration_path,
    voice_model,
    voice_rate,
    transition_style,
    transition_duration,
):
    """Refactored assembly that uses a single ffmpeg filter_complex with xfade."""
    import glob as _glob
    import json
    import os
    import subprocess
    import re

    # In case there are some imports missing in this scope, we can rely on outer ones or re-import.
    # But since it's a module level function, it usually sees them.
    # However, let's be safe.

    # We need the global _pipeline
    global _pipeline
    p = _pipeline

    output_path = os.path.join(project_dir, "output.mp4")
    clips_dir = os.path.join(project_dir, "clips")
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    with open(narration_path) as f:
        lines = [l.strip() for l in f if l.strip()]

    # --- Step 1: TTS audio per line (same as original) ---
    p.push(f"Generating audio for xfade ({voice_model})...")
    for i, line in enumerate(lines, 1):
        audio_path = os.path.join(audio_dir, f"line_{i:02d}.mp3")
        if not os.path.exists(audio_path):
            try:
                subprocess.run(
                    [
                        "/home/henry/.local/bin/edge-tts",
                        "--voice",
                        voice_model,
                        f"--rate={voice_rate}",
                        "--text",
                        line,
                        "--write-media",
                        audio_path,
                    ],
                    check=True,
                    capture_output=True,
                )
            except Exception as e:
                p.push(f"  ⚠ TTS line {i} failed: {e}", "info")

    all_clips = sorted(
        _glob.glob(os.path.join(clips_dir, "clip_*.png"))
        + _glob.glob(os.path.join(clips_dir, "clip_*.mp4"))
    )
    if not all_clips:
        p.push("⚠ No clips found for xfade", "error")
        return

    # Filter out clips without matching audio
    segments = []
    for clip_path in all_clips:
        m = re.search(r"clip_(\d+)", os.path.basename(clip_path))
        if not m:
            continue
        num = m.group(1)
        audio_path = os.path.join(audio_dir, f"line_{num}.mp3")
        if os.path.exists(audio_path):
            try:
                out = (
                    subprocess.check_output(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_entries",
                            "format=duration",
                            "-of",
                            "default=noprint_wrappers=1:nokey=1",
                            audio_path,
                        ]
                    )
                    .strip()
                    .decode()
                )
                dur = float(out)
                segments.append(
                    {
                        "image": clip_path,
                        "audio": audio_path,
                        "duration": dur,
                        "is_video": clip_path.endswith(".mp4"),
                    }
                )
            except:
                pass

    if not segments:
        p.push("⚠ No segments with audio found", "error")
        return

    # --- Step 2: Concat individual audio files ---
    p.push("Concatenating audio for single-pass xfade...")
    full_audio_path = os.path.join(audio_dir, "full_audio.mp3")
    alist_path = os.path.join(audio_dir, "audio_list.txt")
    with open(alist_path, "w") as f:
        for seg in segments:
            f.write(f"file '{os.path.abspath(seg['audio'])}'\n")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            alist_path,
            "-c",
            "copy",
            full_audio_path,
        ],
        check=True,
        capture_output=True,
    )

    # --- Step 3: Single-pass FFmpeg with xfade filter_complex ---
    p.push(f"Assembling with {transition_style} xfade...")
    res_w, res_h = 1280, 720
    cmd = ["ffmpeg", "-y"]
    # Total audio duration for the loop time
    total_audio_dur = sum(s["duration"] for s in segments)

    for seg in segments:
        if seg["is_video"]:
            cmd.extend(
                [
                    "-stream_loop",
                    "-1",
                    "-t",
                    f"{total_audio_dur + 5:.3f}",
                    "-i",
                    seg["image"],
                ]
            )
        else:
            cmd.extend(
                [
                    "-loop",
                    "1",
                    "-r",
                    "25",
                    "-t",
                    f"{total_audio_dur + 5:.3f}",
                    "-i",
                    seg["image"],
                ]
            )
    cmd.extend(["-i", full_audio_path])

    filter_parts = []
    for i, seg in enumerate(segments):
        label = f"s{i}"
        filter_parts.append(
            f"[{i}:v]scale={res_w}:{res_h}:force_original_aspect_ratio=decrease,pad={res_w}:{res_h}:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p[{label}]"
        )

    current_offset = 0.0
    for i in range(len(segments) - 1):
        current_offset += segments[i]["duration"]
        xfade_offset = max(0, current_offset - (transition_duration / 2))
        input1 = "[s0]" if i == 0 else f"[v{i - 1}]"
        input2 = f"[s{i + 1}]"
        output_label = f"[v{i}]" if i < len(segments) - 2 else "[vout]"
        filter_parts.append(
            f"{input1}{input2}xfade=transition={transition_style}:duration={transition_duration}:offset={xfade_offset:.3f}{output_label}"
        )

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vout]",
            "-map",
            f"{len(segments)}:a",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-t",
            f"{total_audio_dur:.3f}",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output_path,
        ]
    )

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        p.push(f"✓ xfade output.mp4 assembled", "success")
    except Exception as e:
        p.push(f"✗ xfade assembly failed: {e}", "error")


@app.route("/api/browse", methods=["GET"])
def browse_project():
    title = safe_title(request.args.get("title", ""))
    if not title:
        return jsonify({"error": "No title"}), 400
    project_dir = os.path.join(VIDEOS_DIR, title)
    # Resolve optional subpath safely
    subpath = request.args.get("subpath", "")
    if subpath:
        target_dir = os.path.realpath(os.path.join(project_dir, subpath))
        if not target_dir.startswith(os.path.realpath(project_dir)):
            return jsonify({"error": "Invalid path"}), 400
    else:
        target_dir = project_dir
    if not os.path.exists(target_dir):
        return jsonify({"error": "Not found"}), 404
    files = []
    for entry in sorted(
        os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name.lower())
    ):
        size = ""
        if entry.is_file():
            b = entry.stat().st_size
            size = f"{b / 1024:.1f} KB" if b < 1_048_576 else f"{b / 1_048_576:.1f} MB"
        files.append({"name": entry.name, "is_dir": entry.is_dir(), "size": size})
    return jsonify({"files": files})


@app.route("/api/browse/delete", methods=["POST"])
def browse_delete():
    data = request.json
    title = safe_title(data.get("title", ""))
    name = os.path.basename(data.get("name", ""))
    subpath = data.get("subpath", "")
    if not title or not name:
        return jsonify({"ok": False, "error": "Missing params"})
    project_dir = os.path.join(VIDEOS_DIR, title)
    if subpath:
        base = os.path.realpath(os.path.join(project_dir, subpath))
        if not base.startswith(os.path.realpath(project_dir)):
            return jsonify({"ok": False, "error": "Invalid path"})
        target = os.path.join(base, name)
    else:
        target = os.path.join(project_dir, name)
    if not os.path.exists(target):
        return jsonify({"ok": False, "error": "Not found"})
    try:
        if os.path.isdir(target):
            import shutil

            shutil.rmtree(target)
        else:
            os.remove(target)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/browse/file", methods=["GET"])
def browse_file():
    import mimetypes

    title = safe_title(request.args.get("title", ""))
    subpath = request.args.get("subpath", "")
    name = os.path.basename(request.args.get("name", ""))
    if not title or not name:
        return "Missing params", 400
    project_dir = os.path.realpath(os.path.join(VIDEOS_DIR, title))
    if subpath:
        base = os.path.realpath(os.path.join(project_dir, subpath))
        if not base.startswith(project_dir):
            return "Invalid path", 400
    else:
        base = project_dir
    target = os.path.join(base, name)
    if not os.path.exists(target) or not os.path.isfile(target):
        return "Not found", 404
    mime, _ = mimetypes.guess_type(target)
    mime = mime or "application/octet-stream"
    return send_file(target, mimetype=mime)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7070, debug=True)
