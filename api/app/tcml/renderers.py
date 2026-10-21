# Renderer TCML: mengubah AST menjadi HTML (materi) atau struktur soal (kuis).
# Porting 1:1 dari v1: MaterialRenderer + QuizRenderer + ExtendedMaterialRenderer.
# Pengelompokan tag per modul ada di registry.py; renderer ini implementasinya.
from .core import BlockNode, TextNode
class MaterialRenderer:
    def __init__(self, root_node):
        self.root_node = root_node
        self.errors = []

    def render(self):
        # Find the main MATERIAL block
        material_nodes = [c for c in self.root_node.children if isinstance(c, BlockNode) and c.tag == 'MATERIAL']
        if not material_nodes:
            self.errors.append({"line": 1, "message": "Missing [MATERIAL] block."})
            return ""

        return self._render_node(material_nodes[0])

    def _render_node(self, node):
        from markupsafe import escape

        if isinstance(node, TextNode):
            # Safe HTML escape of text
            text = str(escape(node.text))

            # Simple conversion of double newlines to paragraphs
            parts = text.split('\n\n')
            html_parts = []
            for part in parts:
                part = part.strip()
                if part:
                    # Single newlines within a paragraph get <br>
                    part_with_br = part.replace('\n', '<br>')
                    html_parts.append(f'<p>{part_with_br}</p>')
            return '\n'.join(html_parts)

        if isinstance(node, BlockNode):
            inner_html = ""
            for child in node.children:
                inner_html += self._render_node(child)

            tag = node.tag

            if tag == 'MATERIAL':
                return f'<div class="tc-material">\n{inner_html}\n</div>'
            elif tag == 'TITLE':
                # Strip wrapping p tags if title is single line
                inner_html = self._strip_outer_p(inner_html)
                return f'<h1 class="tc-title">{inner_html}</h1>'
            elif tag == 'HEADING':
                inner_html = self._strip_outer_p(inner_html)
                return f'<h2 class="tc-heading">{inner_html}</h2>'
            elif tag == 'PARAGRAPH':
                return inner_html # TextNode already wraps in <p>
            elif tag == 'NOTE':
                return f'<div class="tc-note"><strong>Note:</strong><br>{inner_html}</div>'
            elif tag == 'WARNING':
                return f'<div class="tc-warning"><strong>Warning:</strong><br>{inner_html}</div>'
            elif tag == 'SUMMARY':
                return f'<div class="tc-summary"><strong>Summary:</strong><br>{inner_html}</div>'
            elif tag == 'EXAMPLE':
                return f'<div class="tc-example"><strong>Example:</strong><br>{inner_html}</div>'
            elif tag == 'OBJECTIVE':
                return f'<div class="tc-objective"><strong>Objective:</strong><br>{inner_html}</div>'
            elif tag == 'STEPS':
                return f'<div class="tc-steps">\n{inner_html}\n</div>'
            elif tag == 'STEP':
                inner_html = self._strip_outer_p(inner_html)
                return f'<div class="tc-step">{inner_html}</div>'
            elif tag == 'FORMULA':
                # Don't convert newlines to p tags for raw content blocks
                raw_text = self._get_raw_text(node).strip()
                safe_formula = escape(raw_text)
                return f'<pre class="tc-formula"><code>{safe_formula}</code></pre>'
            elif tag == 'CODE':
                raw_text = self._get_raw_text(node).strip()
                safe_code = escape(raw_text)
                return f'<pre class="tc-code"><code>{safe_code}</code></pre>'
            elif tag == 'DATASET' or tag == 'TABLE':
                raw_text = self._get_raw_text(node).strip()
                return self._render_table(raw_text)
            elif tag == 'SCRATCH':
                from .scratch import scratch_embed_html
                return scratch_embed_html(self._get_raw_text(node), node.line, self.errors)
            elif tag == 'BLOCKS':
                from .scratch import blocks_html
                return blocks_html(self._get_raw_text(node))
            elif tag == 'SPRITE':
                from .scratch import sprite_html
                return sprite_html(self._get_raw_text(node))
            else:
                self.errors.append({"line": node.line, "message": f"Unknown tag: [{node.tag}]"})
                return inner_html

        return ""

    def _strip_outer_p(self, html):
        html = html.strip()
        if html.startswith('<p>') and html.endswith('</p>'):
            return html[3:-4]
        return html

    def _get_raw_text(self, node):
        text = ""
        for child in node.children:
            if isinstance(child, TextNode):
                text += child.text
            elif isinstance(child, BlockNode):
                text += self._get_raw_text(child)
        return text

    def _render_table(self, raw_text):
        from markupsafe import escape
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        if not lines:
            return ""

        html = ['<div class="tc-table-container">']
        html.append('<table class="tc-table">')

        for i, line in enumerate(lines):
            cells = [cell.strip() for cell in line.split('|')]
            if i == 0:
                html.append('  <thead>')
                html.append('    <tr>')
                for cell in cells:
                    html.append(f'      <th>{escape(cell)}</th>')
                html.append('    </tr>')
                html.append('  </thead>')
                html.append('  <tbody>')
            else:
                html.append('    <tr>')
                for cell in cells:
                    html.append(f'      <td>{escape(cell)}</td>')
                html.append('    </tr>')

        if len(lines) > 0:
            html.append('  </tbody>')
        html.append('</table>')
        html.append('</div>')

        return '\n'.join(html)


