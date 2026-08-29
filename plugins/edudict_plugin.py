import time
import re
from excel_utils import read_excel_as_dicts
from base_plugin import BaseConverterPlugin

class EduDictRevisedPlugin(BaseConverterPlugin):
    name = "教育部重編國語辭典修訂本 (Excel to MDict)"
    description = "Converts the official dict_revised_2015.xlsx, fully optimized for the advanced jybcb.css grid layout."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def __init__(self):
        self.CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
        self.VARIANT_TYPE = {
            "1": "變", "2": "又音", "3": "語音", "4": "讀音",
            "變": "變", "又音": "又音", "語音": "語音", "讀音": "讀音",
        }
        self.IMG_ALT_MAP = {
            "9868._104_0.gif": "未收錄篆字", "9b46._104_0.gif": "e^x",
            "9a73._104_0.gif": "x^2", "975d._104_0.gif": "a^π",
        }
        self.RE_IMG_GENERIC_GIF = re.compile(r"\b([0-9a-fA-F]{4}\._104_0\.gif)\b")
        self.RE_IMG_ENTITY_PNG = re.compile(r"&([0-9a-fA-F]{4})_\.png;")

    def replace_inline_images(self, text: str) -> str:
        if not text: return ""
        
        # 1. FIX: Deleted the buggy 'for' loop that was causing double-replacements!

        def repl_generic(m):
            fname = m.group(1)
            # This already handles the IMG_ALT_MAP lookup perfectly!
            alt = self.IMG_ALT_MAP.get(fname, fname.split("._")[0])
            return f'<img src="{fname}" class="imgchar" alt="{alt}" />'
            
        def repl_entity_png(m):
            hex4 = m.group(1).lower()
            fname = f"{hex4}_.png"
            return f'<img src="{fname}" class="imgchar" alt="{hex4}" />'
            
        # 2. Process the old GIF and entity markers safely
        text = self.RE_IMG_GENERIC_GIF.sub(repl_generic, text)
        text = self.RE_IMG_ENTITY_PNG.sub(repl_entity_png, text)
        
        # 3. NEW: Process the &filename.jpg markers universally (adding the char/ folder path)
        text = re.sub(
            r'&([\w.-]+\.(?:jpg|jpeg|gif|png));?', 
            r'<img class="pic-inline" src="\1" alt="\1">', 
            text, 
            flags=re.IGNORECASE
        )
        
        return text

    def clean_text(self, s):
        if s is None: return ""
        # 1. FIX: Added _x000D_ removal
        s = str(s).replace("_x000D_", "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(s) >= 2 and ((s.startswith('"') and s.endswith('"')) or (s.startswith("「") and s.endswith("」"))):
            s = s[1:-1].strip()
        s = self.replace_inline_images(s)
        return s

    def safe_int(self, x, default=0):
        try:
            if x == "" or x is None: return default
            return int(str(x).strip())
        except:
            return default

    def build_radical_line(self, row):
        radical = str(row.get("部首字", "") or "").strip()
        total = str(row.get("總筆畫數", "") or "").strip()
        out = str(row.get("部首外筆畫數", "") or "").strip()
        if not radical and not total and not out: return ""
        pieces = []
        if radical: pieces.append(f"{radical}部")
        if out: pieces.append(f"部外 {out} 畫")
        if total: pieces.append(f"總筆畫 {total} 畫")
        return " ".join(pieces)

    def make_bopomo_and_pinyin_block(self, rows):
        rows_sorted = sorted(rows, key=lambda r: (0 if self.safe_int(r.get("多音排序"), 0) > 0 else 1, self.safe_int(r.get("多音排序"), 0)))
        pos_ns = [self.safe_int(r.get("多音排序"), 0) for r in rows_sorted if self.safe_int(r.get("多音排序"), 0) > 0]
        need_enum = len(set(pos_ns)) >= 2

        zhuyin_list, hanyu_list = [], []
        z_seen, p_seen = set(), set()

        for r in rows_sorted:
            n = self.safe_int(r.get("多音排序"), 0)
            z = str(r.get("注音一式", "") or "").strip()
            p = str(r.get("漢語拼音", "") or "").strip()
            zv = str(r.get("變體注音", "") or "").strip()
            pv = str(r.get("變體漢語拼音", "") or "").strip()

            prefix = f"({self.CN_NUM.get(n, str(n))}) " if (need_enum and n > 0) else ""
            
            if z and z not in z_seen:
                zhuyin_list.append(prefix + z)
                z_seen.add(z)
            if p and p not in p_seen:
                hanyu_list.append(prefix + p)
                p_seen.add(p)
            if zv and zv not in z_seen:
                zhuyin_list.append(zv)
                z_seen.add(zv)
            if pv and pv not in p_seen:
                hanyu_list.append(pv)
                p_seen.add(pv)

        # 2. FIX: Removed hardcoded "注音一式：" and "漢語拼音：" since CSS dynamically injects them
        bopomo_line = f'<span class="bopomo">{" ".join(zhuyin_list)}</span>' if zhuyin_list else ""
        hanyu_line = f'<span class="hanyu">{" ".join(hanyu_list)}</span>' if hanyu_list else ""
        return bopomo_line, hanyu_line

    def build_defs_block(self, rows, headword=""):
        rows_sorted = sorted(rows, key=lambda r: (0 if self.safe_int(r.get("多音排序"), 0) > 0 else 1, self.safe_int(r.get("多音排序"), 0)))
        
        parts = []
        for r in rows_sorted:
            defs_raw = self.clean_text(r.get("釋義", ""))
            if not defs_raw: continue
            
            zhuyin = str(r.get("注音一式", "") or "").strip()
            n = self.safe_int(r.get("多音排序"), 0)
            var_type_raw = str(r.get("變體類型 1:變 2:又音 3:語音 4:讀音", "") or "").strip()
            var_type = self.VARIANT_TYPE.get(var_type_raw, var_type_raw)

            header_bits = []
            if len(rows_sorted) > 1 and n > 0:
                header_bits.append(f'({self.CN_NUM.get(n, str(n))})')
            
            if var_type:
                # Uses the red CSS pill tag for variants
                header_bits.append(f'<span class="example">{var_type}</span>')

            pron_header = ""
            if header_bits:
                pron_header = "<div style='font-weight:bold; color:#B45E13; margin-bottom:4px;'>" + " ".join(header_bits) + f" {zhuyin}</div>"

            # 3. FIX: Intelligently parse POS tags [名], [代] and auto-wrap them in CSS .example
            defs_lines = [l.strip() for l in defs_raw.split('\n') if l.strip()]

            defs_html = ""
            current_block_lines = []

            def flush_block():
                nonlocal defs_html, current_block_lines
                if not current_block_lines: return
                
                # Only use <ol> numbers if there are multiple meanings under this POS
                if len(current_block_lines) > 1:
                    defs_html += '<ol style="margin-top:0; padding-left:2em;">'
                    for bl in current_block_lines:
                        defs_html += f'<li>{bl}</li>'
                    defs_html += '</ol>'
                else:
                    defs_html += f'<div style="margin-top:4px; padding-left:0;">{current_block_lines[0]}</div>'
                current_block_lines = []

            for line in defs_lines:
                # Strip Excel's hardcoded numbers (e.g. "1. ", "2. ")
                line = re.sub(r'^\d+\.\s*', '', line).strip()

                # Automatically highlight the headword in the text (like the MOE website)
                if headword:
                    line = line.replace(headword, f'<span style="color:var(--c-red); font-weight:bold;">{headword}</span>')

                # Check for standalone POS tags like "[名]"
                pos_match = re.match(r'^\[(.*?)\]$', line)
                if pos_match:
                    flush_block() # output any pending definitions first
                    pos_tag = pos_match.group(1)
                    # Use the CSS .example pill and create visual space
                    defs_html += f'<div style="margin-top:12px; margin-bottom:4px;"><span class="example">{pos_tag}</span></div>'
                    continue

                # Check for inline POS tags like "[名] something"
                inline_pos_match = re.match(r'^\[(.*?)\](.*)', line)
                if inline_pos_match:
                    pos_tag = inline_pos_match.group(1)
                    rest = inline_pos_match.group(2).strip()
                    line = f'<span class="example">{pos_tag}</span> {rest}'

                current_block_lines.append(line)

            flush_block() # output the final block
                
            parts.append(f'<span class="mean">{pron_header}{defs_html}</span>')

        if not parts: return ""
        return '<span class="article">' + "".join(parts) + "</span>"

    def build_entry_html(self, rows):
        r0 = rows[0]
        head = str(r0.get("字詞名", "") or "").strip()
        head_for_display = self.replace_inline_images(head)
        zi_shu = self.safe_int(r0.get("字數"), 0)

        lines = []
        
        # 5. FIX: Wrapped headword in the .dict-title-group so the orange "字詞" CSS label appears
        radical_line = self.build_radical_line(r0)
        title_html = f'<div class="dict-title-group"><span class="index">{head_for_display}</span>'
        if zi_shu == 1 and radical_line: 
            title_html += f'<span class="radical">{radical_line}</span>'
        title_html += '</div>'
        lines.append(title_html)

        bopomo_line, hanyu_line = self.make_bopomo_and_pinyin_block(rows)
        if bopomo_line: lines.append(bopomo_line)
        if hanyu_line: lines.append(hanyu_line)

        # HERE IS THE FIX applied in the correct place!
        defs_block = self.build_defs_block(rows, head)
        if defs_block: lines.append(defs_block)

        # 6. FIX: Standardized Antonyms/Synonyms to use the dashed .polyref box class
        sim = list({str(r.get("相似詞", "") or "").strip() for r in rows if str(r.get("相似詞", "") or "").strip()})
        ant = list({str(r.get("相反詞", "") or "").strip() for r in rows if str(r.get("相反詞", "") or "").strip()})
        polyref = list({str(r.get("多音參見訊息", "") or "").strip() for r in rows if str(r.get("多音參見訊息", "") or "").strip()})
        
        if sim: lines.append(f'<span class="polyref"><b>相似詞：</b>{"；".join(sim)}</span>')
        if ant: lines.append(f'<span class="polyref"><b>相反詞：</b>{"；".join(ant)}</span>')
        if polyref: lines.append(f'<span class="polyref"><b>多音參見：</b>{"；".join([self.clean_text(x) for x in polyref])}</span>')

        alias_set = list({str(r.get("辭條別名", "") or "").strip() for r in rows if str(r.get("辭條別名", "") or "").strip()})
        variants = list({str(r.get("異體字", "") or "").strip() for r in rows if str(r.get("異體字", "") or "").strip()})
        
        if alias_set: lines.append(f'<span class="polyref"><b>辭條別名：</b>{"；".join(alias_set)}</span>')
        if variants: lines.append(f'<span class="polyref"><b>異體字：</b>{"；".join(variants)}</span>')

        # Link CSS correctly
        custom_head = '<head><meta charset="utf-8"><link rel="stylesheet" type="text/css" href="jybcb.css"><script src="jybcb.js"></script></head>'
        
        return custom_head + '<div class="edugycd">' + "".join(lines) + "</div>"

    def group_rows(self, rows):
        by_head = {}
        order_heads = []
        for row in rows:
            head = str(row.get("字詞名", "") or "").strip()
            if not head: continue
            if head not in by_head:
                by_head[head] = []
                order_heads.append(head)
            by_head[head].append(row)
        return [(h, by_head[h]) for h in order_heads]

    def convert(self, input_file: str, output_file: str, encoding: str, progress_callback, log_callback) -> str:
        start_time = time.time()
        log_callback(f"Loading Excel file: {input_file} (This may take a moment...)")
        
        try:
            rows_data = read_excel_as_dicts(input_file)
        except Exception as e:
            raise RuntimeError(f"Failed to load Excel file. Ensure openpyxl is installed. Error: {e}")

        log_callback("Grouping headwords...")
        grouped = self.group_rows(rows_data)
        total_groups = len(grouped)
        
        if total_groups == 0:
            raise ValueError("No valid entries found in the Excel file.")

        entry_count = 0
        redirect_count = 0

        with open(output_file, "w", encoding=encoding, newline="\n") as f:
            for i, (head_plain, rows) in enumerate(grouped):
                html = self.build_entry_html(rows)
                
                # Write Main Entry
                f.write(f"{head_plain}\n{html}\n</>\n")
                entry_count += 1

                # Generate Redirects for Aliases
                aliases = set()
                for row in rows:
                    alias = str(row.get("辭條別名", "") or "").strip()
                    if alias:
                        for single_alias in alias.split('；'):
                            single_alias = single_alias.strip()
                            if single_alias and single_alias != head_plain:
                                aliases.add(single_alias)

                for alias in aliases:
                    f.write(f"{alias}\n@@@LINK={head_plain}\n</>\n")
                    redirect_count += 1

                # Update UI Progress
                if i % 500 == 0:
                    progress_callback(int((i / total_groups) * 100))

        progress_callback(100)
        elapsed = time.time() - start_time
        return f"Successfully generated MDict source!\nMain Entries: {entry_count}\nAlias Redirects: {redirect_count}\nTime elapsed: {elapsed:.2f}s"
