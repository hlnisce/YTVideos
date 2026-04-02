#!/usr/bin/env python3
"""
prepare.py - Automated story preparation script
Takes narration.txt as input and generates:
1. CREF.txt (character reference descriptions)
2. prompts.txt (numbered video generation prompts)
3. Character reference images (using ComfyUI)

Usage: python prepare.py <narration_file>
"""

import os
import sys
import re
import subprocess
import requests
import time
import shutil
import json
import base64

COMFYUI_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

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


def load_project_config():
    """Load project configuration from project.json."""
    config_path = os.path.join(PARENT_DIR, "project.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


PROJECT_CONFIG = load_project_config()
IMAGE_MODEL = PROJECT_CONFIG.get(
    "image_model", "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
)
KEY_SERVICE_URL = "http://localhost:7755"


def _call_ai(prompt, ai_helper, timeout=120):
    """Send a prompt to the configured AI helper and return the text reply."""
    if ai_helper == "claude":
        resp = requests.post(
            f"{KEY_SERVICE_URL}/tmux/chat",
            json={"text": f"claude: {prompt}", "timeout": timeout},
            timeout=timeout + 10,
        )
        resp.raise_for_status()
        return resp.json().get("reply", "").strip()

    if ai_helper == "geminiproxy":
        import websocket as _ws
        import json as _json

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
        deadline = time.monotonic() + timeout
        poll_id = [1]
        ws = _ws.create_connection(ws_url, timeout=10, suppress_origin=True)

        def cdp_eval(js):
            if time.monotonic() > deadline:
                return None
            pid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                _json.dumps(
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
                msg = _json.loads(ws.recv())
                if msg.get("id") == pid:
                    return msg.get("result", {}).get("result", {}).get("value")
            return None

        cdp_eval("""(function() {
            var el = document.querySelector('[contenteditable="true"]');
            if (el) { el.focus(); el.click(); }
        })()""")
        time.sleep(0.3)
        pre_last = cdp_eval(f"""(function() {{
            var els = document.querySelectorAll({_json.dumps(selector)});
            return els.length ? els[els.length - 1].innerText : null;
        }})()""")
        mid = poll_id[0]
        poll_id[0] += 1
        ws.send(
            _json.dumps(
                {"id": mid, "method": "Input.insertText", "params": {"text": prompt}}
            )
        )
        ws.recv()
        time.sleep(0.2)
        for ev in ("keyDown", "keyUp"):
            mid = poll_id[0]
            poll_id[0] += 1
            ws.send(
                _json.dumps(
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
                var els = document.querySelectorAll({_json.dumps(selector)});
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
        return reply.strip()

    # Default: opencode
    result = subprocess.run(
        ["/home/henry/.opencode/bin/opencode", "run", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", result.stdout).strip()


def _extract_and_describe_characters_with_ai(narration_text, ai_helper):
    """Single AI call: extract all characters from narration and get visual descriptions.
    Returns dict of {canonical_name: visual_description} or empty dict on failure."""
    prompt = (
        f"Read this children's story narration:\n\n{narration_text}\n\n"
        f"List every character that appears in the story, including groups like 'stepsisters' or 'mice'. "
        f"For each, write a one-sentence visual description "
        f"covering physical appearance only (hair, eyes, skin, clothing). "
        f"Output ONLY one character per line in this exact format:\n"
        f"Name | visual description sentence\n\n"
        f"Example:\n"
        f"Red Riding Hood | a young girl with long auburn hair, bright blue eyes, fair skin, "
        f"wearing a red hooded cape over a white blouse and brown skirt\n"
        f"Wolf | a large grey wolf with sharp yellow eyes, dark fur, and a long bushy tail\n\n"
        f"No numbering, no extra commentary, no blank lines between entries."
    )
    try:
        reply = _call_ai(prompt, ai_helper, timeout=120)
        if not reply:
            return {}
        result = {}
        for line in reply.split("\n"):
            line = line.strip()
            if "|" not in line:
                continue
            parts = line.split("|", 1)
            name = parts[0].strip()
            desc = parts[1].strip().strip('"').strip("'")
            if name and desc:
                if not desc.lower().startswith(name.lower()):
                    desc = f"{name}, {desc}"
                result[name] = desc
        return result
    except Exception as e:
        print(f"  AI character extraction failed: {e}")
        return {}


def extract_characters_from_narration(narration_text):
    """
    Extract character names from narration.
    Looks for multi-word names and common story characters.
    """
    characters = set()

    # Common story character patterns
    common_patterns = [
        r"\bLittle Red Riding Hood\b",
        r"\bRed Riding Hood\b",
        r"\bBig Bad Wolf\b",
        r"\bWolf\b",
        r"\bGrandmother\b",
        r"\bGrandma\b",
        r"\bMother\b",
        r"\bMom\b",
        r"\bWoodcutter\b",
        r"\bWoodsman\b",
        r"\bWoodman\b",
        r"\bWood-cutter\b",
        r"\bHunter\b",
        r"\bCinderella\b",
        r"\bSnow White\b",
        r"\bSleeping Beauty\b",
        r"\bRapunzel\b",
        r"\bHansel\b",
        r"\bGretel\b",
        r"\bJack\b",
        r"\bGiant\b",
        r"\bFairy\b",
        r"\bPrince\b",
        r"\bPrincess\b",
        r"\bKing\b",
        r"\bQueen\b",
    ]

    # Check for common patterns first
    for pattern in common_patterns:
        matches = re.findall(pattern, narration_text, re.IGNORECASE)
        for match in matches:
            characters.add(match.title())

    characters = list(characters)

    # If no common patterns found, try to extract capitalized multi-word names
    if not characters:
        # Find sequences of capitalized words (potential names)
        name_patterns = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", narration_text
        )

        # Filter out common non-name phrases
        exclude_phrases = {
            "Once Upon A Time",
            "The End",
            "And They",
            "But She",
            "So He",
            "Remember To",
            "Good Morning",
            "What Big",
            "All The Better",
        }

        word_counts = {}
        for name in name_patterns:
            if name not in exclude_phrases and len(name.split()) <= 4:
                word_counts[name] = word_counts.get(name, 0) + 1

        # Return names that appear at least 2 times
        characters = {name for name, count in word_counts.items() if count >= 2}

    return list(characters)


def read_cref_file(cref_path):
    """Parse an existing CREF.txt and return ({name: description}, {name: [narration_words]})."""
    descriptions = {}
    narration_words = {}
    with open(cref_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("=") or "CHARACTER REFERENCE" in line:
                continue
            # Format: description|narration_words
            parts = line.split("|", 1)
            desc = parts[0].strip()
            if not desc:
                continue
            # Name is everything before the first comma
            name = desc.split(",")[0].strip()
            if name:
                descriptions[name] = desc
                words = (
                    [w.strip().lower() for w in parts[1].split(",")]
                    if len(parts) > 1
                    else []
                )
                narration_words[name] = [w for w in words if w]
    return descriptions, narration_words


def generate_cref_file(
    character_descriptions, output_dir, narration_text="", ai_helper="opencode"
):
    """Generate CREF.txt with character descriptions and narration word mappings."""
    cref_path = os.path.join(output_dir, "CREF.txt")

    # Map narration subjects to each character
    narration_words = {char: [] for char in character_descriptions}
    if narration_text:
        for line in narration_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            subjects = _extract_subjects(line)
            for subject in subjects:
                best_char = None
                best_score = 0
                for char_name, char_desc in character_descriptions.items():
                    score = _score_subject(subject, char_name, char_desc)
                    if score > best_score:
                        best_score = score
                        best_char = char_name
                if (
                    best_char
                    and best_score > 0
                    and subject not in narration_words[best_char]
                ):
                    narration_words[best_char].append(subject)

    # Write CREF file: Name|description|word1, word2, word3
    with open(cref_path, "w") as f:
        f.write("CHARACTER REFERENCE (CREF)\n")
        f.write("=" * 40 + "\n\n")

        for char, desc in character_descriptions.items():
            words = ", ".join(narration_words[char])
            f.write(f"{desc}|{words}\n")

    print(f"Generated: {cref_path}")
    return character_descriptions


def get_main_character(narration_text, character_descriptions):
    """Return the character description for the most-mentioned character in the narration."""
    narration_lower = narration_text.lower()
    sorted_chars = sorted(
        character_descriptions.items(), key=lambda x: len(x[0]), reverse=True
    )
    best_char, best_count = None, 0
    for char_name, description in sorted_chars:
        # Use word-boundary match so "mother" inside "grandmother" isn't counted
        count = len(
            re.findall(r"\b" + re.escape(char_name.lower()) + r"\b", narration_lower)
        )
        if count > best_count:
            best_count = count
            best_char = description
    if best_char:
        return best_char
    if character_descriptions:
        return list(character_descriptions.values())[0]
    return "a character"


CHARACTER_NOUNS = [
    "girl",
    "boy",
    "mother",
    "father",
    "grandmother",
    "grandma",
    "grandfather",
    "grandpa",
    "wolf",
    "woodcutter",
    "woodsman",
    "woodman",
    "hunter",
    "prince",
    "princess",
    "king",
    "queen",
    "fairy",
    "witch",
    "wizard",
    "giant",
    "dragon",
    "knight",
    "rabbit",
    "fox",
    "bear",
    "deer",
    "bird",
    "cat",
    "dog",
    "horse",
    "man",
    "woman",
    "child",
    "baby",
    "sister",
    "brother",
    "son",
    "daughter",
    "wife",
    "husband",
    "friend",
    "neighbor",
    "teacher",
    "doctor",
    "dwarf",
    "elf",
    "goblin",
    "troll",
    "ogre",
    "fairy godmother",
    "old woman",
    "old man",
    "young girl",
    "young boy",
    "little girl",
    "little boy",
]

STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "shall",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "out",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
    "but",
    "and",
    "or",
    "if",
    "while",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "he",
    "she",
    "they",
    "them",
    "his",
    "her",
    "their",
    "our",
    "my",
    "your",
    "we",
    "you",
    "who",
    "which",
    "what",
    "whom",
    "whose",
    "up",
    "about",
    "once",
    "upon",
    "time",
    "lived",
    "near",
    "edge",
    "great",
    "went",
    "said",
    "asked",
    "told",
    "replied",
    "thought",
    "saw",
    "found",
    "took",
    "gave",
    "came",
    "got",
    "made",
    "knew",
    "looked",
    "put",
    "saw",
    "seemed",
    "kept",
    "began",
    "felt",
    "left",
    "brought",
    "sweet",
    "dear",
    "old",
    "young",
    "little",
    "big",
    "good",
    "bad",
}


def _extract_subjects(line):
    """Extract character-like subjects from a narration line."""
    line_lower = line.lower()
    found = []

    # Check multi-word phrases first (longest match wins, whole-word only)
    for phrase in sorted(CHARACTER_NOUNS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(phrase) + r"\b", line_lower):
            found.append(phrase)

    # Check individual words not already covered by found phrases
    words = re.findall(r"[a-z]+", line_lower)
    for word in words:
        if word in CHARACTER_NOUNS and word not in STOP_WORDS:
            if not any(word in f for f in found):
                found.append(word)

    return found


def _score_subject(subject, char_name, char_desc):
    """Score how well a subject maps to a character. Higher = better match."""
    score = 0
    name_lower = char_name.lower()
    desc_lower = char_desc.lower()
    subject_words = set(subject.split())

    # Exact name match (whole word)
    if re.search(r"\b" + re.escape(subject) + r"\b", name_lower):
        score += 10

    # Word overlap with name
    name_words = set(name_lower.split())
    overlap = subject_words & name_words
    score += len(overlap) * 5

    # Subject word appears in description
    for word in subject_words:
        if len(word) > 2 and word in desc_lower:
            score += 2

    return score


def rewrite_prompts_with_character_names(
    source_lines, character_descriptions, ai_helper, narration_lines=None
):
    """Ask the AI to rewrite all prompt lines, replacing generic subjects with CREF character names.
    narration_lines: original story sentences in order, used as pronoun context.
    Returns a list of rewritten lines in the same order. Falls back to original lines on failure."""
    if not character_descriptions:
        return source_lines

    char_list = "\n".join(
        f"- {name}: {desc}" for name, desc in character_descriptions.items()
    )
    numbered = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(source_lines))

    narration_context = ""
    if narration_lines:
        narration_context = (
            f"Story narration (for pronoun context — use this to resolve 'she', 'he', 'they', etc.):\n"
            + "\n".join(f"{i + 1}. {l}" for i, l in enumerate(narration_lines))
            + "\n\n"
        )

    prompt = (
        f"You are rewriting image generation prompts for a story.\n\n"
        f"Characters in this story:\n{char_list}\n\n"
        f"{narration_context}"
        f"Rewrite each prompt below, replacing any generic subject words (she, he, the girl, the boy, "
        f"the wolf, grandmother, etc.) with the matching character's exact name from the list above. "
        f"Use the narration context above to resolve pronouns like 'she' or 'he' to the correct name. "
        f"Keep everything else exactly the same — do not add, remove, or rephrase anything else.\n\n"
        f"Output ONLY the rewritten prompts, one per line, numbered the same way.\n\n"
        f"{numbered}"
    )

    try:
        print(
            f"  Rewriting {len(source_lines)} prompts with character names via {ai_helper}..."
        )
        reply = _call_ai(prompt, ai_helper, timeout=120)
        if not reply:
            return source_lines
        rewritten = {}
        for line in reply.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(\d+)\.\s*(.*)", line)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(source_lines):
                    rewritten[idx] = m.group(2).strip()
        # Build result, falling back to original for any missing indices
        result = [rewritten.get(i, source_lines[i]) for i in range(len(source_lines))]
        print(f"  Character name substitution done.")
        return result
    except Exception as e:
        print(f"  AI subject rewrite failed ({e}) — using original lines")
        return source_lines


def get_scene_cref(
    line, character_descriptions, main_char_desc, cref_narration_words=None
):
    """Find which characters appear in this line by extracting subjects and mapping to CREF.
    Also directly checks for character names appearing in the line text."""
    line_lower = line.lower()
    matched_chars = []

    # Pass 1: direct name match — whole-word so "mother" inside "grandmother" is not counted
    for char_name in character_descriptions:
        if re.search(r"\b" + re.escape(char_name.lower()) + r"\b", line_lower):
            if char_name not in matched_chars:
                matched_chars.append(char_name)

    # Pass 2: generic noun extraction → scored mapping (for pronouns/aliases not already matched)
    subjects = _extract_subjects(line)
    for subject in subjects:
        best_char = None
        best_score = 0

        for char_name, char_desc in character_descriptions.items():
            if char_name in matched_chars:
                continue  # already found via direct name match
            score = _score_subject(subject, char_name, char_desc)
            if cref_narration_words and char_name in cref_narration_words:
                if subject.lower() in cref_narration_words[char_name]:
                    score += 15
            if score > best_score:
                best_score = score
                best_char = char_name

        if best_char and best_char not in matched_chars:
            matched_chars.append(best_char)

    return [character_descriptions[c] for c in matched_chars]


def generate_prompts_file(
    narration_lines,
    character_descriptions,
    output_dir,
    image_style="Stick Figure",
    cref_narration_words=None,
    ai_helper="opencode",
):
    """Generate prompts.txt with numbered prompts for each narration line."""
    prompts_path = os.path.join(output_dir, "prompts.txt")
    rawprompt_path = os.path.join(output_dir, "RawPrompt.txt")

    narration_text = "\n".join(narration_lines)
    main_char_desc = get_main_character(narration_text, character_descriptions)

    style_desc = STYLE_DESCRIPTIONS.get(image_style, STYLE_DESCRIPTIONS["Stick Figure"])

    # Use RawPrompt.txt if available, otherwise fall back to narration lines
    if os.path.exists(rawprompt_path):
        with open(rawprompt_path, "r") as f:
            source_lines = [l.strip() for l in f if l.strip()]
        print(f"Using RawPrompt.txt ({len(source_lines)} prompts)")
    else:
        source_lines = narration_lines

    # Let AI replace generic subjects (girl, wolf, etc.) with actual character names
    source_lines = rewrite_prompts_with_character_names(
        source_lines, character_descriptions, ai_helper, narration_lines
    )

    with open(prompts_path, "w") as f:
        f.write("Video Generation Prompts\n")
        f.write("=" * 40 + "\n\n")

        for i, line in enumerate(source_lines, 1):
            line = line.strip()
            if not line:
                continue

            line = re.sub(r"^\d+\.\s*", "", line)

            scene_crefs = get_scene_cref(
                line, character_descriptions, main_char_desc, cref_narration_words
            )
            if not scene_crefs:
                # No character detected — inject main character so the model has a visual anchor
                scene_crefs = [main_char_desc]
            scene_cref = ", ".join(scene_crefs)
            prompt = f"{style_desc}, {scene_cref}, {line}"

            # Use narration sentence for the ||| part if available, otherwise use the raw prompt
            narration_sentence = (
                narration_lines[i - 1].strip() if i - 1 < len(narration_lines) else line
            )
            narration_sentence = re.sub(r"^\d+\.\s*", "", narration_sentence)
            f.write(f"Prompt {i}: {prompt}|||{narration_sentence}\n\n")

    print(f"Generated: {prompts_path}")
    return len(source_lines)


COMFYUI_DIR = "/home/henry/comfy/ComfyUI"
COMFYUI_PYTHON = "/home/henry/comfy-venv/bin/python"


def comfyui_available():
    """Check if ComfyUI is reachable."""
    try:
        requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        return True
    except Exception:
        return False


def start_comfyui():
    """Launch ComfyUI in the background and wait until it's ready."""
    print("Starting ComfyUI...")
    subprocess.Popen(
        [COMFYUI_PYTHON, "main.py", "--listen", "127.0.0.1"],
        cwd=COMFYUI_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):  # wait up to 60 seconds
        time.sleep(1)
        if comfyui_available():
            print("ComfyUI is ready")
            return True
    print("ComfyUI did not start in time — skipping reference image generation")
    return False


def _generate_image_geminiproxy(prompt, output_path):
    """Generate an image via GeminiProxy CDP. Returns True on success."""
    import websocket as _ws

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
            return False

        rect_val = cdp_eval(
            ws,
            f"""(function() {{
            var imgs = document.querySelectorAll({json.dumps(img_selector)});
            var img = null;
            for (var i = imgs.length - 1; i >= 0; i--) {{
                if ((imgs[i].currentSrc || imgs[i].src || '') === {json.dumps(img_src)}) {{ img = imgs[i]; break; }}
            }}
            if (!img) img = imgs[imgs.length - 1];
            img.scrollIntoView({{block:'center'}});
            var r = img.getBoundingClientRect();
            return JSON.stringify({{x: r.x, y: r.y, width: r.width, height: r.height}});
        }})()""",
        )

        if rect_val:
            rect = json.loads(rect_val)
            capture_js = f"""(async function() {{
                var imgs = document.querySelectorAll({json.dumps(img_selector)});
                var img = null;
                for (var i = imgs.length - 1; i >= 0; i--) {{
                    if ((imgs[i].currentSrc || imgs[i].src || '') === {json.dumps(img_src)}) {{ img = imgs[i]; break; }}
                }}
                if (!img) return null;
                var c = document.createElement('canvas');
                c.width = img.naturalWidth;
                c.height = img.naturalHeight;
                var ctx = c.getContext('2d');
                ctx.drawImage(img, 0, 0);
                return c.toDataURL('image/png');
            }})()"""
            data_url = cdp_eval(ws, capture_js)

            if data_url and data_url.startswith("data:image"):
                b64_data = data_url.split(",", 1)[1]
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                ws.close()
                return True

        ws.close()
        return False
    except Exception as e:
        print(f"  GeminiProxy error: {e}")
        return False


def generate_reference_images(
    character_descriptions, output_dir, image_style="Stick Figure", image_model=None
):
    """Generate reference images for each character using the configured image provider."""
    if image_model is None:
        image_model = IMAGE_MODEL

    style_desc = STYLE_DESCRIPTIONS.get(image_style, STYLE_DESCRIPTIONS["Stick Figure"])

    for char_name, description in character_descriptions.items():
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", char_name).lower()

        if os.path.exists(os.path.join(output_dir, f"ref_{safe_name}.png")):
            print(f"ref_{safe_name}.png already exists — skipping")
            continue

        print(f"Generating {char_name} via {image_model}...")
        prompt = f"{style_desc}, {description}"
        output_path = os.path.join(output_dir, f"ref_{safe_name}.png")

        if image_model == "geminiproxy":
            ok = _generate_image_geminiproxy(prompt, output_path)
            if ok:
                input_dir = "/home/henry/comfy/ComfyUI/input"
                dst = os.path.join(input_dir, f"ref_{safe_name}.png")
                if os.path.exists(output_path):
                    shutil.copy2(output_path, dst)
                    print(f"  Saved: {dst}")
            else:
                print(f"  GeminiProxy failed for {char_name}")
        else:
            if not comfyui_available():
                if not start_comfyui():
                    return

            input_dir = "/home/henry/comfy/ComfyUI/input"
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
                        "seed": 12345,
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

            try:
                resp = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
                data = resp.json()

                if "error" in data:
                    print(f"  Error: {data['error']}")
                    continue

                prompt_id = data["prompt_id"]
                print(f"  Queued: {prompt_id}")

                for attempt in range(60):
                    time.sleep(3)
                    history = requests.get(f"{COMFYUI_URL}/history/{prompt_id}").json()

                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        for node_out in outputs.values():
                            for img in node_out.get("images", []):
                                src = os.path.join(
                                    "/home/henry/comfy/ComfyUI/output", img["filename"]
                                )
                                dst = os.path.join(input_dir, f"ref_{safe_name}.png")
                                dst_out = os.path.join(
                                    output_dir, f"ref_{safe_name}.png"
                                )

                                if os.path.exists(src):
                                    shutil.copy2(src, dst)
                                    shutil.copy2(src, dst_out)
                                    print(f"  Saved: {dst}")
                        break
                else:
                    print(f"  Timeout waiting for {char_name}")
            except Exception as e:
                print(f"  Error: {e}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python prepare.py <narration_file>")
        print("Example: python prepare.py narration.txt")
        sys.exit(1)

    narration_file = sys.argv[1]

    if not os.path.exists(narration_file):
        print(f"Error: File '{narration_file}' not found")
        sys.exit(1)

    # Read narration file
    with open(narration_file, "r") as f:
        narration_text = f.read()

    # Split into lines
    narration_lines = [
        line.strip() for line in narration_text.split("\n") if line.strip()
    ]

    # If the whole story is on one line, split on sentence boundaries and rewrite the file
    if len(narration_lines) == 1 and len(narration_lines[0]) > 200:
        narration_lines = [
            s.strip()
            for s in re.split(r"(?<=[.!?]) +", narration_lines[0])
            if s.strip()
        ]
        with open(narration_file, "w") as f:
            f.write("\n".join(narration_lines) + "\n")
        narration_text = "\n".join(narration_lines)
        print(f"Reformatted narration: {len(narration_lines)} sentences")

    # Remove header if present
    if "=" in narration_lines[0] or "NARRATION" in narration_lines[0].upper():
        narration_lines = narration_lines[2:]  # Skip header and separator

    print(f"STORY PREPARATION PIPELINE")
    print(f"Input: {narration_file}")
    print(f"Lines: {len(narration_lines)}")

    # Determine output directory (same as narration file)
    output_dir = os.path.dirname(os.path.abspath(narration_file))

    # Load project config from the output directory
    project_config_path = os.path.join(output_dir, "project.json")
    project_config = {}
    if os.path.exists(project_config_path):
        with open(project_config_path, "r") as f:
            project_config = json.load(f)
    ai_helper = project_config.get("ai_helper", "opencode")
    image_style = project_config.get("image_style", "Stick Figure")
    image_model = project_config.get("image_model", IMAGE_MODEL)

    cref_path = os.path.join(output_dir, "CREF.txt")
    prompts_path = os.path.join(output_dir, "prompts.txt")

    cref_narration_words = {}

    # Step 1: Extract characters and generate CREF
    if os.path.exists(cref_path):
        print(f"CREF.txt already exists — skipping")
        character_descriptions, cref_narration_words = read_cref_file(cref_path)
        if not character_descriptions:
            characters = extract_characters_from_narration(narration_text)
            character_descriptions = {c: c for c in characters}
        else:
            print(f"Loaded CREF characters: {', '.join(character_descriptions.keys())}")
    else:
        print(f"Extracting characters via {ai_helper}...")
        character_descriptions = _extract_and_describe_characters_with_ai(
            narration_text, ai_helper
        )
        if not character_descriptions:
            print("  AI extraction failed — falling back to regex")
            characters = extract_characters_from_narration(narration_text)
            character_descriptions = {
                c: f"{c}, a character with distinctive features" for c in characters
            }
        else:
            print(f"Characters: {', '.join(character_descriptions.keys())}")
        character_descriptions = generate_cref_file(
            character_descriptions, output_dir, narration_text, ai_helper
        )
        # Re-read narration words after writing CREF
        _, cref_narration_words = read_cref_file(cref_path)

    # Step 2: Generate prompts
    if os.path.exists(prompts_path):
        print(f"prompts.txt already exists — skipping")
    else:
        num_prompts = generate_prompts_file(
            narration_lines,
            character_descriptions,
            output_dir,
            image_style,
            cref_narration_words,
            ai_helper,
        )
        print(f"Generated {num_prompts} prompts")

    # Step 3: Generate reference images
    generate_reference_images(
        character_descriptions, output_dir, image_style, image_model
    )

    print(f"Preparation complete: {output_dir}")


if __name__ == "__main__":
    main()