class QuizRenderer:
    def __init__(self, root_node, quiz_type):
        self.root_node = root_node
        self.quiz_type = quiz_type # 'pilihan_ganda' or 'teks'
        self.errors = []
        self.questions = []

    def render(self):
        quiz_nodes = [c for c in self.root_node.children if isinstance(c, BlockNode) and c.tag == 'QUIZ']
        if not quiz_nodes:
            self.errors.append({"line": 1, "message": "Missing [QUIZ] block."})
            return []

        quiz_node = quiz_nodes[0]

        # Verify type if specified
        type_nodes = [c for c in quiz_node.children if isinstance(c, BlockNode) and c.tag == 'TYPE']
        if type_nodes:
            declared_type = self._get_raw_text(type_nodes[0]).strip().lower()
            if declared_type != self.quiz_type and not (declared_type == 'essay' and self.quiz_type == 'teks'):
                 self.errors.append({"line": type_nodes[0].line, "message": f"Quiz type mismatch. Expected '{self.quiz_type}', found '{declared_type}'."})
                 return []

        # Parse questions
        question_nodes = [c for c in quiz_node.children if isinstance(c, BlockNode) and c.tag.startswith('QUESTION ')]

        for q_node in question_nodes:
            self._parse_question(q_node)

        return self.questions

    def _parse_question(self, node):
        q_text_node = self._find_first_child(node, 'QUESTION')
        if not q_text_node:
            self.errors.append({"line": node.line, "message": f"Missing [QUESTION] in [{node.tag}]."})
            return

        pertanyaan = self._get_raw_text(q_text_node).strip()

        if self.quiz_type == 'pilihan_ganda':
            options_node = self._find_first_child(node, 'OPTIONS')
            answer_node = self._find_first_child(node, 'ANSWER')

            if not options_node:
                self.errors.append({"line": node.line, "message": f"Missing [OPTIONS] in [{node.tag}]."})
                return
            if not answer_node:
                self.errors.append({"line": node.line, "message": f"Missing [ANSWER] in [{node.tag}]."})
                return

            opsi_a = opsi_b = opsi_c = opsi_d = ""
            options_text = self._get_raw_text(options_node).strip()
            lines = options_text.split('\n')

            import re
            for line in lines:
                line = line.strip()
                match = re.match(r'^([A-D])\.\s*(.*)$', line)
                if match:
                    opt = match.group(1).upper()
                    val = match.group(2)
                    if opt == 'A': opsi_a = val
                    elif opt == 'B': opsi_b = val
                    elif opt == 'C': opsi_c = val
                    elif opt == 'D': opsi_d = val

            jawaban_benar = self._get_raw_text(answer_node).strip().upper()
            if jawaban_benar not in ['A', 'B', 'C', 'D']:
                self.errors.append({"line": answer_node.line, "message": f"Invalid [ANSWER] '{jawaban_benar}' in [{node.tag}]. Must be A, B, C, or D."})

            self.questions.append({
                'pertanyaan': pertanyaan,
                'opsi_a': opsi_a,
                'opsi_b': opsi_b,
                'opsi_c': opsi_c,
                'opsi_d': opsi_d,
                'jawaban_benar': jawaban_benar
            })

        else: # essay
            answer_node = self._find_first_child(node, 'ANSWER')
            jawaban_referensi = self._get_raw_text(answer_node).strip() if answer_node else ""

            self.questions.append({
                'pertanyaan': pertanyaan,
                'jawaban_referensi': jawaban_referensi
            })

    def _find_first_child(self, node, tag):
        for child in node.children:
            if isinstance(child, BlockNode) and child.tag == tag:
                return child
        return None

    def _get_raw_text(self, node):
        text = ""
        for child in node.children:
            if isinstance(child, TextNode):
                text += child.text
            elif isinstance(child, BlockNode):
                text += self._get_raw_text(child)
        return text


