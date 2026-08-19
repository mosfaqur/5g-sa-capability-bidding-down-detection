# 5G SA UE Capability Bidding-Down Attack Detection

Whilst fifth-generation (5G) networks introduce considerable security hardening over their
predecessors, the capability negotiation that takes place between a User Equipment (UE) and the
network remains an area where a well-placed adversary can quietly understate what a device is
capable of. This repository holds a curated snapshot of a dissertation project studying exactly
that behaviour: detection of 5G Standalone (SA) UE capability bidding-down attacks, built on a
private software-defined-radio (SDR) testbed. A Python proxy for the Next Generation Application
Protocol (NGAP) sits on the N2 interface between a real gNodeB and the core network, intercepting
the `UERadioCapabilityInfoIndication` protocol data unit (PDU) and rewriting or attacking the UE
capability container before it reaches the Access and Mobility Management Function (AMF), across
seven labelled attack modes. This is not a runnable end-to-end package on its own. See
Dependencies below for the third-party 5G stack this code assumes is built and running separately.

Detection is framed two ways. The first is a single-view supervised model trained over 12
NGAP-derived features, taken from the capability information as the core network sees it. The
second is a cross-layer consistency model, which instead compares the untampered Radio Resource
Control (RRC) capability observed at the gNodeB against what actually reaches the core over N2,
in effect giving the detector a second, independent vantage point on the same registration event.
SHapley Additive exPlanations (SHAP) provide the explainability layer for both models. Every
captured packet capture (PCAP) file and derived artefact is appended to a SHA-256 hash-chain
forensic custody log, assessed against an ISO/IEC 27037:2012 basis, so that the evidentiary trail
behind every result in this repository can be independently re-verified.

## Repository contents

| Path | Contents |
|---|---|
| `proxy/` | The NGAP proxy (`ngap_proxy.py`), the pycrate-based NGAP/RRC-NR codec and attack-label modifiers (`ngap_decode.py`), the gNodeB RRC capability capture tool (`rrc_capture.py`), and their test suites |
| `ml/` | The Q2 machine learning (ML) pipeline (`pipeline.py`), the Chapter 5 artefact builder (`build_ch5_artifacts.py`), the multi-model/feature-ablation/custody-timing benchmarks (`benchmarks/`), trained model files (`models/*.pkl`), and all results, tables and figures (`results/`) |
| `features/` | The 12-feature single-event extractor and the RRC-vs-N2 cross-layer consistency comparator (`extract_features.py`), and the cross-layer feature-matrix builder (`build_xlayer.py`) |
| `analysis/` | Chapter 4 (Q1) outputs: the attack catalogue, cross-layer divergence catalogue, feature significance tables/figures, intra-class consistency tables and decoded-packet exhibits |
| `data/raw_sample/` | A stratified sample of the labelled N2 PCAP dataset (see note below) |
| `sim/` | Physical Universal Subscriber Identity Module (USIM) programming tools and findings (`flash_ue.py`, `grsp_tool.py`, `SIM_FINDINGS.md`); key material has been redacted, see Security note below |
| `ueransim.patch`, `ueransim-config/` | This project's modifications to UERANSIM (see UERANSIM patch below) |
| `COMP997_srsRAN_subscribers.md` | Subscriber/UE profile configuration (Ki/OPc redacted) |
| `chain_of_custody.log` | The append-only SHA-256 hash-chain evidence custody log |
| `logs/collection_manifest.csv` | Per-event manifest (session, profile, label, PCAP path, registration outcome, proxy latency) for the full dataset collection campaign |

## Headline results

The taxonomy underpinning this work has 7 attack classes: 0 Normal, 1 Cat-downgrade,
2 CA-disabled (Carrier Aggregation, CA), 3 MIMO-reduced (Multiple-Input Multiple-Output, MIMO),
4 VoNR-denied, 5 Combined and 6 Partial/noise. All figures below come from a
`RandomForestClassifier(n_estimators=200)` under 5-fold stratified cross-validation.

| Model | Macro-F1 |
|---|---|
| Single-event (12 NGAP features) | 0.847 |
| Sliding window (N=3, 36 features) | 0.872 |
| Cross-layer consistency (9 RRC-vs-N2 divergence features, real handsets only) | 0.748 |

These results are stated honestly here, not oversold. Leave-one-profile-out generalisation, in
particular, is poor and markedly asymmetric: held-out per-profile macro-F1 ranges from a
reasonably robust 0.82 on the best-generalising profiles down to a mere 0.036 on one device
whose baseline capability already sits at the floor of every attack-relevant feature, which
causes the model to misclassify almost all of that device's rows as the Combined-attack label.
This was traced to device-fixed traits aliasing with attack-target features whenever a device's
true baseline is withheld from training, rather than to a defect in the pipeline itself. The full
causal breakdown is set out in the internal build log's "CLI Session D" entry, which is no longer
distributed with this repository. Does strong performance across six devices in the laboratory
guarantee equally strong performance on a seventh device encountered only in the field? The
leave-one-profile-out results suggest not, at least not without a considerably larger and more
varied training set. A related finding concerns the open-set, held-out-mode test: the cross-layer
model did not out-transfer the single-view model here, achieving only a 50.3% detection rate on
unseen labels 5 and 6 against the single-view model's 59.3%, which runs contrary to the project's
own working hypothesis and is flagged for discussion rather than quietly reported as confirming
it.

