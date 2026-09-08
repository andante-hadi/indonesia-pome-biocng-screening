#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(jsonlite)
  library(readr)
  library(scales)
  library(tidyr)
})

script_arg <- grep("^--file=", commandArgs(), value = TRUE)
script_path <- normalizePath(sub("^--file=", "", script_arg[[1]]))
base_dir <- dirname(dirname(script_path))
results_path <- file.path(base_dir, "processed", "province_pome_biocng_screening_results.csv")
mc_path <- file.path(base_dir, "processed", "pome_biocng_monte_carlo_province_summary.csv")
mills_path <- file.path(base_dir, "processed", "trase_indonesia_palm_oil_mills.csv")
boundary_path <- file.path(base_dir, "raw", "natural_earth_ne_50m_admin_0_countries.geojson")
figure_dir <- file.path(base_dir, "figures")
final_dir <- file.path(base_dir, "final_figures")

dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(final_dir, recursive = TRUE, showWarnings = FALSE)

palette <- c(
  ink = "#000000",
  muted = "#000000",
  grid = "#D9DEE5",
  green = "#187A65",
  teal = "#3B9C93",
  blue = "#3977B9",
  pale_blue = "#CFE1F2",
  amber = "#C98324",
  red = "#B64D3D",
  land = "#EDF1EC",
  coast = "#727C75"
)

theme_manuscript <- function(base_size = 13) {
  theme_minimal(base_family = "sans", base_size = base_size) +
    theme(
      plot.title = element_blank(),
      plot.subtitle = element_blank(),
      plot.caption = element_blank(),
      axis.title = element_text(color = palette[["ink"]], size = 12.5),
      axis.text = element_text(color = palette[["muted"]], size = 11.5),
      panel.grid.major = element_line(color = palette[["grid"]], linewidth = 0.35),
      panel.grid.minor = element_blank(),
      legend.title = element_text(color = palette[["ink"]], face = "bold", size = 11.5),
      legend.text = element_text(color = palette[["ink"]], size = 11),
      plot.margin = margin(12, 14, 10, 12)
    )
}

nice_province <- function(x) {
  replacements <- c(
    "RIAU" = "Riau",
    "KALIMANTAN TENGAH" = "Central Kalimantan",
    "SUMATERA UTARA" = "North Sumatra",
    "KALIMANTAN BARAT" = "West Kalimantan",
    "KALIMANTAN TIMUR" = "East Kalimantan",
    "SUMATERA SELATAN" = "South Sumatra",
    "JAMBI" = "Jambi",
    "SUMATERA BARAT" = "West Sumatra",
    "KALIMANTAN SELATAN" = "South Kalimantan",
    "ACEH" = "Aceh"
  )
  unname(ifelse(x %in% names(replacements), replacements[x], tools::toTitleCase(tolower(x))))
}

save_figure <- function(plot, stem, width, height) {
  svg_path <- file.path(figure_dir, paste0(stem, ".svg"))
  png_path <- file.path(figure_dir, paste0(stem, ".png"))
  svg_device <- if (requireNamespace("svglite", quietly = TRUE)) {
    svglite::svglite
  } else {
    grDevices::svg
  }

  ggsave(
    svg_path, plot = plot, width = width, height = height,
    units = "in", device = svg_device, bg = "white"
  )
  ggsave(
    png_path, plot = plot, width = width, height = height,
    units = "in", dpi = 300, device = ragg::agg_png, bg = "white"
  )

  file.copy(svg_path, file.path(final_dir, basename(svg_path)), overwrite = TRUE)
  file.copy(png_path, file.path(final_dir, basename(png_path)), overwrite = TRUE)
}

extract_indonesia_polygons <- function(path) {
  geo <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  ids <- vapply(
    geo$features,
    function(feature) feature$properties$ADM0_A3 %||% "",
    character(1)
  )
  feature <- geo$features[[which(ids == "IDN")[1]]]
  polygons <- feature$geometry$coordinates

  bind_rows(lapply(seq_along(polygons), function(polygon_id) {
    outer_ring <- polygons[[polygon_id]][[1]]
    coordinates <- do.call(rbind, lapply(outer_ring, unlist))
    tibble(
      longitude = as.numeric(coordinates[, 1]),
      latitude = as.numeric(coordinates[, 2]),
      polygon = polygon_id,
      vertex = seq_len(nrow(coordinates))
    )
  }))
}

`%||%` <- function(x, y) if (is.null(x)) y else x

results <- read_csv(results_path, show_col_types = FALSE) %>%
  arrange(biomethane_rank) %>%
  mutate(province = nice_province(province_name))

mc_results <- read_csv(mc_path, show_col_types = FALSE) %>%
  arrange(as.numeric(deterministic_rank)) %>%
  mutate(province = nice_province(province_name))

