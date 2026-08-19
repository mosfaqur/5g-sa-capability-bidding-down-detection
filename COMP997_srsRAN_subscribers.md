# srsRAN / Open5GS Subscriber Configuration

This document sets out the subscriber configuration behind the testbed: five physical OYEITIMES
Universal Subscriber Identity Modules (USIMs), all programmed, of which UE1 through UE4 have been
tested and UE5 remains spare, together with three UERANSIM software profiles, all under
MCC=001/MNC=01.

Whilst UE1 through UE5 (IMSIs 001 through 005) all carry a real subscriber key (K) and derived
operator variant (OPc), only four of the five have actually been tested. UE4, a Realme RMX3363
connected over USB via the Android Debug Bridge (ADB), was confirmed operational and added as the
6th primary dataset profile on the 31st of July 2026. UE1's Samsung A56 was subsequently excluded
from the final Session B dataset on the 10th of August 2026, owing to unresolved radio frequency
(RF) and registration reliability issues, and on the same day UE3's SIM was physically moved from
the Nokia customer premises equipment (CPE) into a Nothing Phone 3a, which replaced the A56 as the
6th real-handset profile. This is, in other words, a roster that has shifted twice over the
project's life, and what follows reflects only its current, authoritative state.

Alongside the physical devices sit three UERANSIM software profiles, SW-Std, SW-Ext and SW-Min
(IMSIs 006 through 008), which share UE1's subscriber key and OPc in MongoDB rather than each
carrying their own.

---

## Subscriber table: physical USIMs

| | UE1 (Samsung A56) | UE2 (Pixel 8) | UE3 (Nothing 3A, moved from Nokia CPE 2026-08-10) | UE4 (Realme RMX3363) | UE5 (unassigned) |
|---|---|---|---|---|---|
| **GRSP file** | `srsRAN_UE1.grsp` | `srsRAN_UE2.grsp` | `srsRAN_UE3.grsp` | `srsRAN_UE4.grsp` | `srsRAN_UE5.grsp` |
| **IMSI** | `001010000000001` | `001010000000002` | `001010000000003` | `001010000000004` | `001010000000005` |
| **Ki** | `REDACTED` | `REDACTED` | `REDACTED` | `REDACTED` | `REDACTED` |
| **OPc** | `REDACTED` | `REDACTED` | `REDACTED` | `REDACTED` | `REDACTED` |
| **Algorithm** | MILENAGE | MILENAGE | MILENAGE | MILENAGE | MILENAGE |
| **MCC/MNC** | 001/01 | 001/01 | 001/01 | 001/01 | 001/01 |
| **SPN** | srsRAN Test | srsRAN Test | srsRAN Test | srsRAN Test | srsRAN Test |
| **ACC** | 0001 | 0001 | 0001 | 0001 | 0001 |
| **AD (MNC len)** | 00000002 (2-digit) | 00000002 (2-digit) | 00000002 (2-digit) | 00000002 (2-digit) | 00000002 (2-digit) |

---

## Subscriber table: UERANSIM software profiles (research UE profiles)

These are software-only entries in MongoDB. No physical SIM card. All three share UE1 credentials
so that the NGAP proxy can control capability presentation without per-SIM key management.

| | SW-Std | SW-Ext | SW-Min |
|---|---|---|---|
| **Role** | Standard capability baseline | Extended (high-end) fingerprint | Minimal (low-end) fingerprint |
| **IMSI** | `001010000000006` | `001010000000007` | `001010000000008` |
| **Ki** | `REDACTED` | `REDACTED` | `REDACTED` |
| **OPc** | `REDACTED` | `REDACTED` | `REDACTED` |
| **Algorithm** | MILENAGE | MILENAGE | MILENAGE |
| **MCC/MNC** | 001/01 | 001/01 | 001/01 |

---

## Open5GS: MongoDB insertMany (all 8 profiles)

Run once after `mongod` is up. Inserts UE1–UE5 (physical) + SW-Std/SW-Ext/SW-Min (UERANSIM).

