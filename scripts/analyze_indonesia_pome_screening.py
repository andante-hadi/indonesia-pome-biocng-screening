import csv
import math
from collections import defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
MILL_CSV = BASE / "processed" / "trase_indonesia_palm_oil_mills.csv"
OUT_DIR = BASE / "processed"


SCENARIOS = {
    "low": {
        "operating_hours_per_year": 5000,
        "pome_m3_per_tonne_ffb": 0.60,
        "cod_kg_per_m3": 45.0,
        "cod_removed_fraction": 0.70,
        "methane_yield_m3_per_kg_cod": 0.25,
        "upgrading_recovery_fraction": 0.90,
    },
    "base": {
        "operating_hours_per_year": 6000,
        "pome_m3_per_tonne_ffb": 0.70,
        "cod_kg_per_m3": 55.0,
        "cod_removed_fraction": 0.80,
        "methane_yield_m3_per_kg_cod": 0.30,
        "upgrading_recovery_fraction": 0.95,
    },
    "high": {
        "operating_hours_per_year": 7000,
        "pome_m3_per_tonne_ffb": 0.80,
        "cod_kg_per_m3": 62.0,
        "cod_removed_fraction": 0.90,
        "methane_yield_m3_per_kg_cod": 0.35,
        "upgrading_recovery_fraction": 0.98,
    },
}

METHANE_LHV_MJ_PER_NM3 = 35.8
DIESEL_LHV_MJ_PER_L = 38.6
NEIGHBOR_RADII_KM = (10.0, 25.0, 50.0)


def to_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except ValueError:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_mills():
    rows = []
    with MILL_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cap = to_float(row.get("capacity_tonnes_ffb_hour"))
            lat = to_float(row.get("latitude_geom") or row.get("latitude"))
            lon = to_float(row.get("longitude_geom") or row.get("longitude"))
            if cap is None or lat is None or lon is None:
                continue
            row["capacity_tonnes_ffb_hour_float"] = cap
            row["lat_float"] = lat
            row["lon_float"] = lon
            rows.append(row)
    return rows


def add_cluster_metrics(mills):
    by_province = defaultdict(list)
    for mill in mills:
        by_province[mill["province_name"]].append(mill)

    cluster_by_province = {}
    for province, rows in by_province.items():
        neighbor_counts = {radius: [] for radius in NEIGHBOR_RADII_KM}
        nearest_distances = []
        for i, a in enumerate(rows):
            distances = []
            for j, b in enumerate(rows):
                if i == j:
                    continue
                d = haversine_km(a["lat_float"], a["lon_float"], b["lat_float"], b["lon_float"])
                distances.append(d)
            for radius in NEIGHBOR_RADII_KM:
                neighbor_counts[radius].append(sum(1 for d in distances if d <= radius))
            if distances:
                nearest_distances.append(min(distances))
        metrics = {"median_nearest_neighbor_km": median(nearest_distances)}
        for radius in NEIGHBOR_RADII_KM:
            counts = neighbor_counts[radius]
            radius_label = int(radius)
            metrics[f"mean_neighbors_within_{radius_label}km"] = (
                sum(counts) / len(counts) if counts else 0
            )
            metrics[f"share_mills_with_3plus_neighbors_{radius_label}km"] = (
                sum(1 for x in counts if x >= 3) / len(counts) if counts else 0
            )
        cluster_by_province[province] = metrics
    return cluster_by_province


def median(values):
    values = sorted(values)
    if not values:
        return ""
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def scenario_outputs(capacity_tph, scenario):
    annual_ffb = capacity_tph * scenario["operating_hours_per_year"]
    pome = annual_ffb * scenario["pome_m3_per_tonne_ffb"]
    cod_removed = pome * scenario["cod_kg_per_m3"] * scenario["cod_removed_fraction"]
    methane_raw = cod_removed * scenario["methane_yield_m3_per_kg_cod"]
    biomethane = methane_raw * scenario["upgrading_recovery_fraction"]
    energy_tj = biomethane * METHANE_LHV_MJ_PER_NM3 / 1_000_000
    diesel_equiv_ml = biomethane * METHANE_LHV_MJ_PER_NM3 / DIESEL_LHV_MJ_PER_L / 1_000_000
    return {
        "annual_ffb_tonnes": annual_ffb,
        "pome_m3": pome,
        "raw_methane_nm3": methane_raw,
        "recoverable_biomethane_nm3": biomethane,
        "recoverable_energy_tj": energy_tj,
        "diesel_equivalent_million_liters": diesel_equiv_ml,
    }