class ExtendedMaterialRenderer(MaterialRenderer):
    def render(self):
        # Allow ROOT to process multiple main blocks if needed, but typically there's one.
        # Find all main container blocks
        main_nodes = [c for c in self.root_node.children if isinstance(c, BlockNode) and c.tag in ('MATERIAL', 'EXERCISE', 'PROJECT')]
        if not main_nodes:
            self.errors.append({"line": 1, "message": "Missing main block [MATERIAL], [EXERCISE], or [PROJECT]."})
            return ""

        # Audit #18: konten di luar akar materi TIDAK lagi dibuang diam-diam.
        # Teks bebas di tingkat dokumen dan akar asing (mis. [QUIZ] yang
        # ditempel ke materi mandiri) kini menjadi error yang jelas.
        for c in self.root_node.children:
            if isinstance(c, TextNode) and c.text.strip():
                self.errors.append({
                    "line": c.line,
                    "message": "Ada teks di luar akar [MATERIAL]/[EXERCISE]/[PROJECT] — teks itu tidak akan tampil. Pindahkan ke dalam akar dokumen.",
                })
            elif isinstance(c, BlockNode) and c.tag not in ('MATERIAL', 'EXERCISE', 'PROJECT'):
                self.errors.append({
                    "line": c.line,
                    "message": f"Akar [{c.tag}] tidak bisa dimuat sebagai materi. Untuk kuis, buat dokumen/kuis terpisah lewat editor dokumen.",
                })

        html_out = ""
        for node in main_nodes:
            html_out += self._render_node(node)
        return html_out

    def _render_node(self, node):
        from markupsafe import escape

        if isinstance(node, TextNode):
            text = str(escape(node.text))
            parts = text.split('\n\n')
            html_parts = []
            for part in parts:
                part = part.strip()
                if part:
                    part_with_br = part.replace('\n', '<br>')
                    html_parts.append(f'<p>{part_with_br}</p>')
            return '\n'.join(html_parts)

        if isinstance(node, BlockNode):
            if node.tag == 'CEK':
                # Soal sisipan "Cek Pemahaman": divalidasi di sini (error
                # menggagalkan simpan materi), dirender sebagai placeholder
                # TANPA kunci — panel interaktifnya diisi frontend dari
                # payload API, pengecekan jawaban selalu di server.
                from .cek import parse_cek_node

                idx = getattr(self, "_cek_counter", 0)
                self._cek_counter = idx + 1
                parse_cek_node(node, self.errors)
                return (
                    f'<div class="tc-cek" data-cek-index="{idx}">'
                    f'<p class="tc-cek-placeholder">🧠 Cek Pemahaman {idx + 1}</p></div>'
                )
            tag = node.tag
            # Audit #6: blok mentah dirender dari teks aslinya TANPA
            # merekursi anak — [CEK] contoh di dalam [CODE]/[FORMULA]/dll
            # tidak boleh terhitung sebagai soal sisipan atau memicu error
            # validasi soal.
            if tag == 'FORMULA':
                raw_text = self._get_raw_text(node).strip()
                return f'<pre class="tc-formula"><code>{str(escape(raw_text))}</code></pre>'
            if tag == 'CODE':
                raw_text = self._get_raw_text(node).strip()
                return f'<pre class="tc-code"><code>{str(escape(raw_text))}</code></pre>'
            if tag in ('DATASET', 'TABLE'):
                return self._render_table(self._get_raw_text(node).strip())
            if tag == 'SCRATCH':
                from .scratch import scratch_embed_html
                return scratch_embed_html(self._get_raw_text(node), node.line, self.errors)
            if tag == 'BLOCKS':
                from .scratch import blocks_html
                return blocks_html(self._get_raw_text(node))
            if tag == 'SPRITE':
                from .scratch import sprite_html
                return sprite_html(self._get_raw_text(node))
            inner_html = ""
            for child in node.children:
                inner_html += self._render_node(child)

            # --- Base Blocks ---
            if tag == 'MATERIAL':
                return f'<div class="tc-material">\n{inner_html}\n</div>'
            elif tag == 'EXERCISE':
                return f'<div class="tc-exercise">\n{inner_html}\n</div>'
            elif tag == 'PROJECT':
                return f'<div class="tc-project">\n{inner_html}\n</div>'

            elif tag == 'TITLE':
                inner_html = self._strip_outer_p(inner_html)
                return f'<h1 class="tc-title">{inner_html}</h1>'
            elif tag == 'HEADING':
                inner_html = self._strip_outer_p(inner_html)
                return f'<h2 class="tc-heading">{inner_html}</h2>'
            elif tag == 'PARAGRAPH':
                return inner_html

            elif tag == 'NOTE':
                return f'<div class="tc-note"><strong>Note:</strong><br>{inner_html}</div>'
            elif tag == 'WARNING':
                return f'<div class="tc-warning"><strong>Warning:</strong><br>{inner_html}</div>'
            elif tag == 'SUMMARY':
                return f'<div class="tc-summary"><strong>Summary:</strong><br>{inner_html}</div>'
            elif tag == 'EXAMPLE':
                return f'<div class="tc-example"><strong>Example:</strong><br>{inner_html}</div>'
            elif tag == 'OBJECTIVE':
                return f'<div class="tc-objective"><strong>Objective:</strong><br>{inner_html}</div>'
            elif tag == 'STEPS':
                return f'<div class="tc-steps">\n{inner_html}\n</div>'
            elif tag == 'STEP':
                inner_html = self._strip_outer_p(inner_html)
                return f'<div class="tc-step">{inner_html}</div>'

            # --- Code / Data ---
            elif tag == 'FORMULA':
                raw_text = self._get_raw_text(node).strip()
                safe_formula = str(escape(raw_text))
                return f'<pre class="tc-formula"><code>{safe_formula}</code></pre>'
            elif tag == 'CODE':
                raw_text = self._get_raw_text(node).strip()
                safe_code = str(escape(raw_text))
                return f'<pre class="tc-code"><code>{safe_code}</code></pre>'
            elif tag == 'DATASET' or tag == 'TABLE':
                raw_text = self._get_raw_text(node).strip()
                return self._render_table(raw_text)
            elif tag == 'SCRATCH':
                from .scratch import scratch_embed_html
                return scratch_embed_html(self._get_raw_text(node), node.line, self.errors)
            elif tag == 'BLOCKS':
                from .scratch import blocks_html
                return blocks_html(self._get_raw_text(node))
            elif tag == 'SPRITE':
                from .scratch import sprite_html
                return sprite_html(self._get_raw_text(node))

            # --- Exercise Blocks ---
            elif tag == 'TASKS':
                return f'<div class="tc-tasks">\n{inner_html}\n</div>'
            elif tag == 'TASK':
                inner_html = self._strip_outer_p(inner_html)
                return f'<div class="tc-task">{inner_html}</div>'
            elif tag == 'HINT':
                return f'<div class="tc-hint"><strong>Hint:</strong><br>{inner_html}</div>'
            elif tag == 'EXPECTED':
                return f'<div class="tc-expected"><strong>Expected Output:</strong><br>{inner_html}</div>'

            # --- Project Blocks ---
            elif tag == 'DESCRIPTION':
                return f'<div class="tc-description"><strong>Description:</strong><br>{inner_html}</div>'
            elif tag == 'REQUIREMENTS':
                return f'<div class="tc-requirements">\n<strong>Requirements:</strong><br>\n{inner_html}\n</div>'
            elif tag == 'REQUIREMENT':
                inner_html = self._strip_outer_p(inner_html)
                return f'<div class="tc-requirement">• {inner_html}</div>'
            elif tag == 'OUTPUT':
                return f'<div class="tc-output"><strong>Output:</strong><br>{inner_html}</div>'
            elif tag == 'RUBRIC':
                return f'<div class="tc-rubric">\n<strong>Rubric:</strong><br>\n{inner_html}\n</div>'
            elif tag == 'CRITERIA':
                inner_html = self._strip_outer_p(inner_html)
                return f'<div class="tc-criteria">{inner_html}</div>'

            else:
                self.errors.append({"line": node.line, "message": f"Unknown tag: [{node.tag}]"})
                return inner_html

        return ""
