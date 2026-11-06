// grimjp: Japanese text rendering for Grimoire: Heralds of the Winged Exemplar (3.0.0.0-R)
//
// Built as a proxy "version.dll" placed next to Grimoire.exe.
//
// The game draws text through an embedded bitmap-font library (Fastgraph-style).
// Fonts hold 96 glyphs (0x20-0x7F); the library also supports 256-glyph fonts
// (flag 0x8000 in the glyph-size word). For every string that contains UTF-8
// sequences we build a temporary 256-glyph font: slots 0x20-0x7F are copied from
// the current font and the string's non-ASCII characters are rendered with GDI into
// slots 0x80-0xFF / 0x01-0x1F. The string is remapped to those single bytes and the
// original library routine is called, so colours (0x7F escapes), justification and
// clipping keep working exactly as in the original game.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <share.h>
#include <ctype.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------- version.dll proxy
static HMODULE g_real;
static FARPROC g_fp[17];
static const char* g_names[17] = {
    "GetFileVersionInfoA", "GetFileVersionInfoByHandle", "GetFileVersionInfoExA", "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA", "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW", "VerFindFileA", "VerFindFileW", "VerInstallFileA", "VerInstallFileW",
    "VerLanguageNameA", "VerLanguageNameW", "VerQueryValueA", "VerQueryValueW"};

static void load_real() {
    char path[MAX_PATH];
    GetSystemDirectoryA(path, MAX_PATH);  // SysWOW64 for a 32-bit process
    strcat_s(path, "\\version.dll");
    g_real = LoadLibraryA(path);
    for (int i = 0; i < 17; i++) g_fp[i] = g_real ? GetProcAddress(g_real, g_names[i]) : nullptr;
}

#define STUB(n, i) extern "C" __declspec(naked) void n() { __asm { jmp dword ptr [g_fp + i * 4] } }
STUB(p_GetFileVersionInfoA, 0)
STUB(p_GetFileVersionInfoByHandle, 1)
STUB(p_GetFileVersionInfoExA, 2)
STUB(p_GetFileVersionInfoExW, 3)
STUB(p_GetFileVersionInfoSizeA, 4)
STUB(p_GetFileVersionInfoSizeExA, 5)
STUB(p_GetFileVersionInfoSizeExW, 6)
STUB(p_GetFileVersionInfoSizeW, 7)
STUB(p_GetFileVersionInfoW, 8)
STUB(p_VerFindFileA, 9)
STUB(p_VerFindFileW, 10)
STUB(p_VerInstallFileA, 11)
STUB(p_VerInstallFileW, 12)
STUB(p_VerLanguageNameA, 13)
STUB(p_VerLanguageNameW, 14)
STUB(p_VerQueryValueA, 15)
STUB(p_VerQueryValueW, 16)

// ---------------------------------------------------------------- game addresses (VA, image base 0x400000)
static uintptr_t g_base;
#define VA(x) (g_base + ((uintptr_t)(x) - 0x400000))
#define FONT_PTR   (*(uint8_t**)VA(0x6B602E))   // current font data (widths, heights, glyphs)
#define FONT_GSIZE (*(uint32_t*)VA(0x6B603E))   // glyph slot size, 0x8000 = 256-glyph font
#define FONT_ID    (*(int32_t*)VA(0x6B603A))    // current font slot, 0 = none
#define FONT_LINEH (*(int32_t*)VA(0x6B6032))    // line height of current font

typedef int(__cdecl* str_fn)(const uint8_t*, int);
struct Hook { uint32_t va; int nbytes; const uint8_t* expect; str_fn tramp; };
static const uint8_t PRO6[] = {0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x0C};   // push ebp; mov ebp,esp; sub esp,0xc
static const uint8_t PRO5[] = {0x55, 0x8B, 0xEC, 0x57, 0x56};         // push ebp; mov ebp,esp; push edi; push esi
static const uint8_t PROW[] = {0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x68};   // sub esp,0x68
static const uint8_t PROM[] = {0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x08};   // sub esp,0x8
enum { H_PRINT_A, H_PRINT_B, H_WIDTH, H_HEIGHT, H_WDRAW, H_WMEASURE, H_COUNT };
static Hook g_hooks[H_COUNT] = {
    {0x622E1C, 6, PRO6, nullptr},   // print (unclipped)
    {0x623504, 6, PRO6, nullptr},   // print (clipped)
    {0x623490, 5, PRO5, nullptr},   // string width
    {0x6230F8, 5, PRO5, nullptr},   // string height
    {0x4E2220, 6, PROW, nullptr},   // widget sprite-font draw
    {0x4DE450, 6, PROM, nullptr},   // widget sprite-font measure
};

static FILE* g_log;
static void logf(const char* fmt, ...) {
    if (!g_log) return;
    va_list ap; va_start(ap, fmt); vfprintf(g_log, fmt, ap); va_end(ap); fflush(g_log);
}

// ---------------------------------------------------------------- settings
static wchar_t g_face[64] = L"MS Gothic";
static int g_size_adjust = 0;     // added to the computed glyph pixel height
static int g_debug = 0;
static char g_ini_path[MAX_PATH];
static int g_small_max = 9;       // fonts with cell height <= this use the 8x8 bitmap font
static int g_fallback_max = 6;    // fonts with cell height <= this use the English fallback table
#include <string>
static std::unordered_map<std::string, std::string> g_fallback;   // utf-8 translation -> original bytes

static void load_fallback(const char* path) {
    FILE* f = nullptr;
    if (fopen_s(&f, path, "rb") || !f) return;
    char line[2048];
    while (fgets(line, sizeof line, f)) {
        size_t n = strlen(line);
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
        char* tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        g_fallback[line] = tab + 1;
    }
    fclose(f);
}

static int font_cell_height() {
    const uint8_t* f0 = FONT_PTR;
    if (!f0 || FONT_ID == 0) return 0;
    bool wide = (FONT_GSIZE & 0x8000) != 0;
    int h = 0;
    for (int c = 0x21; c < 0x7F; c++) {
        int v = wide ? f0[0x100 + c] : f0[0x60 + c - 0x20];
        if (v > h) h = v;
    }
    return h;
}

// ---------------------------------------------------------------- 8x8 bitmap font (Misaki Gothic)
struct Small { uint8_t adv; uint8_t rows[8]; };
static std::unordered_map<uint32_t, Small> g_small;

static void load_small(const char* path) {
    FILE* f = nullptr;
    if (fopen_s(&f, path, "rb") || !f) return;
    char magic[4]; uint32_t n = 0;
    if (fread(magic, 1, 4, f) == 4 && memcmp(magic, "GJP8", 4) == 0 && fread(&n, 4, 1, f) == 1) {
        for (uint32_t i = 0; i < n; i++) {
            uint8_t rec[13];
            if (fread(rec, 1, 13, f) != 13) break;
            Small s; s.adv = rec[4]; memcpy(s.rows, rec + 5, 8);
            g_small[*(uint32_t*)rec] = s;
        }
    }
    fclose(f);
}

// ---------------------------------------------------------------- glyph rendering
struct Glyph { int w, h; std::vector<uint8_t> bits; };  // rows top->bottom, (w+7)/8 bytes per row
static std::unordered_map<uint64_t, Glyph> g_cache;
static CRITICAL_SECTION g_cs;

