import html
import re


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text):
    if text is None:
        return ""
    unescaped = html.unescape(str(text))
    return _TAG_RE.sub("", unescaped).strip()
