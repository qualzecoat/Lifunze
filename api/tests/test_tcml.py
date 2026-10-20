import unittest
from app.tcml import parse_material, parse_quiz_mcq, parse_quiz_text

class TestParsers(unittest.TestCase):
    def test_parse_material(self):
        raw_text = """JUDUL: Pengenalan Aljabar Dasar
TUJUAN: Siswa mampu memahami konsep variabel dan persamaan sederhana
MATERI: Aljabar adalah cabang matematika yang menggunakan simbol/huruf untuk mewakili angka...
CONTOH: 2x + 3 = 7, maka x = 2"""
        html = parse_material(raw_text)['content']
        self.assertIn('<h2 class="material-judul">Pengenalan Aljabar Dasar</h2>', html)
        self.assertIn('<div class="material-tujuan"><strong>Tujuan:</strong><br>Siswa mampu memahami konsep variabel dan persamaan sederhana</div>', html)
        self.assertIn('Aljabar adalah cabang matematika', html)
        self.assertIn('<div class="material-contoh"><strong>Contoh:</strong><br>2x + 3 = 7, maka x = 2</div>', html)

    def test_parse_quiz_mcq(self):
        raw_text = """SOAL 1
Apa ibu kota Indonesia?
A. Bandung
B. Jakarta
C. Surabaya
D. Medan
JAWABAN: B
SOAL 2
Planet tempat kita tinggal adalah?
A. Mars
B. Venus
C. Bumi
D. Jupiter
JAWABAN: C"""
        questions = parse_quiz_mcq(raw_text)['content']
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]['pertanyaan'], 'Apa ibu kota Indonesia?')
        self.assertEqual(questions[0]['opsi_b'], 'Jakarta')
        self.assertEqual(questions[0]['jawaban_benar'], 'B')

        self.assertEqual(questions[1]['pertanyaan'], 'Planet tempat kita tinggal adalah?')
        self.assertEqual(questions[1]['jawaban_benar'], 'C')

    def test_parse_quiz_text(self):
        raw_text = """SOAL 1
Jelaskan proses fotosintesis!
SOAL 2
Sebutkan 3 ciri makhluk hidup."""
        questions = parse_quiz_text(raw_text)['content']
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]['pertanyaan'], 'Jelaskan proses fotosintesis!')
        self.assertEqual(questions[1]['pertanyaan'], 'Sebutkan 3 ciri makhluk hidup.')


    def test_new_material_parser(self):
        text = """[MATERIAL]
[TITLE]Excel Basics[/TITLE]
[HEADING]1. Intro[/HEADING]
[PARAGRAPH]
Welcome to Excel.

It is great.
[/PARAGRAPH]
[NOTE]Do not forget to save.[/NOTE]
[DATASET]
Name | Age
Alice | 20
Bob | 22
[/DATASET]
[/MATERIAL]"""
        res = parse_material(text)
        self.assertTrue(res['success'])
        self.assertEqual(len(res['errors']), 0)

        html = res['content']
        self.assertIn('<h1 class="tc-title">Excel Basics</h1>', html)
        self.assertIn('<h2 class="tc-heading">1. Intro</h2>', html)
        self.assertIn('<p>Welcome to Excel.</p>', html)
        self.assertIn('<p>It is great.</p>', html)
        self.assertIn('<div class="tc-note"><strong>Note:</strong><br><p>Do not forget to save.</p></div>', html)
        self.assertIn('<table class="tc-table">', html)
        self.assertIn('<th>Age</th>', html)
        self.assertIn('<td>20</td>', html)

    def test_new_material_parser_errors(self):
        text = """[MATERIAL]
[TITLE]Missing closing tag
[PARAGRAPH]Text[/PARAGRAPH]
[/MATERIAL]"""
        res = parse_material(text)
        self.assertFalse(res['success'])
        self.assertTrue(any('Missing closing tag for [TITLE]' in e['message'] for e in res['errors']))

        text2 = """[MATERIAL]
[UNKNOWN]Foo[/UNKNOWN]
[/MATERIAL]"""
        res2 = parse_material(text2)
        self.assertFalse(res2['success'])
        self.assertTrue(any('Unknown tag: [UNKNOWN]' in e['message'] for e in res2['errors']))

    def test_new_quiz_parser_mcq(self):
        text = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]What is 2+2?[/QUESTION]
[OPTIONS]
A. 1
B. 2
C. 3
D. 4
[/OPTIONS]
[ANSWER]D[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""
        res = parse_quiz_mcq(text)
        self.assertTrue(res['success'])
        self.assertEqual(len(res['errors']), 0)
        questions = res['content']
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['pertanyaan'], 'What is 2+2?')
        self.assertEqual(questions[0]['opsi_a'], '1')
        self.assertEqual(questions[0]['jawaban_benar'], 'D')

    def test_new_quiz_parser_mcq_type_mismatch(self):
        text = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Explain.[/QUESTION]
[/QUESTION 1]
[/QUIZ]"""
        res = parse_quiz_mcq(text)
        self.assertFalse(res['success'])
        self.assertTrue(any('Quiz type mismatch' in e['message'] for e in res['errors']))

    def test_xss_protection(self):
        text = """[MATERIAL]
[PARAGRAPH]
<script>alert('xss')</script>
[/PARAGRAPH]
[CODE]<img src="x" onerror="alert(1)">[/CODE]
[/MATERIAL]"""
        res = parse_material(text)
        html = res['content']
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<img src="x" onerror="alert(1)">', html)
        self.assertIn('&lt;img src=&#34;x&#34; onerror=&#34;alert(1)&#34;&gt;', html)

if __name__ == '__main__':
    unittest.main()
