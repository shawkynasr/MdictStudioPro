import time
import re
from excel_utils import read_excel_as_dicts
from base_plugin import BaseConverterPlugin

class MOEIdiomPlugin(BaseConverterPlugin):
    name = "教育部成語典 (Excel to MDict)"
    description = "Converts the official MOE Idiom dictionary into MDict source format, perfectly mapped to jybcb.css."
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def to_circled_num(self, match):
        """Converts matched numbers into circled characters (①, ②, ③, etc.)"""
        num = int(match.group(1))
        # Unicode 9312 is ①. So 9311 + 1 = 9312
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

    def format_section(self, text, section_name, head_word=""):
        """Applies specific HTML logic and regex formatting based on the column name."""
        text = text.replace("_x000D_", "").replace("\r", "")
        if not text.strip(): return ""
        # ---> CRUCIAL FIX: Run the image replacement here! <---
        text = self.replace_inline_images(text)

        if section_name == "典源文獻內容":
            text = text.replace("\n", "")
            text = re.sub(r'\*(\d+)\*', lambda m: f'<sup class="source-num">{self.to_circled_num(m)}</sup>', text)
            return f'<span class="content-text source-content dianyuan-wenxian">{text}</span>'

        elif section_name == "典源注解":
            # Split the annotations line by line
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            list_html = '<ul class="annotation-list" style="list-style: none; padding-left: 0;">'
            
            for i, line in enumerate(lines):
                # 1. Clean any hardcoded "1." from Excel just in case
                clean_line = re.sub(r'^\d+\.\s*', '', line).strip()
                
                # 2. Generate the matching circled number (①, ②, ③)
                num = i + 1
                circled = chr(9311 + num) if 1 <= num <= 20 else f"({num})"
                
                # 3. Wrap it in the span so your CSS can color it
                list_html += f'<li style="margin-bottom: 5px;"><span class="line-num">{circled}</span> {clean_line}</li>'
                
            list_html += '</ul>'
            return f'<span class="content-text annotated-content">{list_html}</span>'

        elif section_name == "書證":
            # "書證" still uses the regex because it contains inline *1* markers
            text = re.sub(r'\*(\d+)\*', lambda m: f'<span class="line-num">{self.to_circled_num(m)}</span>', text)
            text = text.replace("\n", "<br />")
            return f'<span class="content-text annotated-content shuzheng">{text}</span>'

        elif section_name == "用法說明-例句":
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            list_html = '<ol class="example-list">'
            
            for line in lines:
                # 1. Remove the old *1* markers from Excel since <ol> numbers it natively
                clean_line = re.sub(r'\*\d+\*', '', line).strip()
                
                # 2. Automatically wrap the idiom in <em> tags to highlight it!
                if head_word:
                    clean_line = clean_line.replace(head_word, f"<em>{head_word}</em>")
                    
                list_html += f'<li>{clean_line}</li>'
                
            list_html += '</ol>'
            return f'<span class="content-text">{list_html}</span>'

        elif section_name in ["近義成語", "反義成語", "參考詞語"]:
            words = [w.strip() for w in text.split('、') if w.strip()]
            links = [f'<span class="jump-word"><a href="entry://{w}">{w}</a></span>' for w in words]
            return f'<span class="content-text reference-content">{"、".join(links)}</span>'

        # --- NEW CODE: Dynamically build an HTML table for the Compare Examples ---
        elif section_name == "辨識-例句":
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if not lines: return ""
            
            # 1. First line contains the idioms being compared
            headers = lines[0].split()
            table_html = '<table class="compare-table"><tr>'
            for h in headers:
                table_html += f'<th>{h}</th>'
            table_html += '<th>例句</th></tr>'
            
            # 2. Remaining lines contain the ○/ㄨ marks and the sentence
            for line in lines[1:]:
                parts = line.split(maxsplit=len(headers))
                table_html += '<tr>'
                for i in range(len(headers)):
                    mark = parts[i] if i < len(parts) else ""
                    table_html += f'<td class="mark">{mark}</td>'
                
                sentence = parts[-1] if len(parts) > len(headers) else ""
                table_html += f'<td class="sentence">{sentence}</td></tr>'
                
            table_html += '</table>'
            return f'<span class="content-text">{table_html}</span>'
        # -------------------------------------------------------------------------

        else:
            text = text.replace("\n", "<br />")
            return f'<span class="content-text">{text}</span>'

    def build_entry_html(self, rows):
        r0 = rows[0]
        
        head = str(r0.get("成語", "") or "").strip()
        mark_raw = str(r0.get("主條成語／非主條成語", "")).strip()
        mark = '<sup class="main-entry-mark">㊣</sup>' if mark_raw == "主條成語" else ""
        
        zhuyin = str(r0.get("注音", "") or "").strip()
        pinyin = str(r0.get("漢語拼音", "") or "").strip()
        
        # Removed the forced <br /> tags
        lines = [f'<span class="headword">{head}</span>{mark}']
        if zhuyin: lines.append(f'<span class="bopomo">{zhuyin}</span>')
        if pinyin: lines.append(f'<span class="hanyu">{pinyin}</span>')
        
        lines.append('<div class="content-section">') 
        
        cols_to_process = [
            "釋義", "典源文獻名稱", "典源文獻內容", "典源注解", "典故說明",
            "書證", "用法說明-語義說明", "用法說明-使用類別", "用法說明-例句",
            "辨識-同", "辨識-異", "辨識-例句", "近義成語", "反義成語", "參考詞語",
            "主條成語／非主條成語"
        ]
        
        for col in cols_to_process:
            raw_text = str(r0.get(col, "") or "")
            if not raw_text.strip(): continue
            
            # Print the title, then process and print the contents (No extra <br />)
            lines.append(f'<span class="content-title">{col}</span>')
            formatted_text = self.format_section(raw_text, col, head)
            lines.append(formatted_text)
            
        lines.append('</div>')
        
        entry_id = str(r0.get("編號", "")).strip()
        id_div = f'\n<div class="entry-id" style="display:none;">{entry_id}</div>' if entry_id else ""
        
        custom_head = '<head><meta charset="utf-8"><link rel="stylesheet" type="text/css" href="jybcb.css"><script src="jybcb.js"></script></head>'
        
        # Changed "<br />".join to "".join so it doesn't artificially space things out
        return custom_head + '<div class="edugycd">' + "".join(lines) + "</div>" + id_div

    def group_rows(self, rows):
        by_head = {}
        order_heads = []
        for row in rows:
            head = str(row.get("成語", "") or "").strip()
            if not head: continue
            if head not in by_head:
                by_head[head] = []
                order_heads.append(head)
            by_head[head].append(row)
        return [(h, by_head[h]) for h in order_heads]

    def convert(self, input_file: str, output_file: str, encoding: str, progress_callback, log_callback) -> str:
        start_time = time.time()
        log_callback(f"Loading Idiom Excel file: {input_file}...")
        
        try:
            rows_data = read_excel_as_dicts(input_file)
        except Exception as e:
            raise RuntimeError(f"Failed to load Excel file. Error: {e}")

        log_callback("Grouping idioms...")
        grouped = self.group_rows(rows_data)
        total_groups = len(grouped)
        
        if total_groups == 0:
            raise ValueError("No valid entries found under the '成語' column.")

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
        return f"Successfully generated MDict source!\nIdiom Entries: {entry_count}\nTime elapsed: {elapsed:.2f}s"