mills <- read_csv(mills_path, show_col_types = FALSE) %>%
  transmute(
    mill_name,
    province = nice_province(province_name),
    longitude = coalesce(longitude_geom, longitude),
    latitude = coalesce(latitude_geom, latitude),
    capacity = capacity_tonnes_ffb_hour
  ) %>%
  filter(
    is.finite(longitude), is.finite(latitude), is.finite(capacity),
    longitude >= 94, longitude <= 142.5,
    latitude >= -11.8, latitude <= 7.5
  ) %>%
  mutate(
    capacity_class = cut(
      capacity,
      breaks = c(-Inf, 30, 45, 60, 90, Inf),
      right = FALSE,
      labels = c("<30", "30-44", "45-59", "60-89", "90+")
    )
  )

indonesia <- extract_indonesia_polygons(boundary_path)

map_labels <- tribble(
  ~province, ~longitude, ~latitude,
  "North Sumatra", 98.6, 4.4,
  "Riau", 101.1, 1.7,
  "Jambi", 102.9, -0.5,
  "South Sumatra", 104.3, -4.8,
  "West Kalimantan", 109.0, 0.9,
  "Central Kalimantan", 113.1, -1.7,
  "East Kalimantan", 117.0, 1.4
)

capacity_colors <- c(
  "<30" = "#4F8FC9",
  "30-44" = "#2F7F8F",
  "45-59" = "#238568",
  "60-89" = palette[["amber"]],
  "90+" = palette[["red"]]
)

figure_1 <- ggplot() +
  geom_polygon(
    data = indonesia,
    aes(longitude, latitude, group = polygon),
    fill = palette[["land"]], color = palette[["coast"]], linewidth = 0.35
  ) +
  geom_point(
    data = arrange(mills, capacity),
    aes(longitude, latitude, size = capacity_class, color = capacity_class),
    alpha = 0.76, stroke = 0
  ) +
  geom_text(
    data = map_labels,
    aes(longitude, latitude, label = province),
    family = "sans", fontface = "bold", size = 4.0,
    color = palette[["ink"]], check_overlap = TRUE
  ) +
  scale_color_manual(values = capacity_colors, drop = FALSE) +
  scale_size_manual(values = c("<30" = 0.65, "30-44" = 0.9, "45-59" = 1.2, "60-89" = 1.55, "90+" = 1.95), drop = FALSE) +
  scale_x_continuous(
    breaks = seq(95, 140, 5),
    labels = function(x) paste0(x, "\u00b0E"),
    expand = c(0, 0)
  ) +
  scale_y_continuous(
    breaks = c(-10, -5, 0, 5),
    labels = function(x) ifelse(x == 0, "0\u00b0", paste0(abs(x), "\u00b0", ifelse(x < 0, "S", "N"))),
    expand = c(0, 0)
  ) +
  coord_quickmap(xlim = c(94, 142.5), ylim = c(-11.8, 7.5), clip = "on") +
  labs(
    color = "Installed capacity\n(t FFB/hour)",
    size = "Installed capacity\n(t FFB/hour)",
    x = NULL, y = NULL
  ) +
  guides(
    color = guide_legend(
      direction = "horizontal", title.position = "top",
      override.aes = list(size = c(3.0, 3.7, 4.4, 5.1, 5.8), alpha = 0.9)
    ),
    size = "none"
  ) +
  theme_manuscript(10) +
  theme(
    legend.position = "inside",
    legend.position.inside = c(0.80, 0.86),
    legend.background = element_rect(fill = alpha("white", 0.94), color = "#C7CED5"),
    legend.key.height = unit(0.18, "in"),
    legend.key.width = unit(0.38, "in"),
    panel.grid.major = element_line(color = "#E0E4E8", linewidth = 0.3),
    panel.border = element_rect(color = "#AAB2BA", fill = NA, linewidth = 0.4)
  )

top_12 <- results %>%
  slice_head(n = 12) %>%
  mutate(
    province = factor(province, levels = rev(province)),
    tier = case_when(
      biomethane_rank <= 3 ~ "Top three",
      biomethane_rank <= 7 ~ "Next four",
      TRUE ~ "Other leading provinces"
    ),
    tier = factor(
      tier,
      levels = c("Top three", "Next four", "Other leading provinces")
    )
  )

figure_2 <- ggplot(top_12, aes(base_biomethane_million_nm3, province, fill = tier)) +
  geom_col(width = 0.68) +
  geom_text(
    aes(label = number(base_biomethane_million_nm3, accuracy = 0.1)),
    hjust = -0.08, family = "sans", size = 4.0, color = palette[["ink"]]
  ) +
  scale_fill_manual(
    values = c(
      "Top three" = palette[["green"]],
      "Next four" = palette[["teal"]],
      "Other leading provinces" = palette[["blue"]]
    )
  ) +
  scale_x_continuous(
    limits = c(0, 710),
    breaks = seq(0, 700, 100),
    expand = expansion(mult = c(0, 0.01))
  ) +
  labs(
    x = expression("Recoverable biomethane potential, base scenario (million Nm"^3*"/year)"),
    y = NULL,
    fill = NULL
  ) +
  theme_manuscript() +
  theme(
    legend.position = "top",
    legend.justification = "right",
    panel.grid.major.y = element_blank()
  )

