"""Tiny-pixel Japanese lettering for paletted images: Misaki Gothic 8x8 (dll/fonts/misaki8.bin),
plus simple in-painting to remove old lettering drawn over a picture.

  glyphs(text) -> (set of (x, y) pixels, width, height)        8px font, optional integer scale
  draw(im, x, y, text, fill, outline=None, shadow=None, scale=1)
  inpaint(im, pixels)                                          fill pixels from their neighbours
  nearest(im, rgb)                                             palette index closest to an RGB colour
"""
import collections, os, struct

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dll', 'fonts', 'misaki8.bin')
_G = None


def _load():
    global _G
    if _G is None:
        d = open(FONT, 'rb').read()
        n = struct.unpack('<I', d[4:8])[0]
        _G, o = {}, 8
        for _ in range(n):
            cp, adv = struct.unpack('<IB', d[o:o + 5])
            _G[cp] = (adv, d[o + 5:o + 13])
            o += 13
    return _G


def glyphs(text, scale=1):
    g = _load()
    pts, x = set(), 0
    for ch in text:
        adv, rows = g.get(ord(ch), g[ord('?')])
        for y, r in enumerate(rows):
            for b in range(8):
                if r & (0x80 >> b):
                    for sy in range(scale):
                        for sx in range(scale):
                            pts.add((x + b * scale + sx, y * scale + sy))
        x += adv * scale
    if not pts:
        return pts, 0, 0
    w = max(p[0] for p in pts) + 1
    h = max(p[1] for p in pts) + 1
    return pts, w, h


def draw(im, x, y, text, fill, outline=None, shadow=None, scale=1):
    pts, w, h = glyphs(text, scale)
    p = im.load()
    W, H = im.size
    if outline is not None:
        ring = {(a + dx, b + dy) for a, b in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts
        for a, b in ring:
            if 0 <= x + a < W and 0 <= y + b < H:
                p[x + a, y + b] = outline
    if shadow is not None:
        for a, b in pts:
            if (a + 1, b + 1) not in pts and 0 <= x + a + 1 < W and 0 <= y + b + 1 < H:
                p[x + a + 1, y + b + 1] = shadow
    for a, b in pts:
        if 0 <= x + a < W and 0 <= y + b < H:
            p[x + a, y + b] = fill
    return w, h


def inpaint(im, pixels):
    """Replace the given pixels with the most common colour of their already-known 8-neighbours."""
    p = im.load()
    W, H = im.size
    todo = set(pixels)
    while todo:
        done = {}
        for x, y in todo:
            c = collections.Counter(p[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                    if (dx or dy) and 0 <= x + dx < W and 0 <= y + dy < H
                                    and (x + dx, y + dy) not in todo)
            if c:
                done[(x, y)] = c.most_common(1)[0][0]
        if not done:
            break
        for (x, y), v in done.items():
            p[x, y] = v
        todo -= set(done)


def nearest(im, rgb):
    pal = im.getpalette()
    used = set(im.getdata())
    return min(used, key=lambda i: sum((pal[i * 3 + k] - rgb[k]) ** 2 for k in range(3)))
