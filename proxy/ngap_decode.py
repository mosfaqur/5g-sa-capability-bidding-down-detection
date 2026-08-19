"""Step 2/3 decode + re-encode helpers: NGAP PDU codec + nested RRC-NR capability decode.

The NGAP IE `id-UERadioCapability` (117) does not directly contain a bare
`UE-NR-Capability` structure. Ground truth from Wireshark (validated against a
live capture, the project's testbed architecture notes §6.2) shows four nested decode passes,
alternating APER (NGAP) and UPER (RRC, per 3GPP TS 38.331 access-stratum
encoding):

    1. NGAP_PDU                            (aper)  -> IE 117 OCTET STRING
    2. UERadioAccessCapabilityInformation   (uper)  -> ue_RadioAccessCapabilityInfo OCTET STRING
    3. UE-CapabilityRAT-ContainerList       (uper)  -> per-RAT ue_CapabilityRAT_Container OCTET STRING
    4. UE-NR-Capability (for rat_Type=='nr') (uper) -> the actual capability fields

This is deeper than the architecture doc's "second decode pass" phrasing
suggests; the doc is directionally correct (decode the inner RRC container)
but the real structure needs all four passes to reach UE-NR-Capability.

Thread safety: the module-level pycrate objects below are singletons (that is
how pycrate's generated ASN.1 modules are meant to be used - decode populates
the object's internal state, encode reads it back). Step 3 decodes+re-encodes
on *both* relay directions within a single association, i.e. two threads can
call into this module concurrently for the same association. A module-level
lock serialises all decode/encode calls; message rates here (NGAP signalling,
not user-plane) make that contention irrelevant.
"""
import random
import threading
from typing import Optional

from pycrate_asn1dir import NGAP
from pycrate_asn1dir.RRCNR import NR_InterNodeDefinitions, NR_RRC_Definitions

NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION = 44
NGAP_IE_ID_UE_RADIO_CAPABILITY = 117

_ngap_pdu = NGAP.NGAP_PDU_Descriptions.NGAP_PDU
_l2 = NR_InterNodeDefinitions.UERadioAccessCapabilityInformation
_l3 = NR_RRC_Definitions.UE_CapabilityRAT_ContainerList
_l4 = NR_RRC_Definitions.UE_NR_Capability

# --- Step 4: Stage 1 profile-baseline rewrite (the project's testbed architecture notes §6.2/§6.3) ---
#
# UERANSIM (patched, see ueransim/src/*/rrc/capability.cpp) always sends the same
# minimal native capability regardless of which of the three software profiles is
# running. Stage 1 replaces that content wholesale with the target profile's
# fingerprint before forwarding - it is a full substitution, not a field-level
# patch, since the native container UERANSIM sends has none of the CA/MIMO/VoNR
# substructures the target profiles need.


def _rohc_profiles_all_false() -> dict:
    return {
        k: False
        for k in (
            "profile0x0000", "profile0x0001", "profile0x0002", "profile0x0003",
            "profile0x0004", "profile0x0006", "profile0x0101", "profile0x0102",
            "profile0x0103", "profile0x0104",
        )
    }


