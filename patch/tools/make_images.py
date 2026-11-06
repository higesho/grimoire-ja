"""Redraw the English lettering of the GUI / help images in Japanese (uses retitle.py).

  python tools/make_images.py <patch_dir>      writes <patch_dir>/IMG/<type>/<name>.png

Boxes are the pixel boxes of the original lettering (x0 y0 x1 y1, inclusive), found by colour
and checked by eye. Two-line labels are two boxes. Images left in English on purpose:
GUI012/013 (ENTER key), GUI028 (no text), GUI057 (NEW over a picture), GUI058 (vertical NPC),
GUI111 (tarot names, 8px), MOUSE23 (7px), SCENE17/18/70 (flyers full of small text).
"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retitle import retitle

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'extracted', 'IMG')

KEYCUTS = [
    ((726, 9, 788, 22), '左へ'), ((730, 28, 784, 41), '横移動'),
    ((279, 11, 341, 24), 'ゲーム'), ((279, 30, 341, 43), 'メニュー'),
    ((104, 24, 159, 37), 'ヘルプ'),
    ((393, 32, 560, 46), '設定'),
    ((168, 37, 222, 50), '休息'),
    ((320, 50, 383, 64), 'クイック'), ((324, 68, 378, 81), 'セーブ'),
    ((198, 61, 301, 75), '自動地図'),
    ((699, 65, 761, 78), '右へ'), ((699, 84, 761, 97), '横移動'),
    ((353, 86, 416, 100), 'クイック'), ((353, 104, 415, 117), 'マーク'),
    ((538, 86, 628, 100), 'バージョン'),
    ((220, 91, 315, 104), '日誌'),
    ((11, 109, 107, 123), 'コンソール'),
    ((390, 121, 453, 135), 'クイック'), ((390, 139, 452, 152), '歩行'),
    ((121, 440, 245, 454), '移動'), ((156, 459, 211, 472), 'キー'),
    ((521, 470, 603, 484), '決定'),
    ((245, 481, 349, 495), '使用'),
    ((10, 499, 206, 513), '次の項目へ'),
    ((615, 534, 739, 548), '移動'), ((650, 553, 705, 566), 'キー'),
    ((229, 564, 597, 586), 'キーボード操作'),
]
KEYPAD = [
    ((335, 116, 396, 130), '前へ'), ((314, 135, 417, 148), '進む'),
    ((140, 158, 244, 172), '使用'),
    ((163, 283, 218, 297), '左を'), ((163, 302, 217, 315), '向く'),
    ((604, 284, 659, 298), '右を'), ((600, 303, 662, 316), '向く'),
    ((601, 335, 683, 349), '選択'), ((601, 354, 683, 367), '決定'),
    ((157, 445, 219, 459), '左へ'), ((161, 464, 215, 477), '横移動'),
    ((525, 453, 587, 467), '右へ'), ((525, 472, 587, 485), '横移動'),
    ((337, 460, 399, 474), '後ろへ'), ((310, 479, 427, 492), '下がる'),
    ((221, 562, 544, 584), 'テンキー操作'),
]
JOBS = {
    'GUI/GUI011': [((22, 13, 165, 28), '鑑　定')],
    'GUI/GUI060': [((1, 10, 88, 26), 'パワー'), ((9, 28, 87, 44), 'レベル')],
    'GUI/GUI051': [((0, 25, 63, 37), '削除')],
    'MIC/MOUSE19': [((1, 18, 30, 30), 'だれ')],
    'MIC/MOUSE20': [((1, 18, 30, 30), '列')],
    'MIC/MOUSE21': [((1, 18, 30, 30), '道具')],
    'MIC/MOUSE22': [((1, 18, 30, 30), '終了')],
    'HLP/KEYCUTS': KEYCUTS,
    'HLP/KEYPAD': KEYPAD,
}
COPY = {'GUI/GUI016': 'patch_imgtest/IMG/GUI/GUI016.png', 'GUI/GUI017': 'patch_imgtest/IMG/GUI/GUI017.png'}


def black_index(path):
    from PIL import Image
    im = Image.open(path)
    pal = im.getpalette()
    used = set(im.getdata())
    return min(used, key=lambda i: sum(pal[i * 3:i * 3 + 3]))


def main(patch):
    root = os.path.dirname(EX.rstrip('/\\').rsplit(os.sep, 1)[0]) if False else os.path.dirname(os.path.dirname(EX))
    for name, jobs in JOBS.items():
        dst = os.path.join(patch, 'IMG', name + '.png')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = os.path.join(EX, name + '.png')
        black = black_index(src)
        for box, text in jobs:
            retitle(src, dst, box, text, bg=black)   # erase with black (the lettering itself can be the most common colour)
            src = dst
    import make_images_small
    make_images_small.run(EX, patch)
    import make_flyers
    make_flyers.run(EX, patch)
    for name, path in COPY.items():
        dst = os.path.join(patch, 'IMG', name + '.png')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(root, path), dst)


if __name__ == '__main__':
    main(sys.argv[1])
