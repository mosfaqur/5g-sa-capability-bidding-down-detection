#!/usr/bin/env python3
"""
flash_ue.py — Write IMSI/ACC/AD/SPN to OYEITIMES USIM via standard UICC APDUs.
Ki and OPc must be set via the OYEITOMES Windows tool (proprietary command).

Usage:
    python3 flash_ue.py ue1
    python3 flash_ue.py ue2
    python3 flash_ue.py --verify-only ue1
"""

import sys
from smartcard.System import readers
from smartcard.Exceptions import CardConnectionException

USIM_AID = [0xA0,0x00,0x00,0x00,0x87,0x10,0x02,0xFF,0x86,0xFF,0x03,0x89,0xFF,0xFF,0xFF,0xFF]
ADM_KEY  = [0x38]*8   # 3838383838383838

PROFILES = {
    'ue1': {
        'imsi': '001010000000001',
        'ki':   'REDACTED',   # reminder only — written by Windows tool
        'opc':  'REDACTED',
        'acc':  '0001',
        'ad':   '00000002',
        'spn':  'srsRAN Test',
    },
    'ue2': {
        'imsi': '001010000000002',
        'ki':   'REDACTED',
        'opc':  'REDACTED',
        'acc':  '0001',
        'ad':   '00000002',
        'spn':  'srsRAN Test',
    },
}


# ── APDU helpers ─────────────────────────────────────────────────────────────

def tx(conn, apdu, label=''):
    data, sw1, sw2 = conn.transmit(apdu)
    sw = f'{sw1:02X}{sw2:02X}'
    ok = sw == '9000'
    marker = 'OK' if ok else 'FAIL'
    if label:
        print(f'  [{marker}] {label}: SW={sw}' + (f'  data={bytes(data).hex().upper()}' if data else ''))
    return data, sw1, sw2, ok


def select_aid(conn, aid):
    apdu = [0x00, 0xA4, 0x04, 0x00, len(aid)] + aid
    _, _, _, ok = tx(conn, apdu, 'SELECT USIM AID')
    return ok


def verify_adm(conn):
    apdu = [0x00, 0x20, 0x00, 0x0B, 0x08] + ADM_KEY
    _, sw1, sw2, ok = tx(conn, apdu, 'VERIFY ADM (ref 0x0B)')
    if not ok and sw1 == 0x63:
        tries = sw2 & 0x0F
        print(f'  [WARN] ADM wrong — {tries} tries remaining')
    return ok


def select_ef(conn, fid_hex):
    fid = bytes.fromhex(fid_hex)
    apdu = [0x00, 0xA4, 0x00, 0x00, 0x02] + list(fid)
    _, _, _, ok = tx(conn, apdu, f'SELECT EF {fid_hex}')
    return ok


def read_binary(conn, length):
    apdu = [0x00, 0xB0, 0x00, 0x00, length]
    data, sw1, sw2 = conn.transmit(apdu)
    return bytes(data) if sw1 == 0x90 else None


def update_binary(conn, data_bytes, label):
    apdu = [0x00, 0xD6, 0x00, 0x00, len(data_bytes)] + list(data_bytes)
    _, _, _, ok = tx(conn, apdu, label)
    return ok


# ── Encoding helpers ──────────────────────────────────────────────────────────

def encode_imsi(imsi_str):
    digits = [int(c) for c in imsi_str]
    b = [0x08, (digits[0] << 4) | 0x09]
    for i in range(1, len(digits), 2):
        lo = digits[i]
        hi = digits[i+1] if i+1 < len(digits) else 0xF
        b.append((hi << 4) | lo)
    while len(b) < 9:
        b.append(0xFF)
    return bytes(b[:9])


def decode_imsi(raw):
    if not raw or len(raw) < 2:
        return None
    digits = []
    b1 = raw[1]
    digits.append(str(b1 >> 4))
    for byte in raw[2:]:
        lo = byte & 0x0F
        hi = (byte >> 4) & 0x0F
        if lo == 0xF:
            break
        digits.append(str(lo))
        if hi == 0xF:
            break
        digits.append(str(hi))
    return ''.join(digits)


def encode_acc(acc_hex):
    return bytes.fromhex(acc_hex.zfill(4))


def encode_ad(ad_hex):
    return bytes.fromhex(ad_hex.zfill(8))


def encode_spn(spn_str):
    raw = spn_str.encode('utf-8')
    b = bytes([0x01]) + raw[:16] + bytes([0xFF] * (16 - len(raw[:16])))
    return b


def decode_spn(raw):
    if not raw or len(raw) < 2:
        return None
    return raw[1:].rstrip(b'\xFF').decode('utf-8', errors='replace')


