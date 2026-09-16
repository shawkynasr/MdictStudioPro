import sys
import os
import shutil
import openpyxl
import subprocess
import time
import inspect
import importlib.util
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QLineEdit, 
                             QPushButton, QTextEdit, QFileDialog, QCheckBox, 
                             QComboBox, QGroupBox, QFormLayout, QMessageBox, 
                             QProgressBar, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction

from base_plugin import BaseConverterPlugin

# Custom MDX writer for the "MdxBuilder"-compatible sort option.
try:
    from mdict_utils.writer import MDictWriter as MDictUtilsWriter, _OffsetTableEntry, pack_mdx_txt
    import locale, re, string, functools
    
    HAVE_CUSTOM_WRITER = True

    class MDictWriterCustomSort(MDictUtilsWriter):
        def __init__(self, *args, sort_style="mdict-utils", **kwargs):
            self._sort_style = sort_style
            super().__init__(*args, **kwargs)

        def _fold_case(self, word):
            if self._sort_style == "mdxbuilder":
                return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in word)
            return word.lower()

        def _build_offset_table(self, items):
            pattern = '[%s ]+' % string.punctuation
            regex_strip = re.compile(pattern)

            def mdict_cmp(item1, item2):
                key1 = self._fold_case(item1['key'])
                key2 = self._fold_case(item2['key'])
                if not self._is_mdd:
                    key1 = regex_strip.sub('', key1)
                    key2 = regex_strip.sub('', key2)
                key1 = locale.strxfrm(key1)
                key2 = locale.strxfrm(key2)
                if key1 > key2: return 1
                elif key1 < key2: return -1
                if len(key1) > len(key2): return -1
                elif len(key1) < len(key2): return 1
                key1 = key1.rstrip(string.punctuation)
                key2 = key2.rstrip(string.punctuation)
                if key1 > key2: return -1
                elif key1 < key2: return 1
                return 0

            items.sort(key=functools.cmp_to_key(mdict_cmp))

            self._offset_table = []
            offset = 0
            for record in items:
                key = record['key']
                key_enc = key.encode(self._python_encoding)
                key_null = (key + "\0").encode(self._python_encoding)
                key_len = len(key_enc) // self._encoding_length
                self._offset_table.append(_OffsetTableEntry(
                    key0=record['key'], key=key_enc, key_null=key_null, key_len=key_len,
                    record_null=record['path'], record_size=record['size'],
                    record_pos=record['pos'], offset=offset,
                    encoding=self._python_encoding, is_mdd=self._is_mdd,
                ))
                offset += record['size']
            self._total_record_len = offset

except ImportError:
    HAVE_CUSTOM_WRITER = False

