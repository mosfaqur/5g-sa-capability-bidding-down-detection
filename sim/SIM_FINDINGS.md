# OYEITIMES USIM Card: srsRAN Test Network Findings

Date: 2026-06-16
Platform: Kali Linux (kali-amd64)
Project: comp997/sim, srsRAN private LTE/5G lab

---

## 1. Hardware

| Item | Detail |
|------|--------|
| Reader | Generic USB2.0-CRW Smart Card Reader Interface |
| USB ID | `0bda:0169` (Realtek) |
| Card type | OYEITIMES Blank 4G LTE USIM (SIM Personalize Tools v4.2.11) |
| ATR | `3B:9F:95:80:1F:C7:80:31:A0:73:B6:A1:00:67:CF:32:15:A9:8F:D7:09:50` |
| Card format | UICC / USIM (not legacy GSM SIM) |
| USIM AID | `A0000000871002FF86FF0389FFFFFFFF` |

### Tools installed
```bash
apt install python3-pyscard
git clone https://github.com/osmocom/pysim.git /opt/pysim
pip3 install --break-system-packages --ignore-installed -r /opt/pysim/requirements.txt
```

---

## 2. Default Card Parameters (from OYEITIMES.pdf, last page)

| Parameter | Default Value | Format |
|-----------|--------------|--------|
| ADM code | `3838383838383838` | HEX16/8 (8 bytes) |
| PIN1 | `1234` | ASCII |
| PUK1 | `88888888` | ASCII |

---

## 3. Critical discovery: ADM key reference

pySim uses key reference `0x0A` (ADM1) by default, whilst OYEITIMES cards in fact use `0x0B`
(ADM2). This discrepancy is not merely cosmetic: it caused 1 try to be consumed on key reference
`0x0A` before the correct reference was identified, and, with only 10 tries typically allowed
before a key reference locks permanently, a mismatch of this kind is worth treating seriously
rather than working around by trial and error.

### CHV retry counter probe (no tries consumed, Lc=0 technique)

| Key Ref | Description | Tries Remaining |
|---------|-------------|-----------------|
| `0x0A` | ADM1 (pySim default) | **1** (damaged, do not retry) |
| `0x0B` | ADM2 (OYEITIMES actual) | ~9 |
| `0x0C` | ADM3 | 10 |
| `0x01` | PIN1 | 3 |
| `0x02` | PIN2 | 3 |
| `0x81` | PIN1 (local) | 3 |

### Correct ADM verification APDU
```
00 20 00 0B 08 38 38 38 38 38 38 38 38
CLA INS P1 P2=0x0B Lc=8  <--- ADM bytes --->
```

### Why the pySim `-A` flag failed

`pySim-shell -A 3838383838383838` sends VERIFY CHV to key reference `0x0A`, not `0x0B`, and there
is no CLI flag in pySim-shell to override which CHV reference is targeted. The workaround adopted
here was to send the raw APDU directly, via the `apdu` command, or to drive pyscard itself rather
than going through pySim's higher-level interface.

---

## 4. Card contents (as found, pre-write)

| Field | Value |
|-------|-------|
| ICCID | `REDACTED` |
| IMSI | `REDACTED` |
| MCC | `530` (New Zealand) |
| MNC | `05` (2-digit, Skinny Mobile NZ) |
| MSIN | `2043223945` |
| SPN | `Skinny` |
| ACC | `0x0020` (Access Class 5) |
| EF.AD | `00 00 01 02`, mode=normal, MNC_len=2 |
| Ki | `REDACTED` (write-only, from OYEITIMES tool screenshot) |
| OPc | `REDACTED` (write-only) |
| Algorithm | MILENAGE |

---

## 5. MILENAGE authentication test

An AUTHENTICATE APDU was sent with an all-zero RAND and AUTN:
```
00 88 00 81 22  [10 + 16×0x00 + 10 + 16×0x00]
```
The response, `SW=98 62` (MAC Failure), confirms that MILENAGE is indeed running on the card and
that it correctly rejects an invalid network AUTN token, which is the expected and reassuring
outcome for a card that is genuinely enforcing mutual authentication.

---

## 6. Test network SIM write

### Parameters written

| Field | Old Value | New Value |
|-------|-----------|-----------|
| IMSI | `REDACTED` | `001010123456789` |
| MCC/MNC | 530/05 (Skinny NZ) | 001/01 (srsRAN test) |
| EF.AD (MNC digits) | 2 | 2 |
| EF.ACC | `0x0020` (class 5) | `0x0001` (class 0) |
| SPN | `Skinny` | `srsRAN Test` |