// px < 0 : use the 8x8 bitmap font, -px = number of rows to keep (7 or 8)
static const Glyph& get_glyph(uint32_t cp, int px) {
    uint64_t key = ((uint64_t)(uint32_t)px << 32) | cp;
    auto it = g_cache.find(key);
    if (it != g_cache.end()) return it->second;
    Glyph g{};
    if (px < 0) {
        int h = -px;
        auto s = g_small.find(cp);
        if (s == g_small.end()) s = g_small.find(0x25A1);   // white square for missing glyphs
        g.w = (s != g_small.end()) ? s->second.adv : 8; g.h = h;
        g.bits.assign((size_t)h, 0);                        // 1 byte per row (w <= 8)
        if (s != g_small.end())
            for (int vr = 0; vr < h; vr++) g.bits[(size_t)(h - 1 - vr)] = s->second.rows[vr];  // bottom row first
        return g_cache.emplace(key, std::move(g)).first->second;
    }
    HDC dc = CreateCompatibleDC(nullptr);
    HFONT f = CreateFontW(-px, 0, 0, 0, FW_NORMAL, 0, 0, 0, SHIFTJIS_CHARSET, OUT_DEFAULT_PRECIS,
                          CLIP_DEFAULT_PRECIS, NONANTIALIASED_QUALITY, FIXED_PITCH | FF_MODERN, g_face);
    HGDIOBJ of = SelectObject(dc, f);
    wchar_t wc[2]; int n = 1;
    if (cp >= 0x10000) { cp -= 0x10000; wc[0] = (wchar_t)(0xD800 + (cp >> 10)); wc[1] = (wchar_t)(0xDC00 + (cp & 0x3FF)); n = 2; }
    else wc[0] = (wchar_t)cp;
    SIZE sz{}; GetTextExtentPoint32W(dc, wc, n, &sz);
    TEXTMETRICW tm{}; GetTextMetricsW(dc, &tm);
    int w = sz.cx > 0 ? sz.cx : px, h = px;
    if (w > 248) w = 248;
    struct { BITMAPINFOHEADER h; RGBQUAD pal[2]; } bi{};
    bi.h.biSize = sizeof(BITMAPINFOHEADER); bi.h.biWidth = w; bi.h.biHeight = -tm.tmHeight;
    bi.h.biPlanes = 1; bi.h.biBitCount = 1;
    bi.pal[1].rgbRed = bi.pal[1].rgbGreen = bi.pal[1].rgbBlue = 255;
    void* bits = nullptr;
    HBITMAP bmp = CreateDIBSection(dc, (BITMAPINFO*)&bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    HGDIOBJ ob = SelectObject(dc, bmp);
    SetBkColor(dc, RGB(0, 0, 0)); SetTextColor(dc, RGB(255, 255, 255)); SetBkMode(dc, OPAQUE);
    TextOutW(dc, 0, 0, wc, n);
    GdiFlush();
    // place the cell (bottom aligned) into h rows. The library stores bitmaps
    // bottom row first, so output row r = visual row (h - 1 - r).
    int stride = ((w + 31) / 32) * 4, bpr = (w + 7) / 8;
    g.w = w; g.h = h; g.bits.assign((size_t)bpr * h, 0);
    int src_bottom = tm.tmHeight;   // rows 0..tmHeight-1
    for (int vr = 0; vr < h; vr++) {
        int sr = src_bottom - h + vr;
        if (sr < 0 || sr >= tm.tmHeight) continue;
        memcpy(&g.bits[(size_t)(h - 1 - vr) * bpr], (uint8_t*)bits + (size_t)sr * stride, bpr);
    }
    SelectObject(dc, ob); DeleteObject(bmp);
    SelectObject(dc, of); DeleteObject(f); DeleteDC(dc);
    return g_cache.emplace(key, std::move(g)).first->second;
}

// ---------------------------------------------------------------- temporary 256-glyph font
static std::vector<uint8_t> g_font;   // 0x200 header (widths, heights) + 256 slots
static std::vector<uint8_t> g_str;

static inline int utf8_decode(const uint8_t* s, int n, uint32_t* cp) {
    uint8_t c = s[0];
    if (c >= 0xC2 && c <= 0xDF && n >= 2 && (s[1] & 0xC0) == 0x80) { *cp = ((c & 0x1F) << 6) | (s[1] & 0x3F); return 2; }
    if (c >= 0xE0 && c <= 0xEF && n >= 3 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80) {
        *cp = ((c & 0x0F) << 12) | ((s[1] & 0x3F) << 6) | (s[2] & 0x3F); return *cp >= 0x800 ? 3 : 0; }
    if (c >= 0xF0 && c <= 0xF4 && n >= 4 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80 && (s[3] & 0xC0) == 0x80) {
        *cp = ((c & 0x07) << 18) | ((s[1] & 0x3F) << 12) | ((s[2] & 0x3F) << 6) | (s[3] & 0x3F); return 4; }
    return 0;
}

static bool needs_jp(const uint8_t* s, int n) {
    for (int i = 0; i < n; i++) {
        if (s[i] == 0x7F) { i++; continue; }
        if (s[i] >= 0x80) return true;
    }
    return false;
}

// Builds the temporary font + remapped string. Returns false when nothing to do.
// standalone_px > 0: no base font; every character (ASCII too) is rendered with GDI at that size
static bool prepare(const uint8_t* s, int n, int standalone_px = 0) {
    bool standalone = standalone_px > 0;
    if (n <= 0 || !needs_jp(s, n)) return false;
    if (!standalone && (FONT_ID == 0 || !FONT_PTR)) return false;
    static const uint8_t empty_font[0x200 + 1] = {0};
    const uint8_t* f0 = standalone ? empty_font : FONT_PTR;
    uint32_t gs0 = standalone ? (0x8000 | 1) : FONT_GSIZE;
    bool wide0 = (gs0 & 0x8000) != 0;
    uint32_t size0 = wide0 ? (gs0 & 0x7FFF) : gs0;
    auto w0 = [&](int c) -> int { return standalone ? 0 : wide0 ? f0[c] : (c >= 0x20 && c < 0x80 ? f0[c - 0x20] : 0); };
    auto h0 = [&](int c) -> int { return standalone ? 0 : wide0 ? f0[0x100 + c] : (c >= 0x20 && c < 0x80 ? f0[0x60 + c - 0x20] : 0); };
    auto g0 = [&](int c) -> const uint8_t* { return standalone ? empty_font : wide0 ? f0 + 0x200 + c * size0 : f0 + 0xC0 + (c - 0x20) * size0; };

    int cellh = 0;
    for (int c = 0x21; c < 0x7F; c++) if (h0(c) > cellh) cellh = h0(c);
    int px = cellh + g_size_adjust;
    if (px < 8) px = 8;
    if (cellh <= g_small_max && !g_small.empty()) px = -(cellh >= 8 ? 8 : 7);
    if (standalone) { cellh = standalone_px; px = standalone_px; if (cellh <= g_small_max && !g_small.empty()) px = -(cellh >= 8 ? 8 : 7); }

    // collect distinct code points
    uint32_t slot_cp[256] = {0};
    std::unordered_map<uint32_t, uint8_t> slot_of;
    const uint8_t free_slots_hi = 0x80;  // 0x80..0xFF, then 0x01..0x1F
    int next = free_slots_hi;
    auto alloc = [&](uint32_t cp) -> uint8_t {
        auto it = slot_of.find(cp);
        if (it != slot_of.end()) return it->second;
        int sl;
        if (next <= 0xFF) sl = next++;
        else if (next - 0x100 + 1 < 0x20) { sl = next - 0x100 + 1; next++; }
        else return '?';
        slot_of[cp] = (uint8_t)sl; slot_cp[sl] = cp; return (uint8_t)sl;
    };
    g_str.clear();
    for (int i = 0; i < n;) {
        uint8_t c = s[i];
        if (c == 0x7F && i + 1 < n) { g_str.push_back(c); g_str.push_back(s[i + 1]); i += 2; continue; }
        // soft break: the patch tools put ' ' between Japanese characters so that the game's
        // word wrap (which only breaks at spaces) can break Japanese lines. Draw it with no width.
        if (c == ' ' && (i == 0 || s[i - 1] >= 0x80) && (i + 1 >= n || s[i + 1] >= 0x80)) { i++; continue; }
        if (c < 0x80 && standalone && c >= 0x20) { slot_cp[c] = c; g_str.push_back(c); i++; continue; }
        if (c < 0x80) { g_str.push_back(c); i++; continue; }
        uint32_t cp; int k = utf8_decode(s + i, n - i, &cp);
        if (!k) {
            // a UTF-8 lead byte whose sequence runs past the end: the game cut the string
            // to a byte length (e.g. Left(78)) -> drop the partial character
            int need = (c >= 0xF0) ? 4 : (c >= 0xE0) ? 3 : (c >= 0xC2) ? 2 : 0;
            bool tail_ok = true;
            for (int t = 1; t < n - i; t++) if ((s[i + t] & 0xC0) != 0x80) tail_ok = false;
            if (need && i + need > n && tail_ok) break;
            // a partial character in the middle: the game cut a name to a byte length and then
            // appended more text (e.g. "?" + name + "?" for unidentified monsters) -> drop it too
            int cont = 0;
            while (i + 1 + cont < n && cont < need - 1 && (s[i + 1 + cont] & 0xC0) == 0x80) cont++;
            if (need && cont >= 1 && cont + 1 < need) { i += 1 + cont; continue; }
            // otherwise an original single-byte (cp1252) character such as e-acute
            wchar_t w = 0; char b = (char)c;
            MultiByteToWideChar(1252, 0, &b, 1, &w, 1);
            cp = w ? w : 0xFFFD; k = 1;
        }
        if (cp == 0x3000) { g_str.push_back(' '); g_str.push_back(' '); i += k; continue; }  // ideographic space
        g_str.push_back(alloc(cp)); i += k;
    }
    // slot size
    uint32_t size1 = size0;
    for (int sl = 1; sl < 256; sl++) {
        if (!slot_cp[sl]) continue;
        const Glyph& g = get_glyph(slot_cp[sl], px);
        uint32_t need = (uint32_t)((g.w + 7) / 8) * g.h;
        if (need > size1) size1 = need;
    }
    if (size1 > 0x7FFF) return false;
    g_font.assign(0x200 + (size_t)256 * size1, 0);
    uint8_t* f1 = g_font.data();
    if (!standalone)
        for (int c = 0x20; c < 0x80; c++) {
            f1[c] = (uint8_t)w0(c); f1[0x100 + c] = (uint8_t)h0(c);
            memcpy(f1 + 0x200 + c * size1, g0(c), size0);
        }
    for (int sl = 1; sl < 256; sl++) {
        if (!slot_cp[sl]) continue;
        const Glyph& g = get_glyph(slot_cp[sl], px);
        f1[sl] = (uint8_t)g.w; f1[0x100 + sl] = (uint8_t)g.h;
        memcpy(f1 + 0x200 + sl * size1, g.bits.data(), g.bits.size());
    }
    if (g_debug) logf("prepare font=%d px=%d size0=%u size1=%u chars=%u len=%d->%d '%.*s'\n", FONT_ID, px, size0, size1,
                      (unsigned)slot_of.size(), n, (int)g_str.size(), n, (const char*)s);
    // stash size for swap
    g_font.push_back((uint8_t)(size1 & 0xFF)); g_font.push_back((uint8_t)(size1 >> 8));
    return true;
}

static int call_swapped(str_fn fn) {
    size_t L = g_font.size();
    uint32_t size1 = g_font[L - 2] | (g_font[L - 1] << 8);
    uint8_t* sp = FONT_PTR; uint32_t sg = FONT_GSIZE;
    FONT_PTR = g_font.data(); FONT_GSIZE = size1 | 0x8000;
    int r = fn(g_str.data(), (int)g_str.size());
    FONT_PTR = sp; FONT_GSIZE = sg;
    return r;
}

static const std::string* find_fallback(const uint8_t* s, int n) {
    if (g_fallback.empty() || n <= 0 || !needs_jp(s, n) || font_cell_height() > g_fallback_max) return nullptr;
    std::string key((const char*)s, (size_t)n);
    auto it = g_fallback.find(key);
    if (it != g_fallback.end()) return &it->second;
    // the game may cut labels to a fixed byte length: accept a unique prefix match
    const std::string* hit = nullptr; int count = 0;
    if (n >= 3)
        for (auto& kv : g_fallback)
            if (kv.first.size() > (size_t)n && kv.first.compare(0, (size_t)n, key) == 0) { hit = &kv.second; count++; }
    if (g_debug) logf("fallback miss len=%d prefix_hits=%d '%.*s'\n", n, count, n, (const char*)s);
    return count >= 1 ? hit : nullptr;
}

// ---------------------------------------------------------------- UI string table (strings hard-coded in the exe)
// grimjp/ui_strings.txt (UTF-8):
//   English<TAB>日本語            exact match of the whole drawn string
//   ~pat*tern<TAB>訳*文           glob: each * captures text, inserted in order into the translation
//   # comment
// Escape sequences in both columns: \t \\ \xHH
static std::unordered_map<std::string, std::string> g_ui_exact;
static std::vector<std::pair<std::string, std::string>> g_ui_glob;
static std::string g_ui_out;
static int g_collect = 0;
static FILE* g_collect_f;
static std::unordered_map<std::string, int> g_collected;

static std::string unescape(const char* p) {
    std::string o;
    for (; *p; p++) {
        if (*p == '\\' && p[1]) {
            p++;
            if (*p == 't') o += '\t';
            else if (*p == 'x' && isxdigit((uint8_t)p[1]) && isxdigit((uint8_t)p[2])) {
                char hx[3] = {p[1], p[2], 0}; o += (char)strtol(hx, nullptr, 16); p += 2;
            } else o += *p;
        } else o += *p;
    }
    return o;
}

static void load_ui(const char* path) {
    FILE* f = nullptr;
    if (fopen_s(&f, path, "rb") || !f) return;
    char line[4096];
    while (fgets(line, sizeof line, f)) {
        size_t n = strlen(line);
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
        char* p = line;
        if ((uint8_t)p[0] == 0xEF && (uint8_t)p[1] == 0xBB && (uint8_t)p[2] == 0xBF) p += 3;  // BOM
        if (!*p || *p == '#') continue;
        char* tab = strchr(p, '\t');
        if (!tab) continue;
        *tab = 0;
        if (*p == '~') g_ui_glob.emplace_back(unescape(p + 1), unescape(tab + 1));
        else g_ui_exact[unescape(p)] = unescape(tab + 1);
    }
    fclose(f);
}

// glob match: '*' = any text (shortest first), '#' = one or more digits; both capture
static bool glob(const char* pat, const char* s, const char* e, std::vector<std::string>& caps) {
    if (!*pat) return s == e;
    if (*pat == '*') {
        for (const char* q = s; q <= e; q++) {
            caps.emplace_back(s, q);
            if (glob(pat + 1, q, e, caps)) return true;
            caps.pop_back();
        }
        return false;
    }
    if (*pat == '#') {
        const char* q = s;
        while (q < e && *q >= '0' && *q <= '9') q++;
        for (; q > s; q--) {
            caps.emplace_back(s, q);
            if (glob(pat + 1, q, e, caps)) return true;
            caps.pop_back();
        }
        return false;
    }
    return s < e && *pat == *s && glob(pat + 1, s + 1, e, caps);
}

static void collect(const uint8_t* s, int n) {
    if (!g_collect || n <= 0 || needs_jp(s, n)) return;
    std::string k((const char*)s, (size_t)n);
    int fid = FONT_ID;
    if (g_collected.count(k)) return;
    g_collected[k] = fid;
    if (!g_collect_f) return;
    fprintf(g_collect_f, "%d\t", fid);
    for (int i = 0; i < n; i++) {
        uint8_t c = s[i];
        if (c == '\\') fputs("\\\\", g_collect_f);
        else if (c < 0x20 || c >= 0x7F) fprintf(g_collect_f, "\\x%02X", c);
        else fputc(c, g_collect_f);
    }
    fputc('\n', g_collect_f); fflush(g_collect_f);
}

// returns replacement for an exe/UI string, or nullptr
static bool g_ui_off;   // set when the Japanese archive cannot be used: keep the whole game English
static const std::string* find_ui(const uint8_t* s, int n, bool fastgraph = true) {
    collect(s, n);
    if (g_ui_off || n <= 0 || (g_ui_exact.empty() && g_ui_glob.empty())) return nullptr;
    if (fastgraph && font_cell_height() <= g_fallback_max) return nullptr;   // tiny 5px lists: keep English
    std::string k((const char*)s, (size_t)n);
    auto it = g_ui_exact.find(k);
    if (it != g_ui_exact.end()) return &it->second;
    for (auto& g : g_ui_glob) {
        std::vector<std::string> caps;
        if (!glob(g.first.c_str(), k.data(), k.data() + k.size(), caps)) continue;
        g_ui_out.clear();
        size_t ci = 0;
        for (char c : g.second) {
            if ((c == '*' || c == '#') && ci < caps.size()) {
                // translate captured pieces too when they are exact UI strings
                auto sub = g_ui_exact.find(caps[ci]);
                g_ui_out += (sub != g_ui_exact.end()) ? sub->second : caps[ci];
                ci++;
            } else g_ui_out += c;
        }
        return &g_ui_out;
    }
    return nullptr;
}

// ---------------------------------------------------------------- UTF-8-safe substring
// 0x4FBAA0 is the game's string Mid(out, a, b): bytes [min(a,b), max(a,b)) of the string
// (Left(n) at 0x4FBBC0 calls Mid(0, n)). Names are cut with it (e.g. monster names to
// 14/20 bytes), which can split a UTF-8 character. The cut is moved back to a character
// boundary. String object: +4 = char*, +0xC = length.
typedef void*(__fastcall* mid_fn)(void* self, void* edx, void* out, uint32_t a, uint32_t b);
static mid_fn g_mid_tramp;
static int g_mid_logged, g_mid_all, g_debug_mid, g_trace_broken;
static void* __fastcall hk_mid(void* self, void* edx, void* out, uint32_t a, uint32_t b) {
    __try {
        const uint8_t* s = *(const uint8_t**)((uint8_t*)self + 4);
        uint32_t len = *(uint32_t*)((uint8_t*)self + 0xC);
        uint32_t lo = a < b ? a : b, hi = a < b ? b : a;
        if (g_debug_mid && s && g_mid_all < 400) {
            bool hb = false;
            for (uint32_t i = 0; i < len && !hb; i++) hb = s[i] >= 0x80;
            if (hb) {
                g_mid_all++;
                logf("mid %u..%u len=%u at %08X '%.*s'\n", lo, hi, len,
                     (unsigned)((uintptr_t)_ReturnAddress() - g_base + 0x400000), (int)len, (const char*)s);
            }
        }
        if (s && hi < len) {
            uint32_t h0 = hi;
            while (hi > lo && (s[hi] & 0xC0) == 0x80) hi--;
            if (hi != h0) {
                if (g_mid_logged < 200) {
                    g_mid_logged++;
                    logf("mid cut %u->%u at %08X '%.*s'\n", h0, hi,
                         (unsigned)((uintptr_t)_ReturnAddress() - g_base + 0x400000), (int)len, (const char*)s);
                }
                a = lo; b = hi;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {}
    return g_mid_tramp(self, edx, out, a, b);
}

static bool hook_mid() {
    uint8_t* p = (uint8_t*)VA(0x4FBAA0);
    static const uint8_t exp[] = {0x55, 0x8B, 0xEC, 0x6A, 0xFF, 0x68};   // push ebp; mov ebp,esp; push -1; push imm32
    if (memcmp(p, exp, sizeof exp) != 0) { logf("Mid at 4FBAA0 not as expected, skipped\n"); return false; }
    const int nb = 10;
    uint8_t* t = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    memcpy(t, p, nb);
    t[nb] = 0xE9; *(int32_t*)(t + nb + 1) = (int32_t)((p + nb) - (t + nb + 5));
    g_mid_tramp = (mid_fn)t;
    DWORD old;
    VirtualProtect(p, nb, PAGE_EXECUTE_READWRITE, &old);
    p[0] = 0xE9; *(int32_t*)(p + 1) = (int32_t)((uint8_t*)hk_mid - (p + 5));
    for (int k = 5; k < nb; k++) p[k] = 0x90;
    VirtualProtect(p, nb, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, nb);
    return true;
}

// log (once per string) the game call stack of a drawn string with a broken UTF-8 sequence
static std::unordered_map<std::string, int> g_broken_seen;
static void trace_broken(const uint8_t* s, int n) {
    bool broken = false;
    for (int i = 0; i < n && !broken;) {
        uint8_t c = s[i];
        int need = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC2 ? 2 : 1;
        if (c >= 0x80 && need == 1) { i++; continue; }
        int k = 1;
        while (k < need && i + k < n && (s[i + k] & 0xC0) == 0x80) k++;
        if (k < need) broken = true;
        i += k;
    }
    if (!broken || g_broken_seen.size() > 300) return;
    std::string key((const char*)s, (size_t)n);
    if (g_broken_seen.count(key)) return;
    g_broken_seen[key] = 1;
    void* fr[24]; USHORT nf = RtlCaptureStackBackTrace(0, 24, fr, nullptr);
    logf("broken utf8 n=%d '%.*s' hex:", n, n, (const char*)s);
    for (int i = 0; i < n; i++) logf(" %02X", s[i]);
    logf(" stack:");
    uintptr_t lo = g_base, hi = g_base + 0x2C8000;
    for (USHORT i = 0; i < nf; i++) {
        uintptr_t a = (uintptr_t)fr[i];
        if (a >= lo && a < hi) logf(" %08X", (unsigned)(a - g_base + 0x400000));
    }
    logf("\n");
}

// debug: draw each font's glyph for '~' (0x7E) into the log, once per font id
static bool g_tilde_done[64];
static void dump_tilde() {
    int id = FONT_ID;
    if (id <= 0 || id >= 64 || g_tilde_done[id] || !FONT_PTR) return;
    g_tilde_done[id] = true;
    const uint8_t* f = FONT_PTR;
    uint32_t gs = FONT_GSIZE;
    bool wide = (gs & 0x8000) != 0;
    uint32_t sz = wide ? (gs & 0x7FFF) : gs;
    static const int cs[] = {0x7E, 0x41};
    for (int c : cs) {
        int w = wide ? f[c] : f[c - 0x20], h = wide ? f[0x100 + c] : f[0x60 + c - 0x20];
        const uint8_t* g = wide ? f + 0x200 + c * sz : f + 0xC0 + (c - 0x20) * sz;
        int bpr = (w + 7) / 8;
        logf("font %d glyph %02X w=%d h=%d size=%u\n", id, c, w, h, sz);
        for (int r = h - 1; r >= 0; r--) {          // stored bottom row first
            char line[80]; int k = 0;
            for (int x = 0; x < w && k < 78; x++) line[k++] = (g[r * bpr + x / 8] & (0x80 >> (x % 8))) ? '#' : '.';
            line[k] = 0;
            logf("  %s\n", line);
        }
    }
}

// ---------------------------------------------------------------- monster group names
// 0x5CC050 builds a group name as  group + " " + plural  from the @MONSTERS fields, e.g.
// "Troop ~" + " " + "Soldiers"; the game font draws '~' as an "of" ligature ("Troop of Soldiers").
// The Japanese group field is "~の部隊", which would come out as "ofの部隊 前衛兵". Here
// "~<group> <name>" (group starting with a non-ASCII character) is reordered to "<name><group>":
// "~の部隊 前衛兵" -> "前衛兵の部隊". The name ends at the end of the string or at the first
// byte that is not part of a UTF-8 character (e.g. the cp1252 '×' before a count).
static int g_trace_tilde;
static std::string g_group_out;
static int utf8_len(const uint8_t* s, int i, int n) {      // length of a valid UTF-8 character at i, else 0
    uint8_t c = s[i];
    int need = c >= 0xF0 && c < 0xF5 ? 4 : c >= 0xE0 ? 3 : c >= 0xC2 && c < 0xE0 ? 2 : 0;
    if (!need || i + need > n) return 0;
    for (int k = 1; k < need; k++) if ((s[i + k] & 0xC0) != 0x80) return 0;
    return need;
}
static const std::string* fix_group(const uint8_t* s, int n) {
    for (int t = 0; t + 1 < n; t++) {
        if (s[t] != '~' || s[t + 1] < 0x80) continue;
        int g = t + 1, sp = g;
        while (sp < n && s[sp] != ' ') {                    // group word: UTF-8 characters up to the space
            int k = utf8_len(s, sp, n);
            if (!k) return nullptr;
            sp += k;
        }
        if (sp >= n) return nullptr;
        int ne = sp + 1;
        while (ne < n) {                                     // name: UTF-8 characters (and '・' etc.)
            int k = utf8_len(s, ne, n);
            if (!k) break;
            ne += k;
        }
        if (ne == sp + 1) return nullptr;
        g_group_out.assign((const char*)s, t);                          // text before '~'
        g_group_out.append((const char*)s + sp + 1, ne - sp - 1);       // name
        g_group_out.append((const char*)s + g, sp - g);                 // group word
        g_group_out.append((const char*)s + ne, n - ne);                // rest (count etc.)
        if (g_trace_tilde) logf("group '%.*s' -> '%s'\n", n, (const char*)s, g_group_out.c_str());
        return &g_group_out;
    }
    return nullptr;
}

static int dispatch(int h, const uint8_t* s, int n) {
    EnterCriticalSection(&g_cs);
    int r;
    __try {
        if (g_trace_broken) trace_broken(s, n);
        if (g_trace_tilde) dump_tilde();
        const std::string* grp = fix_group(s, n);
        if (grp) { s = (const uint8_t*)grp->data(); n = (int)grp->size(); }
        const std::string* ui = find_ui(s, n);
        if (ui) { s = (const uint8_t*)ui->data(); n = (int)ui->size(); }
        const std::string* fb = find_fallback(s, n);
        if (fb) r = g_hooks[h].tramp((const uint8_t*)fb->data(), (int)fb->size());
        else if (prepare(s, n)) r = call_swapped(g_hooks[h].tramp);
        else r = g_hooks[h].tramp(s, n);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("exception in hook %d\n", h);
        r = 0;
    }
    LeaveCriticalSection(&g_cs);
    return r;
}

static int __cdecl hk_print_a(const uint8_t* s, int n) { return dispatch(H_PRINT_A, s, n); }
static int __cdecl hk_print_b(const uint8_t* s, int n) { return dispatch(H_PRINT_B, s, n); }
static int __cdecl hk_width(const uint8_t* s, int n) { return dispatch(H_WIDTH, s, n); }
static int __cdecl hk_height(const uint8_t* s, int n) { return dispatch(H_HEIGHT, s, n); }

// ---------------------------------------------------------------- widget (sprite sheet) font
// 0x4E2220 void draw(const char* s, int x, int y, int font, int colorkey)
// 0x4DE450 int  measure(const char* s, int font)   -> (strlen-1) * advance
typedef void(__cdecl* wdraw_fn)(const char*, int, int, int, int);
typedef int(__cdecl* wmeasure_fn)(const char*, int);
typedef void*(__thiscall* getfont_fn)(void* vec, int idx);
typedef int(__cdecl* setcolor_fn)(uint32_t);
static wdraw_fn g_wdraw_tramp;
static wmeasure_fn g_wmeasure_tramp;
static uint32_t g_widget_rgb = 0xC8A0FF;

static int widget_cell_h(int font) {
    getfont_fn gf = (getfont_fn)VA(0x404318);
    uint8_t* fo = (uint8_t*)gf((void*)VA(0x6C3A54), font);
    return fo ? *(int32_t*)(fo + 0x12) : 16;
}

static int g_widget_index = 49;   // palette index used in 8-bit mode (TRUERGB.PAL 49 = light purple)
static void set_nearest_color(uint32_t rgb) {
    int bpp = *(int32_t*)VA(0x6B6DF0) & 0xFF;
    if (bpp <= 8) { ((setcolor_fn)VA(0x623994))((uint32_t)g_widget_index); return; }
    const uint8_t* tab = (const uint8_t*)VA(0x6B7080);
    int best = 15; long bestd = 0x7FFFFFFF;
    for (int i = 0; i < 256; i++) {
        uint32_t v;
        if (bpp > 16) v = _byteswap_ulong(((const uint32_t*)tab)[i]) & 0xFFFFFF;
        else if (bpp > 8) { uint16_t w = ((const uint16_t*)tab)[i]; v = ((w >> 11) & 31) << 19 | ((w >> 5) & 63) << 10 | (w & 31) << 3; }
        else break;
        long dr = (long)((v >> 16) & 255) - (long)((rgb >> 16) & 255), dg = (long)((v >> 8) & 255) - (long)((rgb >> 8) & 255),
             db = (long)(v & 255) - (long)(rgb & 255);
        long d = dr * dr + dg * dg + db * db;
        if (d < bestd) { bestd = d; best = i; }
    }
    static bool dumped = false;
    if (!dumped) {
        dumped = true;
        logf("palette bpp=%d best=%d dist=%ld:", bpp, best, bestd);
        for (int i = 0; i < 256; i++) logf(" %08X", ((const uint32_t*)tab)[i]);
        logf("\n");
    }
    uint32_t col = best;
    if (bpp > 16) col = _byteswap_ulong(((const uint32_t*)tab)[best]);
    else if (bpp > 8) col = ((const uint16_t*)tab)[best];
    ((setcolor_fn)VA(0x623994))(col);
}

#define G32(a) (*(int32_t*)VA(a))
#define G8(a) (*(int8_t*)VA(a))
static void widget_draw_jp(int x, int y, int px) {
    size_t L = g_font.size();
    uint32_t size1 = g_font[L - 2] | (g_font[L - 1] << 8);
    int32_t sv[10] = {G32(0x6B602E), G32(0x6B603E), G32(0x6B603A), G32(0x6B6032), G32(0x6B6036),
                      G32(0x6B6E18), G32(0x6B6E24), G32(0x6B6DEC)};
    int8_t jh = G8(0x6B6046), jv = G8(0x6B6047);
    FONT_PTR = g_font.data(); FONT_GSIZE = size1 | 0x8000; FONT_ID = 1; FONT_LINEH = px;
    G32(0x6B6036) = 0; G8(0x6B6046) = -1; G8(0x6B6047) = -1;
    G32(0x6B6E18) = x; G32(0x6B6E24) = y;
    set_nearest_color(g_widget_rgb);
    g_hooks[H_PRINT_A].tramp(g_str.data(), (int)g_str.size());
    G32(0x6B602E) = sv[0]; G32(0x6B603E) = sv[1]; G32(0x6B603A) = sv[2]; G32(0x6B6032) = sv[3]; G32(0x6B6036) = sv[4];
    G32(0x6B6E18) = sv[5]; G32(0x6B6E24) = sv[6]; G32(0x6B6DEC) = sv[7];
    G8(0x6B6046) = jh; G8(0x6B6047) = jv;
}

static int jp_width_of_prepared(int* last_w) {
    int total = 0, last = 0;
    for (size_t i = 0; i < g_str.size(); i++) {
        uint8_t b = g_str[i];
        if (b == 0x7F) { i++; continue; }
        last = g_font[b]; total += last;
    }
    if (last_w) *last_w = last;
    return total;
}

static void wdraw_impl(const char* s, int x, int y, int font, int key) {
    const std::string* ui = find_ui((const uint8_t*)s, s ? (int)strlen(s) : 0, false);
    const char* t = ui ? ui->c_str() : s;
    int n = t ? (int)strlen(t) : 0;
    if (n > 0 && needs_jp((const uint8_t*)t, n)) {
        int px = widget_cell_h(font);
        if (g_debug) logf("wdraw font=%d px=%d x=%d y=%d key=%d '%s'\n", font, px, x, y, key, t);
        if (prepare((const uint8_t*)t, n, px)) { widget_draw_jp(x, y, px); return; }
    }
    g_wdraw_tramp(t, x, y, font, key);
}

static int wmeasure_impl(const char* s, int font) {
    const std::string* ui = find_ui((const uint8_t*)s, s ? (int)strlen(s) : 0, false);
    const char* t = ui ? ui->c_str() : s;
    int n = t ? (int)strlen(t) : 0;
    if (n > 0 && needs_jp((const uint8_t*)t, n)) {
        int px = widget_cell_h(font);
        int last = 0;
        if (prepare((const uint8_t*)t, n, px)) {
            int w = jp_width_of_prepared(&last) - last;
            if (g_debug) logf("wmeasure font=%d px=%d w=%d orig=%d '%s'\n", font, px, w, g_wmeasure_tramp(t, font), t);
            return w;
        }
    }
    return g_wmeasure_tramp(t, font);
}

static void __cdecl hk_wdraw(const char* s, int x, int y, int font, int key) {
    EnterCriticalSection(&g_cs);
    __try { wdraw_impl(s, x, y, font, key); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("exception in widget draw\n"); }
    LeaveCriticalSection(&g_cs);
}
static int __cdecl hk_wmeasure(const char* s, int font) {
    int r = 0;
    EnterCriticalSection(&g_cs);
    __try { r = wmeasure_impl(s, font); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("exception in widget measure\n"); }
    LeaveCriticalSection(&g_cs);
    return r;
}

static str_fn g_impl[H_COUNT] = {hk_print_a, hk_print_b, hk_width, hk_height, (str_fn)hk_wdraw, (str_fn)hk_wmeasure};

// ---------------------------------------------------------------- text sanitizer
// 0x4FBFC0 (called through 0x402167) replaces every byte that is not isspace / ispunct /
// isalnum with ' '. UTF-8 bytes (>= 0x80) are none of these, so Japanese text turned into
// blanks (e.g. vocation descriptions from GPC.DBS). Its first test (isspace, 0x630D94) is
// redirected here so that bytes >= 0x80 are kept.
// (CRT: 0x630D94 isspace, 0x630E13 ispunct, 0x630E97 isalnum, 0x630B10 isalpha.)
typedef int(__cdecl* ctype_fn)(int);
static int __cdecl jp_keep_byte(int c) {
    if ((c & 0xFF) >= 0x80) return 1;
    return ((ctype_fn)VA(0x630D94))(c);
}
static const uint32_t g_isalnum_sites[] = {0x4FC05E};

static void patch_ctype_calls() {
    for (uint32_t site : g_isalnum_sites) {
        uint8_t* p = (uint8_t*)VA(site);
        if (p[0] != 0xE8 || (uintptr_t)(p + 5 + *(int32_t*)(p + 1)) != VA(0x630D94)) {
            logf("isalnum call site %08X not as expected, skipped\n", site);
            continue;
        }
        DWORD old;
        VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old);
        *(int32_t*)(p + 1) = (int32_t)((uint8_t*)jp_keep_byte - (p + 5));
        VirtualProtect(p, 5, old, &old);
        FlushInstructionCache(GetCurrentProcess(), p, 5);
    }
}

// ---------------------------------------------------------------- in-place exe string patches
// grimjp/exe_strings.txt: English<TAB>日本語. Strings the game splices into other text
// (e.g. "Your Party" inside a [sub] substitution) cannot be replaced at draw time, so the
// literal in the exe's data section is overwritten at startup. The translation must fit in
// the original slot (string + its NUL padding); otherwise it is skipped and logged.
static void patch_exe_strings(const char* path) {
    FILE* f = nullptr;
    if (fopen_s(&f, path, "rb") || !f) return;
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)g_base;
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(g_base + dos->e_lfanew);
    IMAGE_SECTION_HEADER* sec = IMAGE_FIRST_SECTION(nt);
    char line[1024]; int ok = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        size_t n = strlen(line);
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
        char* p = line;
        if ((uint8_t)p[0] == 0xEF && (uint8_t)p[1] == 0xBB && (uint8_t)p[2] == 0xBF) p += 3;
        if (!*p || *p == '#') continue;
        char* tab = strchr(p, '\t');
        if (!tab) continue;
        *tab = 0;
        std::string en = unescape(p), jp = unescape(tab + 1);
        uint8_t* hit = nullptr; int hits = 0;
        for (int s = 0; s < nt->FileHeader.NumberOfSections; s++) {
            if (!(sec[s].Characteristics & IMAGE_SCN_CNT_INITIALIZED_DATA)) continue;
            uint8_t* a = (uint8_t*)(g_base + sec[s].VirtualAddress);
            size_t len = sec[s].Misc.VirtualSize;
            for (size_t i = 1; i + en.size() + 1 <= len; i++) {
                if (a[i - 1] != 0 || memcmp(a + i, en.c_str(), en.size() + 1) != 0) continue;
                hit = a + i; hits++;
            }
        }
        if (hits != 1) { logf("exe string '%s': %d matches, skipped\n", en.c_str(), hits); bad++; continue; }
        size_t slot = en.size() + 1;
        while (hit[slot] == 0 && slot < en.size() + 64) slot++;   // trailing NUL padding is ours too
        if (jp.size() + 1 > slot) { logf("exe string '%s': translation %u bytes > slot %u, skipped\n",
                                         en.c_str(), (unsigned)jp.size() + 1, (unsigned)slot); bad++; continue; }
        DWORD old;
        VirtualProtect(hit, slot, PAGE_READWRITE, &old);
        memset(hit, 0, slot);
        memcpy(hit, jp.c_str(), jp.size());
        VirtualProtect(hit, slot, old, &old);
        ok++;
    }
    fclose(f);
    logf("exe strings patched: %d ok, %d skipped\n", ok, bad);
}

// debug: after the game has set its locale, record what its CRT toupper (0x6312D7) does to
// bytes >= 0x80 (the game upper-cases names byte by byte with sign extension)
static DWORD WINAPI toupper_probe(LPVOID) {
    Sleep(15000);
    typedef int(__cdecl* tu_fn)(int);
    tu_fn tu = (tu_fn)VA(0x6312D7);
    int changed = 0;
    logf("toupper probe:");
    for (int b = 0x80; b < 0x100; b++) {
        int c = (int)(signed char)b;
        int r = tu(c);
        if ((r & 0xFF) != b) { logf(" %02X->%X", b, r); changed++; }
    }
    logf(" (%d changed)\n", changed);
    return 0;
}

// ---------------------------------------------------------------- monster name length limits
// 0x5CC050 builds a monster name for display: mode 0 is copied into a fixed buffer of the
// monster record (strcpy to +4), modes 1 and 2 only go into string objects for lists.
// Names are cut with Left(): 20 bytes when identified, 14 when not (then shown as ?name?).
// That is 6 / 4 Japanese characters. For modes 1 and 2 the limits are raised to 30 / 21 bytes
// (10 / 7 characters, about the same width as the English limits). Mode 0 is left alone.
static void patch_name_limits() {
    struct { uint32_t va; uint8_t from, to; } p[] = {
        {0x5CC26D, 0x14, 30}, {0x5CC2B7, 0x0E, 21},   // mode 1 (plural): identified / unidentified
        {0x5CC3EC, 0x0E, 21},                         // mode 2: unidentified
    };
    int ok = 0;
    for (auto& e : p) {
        uint8_t* a = (uint8_t*)VA(e.va);
        if (a[-1] != 0x6A || a[0] != e.from) { logf("name limit at %08X not as expected, skipped\n", e.va); continue; }
        DWORD old;
        VirtualProtect(a, 1, PAGE_EXECUTE_READWRITE, &old);
        a[0] = e.to;
        VirtualProtect(a, 1, old, &old);
        FlushInstructionCache(GetCurrentProcess(), a, 1);
        ok++;
    }
    logf("name limits patched: %d\n", ok);
}

// debug: make the monster name builder (0x5CC050) treat every monster as identified, so that
// identified names and group names can be checked on screen early in the game
static void force_identified() {
    uint8_t* a = (uint8_t*)VA(0x5CC0C6);
    static const uint8_t exp[] = {0x8A, 0x44, 0x02, 0x31};   // mov al, [edx+eax+0x31]
    if (memcmp(a, exp, 4) != 0) { logf("force_identified: bytes not as expected\n"); return; }
    DWORD old;
    VirtualProtect(a, 4, PAGE_EXECUTE_READWRITE, &old);
    a[0] = 0xB0; a[1] = 0x01; a[2] = 0x90; a[3] = 0x90;      // mov al, 1
    VirtualProtect(a, 4, old, &old);
    FlushInstructionCache(GetCurrentProcess(), a, 4);
    logf("force_identified: on\n");
}

// ---------------------------------------------------------------- Japanese archive (drop-in install)
// The original BUNDLE-Z.RSF is never modified. grimjp/jp_bundle.pat (tools/make_dist.py) holds the
// difference to the Japanese archive: copy-from-original instructions plus the replaced entries.
// On the first launch (or when the original or the .pat file changes) the Japanese archive is
// built from the player's own original into grimjp/cache/BUNDLE-Z.RSF, and the game's
// CreateFileA/W calls for BUNDLE-Z.RSF are redirected to it. If the original archive does not
// match (e.g. a different game version), nothing is redirected and the game stays in English.
static char g_dir[MAX_PATH];             // folder of version.dll, with trailing backslash
static int g_bundle_state;               // 0 = not tried, 1 = ready, -1 = failed
static char g_bundle_path[MAX_PATH];
static wchar_t g_bundle_pathw[MAX_PATH];
static CRITICAL_SECTION g_bundle_cs;
typedef HANDLE(WINAPI* cfa_fn)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HANDLE(WINAPI* cfw_fn)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static cfa_fn g_cfa;
static cfw_fn g_cfw;

static uint32_t crc32_update(uint32_t crc, const uint8_t* p, size_t n) {
    static uint32_t tab[256];
    if (!tab[1]) for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        tab[i] = c;
    }
    crc = ~crc;
    while (n--) crc = tab[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

struct MappedFile {
    HANDLE f = INVALID_HANDLE_VALUE, m = nullptr; const uint8_t* p = nullptr; uint32_t size = 0;
    bool open(const char* path) {
        f = g_cfa ? g_cfa(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr)
                  : CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
        if (f == INVALID_HANDLE_VALUE) return false;
        size = GetFileSize(f, nullptr);
        if (!size) return false;
        m = CreateFileMappingA(f, nullptr, PAGE_READONLY, 0, 0, nullptr);
        if (!m) return false;
        p = (const uint8_t*)MapViewOfFile(m, FILE_MAP_READ, 0, 0, 0);
        return p != nullptr;
    }
    ~MappedFile() {
        if (p) UnmapViewOfFile(p);
        if (m) CloseHandle(m);
        if (f != INVALID_HANDLE_VALUE) CloseHandle(f);
    }
};

static bool file_stamp(const char* path, char* out, size_t n) {
    WIN32_FILE_ATTRIBUTE_DATA a;
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &a)) return false;
    sprintf_s(out, n, "%u-%08X%08X", a.nFileSizeLow, a.ftLastWriteTime.dwHighDateTime, a.ftLastWriteTime.dwLowDateTime);
    return true;
}