# ── Main flash / verify ───────────────────────────────────────────────────────

def flash(profile_name, verify_only=False):
    p = PROFILES[profile_name]
    action = 'VERIFY' if verify_only else 'FLASH'
    print(f'\n{"="*55}')
    print(f'  {action} — {profile_name.upper()}')
    print(f'  IMSI : {p["imsi"]}')
    print(f'  ACC  : {p["acc"]}')
    print(f'  AD   : {p["ad"]}')
    print(f'  SPN  : {p["spn"]}')
    print(f'{"="*55}\n')

    rs = readers()
    if not rs:
        print('ERROR: no smart card reader found')
        sys.exit(1)
    conn = rs[0].createConnection()
    conn.connect()
    print(f'  ATR  : {bytes(conn.getATR()).hex().upper()}')

    if not select_aid(conn, USIM_AID):
        print('ERROR: failed to select USIM AID')
        sys.exit(1)

    if not verify_only:
        if not verify_adm(conn):
            print('ERROR: ADM verification failed — cannot write')
            sys.exit(1)

    results = {}

    # ── IMSI (EF 6F07, 9 bytes) ───────────────────────────────────────────────
    imsi_raw = encode_imsi(p['imsi'])
    if not verify_only:
        print()
        select_ef(conn, '6F07')
        update_binary(conn, imsi_raw, f'WRITE IMSI {p["imsi"]}')

    select_ef(conn, '6F07')
    raw = read_binary(conn, 9)
    got_imsi = decode_imsi(raw)
    match = got_imsi == p['imsi']
    results['IMSI'] = (p['imsi'], got_imsi, match)
    print(f'  {"[OK] " if match else "[FAIL]"} IMSI read back: {got_imsi}  (raw: {raw.hex().upper() if raw else "None"})')

    # ── ACC (EF 6F78, 2 bytes) ────────────────────────────────────────────────
    acc_raw = encode_acc(p['acc'])
    if not verify_only:
        print()
        select_ef(conn, '6F78')
        update_binary(conn, acc_raw, f'WRITE ACC {p["acc"]}')

    select_ef(conn, '6F78')
    raw = read_binary(conn, 2)
    got_acc = raw.hex().upper() if raw else None
    match = got_acc == p['acc'].upper()
    results['ACC'] = (p['acc'], got_acc, match)
    print(f'  {"[OK] " if match else "[FAIL]"} ACC  read back: {got_acc}')

    # ── AD (EF 6FAD, 4 bytes) ─────────────────────────────────────────────────
    ad_raw = encode_ad(p['ad'])
    if not verify_only:
        print()
        select_ef(conn, '6FAD')
        update_binary(conn, ad_raw, f'WRITE AD {p["ad"]}')

    select_ef(conn, '6FAD')
    raw = read_binary(conn, 4)
    got_ad = raw.hex().upper() if raw else None
    match = got_ad == p['ad'].upper()
    results['AD'] = (p['ad'], got_ad, match)
    print(f'  {"[OK] " if match else "[FAIL]"} AD   read back: {got_ad}')

    # ── SPN (EF 6F46, 17 bytes) ───────────────────────────────────────────────
    spn_raw = encode_spn(p['spn'])
    if not verify_only:
        print()
        select_ef(conn, '6F46')
        update_binary(conn, spn_raw, f'WRITE SPN "{p["spn"]}"')

    select_ef(conn, '6F46')
    raw = read_binary(conn, 17)
    got_spn = decode_spn(raw)
    match = got_spn == p['spn']
    results['SPN'] = (p['spn'], got_spn, match)
    print(f'  {"[OK] " if match else "[FAIL]"} SPN  read back: "{got_spn}"')

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    all_ok = all(v[2] for v in results.values())
    if all_ok:
        print(f'  PASS — all fields verified for {profile_name.upper()}')
        if not verify_only:
            print()
            print(f'  NOTE: Ki and OPc must be written via OYEITIMES Windows tool.')
            print(f'  Ki  = {p["ki"]}')
            print(f'  OPc = {p["opc"]}')
    else:
        print('  FAIL — one or more fields did not match:')
        for field, (expected, got, ok) in results.items():
            if not ok:
                print(f'    {field}: expected={expected}  got={got}')
    print()
    return all_ok


if __name__ == '__main__':
    args = sys.argv[1:]
    verify_only = '--verify-only' in args
    args = [a for a in args if not a.startswith('--')]

    if not args or args[0] not in PROFILES:
        print(__doc__)
        print(f'\nAvailable profiles: {list(PROFILES.keys())}')
        sys.exit(1)

    ok = flash(args[0], verify_only=verify_only)
    sys.exit(0 if ok else 1)
