import time
import re
from excel_utils import read_excel_as_dicts
from base_plugin import BaseConverterPlugin

class MOEConcisePlugin(BaseConverterPlugin):
    name = "教育部國語辭典簡編本 (Excel to MDict)"
    description = "Converts the official MOE Concise Dictionary, fully optimized for jybcb.css grid layout."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def __init__(self):
        # Maps polyphonic sorting numbers to Chinese numerals
        self.CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
        # Maps variant types
        self.VARIANT_TYPE = {
            "1": "變", "2": "又音", "3": "語音", "4": "讀音",
            "變": "變", "又音": "又音", "語音": "語音", "讀音": "讀音",
        }
        
    def replace_inline_images(self, text: str) -> str:
        if not text: return ""
        
        # ONLY process the standard &filename.jpg; markers 
        # (Removed the 'alt' tag as requested for a cleaner display!)
        text = re.sub(
            r'&([\w.-]+\.(?:jpg|jpeg|gif|png));?', 
            r'<img class="pic-inline" src="\1">', 
            text, 
            flags=re.IGNORECASE
        )
        
        return text    

    def clean_text(self, s):
        if s is None: return ""
        
        # 1. Run the image replacement FIRST and save it to 'text'
        text = self.replace_inline_images(str(s))
        
        # 2. CRUCIAL FIX: Return the updated 'text' variable, not the original 'str(s)'
        return text.replace("_x000D_", "").replace("\r\n", "\n").replace("\r", "\n").strip().replace("\n", "<br />")

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

    def build_entry_html(self, rows):
        r0 = rows[0]
        head = str(r0.get("字詞名", "") or "").strip()
        
        lines = []
        
        # 1. Title Group (Generates the "字詞" orange label via CSS)
        radical_line = self.build_radical_line(r0)
        title_html = f'<div class="dict-title-group"><span class="index">{head}</span>'
        if radical_line: 
            # CSS ::before and ::after automatically add the [ ] brackets
            title_html += f'<span class="radical">{radical_line}</span>'
        title_html += '</div>'
        lines.append(title_html)

        # 2. Pronunciations and Definitions (Grouped by polyphonic sorting)
        rows_sorted = sorted(rows, key=lambda r: (0 if self.safe_int(r.get("多音排序"), 0) > 0 else 1, self.safe_int(r.get("多音排序"), 0)))
        pos_ns = [self.safe_int(r.get("多音排序"), 0) for r in rows_sorted if self.safe_int(r.get("多音排序"), 0) > 0]
        need_enum = len(set(pos_ns)) >= 2
        
        zhuyin_list, hanyu_list, mean_parts = [], [], []
        
        for r in rows_sorted:
            n = self.safe_int(r.get("多音排序"), 0)
            prefix = f"({self.CN_NUM.get(n, str(n))}) " if (need_enum and n > 0) else ""
            
            zhuyin = str(r.get("注音一式", "") or "").strip()
            pinyin = str(r.get("漢語拼音", "") or "").strip()
            var_zhuyin = str(r.get("變體注音", "") or "").strip()
            var_pinyin = str(r.get("變體漢語拼音", "") or "").strip()
            
            defs = self.clean_text(r.get("釋義", ""))
            
            var_type_raw = str(r.get("變體類型 1:變 2:又音 3:語音 4:讀音", "") or "").strip()
            var_type = self.VARIANT_TYPE.get(var_type_raw, var_type_raw)
            # Uses the CSS .example class for red variant tags
            var_tag = f'<span class="example">{var_type}</span>' if var_type else ""
            
            # Accumulate pronunciations without label text (CSS handles labels)
            if zhuyin: zhuyin_list.append(prefix + zhuyin)
            if pinyin: hanyu_list.append(prefix + pinyin)
            if var_zhuyin: zhuyin_list.append(var_tag + var_zhuyin)
            if var_pinyin: hanyu_list.append(var_tag + var_pinyin)
            
            # Accumulate definitions inside .mean blocks
            if defs:
                mean_parts.append(f'<span class="mean">{prefix}{defs}</span>')

        # Remove duplicate pronunciations while preserving order
        zhuyin_list = list(dict.fromkeys(zhuyin_list))
        hanyu_list = list(dict.fromkeys(hanyu_list))

        # 3. Add Blocks to Lines
        if zhuyin_list:
            lines.append(f'<span class="bopomo">{" ".join(zhuyin_list)}</span>')
        if hanyu_list:
            lines.append(f'<span class="hanyu">{" ".join(hanyu_list)}</span>')
            
        if mean_parts:
            # CSS makes the outer text "釋義：" transparent, and restores color for .mean inner blocks
            article_html = f'<span class="article">釋義：{"".join(mean_parts)}</span>'
            lines.append(article_html)

        # 4. Synonyms, Antonyms, and References (Using the dashed .polyref box styling)
        sim = list({str(r.get("相似詞", "") or "").strip() for r in rows if str(r.get("相似詞", "") or "").strip()})
        ant = list({str(r.get("相反詞", "") or "").strip() for r in rows if str(r.get("相反詞", "") or "").strip()})
        polyref = list({str(r.get("多音參見訊息", "") or "").strip() for r in rows if str(r.get("多音參見訊息", "") or "").strip()})

        if sim: lines.append(f'<span class="polyref"><b>相似詞：</b>{"；".join(sim)}</span>')
        if ant: lines.append(f'<span class="polyref"><b>相反詞：</b>{"；".join(ant)}</span>')
        if polyref: lines.append(f'<span class="polyref"><b>多音參見：</b>{"；".join(self.clean_text(x) for x in polyref)}</span>')

        # Wrap everything in .edugycd and link the correct CSS
        custom_head = '<head><meta charset="utf-8"><link rel="stylesheet" type="text/css" href="jybcb.css"></head>'
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
        log_callback(f"Loading Concise Dictionary Excel file...")
        
        try:
            rows_data = read_excel_as_dicts(input_file)
        except Exception as e:
            raise RuntimeError(f"Failed to load Excel file: {e}")

        log_callback("Grouping entries by headword...")
        grouped = self.group_rows(rows_data)
        total_groups = len(grouped)
        
        if total_groups == 0:
            raise ValueError("No valid entries found under the '字詞名' column.")

        entry_count = 0
        with open(output_file, "w", encoding=encoding, newline="\n") as f:
            for i, (head_plain, rows) in enumerate(grouped):
                html = self.build_entry_html(rows)
                f.write(f"{head_plain}\n{html}\n</>\n")
                entry_count += 1
                
                if i % 500 == 0:
                    progress_callback(int((i / total_groups) * 100))

        progress_callback(100)
        elapsed = time.time() - start_time
        return f"Successfully generated MDict source!\nMain Entries: {entry_count}\nTime elapsed: {elapsed:.2f}s"
