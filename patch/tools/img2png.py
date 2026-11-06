"""Convert the game's 8-bit images (9-byte header + w*h pixels) and PCX screens to PNG."""
import os, sys, struct
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grimtool as g


def palette(b, keys):
    e = [e for e in b.entries if e['name'] == 'TRUERGB.PAL'][0]
    p = g.xor(b.raw(e), keys[e['size'] % 4])
    return [min(255, c * 255 // 63) for c in p[:768]]


def decode(raw, keys, xor=True):
    d = g.xor(raw, keys[len(raw) % 4]) if xor else raw
    w, h = struct.unpack_from('<HH', d, 0)
    if len(d) == w * h + 9:
        return w, h, d[9:]
    return None


def to_png(w, h, px, pal, path, flip=False):
    im = Image.frombytes('P', (w, h), bytes(px))
    im.putpalette(pal)
    if flip:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    im.convert('RGB').save(path)


if __name__ == '__main__':
    game, out = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    keys = g.load_keys(os.path.join(game, 'Grimoire.exe'))
    b = g.Bundle(os.path.join(game, '_jp_work', 'backup', 'BUNDLE-Z.RSF.orig'))
    pal = palette(b, keys)
    os.makedirs(out, exist_ok=True)
    n = 0
    for e in b.entries:
        if names and e['name'] not in names and e['type'] not in names:
            continue
        if not e['name'].endswith('.BMP'):
            continue
        r = decode(b.raw(e), keys)
        if not r:
            continue
        w, h, px = r
        os.makedirs(os.path.join(out, e['type']), exist_ok=True)
        to_png(w, h, px, pal, os.path.join(out, e['type'], e['name'][:-4] + '.png'), flip=True)
        n += 1
    print(n, 'images ->', out)
