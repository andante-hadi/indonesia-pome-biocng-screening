# Indonesia POME-to-Bio-CNG Screening

This repository contains the public reproducibility package for a remote-data screening study of palm oil mill effluent (POME)-to-bio-CNG readiness in Indonesia.

Working manuscript title:

> Open-data Monte Carlo screening of palm oil mill effluent bio-CNG for renewable energy system planning in Indonesia

The workflow estimates province-level POME generation, methane recovery, biomethane potential, diesel-equivalent energy, mill-clustering indicators, Monte Carlo uncertainty intervals, rank-stability metrics, and correlation tests from open palm oil mill data and literature-based screening assumptions. It is intended as an open-data prioritization study, not a plant-level investment feasibility assessment.

## Repository Contents

| Path | Contents |
|---|---|
| `raw/` | Open raw inputs used by the reproducibility workflow. |
| `processed/` | Prepared mill tables, province summaries, scenario assumptions, and screening results. |
| `scripts/prepare_trase_mill_data.py` | Converts the Trase GeoJSON mill dataset into tabular CSV inputs. |
| `scripts/analyze_indonesia_pome_screening.py` | Calculates province-level POME-to-bio-CNG screening results. |
| `scripts/monte_carlo_robustness.py` | Calculates Monte Carlo uncertainty, rank stability, and correlation tests. |
| `scripts/make_manuscript_figures.R` | Generates manuscript-ready SVG and PNG figures. |
| `final_figures/` | Current final manuscript figures. |
| `source_register.csv` | Source URLs, local file references, and access notes. |

## Data Sources

The main mill dataset is the Trase Indonesia palm oil mills GeoJSON. Country boundaries are from Natural Earth. Source URLs and access notes are recorded in `source_register.csv`.

Third-party data remain subject to their original source terms. The license in this repository applies to original code and original derived materials only; it does not relicense Trase, Natural Earth, or any other third-party source.

## Software Requirements

Python:

- Python 3.10 or later
- standard library plus `numpy`; `scipy` is optional and used only for exact Spearman p-values when available

R:

- R 4.3 or later recommended
- `dplyr`
- `ggplot2`
- `jsonlite`
- `ragg`
- `readr`
- `scales`
- `svglite`
- `tidyr`

Install R packages with:

```r
install.packages(c("dplyr", "ggplot2", "jsonlite", "ragg", "readr", "scales", "svglite", "tidyr"))
```

## Reproduce Results

From the repository root:

```bash
python3 scripts/prepare_trase_mill_data.py
python3 scripts/analyze_indonesia_pome_screening.py
python3 scripts/monte_carlo_robustness.py
Rscript scripts/make_manuscript_figures.R
```

Expected outputs:

- `processed/trase_indonesia_palm_oil_mills.csv`
- `processed/trase_mill_capacity_by_province.csv`
- `processed/province_pome_biocng_screening_results.csv`
- `processed/pome_biocng_scenario_assumptions.csv`
- `processed/pome_biocng_monte_carlo_assumptions.csv`
- `processed/pome_biocng_monte_carlo_province_summary.csv`
- `processed/pome_biocng_correlation_tests.csv`
- `figures/*.svg`
- `figures/*.png`
- `final_figures/*.svg`
- `final_figures/*.png`

## Modeling Boundary

The screening model converts installed fresh fruit bunch (FFB) processing capacity to annual FFB throughput, POME volume, COD removed, methane generation, upgraded biomethane, energy content, and diesel-equivalent volume using low/base/high assumptions. The Monte Carlo robustness layer converts these low/base/high values into triangular distributions and reports uncertainty intervals and rank-stability metrics.

The model does not include road routing, gas infrastructure proximity, site-level POME measurements, technology vendor quotes, project finance, offtake contracts, or licensed life-cycle inventory data. Those belong in a later LCA/TEA or plant-level feasibility study.

## Suggested Citation

If using this repository before formal article publication, cite the archived repository release and the source datasets listed in `source_register.csv`.
