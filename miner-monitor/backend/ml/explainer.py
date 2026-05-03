"""
Explainer — generates human-readable anomaly explanations.

Takes IF feature attributions + LSTM per-feature errors.
Produces: ranked features, failure signature, confidence, narrative.

NO external dependencies (no SHAP). Works everywhere.
"""
import logging

logger = logging.getLogger("ml.explainer")

FAILURE_SIGNATURES = {
    "cooling_failure": {
        "features": {"fan1", "fan2", "temp2_1", "temp2_2", "temp2_3", "temp2_4",
                      "temp_max", "temp_spread"},
        "label": "Probable cooling system issue",
        "action": "Check fan bearings, clean dust filters, verify ambient temperature.",
    },
    "board_degradation": {
        "features": {"chain_rate1", "chain_rate2", "chain_rate3", "chain_rate4",
                      "chain_rate_imbalance", "GHS 5s"},
        "label": "Probable hash board degradation",
        "action": "Inspect board connectors, check for chip failures, compare per-board rates.",
    },
    "hashrate_drop": {
        "features": {"GHS 5s", "GHS av"},
        "label": "Overall hashrate deviation",
        "action": "Check pool settings, firmware version, and overclock configuration.",
    },
    "thermal_imbalance": {
        "features": {"temp_spread", "temp2_1", "temp2_2", "temp2_3", "temp2_4"},
        "label": "Thermal imbalance across boards",
        "action": "One board is running significantly hotter. Check airflow and board placement.",
    },
}


class AnomalyExplainer:

    def explain(self, if_result: dict, lstm_result: dict,
                baseline: dict = None, top_k: int = 5) -> dict:
        """Produce a unified explanation from IF + LSTM results."""

        is_anomaly = if_result.get("is_anomaly", False) or lstm_result.get("is_anomaly", False)
        if not is_anomaly:
            return {
                "is_anomaly": False,
                "ranked_features": [],
                "confidence": None,
                "signature": None,
                "narrative": "All systems operating within normal parameters.",
            }

        # Gather attributions from IF (permutation-based)
        if_attrs = {a["feature"]: a for a in if_result.get("feature_attributions", [])}

        # Gather LSTM per-feature errors
        lstm_errs = {f["feature"]: f for f in lstm_result.get("per_feature_error", [])}

        all_feats = set(if_attrs.keys()) | set(lstm_errs.keys())
        if not all_feats:
            severity = if_result.get("severity", "anomaly")
            score = if_result.get("anomaly_score", 0)
            return {
                "is_anomaly": True,
                "ranked_features": [],
                "confidence": "low",
                "signature": None,
                "narrative": (
                    f"Anomaly detected (score: {score:.1%}, severity: {severity}). "
                    f"Feature attribution unavailable — model may need retraining with more data."
                ),
            }

        # Normalize and combine
        if_max = max((abs(a["contribution"]) for a in if_attrs.values()), default=1) or 1
        lstm_max = max((abs(e.get("error_normalized", 0)) for e in lstm_errs.values()), default=1) or 1

        ranked = []
        for feat in all_feats:
            if_a = if_attrs.get(feat, {})
            lstm_e = lstm_errs.get(feat, {})

            if_norm = abs(if_a.get("contribution", 0)) / if_max
            lstm_norm = abs(lstm_e.get("error_normalized", 0)) / lstm_max
            importance = 0.6 * if_norm + 0.4 * lstm_norm

            entry = {
                "feature": feat,
                "importance": round(importance, 4),
                "value": if_a.get("value"),
                "baseline": if_a.get("baseline"),
                "pct_deviation": if_a.get("pct_deviation", 0),
                "contribution": if_a.get("contribution", 0),
                "direction": if_a.get("direction", "unknown"),
            }
            ranked.append(entry)

        ranked.sort(key=lambda r: -r["importance"])
        top = ranked[:top_k]

        # Confidence from model agreement
        if_top = set(list(if_attrs.keys())[:3])
        lstm_top = set(list(lstm_errs.keys())[:3])
        overlap = len(if_top & lstm_top) if if_attrs and lstm_errs else 0
        confidence = "high" if overlap >= 2 else "medium" if overlap >= 1 or (if_attrs and not lstm_errs) else "low"

        # Match failure signature
        top_names = {f["feature"] for f in top}
        signature = self._match_signature(top_names)

        # Build narrative
        score = if_result.get("anomaly_score", 0)
        severity = if_result.get("severity", "anomaly")
        narrative = self._narrative(score, severity, confidence, signature, top)

        return {
            "is_anomaly": True,
            "ranked_features": top,
            "confidence": confidence,
            "signature": signature,
            "narrative": narrative,
        }

    def _match_signature(self, top_features):
        best, best_n = None, 0
        for sig_id, sig in FAILURE_SIGNATURES.items():
            n = len(top_features & sig["features"])
            if n > best_n and n >= 2:
                best_n = n
                best = {"id": sig_id, "label": sig["label"], "action": sig["action"], "match": n}
        return best

    def _narrative(self, score, severity, confidence, signature, top):
        parts = []
        sev = {"critical": "Critical", "anomaly": "Moderate"}.get(severity, "")
        parts.append(f"{sev} anomaly detected (score: {score:.1%}, confidence: {confidence}).")

        if signature:
            parts.append(f"{signature['label']}.")
            parts.append(signature["action"])
        else:
            parts.append("No specific failure pattern matched.")

        if top:
            descs = []
            for f in top[:3]:
                s = f["feature"]
                if f.get("pct_deviation") and abs(f["pct_deviation"]) > 0.5:
                    sign = "+" if f["pct_deviation"] > 0 else ""
                    s += f" ({sign}{f['pct_deviation']:.1f}%)"
                elif f.get("value") is not None and f.get("baseline") is not None:
                    s += f" ({f['value']:.1f} vs baseline {f['baseline']:.1f})"
                descs.append(s)
            parts.append("Key features: " + ", ".join(descs) + ".")

        return " ".join(parts)


explainer = AnomalyExplainer()
