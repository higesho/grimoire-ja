"""Convert an 8x8 BDF font (e.g. Misaki Gothic, ISO10646 encoded) to grimjp's bitmap format.

Output (little endian):
  'GJP8' u32 count, then count * { u32 codepoint, u8 advance, u8 rows[8] }   (top row first, MSB = left)
Usage: python bdf2bin.py misaki_gothic.bdf misaki8.bin
"""
import struct, sys


def convert(src, dst):
    ascent = 6
    glyphs = []
    cur = None
    with open(src, encoding='latin-1') as f:
        lines = iter(f.read().splitlines())
    for line in lines:
        k = line.split()
        if not k:
            continue
        if k[0] == 'FONT_ASCENT':
            ascent = int(k[1])
        elif k[0] == 'STARTCHAR':
            cur = {}
        elif k[0] == 'ENCODING':
            cur['cp'] = int(k[1])
        elif k[0] == 'DWIDTH':
            cur['adv'] = int(k[1])
        elif k[0] == 'BBX':
            cur['bbx'] = tuple(int(v) for v in k[1:5])
        elif k[0] == 'BITMAP':
            w, h, xo, yo = cur['bbx']
            rows = [0] * 8
            top = ascent - (yo + h)
            for r in range(h):
                v = int(next(lines).strip(), 16)
                nbytes = (w + 7) // 8
                v <<= 8 * (1 - nbytes) if nbytes < 2 else 0   # normalise to 8 bits for w<=8
                if nbytes > 1:
                    v >>= 8 * (nbytes - 1)
                y = top + r
                if 0 <= y < 8:
                    rows[y] = (v >> xo) & 0xFF if xo >= 0 else (v << -xo) & 0xFF
            cur['rows'] = rows
        elif k[0] == 'ENDCHAR':
            if cur.get('cp', -1) >= 0 and 'rows' in cur:
                glyphs.append(cur)
            cur = None
    glyphs.sort(key=lambda g: g['cp'])
    with open(dst, 'wb') as o:
        o.write(b'GJP8' + struct.pack('<I', len(glyphs)))
        for g in glyphs:
            o.write(struct.pack('<IB', g['cp'], g['adv']) + bytes(g['rows']))
    print(f'{len(glyphs)} glyphs -> {dst}')


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
