import time
import re
from excel_utils import read_excel_as_dicts
from base_plugin import BaseConverterPlugin

class MOEMiniPlugin(BaseConverterPlugin):
    name = "教育部國語小字典 (Excel to MDict)"
    description = "Converts the official MOE Mini Dictionary, generating HTML5 Ruby text (Zhuyin) above characters."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def __init__(self):
        # Maps list numbers to Chinese numerals for multiple pronunciations/meanings
        self.CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}
    
    def replace_inline_images(self, text: str) -> str:
        if not text: return ""
        
        # ONLY process the standard &filename.jpg; markers 
        text = re.sub(
            r'&([\w.-]+\.(?:jpg|jpeg|gif|png));?', 
            r'<img class="pic-inline" src="\1">', 
            text, 
            flags=re.IGNORECASE
        )
        
        return text
        
    def clean_text(self, s):
        if s is None: return ""
        # 1. Run the image replacement FIRST
        text = self.replace_inline_images(str(s))
        text = str(s).replace("_x000D_", "").replace("\r\n", "\n").replace("\r", "\n").strip()
        
        # 2. Strip the && delimiters completely
        text = text.replace("&&", "")
        
        # 3. Find any character followed by Bopomofo/Tones and wrap them in <ruby> and <rt> tags
        # (.) grabs the Hanzi, ([ㄅ-ㄩ˙ˊˇˋ]+) grabs the exact Zhuyin string attached to it
        text = re.sub(r'(.)([ㄅ-ㄩ˙ˊˇˋ]+)', r'<ruby>\1<rt>\2</rt></ruby>', text)
        
        return text.replace("\n", "<br />")

    def build_radical_line(self, row):
        radical = str(row.get("部首", "") or "").strip()
        total = str(row.get("總筆畫數", "") or "").strip()
        out = str(row.get("部首外筆畫", "") or "").strip()
        
        if not radical and not total and not out: return ""
        
        pieces = []
        if radical: pieces.append(f"{radical}部")
        if out: pieces.append(f"部外 {out} 畫")
        if total: pieces.append(f"總筆畫 {total} 畫")
        return " ".join(pieces)

    def build_entry_html(self, rows):
        r0 = rows[0]
        head = str(r0.get("單字", "") or "").strip()
        
        lines = []
        
        # 1. Title Group (Generates the "字詞" orange label via CSS)
        radical_line = self.build_radical_line(r0)
        title_html = f'<div class="dict-title-group"><span class="index">{head}</span>'
        if radical_line: 
            title_html += f'<span class="radical">{radical_line}</span>'
        title_html += '</div>'
        lines.append(title_html)

        # 2. Pronunciations and Definitions
        multiple = len(rows) > 1
        zhuyin_list, mean_parts = [], []
        
        for i, r in enumerate(rows):
            zhuyin = str(r.get("注音", "") or "").strip()
            defs = self.clean_text(r.get("解釋", ""))
            
            prefix = f"({self.CN_NUM.get(i+1, str(i+1))}) " if multiple else ""
            
            if zhuyin:
                zhuyin_list.append(prefix + zhuyin)
            
            if defs:
                mean_parts.append(f'<span class="mean">{prefix}{defs}</span>')

        # 3. Add Blocks to Lines
        if zhuyin_list:
            lines.append(f'<span class="bopomo">{" ".join(zhuyin_list)}</span>')
            
        if mean_parts:
            lines.append(f'<span class="article">釋義：{"".join(mean_parts)}</span>')

        # Injecting the official MOE Ruby CSS for perfect vertical Bopomofo alignment
        custom_head = """<head>
        <meta charset="utf-8">
        <link rel="stylesheet" type="text/css" href="jybcb.css">
        <style>
            ruby {
                display: inline-flex;
                align-items: center;
                vertical-align: bottom;
            }
            ruby rt {
                display: block;
                font-family: "Bopomofo Custom", "Bopomofo", "TWK-Mod", "DFKai-sb", sans-serif;
                font-size: 45%; /* Adjusted slightly from 30% for better dictionary readability */
                font-weight: 500;
                line-height: 1;
                text-align: center;
                padding-left: 0.1em;
                position: relative;
                -webkit-text-orientation: upright;
                text-orientation: upright;
                -webkit-writing-mode: vertical-lr;
                writing-mode: vertical-lr;
                white-space: nowrap;
                width: 1.5em;
                color: inherit;
            }
            ruby rt:empty {
                display: none;
            }
        </style>
        </head>"""
        
        return custom_head + '<div class="edugycd">' + "".join(lines) + "</div>"

    def group_rows(self, rows):
        by_head = {}
        order_heads = []
        for row in rows:
            head = str(row.get("單字", "") or "").strip()
            if not head: continue
            if head not in by_head:
                by_head[head] = []
                order_heads.append(head)
            by_head[head].append(row)
        return [(h, by_head[h]) for h in order_heads]

    def convert(self, input_file: str, output_file: str, encoding: str, progress_callback, log_callback) -> str:
        start_time = time.time()
        log_callback(f"Loading Mini Dictionary Excel file...")
        
        try:
            rows_data = read_excel_as_dicts(input_file)
        except Exception as e:
            raise RuntimeError(f"Failed to load Excel file: {e}")

        log_callback("Grouping entries by character...")
        grouped = self.group_rows(rows_data)
        total_groups = len(grouped)
        
        if total_groups == 0:
            raise ValueError("No valid entries found under the '單字' column. Please check your Excel headers.")

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
