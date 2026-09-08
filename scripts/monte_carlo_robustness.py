import csv
import math
from pathlib import Path

import numpy as np


BASE = Path(__file__).resolve().parents[1]
RESULTS_CSV = BASE / "processed" / "province_pome_biocng_screening_results.csv"
OUT_DIR = BASE / "processed"

N_ITERATIONS = 20000
RANDOM_SEED = 20260908

PARAMETER_RANGES = {
    "operating_hours_per_year": (5000.0, 6000.0, 7000.0),
    "pome_m3_per_tonne_ffb": (0.60, 0.70, 0.80),
    "cod_kg_per_m3": (45.0, 55.0, 62.0),
    "cod_removed_fraction": (0.70, 0.80, 0.90),
    "methane_yield_m3_per_kg_cod": (0.25, 0.30, 0.35),
    "upgrading_recovery_fraction": (0.90, 0.95, 0.98),
}


def read_results():
    with RESULTS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def triangular(rng, name, size):
    low, mode, high = PARAMETER_RANGES[name]
    return rng.triangular(low, mode, high, size=size)


def rankdata(values):
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        ranks[order[i : j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def clean_pair(x, y):
    pairs = []
    for a, b in zip(x, y):
        try:
            af = float(a)
            bf = float(b)
        except (TypeError, ValueError):
            continue
        if math.isfinite(af) and math.isfinite(bf):
            pairs.append((af, bf))
    return pairs


def spearman_rho(x, y):
    rx = rankdata(np.asarray(x, dtype=float))
    ry = rankdata(np.asarray(y, dtype=float))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def spearman_pvalue(rho, n):
    if not math.isfinite(rho) or n < 4 or abs(rho) >= 1:
        return ""
    t_stat = rho * math.sqrt((n - 2) / (1 - rho * rho))
    try:
        from scipy import stats

        return float(2 * stats.t.sf(abs(t_stat), df=n - 2))
    except Exception:
        # Normal approximation fallback for environments without scipy.
        return float(math.erfc(abs(t_stat) / math.sqrt(2)))


def main():
    rows = read_results()
    provinces = [row["province_name"] for row in rows]
    capacities = np.array([float(row["total_capacity_tonnes_ffb_hour"]) for row in rows])
    base_biomethane = np.array([float(row["base_biomethane_million_nm3"]) for row in rows])
    rng = np.random.default_rng(RANDOM_SEED)

    pome = triangular(rng, "pome_m3_per_tonne_ffb", N_ITERATIONS)
    cod = triangular(rng, "cod_kg_per_m3", N_ITERATIONS)
    removal = triangular(rng, "cod_removed_fraction", N_ITERATIONS)
    yield_factor = triangular(rng, "methane_yield_m3_per_kg_cod", N_ITERATIONS)
    recovery = triangular(rng, "upgrading_recovery_fraction", N_ITERATIONS)

    # Province-specific operating hours test whether the priority ranking survives
    # plausible utilization differences across provinces.
    hours = triangular(
        rng,
        "operating_hours_per_year",
        (N_ITERATIONS, len(provinces)),
    )

    common_conversion = (pome * cod * removal * yield_factor * recovery)[:, None]
    biomethane = capacities[None, :] * hours * common_conversion / 1_000_000
    ranks = np.argsort(np.argsort(-biomethane, axis=1), axis=1) + 1

    summary_rows = []
    for i, province in enumerate(provinces):
        values = biomethane[:, i]
        province_ranks = ranks[:, i]
        summary_rows.append(
            {
                "province_name": province,
                "deterministic_rank": rows[i]["biomethane_rank"],
                "base_biomethane_million_nm3": f"{base_biomethane[i]:.3f}",
                "mc_mean_biomethane_million_nm3": f"{np.mean(values):.3f}",
                "mc_p05_biomethane_million_nm3": f"{np.percentile(values, 5):.3f}",
                "mc_p50_biomethane_million_nm3": f"{np.percentile(values, 50):.3f}",
                "mc_p95_biomethane_million_nm3": f"{np.percentile(values, 95):.3f}",
                "median_rank": f"{np.percentile(province_ranks, 50):.0f}",
                "rank_p05": f"{np.percentile(province_ranks, 5):.0f}",
                "rank_p95": f"{np.percentile(province_ranks, 95):.0f}",
                "top1_probability": f"{np.mean(province_ranks <= 1):.3f}",
                "top3_probability": f"{np.mean(province_ranks <= 3):.3f}",
                "top5_probability": f"{np.mean(province_ranks <= 5):.3f}",
            }
        )

    fields = list(summary_rows[0].keys())
    summary_path = OUT_DIR / "pome_biocng_monte_carlo_province_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    metrics = [
        ("installed capacity", [float(r["total_capacity_tonnes_ffb_hour"]) for r in rows]),
        ("base biomethane potential", base_biomethane),
        ("mean neighbors within 25 km", [float(r["mean_neighbors_within_25km"]) for r in rows]),
        (
            "share of mills with at least three neighbors within 25 km",
            [float(r["share_mills_with_3plus_neighbors_25km"]) for r in rows],
        ),
        ("median nearest-neighbor distance", [r["median_nearest_neighbor_km"] for r in rows]),
    ]
    correlation_tests = [
        ("base biomethane potential", "mean neighbors within 25 km"),
        ("base biomethane potential", "share of mills with at least three neighbors within 25 km"),
        ("base biomethane potential", "median nearest-neighbor distance"),
        ("installed capacity", "mean neighbors within 25 km"),
        ("installed capacity", "share of mills with at least three neighbors within 25 km"),
    ]
    metric_values = dict(metrics)
    corr_rows = []
    for x_name, y_name in correlation_tests:
        pairs = clean_pair(metric_values[x_name], metric_values[y_name])
        x_values = [p[0] for p in pairs]
        y_values = [p[1] for p in pairs]
        rho = spearman_rho(x_values, y_values)
        pvalue = spearman_pvalue(rho, len(pairs))
        corr_rows.append(
            {
                "x_variable": x_name,
                "y_variable": y_name,
                "spearman_rho": f"{rho:.3f}",
                "p_value": "" if pvalue == "" else f"{pvalue:.4f}",
                "n_provinces": len(pairs),
            }
        )

    corr_path = OUT_DIR / "pome_biocng_correlation_tests.csv"
    with corr_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(corr_rows[0].keys()))
        writer.writeheader()
        writer.writerows(corr_rows)

    assumptions_path = OUT_DIR / "pome_biocng_monte_carlo_assumptions.csv"
    with assumptions_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["parameter", "low", "mode", "high", "distribution", "sampling"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for name, (low, mode, high) in PARAMETER_RANGES.items():
            writer.writerow(
                {
                    "parameter": name,
                    "low": low,
                    "mode": mode,
                    "high": high,
                    "distribution": "triangular",
                    "sampling": "province-specific"
                    if name == "operating_hours_per_year"
                    else "common across provinces",
                }
            )

    print(f"Wrote {summary_path}")
    print(f"Wrote {corr_path}")
    print(f"Wrote {assumptions_path}")
    print("Leading provinces by Monte Carlo median biomethane:")
    for row in summary_rows[:10]:
        print(row)


if __name__ == "__main__":
    main()
