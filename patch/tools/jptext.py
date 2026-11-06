"""Helpers for Japanese text in the game's byte strings.

softbreak(s): the game word-wraps long strings only at ASCII spaces. Japanese has no spaces, so we
put a ' ' at every position where a line break is allowed (between two non-ASCII characters,
respecting basic kinsoku rules). The jp DLL draws a space between two non-ASCII characters with
zero width, so these spaces are invisible.
Only strings wider than SOFT_MIN_WIDTH get them: pre-wrapped lines (about 35 columns) are left alone.
"""
import unicodedata

SOFT_MIN_WIDTH = 40
NO_START = set('、。，．・：；？！ー～…‥」』）］｝〕〉》】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々ゝゞヽヾ'
               '!?)]},.:;')
NO_END = set('「『（［｛〔〈《【')


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in 'WFA' and ord(ch) > 0x7F else 1 for ch in s)


def softbreak(s):
    if width(s) <= SOFT_MIN_WIDTH or not any(ord(c) > 0x7F for c in s):
        return s
    out = []
    for i, ch in enumerate(s):
        if i and ord(ch) > 0x7F and ord(s[i - 1]) > 0x7F and ch != '　' and s[i - 1] != '　' \
                and ch not in NO_START and s[i - 1] not in NO_END:
            out.append(' ')
        out.append(ch)
    return ''.join(out)


def unsoft(s):
    """Inverse of softbreak (for display / re-export)."""
    out = []
    for i, ch in enumerate(s):
        if ch == ' ' and 0 < i < len(s) - 1 and ord(s[i - 1]) > 0x7F and ord(s[i + 1]) > 0x7F:
            continue
        out.append(ch)
    return ''.join(out)


if __name__ == '__main__':
    t = 'この呪文を唱えると、魔物の頭上に煮えたぎる酸の雲が現れ、威力の段階ごとに2D8の損害を与える。「雲」の強さは毎回半分になる。'
    print(softbreak(t))
    assert unsoft(softbreak(t)) == t
