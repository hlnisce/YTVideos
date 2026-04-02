#!/usr/bin/env python3
"""
setconfig.py - GUI dialog to edit project.json configuration
Shows text fields and dropdowns for each configuration item

Usage: python setconfig.py
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PARENT_DIR, "project.json")

# Available options for dropdowns
VOICE_OPTIONS = [
    "en-US-AnaNeural",  # Young female (child-friendly)
    "en-US-JennyNeural",  # Female
    "en-US-AriaNeural",  # Female, expressive
    "en-US-GuyNeural",  # Male
    "en-US-DavisNeural",  # Male, casual
    "en-US-TonyNeural",  # Male, warm
]

RATE_OPTIONS = [
    "-50%",
    "-40%",
    "-30%",
    "-20%",
    "-10%",
    "+0%",
    "+10%",
    "+20%",
    "+30%",
    "+40%",
    "+50%",
]

IMAGE_MODELS = [
    "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
    "RealVisXL_V5.0_Lightning_fp16.safetensors",
    "sd_xl_base_1.0.safetensors",
]

VIDEO_MODELS = [
    "wan2.1_t2v_14B_fp8_e4m3fn.safetensors",
    "wan2.1_t2v_1.3B_fp16.safetensors",
]

STORY_TYPES = [
    "children_story",
    "fairy_tale",
    "adventure",
    "educational",
    "fantasy",
    "comedy",
]

IMAGE_STYLES = [
    "cartoon",
    "anime",
    "realistic",
    "stick_figure",
    "watercolor",
    "pixel_art",
    "3d_render",
    "storybook",
]

VIDEO_QUALITY = ["high", "medium", "low"]

RATE_OPTIONS = [
    "-50%",
    "-40%",
    "-30%",
    "-20%",
    "-10%",
    "+0%",
    "+10%",
    "+20%",
    "+30%",
    "+40%",
    "+50%",
]

IMAGE_MODELS = [
    "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
    "RealVisXL_V5.0_Lightning_fp16.safetensors",
    "sd_xl_base_1.0.safetensors",
]

VIDEO_MODELS = [
    "wan2.1_t2v_14B_fp8_e4m3fn.safetensors",
    "wan2.1_t2v_1.3B_fp16.safetensors",
]


def load_config():
    """Load configuration from project.json."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save configuration to project.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class ConfigDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Project Configuration")
        self.root.geometry("500x400")
        self.root.resizable(True, True)

        # Load current config
        self.config = load_config()
        self.entries = {}

        # Create main frame with scrollbar
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Title
        row = 0
        ttk.Label(main_frame, text="Title:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["title"] = ttk.Entry(main_frame, width=40)
        self.entries["title"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["title"].insert(0, self.config.get("title", ""))

        # Image Model
        row += 1
        ttk.Label(main_frame, text="Image Model:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["image_model"] = ttk.Combobox(
            main_frame, values=IMAGE_MODELS, state="readonly", width=37
        )
        self.entries["image_model"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["image_model"].set(self.config.get("image_model", IMAGE_MODELS[0]))

        # Video Model
        row += 1
        ttk.Label(main_frame, text="Video Model:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["video_model"] = ttk.Combobox(
            main_frame, values=VIDEO_MODELS, state="readonly", width=37
        )
        self.entries["video_model"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["video_model"].set(self.config.get("video_model", VIDEO_MODELS[0]))

        # Voice Model
        row += 1
        ttk.Label(main_frame, text="Voice Model:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["voice_model"] = ttk.Combobox(
            main_frame, values=VOICE_OPTIONS, state="readonly", width=37
        )
        self.entries["voice_model"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["voice_model"].set(
            self.config.get("voice_model", VOICE_OPTIONS[0])
        )

        # Voice Rate
        row += 1
        ttk.Label(main_frame, text="Voice Rate:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["voice_rate"] = ttk.Combobox(
            main_frame, values=RATE_OPTIONS, state="readonly", width=37
        )
        self.entries["voice_rate"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["voice_rate"].set(self.config.get("voice_rate", "-20%"))

        # Video Resolution
        row += 1
        ttk.Label(
            main_frame, text="Video Resolution:", font=("Arial", 10, "bold")
        ).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        res_frame = ttk.Frame(main_frame)
        res_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)

        self.entries["video_width"] = ttk.Entry(res_frame, width=10)
        self.entries["video_width"].pack(side=tk.LEFT, padx=2)
        self.entries["video_width"].insert(0, str(self.config.get("video_width", 832)))

        ttk.Label(res_frame, text="x").pack(side=tk.LEFT, padx=2)

        self.entries["video_height"] = ttk.Entry(res_frame, width=10)
        self.entries["video_height"].pack(side=tk.LEFT, padx=2)
        self.entries["video_height"].insert(
            0, str(self.config.get("video_height", 480))
        )

        # Video FPS
        row += 1
        ttk.Label(main_frame, text="Video FPS:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["video_fps"] = ttk.Entry(main_frame, width=40)
        self.entries["video_fps"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["video_fps"].insert(0, str(self.config.get("video_fps", 8)))

        # Video Length
        row += 1
        ttk.Label(main_frame, text="Video Length:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.entries["video_length"] = ttk.Entry(main_frame, width=40)
        self.entries["video_length"].grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        self.entries["video_length"].insert(0, str(self.config.get("video_length", 17)))

        # Buttons
        row += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(button_frame, text="Cancel", command=self.root.quit).pack(
            side=tk.LEFT, padx=10
        )

    def save(self):
        """Save configuration and close dialog."""
        try:
            config = {
                "title": self.entries["title"].get(),
                "image_model": self.entries["image_model"].get(),
                "video_model": self.entries["video_model"].get(),
                "voice_model": self.entries["voice_model"].get(),
                "voice_rate": self.entries["voice_rate"].get(),
                "video_width": int(self.entries["video_width"].get()),
                "video_height": int(self.entries["video_height"].get()),
                "video_fps": int(self.entries["video_fps"].get()),
                "video_length": int(self.entries["video_length"].get()),
                "created": self.config.get("created", "2026-03-31"),
            }

            save_config(config)
            messagebox.showinfo("Success", "Configuration saved successfully!")
            self.root.quit()

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value: {e}")


def main():
    root = tk.Tk()
    app = ConfigDialog(root)
    root.mainloop()


if __name__ == "__main__":
    main()
