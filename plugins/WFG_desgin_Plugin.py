import time
import re
from excel_utils import read_excel_as_dicts
from base_plugin import BaseConverterPlugin

class WFGRevisedPlugin(BaseConverterPlugin):
    name = "教育部重編國語辭典 (WFG Design) (Excel to MDict)"
    description = "Converts the MOE Revised Dictionary into the elegant WFG layout, mapping POS, examples, and quotes to specific CSS styles."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def to_circled_num(self, match):
        """Converts matched numbers 1. 2. into circled characters ①, ②"""
        num = int(match.group(1))
        if 1 <= num <= 20:
            return chr(9311 + num)
        return f"({num})"
        
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

    def clean_text(self, text):
        if not text: return ""
        # 1. Run the image replacement
        cleaned_text = self.replace_inline_images(str(text))
        
        # 2. Return the stripped text
        return cleaned_text.replace("_x000D_", "").replace("\r", "").strip()

    def format_definition(self, text):
        """Intelligently parses MOE text and wraps it in WFG CSS classes"""
        # Replace full-width dot with Katakana middle dot for authors
        text = text.replace("．", "・")
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        out_html = ""
        pos_count = 0
        
        for line in lines:
            # 1. POS Tags (Handles the pos1 spacer correctly)
            if line.startswith('[') and ']' in line:
                pos = line[1:line.find(']')]
                if pos_count > 0:
                    out_html += '<span class="pos1"></span>'
                out_html += f'<span class="pos">{pos}</span>'
                pos_count += 1
                line = line[line.find(']')+1:]
                if not line: continue
            
            # 2. Examples (li)
            # Matches '如：「' up to the last '」' that doesn't cross into a quote '《' or '〈'
            line = re.sub(r'(如：「[^《〈]*?」)', r'<span class="li">\1</span>', line)
            
            # 3. Quotes (yz)
            # Matches starting after a period, a closing tag '>', string start, or closing quote '」'
            line = re.sub(r'(。|>|^|」)([^。>」]*?[《〈][^<]*?」)', r'\1<span class="yz">\2</span>', line)
            
            # 4. Entry Types (Numbered vs Single)
            match = re.match(r'^(\d+)\.\s*(.*)', line)
            if match:
                num_char = self.to_circled_num(match)
                rest_of_line = match.group(2)
                out_html += f'<span class="entry"><span class="num">{num_char}</span>{rest_of_line}</span>'
            else:
                out_html += f'<span class="entry-single">{line}</span>'
            
        return out_html

    def safe_int(self, x, default=0):
        try:
            if x == "" or x is None: return default
            return int(str(x).strip())
        except:
            return default

    def build_entry_html(self, head_plain, rows):
        # The target layout drops the <head> wrapper entirely
        html = '<link href="cbgycd.css" rel="stylesheet" type="text/css"><script src="cbgycd.js"></script><cbgycd>'
        
        rows_sorted = sorted(rows, key=lambda r: self.safe_int(r.get("多音排序"), 0))
        is_polyphone = len(rows_sorted) > 1
        
        homo_numerals = ["", "㈠", "㈡", "㈢", "㈣", "㈤", "㈥", "㈦", "㈧", "㈨", "㈩"]

        for idx, r in enumerate(rows_sorted):
            # HR1 for the first entry, HR3 for subsequent polyphones
            if idx == 0:
                html += '<hr class="hr1">'
            else:
                html += '<hr class="hr3">'
                
            # Headword and Homophone Superscript
            html += f'<span class="hw">{head_plain}</span>'
            if is_polyphone and (idx + 1) < len(homo_numerals):
                html += f'<sup class="homo">{homo_numerals[idx + 1]}</sup>'
            html += '<hr class="hr2">'
            
            # Radicals and Strokes (No spaces between spans)
            radical = str(r.get("部首字", "") or "").strip()
            strokes_out = str(r.get("部首外筆畫數", "") or "").strip()
            strokes_tot = str(r.get("總筆畫數", "") or "").strip()
            
            if radical or strokes_out or strokes_tot:
                html += '<span class="sy">'
                if radical: html += f'<span class="bs">{radical}</span>'
                if strokes_out: html += f'<span class="bh">{strokes_out}</span>'
                if strokes_tot: html += f'<span class="zbh">{strokes_tot}</span>'
                html += '</span>'

            # Pronunciations (Inject full-width space for Zhuyin)
            zhuyin = str(r.get("注音一式", "") or "").strip().replace(" ", " ")
            pinyin = str(r.get("漢語拼音", "") or "").strip()
            if zhuyin: html += f'<span class="sy"><span class="zy">{zhuyin}</span></span>'
            if pinyin: html += f'<span class="sy"><span class="py">{pinyin}</span></span>'
            
            html += '<hr class="hr2">'

            # Definitions
            defs_raw = self.clean_text(r.get("釋義", ""))
            if defs_raw:
                html += self.format_definition(defs_raw)
                
            # --- RESTORED SYNONYMS & ANTONYMS ---
            # Converted from <div> to <span> to match the WFG inline flow
            sim = str(r.get("相似詞", "") or "").strip()
            ant = str(r.get("相反詞", "") or "").strip()
            if sim: html += f'<span class="jy">{sim}</span>'
            if ant: html += f'<span class="fy">{ant}</span>'
                
        html += '</cbgycd>'
        return html

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
        log_callback(f"Loading Excel file for WFG Design...")
        
        try:
            rows_data = read_excel_as_dicts(input_file)
        except Exception as e:
            raise RuntimeError(f"Failed to load Excel file. Error: {e}")

        log_callback("Grouping headwords...")
        grouped = self.group_rows(rows_data)
        total_groups = len(grouped)
        
        if total_groups == 0:
            raise ValueError("No valid entries found.")

        entry_count = 0
        with open(output_file, "w", encoding=encoding, newline="\n") as f:
            for i, (head_plain, rows) in enumerate(grouped):
                html = self.build_entry_html(head_plain, rows)
                f.write(f"{head_plain}\n{html}\n</>\n")
                entry_count += 1
                
                if i % 500 == 0:
                    progress_callback(int((i / total_groups) * 100))

        progress_callback(100)
        elapsed = time.time() - start_time
        return f"Successfully generated WFG style MDict source!\nEntries: {entry_count}\nTime: {elapsed:.2f}s"
