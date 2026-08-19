# Chapter 5 figure captions (SHAP + confusion matrices)

These figures belong in Chapter 5 (W5.1-W5.3 SHAP analysis / confusion matrices),
not Chapter 4. Renumber [Figure X.Y] placeholders to the actual Ch 5 sequence
before final submission.

## shap_single_summary.png
[Figure X.Y — assign number in Ch 5 sequence]: Mean |SHAP| values for the
single-event 12-feature Random Forest model. Feature names correspond to UE
radio capability IE fields defined in 3GPP TS 38.306 and carried in the NGAP
UERadioCapabilityInfoIndication PDU of 3GPP TS 38.413 (3GPP, 2024c, 2024e).
Confirmed: bar chart covers all 12 tracked features, labelled by IE field name.
Top feature: mimo_layers_dl.

## shap_window_summary.png
[Figure X.Y]: Mean |SHAP| values for the sliding-window (N=3) Random Forest
model, aggregated across the 12 tracked features and broken out by time-step
(t0 = oldest event in the window, t2 = most recent) to show each event's
relative contribution within the window. Secondary to the single-event SHAP
figure above. Top feature: mimo_layers_dl.

## shap_xlayer_summary.png
[Figure X.Y]: Mean |SHAP| values for the cross-layer consistency model (9
trained features; capability_size_delta and container_hash_match excluded,
the project's testbed architecture notes §7.2). Detection is driven by RRC-vs-N2 field
divergence (num_fields_mismatched and the specific semantic fields), not by
the raw capability value. Top feature: mimo_dl_delta.

## confusion_matrix_single.png
[Figure X.Y]: Confusion matrix for the single-event Random Forest classifier
across seven attack classes.

## confusion_matrix_window.png
[Figure X.Y]: Confusion matrix for the sliding-window Random Forest classifier
(N=3) across seven attack classes.

## confusion_matrix_xlayer.png
[Figure X.Y]: Confusion matrix for the cross-layer consistency model (real
handsets) across seven attack classes.