def build_profile_capability(bands, ca_bands, mimo_dl, mimo_ul, vonr) -> dict:
    """Build a UE-NR-Capability value dict (pycrate get_val()/set_val() format).

    bands: list of NR band numbers reported as standalone supported bands.
    ca_bands: list of band numbers used to build one CA band combination, or
        None/[] for no carrier aggregation.
    mimo_dl / mimo_ul: MIMO layer ENUM strings (e.g. 'twoLayers', 'fourLayers')
        or None to omit the featureSets substructure entirely (SISO/1x1).
    vonr: whether to add the ims-Parameters nonCriticalExtension (VoNR support).
    """
    cap = {
        "accessStratumRelease": "rel15",
        "pdcp-Parameters": {
            "supportedROHC-Profiles": _rohc_profiles_all_false(),
            "maxNumberROHC-ContextSessions": "cs2",
        },
        "phy-Parameters": {},
        "rf-Parameters": {"supportedBandListNR": [{"bandNR": b} for b in bands]},
    }
    if ca_bands:
        cap["rf-Parameters"]["supportedBandCombinationList"] = [
            {
                "bandList": [
                    ("nr", {"bandNR": b, "ca-BandwidthClassDL-NR": "a", "ca-BandwidthClassUL-NR": "a"})
                    for b in ca_bands
                ],
                "featureSetCombination": 0,
            }
        ]
    if mimo_dl or mimo_ul:
        feature_sets = {}
        if mimo_dl:
            feature_sets["featureSetsDownlinkPerCC"] = [
                {
                    "supportedSubcarrierSpacingDL": "kHz30",
                    "supportedBandwidthDL": ("fr1", "mhz100"),
                    "maxNumberMIMO-LayersPDSCH": mimo_dl,
                    "supportedModulationOrderDL": "qam256",
                }
            ]
        if mimo_ul:
            feature_sets["featureSetsUplinkPerCC"] = [
                {
                    "supportedSubcarrierSpacingUL": "kHz30",
                    "supportedBandwidthUL": ("fr1", "mhz100"),
                    "mimo-CB-PUSCH": {
                        "maxNumberMIMO-LayersCB-PUSCH": mimo_ul,
                        "maxNumberSRS-ResourcePerSet": 1,
                    },
                    "supportedModulationOrderUL": "qam256",
                }
            ]
        cap["featureSets"] = feature_sets
    if vonr:
        cap["nonCriticalExtension"] = {"interRAT-Parameters": {}, "nonCriticalExtension": {"ims-Parameters": {}}}
    return cap


# Fingerprints per the project's testbed architecture notes §6.2:
#   SW-Std: n78, CA enabled, 2x2 MIMO, VoNR on
#   SW-Ext: n1/n3/n28/n78, CA multi-band, 4x4 MIMO, VoNR on
#   SW-Min: n78 only, no CA, 1x1 SISO, VoNR off
PROFILE_CAPABILITIES = {
    "sw-min": build_profile_capability([78], ca_bands=None, mimo_dl=None, mimo_ul=None, vonr=False),
    "sw-std": build_profile_capability([78], ca_bands=[78, 78], mimo_dl="twoLayers", mimo_ul="oneLayer", vonr=True),
    "sw-ext": build_profile_capability(
        [1, 3, 28, 78], ca_bands=[1, 78], mimo_dl="fourLayers", mimo_ul="twoLayers", vonr=True
    ),
}


def _build_ue_radio_capability_bytes(nr_capability: dict) -> bytes:
    """Layers 4->3->2: encode a UE-NR-Capability dict up into the NGAP
    UERadioCapability IE's OCTET STRING content (the inverse of
    decode_ue_radio_capability_container). Always builds a fresh single-item
    RAT container list (rat-Type=nr) - Stage 1 is a full substitution."""
    with _lock:
        _l4.set_val(nr_capability)
        l4_bytes = _l4.to_uper()

        _l3.set_val([{"rat-Type": "nr", "ue-CapabilityRAT-Container": l4_bytes}])
        l3_bytes = _l3.to_uper()

        _l2.set_val(
            {
                "criticalExtensions": (
                    "c1",
                    ("ueRadioAccessCapabilityInformation", {"ue-RadioAccessCapabilityInfo": l3_bytes}),
                )
            }
        )
        return _l2.to_uper()


_lock = threading.RLock()  # RLock, not Lock: apply_capability_pipeline (Steps 4+5) takes
# _lock itself, then calls _build_ue_radio_capability_bytes, which takes _lock again -
# a plain Lock would deadlock on that nested acquisition, single-threaded or not.


def decode_ngap_pdu(raw: bytes) -> Optional[dict]:
    """Decode one NGAP PDU (aligned PER). Returns pycrate's nested get_val() or None on failure."""
    with _lock:
        try:
            _ngap_pdu.from_aper(raw)
            return _ngap_pdu.get_val()
        except Exception:
            return None


def decode_and_reencode_ngap_pdu(raw: bytes) -> Optional[bytes]:
    """Step 3: decode then immediately re-encode the same PDU, atomically under the lock.

    Returns the re-encoded bytes, or None if either decode or encode failed - callers
    should fall back to forwarding the original raw bytes unmodified in that case.
    """
    with _lock:
        try:
            _ngap_pdu.from_aper(raw)
            return _ngap_pdu.to_aper()
        except Exception:
            return None


