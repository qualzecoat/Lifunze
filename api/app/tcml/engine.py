# Engine TCML — API publik parser (porting 1:1 dari v1).
# Semua fungsi mengembalikan dict: {"success": bool, "content": ..., "errors": [{"line": int, "message": str}]}.
from .core import Tokenizer, ASTBuilder
from .legacy import legacy_parse_material, legacy_parse_quiz_mcq, legacy_parse_quiz_text
from .renderers import ExtendedMaterialRenderer, QuizRenderer

def parse_material(raw_text):
    if '[MATERIAL]' in raw_text or '[EXERCISE]' in raw_text or '[PROJECT]' in raw_text:
        tokens = Tokenizer(raw_text).tokenize()
        ast, ast_errors = ASTBuilder(tokens).build()

        # If it's a project or exercise, we might want to render them generically if they are the root.
        # But our MaterialRenderer expects [MATERIAL]. Let's make it handle [EXERCISE] and [PROJECT] too.
        # We'll update the renderer logic slightly below.

        renderer = ExtendedMaterialRenderer(ast)
        html = renderer.render()
        errors = ast_errors + renderer.errors

        return {
            "success": len(errors) == 0,
            "content": html,
            "errors": errors
        }
    else:
        # Fallback to legacy parser
        html = legacy_parse_material(raw_text)
        return {
            "success": True,
            "content": html,
            "errors": []
        }

def parse_quiz_mcq(raw_text):
    if '[QUIZ]' in raw_text:
        tokens = Tokenizer(raw_text).tokenize()
        ast, ast_errors = ASTBuilder(tokens).build()

        renderer = QuizRenderer(ast, 'pilihan_ganda')
        questions = renderer.render()
        errors = ast_errors + renderer.errors

        # We need to adapt the signature if we want to return structured results.
        # For legacy compatibility in app.py which expects a list directly for import_quiz/parse_quiz_raw,
        # we will check if the user of parse_quiz_mcq expects a list or a dict.
        # However, the prompt specifically says "Change the return signature of all parsers to a structured dictionary".
        # Let's do that and update app.py later. Wait, for `parse_quiz_mcq`, if we change the return signature, we MUST update app.py immediately.
        # Let's keep the return as dict for the final integration, but app.py needs updating.
        return {
            "success": len(errors) == 0,
            "content": questions,
            "errors": errors
        }
    else:
        questions = legacy_parse_quiz_mcq(raw_text)
        return {
            "success": True,
            "content": questions,
            "errors": []
        }

def parse_quiz_text(raw_text):
    if '[QUIZ]' in raw_text:
        tokens = Tokenizer(raw_text).tokenize()
        ast, ast_errors = ASTBuilder(tokens).build()

        renderer = QuizRenderer(ast, 'teks')
        questions = renderer.render()
        errors = ast_errors + renderer.errors

        return {
            "success": len(errors) == 0,
            "content": questions,
            "errors": errors
        }
    else:
        questions = legacy_parse_quiz_text(raw_text)
        return {
            "success": True,
            "content": questions,
            "errors": []
        }