def main():
    mills = load_mills()
    cluster_metrics = add_cluster_metrics(mills)
    by_province = defaultdict(list)
    for mill in mills:
        by_province[mill["province_name"]].append(mill)

    rows = []
    for province, province_mills in sorted(by_province.items()):
        capacity = sum(m["capacity_tonnes_ffb_hour_float"] for m in province_mills)
        base = scenario_outputs(capacity, SCENARIOS["base"])
        low = scenario_outputs(capacity, SCENARIOS["low"])
        high = scenario_outputs(capacity, SCENARIOS["high"])
        cm = cluster_metrics[province]
        rows.append({
            "province_name": province,
            "mills_with_capacity": len(province_mills),
            "total_capacity_tonnes_ffb_hour": round(capacity, 2),
            "base_annual_ffb_million_tonnes": round(base["annual_ffb_tonnes"] / 1_000_000, 3),
            "base_pome_million_m3": round(base["pome_m3"] / 1_000_000, 3),
            "low_biomethane_million_nm3": round(low["recoverable_biomethane_nm3"] / 1_000_000, 3),
            "base_biomethane_million_nm3": round(base["recoverable_biomethane_nm3"] / 1_000_000, 3),
            "high_biomethane_million_nm3": round(high["recoverable_biomethane_nm3"] / 1_000_000, 3),
            "base_energy_tj": round(base["recoverable_energy_tj"], 1),
            "base_diesel_equivalent_million_liters": round(base["diesel_equivalent_million_liters"], 2),
            "mean_neighbors_within_10km": round(cm["mean_neighbors_within_10km"], 2),
            "share_mills_with_3plus_neighbors_10km": round(cm["share_mills_with_3plus_neighbors_10km"], 3),
            "mean_neighbors_within_25km": round(cm["mean_neighbors_within_25km"], 2),
            "share_mills_with_3plus_neighbors_25km": round(cm["share_mills_with_3plus_neighbors_25km"], 3),
            "mean_neighbors_within_50km": round(cm["mean_neighbors_within_50km"], 2),
            "share_mills_with_3plus_neighbors_50km": round(cm["share_mills_with_3plus_neighbors_50km"], 3),
            "median_nearest_neighbor_km": round(cm["median_nearest_neighbor_km"], 2) if cm["median_nearest_neighbor_km"] != "" else "",
        })

    rows.sort(key=lambda r: (r["base_biomethane_million_nm3"], r["share_mills_with_3plus_neighbors_25km"]), reverse=True)
    for rank, row in enumerate(rows, 1):
        row["biomethane_rank"] = rank

    fields = [
        "biomethane_rank",
        "province_name",
        "mills_with_capacity",
        "total_capacity_tonnes_ffb_hour",
        "base_annual_ffb_million_tonnes",
        "base_pome_million_m3",
        "low_biomethane_million_nm3",
        "base_biomethane_million_nm3",
        "high_biomethane_million_nm3",
        "base_energy_tj",
        "base_diesel_equivalent_million_liters",
        "mean_neighbors_within_10km",
        "share_mills_with_3plus_neighbors_10km",
        "mean_neighbors_within_25km",
        "share_mills_with_3plus_neighbors_25km",
        "mean_neighbors_within_50km",
        "share_mills_with_3plus_neighbors_50km",
        "median_nearest_neighbor_km",
    ]
    out = OUT_DIR / "province_pome_biocng_screening_results.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    assumptions = OUT_DIR / "pome_biocng_scenario_assumptions.csv"
    with assumptions.open("w", newline="", encoding="utf-8") as f:
        fields = ["scenario", *next(iter(SCENARIOS.values())).keys(), "methane_lhv_mj_per_nm3", "diesel_lhv_mj_per_l"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for name, values in SCENARIOS.items():
            writer.writerow({
                "scenario": name,
                **values,
                "methane_lhv_mj_per_nm3": METHANE_LHV_MJ_PER_NM3,
                "diesel_lhv_mj_per_l": DIESEL_LHV_MJ_PER_L,
            })

    print(f"Wrote {out}")
    print(f"Wrote {assumptions}")
    for row in rows[:10]:
        print(row)


if __name__ == "__main__":
    main()
