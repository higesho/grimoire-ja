"""Translation rules for the string tables: what must stay English and what has structure.

kind(file, section) ->
  'keep'   : internal identifiers or words the player types / the game matches. Do not translate.
  'csv'    : comma separated fields; keep the number of fields, '*', '-', '~' and digit-only fields
  'riddle' : "question,ANSWER" - translate the question, keep the typed answer (last field)
  'text'   : normal text
"""
import re

KEEP_FILES = {
    'LOGFLAGS.TXT',   # editor documentation, never shown
    'HELP.LST',       # image file names
}

# MASTER.TXT sections
KEEP_SECTIONS = {
    'LISTS', 'ACTIONS', 'ANIMATIONS', 'ATMOSPHERICS', 'EFXANIMS', 'LIGHTING', 'LOGICFLAGS',
    'NPCLOGIC', 'SCENES', 'SEFX', 'MIDI', 'UNIQUE', 'GLOBALS', 'MYSTERY',   # internal names
    'CHEATS',        # cheat codes (typed, stored reversed)
    'PASSWORDS',     # answers the player types (YES/NO/...)
    'CLIMBER',       # typed verbs (climb up / descend)
    'NPCTRIGS',      # dialogue question words matched by the parser (WHO/WHAT/...)
    'FSUGGEST', 'MSUGGEST',   # suggested character names (typed into the ASCII name field)
    # not seen on screen yet; kept English to be safe (check during testing):
    'AMBIENCE', 'SPELLTYPE', 'IMPORT', 'PERKS',
}
CSV_SECTIONS = {'ITEMS', 'MONSTERS', 'MULTICHOICE', 'OPDESC'}
RIDDLE_FILES = {'LOCKHINT.TXT'}


def kind(fname, section):
    base = fname[:-4] if fname.endswith('.txt') else fname
    if base in KEEP_FILES:
        return 'keep'
    if base in RIDDLE_FILES:
        return 'riddle'
    if base == 'MASTER.TXT':
        s = section.lstrip('@')
        if s in KEEP_SECTIONS:
            return 'keep'
        if s in CSV_SECTIONS:
            return 'csv'
    return 'text'


def sections(lines):
    """lines: iterable of (num, text) in file order -> {num: section name}"""
    out, cur = {}, ''
    for num, text in lines:
        if text.startswith('@') and re.fullmatch(r'@[A-Z]+', text):
            cur = text
        out[num] = cur
    return out


FIXED = re.compile(r'^(\*|-|~|\d+|.*~)$')


def check(fname, section, orig, new):
    """Returns (use_new, level, message): level None / 'warn' (change ignored) / 'error'."""
    k = kind(fname, section)
    if new == orig:
        return True, None, None
    if orig.startswith('@') or orig in ('[pag]', '[new]'):
        return False, 'error', f'{fname} {section}: control line must not change: {orig!r}'
    if k == 'keep':
        return False, 'warn', f'{fname} {section}: section must stay English (ignored): {new!r}'
    if k == 'csv':
        o, n = orig.split(','), new.split(',')
        if len(o) != len(n):
            return False, 'error', f'{fname} {section}: field count {len(n)} != {len(o)}: {new!r}'
        for a, b in zip(o, n):
            if a.strip() in ('*', '-') or re.fullmatch(r'\d+', a.strip()):
                if a != b:
                    return False, 'error', f'{fname} {section}: fixed field {a!r} changed: {new!r}'
    if k == 'riddle':
        o, n = orig.rsplit(',', 1), new.rsplit(',', 1)
        if len(n) != 2 or n[1] != o[1]:
            return False, 'error', f'{fname}: the answer after the last comma must stay {o[1]!r}: {new!r}'
    return True, None, None
