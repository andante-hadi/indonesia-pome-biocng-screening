#!/usr/bin/env python3
"""Prepare Trase Indonesia palm oil mill data for screening analysis."""

import csv
import json
from collections import defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
RAW_GEOJSON = BASE / "raw" / "trase_IDN_PO_mills_clean.geojson"
OUT_DIR = BASE / "processed"

MILL_FIELDS = [
    "trase_code",
    "uml_id",
    "group",
    "company",
    "mill_name",
    "latitude",
    "longitude",
    "capacity_tonnes_ffb_hour",
    "active",
    "earliest_year_of_existence",
    "earliest_year_of_existence_source",
    "kabupaten_name",
    "kabupaten_trase_id",
    "province_name",
    "longitude_geom",
    "latitude_geom",
]

PROVINCE_FIELDS = [
    "province_name",
    "mill_count",
    "operating_count",
    "closed_or_inactive_count",
    "unknown_status_count",
    "mills_with_capacity",
    "mills_missing_capacity",
    "total_capacity_tonnes_ffb_hour",
    "mean_capacity_tonnes_ffb_hour",
    "median_capacity_tonnes_ffb_hour",
]


def as_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def median(values):
    values = sorted(values)
    if not values:
        return ""
    midpoint = len(values) // 2
    if len(values) % 2:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / 2


def load_features():
    with RAW_GEOJSON.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def feature_to_row(feature):
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or [None, None]

    row = {field: properties.get(field, "") for field in MILL_FIELDS}
    row["longitude_geom"] = coordinates[0]
    row["latitude_geom"] = coordinates[1]
    return row


def status_counts(rows):
    operating = 0
    inactive = 0
    unknown = 0
    for row in rows:
        status = str(row.get("active", "")).strip().lower()
        if status == "operating":
            operating += 1
        elif status:
            inactive += 1
        else:
            unknown += 1
    return operating, inactive, unknown


def province_summary(rows):
    by_province = defaultdict(list)
    for row in rows:
        by_province[row["province_name"]].append(row)

    summary = []
    for province, province_rows in sorted(by_province.items()):
        capacities = [
            value
            for value in (as_number(row["capacity_tonnes_ffb_hour"]) for row in province_rows)
            if value is not None
        ]
        operating, inactive, unknown = status_counts(province_rows)
        total_capacity = sum(capacities)
        summary.append(
            {
                "province_name": province,
                "mill_count": len(province_rows),
                "operating_count": operating,
                "closed_or_inactive_count": inactive,
                "unknown_status_count": unknown,
                "mills_with_capacity": len(capacities),
                "mills_missing_capacity": len(province_rows) - len(capacities),
                "total_capacity_tonnes_ffb_hour": round(total_capacity, 2),
                "mean_capacity_tonnes_ffb_hour": round(total_capacity / len(capacities), 2)
                if capacities
                else "",
                "median_capacity_tonnes_ffb_hour": round(median(capacities), 2)
                if capacities
                else "",
            }
        )
    return summary


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = [feature_to_row(feature) for feature in load_features()]
    write_csv(OUT_DIR / "trase_indonesia_palm_oil_mills.csv", MILL_FIELDS, rows)
    write_csv(
        OUT_DIR / "trase_mill_capacity_by_province.csv",
        PROVINCE_FIELDS,
        province_summary(rows),
    )
    print(f"Wrote {OUT_DIR / 'trase_indonesia_palm_oil_mills.csv'}")
    print(f"Wrote {OUT_DIR / 'trase_mill_capacity_by_province.csv'}")


if __name__ == "__main__":
    main()