def get_procedure_code(pdu_val) -> Optional[int]:
    """pdu_val is (choice_name, {'procedureCode': int, 'criticality': ..., 'value': (...)})."""
    if not pdu_val or not isinstance(pdu_val, tuple):
        return None
    return pdu_val[1].get("procedureCode")


def extract_protocol_ie(pdu_val, ie_id: int):
    """Walk protocolIEs of an initiatingMessage/successfulOutcome and return the raw
    value for the given IE id, or None if absent."""
    if not pdu_val or not isinstance(pdu_val, tuple):
        return None
    body = pdu_val[1].get("value")
    if not body or not isinstance(body, tuple):
        return None
    ies = body[1].get("protocolIEs", [])
    for ie in ies:
        if ie.get("id") == ie_id:
            value = ie.get("value")
            return value[1] if isinstance(value, tuple) else value
    return None


def decode_ue_radio_capability_container(ue_radio_capability_bytes: bytes) -> Optional[dict]:
    """Layers 2-4: unwrap the NGAP UERadioCapability OCTET STRING down to UE-NR-Capability.

    Returns a dict: {"ratType": "nr", "capability": <UE-NR-Capability get_val() dict>,
    "container_bytes": <inner ue-CapabilityRAT-Container octets>} or None if any layer
    fails to decode / no NR RAT container is present (e.g. LTE-only capability, or the
    EUTRA-Format variant IE was used instead).

    2026-07-31 finding: "container_bytes" here is the INNER ue-CapabilityRAT-Container
    octets, one ASN.1 layer deeper than ue_radio_capability_bytes (the outer NGAP
    UERadioCapability OCTET STRING, which wraps a UE-CapabilityRAT-ContainerList -
    a SEQUENCE OF, plus that entry's own rat-Type tag - even when there is only one
    nr entry). Confirmed live: a real Realme/imsi-...0004 registration's outer bytes
    (819) vs. rrc_capture.py's case-(b) capture of the same content (813, srsRAN's
    own RRC-layer log already gives the inner container directly) differ by exactly
    this ~6-byte wrapper, even though the two are byte-for-byte identical once the
    outer is unwrapped to this same inner scope. features/extract_features.py's
    _capability_record_from_bytes() uses this field (not the raw bytes passed in)
    for container_bytes/capability_size_bytes so N2-side and RRC-side records are
    comparable at the same ASN.1 nesting level - see xlayer()'s docstring.
    """
    with _lock:
        try:
            _l2.from_uper(ue_radio_capability_bytes)
            l2val = _l2.get_val()
        except Exception:
            return None

    ext = l2val.get("criticalExtensions")
    if not ext or ext[0] != "c1" or not isinstance(ext[1], tuple):
        return None
    c1_choice, c1_body = ext[1]
    if c1_choice != "ueRadioAccessCapabilityInformation":
        return None
    # pycrate get_val() keeps the original hyphenated ASN.1 field names as dict
    # keys (only the generated *class attribute* names are underscored), and this
    # particular IE is itself an OPEN type wrapped as (typename, value).
    rat_info = c1_body.get("ue-RadioAccessCapabilityInfo")
    if not rat_info:
        return None
    l3val = rat_info[1] if isinstance(rat_info, tuple) else rat_info
    if not isinstance(l3val, list):
        # not yet unwrapped by pycrate as a typed OPEN - decode the raw bytes ourselves
        with _lock:
            try:
                _l3.from_uper(rat_info if isinstance(rat_info, bytes) else bytes(rat_info))
                l3val = _l3.get_val()
            except Exception:
                return None

    nr_items = [item for item in l3val if item.get("rat-Type") == "nr"]
    if not nr_items:
        return None
    nr_container_bytes = nr_items[0]["ue-CapabilityRAT-Container"]

    with _lock:
        try:
            _l4.from_uper(nr_container_bytes)
            l4val = _l4.get_val()
        except Exception:
            return None

    return {"ratType": "nr", "capability": l4val, "container_bytes": bytes(nr_container_bytes)}