// The warning runs on its own thread: the game is already in full-screen mode when it opens the
// archive, so a modal box on the game's thread would be hidden behind it and stop the game.
static DWORD WINAPI bundle_warning(LPVOID) {
    MessageBoxW(nullptr,
        L"日本語化データ（grimjp\\jp_bundle.pat）を使えませんでした。\n"
        L"ゲームの版が違うか、ファイルが壊れている可能性があります。\n"
        L"このまま英語で起動します。詳しくは grimjp.log を見てください。",
        L"Grimoire 日本語化", MB_OK | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND);
    return 0;
}

static void bundle_fail(const char* why) {
    logf("jp archive: %s - the game runs with the original (English) archive\n", why);
    g_ui_off = true;
    HANDLE t = CreateThread(nullptr, 0, bundle_warning, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
}

static bool build_bundle(const char* orig_path, const char* pat, const char* cache, const char* tmp) {
    DWORD t0 = GetTickCount();
    MappedFile P, O;
    if (!P.open(pat) || P.size < 32 || memcmp(P.p, "GJPP", 4) != 0 || *(const uint32_t*)(P.p + 4) != 1) {
        bundle_fail("jp_bundle.pat is missing or broken"); return false;
    }
    const uint32_t* h = (const uint32_t*)(P.p + 8);
    uint32_t orig_size = h[0], orig_crc = h[1], new_size = h[2], new_crc = h[3], nops = h[4], lit = h[5];
    const uint32_t* ops = h + 6;
    if (32 + 12ull * nops + lit != P.size) { bundle_fail("jp_bundle.pat has a wrong size"); return false; }
    const uint8_t* pool = (const uint8_t*)(ops + 3 * (size_t)nops);
    if (!O.open(orig_path)) { bundle_fail("cannot read the original archive"); return false; }
    if (O.size != orig_size || crc32_update(0, O.p, O.size) != orig_crc) {
        logf("jp archive: original size %u (expected %u)\n", O.size, orig_size);
        bundle_fail("the original BUNDLE-Z.RSF is not the expected version"); return false;
    }
    CreateDirectoryA(cache, nullptr);
    HANDLE out = g_cfa(tmp, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, 0, nullptr);
    if (out == INVALID_HANDLE_VALUE) { bundle_fail("cannot write to grimjp\\cache"); return false; }
    uint32_t crc = 0, total = 0; bool ok = true;
    for (uint32_t i = 0; i < nops && ok; i++) {
        uint32_t kind = ops[i * 3], src = ops[i * 3 + 1], len = ops[i * 3 + 2];
        const uint8_t* from = kind == 0 ? O.p : pool;
        uint32_t lim = kind == 0 ? O.size : lit;
        if (src > lim || len > lim - src) { ok = false; break; }
        DWORD w = 0;
        ok = WriteFile(out, from + src, len, &w, nullptr) && w == len;
        crc = crc32_update(crc, from + src, len); total += len;
    }
    CloseHandle(out);
    if (!ok || total != new_size || crc != new_crc) {
        DeleteFileA(tmp); bundle_fail("building the Japanese archive failed"); return false;
    }
    if (!MoveFileExA(tmp, g_bundle_path, MOVEFILE_REPLACE_EXISTING)) {
        DeleteFileA(tmp); bundle_fail("cannot rename the Japanese archive"); return false;
    }
    logf("jp archive: built %s (%u bytes, %u ms)\n", g_bundle_path, total, GetTickCount() - t0);
    return true;
}

// builds (if needed) the Japanese archive; returns true when g_bundle_path is usable
static bool ensure_bundle(const char* orig_path) {
    EnterCriticalSection(&g_bundle_cs);
    if (!g_bundle_state) {
        g_bundle_state = -1;
        char pat[MAX_PATH], cache[MAX_PATH], stampf[MAX_PATH], tmp[MAX_PATH];
        sprintf_s(pat, "%sgrimjp\\jp_bundle.pat", g_dir);
        sprintf_s(cache, "%sgrimjp\\cache", g_dir);
        sprintf_s(g_bundle_path, "%s\\BUNDLE-Z.RSF", cache);
        sprintf_s(stampf, "%s\\stamp.txt", cache);
        sprintf_s(tmp, "%s\\BUNDLE-Z.tmp", cache);
        char s_orig[64], s_pat[64], want[160], have[160] = {0};
        if (!file_stamp(pat, s_pat, sizeof s_pat)) logf("jp archive: %s not found, not redirecting\n", pat);
        else if (!file_stamp(orig_path, s_orig, sizeof s_orig)) logf("jp archive: original %s not found\n", orig_path);
        else {
            sprintf_s(want, "%s %s", s_orig, s_pat);
            FILE* f = nullptr;
            if (!fopen_s(&f, stampf, "rb") && f) { fgets(have, sizeof have, f); fclose(f); }
            if (strcmp(want, have) == 0 && GetFileAttributesA(g_bundle_path) != INVALID_FILE_ATTRIBUTES) {
                logf("jp archive: using %s\n", g_bundle_path);
                g_bundle_state = 1;
            } else if (build_bundle(orig_path, pat, cache, tmp)) {
                f = nullptr;
                if (!fopen_s(&f, stampf, "wb") && f) { fputs(want, f); fclose(f); }
                g_bundle_state = 1;
            }
        }
        if (g_bundle_state > 0) MultiByteToWideChar(CP_ACP, 0, g_bundle_path, -1, g_bundle_pathw, MAX_PATH);
    }
    bool ok = g_bundle_state > 0;
    LeaveCriticalSection(&g_bundle_cs);
    return ok;
}

static bool is_bundle_name(const char* p) {
    const char* b = p;
    for (const char* q = p; *q; q++) if (*q == '\\' || *q == '/' || *q == ':') b = q + 1;
    return _stricmp(b, "BUNDLE-Z.RSF") == 0;
}

static HANDLE WINAPI hk_CreateFileA(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disp,
                                    DWORD flags, HANDLE tmpl) {
    if (name && !(acc & (GENERIC_WRITE | GENERIC_ALL)) && is_bundle_name(name)) {
        char full[MAX_PATH];
        if (GetFullPathNameA(name, MAX_PATH, full, nullptr) && ensure_bundle(full))
            return g_cfa(g_bundle_path, acc, share, sa, disp, flags, tmpl);
    }
    return g_cfa(name, acc, share, sa, disp, flags, tmpl);
}

static HANDLE WINAPI hk_CreateFileW(LPCWSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disp,
                                    DWORD flags, HANDLE tmpl) {
    if (name && !(acc & (GENERIC_WRITE | GENERIC_ALL))) {
        char a[MAX_PATH];
        if (WideCharToMultiByte(CP_ACP, 0, name, -1, a, MAX_PATH, nullptr, nullptr) && is_bundle_name(a)) {
            char full[MAX_PATH];
            if (GetFullPathNameA(a, MAX_PATH, full, nullptr) && ensure_bundle(full))
                return g_cfw(g_bundle_pathw, acc, share, sa, disp, flags, tmpl);
        }
    }
    return g_cfw(name, acc, share, sa, disp, flags, tmpl);
}

// replaces the exe's import table entries for kernel32 CreateFileA / CreateFileW
static void hook_create_file() {
    InitializeCriticalSection(&g_bundle_cs);
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)g_base;
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(g_base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    int n = 0;
    for (IMAGE_IMPORT_DESCRIPTOR* d = (IMAGE_IMPORT_DESCRIPTOR*)(g_base + dd.VirtualAddress); d->Name; d++) {
        if (_stricmp((const char*)(g_base + d->Name), "KERNEL32.dll") != 0) continue;
        IMAGE_THUNK_DATA* names = (IMAGE_THUNK_DATA*)(g_base + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        IMAGE_THUNK_DATA* iat = (IMAGE_THUNK_DATA*)(g_base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, iat++) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            const char* fn = (const char*)((IMAGE_IMPORT_BY_NAME*)(g_base + names->u1.AddressOfData))->Name;
            void* hook = nullptr;
            if (strcmp(fn, "CreateFileA") == 0) { g_cfa = (cfa_fn)iat->u1.Function; hook = (void*)hk_CreateFileA; }
            else if (strcmp(fn, "CreateFileW") == 0) { g_cfw = (cfw_fn)iat->u1.Function; hook = (void*)hk_CreateFileW; }
            if (!hook) continue;
            DWORD old;
            VirtualProtect(&iat->u1.Function, sizeof(void*), PAGE_READWRITE, &old);
            iat->u1.Function = (uintptr_t)hook;
            VirtualProtect(&iat->u1.Function, sizeof(void*), old, &old);
            n++;
        }
    }
    logf("archive redirect: %d imports hooked\n", n);
}

static bool install_hooks() {
    g_base = (uintptr_t)GetModuleHandleA(nullptr);
    for (int i = 0; i < H_COUNT; i++) {
        uint8_t* p = (uint8_t*)VA(g_hooks[i].va);
        if (memcmp(p, g_hooks[i].expect, g_hooks[i].nbytes) != 0) {
            logf("unexpected bytes at %08X, hooks disabled (different game build?)\n", g_hooks[i].va);
            return false;
        }
    }
    for (int i = 0; i < H_COUNT; i++) {
        uint8_t* p = (uint8_t*)VA(g_hooks[i].va);
        int nb = g_hooks[i].nbytes;
        uint8_t* t = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
        memcpy(t, p, nb);
        t[nb] = 0xE9; *(int32_t*)(t + nb + 1) = (int32_t)((p + nb) - (t + nb + 5));
        g_hooks[i].tramp = (str_fn)t;
        DWORD old;
        VirtualProtect(p, nb, PAGE_EXECUTE_READWRITE, &old);
        p[0] = 0xE9; *(int32_t*)(p + 1) = (int32_t)((uint8_t*)g_impl[i] - (p + 5));
        for (int k = 5; k < nb; k++) p[k] = 0x90;
        VirtualProtect(p, nb, old, &old);
        FlushInstructionCache(GetCurrentProcess(), p, nb);
    }
    patch_ctype_calls();
    hook_create_file();
    g_debug_mid = GetPrivateProfileIntA("debug", "trace_mid", 0, g_ini_path);
    g_trace_broken = GetPrivateProfileIntA("debug", "trace_broken", 0, g_ini_path);
    g_trace_tilde = GetPrivateProfileIntA("debug", "trace_tilde", 0, g_ini_path);
    patch_name_limits();
    if (GetPrivateProfileIntA("debug", "force_identified", 0, g_ini_path)) force_identified();
    hook_mid();
    if (GetPrivateProfileIntA("debug", "toupper_probe", 0, g_ini_path)) CreateThread(nullptr, 0, toupper_probe, nullptr, 0, nullptr);
    g_wdraw_tramp = (wdraw_fn)g_hooks[H_WDRAW].tramp;
    g_wmeasure_tramp = (wmeasure_fn)g_hooks[H_WMEASURE].tramp;
    logf("hooks installed, image base %08X\n", (unsigned)g_base);
    return true;
}

static void load_settings(HMODULE self) {
    char ini[MAX_PATH];
    GetModuleFileNameA(self, ini, MAX_PATH);
    char* sl = strrchr(ini, '\\'); if (sl) sl[1] = 0;
    strcpy_s(g_dir, ini);
    char logp[MAX_PATH]; strcpy_s(logp, ini); strcat_s(logp, "grimjp.log");
    strcat_s(ini, "grimjp.ini");
    strcpy_s(g_ini_path, ini);
    wchar_t wini[MAX_PATH]; MultiByteToWideChar(CP_ACP, 0, ini, -1, wini, MAX_PATH);
    GetPrivateProfileStringW(L"font", L"face", L"MS Gothic", g_face, 64, wini);
    g_size_adjust = GetPrivateProfileIntW(L"font", L"size_adjust", 0, wini);
    g_debug = GetPrivateProfileIntW(L"debug", L"log", 0, wini);
    g_small_max = GetPrivateProfileIntW(L"font", L"small_max_cell", 9, wini);
    if (GetPrivateProfileIntW(L"debug", L"enable_log", 1, wini)) g_log = _fsopen(logp, "w", _SH_DENYNO);
    char smallp[MAX_PATH]; strcpy_s(smallp, logp);
    char* s2 = strrchr(smallp, '\\'); if (s2) s2[1] = 0;
    char fbp[MAX_PATH]; strcpy_s(fbp, smallp);
    strcat_s(smallp, "grimjp\\misaki8.bin");
    strcat_s(fbp, "grimjp\\tiny_fallback.txt");
    load_small(smallp);
    g_fallback_max = GetPrivateProfileIntW(L"font", L"fallback_max_cell", 6, wini);
    load_fallback(fbp);
    char uip[MAX_PATH]; strcpy_s(uip, fbp);
    char* s3 = strrchr(uip, '\\'); if (s3) s3[1] = 0;
    char colp[MAX_PATH]; strcpy_s(colp, uip);
    strcat_s(uip, "ui_strings.txt");
    load_ui(uip);
    wchar_t wc[16];
    GetPrivateProfileStringW(L"font", L"widget_color", L"C8A0FF", wc, 16, wini);
    g_widget_rgb = wcstoul(wc, nullptr, 16);
    g_widget_index = GetPrivateProfileIntW(L"font", L"widget_color_index", 49, wini);
    g_collect = GetPrivateProfileIntW(L"debug", L"collect_ascii", 0, wini);
    if (g_collect) { strcat_s(colp, "collected_ascii.txt"); g_collect_f = _fsopen(colp, "a", _SH_DENYNO); }
    logf("ui strings: %u exact, %u patterns, collect=%d\n", (unsigned)g_ui_exact.size(), (unsigned)g_ui_glob.size(), g_collect);
    logf("grimjp loaded. face=%ls size_adjust=%d small_font=%u glyphs (<= %d px) fallback=%u (<= %d px)\n",
         g_face, g_size_adjust, (unsigned)g_small.size(), g_small_max, (unsigned)g_fallback.size(), g_fallback_max);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        InitializeCriticalSection(&g_cs);
        load_real();
        load_settings(h);
        // only hook the game itself
        char exe[MAX_PATH]; GetModuleFileNameA(nullptr, exe, MAX_PATH);
        const char* b = strrchr(exe, '\\'); b = b ? b + 1 : exe;
        if (_stricmp(b, "Grimoire.exe") == 0 && install_hooks()) {
            char ep[MAX_PATH]; GetModuleFileNameA(h, ep, MAX_PATH);
            char* sl = strrchr(ep, '\\'); if (sl) sl[1] = 0;
            strcat_s(ep, "grimjp\\exe_strings.txt");
            patch_exe_strings(ep);
        }
    }
    return TRUE;
}
