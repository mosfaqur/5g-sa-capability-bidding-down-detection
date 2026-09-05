# Installing the 5G SA Testbed on Kali Linux

Build instructions for the third-party 5G stack this repository's code assumes is already
running: **Open5GS 2.7.7** (5G SA core) and **srsRAN Project 25.10** (5G NR gNodeB), on
Kali Linux with a USRP B210. UERANSIM is covered in §9 as an optional addition for
software-only UE profiles.

None of this software is vendored in this repository — see the Dependencies table in the
[README](../README.md). This document exists because neither project builds out of the box on
current Kali: `apt install open5gs` does not work, Kali's `libmongoc` packaging breaks the
Open5GS build in three separate ways, and the srsRAN GitHub repository was archived in
December 2025 so a naive `git clone` yields nothing but a README.

> **Scope.** This gets you to a cell that real handsets attach to and a core that registers
> them. It does not cover this repository's own NGAP proxy, feature extraction or ML
> pipeline; those are documented in the README.

---

## 1. Verified environment

Every version below was confirmed on the working testbed on 2026-09-05. Where a value drifts
over time (Kali is a rolling release), the step that depends on it says so and gives a
version-agnostic way to derive it.

| Component | Version | Notes |
|---|---|---|
| OS | Kali GNU/Linux Rolling, `VERSION_ID="2026.3"` | ≥16 GB RAM |
| Compiler | GCC 15.3.0 (Debian 15.3.0-2) | The source of most build friction below |
| CMake | 4.3.4 | See the CMake 4 note in §7 |
| Meson / Ninja | 1.11.1 / 1.13.2 | |
| MongoDB | 8.0.29 | Subscriber database |
| libmongoc / libbson | 2.3.3-1 | **Was 2.3.1 when the testbed was first built** — see §3 |
| UHD | 4.9.0.1 | Driver for the B210 |
| Open5GS | v2.7.7 | Built from source |
| srsRAN Project | `release_25_10`, commit `d2f4b70` | Built from source |
| UERANSIM | `v3.2.6`, commit `384636f` | Optional; plus this repo's patch |

### Hardware

| Item | Requirement |
|---|---|
| SDR | USRP B210. **Must be on a genuine USB 3.0 port** — 20 MHz n78 needs 23.04 Msps, which USB 2.0 cannot sustain. See §10, Bug 11. |
| UEs | 5G SA capable handsets with programmable USIMs (MILENAGE), and/or UERANSIM software UEs |
| RF containment | Faraday bag or shielded room. You are transmitting on band n78; do not radiate into licensed spectrum. |

---

## 2. Step 0 — UHD firmware and B210 detection

One-time per machine:

```bash
uhd_images_downloader        # downloads FPGA images to /usr/lib/uhd/images/
uhd_find_devices             # expect: type=b200, and your board's serial
```

`uhd_find_devices` succeeding is **not** proof the link is fast enough — it succeeds on USB
2.0 too. Verify the negotiated speed now, before you spend an hour building:

```bash
lsusb -t   # find the B210 line: it must end in 5000M (USB 3.0), not 480M (USB 2.0)
```

---

## 3. Step 1 — System dependencies

```bash
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  meson ninja-build build-essential flex bison \
  cmake libsctp-dev libgnutls28-dev libgcrypt-dev \
  libssl-dev libidn11-dev libbson-dev libmicrohttpd-dev \
  libcurl4-gnutls-dev libnghttp2-dev libyaml-dev \
  libtalloc-dev libpcsclite-dev pcscd libtins-dev \
  libfftw3-dev libmbedtls-dev libboost-all-dev \
  libconfig++-dev libyaml-cpp-dev libzmq3-dev cppzmq-dev \
  libuhd-dev uhd-host python3-pip
```

> If `apt-get` refuses to proceed with "dpkg was interrupted" — typically an abandoned
> interactive `iperf3` postinst prompt — clear it non-interactively:
> `sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a`

---

## 4. Step 2 — MongoDB 8.0

Kali has no MongoDB package of its own; use the upstream Debian repository.

```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
  sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg

echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] \
  https://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list

sudo apt-get update && sudo apt-get install -y mongodb-org
sudo mkdir -p /var/lib/mongodb /var/log/mongodb
sudo mongod --dbpath /var/lib/mongodb --logpath /var/log/mongodb/mongod.log --fork
```

Confirm it is up before continuing — the Open5GS build does not need it, but nothing will
register without it:

