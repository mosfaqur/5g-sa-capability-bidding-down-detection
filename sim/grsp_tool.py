#!/usr/bin/env python3
"""
grsp_tool.py — OYEITIMES .grsp file parser and generator
Usage:
  python3 grsp_tool.py parse  <file.grsp>          # show all fields
  python3 grsp_tool.py gen    <template.grsp> <out> # generate new grsp
"""

import sys
import re

# ── Parser ─────────────────────────────────────────────────────────────────

def parse_grsp(path):
    """Return list of (control_num, name, state, value) tuples preserving order."""
    controls = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().replace('\r\n', '\n')

    current = {}
    for line in content.split('\n'):
        line = line.strip()
        m = re.match(r'^Control(\d+)$', line)
        if m:
            if current:
                controls.append(current)
            current = {'num': int(m.group(1)), 'name': None, 'state': None, 'value': None}
        elif line.startswith('Name=') and current is not None:
            current['name'] = line[5:]
        elif line.startswith('State=') and current is not None:
            current['state'] = line[6:]
        elif line.startswith('Value=') and current is not None:
            current['value'] = line[6:]
    if current:
        controls.append(current)

    return controls


def controls_to_dict(controls):
    """Return {name: value} dict for named controls that have values."""
    return {c['name']: c['value'] for c in controls
            if c['name'] and c['value'] is not None}


def write_grsp(controls, path, cardinfo=None):
    """Write controls list back to .grsp file, preserving CardInfo block."""
    lines = ['GRSIMWrite Data file', 'V 1.0', '']
    for c in controls:
        lines.append(f"Control{c['num']}")
        if c['name']:
            lines.append(f"Name={c['name']}")
        if c['state'] is not None:
            lines.append(f"State={c['state']}")
        if c['value'] is not None:
            lines.append(f"Value={c['value']}")
        lines.append('')
    if cardinfo:
        lines.append('')
        lines.extend(cardinfo)
    with open(path, 'w', newline='\r\n') as f:
        f.write('\n'.join(lines))
    print(f"Written: {path}")


def extract_cardinfo(path):
    """Extract the CardInfo block at the end of a .grsp file."""
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.rstrip('\r\n') for l in f]
    cardinfo = [l for l in lines if l.startswith('CardInfo.')]
    return cardinfo


def set_field(controls, name, value, state='-1'):
    """Update a named control's value and state in place."""
    for c in controls:
        if c['name'] == name:
            c['value'] = value
            c['state'] = state
            return True
    return False


# ── IMSI encoding helpers ──────────────────────────────────────────────────

def encode_imsi_raw(imsi_str):
    """Encode IMSI string to 9 raw bytes (EF_IMSI format)."""
    digits = [int(x) for x in imsi_str]
    b = [0x08, (digits[0] << 4) | 0x09]   # length=8, parity=9 (odd)
    for i in range(1, len(digits), 2):
        lo = digits[i]
        hi = digits[i + 1] if i + 1 < len(digits) else 0xF
        b.append((hi << 4) | lo)
    while len(b) < 9:
        b.append(0xFF)
    return bytes(b[:9])


def imsi15_to_imsi18(imsi15):
    """Convert 15-digit IMSI to the 18-digit display format used by OYEITIMES tool."""
    raw = encode_imsi_raw(imsi15)
    return ''.join(f'{((b & 0xF) << 4) | (b >> 4):02X}' for b in raw)


# ── Profiles ───────────────────────────────────────────────────────────────

_BASE = {
    'acc':       '0001',
    'spn':       'srsRAN Test',
    'smsp':      '',
    'fplmn':     '',
    'hplmn_lte': '00101:C080',
    'hpplmn':    'FF',
    'ad':        '00000002',
    'ecc_gsm':   '112; 911',
    'ecc_lte':   '112:Emergency:1F; 911:Emergency:1F',
    'gid1':      '',
    'gid2':      '',
    'oplmn':     '',
    'ehplmn':    '',
}

