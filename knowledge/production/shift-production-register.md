---
type: Synthetic Production Register
title: Line A shift production register
description: Ten fictional day and night shift records for five sample dates, including output, quality counts, and downtime.
tags: [synthetic, manufacturing, production, shift, register]
status: stable
provenance: Fabricated records; no real facility, worker, machine, or production records are represented.
time_zone: UTC
---

# Register

See [dataset overview and metric definitions](production-data-overview.md) before interpreting these values. All records describe the fictional `SYN-LINE-A` and are not suitable for operational decisions.

| shift_id | start_utc | duration_minutes | units_produced | good_units | rejected_units | downtime_minutes | ideal_units_per_minute |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SYN-LINE-A-2025-02-03-D | 2025-02-03T06:00:00Z | 480 | 8,040 | 7,920 | 120 | 18 | 18 |
| SYN-LINE-A-2025-02-03-N | 2025-02-03T14:00:00Z | 480 | 7,800 | 7,662 | 138 | 32 | 18 |
| SYN-LINE-A-2025-02-04-D | 2025-02-04T06:00:00Z | 480 | 8,280 | 8,142 | 138 | 12 | 18 |
| SYN-LINE-A-2025-02-04-N | 2025-02-04T14:00:00Z | 480 | 7,920 | 7,781 | 139 | 25 | 18 |
| SYN-LINE-A-2025-02-05-D | 2025-02-05T06:00:00Z | 480 | 8,100 | 7,942 | 158 | 20 | 18 |
| SYN-LINE-A-2025-02-05-N | 2025-02-05T14:00:00Z | 480 | 7,560 | 7,436 | 124 | 46 | 18 |
| SYN-LINE-A-2025-02-06-D | 2025-02-06T06:00:00Z | 480 | 8,400 | 8,255 | 145 | 15 | 18 |
| SYN-LINE-A-2025-02-06-N | 2025-02-06T14:00:00Z | 480 | 7,740 | 7,594 | 146 | 38 | 18 |
| SYN-LINE-A-2025-02-07-D | 2025-02-07T06:00:00Z | 480 | 8,160 | 8,011 | 149 | 22 | 18 |
| SYN-LINE-A-2025-02-07-N | 2025-02-07T14:00:00Z | 480 | 7,860 | 7,713 | 147 | 29 | 18 |

# Daily totals

| date_utc | units_produced | good_units | rejected_units | downtime_minutes |
| --- | ---: | ---: | ---: | ---: |
| 2025-02-03 | 15,840 | 15,582 | 258 | 50 |
| 2025-02-04 | 16,200 | 15,923 | 277 | 37 |
| 2025-02-05 | 15,660 | 15,378 | 282 | 66 |
| 2025-02-06 | 16,140 | 15,849 | 291 | 53 |
| 2025-02-07 | 16,020 | 15,724 | 296 | 51 |
| **Total** | **79,860** | **78,456** | **1,404** | **257** |

For every shift, good plus rejected units equal total produced units. Daily totals are the sum of the day and night records and reconcile to the [quality](quality-defect-rollup.md) and [downtime](downtime-reason-rollup.md) rollups.

# Field notes

- `shift_id` is a synthetic identifier; `D` and `N` label day and night sample shifts.
- `start_utc` is the shift start in UTC. The `duration_minutes` field is scheduled time, not run time.
- `downtime_minutes` is a rolled-up unplanned amount. Scheduled run time for the illustrative formulas is duration minus downtime.
- `ideal_units_per_minute` is a constant invented for this example. See the [overview](production-data-overview.md) for metric formulas and limitations.