```bash
mongosh --quiet --eval "db.adminCommand('ping')"
```

---

## 5. Step 3 — Kali libmongoc fixups (**required** before building Open5GS)

This is the step that makes a Kali install different from the upstream Open5GS instructions,
and it is the one most likely to break again in future.

**The problem.** Debian/Kali ship libmongoc 2.x under the `mongoc2` name, with headers in a
versioned directory and a pkg-config file that does not use the upstream name. Open5GS 2.7.7
expects the libmongoc 1.x layout: a `libmongoc-1.0.pc` and a top-level `<mongoc.h>`. Three
distinct failures follow, fixed below and in §6.

### Fix 1 — pkg-config name symlinks

```bash
PC=/usr/lib/x86_64-linux-gnu/pkgconfig
sudo ln -sf $PC/mongoc2.pc        $PC/libmongoc-1.0.pc
sudo ln -sf $PC/mongoc2-static.pc $PC/libmongoc-static-1.0.pc
sudo ln -sf $PC/bson2.pc          $PC/libbson-1.0.pc
sudo ln -sf $PC/bson2-static.pc   $PC/libbson-static-1.0.pc
```

Without this, `meson setup` fails with `Dependency libmongoc-1.0 not found`.

### Fix 2 — header shims

Kali installs the headers at `/usr/include/mongoc-<version>/mongoc/mongoc.h`, but Open5GS
does `#include <mongoc.h>`. Create a one-line shim at the top of each versioned include
directory that redirects to the real header.

**Derive the paths from pkg-config rather than hardcoding a version.** The original testbed
was built against mongoc 2.3.1 and Kali has since moved to 2.3.3; a shim written for one
version is silently invisible to the next, and the build fails with the same
`fatal error: mongoc.h: No such file or directory` as if the fixup had never been applied:

```bash
MONGOC_INC="$(pkg-config --variable=prefix libmongoc-1.0)/include/mongoc-$(pkg-config --modversion libmongoc-1.0)"
BSON_INC="$(pkg-config --variable=prefix libbson-1.0)/include/bson-$(pkg-config --modversion libbson-1.0)"

echo '#include "mongoc/mongoc.h"' | sudo tee "$MONGOC_INC/mongoc.h"
echo '#include "bson/bson.h"'     | sudo tee "$BSON_INC/bson.h"
```

Verify the shim resolves before building anything:

```bash
printf '#include <mongoc.h>\n#include <bson.h>\nint main(void){return 0;}\n' > /tmp/probe.c
gcc $(pkg-config --cflags libmongoc-1.0) -c /tmp/probe.c -o /dev/null && echo "shim OK"
```

> **Re-run this step after any `apt upgrade` that bumps `libmongoc-dev`.** The shims live
> inside the versioned include directory, so a package upgrade leaves them behind in the old
> directory and the next Open5GS rebuild fails. The existing binaries keep working; only
> rebuilds are affected.

---

## 6. Step 4 — Build Open5GS 2.7.7 from source

```bash
git clone --depth 1 --branch v2.7.7 https://github.com/open5gs/open5gs.git
cd open5gs
```

### Fix 3 — disable the bundled test suite

`tests/common/context.c` calls `mongoc_collection_count()`, which was removed in libmongoc
2.x. The tests fail to compile even though the daemons themselves build fine:

```bash
sed -i 's/^if build_tests/if false # build_tests/' meson.build
```

This is a build-only change — it disables Open5GS's own unit tests and touches no core
functionality, which is why this repository ships no patch file for it.

### Build and install

```bash
meson setup build --prefix=/usr/local
ninja -C build -j"$(nproc)"
sudo ninja -C build install
sudo ldconfig
```

Output locations:

| What | Where |
|---|---|
| Binaries | `/usr/local/bin/open5gs-*d` |
| Configs | `/usr/local/etc/open5gs/*.yaml` |
| SUCI home-network keys | `/usr/local/etc/open5gs/hnet/` (installed automatically) |

Confirm the version:

```bash
/usr/local/bin/open5gs-amfd -v     # Open5GS v2.7.7
```

---

## 7. Step 5 — Configure Open5GS for PLMN 001/01

A stock Open5GS install will start, register nothing, and return `504 Gateway Timeout` on
every discovery request. Four config-level problems cause this, and all four must be fixed
together. Configs live in `/usr/local/etc/open5gs/`.

### 7.1 NRF must allow the test PLMN

