#!/usr/bin/env python3
"""collector.py — sweep-harness output -> expert-metrics repo layout.

Input: a stats dir from the llama.cpp fork tools/expert-atlas sweep.sh
(per-probe JSONs: {telemetry, category, idx, selections}) plus the Stage-B
/experts geometry snapshot and run provenance.

Output: models/<model_slug>/manifest.json + runs/<run_id>/*.json, laid out per
schema/run-record.schema.json and schema/manifest.schema.json. Honest-state:
telemetry:false probes are recorded as-is (explicit OFF records).

Usage:
  python3 collector.py --stats sweep-out/stats --geometry sweep-out/experts_before.json \
      --run-id 20260918T120000Z-p100 --llama-cpp-commit 2aa3ada4a \
      --out /path/to/expert-metrics --model-slug Qwopus3.6-35B-A3B-v1-APEX-MTP-I-Nano
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os


def main(argv=None):
    ap = argparse.ArgumentParser(description="record a probe run into expert-metrics")
    ap.add_argument("--stats", required=True, help="sweep.sh stats dir")
    ap.add_argument("--geometry", required=True, help="Stage-B /experts snapshot JSON")
    ap.add_argument("--run-id", required=True, help="run id: <UTC timestamp>-<slug>")
    ap.add_argument("--llama-cpp-commit", required=True)
    ap.add_argument("--out", required=True, help="expert-metrics repo root")
    ap.add_argument("--model-slug", required=True,
                    help="models/ directory name (the model_hash from geometry)")
    ap.add_argument("--atlas-stage", default="C1", choices=["A", "B", "C1", "C2", "C3"])
    args = ap.parse_args(argv)

    geo = json.load(open(args.geometry))
    g = geo["geometry"]
    model_hash = g["model_hash"]
    if args.model_slug != model_hash:
        raise SystemExit(f"refusing: --model-slug {args.model_slug!r} != geometry "
                         f"model_hash {model_hash!r} (engine-id refusal discipline)")

    recorded_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = os.path.join(args.out, "models", args.model_slug, "runs", args.run_id)
    os.makedirs(run_dir, exist_ok=True)

    n_probes = telemetry_probes = 0
    for path in sorted(glob.glob(os.path.join(args.stats, "*.json"))):
        d = json.load(open(path))
        rec = {
            "schema_version": 1,
            "run_id": args.run_id,
            "category": d["category"],
            "idx": int(d["idx"]),
            "telemetry": bool(d.get("telemetry")),
            "selections": d.get("selections", {}) if d.get("telemetry") else {},
            "confounds": {
                "temperature": 0, "top_p": 1.0, "top_k": 0, "min_p": 0.0,
                "decode_only": True, "mtp_off": True,
            },
            "provenance": {
                "engine_id": g["engine_id"],
                "model_hash": model_hash,
                "llama_cpp_commit": args.llama_cpp_commit,
                "atlas_stage": args.atlas_stage,
                "recorded_at": recorded_at,
            },
        }
        name = f"{d['category']}_{int(d['idx'])}.json"
        with open(os.path.join(run_dir, name), "w") as fh:
            json.dump(rec, fh, indent=1)
        n_probes += 1
        telemetry_probes += bool(d.get("telemetry"))

    manifest_path = os.path.join(args.out, "models", args.model_slug, "manifest.json")
    manifest = {"schema_version": 1, "engine_id": g["engine_id"], "model_hash": model_hash}
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path))
    manifest["llama_cpp_commit"] = args.llama_cpp_commit
    manifest["geometry"] = {
        "dense_prefix": g["dense_prefix"],
        "moe_rows": g["moe_rows"],
        "nextn_rows": g["nextn_rows"],
        "n_expert_used": g["n_expert_used"],
    }
    manifest["env_gates"] = {"HYDRA_EXPERT_META": bool(geo.get("telemetry_enabled"))}
    runs = [r for r in manifest.get("runs", []) if r["run_id"] != args.run_id]
    runs.append({
        "run_id": args.run_id,
        "recorded_at": recorded_at,
        "telemetry_present": telemetry_probes > 0,
        "n_probes": n_probes,
        "artifacts": [],
    })
    manifest["runs"] = runs
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=1)

    print(f"recorded {n_probes} probes ({telemetry_probes} with telemetry) -> {run_dir}")
    if telemetry_probes == 0:
        print("honest OFF run recorded (telemetry absent) — no artifact emission expected")


if __name__ == "__main__":
    main()