PROFILES = {
    'srsran': {
        **_BASE,
        'desc': 'srsRAN / Open5GS test network (MCC=001 MNC=01)',
        'imsi': '001010123456789',
        'ki':   'REDACTED',
        'opc':  'REDACTED',
    },
    'ue1': {
        **_BASE,
        'desc': 'srsRAN Test UE1 — IMSI 001010000000001',
        'imsi': '001010000000001',
        'ki':   'REDACTED',
        'opc':  'REDACTED',
    },
    'ue2': {
        **_BASE,
        'desc': 'srsRAN Test UE2 — IMSI 001010000000002',
        'imsi': '001010000000002',
        'ki':   'REDACTED',
        'opc':  'REDACTED',
    },
}


def apply_profile(controls, profile):
    p = profile
    imsi15  = p['imsi']
    imsi18  = imsi15_to_imsi18(imsi15)

    fields = {
        # GSM
        'EditGSM_IMSI15':   (imsi15,        '-1'),
        'EditGSM_IMSI18':   (imsi18,         '0'),   # disabled, IMSI15 is used
        'EditGSM_KI':       (p['ki'],        '-1'),
        'EditGSM_ACC':      (p['acc'],       '-1'),
        'EditGSM_SPN':      (p['spn'],       '-1'),
        'EditGSM_SMSP':     (p['smsp'],      '-1'),
        'EditGSM_FPLMN':    (p['fplmn'],     '-1'),
        'EditGSM_AD':       (p['ad'],        '-1'),
        'EditGSM_ECC':      (p['ecc_gsm'],   '-1'),
        'EditGSM_GID1':     (p['gid1'],      '-1'),
        'EditGSM_GID2':     (p['gid2'],      '-1'),
        'EditGSM_EHPLMN':   (p['ehplmn'],    '-1'),
        # LTE / USIM
        'EditLTE_IMSI15':   (imsi15,        '-1'),
        'EditLTE_IMSI18':   (imsi18,         '0'),
        'EditLTE_KI':       (p['ki'],        '-1'),
        'EditLTE_OPC':      (p['opc'],       '-1'),
        'EditLTE_OP':       ('',              '0'),   # use OPc not OP
        'EditLTE_ACC':      (p['acc'],       '-1'),
        'EditLTE_SPN':      (p['spn'],       '-1'),
        'EditLTE_SMSP':     (p['smsp'],      '-1'),
        'EditLTE_FPLMN':    (p['fplmn'],     '-1'),
        'EditLTE_AD':       (p['ad'],        '-1'),
        'EditLTE_ECC':      (p['ecc_lte'],   '-1'),
        'EditLTE_GID1':     (p['gid1'],      '-1'),
        'EditLTE_GID2':     (p['gid2'],      '-1'),
        'EditLTE_HPLMN':    (p['hplmn_lte'], '-1'),
        'EditLTE_HPPLMN':   (p['hpplmn'],   '-1'),
        'EditLTE_OPLMN':    (p['oplmn'],     '-1'),
        'EditLTE_EHPLMN':   (p['ehplmn'],    '-1'),
        # Ensure OPc radio button selected
        'RadLTE_OPC':       ('-1',           '-1'),
        'RadLTE_OP':        ('0',             '-1'),
        # Ensure IMSI15 radio selected
        'RadGSM_IMSI15':    ('-1',           '-1'),
        'RadGSM_IMSI18':    ('0',            '-1'),
        'RadLTE_IMSI15':    ('-1',           '-1'),
        'RadLTE_IMSI18':    ('0',            '-1'),
        # Algorithm: MILENAGE
        'RadGSM_MLG':       ('0',            '-1'),
        'RadLTE_MLG':       ('-1',           '-1'),
        'RadLTE_XOR':       ('0',             '0'),
    }

    for name, (value, state) in fields.items():
        if not set_field(controls, name, value, state):
            print(f"  [WARN] field not found in template: {name}")

    return imsi15, imsi18


