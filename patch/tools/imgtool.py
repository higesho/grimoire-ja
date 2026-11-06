"""Image conversion for Grimoire's 8-bit bitmaps (*.BMP resources).

Game format (after XOR decryption): u16 width, u16 height, 5 zero bytes, then width*height
palette indices, BOTTOM row first. Palette: TRUERGB.PAL (256 x RGB, 6-bit components).

  python imgtool.py export <Grimoire.exe> <orig.RSF> <out_dir> [NAME.BMP|TYPE ...]
      -> <out_dir>/<TYPE>/<NAME>.png  (paletted PNG, top row first)
  python imgtool.py check  <Grimoire.exe> <orig.RSF>
      -> export + re-encode every image in memory and compare with the original bytes

Edited PNGs go to <patch_dir>/IMG/<TYPE>/<NAME>.png; `grimtool.py build` converts them back.
  * paletted PNG with the game palette: indices are used as they are
  * any other PNG (RGB etc.): pixels identical to the original keep their original index,
    changed pixels get the nearest palette colour (index 0 = transparent black is only kept
    where the original pixel was index 0)
  * the size must stay the same as the original
"""
import io, os, struct, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grimtool as g


def load_palette(bundle, keys):
    e = [e for e in bundle.entries if e['name'] == 'TRUERGB.PAL'][0]
    p = g.xor(bundle.raw(e), keys[e['size'] % 4])[:768]
    return [min(255, c * 255 // 63) for c in p]


def decode(plain):
    w, h = struct.unpack_from('<HH', plain, 0)
    if len(plain) != w * h + 9:
        return None
    return w, h, plain[9:]


def to_image(w, h, px, pal):
    im = Image.frombytes('P', (w, h), bytes(px)).transpose(Image.FLIP_TOP_BOTTOM)
    im.putpalette(pal)
    return im


def encode(png, orig_plain, pal):
    """PNG (path, file object or Image) -> game bitmap bytes (decrypted)."""
    w, h, opx = decode(orig_plain)
    im = png if isinstance(png, Image.Image) else Image.open(png)
    if im.size != (w, h):
        raise ValueError(f'size {im.size} != original {(w, h)}')
    if im.mode == 'P' and (im.getpalette() or [])[:768] == pal:
        idx = im.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
    else:
        rgb = im.convert('RGB').transpose(Image.FLIP_TOP_BOTTOM).tobytes()
        cols = [tuple(pal[i * 3:i * 3 + 3]) for i in range(256)]
        cache = {}
        out = bytearray(w * h)
        for i in range(w * h):
            c = tuple(rgb[i * 3:i * 3 + 3])
            o = opx[i]
            if cols[o] == c:
                out[i] = o
                continue
            if c not in cache:
                best, bd = 1, 1 << 30
                for k in range(1, 256):
                    r, gg, b = cols[k]
                    d = (r - c[0]) ** 2 + (gg - c[1]) ** 2 + (b - c[2]) ** 2
                    if d < bd:
                        best, bd = k, d
                cache[c] = best
            out[i] = cache[c]
        idx = bytes(out)
    return struct.pack('<HH', w, h) + b'\0' * 5 + idx


def iter_images(bundle, keys, names=()):
    for e in bundle.entries:
        if not e['name'].endswith('.BMP'):
            continue
        if names and e['name'] not in names and e['type'] not in names:
            continue
        plain = g.xor(bundle.raw(e), keys[e['size'] % 4])
        if decode(plain):
            yield e, plain


def cmd_export(exe, rsf, out, names):
    keys = g.load_keys(exe); b = g.Bundle(rsf); pal = load_palette(b, keys)
    n = 0
    for e, plain in iter_images(b, keys, names):
        w, h, px = decode(plain)
        d = os.path.join(out, e['type']); os.makedirs(d, exist_ok=True)
        to_image(w, h, px, pal).save(os.path.join(d, e['name'][:-4] + '.png'))
        n += 1
    print(n, 'images ->', out)


def cmd_check(exe, rsf):
    keys = g.load_keys(exe); b = g.Bundle(rsf); pal = load_palette(b, keys)
    ok = bad = 0
    for e, plain in iter_images(b, keys):
        w, h, px = decode(plain)
        im = to_image(w, h, px, pal)
        buf = io.BytesIO(); im.save(buf, 'PNG'); buf.seek(0)
        a = encode(buf, plain, pal)                       # paletted PNG
        rgb = im.convert('RGB')
        c = encode(rgb, plain, pal)                       # same picture as RGB
        if a == plain and c == plain:
            ok += 1
        else:
            bad += 1
            print('MISMATCH', e['name'], a == plain, c == plain)
    print(f'images round-trip: {ok} ok, {bad} mismatch')


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == 'export':
        cmd_export(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'check':
        cmd_check(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
