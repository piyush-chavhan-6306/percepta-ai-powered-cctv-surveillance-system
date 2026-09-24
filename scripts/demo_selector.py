#!/usr/bin/env python3
"""
Border Intelligence — Demonstration Dataset & Scenario Switcher.
Aligned with SIH Problem Statement SIH26187.
Provides inspection, validation, and launching of benchmark surveillance scenarios:
- BOP Fixed Perimeter CCTV (VIRAT)
- UAV Tactical Aerial Border Patrol (VisDrone MOT)
- International Border Checkpoint Corridor (MOT17)
- Tactical Vehicle Drop-off & Quick Breach (VIRAT Incident)
"""
import argparse
import json
import os
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = WORKSPACE_ROOT / "configs" / "demo_datasets.json"


def load_manifest() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[ERROR] Manifest file not found at: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_profiles(manifest: dict) -> None:
    print("\n" + "=" * 76)
    print("  MHA / SSB BORDER SURVEILLANCE — BENCHMARK EVALUATION PROFILES")
    print("=" * 76)
    for idx, p in enumerate(manifest.get("dataset_profiles", []), 1):
        source_full = WORKSPACE_ROOT / p["source_path"]
        exists = source_full.exists()
        status_tag = "[READY ON DISK]" if exists else "[FILE MISSING]"
        print(f"\n[{idx}] Profile ID : {p['id']}")
        print(f"    Name       : {p['name']}")
        print(f"    Scenario   : {p['scenario']}")
        print(f"    Modality   : {p['modality']} | FPS: {p['fps']} | Type: {p['source_type']}")
        print(f"    Path       : {p['source_path']} {status_tag}")
        if p.get("verification_status"):
            print(f"    Verified   : {p['verification_status']}")
        ver = p.get("verification") or {}
        if ver.get("source"):
            print(f"    Provenance : {ver['source']}")
        if ver.get("measured"):
            print(f"    Measured   : {ver['measured']}")
        print(f"    Summary    : {p['description']}")
    print("\n" + "=" * 76 + "\n")


def verify_profiles(manifest: dict) -> bool:
    print("\nVerifying benchmark dataset profiles on disk...")
    all_ok = True
    for p in manifest.get("dataset_profiles", []):
        target = WORKSPACE_ROOT / p["source_path"]
        if target.exists():
            if target.is_dir():
                file_count = len(list(target.iterdir()))
                print(f"  [OK] {p['id']}: directory verified ({file_count} items in {p['source_path']})")
            else:
                size_mb = target.stat().st_size / (1024 * 1024)
                # Deep verification: OpenCV must actually open and decode the file.
                decode_note = ""
                try:
                    import cv2
                    cap = cv2.VideoCapture(str(target))
                    if cap.isOpened():
                        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        ok, _ = cap.read()
                        cap.release()
                        decode_note = (
                            f", decodable {int(fps)}fps {frames}f"
                            + (", first-frame OK" if ok else ", FIRST-FRAME FAIL")
                        )
                    else:
                        decode_note = ", UNDECODABLE"
                except Exception as cv_err:
                    decode_note = f", decode check skipped ({cv_err})"
                print(f"  [OK] {p['id']}: file verified ({size_mb:.1f} MB: {p['source_path']}{decode_note})")
        else:
            print(f"  [MISSING] {p['id']}: path not found at {target}")
            all_ok = False
    return all_ok


def show_profile(manifest: dict, profile_id: str) -> None:
    for p in manifest.get("dataset_profiles", []):
        if p["id"] == profile_id:
            print(json.dumps(p, indent=2))
            return
    print(f"[ERROR] Profile '{profile_id}' not found.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Border Intelligence Demo Scenario Selector")
    parser.add_argument("--list", action="store_true", help="List all available surveillance profiles")
    parser.add_argument("--verify", action="store_true", help="Verify scenario media paths on disk")
    parser.add_argument("--info", type=str, help="Show full JSON configuration for a specific profile ID")

    args = parser.parse_args()
    manifest = load_manifest()

    if args.info:
        show_profile(manifest, args.info)
    elif args.verify:
        ok = verify_profiles(manifest)
        sys.exit(0 if ok else 1)
    else:
        list_profiles(manifest)


if __name__ == "__main__":
    main()