```javascript
mongosh open5gs
db.subscribers.insertMany([
  // ── Physical USIMs ──────────────────────────────────────────────────────
  {
    imsi: "001010000000001",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000002",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000003",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000004",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000005",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  // ── UERANSIM Software Profiles (SW-Std / SW-Ext / SW-Min) ──────────────
  // All three share UE1 K/OPc. NGAP proxy applies capability manipulation
  // at the SCTP layer. The core authenticates these as if they were UE1.
  {
    imsi: "001010000000006",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000007",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  },
  {
    imsi: "001010000000008",
    msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0
  }
])
```

Or add UERANSIM entries only (if UE1–UE5 already exist in MongoDB from the CLAUDE-5 run):

```javascript
mongosh open5gs
db.subscribers.insertMany([
  { imsi: "001010000000006", msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0 },
  { imsi: "001010000000007", msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0 },
  { imsi: "001010000000008", msisdn: [], imeisv: [],
    security: { k: "REDACTED", op: null,
                opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
    slice: [{ sst: 1, default_indicator: true,
              session: [{ name: "internet", type: 3,
                          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                          qos: { index: 9, arp: { priority_level: 8,
                                 pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
    access_restriction_data: 32, network_access_mode: 0,
    subscriber_status: 0, operator_determined_barring: 0, __v: 0 }
])
```

Verify all 8 entries are present:
```javascript
db.subscribers.find({}, {imsi:1, _id:0}).sort({imsi:1})
// Expected: 001, 002, 003, 004, 005, 006, 007, 008
```

---

## Open5GS WebUI: manual entry (http://localhost:9999)

For each UERANSIM profile add a subscriber with:
- IMSI: `001010000000006` / `007` / `008`
- K: `REDACTED`
- OPc: `REDACTED`
- AMF: `8000`
- SQN: `000000000000`
- Slice: SST=1, DNN=internet

---

## UERANSIM nr-ue.conf: per profile

UERANSIM reads IMSI/K/OPc from the config file (no physical card required).
Place each config at `/root/comp997/ueransim/config/` and pass with `nr-ue -c <file>`.

**SW-Std (IMSI 006):**
```yaml
supi: 'imsi-001010000000006'
mcc: '001'
mnc: '01'
key: 'REDACTED'
op: 'REDACTED'
opType: 'OPC'
amf: '8000'
imei: '356938035643806'
imeiSv: '4370816125816151'
gnbSearchList:
  - 127.0.0.1
uacAic:
  mps: false
  mcs: false
uacAcc:
  normalClass: 0
  class11: false
  class12: false
  class13: false
  class14: false
  class15: false
initialSlices:
  - sst: 1
sessions:
  - type: 'IPv4'
    apn: 'internet'
    slice:
      sst: 1
configured-nssai:
  - sst: 1
default-nssai:
  - sst: 1
    sd: 0xffffff
integrity:
  IA1: true
  IA2: true
  IA3: false
ciphering:
  EA0: true
  EA1: false
  EA2: false
  EA3: false
integrityMaxRate:
  uplink: 'full'
  downlink: 'full'
```

**SW-Ext (IMSI 007)**, same as SW-Std except:
```yaml
supi: 'imsi-001010000000007'
imei: '356938035643807'
```

**SW-Min (IMSI 008)**, same as SW-Std except:
```yaml
supi: 'imsi-001010000000008'
imei: '356938035643808'
```

---

## Physical SIM flash procedure

1. Copy `.grsp` file to Windows machine with OYEITIMES SIM Personalize Tools v4.2.11
2. Insert blank OYEITIMES USIM into the reader
3. File → Open → select `.grsp` → click **Write**
4. ADM for all cards: `3838383838383838` (HEX16/8), handled automatically by the tool

| GRSP file | IMSI | Intended device |
|---|---|---|
| `srsRAN_UE1.grsp` | 001010000000001 | Samsung Galaxy A56 |
| `srsRAN_UE2.grsp` | 001010000000002 | Google Pixel 8 |
| `srsRAN_UE3.grsp` | 001010000000003 | Nokia CPE 5G Gateway 2 originally; physically moved to a Nothing Phone 3a 2026-08-10 (see the project's internal build log's "CLI Session B continued") |
| `srsRAN_UE4.grsp` | 001010000000004 | Realme RMX3363 (confirmed 2026-07-31) |
| `srsRAN_UE5.grsp` | 001010000000005 | Spare, unassigned |

---

## eNodeB/gNodeB: MCC/MNC (same for all profiles)

```ini
mcc = 001
mnc = 01
```