`nrf.yaml` defaults to `mcc: 999, mnc: 70` and rejects every NF that registers with anything
else (`PLMN-ID[MCC:001,MNC:01] is not allowed`):

```yaml
nrf:
  serving:
    - plmn_id:
        mcc: 001
        mnc: 01
  sbi:
    server:
      - address: 127.0.0.10
        port: 7777
```

### 7.2 Every NF needs an explicit `serving` section

`ausf.yaml`, `udm.yaml`, `udr.yaml`, `pcf.yaml`, `nssf.yaml` and `bsf.yaml` ship without one,
so they register under the default PLMN 999/70 and the AMF cannot discover them for 001/01.
Add to each:

```yaml
<nf>:
  serving:
    - plmn_id:
        mcc: 001
        mnc: 01
```

### 7.3 Route through the NRF, not the SCP

Every NF config defaults to `client.scp: http://127.0.0.200:7777`. The SCP expects a SEPP for
inter-PLMN routing, which a single-PLMN private network does not have, so all discovery fails
with `No SEPP configured`. Change `client.scp:` to `client.nrf:` in **every** NF config:

```yaml
  sbi:
    client:
      nrf:
        - uri: http://127.0.0.10:7777
```

### 7.4 SBI addresses

Each NF binds its own loopback address:

| NF | SBI address | NF | SBI address |
|---|---|---|---|
| NRF | 127.0.0.10 | UDM | 127.0.0.12 |
| SMF | 127.0.0.4 | PCF | 127.0.0.13 |
| AMF | 127.0.0.5 | NSSF | 127.0.0.14 |
| UPF | 127.0.0.7 | BSF | 127.0.0.15 |
| AUSF | 127.0.0.11 | UDR | 127.0.0.20 |

### 7.5 AMF — NGAP, GUAMI, TAI and network name

`amf.yaml`, key sections:

```yaml
amf:
  sbi:
    server:
      - address: 127.0.0.5
        port: 7777
    client:
      nrf:
        - uri: http://127.0.0.10:7777
  ngap:
    server:
      - address: 127.0.0.5
  guami:
    - plmn_id: { mcc: 001, mnc: 01 }
      amf_id: { region: 2, set: 1 }
  tai:
    - plmn_id: { mcc: 001, mnc: 01 }
      tac: 1
  plmn_support:
    - plmn_id: { mcc: 001, mnc: 01 }
      s_nssai:
        - sst: 1
  security:
    integrity_order: [NIA2, NIA1, NIA0]
    ciphering_order: [NEA0, NEA1, NEA2]
  network_name:
    full: srsRAN 5G Test
    short: srsTest
  amf_name: open5gs-amf0
  time:
    t3512:
      value: 540
```

### 7.6 SMF and UPF — UE subnet

Both need matching session blocks:

```yaml
  session:
    - subnet: 10.45.0.0/16
      gateway: 10.45.0.1
      dnn: internet
```

`smf.yaml` additionally takes DNS (`8.8.8.8`, `8.8.4.4`) and `mtu: 1400`. The `gtpc`/`gtpu`
and `freeDiameter` entries in the installed `smf.yaml` are 4G EPC legacy and are unused in
5G SA — leave them alone.

> **`ogstun` comes up DOWN.** The UPF creates the TUN interface but neither brings it up nor
> assigns the gateway address. Until you do, a UE gets an IP but passes no traffic:
> ```bash
> sudo ip link set ogstun up
> sudo ip addr add 10.45.0.1/16 dev ogstun
> ```
> The start script in §10 handles this automatically.

### 7.7 UDM home-network keys

`udm.yaml` references six SUCI concealment keys under `/usr/local/etc/open5gs/hnet/`. They are
installed by `ninja install`; **UDM will not start if they are missing.** Test USIMs using the
SUCI null-scheme never exercise them, but they must still be present.

---

## 8. Step 6 — Provision subscribers

Subscribers go directly into MongoDB. The full profile set used by this project — five
physical USIMs and three UERANSIM software profiles — is documented in
[`COMP997_srsRAN_subscribers.md`](../COMP997_srsRAN_subscribers.md), which includes a
ready-to-paste `insertMany` block.

**Key material (Ki/OPc) is redacted throughout this repository**, since it is public. Substitute
your own USIM credentials for the `REDACTED` placeholders. The IMSI prefix `001010000000xxx` is
not sensitive: MCC=001/MNC=01 is the 3GPP test PLMN, assigned to no real operator.