def summarize_capability(capability: dict) -> dict:
    """Best-effort extraction of the fields the project's testbed architecture notes §6.1/§6.3 target.

    Field names below are the literal (hyphenated) ASN.1 identifiers pycrate's
    get_val() returns as dict keys - confirmed against a live-captured, real-handset
    UE-NR-Capability (the project's testbed architecture notes §6.2), not guessed from the spec text.

    Note: 5G NR RRC has no 'ue-Category' IE (that is an LTE/EUTRA concept carried
    over loosely in the architecture doc's phrasing) - the closest NR analogue is
    accessStratumRelease, so that is what is reported under that heading.
    """
    rf_params = capability.get("rf-Parameters", {}) or {}
    bands = rf_params.get("supportedBandListNR", []) or []
    band_ids = [b.get("bandNR") for b in bands]

    # CA support is a dedicated list of multi-band combinations, not inferable
    # from the standalone band list count alone.
    band_combos = rf_params.get("supportedBandCombinationList", []) or []
    ca_supported = len(band_combos) > 0

    # MIMO layer counts live per component-carrier feature set (ENUM values like
    # 'twoLayers'/'fourLayers'), referenced indirectly from featureSetCombinations -
    # walk featureSets directly instead of resolving that indirection. Downlink is a
    # flat field; uplink is nested one level deeper under mimo-CB-PUSCH (confirmed
    # live - not symmetric with the downlink field naming).
    feature_sets = capability.get("featureSets", {}) or {}
    fs_dl = feature_sets.get("featureSetsDownlinkPerCC", []) or []
    fs_ul = feature_sets.get("featureSetsUplinkPerCC", []) or []
    dl_layers = {fs.get("maxNumberMIMO-LayersPDSCH") for fs in fs_dl if fs.get("maxNumberMIMO-LayersPDSCH") is not None}
    ul_layers = {
        fs["mimo-CB-PUSCH"].get("maxNumberMIMO-LayersCB-PUSCH")
        for fs in fs_ul
        if fs.get("mimo-CB-PUSCH", {}).get("maxNumberMIMO-LayersCB-PUSCH") is not None
    }

    # VoNR: IMS-over-NR support is signalled by presence of the v1540 ims-Parameters
    # extension, reached by walking the nonCriticalExtension chain (confirmed live:
    # it is not present at the top level, only one or more hops down the chain).
    vonr_supported = False
    ext = capability.get("nonCriticalExtension")
    depth = 0
    while isinstance(ext, dict) and depth < 10:
        if "ims-Parameters" in ext:
            vonr_supported = True
            break
        ext = ext.get("nonCriticalExtension")
        depth += 1

    return {
        "access_stratum_release": capability.get("accessStratumRelease"),
        "band_count": len(band_ids),
        "band_ids": band_ids,
        "ca_supported": ca_supported,
        "mimo_dl_layers": sorted(dl_layers) if dl_layers else None,
        "mimo_ul_layers": sorted(ul_layers) if ul_layers else None,
        "vonr_supported": vonr_supported,
    }


# --- Step 5: Stage 2 attack modifiers, labels 1-6 (the project's testbed architecture notes §6.3) ---
#
# Applied on top of the Stage 1 baseline (UERANSIM profiles) or the native handset
# capability (real handsets skip Stage 1 - §6.1). Label 0 is a pass-through: the
# baseline forwards unchanged. All modifiers mutate a *copy* of the baseline dict;
# the caller is always the one that decides what "baseline" means (profile
# template vs. decoded native capability).
#
# Note on label 1 ("Cat downgrade"): per the project's testbed architecture notes Sec6.3, this
# targets `accessStratumRelease` directly (rel15 -> a lower codepoint), since
# extract_features.py's `ue_category` feature is exactly the numeric release
# parsed out of that field (rel15 -> 15). 5G NR RRC has no ue-Category IE at
# all - that is an LTE/EUTRA concept - so this is the closest real NR field
# for a category/generation-downgrade attack, and unlike the previous
# pdcp/featureSets-based modifier (Build 0b finding: produced no signal in
# the tracked 12-feature vector), it is directly observable single-view.
#
# Caveat found while implementing this fix: AccessStratumRelease's ASN.1
# enum (3GPP TS 38.331) is {rel15, rel16, rel17, rel18, spare4..spare1} -
# there is no 'rel8' or any codepoint below rel15 (NR's minimum release is
# itself rel15; a literal "rel15 -> rel8" downgrade, as loosely phrased in
# the architecture doc, is not encodable - pycrate rejects it outright).
# The lowest valid, encodable alternative to the rel15 baseline is one of
# the reserved 'spareN' codepoints; we use 'spare1', which
# extract_features._encode_ue_category's digit-regex parses as ue_category=1
# (vs. the label-0 baseline of 15) - a clear, spec-valid downgrade signal.

