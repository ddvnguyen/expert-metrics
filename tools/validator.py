#!/usr/bin/env python3
"""validator.py — CI gate for expert-metrics: every record/artifact/manifest
validates against schema/, engine-id consistency is enforced (no mixed models
inside one model dir), and derived artifacts only exist when telemetry was
present (honest-state discipline)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schema")


def fail(msg):
    print(f"validator: FAIL {msg}", file=sys.stderr)
    sys.exit(1)


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name)) as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description="validate expert-metrics repo")
    ap.add_argument("repo_root")
    args = ap.parse_args(argv)
    root = args.repo_root

    if jsonschema is None:
        print("validator: jsonschema not installed — structural checks only")
    run_schema = load_schema("run-record.schema.json")
    experts_schema = load_schema("experts.schema.json")
    manifest_schema = load_schema("manifest.schema.json")

    n_records = n_models = n_artifacts = 0
    for manifest_path in sorted(glob.glob(os.path.join(root, "models", "*", "manifest.json"))):
        model_dir = os.path.dirname(manifest_path)
        model_slug = os.path.basename(model_dir)
        manifest = json.load(open(manifest_path))
        if jsonschema:
            jsonschema.validate(manifest, manifest_schema)
        if manifest["model_hash"] != model_slug:
            fail(f"{model_slug}: manifest model_hash mismatch")
        engine_id = manifest["engine_id"]
        n_models += 1

        for run in manifest.get("runs", []):
            run_dir = os.path.join(model_dir, "runs", run["run_id"])
            if not os.path.isdir(run_dir):
                fail(f"{model_slug}/{run['run_id']}: manifest run missing on disk")
            telemetry_seen = False
            for rec_path in sorted(glob.glob(os.path.join(run_dir, "*.json"))):
                rec = json.load(open(rec_path))
                if jsonschema:
                    jsonschema.validate(rec, run_schema)
                if rec["provenance"]["engine_id"] != engine_id:
                    fail(f"{rec_path}: engine_id mismatch vs manifest (mixed models)")
                if rec["telemetry"]:
                    if not rec["selections"]:
                        fail(f"{rec_path}: telemetry true but selections empty")
                    telemetry_seen = True
                else:
                    if rec["selections"]:
                        fail(f"{rec_path}: telemetry false but selections present (fabricated)")
                n_records += 1
            if telemetry_seen != run["telemetry_present"]:
                fail(f"{model_slug}/{run['run_id']}: telemetry_present flag wrong")

        for art_path in sorted(glob.glob(os.path.join(model_dir, "artifacts", "experts.json"))):
            art = json.load(open(art_path))
            if jsonschema:
                jsonschema.validate(art, experts_schema)
            if art["provenance"]["engine_id"] != engine_id:
                fail(f"{art_path}: engine_id mismatch vs manifest")
            if not art["provenance"].get("telemetry_present"):
                fail(f"{art_path}: artifact emitted without telemetry (honest-state violation)")
            if not art["provenance"].get("gates", {}).get("replication"):
                fail(f"{art_path}: replication gate not recorded as passed")
            n_artifacts += 1

    print(f"validator: OK — {n_models} models, {n_records} records, {n_artifacts} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