Document shape, per subscriber:

```javascript
{
  imsi: "001010000000001",
  msisdn: [], imeisv: [],
  security: { k: "REDACTED", op: null, opc: "REDACTED", amf: "8000", sqn: NumberLong("0") },
  ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
  slice: [{ sst: 1, default_indicator: true,
            session: [{ name: "internet", type: 3,
                        ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
                        qos: { index: 9, arp: { priority_level: 8,
                               pre_emption_capability: 1, pre_emption_vulnerability: 1 } } }] }],
  access_restriction_data: 32, network_access_mode: 0,
  subscriber_status: 0, operator_determined_barring: 0, __v: 0
}
```

Verify:

```bash
mongosh open5gs --eval 'db.subscribers.find({}, {imsi:1, _id:0}).sort({imsi:1})'
```

> A device's **first** attach on a new SIM logs one
> `Authentication failure(Synch failure[count=0])`. This is normal MILENAGE SQN resync and
> registration completes on the immediate retry. If authentication keeps failing, reset:
> ```bash
> mongosh open5gs --eval 'db.subscribers.updateMany({}, {$set: {"security.sqn": NumberLong("0")}})'
> ```

---

## 9. Step 7 — Build srsRAN Project 25.10

> **The GitHub repository was archived in December 2025.** Its default branch now contains
> only a README pointing at GitLab, so a plain `git clone` appears to succeed and gives you
> nothing. You must clone an explicit release tag.

```bash
git clone --depth 1 --branch release_25_10 https://github.com/srsran/srsRAN_Project.git
mkdir -p srsRAN_Project/build && cd srsRAN_Project/build

cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_EXPORT=ON \
  -DENABLE_UHD=ON \
  -DENABLE_ZEROMQ=ON \
  -DBUILD_TESTING=OFF

make -j"$(nproc)" gnb
```

Binary: `build/apps/gnb/gnb`. Confirm with `./build/apps/gnb/gnb --version`.

srsRAN builds cleanly under GCC 15 — unlike Open5GS, it needs no patches. It also declares
`cmake_minimum_required(VERSION 3.14)`, comfortably above the 3.5 floor that CMake 4.x
enforces, so no `-DCMAKE_POLICY_VERSION_MINIMUM` workaround is needed.

### gNB configuration

The testbed's config lives at `/root/.config/open5gs/gnb.yml`:

```yaml
cu_cp:
  amf:
    addr: 127.0.0.5
    port: 38412
    bind_addr: 127.0.0.1
    supported_tracking_areas:
      - tac: 1
        plmn_list:
          - plmn: "00101"
            tai_slice_support_list:
              - sst: 1

ru_sdr:
  device_driver: uhd
  device_args: type=b200,serial=YOUR_B210_SERIAL,num_recv_frames=64,num_send_frames=64
  srate: 23.04
  otw_format: sc12
  tx_gain: 89
  rx_gain: 50

cell_cfg:
  dl_arfcn: 632628
  band: 78
  channel_bandwidth_MHz: 20
  common_scs: 30
  plmn: "00101"
  tac: 1
  pci: 1

log:
  filename: /tmp/gnb.log
  all_level: info
```

Two settings are not optional:

- `num_recv_frames=64,num_send_frames=64` — without these the B210 underruns regardless of
  USB generation.
- `tx_gain: 89` (the B210 maximum), `rx_gain: 50`. At `tx_gain: 80` some handsets never saw
  the cell at all while others attached fine — a confusing failure to diagnose, because the
  cell is genuinely on-air the whole time.

Substitute your own B210 serial from `uhd_find_devices`.

---

## 10. Step 8 — UERANSIM v3.2.6 (optional, software UEs)

Only needed for the SW-Std / SW-Ext / SW-Min software profiles. Skip if you are working with
physical handsets only.

```bash
git clone --depth 1 --branch v3.2.6 https://github.com/aligungr/UERANSIM.git ueransim
cd ueransim
```

### Kali/GCC 15 build fixups

UERANSIM's 2022-era code relies on standard-library headers that older GCC pulled in
transitively; GCC 15 does not. Two changes:

1. `src/ext/yaml-cpp/emitterutils.cpp` — add `#include <cstdint>`.
2. Top-level `CMakeLists.txt` — append to `CMAKE_CXX_FLAGS`:
   ```cmake
   set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -include cstdint -include cstring -include cstdio -include string")
   ```
   Force-including globally is cheaper than patching every offending file individually.