# ── CLI ────────────────────────────────────────────────────────────────────

DISPLAY_FIELDS = [
    ('EditICCID',       'ICCID'),
    ('EditADM',         'ADM'),
    ('EditATR',         'ATR'),
    ('EditType',        'Card type'),
    ('EditGSM_IMSI15',  'GSM IMSI'),
    ('EditGSM_KI',      'GSM Ki'),
    ('EditGSM_ACC',     'GSM ACC'),
    ('EditGSM_SPN',     'GSM SPN'),
    ('EditGSM_SMSP',    'GSM SMSP'),
    ('EditGSM_FPLMN',   'GSM FPLMN'),
    ('EditGSM_AD',      'GSM AD'),
    ('EditGSM_ECC',     'GSM ECC'),
    ('EditGSM_HPLMN',   'GSM HPLMN'),
    ('EditLTE_IMSI15',  'LTE IMSI'),
    ('EditLTE_KI',      'LTE Ki'),
    ('EditLTE_OPC',     'LTE OPc'),
    ('EditLTE_OP',      'LTE OP'),
    ('EditLTE_ACC',     'LTE ACC'),
    ('EditLTE_SPN',     'LTE SPN'),
    ('EditLTE_SMSP',    'LTE SMSP'),
    ('EditLTE_FPLMN',   'LTE FPLMN'),
    ('EditLTE_AD',      'LTE AD'),
    ('EditLTE_ECC',     'LTE ECC'),
    ('EditLTE_HPLMN',   'LTE HPLMN'),
    ('EditLTE_HPPLMN',  'LTE HPPLMN timer'),
    ('EditLTE_OPLMN',   'LTE OPLMN'),
]


def cmd_parse(path):
    controls = parse_grsp(path)
    d = controls_to_dict(controls)
    print(f"\n{'='*55}")
    print(f"  {path}")
    print(f"{'='*55}")
    for field, label in DISPLAY_FIELDS:
        v = d.get(field, '')
        if v:
            print(f"  {label:<22} {v}")
    print()


def cmd_gen(template_path, out_path, profile_name='srsran'):
    if profile_name not in PROFILES:
        print(f"Unknown profile '{profile_name}'. Available: {list(PROFILES)}")
        sys.exit(1)

    profile = PROFILES[profile_name]
    print(f"\nGenerating '{profile['desc']}'")
    print(f"  Template : {template_path}")
    print(f"  Output   : {out_path}\n")

    controls = parse_grsp(template_path)
    cardinfo = extract_cardinfo(template_path)
    imsi15, imsi18 = apply_profile(controls, profile)

    print(f"  IMSI15   : {imsi15}")
    print(f"  IMSI18   : {imsi18}")
    print(f"  Ki       : {profile['ki']}")
    print(f"  OPc      : {profile['opc']}")
    print(f"  ACC      : {profile['acc']}")
    print(f"  SPN      : {profile['spn']}")
    print(f"  AD       : {profile['ad']}  (MNC len=2)")
    if cardinfo:
        print(f"  CardInfo : {len(cardinfo)} lines preserved from template")
    print()

    write_grsp(controls, out_path, cardinfo=cardinfo)

    print("\nsrsRAN / Open5GS HSS entry:")
    print(f"  IMSI : {imsi15}")
    print(f"  K    : {profile['ki']}")
    print(f"  OPc  : {profile['opc']}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nAvailable profiles:", list(PROFILES.keys()))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'parse':
        cmd_parse(sys.argv[2])
    elif cmd == 'gen':
        # gen <template> <out> [profile]
        out     = sys.argv[3] if len(sys.argv) > 3 else 'srsran_test.grsp'
        profile = sys.argv[4] if len(sys.argv) > 4 else 'srsran'
        cmd_gen(sys.argv[2], out, profile)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