_STAGE2_RNG = random.Random(42)  # label 6: reproducible sequence across the whole run, not per-call


def _clear_ims_parameters(ext: Optional[dict]) -> Optional[dict]:
    """Walk a nonCriticalExtension chain and drop ims-Parameters wherever it is,
    without disturbing sibling fields at the same or other levels."""
    if not isinstance(ext, dict):
        return ext
    ext = dict(ext)
    if "ims-Parameters" in ext:
        del ext["ims-Parameters"]
    if "nonCriticalExtension" in ext:
        ext["nonCriticalExtension"] = _clear_ims_parameters(ext["nonCriticalExtension"])
    return ext


def apply_cat_downgrade(capability: dict) -> dict:
    """Label 1: downgrade accessStratumRelease (rel15 -> spare1; see module note
    above for why spare1, not rel8). Directly moves ue_category (§7.1) from 15
    to 1 in the tracked 12-feature vector."""
    cap = dict(capability)
    cap["accessStratumRelease"] = "spare1"
    return cap


def apply_ca_disabled(capability: dict) -> dict:
    """Label 2: clear the CA band combination list(s).

    2026-08-10 finding: a real device (Nothing 3A) declared CA via a
    supportedBandCombinationList-v1610 key not previously seen on any device
    on file (Pixel 8/Realme only ever used the base key plus -v1540/-v1560) -
    left unstripped, this survived the attack on the wire even though
    ca_supported/ca_band_count in raw_12f.csv were unaffected, since
    summarize_capability() only ever reads the base key. Added -v1610 here so
    future collection strips CA more completely at the wire level; no
    re-collection needed for data already gathered under the old behaviour."""
    cap = dict(capability)
    rf = dict(cap.get("rf-Parameters", {}))
    for key in (
        "supportedBandCombinationList",
        "supportedBandCombinationList-v1540",
        "supportedBandCombinationList-v1560",
        "supportedBandCombinationList-v1610",
    ):
        rf.pop(key, None)
    cap["rf-Parameters"] = rf
    return cap


def apply_mimo_reduced(capability: dict) -> dict:
    """Label 3: force MIMO down to 1x1 (SISO) on every declared feature set.

    MIMO-LayersDL's ASN.1 enum only has {twoLayers, fourLayers, eightLayers} -
    there is no 'oneLayer' downlink value (confirmed against the generated
    schema; 3GPP models 1-layer DL as the field being *absent*, not a value).
    Uplink's enum does include 'oneLayer', so DL and UL are handled differently.
    """
    cap = dict(capability)
    feature_sets = cap.get("featureSets")
    if not feature_sets:
        return cap  # already SISO by omission - nothing to reduce
    feature_sets = dict(feature_sets)
    fs_dl = feature_sets.get("featureSetsDownlinkPerCC")
    if fs_dl:
        new_dl = []
        for fs in fs_dl:
            fs = dict(fs)
            fs.pop("maxNumberMIMO-LayersPDSCH", None)
            new_dl.append(fs)
        feature_sets["featureSetsDownlinkPerCC"] = new_dl
    fs_ul = feature_sets.get("featureSetsUplinkPerCC")
    if fs_ul:
        new_ul = []
        for fs in fs_ul:
            fs = dict(fs)
            if "mimo-CB-PUSCH" in fs:
                fs["mimo-CB-PUSCH"] = {**fs["mimo-CB-PUSCH"], "maxNumberMIMO-LayersCB-PUSCH": "oneLayer"}
            new_ul.append(fs)
        feature_sets["featureSetsUplinkPerCC"] = new_ul
    cap["featureSets"] = feature_sets
    return cap