# ==========================================================
# PLUGIN MANAGER
# ==========================================================
class PluginManager:
    def __init__(self, plugin_dir="plugins"):
        self.plugins = {}
        self.load_errors = []
        
        # 1. Define the User's visible folder: ~/Documents/Mdict Studio Pro
        self.app_folder = os.path.join(Path.home(), "Documents", "Mdict Studio Pro")
        self.plugin_dir = os.path.join(self.app_folder, plugin_dir)
        
        # Create the visible folders if they don't exist
        os.makedirs(self.plugin_dir, exist_ok=True)
        
        # 2. Find the internal bundled folder (sealed inside the .app / .exe)
        if getattr(sys, 'frozen', False):
            internal_base = sys._MEIPASS # PyInstaller's hidden temp folder
        else:
            internal_base = os.path.dirname(os.path.abspath(__file__))
            
        internal_plugin_dir = os.path.join(internal_base, plugin_dir)
        
        # 3. AUTO-EXTRACT: If the user's plugin folder is empty, copy the 6 defaults over!
        if os.path.exists(internal_plugin_dir) and not os.listdir(self.plugin_dir):
            for item in os.listdir(internal_plugin_dir):
                src = os.path.join(internal_plugin_dir, item)
                dst = os.path.join(self.plugin_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            
            # Crucial: Copy base_plugin.py to the Documents folder too, 
            # so the user's future plugins can import it easily!
            for helper_file in ["base_plugin.py", "excel_utils.py"]:
                src = os.path.join(internal_base, helper_file)
                dst = os.path.join(self.app_folder, helper_file)
                if os.path.exists(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)

        # 4. Ensure the user's Documents folder is in sys.path so imports work
        if self.app_folder not in sys.path:
            sys.path.insert(0, self.app_folder)

        self.load_plugins()

    def load_plugins(self):
        # Gracefully handle a missing base_plugin.py (Bug #2)
        try:
            from base_plugin import BaseConverterPlugin
        except ImportError as e:
            self.load_errors.append(("Core System", f"CRITICAL: base_plugin.py is missing. {e}"))
            return

        if not os.path.exists(self.plugin_dir):
            return

        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                filepath = os.path.join(self.plugin_dir, filename)
                module_name = filename[:-3]
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        # Safely skip abstract classes so they don't crash the loader (Bug #6)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseConverterPlugin) and 
                            attr is not BaseConverterPlugin and 
                            not inspect.isabstract(attr)):
                            
                            instance = attr()
                            # Key by 'id' instead of 'name' to prevent silent overwrites (Bug #1)
                            # Safely check for an ID, otherwise fall back to the display name
                            plugin_id = getattr(instance, 'id', None) or instance.name
                            self.plugins[plugin_id] = instance
                            
                except Exception as e:
                    # Catch the error instead of printing it to a hidden console (Bug #4)
                    self.load_errors.append((filename, str(e)))

# ==========================================================
# THREAD WORKERS
# ==========================================================
class PythonPackWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log_msg = pyqtSignal(str)

    def __init__(self, input_txt, output_mdx, sort_style, encoding="utf-8", title="", description=""):
        super().__init__()
        self.input_txt = input_txt
        self.output_mdx = output_mdx
        self.sort_style = sort_style
        self.encoding = encoding
        self.title = title
        self.description = description

    def run(self):
        try:
            self.log_msg.emit(f"Parsing dictionary text file ({self.encoding})...")
            
            # Import the library functions
            import mdict_utils.writer as mu_writer
            
            # 1. Parse the text file into the exact dictionary list the writer expects
            # (This completely replaces parse_txt_to_tuples!)
            dictionary_data = mu_writer.pack_mdx_txt(
                self.input_txt, 
                encoding=self.encoding
            )
            
            self.log_msg.emit(f"Initializing native packing engine ({self.sort_style} sort)...")
            
            # 2. Instantiate our custom writer directly with the parsed data
            writer = MDictWriterCustomSort(
                dictionary_data,
                title=self.title,
                description=self.description,
                sort_style=self.sort_style
            )
            
            self.log_msg.emit(f"Writing binary MDX file to {self.output_mdx}...")
            
            # 3. Write it safely to disk
            with open(self.output_mdx, "wb") as f:
                writer.write(f)
                
            self.finished.emit("MDX Pack Successful!")
        except Exception as e:
            self.error.emit(f"Packing Failed: {str(e)}")

class ShellWorker(QThread):
    """Executes mdict-utils commands and streams output to prevent freezing."""
    log_msg = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            self.log_msg.emit(f"Running: {' '.join(self.command)}")
            # Use Popen to stream stdout/stderr without freezing
            process = subprocess.Popen(
                self.command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True
            )
            
            for line in process.stdout:
                self.log_msg.emit(line.strip())
                
            process.wait()
            if process.returncode == 0:
                self.finished.emit("Process completed successfully.")
            else:
                self.error.emit(f"Process exited with code {process.returncode}")
        except Exception as e:
            self.error.emit(str(e))