### Capability-enquiry patch

**Stock UERANSIM never sends `UERadioCapabilityInfoIndication` at all** — there is no RRC
`UECapabilityEnquiry`/`UECapabilityInformation` implementation on either the gNB or the UE
side. For this project that means the NGAP proxy has nothing to intercept for software
profiles. [`ueransim.patch`](../ueransim.patch) in this repository adds it; see the README's
UERANSIM section for what it touches.

```bash
git apply /path/to/ueransim.patch
cp /path/to/ueransim-config/gnb.yaml config/gnb.yaml
make build      # produces build/nr-gnb, build/nr-ue, build/nr-cli
```

> **Known robustness gap:** if `nr-gnb` is left running across a restart of whatever it is
> connected to, it can wedge in a broken internal AMF-context state (`AMF selection ...
> failed` / `AMF context not found with id: 0`) while its SCTP transport still looks healthy.
> Restart `nr-gnb` fresh whenever its peer restarts rather than trusting its reconnect logic.
>
> Its GTP/UDP task will also fail to bind (`Address already in use`) if a real srsRAN gNB is
> running, since both claim port 2152 on loopback. Harmless for NGAP signalling; user-plane
> data will not flow for UERANSIM UEs in that configuration.

---

## 11. Bring-up and verification

Start order matters: MongoDB, then NRF and SCP, then the remaining NFs, then AMF/SMF, then
UPF, then the gNB. The project's `start_5g.sh` encodes this along with CPU governor tuning,
IP forwarding, the `ogstun` fix and NAT masquerade for `10.45.0.0/16`.

```bash
# Minimal manual sequence
sudo mongod --dbpath /var/lib/mongodb --logpath /var/log/mongodb/mongod.log --fork
for nf in nrf scp ausf udm udr pcf nssf bsf amf smf upf; do
  sudo /usr/local/bin/open5gs-${nf}d > /tmp/${nf}.log 2>&1 &
  sleep 1
done
sudo ip link set ogstun up
sudo ip addr add 10.45.0.1/16 dev ogstun 2>/dev/null || true
sudo sysctl -w net.ipv4.ip_forward=1
UPLINK=$(ip route show default | awk '{print $5; exit}')
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 -o "$UPLINK" -j MASQUERADE
sudo /path/to/srsRAN_Project/build/apps/gnb/gnb -c /root/.config/open5gs/gnb.yml > /tmp/gnb.log 2>&1 &
```

### Verification checklist

| Check | Command | Expect |
|---|---|---|
| AMF listening on N2 | `ss -lntu \| grep 38412` | a listening socket |
| NG Setup succeeded | `grep -i "ng setup" /tmp/gnb.log` | success, PLMN 00101 |
| UE registered | `sed 's/\x1b\[[0-9;]*m//g' /tmp/amf.log \| grep "Registration complete"` | one line per UE |
| UE got an IP | `sed 's/\x1b\[[0-9;]*m//g' /tmp/smf.log \| grep "UE IPv4"` | an address in 10.45.0.0/16 |
| Data path | `ping -I ogstun 10.45.0.2` | replies |
| RF underflows | `grep -c underflow /tmp/gnb.log` | near zero — see Bug 11 |

**Confirming the cell is actually transmitting.** Protocol-level evidence is the primary
check: PRACH detection in `/tmp/gnb.log`, NG Setup, and a successful registration. For an
independent RF-layer confirmation, a wideband `hackrf_sweep` is *not* reliable — it produces
noisy readings with no stable peak. Use GQRX narrowband instead: tune to `3489420000` Hz,
sample rate `20000000`, LNA/IF `16 dB`, VGA/BB `20 dB`, RF amp **off** (the B210 is
transmitting at maximum gain right next to it). The carrier appears as a sharp spike around
−35 to −40 dBFS against a −85 to −90 dBFS noise floor, with visible TDD burst structure.

> GQRX gotcha: the LNA/VGA/RF-amp sliders are in the **Input controls** tab of the Receiver
> Options dock, *not* in "Configure I/O devices". And GQRX does not auto-start — click ▶
> (Start/Stop DSP) or the waterfall stays black no matter how correct your settings are.

---

## 12. Troubleshooting

Install-time and bring-up failures encountered on this testbed, with root causes.

