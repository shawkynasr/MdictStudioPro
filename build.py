"""
build.py

Cross-platform PyInstaller build script for Mdict Studio Pro.

Run directly: `python build.py`

Handles the two things that differ per-OS so the CI workflow (and your
local build commands) don't need OS-specific flags:
  - --add-data separator: ':' on macOS/Linux, ';' on Windows (os.pathsep)
  - --icon: .icns on macOS, .ico on Windows, omitted on Linux
    (PyInstaller ignores --icon on Linux entirely - the app icon there
    comes from the .desktop file / icon theme, not the binary itself)
"""

import os
import sys
import shutil

import PyInstaller.__main__

APP_NAME = "Mdict Studio Pro"
ENTRY_SCRIPT = "MdictStudio.py"

sep = os.pathsep  # ':' on darwin/linux, ';' on win32

args = [
    ENTRY_SCRIPT,
    "--name", APP_NAME,
    "--windowed",
    "--noconfirm",
    "--clean",
    
    # --- EXISTING HIDDEN IMPORTS ---
    # openpyxl is only imported dynamically by plugins loaded at runtime,
    # so PyInstaller's static analysis can't see it without this hint.
    "--hidden-import", "openpyxl",
    
    # --- V2.1 NATIVE ENGINE HIDDEN IMPORTS ---
    "--hidden-import", "mdict_utils",
    "--hidden-import", "mdict_utils.writer",
    "--hidden-import", "xxhash",

    # --- ASSETS & PLUGINS ---
    # Bundle default plugins + framework helper files so PluginManager's
    # first-run auto-extract (see MdictStudio.py) has something to copy
    # into ~/Documents/Mdict Studio Pro/plugins.
    "--add-data", f"plugins{sep}plugins",
    "--add-data", f"base_plugin.py{sep}.",
    "--add-data", f"excel_utils.py{sep}.",
]

if sys.platform == "darwin":
    # Updated to point to the assets/ folder
    if os.path.exists("assets/AppIcon.icns"):
        args += ["--icon", "assets/AppIcon.icns"]
    else:
        print("Warning: assets/AppIcon.icns not found. Building without custom Mac icon.")
elif sys.platform == "win32":
    if os.path.exists("assets/icon.ico"):
        args += ["--icon", "assets/icon.ico"]
    else:
        print("Warning: assets/icon.ico not found. Building without custom Windows icon.")
# Linux: no --icon - PyInstaller silently ignores it on this platform anyway.

print(f"Building for platform: {sys.platform}")
print("PyInstaller args:", " ".join(args))

PyInstaller.__main__.run(args)

print("\nBuild complete. Output in dist/")