# Mdict Studio Pro

**English** | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [العربية](README.ar.md)

**A modern, cross-platform desktop toolkit for building, converting, and inspecting MDict dictionary files.**

Mdict Studio Pro streamlines the full MDict workflow — packing and unpacking `.mdx`/`.mdd` files, converting raw dictionary data into MDict source text, managing SQLite-backed lookups, and inspecting compiled dictionaries — behind a single, self-contained GUI. It's built for linguists, dictionary hobbyists, and developers who work with structured lexical data.

![Converters tab](docs/screenshots/converters-tab.png)

---

## Table of contents

- [What's new in V2.0](#whats-new-in-v20)
- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Writing custom plugins](#writing-custom-plugins)
- [Sample output](#sample-output)
- [Contributing](#contributing)
- [License & author](#license--author)

---

## What's new in V2.0

V2.0's headline feature is the **Converter Plugin System** — a modular execution engine that replaces hard-coded, single-format parsing with dynamically loaded Python plugins.

Drop a plugin file into the app's plugins folder and Mdict Studio Pro discovers it automatically, builds its input form from the plugin's declared metadata, and runs it in a background thread — no changes to the core application required. This means anyone can write a converter for a dictionary format the app doesn't natively support, without forking the codebase.

## Features

- **Modular converter plugins** — write a Python class that inherits from `BaseConverterPlugin` to parse any source format (Excel, CSV, XML, custom text layouts) into MDict source. The GUI generates its input form from the plugin automatically.
- **Pack / unpack `.mdx` and `.mdd`** — build compiled dictionaries from source text (with optional resource folders for `.mdd`), or extract existing dictionaries back to source.
- **Advanced typographic control** — plugins can emit semantic HTML, including `<ruby>` markup for Bopomofo/Pinyin annotation, structured `<ol>` definition lists, and CSS-driven layout.
- **Robust CJK encoding support** — reliable handling of UTF-8, UTF-16LE, Big5, GBK, and GB18030 source files.
- **SQLite database integration** — convert between raw text/MDX sources and SQLite databases for fast programmatic queries.
- **MDX inspection tools** — extract embedded metadata and `.style` (CSS) sheets from a compiled `.mdx` file, or run test queries against a dictionary directly from the GUI.
- **Morphology support** — integrates external inflection/wordform data (`addflex.py`, `wordforms.txt`) for building morphology-aware dictionaries.
- **Cross-platform** — runs on macOS, Windows, and Linux.

## Screenshots

| Pack (Build) | Converters (Plugins) | Tools |
|---|---|---|
| ![Pack tab](docs/screenshots/pack-tab.png) | ![Converters tab with CC-CEDICT plugin selected](docs/screenshots/converters-tab-cedict.png) | ![Tools tab](docs/screenshots/tools-tab.png) |

## Installation

**Requirements:**
- Python 3.8+
- [mdict-utils](https://github.com/liuyug/mdict-utils) (provides the `mdict` command-line tool that Pack/Unpack/Database operations call under the hood)

**1. Clone the repository**
```bash
git clone https://github.com/shawkynasr/MdictStudioPro.git
cd MdictStudioPro
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the application**
```bash
python MdictStudio.py
```

> **macOS packaging:** the app can be built into a native `.app`/`.dmg` with PyInstaller. See [`docs/BUILD.md`](docs/BUILD.md) for the packaging steps, or grab a prebuilt release from the [Releases page](https://github.com/shawkynasr/MdictStudioPro/releases).

## Usage

The app is organized into six tabs, each covering one stage of the MDict workflow:

| Tab | Purpose |
|---|---|
| **Pack (Build)** | Compile source text (and optional resources) into `.mdx`/`.mdd`. |
| **Unpack (Extract)** | Decompile an existing `.mdx`/`.mdd` back to source. |
| **Converters (Plugins)** | Run a converter plugin to turn raw data into MDict source. |
| **Database (SQLite)** | Convert between text/MDX sources and SQLite. |
| **Morphology** | Build inflection/wordform data for morphology-aware lookups. |
| **Tools** | Inspect MDX metadata/stylesheets, or run test queries. |

## Writing custom plugins

Creating a new dictionary converter takes one file. Create a `.py` file in the plugins folder and subclass `BaseConverterPlugin`:

```python
from base_plugin import BaseConverterPlugin

class MyCustomDictPlugin(BaseConverterPlugin):
    id = "my_custom_dict_v1"                 # unique internal identifier
    name = "My Custom Dictionary"             # shown in the Converters dropdown
    description = "Parses my specific dictionary format into MDict HTML."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        # 1. Add your parsing logic here
        # 2. Report progress: progress_callback(50)
        # 3. Log status:      log_callback("Processing entries...")

        return "Successfully generated MDict source!"
```

Mdict Studio Pro detects the plugin on next launch (or via **Refresh Plugins** in the Converters tab) and builds the input form — file picker, encoding selector, and any custom options — automatically, based entirely on what your class declares.

**Where to put it:**
- Running from source: drop it in the `plugins/` folder next to `MdictStudio.py`.
- Running the packaged app: use `~/Documents/Mdict Studio Pro/plugins` (created automatically on first launch — click **Open Plugins Folder** in the Converters tab to jump straight there).

`id` must be unique across all installed plugins; `name` is just the display label and can be descriptive (including non-Latin scripts — see the sample plugins below).

> **Licensing note for plugin authors:** since Mdict Studio Pro is distributed under AGPL-3.0 (see below), plugins that are loaded into and distributed alongside the application are expected to be compatible with that license. If you're building a private/internal plugin for personal use, this doesn't affect you.

## Sample output

A few dictionaries built with community/example converter plugins, showing the typographic detail the HTML pipeline supports — tone-marked Pinyin, colored part-of-speech tags, and structured cross-references:

<table>
<tr>
<td><img src="docs/screenshots/sample-cc-cedict.png" alt="CC-CEDICT converter output for 和"></td>
<td><img src="docs/screenshots/sample-idiom.png" alt="Idiom dictionary output for 入木三分"></td>
</tr>
</table>

## Contributing

Contributions, issues, and feature requests are welcome — check the [issues page](https://github.com/shawkynasr/MdictStudioPro/issues) to get started.

If you write a converter plugin for a well-known dictionary format, consider opening a pull request to have it included as a default/example plugin.

## License & author

- **Author:** Shawky Nasr
- **Contact:** shawkynasr@126.com
- **License:** [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE)

This project uses [PyQt6](https://www.riverbankcomputing.com/software/pyqt/), which is dual-licensed under GPL v3 and a commercial license. Mdict Studio Pro is distributed under AGPL-3.0 accordingly.