Full per-class tables, confusion matrices, SHAP summaries and the open-set/leave-one-profile-out
detail are available in `ml/results/`.

## `data/raw_sample/`

The full labelled dataset comprises approximately 5,251 raw N2 PCAPs (406MB) behind a
4,225-event single-view feature matrix. What is included here, in `data/raw_sample/`, is instead
a stratified sample of up to 3 events per (profile, label) combination, drawn from
`logs/collection_manifest.csv`, sufficient to illustrate the raw capture format without
substantially bloating the repository. The full dataset remains available on request, or is
regenerable from the testbed procedure that this project's internal documentation describes in
detail, although that documentation is not itself distributed here. See
`data/raw_sample/README.md` for the exact per-group counts.

## UERANSIM patch

`ueransim/` is a clone of [aligungr/UERANSIM](https://github.com/aligungr/UERANSIM) at tag
`v3.2.6`, commit `384636f`, and it is not included in this repository. Only this project's
modifications are, as `ueransim.patch` at the repository root, together with
`ueransim-config/gnb.yaml`. This distinction matters because upstream UERANSIM has no RRC
`UECapabilityEnquiry`/`UECapabilityInformation` implementation and never sends a
`UERadioCapabilityInfoIndication` message at all. The patch adds this behaviour directly: new
gNodeB and UE RRC capability handlers, the corresponding NGAP transmission path and the
supporting intertask message plumbing that connects them. This is what makes UERANSIM's three
software UE profiles, SW-Std, SW-Ext and SW-Min, reachable by the NGAP proxy's Stage 1/2
pipeline in the first place; without the patch, there would simply be nothing for the proxy to
intercept.

To reconstruct the full working tree:

```bash
git clone https://github.com/aligungr/UERANSIM.git ueransim
cd ueransim
git checkout 384636f
git apply /path/to/ueransim.patch
cp /path/to/ueransim-config/gnb.yaml config/gnb.yaml
make build
```

Kali Linux/GNU Compiler Collection (GCC) 15 build fixups may additionally be required, although
the details of these are kept in the project's internal build notes rather than here.

## Dependencies

This repository's code assumes that the following are cloned and built separately. None of them
are vendored here.

| Project | Role | Repository | Version used |
|---|---|---|---|
| srsRAN Project | 5G New Radio (NR) gNodeB | https://github.com/srsran/srsRAN_Project | release `25.10` (the repository was archived in December 2025, so the release tag should be used rather than `main`) |
| Open5GS | 5G SA core network (NRF/AMF/SMF/UPF/AUSF/UDM/UDR/PCF/NSSF/BSF/SCP) | https://github.com/open5gs/open5gs | `2.7.7` (one local modification: `meson.build` disables its own test-suite build; this is not a methodology change, so no patch file is needed) |
| UERANSIM | Software 5G SA UE/gNodeB (SW-Std/SW-Ext/SW-Min profiles) | https://github.com/aligungr/UERANSIM | tag `v3.2.6`, commit `384636f`, plus this project's patch, described above |
| srsRAN 4G | Prior-generation 4G Long Term Evolution (LTE) eNodeB and Evolved Packet Core (EPC), superseded by the 5G SA stack and kept only for background | https://github.com/srsran/srsRAN_4G | no local modifications |
| LTE-Cell-Scanner | Radio frequency (RF) diagnostic and cell-scanning tool used during testbed bring-up | https://github.com/JiaoXianjun/LTE-Cell-Scanner | no local modifications |

The hardware behind all of this is comparatively modest: a Universal Software Radio Peripheral
(USRP) B210 SDR and OYEITIMES programmable USIMs. Full build steps, configuration files and
bring-up scripts are, again, documented in the project's internal build notes rather than in this
repository.

## Security note

Test-network subscriber Ki/OPc key material, along with the Integrated Circuit Card Identifier
(ICCID), International Mobile Subscriber Identity (IMSI) and International Mobile Equipment
Identity (IMEI) of physical Subscriber Identity Module (SIM) cards encountered whilst researching
the OYEITIMES card-programming tool, have all been redacted (`REDACTED`) throughout this
repository, including in `COMP997_srsRAN_subscribers.md` and `sim/SIM_FINDINGS.md`, since this
repository is public. The `001010000000xxx` IMSI prefix used throughout the codebase is, by
contrast, not sensitive: it belongs to the project's own private test Public Land Mobile Network
(PLMN), MCC=001/MNC=01.

## Licence

MIT. See `LICENSE`. This was confirmed with the supervisor prior to publishing under this
licence.
