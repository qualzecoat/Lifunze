# Parser format legacy v1 (label JUDUL:/TUJUAN:/MATERI:/CONTOH: dan blok SOAL n/JAWABAN:) — dipertahankan untuk kompatibilitas impor konten lama.
import html
import re

def legacy_parse_material(raw_text):
    lines = raw_text.split('\n')
    html_output = []
    current_label = None
    current_content = []

    def process_block(label, content):
        if not content: return ""
        # Escape SEMUA teks pengguna — keluaran fungsi ini disimpan sebagai
        # rendered_html dan dirender mentah di halaman siswa (audit #3:
        # tanpa escape, <img onerror=...> lolos menjadi stored XSS).
        text = "<br>".join(html.escape(c) for c in content)
        if label == 'JUDUL':
            return f'<h2 class="material-judul">{text}</h2>'
        elif label == 'TUJUAN':
            return f'<div class="material-tujuan"><strong>Tujuan:</strong><br>{text}</div>'
        elif label == 'MATERI':
            return f'<div class="material-teks">{text}</div>'
        elif label == 'CONTOH':
            return f'<div class="material-contoh"><strong>Contoh:</strong><br>{text}</div>'
        else:
            return f'<div class="material-section material-{label.lower()}"><strong>{label}:</strong><br>{text}</div>'

    for line in lines:
        line_stripped = line.strip()
        match = re.match(r'^([A-Z_]+):(.*)$', line_stripped)
        if match:
            if current_label:
                html_output.append(process_block(current_label, current_content))
            current_label = match.group(1)
            content_part = match.group(2).strip()
            current_content = [content_part] if content_part else []
        else:
            if current_label:
                current_content.append(line_stripped)
            else:
                if line_stripped:
                    html_output.append(f'<div>{html.escape(line_stripped)}</div>')

    if current_label:
        html_output.append(process_block(current_label, current_content))

    return "\n".join(html_output)

def legacy_parse_quiz_mcq(raw_text):
    questions = []
    blocks = re.split(r'^SOAL\s+\d+\s*$', raw_text, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        question_text = []
        options = {}
        correct_answer = None
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            opt_match = re.match(r'^([A-Z])\.\s*(.*)$', line)
            ans_match = re.match(r'^JAWABAN:\s*([A-Z])$', line, re.IGNORECASE)
            if ans_match:
                correct_answer = ans_match.group(1).upper()
            elif opt_match:
                options[opt_match.group(1)] = opt_match.group(2)
            else:
                question_text.append(line)
            i += 1
        if question_text and options and correct_answer:
            questions.append({
                'pertanyaan': '\n'.join(question_text),
                'opsi_a': options.get('A', ''),
                'opsi_b': options.get('B', ''),
                'opsi_c': options.get('C', ''),
                'opsi_d': options.get('D', ''),
                'jawaban_benar': correct_answer
            })
    return questions

def legacy_parse_quiz_text(raw_text):
    questions = []
    blocks = re.split(r'^SOAL\s+\d+\s*$', raw_text, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        questions.append({
            'pertanyaan': block,
            'jawaban_referensi': None
        })
    return questions

