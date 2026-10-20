# TCML core — Tokenizer + AST builder (porting 1:1 dari Tenebris-Class v1, parsers.py).
# Inti ini TIDAK tahu tag spesifik apapun: hanya struktur buka/tutup tag, nesting, dan error per baris.
import re

class Token:
    def __init__(self, type, value, line):
        self.type = type
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value}, line={self.line})"

class Tokenizer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.tokens = []

    def tokenize(self):
        lines = self.text.split('\n')

        for i, line in enumerate(lines):
            self.line = i + 1
            # We need to find tags like [TAG] and [/TAG]
            # Since tags are usually on their own lines or wrapping text, we use regex to find all tags
            # A simple way is to tokenize line by line, splitting by tags

            # Find all tag matches in the line
            pattern = re.compile(r'(\[/?(?:[A-Z0-9_]+\s?[A-Z0-9_]*)\])')
            parts = pattern.split(line)

            for part in parts:
                if not part:
                    continue
                if part.startswith('[/') and part.endswith(']'):
                    tag_name = part[2:-1].strip()
                    self.tokens.append(Token('CLOSE_TAG', tag_name, self.line))
                elif part.startswith('[') and part.endswith(']'):
                    tag_name = part[1:-1].strip()
                    self.tokens.append(Token('OPEN_TAG', tag_name, self.line))
                else:
                    # It's text. Let's only add if it's not purely empty when stripped,
                    # OR if we want to preserve whitespace, we should add it all.
                    # Wait, preserving paragraph breaks is important. We will add text tokens verbatim.
                    self.tokens.append(Token('TEXT', part, self.line))

            # Add a newline token to preserve line breaks for paragraphs, unless it's the last line
            if i < len(lines) - 1:
                self.tokens.append(Token('NEWLINE', '\n', self.line))

        # Cleanup: merge consecutive TEXT and NEWLINE tokens into single TEXT tokens to make AST building easier
        cleaned_tokens = []
        current_text = []
        current_line = 1

        for token in self.tokens:
            if token.type in ('TEXT', 'NEWLINE'):
                current_text.append(token.value)
                current_line = token.line
            else:
                if current_text:
                    merged_text = ''.join(current_text)
                    if merged_text.strip(): # keep only if it has some non-whitespace OR if we strictly want all? We must keep paragraph structure. Let's keep all and trim later.
                        cleaned_tokens.append(Token('TEXT', merged_text, current_line))
                    current_text = []
                cleaned_tokens.append(token)

        if current_text:
            merged_text = ''.join(current_text)
            if merged_text.strip():
                cleaned_tokens.append(Token('TEXT', merged_text, current_line))

        return cleaned_tokens


class BlockNode:
    def __init__(self, tag, line):
        self.tag = tag
        self.line = line
        self.children = []

    def __repr__(self):
        return f"BlockNode({self.tag}, children={len(self.children)})"

class TextNode:
    def __init__(self, text, line):
        self.text = text
        self.line = line

    def __repr__(self):
        return f"TextNode({repr(self.text)})"

class ASTBuilder:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errors = []

    def build(self):
        root = BlockNode('ROOT', 0)
        stack = [root]

        for token in self.tokens:
            if token.type == 'OPEN_TAG':
                node = BlockNode(token.value, token.line)
                stack[-1].children.append(node)
                stack.append(node)
            elif token.type == 'CLOSE_TAG':
                if len(stack) > 1:
                    if stack[-1].tag == token.value:
                        stack.pop()
                    else:
                        self.errors.append({
                            'line': token.line,
                            'message': f"Mismatched closing tag. Expected [/{stack[-1].tag}], found [/{token.value}]."
                        })
                        # Heuristic recovery: just ignore the bad closing tag and keep the block open
                else:
                    self.errors.append({
                        'line': token.line,
                        'message': f"Unexpected closing tag [/{token.value}] without matching opening tag."
                    })
            elif token.type == 'TEXT':
                # Strip leading/trailing whitespace strictly for purely empty nodes, but keep inner newlines.
                # Actually, we should just append it.
                stack[-1].children.append(TextNode(token.value, token.line))

        if len(stack) > 1:
            for unclosed in reversed(stack[1:]):
                self.errors.append({
                    'line': unclosed.line,
                    'message': f"Missing closing tag for [{unclosed.tag}]."
                })

        return root, self.errors