def apply_vonr_denied(capability: dict) -> dict:
    """Label 4: strip the ims-Parameters extension (VoNR support signal)."""
    cap = dict(capability)
    if "nonCriticalExtension" in cap:
        cap["nonCriticalExtension"] = _clear_ims_parameters(cap["nonCriticalExtension"])
    return cap


def apply_combined(capability: dict) -> dict:
    """Label 5: CA disabled + MIMO reduced + VoNR denied together."""
    cap = apply_ca_disabled(capability)
    cap = apply_mimo_reduced(cap)
    cap = apply_vonr_denied(cap)
    return cap


def apply_partial_noise(capability: dict) -> dict:
    """Label 6: probabilistic single-bit (single ROHC profile flag) flip, using a
    module-level RNG seeded with random_state=42 so the sequence is reproducible
    across an entire data-collection run (not re-seeded per call, which would make
    every event identical rather than a distribution)."""
    cap = dict(capability)
    if _STAGE2_RNG.random() < 0.5:
        pdcp = dict(cap.get("pdcp-Parameters", {}))
        profiles = dict(pdcp.get("supportedROHC-Profiles", {}))
        if profiles:
            key = _STAGE2_RNG.choice(list(profiles.keys()))
            profiles[key] = not profiles[key]
            pdcp["supportedROHC-Profiles"] = profiles
            cap["pdcp-Parameters"] = pdcp
    return cap


STAGE2_MODIFIERS = {
    1: apply_cat_downgrade,
    2: apply_ca_disabled,
    3: apply_mimo_reduced,
    4: apply_vonr_denied,
    5: apply_combined,
    6: apply_partial_noise,
}


def apply_capability_pipeline(raw_ngap_pdu: bytes, profile: Optional[str], label: int) -> Optional[bytes]:
    """Steps 4+5 combined: decode, determine the baseline capability (Stage 1
    profile template for UERANSIM, or the UE's own native capability for real
    handsets), apply the Stage 2 label modifier (label 0 = no-op), and re-encode
    the whole NGAP PDU.

    Returns the rewritten NGAP PDU bytes, or None if raw_ngap_pdu does not decode,
    is not a UERadioCapabilityInfoIndication, has no IE 117, or (real-handset case
    only) its capability container does not decode - callers should forward the
    original bytes unmodified in that case.
    """
    with _lock:
        try:
            _ngap_pdu.from_aper(raw_ngap_pdu)
            pdu_val = _ngap_pdu.get_val()
        except Exception:
            return None

        if get_procedure_code(pdu_val) != NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION:
            return None

        choice_name, body = pdu_val
        ies = body["value"][1]["protocolIEs"]
        ie_117 = next((ie for ie in ies if ie.get("id") == NGAP_IE_ID_UE_RADIO_CAPABILITY), None)
        if ie_117 is None:
            return None

        if profile is not None:
            if profile not in PROFILE_CAPABILITIES:
                return None
            baseline = PROFILE_CAPABILITIES[profile]
        else:
            # Real handset: Stage 1 skipped entirely (§6.1) - baseline is whatever
            # the UE actually sent, decoded fresh (not the module singletons,
            # since decode_ue_radio_capability_container itself takes the lock).
            native_ie_value = ie_117.get("value")
            native_bytes = native_ie_value[1] if isinstance(native_ie_value, tuple) else native_ie_value
            decoded = decode_ue_radio_capability_container(native_bytes)
            if decoded is None:
                return None
            baseline = decoded["capability"]

        final_capability = STAGE2_MODIFIERS[label](baseline) if label in STAGE2_MODIFIERS else baseline

        ie_117["value"] = ("UERadioCapability", _build_ue_radio_capability_bytes(final_capability))

        try:
            _ngap_pdu.set_val(pdu_val)
            return _ngap_pdu.to_aper()
        except Exception:
            return None