All 5 fields were verified as read back correctly after the write.

### IMSI encoding (for reference)

IMSI `001010123456789` encodes to 9 raw bytes:
```
08 09 10 10 10 32 54 76 98
```
- Byte 0: `0x08`, the length.
- Byte 1: high nibble is digit 1 (`0`), low nibble is parity (`9`, odd).
- Bytes 2 to 8: pairs of digits packed as `(next_digit << 4) | prev_digit`.

### Ki / OPc write status

Ki and OPc proved to be hardware write-protected via the standard `UPDATE BINARY` command
(`SW=6986`), and the OYEITIMES SIM Personalize tool instead uses a proprietary command sequence to
write these values. Updating Ki or OPc therefore requires the OYEITIMES Windows application
(version 4.2.11) rather than any of the standard APDU-level tools used elsewhere in this
investigation. The card's current Ki and OPc values, `REDACTED` in both cases, remain from
previous programming.

---

## 7. srsRAN / Open5GS Configuration

### HSS Subscriber Entry
```yaml
imsi:  "001010123456789"
key:   "REDACTED"
opc:   "REDACTED"
amf:   "8000"
sqn:   "000000000000"
```

### Open5GS MongoDB (dbctl)
```bash
open5gs-dbctl add 001010123456789 REDACTED REDACTED
```

### srsRAN `ue.conf`
```ini
[usim]
mode = soft
algo = milenage
opc  = REDACTED
k    = REDACTED
imsi = 001010123456789
imei = REDACTED
```

### srsRAN `enb.conf` / `gnb.conf`
```ini
mcc = 001
mnc = 01
```

---

## 8. Key Python snippets

### Verify ADM (key ref 0x0B)
```python
from smartcard.System import readers
r = readers()
conn = r[0].createConnection()
conn.connect()

adm = bytes.fromhex("3838383838383838")
apdu = [0x00, 0x20, 0x00, 0x0B, len(adm)] + list(adm)
data, sw1, sw2 = conn.transmit(apdu)
# SW=9000 = success
```

### Check remaining ADM tries (non-destructive)
```python
# Send VERIFY with Lc=0, which queries tries without consuming one
data, sw1, sw2 = conn.transmit([0x00, 0x20, 0x00, 0x0B, 0x00])
# SW=63CX -> X tries remaining
# SW=6983 -> blocked
tries = sw2 & 0x0F  # if sw1 == 0x63
```

### Write IMSI
```python
def encode_imsi(imsi_str):
    digits = [int(c) for c in imsi_str]
    b = [0x08, (digits[0] << 4) | 0x09]  # 0x09 = odd parity
    for i in range(1, len(digits), 2):
        lo = digits[i]
        hi = digits[i+1] if i+1 < len(digits) else 0xF
        b.append((hi << 4) | lo)
    while len(b) < 9:
        b.append(0xFF)
    return bytes(b[:9])

imsi_raw = encode_imsi("001010123456789")
# Then SELECT EF.IMSI (6F07) and UPDATE BINARY with imsi_raw
```

---

## 9. EF file map (OYEITIMES USIM ADF)

| EF FID | Name | Access | Notes |
|--------|------|--------|-------|
| `6F07` | EF.IMSI | R: always, W: ADM `0x0B` | Written successfully |
| `6FAD` | EF.AD | R: always, W: ADM `0x0B` | Written successfully |
| `6F78` | EF.ACC | R: always, W: ADM `0x0B` | Written successfully |
| `6F46` | EF.SPN | R: always, W: ADM `0x0B` | Written successfully |
| `6F38` | EF.UST | R: always | 88 USIM services, EPS MM enabled |
| `2FE2` | EF.ICCID | R: always, W: blocked | `REDACTED` |
| `6F1B` | EF_Ki | W: proprietary only | OYEITIMES tool required |
| `6F99` | EF.OPc | W: proprietary only | OYEITIMES tool required |

---

## 10. OYEITIMES .grsp file format

The OYEITIMES SIM Personalize Tools uses `.grsp` files to save and load SIM configuration. These
are INI-style text files built from `Control<N>` blocks, and understanding their structure was
what made it possible to generate a fresh srsRAN configuration programmatically rather than
through the vendor's own Windows application.

### File structure