class PluginWorker(QThread):
    """Executes dynamic dictionary parsers safely in the background."""
    progress_changed = pyqtSignal(int)
    log_msg = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, plugin: BaseConverterPlugin, infile: str, outfile: str, encoding: str):
        super().__init__()
        self.plugin = plugin
        self.infile = infile
        self.outfile = outfile
        self.encoding = encoding

    def run(self):
        try:
            summary = self.plugin.convert(
                input_file=self.infile,
                output_file=self.outfile,
                encoding=self.encoding,
                progress_callback=self.progress_changed.emit,
                log_callback=self.log_msg.emit
            )
            self.finished.emit(summary)
        except Exception as e:
            self.error.emit(str(e))

# ==========================================================
# MAIN APPLICATION
# ==========================================================
class MdictStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mdict Studio Pro V2 By (Shawky Nasr)")
        self.resize(900, 750)
        
        self.mdict_path = shutil.which("mdict") or "mdict"
        self.python_path = sys.executable
        
        # Keep references to prevent threads from being garbage collected
        self.active_workers = [] 

        self.create_menu_bar()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.init_pack_tab()       # Tab 1
        self.init_unpack_tab()     # Tab 2
        self.init_plugin_tab()     # Tab 3: Converters (Plugins) moved here
        self.init_database_tab()   # Tab 4
        self.init_morphology_tab() # Tab 5
        self.init_tools_tab()      # Tab 6

        self.layout.addWidget(QLabel("Process Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Menlo, Monaco; font-size: 12px; background-color: #1e1e1e; color: #00ff00;")
        self.log_output.setFixedHeight(180)
        self.layout.addWidget(self.log_output)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.layout.addWidget(self.progress)
    # ---> THE ERROR DISPLAY CODE HERE <---
        if hasattr(self, 'plugin_mgr') and self.plugin_mgr.load_errors:
            self.log_output.append("<b><font color='red'>⚠️ Plugin Load Errors Detected:</font></b>")
            for filename, err in self.plugin_mgr.load_errors:
                self.log_output.append(f"<font color='red'> - <b>{filename}</b>: {err}</font>")
            self.log_output.append("<br>")

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("About Mdict Studio Pro", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About Mdict Studio Pro")
        # Enable rich text and clickable links
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        
        msg.setText(
            "<h3>Mdict Studio Pro V2.1</h3>"
            "<p><b>Author:</b> Shawky Nasr &lt;shawkynasr@126.com&gt;</p>"
            "<p><b>GitHub:</b> <a href='https://github.com/shawkynasr/MdictStudioPro'>Official Repository</a></p>"
        )
        msg.exec()

    # ==========================================================
    # 0. PLUGIN TAB (New Modular Converter)
    # ==========================================================
    def init_plugin_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        self.plugin_mgr = PluginManager()

        grp_plugin = QGroupBox("Select Dictionary Converter")
        form_plugin = QFormLayout()
        self.combo_plugins = QComboBox()
        self.combo_plugins.currentIndexChanged.connect(self.on_plugin_selected)
        
        self.lbl_plugin_desc = QLabel()
        self.lbl_plugin_desc.setWordWrap(True)
        self.lbl_plugin_desc.setStyleSheet("color: gray; font-style: italic;")
        
        btn_reload = QPushButton("🔄 Refresh Plugins")
        btn_reload.clicked.connect(self.reload_plugins)
        
        # NEW Open Folder Button
        btn_open_folder = QPushButton("📂 Open Plugins Folder")
        btn_open_folder.clicked.connect(self.open_plugin_folder)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_reload)
        btn_layout.addWidget(btn_open_folder)
        
        form_plugin.addRow("Plugin:", self.combo_plugins)
        form_plugin.addRow("Description:", self.lbl_plugin_desc)
        form_plugin.addRow("", btn_layout) # <--- Now it adds the layout with BOTH buttons!
        grp_plugin.setLayout(form_plugin)
        layout.addWidget(grp_plugin)

        grp_io = QGroupBox("Input / Output")
        form_io = QFormLayout()
        
        self.plugin_src_line = QLineEdit()
        self.plugin_src_btn = QPushButton("Browse")
        self.plugin_src_btn.clicked.connect(self.browse_plugin_file)
        
        src_layout = QHBoxLayout()
        src_layout.addWidget(self.plugin_src_line)
        src_layout.addWidget(self.plugin_src_btn)
        
        self.plugin_encoding = QComboBox()
        
        form_io.addRow("Source File:", src_layout)
        form_io.addRow("Encoding:", self.plugin_encoding)
        grp_io.setLayout(form_io)
        layout.addWidget(grp_io)

        btn_convert = QPushButton("⚡ Run Converter Plugin")
        btn_convert.setFixedHeight(45)
        btn_convert.clicked.connect(self.run_plugin)
        layout.addWidget(btn_convert)

        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Converters (Plugins)")
        
        self.reload_plugins() # Initialize list

    def reload_plugins(self):
        # Clear old data before reloading
        self.plugin_mgr.plugins.clear()
        self.plugin_mgr.load_errors.clear()
        
        self.plugin_mgr.load_plugins()
        
        self.combo_plugins.clear()
        self.combo_plugins.addItems(list(self.plugin_mgr.plugins.keys()))
        
        if not self.plugin_mgr.plugins:
            # If empty, print the EXACT absolute path it tried to read to the UI
            self.lbl_plugin_desc.setText(f"No plugins found in:\n{self.plugin_mgr.plugin_dir}")

    def open_plugin_folder(self):
        import platform
        import subprocess
        path = self.plugin_mgr.plugin_dir
        
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    def on_plugin_selected(self):
        plugin_name = self.combo_plugins.currentText()
        if plugin_name in self.plugin_mgr.plugins:
            plugin = self.plugin_mgr.plugins[plugin_name]
            self.lbl_plugin_desc.setText(plugin.description)
            self.plugin_encoding.clear()
            self.plugin_encoding.addItems(plugin.default_encodings)

    def browse_plugin_file(self):
        plugin_name = self.combo_plugins.currentText()
        filter_str = "All Files (*.*)"
        if plugin_name in self.plugin_mgr.plugins:
            filter_str = self.plugin_mgr.plugins[plugin_name].file_filter
            
        f, _ = QFileDialog.getOpenFileName(self, "Select Source", "", filter_str)
        if f: self.plugin_src_line.setText(f)

    def run_plugin(self):
        plugin_name = self.combo_plugins.currentText()
        infile = self.plugin_src_line.text()
        
        if not plugin_name or plugin_name not in self.plugin_mgr.plugins:
            return QMessageBox.warning(self, "Error", "No valid plugin selected.")
        if not infile:
            return QMessageBox.warning(self, "Error", "Please select an input file.")

        plugin = self.plugin_mgr.plugins[plugin_name]
        encoding = self.plugin_encoding.currentText()
        outfile = infile + "_mdict_source.txt"

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.log_output.append(f"--- Starting Plugin: {plugin.name} ---")

        worker = PluginWorker(plugin, infile, outfile, encoding)
        worker.progress_changed.connect(self.progress.setValue)
        worker.log_msg.connect(self.log_output.append)
        worker.finished.connect(self.on_success)
        worker.error.connect(self.on_error)
        
        self.active_workers.append(worker)
        
        def cleanup_plugin_worker():
            if worker in self.active_workers:
                self.active_workers.remove(worker)
                
        worker.finished.connect(cleanup_plugin_worker)
        if hasattr(worker, 'error'):
            worker.error.connect(cleanup_plugin_worker)
            
        worker.start()

    # ==========================================================
    # 1. PACKING TAB
    # ==========================================================
    def init_pack_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        grp_src = QGroupBox("1. Source Files")
        form = QFormLayout()
        self.txt_source = self.create_file_selector("Select Source TXT/HTML", "Text Files (*.txt *.html)")
        
        # --------------------------------
        
        self.pack_encoding = QComboBox()
        self.pack_encoding.addItems(["utf-8", "utf-16le", "big5", "gb18030", "gbk"])
        
        self.mdd_source_dir = self.create_dir_selector("Select Resource Folder (for MDD)")
        
        form.addRow("Source Text:", self.txt_source)
        form.addRow("Source Encoding:", self.pack_encoding)
        form.addRow("Resource Dir:", self.mdd_source_dir)
        grp_src.setLayout(form)
        layout.addWidget(grp_src)

        grp_meta = QGroupBox("2. Metadata (Optional)")
        form_meta = QFormLayout()
        self.meta_title = QLineEdit()
        self.meta_desc = self.create_file_selector("Select Description HTML", "HTML (*.html *.txt)")
        form_meta.addRow("Title:", self.meta_title)
        form_meta.addRow("Description File:", self.meta_desc)
        grp_meta.setLayout(form_meta)
        layout.addWidget(grp_meta)

        grp_out = QGroupBox("3. Output")
        layout_out = QHBoxLayout()
        self.pack_out_path = QLineEdit()
        self.pack_out_path.setPlaceholderText("Output filename will be auto-generated if empty")
        layout_out.addWidget(self.pack_out_path)
        grp_out.setLayout(layout_out)
        layout.addWidget(grp_out)
        # ==========================================
        # 4. Sorting Standard Block (New code)
        # ==========================================
        grp_sort = QGroupBox("4. Sorting Standard")
        sort_layout = QHBoxLayout()
        
        self.radio_sort_mdictutils = QRadioButton("mdict-utils / Unicode (BlueDict, GoldenDict)")
        self.radio_sort_mdxbuilder = QRadioButton("MdxBuilder (MDict, DictTango)")
        # Recommendation: Set MdxBuilder as default since it fixes the core bug!
        self.radio_sort_mdxbuilder.setChecked(True)
        
        self.sort_style_group = QButtonGroup(self)
        # CRITICAL FIX: Add IDs (2 for mdictutils, 1 for mdxbuilder) to match our Worker logic
        self.sort_style_group.addButton(self.radio_sort_mdictutils, 2) # ID 2
        self.sort_style_group.addButton(self.radio_sort_mdxbuilder, 1) # ID 1
        
        if not HAVE_CUSTOM_WRITER:
            self.radio_sort_mdxbuilder.setEnabled(False)
            self.radio_sort_mdxbuilder.setToolTip("mdict-utils not importable as a library - install via pip to enable")
            self.radio_sort_mdictutils.setChecked(True) # Force fallback to Unicode if disabled
            
        sort_layout.addWidget(self.radio_sort_mdictutils)
        sort_layout.addWidget(self.radio_sort_mdxbuilder)
        grp_sort.setLayout(sort_layout)
        
        layout.addWidget(grp_sort)
        
        btn_layout = QHBoxLayout()
        btn_pack_mdx = QPushButton("🔨 Build MDX")
        btn_pack_mdx.setFixedHeight(40)
        btn_pack_mdx.clicked.connect(self.run_pack_mdx)
        
        btn_pack_mdd = QPushButton("📦 Build MDD")
        btn_pack_mdd.setFixedHeight(40)
        btn_pack_mdd.clicked.connect(self.run_pack_mdd)

        btn_layout.addWidget(btn_pack_mdx)
        btn_layout.addWidget(btn_pack_mdd)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Pack (Build)")

    # ==========================================================
    # 2. UNPACK TAB
    # ==========================================================
    def init_unpack_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        grp_in = QGroupBox("Input Dictionary")
        form = QFormLayout()
        self.unpack_src = self.create_file_selector("Select MDX/MDD", "Mdict Files (*.mdx *.mdd)")
        
        self.unpack_encoding = QComboBox()
        self.unpack_encoding.addItems(["Auto-Detect", "utf-8", "utf-16le", "big5", "gb18030", "gbk"])
        
        form.addRow("File:", self.unpack_src)
        form.addRow("Force Encoding:", self.unpack_encoding)
        grp_in.setLayout(form)
        layout.addWidget(grp_in)

        btn_unpack = QPushButton("🔓 Extract to Folder")
        btn_unpack.setFixedHeight(40)
        btn_unpack.clicked.connect(self.run_unpack)
        layout.addWidget(btn_unpack)

        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Unpack (Extract)")

    # ==========================================================
    # OTHER TABS (Simplified for brevity, matches original)
    # ==========================================================
    def init_database_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        lbl = QLabel("Convert between Text/MDX and fast SQLite Databases (useful for queries).")
        layout.addWidget(lbl)
        
        grp_1 = QGroupBox("TXT <-> DB")
        l1 = QHBoxLayout()
        self.db_txt_src = self.create_file_selector("Source", "Files (*.txt *.db)")
        btn_txt2db = QPushButton("TXT -> DB")
        btn_txt2db.clicked.connect(lambda: self.run_shell_cmd([self.mdict_path, "--txt-db", self.db_txt_src.text()]))
        l1.addWidget(self.db_txt_src)
        l1.addWidget(btn_txt2db)
        grp_1.setLayout(l1)
        layout.addWidget(grp_1)

        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Database (SQLite)")

    def init_morphology_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        grp_scripts = QGroupBox("External Scripts Setup")
        form = QFormLayout()
        self.path_addflex = self.create_file_selector("Locate 'addflex.py'", "Python (*.py)")
        self.path_wordforms = self.create_file_selector("Locate 'wordforms.txt'", "Text (*.txt)")
        form.addRow("addflex.py:", self.path_addflex)
        form.addRow("wordforms:", self.path_wordforms)
        grp_scripts.setLayout(form)
        layout.addWidget(grp_scripts)
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Morphology")

    def init_tools_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # --- NEW: Inspect MDX Feature ---
        grp_info = QGroupBox("Inspect MDX (Get Meta Info and Styles)")
        l_info = QHBoxLayout()
        self.info_src = self.create_file_selector("Select MDX", "MDX (*.mdx)")
        btn_info = QPushButton("Get Meta Info")
        
        # Connect the button to mdict-utils with the '-m' flag
        btn_info.clicked.connect(
            lambda: self.run_shell_cmd([self.mdict_path, "-m", self.info_src.text()])
        )
        
        # --- NEW EXPORT BUTTON ---
        btn_export_style = QPushButton("Export .style")
        btn_export_style.clicked.connect(self.run_export_style)
        
        l_info.addWidget(self.info_src)
        l_info.addWidget(btn_info)
        l_info.addWidget(btn_export_style) # Add to layout
        grp_info.setLayout(l_info)
        layout.addWidget(grp_info)
        # --------------------------------

        # --- Existing Query Feature ---
        grp_query = QGroupBox("Query (Test Dictionary)")
        form = QFormLayout()
        self.query_key = QLineEdit()
        self.query_file = self.create_file_selector("Target MDX", "MDX (*.mdx)")
        btn_query = QPushButton("Search Key")
        def execute_query():
            word = self.query_key.text().strip()
            dict_file = self.query_file.text().strip()
            if not word or not dict_file:
                return QMessageBox.warning(self, "Missing Info", "Please provide both a search word and a dictionary file.")
            self.run_shell_cmd([self.mdict_path, "-q", word, dict_file])

        btn_query.clicked.connect(execute_query)
        form.addRow("Search Word:", self.query_key)
        form.addRow("Dictionary:", self.query_file)
        form.addRow("", btn_query)
        grp_query.setLayout(form)
        layout.addWidget(grp_query)
        # ------------------------------

        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Tools")

    # --- UI Helpers ---
    def create_file_selector(self, placeholder, filter_str):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_file(line, filter_str))
        layout.addWidget(line)
        layout.addWidget(btn)
        container.text = line.text
        container.setText = line.setText
        return container

    def create_dir_selector(self, placeholder):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        btn = QPushButton("Folder")
        btn.clicked.connect(lambda: self.browse_dir(line))
        layout.addWidget(line)
        layout.addWidget(btn)
        
        # Make sure 'text' is entirely lowercase here!
        container.text = line.text
        container.setText = line.setText
        
        return container

    def browse_file(self, line_edit, filter_str):
        f, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if f: line_edit.setText(f)

    def browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d: line_edit.setText(d)

    # --- Shell Execution ---
    def run_shell_cmd(self, cmd):
        if not cmd[-1]: return
        self.progress.setRange(0, 0) # Indeterminate loading
        
        worker = ShellWorker(cmd)
        worker.log_msg.connect(self.log_output.append)
        worker.finished.connect(self.on_success)
        worker.error.connect(self.on_error)
        
        self.active_workers.append(worker)
        
        def cleanup_shell_worker():
            if worker in self.active_workers:
                self.active_workers.remove(worker)
                
        worker.finished.connect(cleanup_shell_worker)
        if hasattr(worker, 'error'):
            worker.error.connect(cleanup_shell_worker)
            
        worker.start()

    def on_success(self, log):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.log_output.append(log)
        self.log_output.append("--- SUCCESS ---")

    def on_error(self, err):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.log_output.append(f"ERROR: {err}")
        QMessageBox.critical(self, "Error", err)

    # --- Actions ---
    def run_pack_mdx(self):
        # 1. Validate Input Source
        src = self.txt_source.text().strip()
        if not src: 
            return QMessageBox.warning(self, "Missing", "Source TXT required")
            
        # 2. Validate Output Destination
        raw_dst = self.pack_out_path.text().strip()
        
        if not raw_dst:
            dst = os.path.splitext(src)[0] + ".mdx"
        elif os.path.isdir(raw_dst):
            base_name = os.path.splitext(os.path.basename(src))[0]
            dst = os.path.join(raw_dst, base_name + ".mdx")
        elif not os.path.isabs(raw_dst):
            dst = os.path.join(os.path.dirname(src), raw_dst)
        else:
            dst = raw_dst
            
        if not dst.lower().endswith(".mdx"):
            dst += ".mdx"
            
        # 3. Read UI Options
        selected_style = "mdxbuilder" if self.sort_style_group.checkedId() == 1 else "mdict-utils"
        encoding = self.pack_encoding.currentText() if hasattr(self, 'pack_encoding') else 'utf-8'
        title = self.meta_title.text().strip() if hasattr(self, 'meta_title') else ''
        
        # Safely read the description path
        desc_path = self.meta_desc.text().strip() if hasattr(self, 'meta_desc') else ''

        # 4. Cleanup Function for Threads
        def _cleanup_and_finish():
            if hasattr(self, 'active_workers') and self.pack_worker in self.active_workers:
                self.active_workers.remove(self.pack_worker)

        # 5. Branching Logic
        if HAVE_CUSTOM_WRITER:
            self.log_output.append(f"Starting native Python MDX packing ({selected_style} sort)...")
            if hasattr(self, 'progress'):
                self.progress.setRange(0, 0) # Indeterminate/Processing state
            
            # Read HTML content for the native writer
            desc_content = ""
            if desc_path and os.path.exists(desc_path):
                with open(desc_path, "r", encoding=encoding) as f:
                    desc_content = f.read()
                    
            self.pack_worker = PythonPackWorker(
                input_txt=src,
                output_mdx=dst,
                sort_style=selected_style,
                encoding=encoding,
                title=title,
                description=desc_content
            )
            
            self.pack_worker.log_msg.connect(self.log_output.append)
            self.pack_worker.finished.connect(self.on_pack_success)
            self.pack_worker.error.connect(self.on_pack_error)
            
            # Attach cleanup
            self.pack_worker.finished.connect(_cleanup_and_finish)
            self.pack_worker.error.connect(_cleanup_and_finish)
            
            if hasattr(self, 'active_workers'):
                self.active_workers.append(self.pack_worker)
                
            self.pack_worker.start()
            
        else:
            self.log_output.append("mdict-utils native import failed. Falling back to Shell mode...")
            if hasattr(self, 'progress'):
                self.progress.setRange(0, 0)
            
            # Pass the raw path for the CLI
            cmd = ["mdict", "-a", src, dst, "--encoding", encoding]
            if title:
                cmd.extend(["--title", title])
            if desc_path:
                cmd.extend(["--description", desc_path])
                
            self.pack_worker = ShellWorker(cmd)
            self.pack_worker.log_msg.connect(self.log_output.append)
            self.pack_worker.finished.connect(self.on_pack_success)
            self.pack_worker.error.connect(self.on_pack_error)
            
            # Attach cleanup
            self.pack_worker.finished.connect(_cleanup_and_finish)
            self.pack_worker.error.connect(_cleanup_and_finish)
            
            if hasattr(self, 'active_workers'):
                self.active_workers.append(self.pack_worker)
                
            self.pack_worker.start()
            
    def on_pack_success(self, message):
        # Reset the range to normal and fill the bar to 100%
        if hasattr(self, 'progress'):
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            
        QMessageBox.information(self, "Success", message)

    def on_pack_error(self, err_msg):
        # Reset the range to normal and empty the bar to 0%
        if hasattr(self, 'progress'):
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            
        QMessageBox.critical(self, "Pack Failed", err_msg)

    def run_pack_mdd(self):
        src = self.mdd_source_dir.text()
        if not src: return QMessageBox.warning(self, "Missing", "Resource Dir required")
        self.run_shell_cmd([self.mdict_path, "-a", src, src + ".mdd"])

    def run_unpack(self):
        src = self.unpack_src.text()
        if not src: return
        cmd = [self.mdict_path, "-x", src, "-d", src + "_unpacked"]
        
        enc = self.unpack_encoding.currentText()
        if enc != "Auto-Detect":
            cmd.extend(["--encoding", enc])
            
        self.run_shell_cmd(cmd)
    def run_export_style(self):
        src = self.info_src.text()
        if not src:
            return QMessageBox.warning(self, "Missing", "Please select an MDX file first.")
        
        self.progress.setRange(0, 0)
        self.log_output.append(f"Extracting style file from {src}...")
        
        try:
            # 1. Run the metadata command silently in the background
            result = subprocess.run([self.mdict_path, "-m", src], capture_output=True, text=True)
            output = result.stdout
            
            # 2. Safely extract the block using string splitting
            if 'Stylesheet: "' in output:
                style_part = output.split('Stylesheet: "', 1)[1]
                
                # Find the closing quotation mark at the very end of the block
                if '"' in style_part:
                    raw_escaped_string = '"' + style_part.rsplit('"', 1)[0] + '"'
                else:
                    raw_escaped_string = '"' + style_part + '"'
                
                import ast
                try:
                    # Converts python-escaped \n back into real newlines
                    style_content = ast.literal_eval(raw_escaped_string)
                except Exception:
                    # Fallback in case ast eval fails
                    style_content = raw_escaped_string.strip('"').replace('\\n', '\n').replace('\\t', '\t')
                
                # 3. Clean up the <StyleSheet> wrapper tags
                style_content = style_content.replace("<StyleSheet>\n", "")
                style_content = style_content.replace("</StyleSheet>\n", "")
                style_content = style_content.replace("<StyleSheet>", "")
                style_content = style_content.replace("</StyleSheet>", "")
                
                # Remove leading/trailing blank space, but keep internal blank lines intact
                style_content = style_content.strip()
                
                if not style_content:
                    self.log_output.append("The Stylesheet is empty. Nothing to export.")
                    self.progress.setRange(0, 100)
                    return
                    
                # 4. Save it as "_style.txt" next to the original MDX
                if src.lower().endswith(".mdx"):
                    out_path = src[:-4] + "_style.txt"
                else:
                    out_path = src + "_style.txt"
                    
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(style_content)
                    
                self.log_output.append(f"--- SUCCESS: Exported to {out_path} ---")
                QMessageBox.information(self, "Success", f"Style file successfully extracted to:\n{out_path}")
                
            else:
                self.log_output.append("No Stylesheet was found inside this MDX file.")
                QMessageBox.information(self, "Not Found", "This dictionary does not contain an embedded .style file.")
                
        except Exception as e:
            self.log_output.append(f"Error extracting style: {e}")
            
        finally:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MdictStudio()
    window.show()
    sys.exit(app.exec())