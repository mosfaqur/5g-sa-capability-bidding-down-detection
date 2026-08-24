Generate a wide horizontal (16:9 aspect ratio), clean 2D vector technical diagram image that visualises the components and data flows defined in the Mermaid code below.

---
### 1. LAYOUT & FRAMING (MINIMALIST HORIZONTAL)
- Orientation: Single horizontal line from Left to Right, spanning the full width with clean, balanced spacing.
- Domain Titles: Render domain/subgraph names as standalone bold text floating cleanly ABOVE their respective component boxes (do NOT use heavy outer container boxes or shaded backgrounds).
- Background: Pure solid white (#FFFFFF), completely flat vector design (no 3D, no gradients, no shadows).

---
### 2. COMPONENT BOX SPECIFICATIONS
- Standard Nodes:
  * White rounded rectangle cards (#FFFFFF) with a thin, crisp dark border (#1E293B).
  * Inside each box: Place a large, crisp monochrome outline icon centered directly ABOVE the component name.
  * Typography: Clean, centered sans-serif text.
- Highlighted / Adversary Nodes (Threats, Proxies, Anomaly Engines):
  * Fill: Soft pastel rose/pink fill (#FCA5A5 or #FECACA).
  * Border: Dark red dashed border (#DC2626, stroke-dasharray).
  * Icon & Text: Crisp dark icon and bold centered label.

---
### 3. CONNECTOR ARROWS & LABELS
- Standard Flow: Crisp solid black directional arrows with bold step numbering and interface details beside the arrow (e.g., "1. Label (Interface)").
- Intercepted / Internal Flow: Crisp dashed black directional arrows for sequential steps (e.g., "2a. ...", "2b. ...").
- Bypass / Suppressed Path: A faint grey dashed line routed overhead above the components with muted text (e.g., "Baseline Path (Suppressed)").
- Arrow Labels: Clean, horizontal text placed directly adjacent to the corresponding arrow.

---
### 4. OUTPUT REQUIREMENTS
- Output ONLY the finished high-resolution diagram image.
- Ensure all text labels, step numbers, and technical terms from the Mermaid code are rendered accurately and legibly.

---
### MERMAID SOURCE CODE:

```mermaid
flowchart LR
    subgraph SG1 [Empirical Research Findings]
        direction TB
        F1["<b>Finding 1: Cross-Profile LOPO Instability</b><br/>(Macro-F1 0.036 on Held-Out SW-Min)"]
        F2["<b>Finding 2: Open-Set Detection Rate Drop</b><br/>(Cross-Layer 50.3% vs Single-View 59.3%)"]
        F3["<b>Finding 3: CA Ablation Feature Invariance</b><br/>(0.0000 Recall Loss on Label 2)"]
        F4["<b>Finding 4: Cross-Layer Mode 6 Blindness</b><br/>(Cross-Layer F1 = 0.000 on Noise)"]
        F5["<b>Finding 5: VoNR Denial Modem Policy Drop</b><br/>(Cross-Layer VoNR F1 = 0.658 on Pixel 8)"]
        F6["<b>Finding 6: Latency Ceiling Compliance</b><br/>(Max Latency 456.1 ms on Single Cell)"]
        F7["<b>Finding 7: Host-Level Custody Verification</b><br/>(8,511 Records Verified in 4.8 ms)"]
        F8["<b>Finding 8: Sliding-Window Sequence Lift</b><br/>(Macro-F1 0.8720 over 0.8474)"]
        F9["<b>Finding 9: Single-View Bitmask Blindness</b><br/>(Mode 6 Normal Aliasing at N2)"]
    end

    subgraph SG2 [Qualifying Methodological Limitations]
        direction TB
        L1["<b>Limitation 1: Baseline Dependency</b><br/>(Single-View Aliasing on Minimal UEs)"]
        L2["<b>Limitation 2: Open-Set Sample Scarcity</b><br/>(N=1,418 Events and 9 Scalar Fields)"]
        L3["<b>Limitation 3: Feature Collinearity</b><br/>(Size Correlation Masking CA Impact)"]
        L4["<b>Limitation 4: Unmonitored Bitmask Bounds</b><br/>(ROHC Fields Outside Tracked Set)"]
        L5["<b>Limitation 5: Carrier Policy Suppression</b><br/>(Modem Omission of ims-Parameters)"]
        L6["<b>Limitation 6: Topology and Transport Bounds</b><br/>(Single-Cell Cleartext Environment)"]
        L7["<b>Limitation 7: Host-Level Boundary</b><br/>(Vulnerable to Root OS Compromise)"]
        L8["<b>Limitation 8: Sequence Continuity Scope</b><br/>(Requires Stationary Multi-Event Probing)"]
        L9["<b>Limitation 9: Single-View Field Scope Bounds</b><br/>(Single-View Blind to Unmonitored Bitmasks)"]
    end

    F1 <--> L1
    F2 <--> L2
    F3 <--> L3
    F4 <--> L4
    F5 <--> L5
    F6 <--> L6
    F7 <--> L7
    F8 <--> L8
    F9 <--> L9
```















---

**Figure 1**  
*Threat Model of N2 Control-Plane Signalling and On-Path Capability Modification*

```mermaid
flowchart LR
    subgraph UE_Domain ["User Equipment (UE)"]
        UE["<b>Commercial 5G Handset</b><br/>(Physical / Software UE)"]
    end

    subgraph RAN_Domain ["Radio Access Network (NG-RAN)"]
        gNB["<b>srsRAN gNodeB</b><br/>(Access Stratum Termination)"]
    end

    subgraph Core_Domain ["5G Core Network (5GC)"]
        AMF["<b>Open5GS AMF</b><br/>(N2 Control-Plane Ingress)"]
    end

    %% Legitimate / Baseline Signalling Paths
    UE -->|"1. RRC Capability Enquiry / Info (OTA / AS Security)"| gNB
    gNB -->|"2. NGAP UERadioCapabilityInfoIndication (N2 / SCTP)"| AMF

    %% Adversarial Interception & Mutation Path
    Proxy["<b>On-Path NGAP Proxy</b><br/>(Capability Modification Engine)"]
    gNB -.->|"2a. Interception and PER Mutation"| Proxy
    Proxy -.->|"2b. Injected Mutated IEs"| AMF
```


---
**Figure 2**  
*Literature Synthesis and Gap Consolidation Framework Mapping Gaps 1–3 to Research Questions Q1 and Q2*

```mermaid
flowchart TD
    subgraph SG1 [Literature Gaps]
        G1["Gap 1: Absence of Feature-Level<br/>Attack Characterisation<br/>(Karakoc 2023; Moheddine 2025)"]
        G2["Gap 2: Lack of Supervised, Explainable<br/>ML Detection on NGAP IEs<br/>(Feng 2025b; Wang 2020)"]
        G3["Gap 3: Missing Passive ISO 27037<br/>Digital Evidence Integrity<br/>(Mancini 2025; Aiello 2026)"]
    end

    subgraph SG2 [Research Questions]
        RQ1["RQ1: Attack Characterisation<br/>Extract 12-feature NGAP vector<br/>and RRC cross-layer divergence"]
        RQ2["RQ2: ML Pipeline Effectiveness<br/>Supervised RF, TreeSHAP explainability,<br/>latency and ISO 27037 hash-chaining"]
    end

    G1 --> RQ1
    G2 --> RQ2
    G3 --> RQ2
```

---

**Figure 3**  
*Formal Threat Model: On-Path Active MitM Adversary on the N2 Interface*

```mermaid
flowchart TD
    subgraph SG1 [Radio Access Network Domain]
        UE["User Equipment (UE)"] -- "Uu Interface (RRC)" --> GNB["gNodeB (srsRAN)"]
    end
    subgraph SG2 [Control Plane Transport Domain]
        GNB -- "N2 / SCTP (Port 38412)" --> PROXY["On-Path NGAP Proxy (Attacker)"]
        PROXY -- "Mutated N2 / SCTP (Port 38413)" --> AMF["AMF (Open5GS Core)"]
    end
    subgraph SG3 [Core Network Functions]
        AMF <--> AUSF["AUSF / UDM (5G-AKA)"]
        AMF <--> SMF["SMF / UPF (N3 / N4)"]
    end
```

---

**Figure 4**  
*Private 5G Standalone Testbed Architecture and Dual-Point Observation Framework*

```mermaid
flowchart TD
    subgraph SB1 [Physical Radio Environment]
        subgraph FAR [RF-Shielded Faraday Enclosure - RF Isolation Cavity]
            direction TB
            subgraph UES [Physical Commercial Handsets]
                direction LR
                H1["Google Pixel 8<br/>(UE2)"]
                H2["Nothing Phone 3a<br/>(UE3)"]
                H3["Realme RMX3363<br/>(UE4)"]
            end

            USRP["Ettus USRP B210<br/>(5G NR SDR Transceiver)"]
            HACK["HackRF One<br/>(Passive OTA Spectrum Analyser)"]

            UES <==>|"1a. 5G NR Band n78 OTA Duplex Link"| USRP
            HACK -.->|"Passive RF Sniffing / GQRX"| UES
        end
    end

    subgraph SB2 [Host Platform - Kali Linux 2026.2]
        GNB["srsRAN Project 25.10<br/>(CU/DU gNodeB)"]
        SWUE["UERANSIM v3.2.6<br/>(SW-Std, SW-Ext, SW-Min)"]
        
        PROXY["Python NGAP Proxy<br/>Stage 1: Profile Baseline Setter<br/>Stage 2: Attack Injection Engine"]
        CORE["Open5GS 2.7.7 Core<br/>(AMF, SMF, UPF, UDM, UDR, AUSF)"]
        
        RRC_CAP["RRC Capability Capture Hook<br/>(Point A: Untampered Reference)"]
        N2_CAP["N2 PCAP Capture Interface<br/>(Point B: Post-Attack Observation)"]
        CUSTODY["Forensic Custody Logger<br/>(SHA-256 Hash Chain)"]
    end

    %% Physical to Host Interconnect
    USRP <==>|"High-Speed USB 3.0 (UHD 4.6)"| GNB
    HACK -.->|"USB Interface (GQRX)"| SB2

    %% Host Protocol Signalling & Capture
    GNB -->|"1b. RRC Capture"| RRC_CAP
    GNB -->|"2a. NGAP Data Flow (SCTP Port 38412)"| PROXY
    SWUE -->|"2b. SW-UE Control Plane (SCTP Direct)"| PROXY
    PROXY -->|"3a. Adversarial Attack Injection (SCTP Port 38413)"| CORE
    PROXY -->|"3b. N2 PCAP Capture"| N2_CAP

    %% Forensic Custody Flow
    N2_CAP -->|"4a. Post-Attack Data Logs"| CUSTODY
    RRC_CAP -->|"4b. Reference Data Logs"| CUSTODY

    %% Suppressed Baselines (Visual Reference)
    GNB -.->|"Baseline Path (Suppressed)"| CORE
    SWUE -.->|"Baseline Path (Suppressed)"| CORE
```


---
**Figure 6**  
*Machine Learning Classification and Game-Theoretic Attribution Workflow*

```mermaid
flowchart TD
    subgraph IN [Telemetry Ingestion]
        PCAP["Captured N2 PCAP"] --> EXTRACT["pyshark Feature Extraction"]
        EXTRACT --> VEC["12-Feature Tabular Vector"]
    end
    subgraph ML [Classification and Attribution]
        VEC --> RF["Random Forest Classifier\n(200 Estimators, Stratified 5-Fold)"]
        RF --> PRED["Multi-Class Prediction\n(Labels 0 to 6)"]
        RF --> SHAP["TreeSHAP Explainer"]
        SHAP --> EXP["IE Field Attribution\n(Game-Theoretic Validation)"]
    end
```

---

**Figure 7**  
*Cryptographic Hash-Chain Custody Record Architecture*

```mermaid
flowchart TD
    subgraph PREV [Custody Record i-1]
        R1["<b>ChainHash i-1</b>: H_prev"]
    end

    subgraph CURR [Custody Record i: Active Evidence Acquisition]
        subgraph META [Captured Evidence Metadata - 5 Fields]
            direction LR
            M1["1. File SHA-256<br/>(Raw PCAP Digest)"]
            M2["2. Filename<br/>(capture_042.pcap)"]
            M3["3. Timestamp<br/>(ISO 8601 UTC)"]
            M4["4. Attack Mode<br/>(Cat_Downgrade)"]
            M5["5. Session ID<br/>(S_0810)"]
        end

        HASH_OP["<b>Cryptographic Hashing Engine</b><br/>SHA-256( H_prev || FileHash || Timestamp || Mode || SessionID )"]
        R2["<b>ChainHash i</b>: H_curr<br/>(Immutable Log Entry)"]

        META --> HASH_OP
        HASH_OP --> R2
    end

    subgraph NEXT [Custody Record i+1]
        R3["<b>ChainHash i+1</b>: H_next"]
    end

    %% Cryptographic Cascading Chain Links
    R1 ==>|"H_prev Ingestion"| HASH_OP
    R2 ==>|"Forward Cascading Link (H_curr)"| NEXT
```

---

**Figure 8**  
*Two-Stage On-Path NGAP Mediation and Attack Injection Architecture*

```mermaid
flowchart TD
    subgraph SG1 [Radio Interface Signalling]
        UE["User Equipment (UE)<br/>(Physical Commercial Handsets / UERANSIM)"] -->|"RRC: UECapabilityInformation"| GNB["srsRAN Project gNodeB<br/>(Decodes RRC Transfer Syntax)"]
    end

    subgraph SG2 [On-Path Mediation Layer]
        GNB -->|"NGAP over SCTP (Port 38412)"| PROXY["Python NGAP Proxy<br/>(pycrate ASN.1 PER Runtime Engine)"]
        
        PROXY -.->|"UERANSIM Only"| S1["Stage 1: Profile Baseline Setter<br/>(SW-Std / SW-Ext / SW-Min)"]
        PROXY ==>|"Physical Handsets (Bypass Stage 1)"| S2["Stage 2: Attack Injection Engine<br/>(Labels 0 to 6 Semantic Modifiers)"]
        S1 --> S2
        
        S2 -->|"Mutated NGAP PDU (Port 38413)"| AMF["Open5GS AMF<br/>(Commits IEs to Session Cache)"]
    end

    subgraph SG3 [Multi-Class Attack Taxonomy - Stage 2 Mutations]
        direction TB
        M0["<b>Label 0: Normal Baseline</b><br/>(Unmodified Container)"]
        M1["<b>Label 1: Category Downgrade</b><br/>(accessStratumRelease to spare1)"]
        M2["<b>Label 2: CA Disabled</b><br/>(supportedBandCombinationList Stripped)"]
        M3["<b>Label 3: MIMO Reduced</b><br/>(maxNumberMIMO-Layers to 1x1 SISO)"]
        M4["<b>Label 4: VoNR Denied</b><br/>(voiceOverNR Flag Cleared)"]
        M5["<b>Label 5: Combined</b><br/>(Simultaneous Composite Downgrade)"]
        M6["<b>Label 6: Partial / Noise</b><br/>(Low-Impact Syntax Bit-Flip)"]

        S2 --> M0
        S2 --> M1
        S2 --> M2
        S2 --> M3
        S2 --> M4
        S2 --> M5
        S2 --> M6
    end
```

---

**Figure 10**  
*Taxonomy of Feature Discriminative Power Across Protocol Dimensions*

```mermaid
flowchart TD
    subgraph SG1 [Taxonomy of Feature Discriminative Power - 12 Dimensions]
        direction TB
        F_PERF["<b>Perfect Discriminator (|r| = 1.000)</b><br/>• ue_category (Mode 1 Cat-Downgrade: |r| = 1.000)"]
        
        F_LARGE["<b>Large Effect Discriminators (|r| &ge; 0.500)</b><br/>• ca_supported and ca_band_count (Modes 2, 5: |r| = 0.834)<br/>• mimo_layers_dl (Modes 3, 5: |r| = 0.834)<br/>• vonr_supported (Modes 4, 5: |r| = 0.662)"]
        
        F_MED["<b>Medium Effect Discriminator (0.300 &le; |r| < 0.500)</b><br/>• mimo_layers_ul (Modes 3, 5: |r| = 0.338)"]
        
        F_SMALL["<b>Small Structural Discriminator (0.100 &le; |r| < 0.300)</b><br/>• total_capability_size_bytes (Modes 2, 5: |r| = 0.166 to 0.199)"]
        
        F_ENV["<b>Environmental / Timing Dimension (Weak: |r| &le; 0.111)</b><br/>• session_timestamp_delta (Modes 1, 6: |r| = 0.052 to 0.111)"]
        
        F_NULL["<b>Non-Discriminative Invariant Dimensions (|r| < 0.010)</b><br/>• ie_field_count, nr_band_count (Structural Invariants)<br/>• volte_supported, psm_supported (Constant Zero Controls)"]

        F_PERF --> F_LARGE
        F_LARGE --> F_MED
        F_MED --> F_SMALL
        F_SMALL --> F_ENV
        F_ENV --> F_NULL
    end
```

---

**Figure 12**  
*Intra-Class Stability Distribution Across Protocol and Environmental Features*

```mermaid
flowchart LR
    subgraph SG1 [Deterministic Protocol Features: CoV = 0.000 and 100% Modal Agreement]
        direction TB
        F_CAT["<b>UE Category</b><br/>ue_category"]
        F_CA["<b>Carrier Aggregation</b><br/>ca_supported, ca_band_count"]
        F_MIMO["<b>Spatial Multiplexing</b><br/>mimo_layers_dl, mimo_layers_ul"]
        F_VONR["<b>Voice and Band Configuration</b><br/>vonr_supported, nr_band_count"]
        F_SIZE["<b>Container Geometry and Invariant Controls</b><br/>total_capability_size_bytes, ie_field_count<br/>(volte_supported, psm_supported)"]
    end

    subgraph SG2 [Host Scheduling Dispersion: Elevated Jitter with CoV = 0.231 to 0.373]
        direction TB
        F_JITT["<b>Host Scheduling Jitter</b><br/>session_timestamp_delta<br/>(CPU Scheduling, USB 3.0 Polling, RACH Backoff)"]
    end
```



---

**Figure 13**  
*Dual-Point Cross-Layer Observation and Semantic Difference Architecture*

```mermaid
flowchart TD
    subgraph SG1 [Dual-Point Observation Architecture]
        OTA["<b>Over-the-Air Transmission</b><br/>(Uu Air Interface)"] -->|"RRC Enquiry / Response"| GNB["<b>srsRAN Project gNodeB</b><br/>(Decodes RRC into Memory)"]
        
        GNB -->|"Untampered Decode"| PTA["<b>Point A: Untampered Reference</b><br/>(rrc_capture.py Hook / Case a Store)"]
        GNB -->|"N2 Signalling (SCTP Port 38412)"| PROXY["<b>On-Path NGAP Proxy</b><br/>(Applies Semantic ASN.1 Mutation)"]
        PROXY -->|"Mutated Signalling (Port 38413)"| PTB["<b>Point B: Observed Container</b><br/>(Post-Attack N2 PCAP at Core)"]
    end

    subgraph SG2 [Cross-Layer Consistency Comparator]
        PTA -->|"Reference Vector (P_RRC)"| COMP["<b>Semantic Difference Engine</b><br/>&Delta; = Extract(P_RRC) &ominus; Extract(P_NGAP)"]
        PTB -->|"Observed Vector (P_NGAP)"| COMP
        
        COMP -->|"Evaluates Delta &ne; 0"| VEC["<b>9-Feature Cross-Layer Divergence Vector</b><br/>• ca_supported_match, vonr_supported_match<br/>• ue_category_delta, ca_band_count_delta<br/>• mimo_dl_delta, mimo_ul_delta<br/>• nr_band_count_delta, ie_field_count_delta<br/>• num_fields_mismatched"]
    end
```



---

**Figure 14**  
*Taxonomy of Supervised Detection Pipelines and Multi-Class Performance*

```mermaid
flowchart LR
    subgraph SG1 [Input Protocol Telemetry]
        direction TB
        D1["<b>Single-Event N2 Vector</b><br/>• 12 Extracted Features<br/>• 4,225 Events (6 Active Profiles)"]
        D2["<b>Sliding-Window N2 Vector</b><br/>• 36 Aggregated Features (N=3)<br/>• 3,783 Windows (6 Active Profiles)"]
        D3["<b>Cross-Layer Divergence Vector</b><br/>• 9 Semantic Delta Features<br/>• 1,418 Paired Events (Physical Handsets)"]
    end

    subgraph SG2 [Supervised Classifiers - Random Forest 200 Trees]
        direction TB
        M1["<b>Single-Event Classifier</b><br/>Macro-F1: 0.8474 | Accuracy: 0.8476"]
        M2["<b>Sliding-Window Classifier</b><br/>Macro-F1: 0.8720 | Accuracy: 0.8718"]
        M3["<b>Cross-Layer Classifier</b><br/>Macro-F1: 0.7475 | Accuracy: 0.7863"]
    end

    subgraph SG3 [Empirical Multi-Class Detection Insights]
        direction TB
        O1["<b>Mode 1 (Cat-Downgrade)</b>: F1 = 1.000<br/>(Deterministic separation across all models)"]
        O2["<b>Modes 2, 3 and 5 (CA, MIMO, Combined)</b><br/>Single F1: 0.859–0.881 | Cross-Layer F1: 1.000"]
        O3["<b>Mode 4 (VoNR-Denied)</b><br/>Single F1: 0.848 | Cross F1: 0.658 (Pixel 8 native baseline)"]
        O4["<b>Mode 6 (Partial / Noise)</b><br/>Single F1: 0.746 | Cross F1: 0.000 (Unmonitored ROHC)"]
        O5["<b>Mode 0 (Normal Baseline)</b><br/>Single F1: 0.722 | Window F1: 0.824 (Temporal gain)"]
    end

    %% Pipeline Routing
    D1 --> M1
    D2 --> M2
    D3 --> M3

    %% Clean Insight Linkages
    M1 --> O1
    M1 --> O3
    M1 --> O4
    M2 --> O5
    M3 --> O2
```

---

**Figure 25**  
*ISO/IEC 27037:2012 Digital Forensic Acquisition and SHA-256 Hash-Chaining Pipeline*

```mermaid
flowchart TD
    subgraph SG1 [Phase 1: Digital Evidence Acquisition at N2]
        direction TB
        P1["<b>Raw SCTP Signalling Stream</b><br/>(gNodeB to AMF Port 38412)"]
        P2["<b>Non-Invasive Packet Capture Engine</b><br/>(tcpdump / libpcap Interface Hook)"]
        P3["<b>Raw PCAP Evidence File</b><br/>(ngap_labelX_eventY.pcap)"]
        P4["<b>Cryptographic Hash Computation</b><br/>(File SHA-256 Digest: H_file)"]
        
        P1 --> P2 --> P3 --> P4
    end

    subgraph SG2 [Phase 2: Cryptographic Hash-Chain Custody Log Engine]
        direction TB
        H1["<b>Record Payload Construction</b><br/>• File Hash + Timestamp (ISO 8601)<br/>• Attack Mode + Session ID"]
        H0["<b>Genesis / Prior State</b><br/>(H_i-1 from Genesis Block / Prior Event)"]
        H2["<b>Chained Digest Computation</b><br/>H_i = SHA-256(H_i-1 || H_file || TS || Mode || Session)"]
        H3["<b>Append-Only Custody Log</b><br/>(chain_of_custody.log)"]
        
        H0 --> H2
        H1 --> H2
        H2 --> H3
    end

    subgraph SG3 [Phase 3: Automated Forensic Verification Audit]
        direction TB
        V1["<b>Track A: Chain-Hash Recomputation</b><br/>8,511 Records in 4.8 ms (1.76M records/s)<br/>Integrity: 100.0% (Zero breaks)"]
        V2["<b>Track B: On-Disk File Hash Audit</b><br/>8,425 Files in 118.8 s (70.9 files/s)<br/>Concordance: 99.61% raw / 100.0% active dataset"]
        ADM["<b>ISO/IEC 27037:2012 Aligned Evidentiary Package</b><br/>• Integrity, Authenticity and Provenance Verified<br/>• Mathematically Provable Non-Repudiation"]
        
        V1 --> ADM
        V2 --> ADM
    end

    %% Inter-phase linkages
    P4 --> H1
    H3 --> V1
    H3 --> V2
```

---

**Figure 27**  
*Production 5G Core Deployment Architecture with Passive Optical N2 TAP, ML Inference and SOC/SIEM Integration*

```mermaid
flowchart TD
    subgraph SG1 [1. 5G Radio Access Network]
        direction LR
        GNB1["<b>Commercial gNodeB / CU</b><br/>(Centralised Unit / Air Interface)"]
        GNB2["<b>Secondary gNodeB / DU</b><br/>(Distributed Unit / Base Station)"]
    end

    subgraph SG2 [2. Production Core Transport Network]
        direction LR
        TAP["<b>Passive Optical TAP / Port Mirror</b><br/>(N2 Reference Point: SCTP Port 38412)"]
        AMF["<b>Access & Mobility Management Function</b><br/>(AMF Control-Plane Ingress)"]
        
        GNB1 -->|"Unmodified N2 Signalling"| TAP
        GNB2 -->|"Unmodified N2 Signalling"| TAP
        TAP -->|"Zero Insertion Loss (Live Traffic)"| AMF
    end

    subgraph SG3 [3. Real-Time AI Detection and Forensic Engine]
        direction TB
        PARSER["<b>Kernel-Space Packet Capture</b><br/>(eBPF / XDP High-Speed Filter)"]
        DEC["<b>High-Performance ASN.1 Decoder</b><br/>(pycrate PER Streaming Parser)"]
        EXT["<b>12-Feature Extraction Module</b><br/>(Real-Time Tabular Telemetry Builder)"]
        ML["<b>Frozen Random Forest Inference Engine</b><br/>(rf_single_event.pkl | 5.4 ms Latency)"]
        DECIS{"<b>Multi-Class Decision</b><br/>Predicted Attack Label"}

        PARSER --> DEC --> EXT --> ML --> DECIS
    end

    subgraph SG4 [4. Forensic Vault and Operator Mitigation]
        direction TB
        LOG1["<b>Standard Session Audit Log</b><br/>(SHA-256 Chained Custody Engine)"]
        ALERT["<b>High-Priority Forensic Alert</b><br/>(CEF / JSON Schema with Top 3 SHAP)"]
        SIEM["<b>Enterprise SOC / SIEM Platform</b><br/>(Splunk / Elastic / Microsoft Sentinel)"]
        NWDAF["<b>Network Data Analytics Function</b><br/>(3GPP TS 23.501 Analytics Service)"]

        DECIS -->|"Label 0: Benign"| LOG1
        DECIS -->|"Labels 1 to 6: Attack"| ALERT
        ALERT --> SIEM
        ALERT --> NWDAF
    end

    %% Replicated Optical Tap Feed
    TAP -.->|"Passive Replicated Stream"| PARSER

    %% Automated Remediation Closed-Loop
    NWDAF -.->|"Automated UE Context Release"| AMF
```



---


**Figure 28**  
*Strict Pairing Between Empirical Research Findings and Methodological Limitations*

```mermaid
flowchart LR
    subgraph SG1 [Empirical Research Findings]
        direction TB
        F1["<b>Finding 1: Cross-Profile LOPO Instability</b><br/>(Macro-F1 0.036 on Held-Out SW-Min)"]
        F2["<b>Finding 2: Open-Set Detection Rate Drop</b><br/>(Cross-Layer 50.3% vs Single-View 59.3%)"]
        F3["<b>Finding 3: CA Ablation Feature Invariance</b><br/>(0.0000 Recall Loss on Label 2)"]
        F4["<b>Finding 4: Cross-Layer Mode 6 Blindness</b><br/>(Cross-Layer F1 = 0.000 on Noise)"]
        F5["<b>Finding 5: VoNR Denial Modem Policy Drop</b><br/>(Cross-Layer VoNR F1 = 0.658 on Pixel 8)"]
        F6["<b>Finding 6: Latency Ceiling Compliance</b><br/>(Max Latency 456.1 ms on Single Cell)"]
        F7["<b>Finding 7: Host-Level Custody Verification</b><br/>(8,511 Records Verified in 4.8 ms)"]
        F8["<b>Finding 8: Sliding-Window Sequence Lift</b><br/>(Macro-F1 0.8720 over 0.8474)"]
        F9["<b>Finding 9: Single-View Bitmask Blindness</b><br/>(Mode 6 Normal Aliasing at N2)"]
    end

    subgraph SG2 [Qualifying Methodological Limitations]
        direction TB
        L1["<b>Limitation 1: Baseline Dependency</b><br/>(Single-View Aliasing on Minimal UEs)"]
        L2["<b>Limitation 2: Open-Set Sample Scarcity</b><br/>(N=1,418 Events and 9 Scalar Fields)"]
        L3["<b>Limitation 3: Feature Collinearity</b><br/>(Size Correlation Masking CA Impact)"]
        L4["<b>Limitation 4: Unmonitored Bitmask Bounds</b><br/>(ROHC Fields Outside Tracked Set)"]
        L5["<b>Limitation 5: Carrier Policy Suppression</b><br/>(Modem Omission of ims-Parameters)"]
        L6["<b>Limitation 6: Topology and Transport Bounds</b><br/>(Single-Cell Cleartext Environment)"]
        L7["<b>Limitation 7: Host-Level Boundary</b><br/>(Vulnerable to Root OS Compromise)"]
        L8["<b>Limitation 8: Sequence Continuity Scope</b><br/>(Requires Stationary Multi-Event Probing)"]
        L9["<b>Limitation 9: Single-View Field Scope Bounds</b><br/>(Single-View Blind to Unmonitored Bitmasks)"]
    end

    F1 <--> L1
    F2 <--> L2
    F3 <--> L3
    F4 <--> L4
    F5 <--> L5
    F6 <--> L6
    F7 <--> L7
    F8 <--> L8
    F9 <--> L9
```

---



---



---





