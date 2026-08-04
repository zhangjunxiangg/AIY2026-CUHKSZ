"""Extract text from .docx files to Markdown using stdlib only (zipfile + XML)."""
import sys, zipfile, re
import xml.etree.ElementTree as ET
from pathlib import Path

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def para_text(p):
    parts = []
    for node in p.iter():
        if node.tag == W + 't':
            parts.append(node.text or '')
        elif node.tag == W + 'tab':
            parts.append('\t')
        elif node.tag == W + 'br':
            parts.append('\n')
    return ''.join(parts).strip()

def para_style(p):
    pPr = p.find(W + 'pPr')
    if pPr is None:
        return ''
    st = pPr.find(W + 'pStyle')
    return st.get(W + 'val', '') if st is not None else ''

def extract(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    body = root.find(W + 'body')
    lines = []
    for el in body:
        if el.tag == W + 'p':
            t = para_text(el)
            if not t:
                continue
            style = para_style(el)
            m = re.match(r'[Hh]eading(\d)', style or '')
            if m:
                lines.append('#' * min(int(m.group(1)) + 1, 6) + ' ' + t)
            else:
                lines.append(t)
        elif el.tag == W + 'tbl':
            rows = []
            for tr in el.findall(W + 'tr'):
                cells = []
                for tc in tr.findall(W + 'tc'):
                    txt = ' '.join(filter(None, (para_text(p) for p in tc.findall(W + 'p'))))
                    cells.append(txt.replace('|', '\\|'))
                rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [''] * (width - len(r)) for r in rows]
                lines.append('| ' + ' | '.join(rows[0]) + ' |')
                lines.append('|' + '---|' * width)
                for r in rows[1:]:
                    lines.append('| ' + ' | '.join(r) + ' |')
        lines.append('')
    return '\n'.join(lines)

if __name__ == '__main__':
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(extract(src), encoding='utf-8')
    print(f'OK {src.name} -> {dst.name} ({dst.stat().st_size} bytes)')
