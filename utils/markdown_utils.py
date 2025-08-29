import re
from typing import List

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')

def _parse_markdown(md_text: str):
    lines = md_text.splitlines()
    segments = []
    stack: List[tuple[int, str]] = []
    current = None
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if current:
                segments.append(current)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = {"path": [t for _, t in stack], "content": []}
        else:
            if current is None:
                continue
            current["content"].append(line)
    if current:
        segments.append(current)
    return segments

def _binary_split(text: str, max_len: int) -> List[str]:
    text = text.strip()
    if max_len <= 0 or len(text) <= max_len:
        return [text]
    mid = len(text) // 2
    return _binary_split(text[:mid], max_len) + _binary_split(text[mid:], max_len)

def split_markdown(md_text: str, max_len: int) -> List[str]:
    segments = _parse_markdown(md_text)
    chunks: List[str] = []
    for seg in segments:
        base = "\n".join(seg["path"]).strip()
        body = "\n".join(seg["content"]).strip()
        if not base and not body:
            continue
        prefix = base + ("\n" if body else "")
        total = prefix + body
        if max_len > 0 and len(total) > max_len:
            for part in _binary_split(body, max_len - len(prefix)):
                chunks.append(prefix + part)
        else:
            chunks.append(total)
    return [c for c in chunks if c.strip()]

def binary_split(text: str, max_len: int) -> List[str]:
    return _binary_split(text, max_len)
