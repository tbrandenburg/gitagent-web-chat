---
type: Synthetic Quality Rollup
title: Line A daily quality defect rollup
description: Fictional daily rejected-unit counts by defect category, reconciling to the shift production register.
tags: [synthetic, manufacturing, quality, defects]
status: stable
provenance: Fabricated aggregate counts; no real inspection, product, or quality-release records are represented.
time_zone: UTC
---

# Daily rejected units

See the [dataset overview](production-data-overview.md) for scope and the [shift register](shift-production-register.md) for daily rejected-unit totals. Category labels and counts are invented for this example and must not be used for quality release or process control.

| date_utc | seal_defect | label_defect | weight_out_of_range | other | rejected_units |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025-02-03 | 92 | 71 | 54 | 41 | 258 |
| 2025-02-04 | 101 | 68 | 59 | 49 | 277 |
| 2025-02-05 | 96 | 83 | 57 | 46 | 282 |
| 2025-02-06 | 109 | 74 | 62 | 46 | 291 |
| 2025-02-07 | 104 | 88 | 61 | 43 | 296 |
| **Total** | **502** | **384** | **293** | **225** | **1,404** |

Each row's categories sum to `rejected_units`. The daily total equals rejected units in the shift register. The category rollup has no lot-level detail, inspection method, or timestamps.
