"""Japanese versions of the three flyers (SCN/SCENE17 HAVOC SEED, SCENE18 METRONOME MYSTERIUM,
SCENE70 HAVE YOU SEEN THIS BABY?). For each text block: remove the old ink by in-painting the paper,
then draw the Japanese lines (no anti-aliasing) centred in the block. Called from make_images.py."""
import os
from PIL import Image, ImageDraw, ImageFont
from pixfont import inpaint, nearest

GOTHIC = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'

DARK = lambda c: sum(c) < 540
RED_ON_YELLOW = lambda c: c[0] > 140 and c[1] < 150 and c[2] < 120
RED_INK = lambda c: (c[0] - c[1] > 45) or sum(c) < 330

# block: (box x0 y0 x1 y1, ink test, [lines], fill rgb, outline rgb or None, max px)
FLYERS = {
    'SCN/SCENE17': [
        ((44, 14, 505, 74), DARK, ['平和と繁栄は', '惑星の成長を妨げる！'], (40, 25, 20), None, 22),
        ((96, 76, 505, 132), DARK, ['戦争と混沌こそが', '雇用と革新を生む！'], (40, 25, 20), None, 22),
        ((100, 142, 452, 206), DARK, ['災厄の種'], (20, 10, 10), None, 52),
        ((22, 262, 440, 387), DARK, ['あなたの世界のどこに埋めても', '火花が飛び散る！', '＊内戦と種族間の暴力！',
                                    '＊領土と資源をめぐる刺激的な争奪戦！', '＊言葉も文化も通じ合わない',
                                    '　バベルの塔の食べ放題！'], (40, 25, 20), None, 18),
        ((444, 330, 538, 392), DARK, ['今すぐ', 'お電話を！', '係員が', '待機中'], (40, 25, 20), None, 12),
        ((50, 390, 505, 434), DARK, ['「多文化オーブ」や「多様性の錠剤」のような安物の粗悪な',
                                    '模倣品にご注意を。正真正銘・特許取得の',
                                    'リアリティ・ハイジンクス製品だけをお選びください！'], (40, 25, 20), None, 12),
        ((0, 78, 97, 188), RED_ON_YELLOW, ['わお！', 'これは', 'ひとつ', '買わねば！', '―梟'], (210, 20, 20), None, 14),
    ],
    'SCN/SCENE18': [
        ((40, 20, 505, 66), DARK, ['あなたの惑星は争いに苦しんでいませんか？', '住民たちの果てしない戦争と'], (40, 25, 20), None, 18),
        ((58, 68, 484, 89), DARK, ['蛮行を見るのに'], (40, 25, 20), None, 18),
        ((84, 92, 470, 114), DARK, ['うんざりしていませんか？'], (40, 25, 20), None, 18),
        ((85, 117, 455, 138), DARK, ['そろそろ導入してみては――'], (40, 25, 20), None, 18),
        ((105, 147, 432, 232), DARK, ['メトロノーム', 'ミステリウム'], (20, 10, 10), None, 36),
        ((68, 234, 452, 384), DARK, ['宇宙中で話題沸騰！', '驚異の低周波エーテル', '慈愛放射装置！',
                                    '面倒なし・手間なし・嫌なにおいなし！', 'お手頃・静か・お手入れ簡単！'], (20, 10, 10), None, 24),
        ((445, 318, 482, 352), DARK, [], None, None, 0),
        ((56, 318, 74, 352), DARK, [], None, None, 0),
        ((74, 387, 446, 438), DARK, ['警告：時計を定期的に巻き戻さないと保証は無効となり、',
                                    'ヌル空間の悪魔の恐ろしい襲来を招いて',
                                    '土着の有機生命がすべて滅びるおそれがあります'], (40, 25, 20), None, 12),
        ((447, 350, 539, 434), RED_ON_YELLOW, ['こいつを', '買うには', '宇宙人の', '高利貸しと', '話をつけねば', '―梟'], (210, 20, 20), None, 11),
    ],
    'SCN/SCENE70': [
        ((38, 4, 502, 102), RED_INK, ['この赤ん坊を', '見かけませんでしたか？'], (200, 50, 50), (70, 25, 20), 40),
        ((38, 104, 502, 160), RED_INK, ['危険につき', '近づかないこと！'], (200, 50, 50), (70, 25, 20), 22),
        ((38, 286, 502, 436), RED_INK, ['ヴァンガードは、', '巨大なクリーム菓子で', '我らの前哨基地を破壊した件で',
                                     'この者と話がしたい'], (200, 50, 50), (70, 25, 20), 28),
    ],
}


def render_lines(lines, px):
    f = ImageFont.truetype(GOTHIC, px)
    out = []
    for t in lines:
        img = Image.new('1', (px * len(t) * 2 + 8, px * 2), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = '1'
        d.text((2, 2), t, font=f, fill=1)
        bb = img.getbbox()
        out.append(img.crop(bb) if bb else img.crop((0, 0, 1, 1)))
    return out


def block(im, box, ink, lines, fill, outline, maxpx):
    x0, y0, x1, y1 = box
    rgb = im.convert('RGB').load()
    W, H = im.size
    core = {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if ink(rgb[x, y])}
    mask = {(x + dx, y + dy) for x, y in core for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
            if x0 <= x + dx <= x1 and y0 <= y + dy <= y1}
    inpaint(im, mask)
    if not lines:          # erase only
        return 0
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    pad = 2 if outline else 0
    for px in range(maxpx, 7, -1):
        imgs = render_lines(lines, px)
        gap = max(2, px // 4)
        th = sum(i.height + pad for i in imgs) + gap * (len(imgs) - 1)
        if th <= bh and max(i.width + pad for i in imgs) <= bw:
            break
    fi = nearest(im, fill)
    oi = nearest(im, outline) if outline else None
    p = im.load()
    y = y0 + (bh - th) // 2
    for img in imgs:
        x = x0 + (bw - img.width) // 2
        g = img.load()
        pts = {(a, b) for b in range(img.height) for a in range(img.width) if g[a, b]}
        if oi is not None:
            for a, b in {(a + dx, b + dy) for a, b in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts:
                if 0 <= x + a < W and 0 <= y + b < H:
                    p[x + a, y + b] = oi
        for a, b in pts:
            p[x + a, y + b] = fi
        y += img.height + pad + gap
    return px


def run(ex, patch):
    for name, blocks in FLYERS.items():
        im = Image.open(os.path.join(ex, name + '.png'))
        for args in blocks:
            block(im, *args)
        dst = os.path.join(patch, 'IMG', name + '.png')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst)
