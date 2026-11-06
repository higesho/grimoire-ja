"""Replace the lettering of a heading/button image with Japanese text, keeping the
original per-row colour gradient. Works on the paletted PNGs from imgtool.py export.

  python retitle.py <in.png> <out.png> <x0> <y0> <x1> <y1> <text> [font] [px] [bg_index]

  x0..x1 / y0..y1 : box that contains the original lettering (inclusive)
  font            : TrueType font (default BIZ UDGothic Bold)
  px              : text height in pixels (default: box height)
  bg_index        : palette index used to erase the box (default: most common index in the box)
"""
import sys, collections
from PIL import Image, ImageDraw, ImageFont

FONT = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
STYLE = 'shadow'   # 'shadow' (1px drop shadow, keeps glyphs large) or 'outline' (1px edge)


def retitle(src, dst, box, text, font=FONT, px=None, bg=None):
    im = Image.open(src)
    assert im.mode == 'P', 'use the paletted PNG exported by imgtool.py'
    x0, y0, x1, y1 = box
    p = im.load()
    cnt = collections.Counter(p[x, y] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    if bg is None:
        bg = cnt.most_common(1)[0][0]
    # colour of the lettering on each row (most common non-background index)
    row_col = {}
    for y in range(y0, y1 + 1):
        c = collections.Counter(p[x, y] for x in range(x0, x1 + 1) if p[x, y] != bg)
        row_col[y] = c.most_common(1)[0][0] if c else None
    fallback = collections.Counter(v for v in row_col.values() if v is not None).most_common(1)[0][0]
    # colour of the lettering's edge (letter pixels touching the background)
    edge = collections.Counter()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if p[x, y] != bg and any(p[x + dx, y + dy] == bg for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                     if x0 <= x + dx <= x1 and y0 <= y + dy <= y1):
                edge[p[x, y]] += 1
    edge_col = edge.most_common(1)[0][0] if edge else fallback
    # darkest colour used by the lettering, for the drop shadow
    pal = im.getpalette()
    used = set(v for v in row_col.values() if v is not None) | set(edge)
    shadow_col = min(used, key=lambda i: sum(pal[i * 3:i * 3 + 3]))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            p[x, y] = bg
    # render text (no anti-aliasing), shrink until it fits the box
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    size = px or bh
    while True:
        f = ImageFont.truetype(font, size)
        outer = Image.new('1', (bw * 3, bh * 3), 0)      # text + 1px stroke
        inner = Image.new('1', (bw * 3, bh * 3), 0)      # text
        for img, sw, off in ((outer, 1 if STYLE == 'outline' else 0, 0 if STYLE == 'outline' else 1), (inner, 0, 0)):
            d = ImageDraw.Draw(img)
            d.fontmode = '1'
            d.text((2, 2), text, font=f, fill=1, stroke_width=sw, stroke_fill=1)
            if off:   # shadow: text shifted right/down by 1px, merged with the text
                d.text((2 + off, 2 + off), text, font=f, fill=1)
        bb = outer.getbbox()
        if bb is None:
            raise ValueError('empty text')
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if (tw <= bw and th <= bh) or size <= 6:
            break
        size -= 1
    outer, inner = outer.crop(bb), inner.crop(bb)
    ox = x0 + (bw - tw) // 2
    oy = y0 + (bh - th) // 2
    om, im_ = outer.load(), inner.load()
    for y in range(th):
        col = row_col.get(oy + y) or fallback
        for x in range(tw):
            if im_[x, y]:
                p[ox + x, oy + y] = col
            elif om[x, y]:
                p[ox + x, oy + y] = edge_col if STYLE == 'outline' else shadow_col
    im.save(dst)
    print(f'{dst}: "{text}" {size}px at ({ox},{oy}) {tw}x{th}, bg={bg}')


if __name__ == '__main__':
    a = sys.argv
    retitle(a[1], a[2], tuple(int(v) for v in a[3:7]), a[7],
            a[8] if len(a) > 8 else FONT, int(a[9]) if len(a) > 9 else None,
            int(a[10]) if len(a) > 10 else None)
