import time
import os
import re
from base_plugin import BaseConverterPlugin

class CCCEDICTPlugin(BaseConverterPlugin):
    name = "CC-CEDICT to MDict (Pro)"
    description = "Parses CC-CEDICT format (cedict_ts.u8) into MDict source text. Applies Pinyin tone marks, clickable Traditional/Simplified links, CSS tags, and generates a conversion log file."
    file_filter = "CC-CEDICT Files (*.u8 *.txt);;All Files (*.*)"
    default_encodings = ["utf-8", "big5", "gb18030"]

    def __init__(self):
        self.line_pattern = re.compile(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/$')
        self.pinyin_tones = {
            'a': 'āáǎàa', 'e': 'ēéěèe', 'i': 'īíǐìi',
            'o': 'ōóǒòo', 'u': 'ūúǔùu', 'v': 'ǖǘǚǜü', 'ü': 'ǖǘǚǜü'
        }

        # Pre-processing regexes
        self.xref_pattern_1 = re.compile(r'([^ ]+)\|([^a-z\[< ]+)')
        self.xref_pattern_2 = re.compile(r'("cc_def_pinyin".+)')

        # Tag replacements
        self.replacements = {
            "(old)": '<span class="cc_tag">(old)</span>',
            "(slang)": '<span class="cc_tag">(slang)</span>',
            "(coll.)": '<span class="cc_tag">(coll.)</span>',
            "(archaic)": '<span class="cc_tag">(archaic)</span>',
            "(bird species of China)": '<span class="cc_tag">(bird species of China)</span>',
            "(idiom)": '<span class="cc_tag">(idiom)</span>',
            "(Tw)": '<span class="cc_tag">(Tw)</span>',
            "(vulgar)": '<span class="cc_tag">(vulgar)</span>',
            "(Internet slang)": '<span class="cc_tag">(Internet slang)</span>',
            "(loanword)": '<span class="cc_tag">(loanword)</span>',
            "(computing)": '<span class="cc_tag">(computing)</span>',
            "(math.)": '<span class="cc_tag">(math.)</span>',
            "(chemistry)": '<span class="cc_tag">(chemistry)</span>',
            "(medicine)": '<span class="cc_tag">(medicine)</span>',
            "(Chinese medicine)": '<span class="cc_tag">(Chinese medicine)</span>',
            "(botany)": '<span class="cc_tag">(botany)</span>',
            "(Buddhism)": '<span class="cc_tag">(Buddhism)</span>',
            "(dialect)": '<span class="cc_tag">(dialect)</span>',
            "(Cantonese)": '<span class="cc_tag">(Cantonese)</span>',
            "(Taiwanese)": '<span class="cc_tag">(Taiwanese)</span>',
            "i.e.": '<span class="cc_ie">i.e.</span>',
            "e.g.": '<span class="cc_ie">e.g.</span>',
            "fig.": '<span class="cc_ie">fig.</span>',
            "lit.": '<span class="cc_ie">lit.</span>',
            "CL: ": '<span class="cc_ie">CL</span> :',
            "CL": '<span class="cc_ie">CL</span>',
            "(abbr.)": '<span class="cc_ie">(abbr.)</span>'
        }
        
        sorted_keys = sorted(self.replacements.keys(), key=len, reverse=True)
        escaped_keys = [re.escape(k) for k in sorted_keys]
        self.replace_pattern = re.compile(f"({'|'.join(escaped_keys)})")

    def convert_pinyin(self, pinyin_str: str) -> str:
        words = pinyin_str.split(' ')
        converted = []
        for word in words:
            if not word or not word[-1].isdigit():
                converted.append(word.replace('u:', 'ü'))
                continue
            tone = int(word[-1])
            if tone < 1 or tone > 5:
                converted.append(word[:-1].replace('u:', 'ü'))
                continue
            w = word[:-1].lower().replace('u:', 'ü')
            if tone == 5:
                converted.append(w)
                continue
            vowels = 'aeiouvü'
            target = ''
            if 'a' in w: target = 'a'
            elif 'e' in w: target = 'e'
            elif 'ou' in w: target = 'o'
            else:
                for c in reversed(w):
                    if c in vowels: target = c; break
            if target:
                w = w.replace(target, self.pinyin_tones[target][tone - 1], 1)
            converted.append(w)
        return ' '.join(converted)

    def _replace_match(self, match):
        return self.replacements.get(match.group(0), match.group(0))

    def convert(self, input_file: str, output_file: str, encoding: str, progress_callback, log_callback) -> str:
        start_time = time.time()
        log_callback(f"Analyzing dictionary: {input_file} (Encoding: {encoding})")

        with open(input_file, 'r', encoding=encoding) as f:
            total_lines = sum(1 for _ in f)

        if total_lines == 0:
            raise ValueError("The selected file is empty.")

        log_callback(f"Found {total_lines} lines. Starting conversion...")

        header_lines = []
        entry_count = 0
        link_count = 0

        with open(input_file, 'r', encoding=encoding) as infile, \
             open(output_file, 'w', encoding='utf-8') as outfile:
            
            for i, line in enumerate(infile):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    header_lines.append(line)
                    continue

                m = self.line_pattern.match(line)
                if m:
                    trad, simp, pinyin_raw, defs_str = m.groups()
                    py_accented = self.convert_pinyin(pinyin_raw)
                    defs = [d for d in defs_str.split('/') if d]

                    html = '<link rel="stylesheet" type="text/css" href="cedict_ts.css">'
                    html += '<div class="cc_wrapper"><div class="cc_header">'
                    html += f'<span class="cc_trad">{trad}</span><span class="cc_simp">{simp}</span></div>'
                    html += f'<div class="cc_header_pinyin">{py_accented}</div><div class="cc_defs">'
                    
                    for d in defs:
                        d = self.xref_pattern_1.sub(r'<a href="entry://\1">\1</a>|<a href="entry://\2">\2</a><font class="cc_def_pinyin">', d)
                        d = self.xref_pattern_2.sub(r'\1</font>', d)
                        d = d.replace('<font class="cc_def_pinyin"></p><p class="cc_def">', '')
                        d = self.replace_pattern.sub(self._replace_match, d)
                        html += f'<p class="cc_def">{d}</p>'
                        
                    html += '</div></div>'

                    outfile.write(f"{simp}\n{html}\n</>\n")
                    entry_count += 1
                    
                    if trad != simp:
                        outfile.write(f"{trad}\n{html}\n</>\n")
                        link_count += 1

                if i % 500 == 0:
                    progress_callback(int((i / total_lines) * 100))

        # Generate Log File
        total_time = time.time() - start_time
        log_filepath = input_file + "_log.txt"
        
        with open(log_filepath, 'w', encoding='utf-8') as log_file:
            log_file.write(f"Charset: {encoding.upper()}\n")
            log_file.write("-" * 20 + "\n")
            for h_line in header_lines:
                log_file.write(h_line + "\n")
            log_file.write("-" * 20 + "\n")
            log_file.write(f"Entry Count: {entry_count}\n")
            log_file.write(f"Link Count: {link_count}\n")
            log_file.write(f"Total words: {entry_count + link_count}\n")
            log_file.write("-" * 20 + "\n")
            log_file.write("CREATE SUCCESS\n")
            log_file.write("-" * 20 + "\n")
            log_file.write(f"Total time: {total_time:.2f}s\n")

        progress_callback(100)
        return f"Successfully generated MDict source and log file.\nTotal entries: {entry_count}\nTotal links: {link_count}\nTime elapsed: {total_time:.2f}s"