top_10_mc <- mc_results %>%
  slice_head(n = 10) %>%
  mutate(
    province = factor(province, levels = province),
    top5_label = paste0(round(top5_probability * 100), "%")
  )

figure_3 <- ggplot(top_10_mc, aes(province, mc_p50_biomethane_million_nm3)) +
  geom_linerange(
    aes(
      ymin = mc_p05_biomethane_million_nm3,
      ymax = mc_p95_biomethane_million_nm3
    ),
    linewidth = 1.25,
    color = palette[["blue"]]
  ) +
  geom_point(size = 3.0, color = palette[["green"]]) +
  geom_text(
    aes(
      y = mc_p95_biomethane_million_nm3 + 43,
      label = top5_label
    ),
    family = "sans",
    size = 3.7,
    color = palette[["ink"]]
  ) +
  scale_y_continuous(
    limits = c(0, 900),
    breaks = seq(0, 900, 100),
    expand = expansion(mult = c(0, 0.01))
  ) +
  labs(
    x = NULL,
    y = expression("Recoverable biomethane (million Nm"^3*"/year)")
  ) +
  theme_manuscript() +
  theme(
    axis.text.x = element_text(angle = 38, hjust = 1, vjust = 1),
    panel.grid.major.x = element_blank()
  )

leading_names <- results %>%
  slice_head(n = 10) %>%
  pull(province_name)

label_offsets <- tribble(
  ~province_name, ~dx, ~dy,
  "RIAU", 260, -0.045,
  "KALIMANTAN TENGAH", 260, 0.025,
  "SUMATERA UTARA", 260, 0.035,
  "KALIMANTAN BARAT", 250, 0.035,
  "KALIMANTAN TIMUR", 250, -0.045,
  "SUMATERA SELATAN", 250, 0.022,
  "JAMBI", 240, 0.030,
  "SUMATERA BARAT", 220, 0.040,
  "KALIMANTAN SELATAN", 220, 0.015,
  "ACEH", 220, -0.040
)

cluster_data <- results %>%
  mutate(leading = province_name %in% leading_names)

cluster_labels <- cluster_data %>%
  filter(leading) %>%
  left_join(label_offsets, by = "province_name") %>%
  mutate(
    label_x = total_capacity_tonnes_ffb_hour + coalesce(dx, 220),
    label_y = share_mills_with_3plus_neighbors_25km + coalesce(dy, 0.02)
  )

figure_4 <- ggplot(
  cluster_data,
  aes(
    total_capacity_tonnes_ffb_hour,
    share_mills_with_3plus_neighbors_25km
  )
) +
  geom_point(
    aes(
      size = base_biomethane_million_nm3,
      color = leading
    ),
    alpha = 0.82
  ) +
  geom_text(
    data = cluster_labels,
    aes(label_x, label_y, label = province),
    inherit.aes = FALSE, hjust = 0, family = "sans",
    size = 3.8, color = palette[["ink"]], check_overlap = FALSE
  ) +
  scale_color_manual(
    values = c("TRUE" = palette[["green"]], "FALSE" = palette[["blue"]]),
    guide = "none"
  ) +
  scale_size_continuous(
    range = c(2.2, 9.0),
    breaks = c(100, 300, 500),
    labels = number_format(accuracy = 1),
    guide = guide_legend(
      override.aes = list(color = "#2B2B2B", alpha = 0.92)
    )
  ) +
  scale_x_continuous(
    limits = c(0, 14000),
    breaks = seq(0, 14000, 2000),
    labels = comma
  ) +
  scale_y_continuous(
    limits = c(0, 1.02),
    breaks = seq(0, 1, 0.25),
    labels = number_format(accuracy = 0.01)
  ) +
  labs(
    x = "Installed FFB processing capacity (tonnes FFB/hour)",
    y = "Share of mills with at least 3 neighbors within 25 km",
    size = expression("Base biomethane potential"~(million~Nm^3*"/year"))
  ) +
  theme_manuscript() +
  theme(
    legend.position = "inside",
    legend.position.inside = c(0.83, 0.19),
    legend.background = element_rect(fill = alpha("white", 0.94), color = "#C7CED5")
  )

save_figure(figure_1, "figure_1_indonesia_palm_oil_mills_map", 12.5, 6.3)
save_figure(figure_2, "figure_2_province_biomethane_ranking", 10.8, 6.8)
save_figure(figure_3, "figure_3_potential_uncertainty", 10.8, 6.8)
save_figure(figure_4, "figure_4_capacity_clustering_matrix", 10.8, 7.2)

message("R-generated manuscript figures written to:")
message("  ", figure_dir)
message("  ", final_dir)
