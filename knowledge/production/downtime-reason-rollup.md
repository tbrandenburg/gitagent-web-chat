---
type: Synthetic Downtime Rollup
title: Line A daily downtime reason rollup
description: Fictional daily unplanned downtime minutes by cause, reconciling to the shift production register.
tags: [synthetic, manufacturing, downtime, maintenance]
status: stable
provenance: Fabricated aggregate minutes; no real equipment, maintenance, or event records are represented.
time_zone: UTC
---

# Daily unplanned downtime minutes

See the [dataset overview](production-data-overview.md) for scope and the [shift register](shift-production-register.md) for daily downtime totals. Cause labels and minutes are invented and do not describe real equipment or maintenance needs.

| date_utc | material_feed_interruption | sensor_or_controls_stop | mechanical_jam | downtime_minutes |
| --- | ---: | ---: | ---: | ---: |
| 2025-02-03 | 16 | 12 | 22 | 50 |
| 2025-02-04 | 8 | 11 | 18 | 37 |
| 2025-02-05 | 17 | 24 | 25 | 66 |
| 2025-02-06 | 13 | 21 | 19 | 53 |
| 2025-02-07 | 17 | 14 | 20 | 51 |
| **Total** | **71** | **82** | **104** | **257** |

Each row's categories sum to `downtime_minutes`. Daily minutes equal the day and night shift values in the register. This is a daily aggregate, not an event log: start/end times, repair actions, affected equipment, and verified root causes are not represented.