```
GRSIMWrite Data file
V 1.0

Control0
Name=<field_name>
State=<-1|0>
Value=<field_value>

Control1
...

[CardInfo section at end]
CardInfo.Code=LY14
CardInfo.Name=LTE
CardInfo.ATR=3B9F95801FC78031A073B6A10067CF3215A98FD70950
CardInfo.AID_USIM=A0000000871002FF86FF0389FFFFFFFF
...
```

- `State=-1` means enabled or active; `State=0` means disabled.
- Line endings are CRLF.
- The `CardInfo.*` lines at the end identify the physical card type, and the tool requires them.

### Key field names

| Field name | Content |
|------------|---------|
| `EditICCID` | ICCID (hex, 20 chars) |
| `EditGSM_IMSI15` / `EditLTE_IMSI15` | 15-digit IMSI string |
| `EditGSM_KI` / `EditLTE_KI` | Ki (32 hex chars) |
| `EditLTE_OPC` / `EditLTE_OP` | OPc or OP (32 hex chars) |
| `RadLTE_OPC` / `RadLTE_OP` | `-1` = select OPc, `0` = deselect |
| `RadLTE_MLG` | `-1` = MILENAGE selected |
| `EditGSM_ACC` / `EditLTE_ACC` | ACC (4 hex chars) |
| `EditGSM_SPN` / `EditLTE_SPN` | SPN string |
| `EditGSM_AD` / `EditLTE_AD` | AD bytes (8 hex chars, e.g. `00000002`) |
| `EditLTE_HPLMN` | HPLMN list for LTE: `MCCMNC:AccessTech`, e.g. `00101:C080` |
| `EditLTE_HPPLMN` | HPPLMN timer (`FF` = default) |
| `EditGSM_ECC` / `EditLTE_ECC` | Emergency call codes |

### Captured .grsp files

| File | Source | Notes |
|------|--------|-------|
| `default.grsp` | Blank/factory OYEITIMES USIM | ICCID=FFF...F, Ki/OPc=REDACTED, no operator data; the canonical blank template |
| `GRSIMWrite.grsp` | Card after Skinny NZ provisioning | IMSI=REDACTED, SPN=Skinny, SMSP=+6427... |
| `OneNZ_SIM.grsp` | Different card (Vodafone NZ) | IMSI=REDACTED, SPN=vodafone NZ |
| `srsRAN_test.grsp` | Generated from `default.grsp` | Ready to flash for srsRAN lab use |

### Generating a new config

```bash
python3 grsp_tool.py parse default.grsp        # inspect blank template
python3 grsp_tool.py gen default.grsp out.grsp  # generate srsRAN config
python3 grsp_tool.py parse srsRAN_test.grsp     # verify output
```

`grsp_tool.py`, at `/root/comp997/sim/grsp_tool.py`, uses `default.grsp` as the canonical
blank-SIM template, applies srsRAN test network values (IMSI, Ki, OPc, ACC, SPN, AD, HPLMN) on
top of it, and preserves the `CardInfo.*` block from the template unchanged.

### Blank SIM factory defaults (from `default.grsp`)

| Field | Factory value |
|-------|--------------|
| ICCID | `FFFFFFFFFFFFFFFFFFFF` |
| IMSI | `FFFFFFFFFFFFFFF` (all F) |
| Ki | `REDACTED` |
| OPc | `REDACTED` |
| ACC | `FFFF` |
| AD | `00000002` (MNC len=2) |
| SPN | (empty) |
| SMSP | `+687770009` (Moorea/French Polynesia default) |
| Algorithm | MILENAGE (`RadLTE_MLG=-1`) |
| Card type | LY14 |

---

## 11. Warnings and notes

1. Key reference `0x0A` has only 1 try remaining. VERIFY CHV should not be attempted again on
   `0x0A`, since it will block permanently on the next failure.
2. Ki and OPc cannot be changed via pySim or raw APDUs on this card family. The OYEITIMES SIM
   Personalize Tools (Windows) must be used instead.
3. The pySim-shell `-A` flag always targets key reference `0x0A`. To use ADM on this card, a raw
   `apdu` command should be sent first: `apdu 0020000B083838383838383838`.
4. The OYEITIMES tool reads Ki/OPc values for display purposes from its own local configuration
   file, not from the card itself, since Ki and OPc are truly write-only on the card hardware.
5. When flashing `srsRAN_test.grsp`, the Ki and OPc values embedded in the grsp file (both
   `REDACTED` in this document) will be written to the card by the OYEITIMES tool. These should be
   matched exactly in the corresponding HSS/Open5GS subscriber entry.