| Symptom | Cause | Fix |
|---|---|---|
| `apt-get` fails: "dpkg was interrupted" | Abandoned interactive postinst prompt | `DEBIAN_FRONTEND=noninteractive dpkg --configure -a` |
| meson: `Dependency libmongoc-1.0 not found` | Kali names the .pc file `mongoc2.pc` | pkg-config symlinks, §5 Fix 1 |
| `fatal error: mongoc.h: No such file or directory` | Headers live at `mongoc-<ver>/mongoc/mongoc.h` | Header shims, §5 Fix 2. **If this appears after a working build, `libmongoc-dev` was upgraded and the shim is stranded in the old versioned directory — re-run §5 Fix 2.** |
| `implicit declaration of function 'mongoc_collection_count'` | Removed in libmongoc 2.x; Open5GS tests still use it | Disable tests, §6 Fix 3 |
| `git clone` of srsRAN yields only a README | GitHub repo archived Dec 2025 | Clone `--branch release_25_10`, §9 |
| Every AMF discovery returns `504`; SCP logs `No SEPP configured` | NFs routing via SCP, which needs a SEPP | Switch `client.scp` → `client.nrf`, §7.3 |
| NRF logs `PLMN-ID[MCC:001,MNC:01] is not allowed` | `nrf.yaml` still serving default 999/70 | §7.1 |
| AMF discovery for AUSF/UDM returns empty | Those NFs registered under default PLMN 999/70 | Add `serving:` to every NF, §7.2 |
| UDM will not start | Missing `hnet/` SUCI key files | Reinstall; they come from `ninja install`, §7.7 |
| UE gets an IP but no traffic; `ping -I ogstun` → "Network is unreachable" | UPF leaves `ogstun` DOWN | `ip link set ogstun up`, §7.6 |
| One handset sees the cell, another does not | `tx_gain` too low for that device at that distance | `tx_gain: 89`, `rx_gain: 50`, §9 |
| Thousands of `Real-time failure in RF: underflow`, `DL task queue is full` — despite NG Setup succeeding | B210 on a USB 2.0 port. **`lsusb` and `uhd_find_devices` both succeed on USB 2.0 — presence is not proof of link speed.** | Move to a port under a true USB 3.0 (`xhci_hcd`) root hub; confirm `5000M` in `lsusb -t`. Isolated single-slot underflows under heavy load remain normal. |
| UE registers at NAS/RRC but never gets a PDU session; gNB loops `UE did not request a PDU session ... Requesting UE release` | Device's APN/DNN profile requests something other than `internet` (e.g. `ims`) with no fallback | Fix on the **device's** APN configuration, not the network. Check `/tmp/amf.log` for the requested DNN. |
| Recurring `Ue requested DNN "ims" Not Supported` every ~16s | Handset probing for a VoNR/IMS bearer Open5GS does not provide | Harmless. Disable VoNR on the handset, or ignore. |
| Registration succeeds, then drops every 15–90s | RF link quality — check PUSCH SINR in `gnb.log`. Collapse to −20…−35 dB means uplink is failing outright. | Antenna positioning. Not a software fault. |
| CPE/device unreachable by `ping` despite a working session | Many CPEs silently drop unsolicited ICMP | Check for live flows instead: `tcpdump -i ogstun host <ip>` |

---

## 13. Network parameters reference

| Parameter | Value |
|---|---|
| MCC / MNC | 001 / 01 (3GPP test PLMN) |
| TAC | 1 |
| Band | n78 (TDD, 3300–3800 MHz) |
| DL ARFCN | 632628 (3489.42 MHz) |
| SSB ARFCN | 632256 |
| Channel bandwidth | 20 MHz |
| Subcarrier spacing | 30 kHz |
| S-NSSAI | SST=1 (eMBB) |
| AMF NGAP | 127.0.0.5:38412 |
| UE IP pool | 10.45.0.0/16 |
| UPF TUN | `ogstun` (10.45.0.1/16) |
| DNN | `internet` |
| DNS | 8.8.8.8, 8.8.4.4 |
| TX / RX gain | 89 dB / 50 dB |

---

## 14. Legal and safety

Band n78 is licensed spectrum. Transmit only inside a Faraday enclosure or shielded room, or
under a licence that permits it. The PLMN 001/01 used throughout is the 3GPP test network,
assigned to no real operator, which keeps a stray UE from mistaking this cell for a
commercial one — but that is not a substitute for RF containment.

This testbed exists to study attacks against capability negotiation on a private network with
subscribers you control. Do not point it at devices or subscribers that are not yours.
