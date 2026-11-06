"""Small lettering redrawn with the 8px Misaki font (pixfont.py): tarot names (GUI111), the ITEM? cursor
(MOUSE23), the ENTER key buttons (GUI012/013) and the NEW badge (GUI057). Called from make_images.py."""
import os
from PIL import Image
from pixfont import draw, glyphs, inpaint, nearest

CW, CH = 34, 58          # tarot card cell in GUI111 (10 x 8 cards)
MAJOR = [  # (col, row, name) : white strip at card rows 49..55, x 2..31
    (2, 0, '愚者'), (3, 0, '魔術師'), (4, 0, '女教皇'), (5, 0, '女帝'), (6, 0, '皇帝'), (7, 0, '教皇'),
    (8, 0, '恋人'), (9, 0, '戦車'),
    (0, 1, '力'), (1, 1, '隠者'), (2, 1, '運命の輪'), (3, 1, '正義'), (4, 1, '刑死者'), (5, 1, '死神'),
    (6, 1, '節制'), (7, 1, '悪魔'), (8, 1, '塔'), (9, 1, '星'),
    (0, 2, '月'), (1, 2, '太陽'), (2, 2, '審判'), (3, 2, '世界'),
]
COURT = {'ACE': 'エース', 'KING': '王', 'KNIGHT': '騎士', 'PAGE': '小姓', 'QUEEN': '女王'}
MINOR = [  # (col, row, label) : white letters with a black edge drawn over the picture, card rows 47..55
    (3, 3, 'ACE'), (4, 3, 'KING'), (5, 3, 'KNIGHT'), (6, 3, 'PAGE'), (7, 3, 'QUEEN'),
    (7, 4, 'ACE'), (8, 4, 'KING'), (9, 4, 'KNIGHT'), (0, 5, 'PAGE'), (1, 5, 'QUEEN'),
    (1, 6, 'ACE'), (2, 6, 'KING'), (3, 6, 'KNIGHT'), (4, 6, 'PAGE'), (5, 6, 'QUEEN'),
    (5, 7, 'ACE'), (6, 7, 'KING'), (7, 7, 'KNIGHT'), (8, 7, 'PAGE'), (9, 7, 'QUEEN'),
]


def tarot(src, dst):
    im = Image.open(src)
    p, rgb = im.load(), im.convert('RGB').load()
    white, black, red = nearest(im, (255, 255, 255)), nearest(im, (0, 0, 0)), nearest(im, (230, 30, 30))
    for c, r, name in MAJOR:
        x0, y0 = c * CW, r * CH
        for y in range(y0 + 49, y0 + 56):
            for x in range(x0 + 2, x0 + 32):
                p[x, y] = white
        _, w, h = glyphs(name)
        if w > 30:   # 4 characters: use the strip's black side columns too
            for y in range(y0 + 49, y0 + 56):
                p[x0 + 1, y] = p[x0 + 32, y] = white
        tx = x0 + 17 - (w + 1) // 2
        draw(im, tx, y0 + 49, name[0], red)
        draw(im, tx + glyphs(name[0])[1] + 1, y0 + 49, name[1:], black) if len(name) > 1 else None
    for c, r, lab in MINOR:
        x0, y0 = c * CW, r * CH
        whites = [(x, y) for y in range(y0 + 47, y0 + 56) for x in range(x0 + 2, x0 + 32) if sum(rgb[x, y]) > 600]
        if whites:
            xa, xb = min(x for x, _ in whites) - 1, max(x for x, _ in whites) + 1
            mask = [(x, y) for y in range(y0 + 47, y0 + 56) for x in range(xa, xb + 1)
                    if sum(rgb[x, y]) > 600 or sum(rgb[x, y]) < 90]
            inpaint(im, mask)
        name = COURT[lab]
        _, w, h = glyphs(name)
        draw(im, x0 + 17 - w // 2, y0 + 47, name, white, outline=black)
    im.save(dst)


def mouse23(src, dst):
    im = Image.open(src)
    p = im.load()
    black, red, yellow = nearest(im, (0, 0, 0)), nearest(im, (230, 0, 0)), nearest(im, (255, 230, 0))
    for y in range(21, 32):
        for x in range(0, 32):
            p[x, y] = black
    _, w, h = glyphs('道具？')
    draw(im, 16 - w // 2, 23, '道具？', red, outline=yellow)
    im.save(dst)


def enter(src, dst, dark):
    im = Image.open(src)
    p = im.load()
    rgb = im.convert('RGB').load()
    # lettering box of "ENTER" on the key face (the return arrow at the right is kept)
    face = nearest(im, (240, 180, 0))
    col = nearest(im, (40, 20, 0)) if dark else nearest(im, (220, 0, 0))
    for y in range(17, 24):          # letters are at x 5..24, y 18..22; the return arrow head starts at y 24
        for x in range(4, 26):
            p[x, y] = face
    _, w, h = glyphs('決定')
    draw(im, 15 - w // 2, 17, '決定', col)
    im.save(dst)


def new_badge(src, dst):
    im = Image.open(src)
    rgb = im.convert('RGB').load()
    W, H = im.size
    red, yellow = nearest(im, (230, 0, 0)), nearest(im, (255, 230, 0))
    # old letters: saturated red / yellow pixels in the band
    mask = [(x, y) for y in range(6, 23) for x in range(W)
            if (rgb[x, y][0] > 170 and rgb[x, y][2] < 90)]
    inpaint(im, mask)
    _, w, h = glyphs('新規', 2)
    draw(im, 16 - w // 2, 7, '新規', red, outline=yellow, scale=2)
    im.save(dst)


def run(ex, patch):
    def io(name):
        dst = os.path.join(patch, 'IMG', name + '.png')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        return os.path.join(ex, name + '.png'), dst
    tarot(*io('GUI/GUI111'))
    mouse23(*io('MIC/MOUSE23'))
    enter(*io('GUI/GUI012'), dark=False)
    enter(*io('GUI/GUI013'), dark=True)
    new_badge(*io('GUI/GUI057'))
