---
type: Synthetic Dataset
title: Compact two-shift regression example
description: Two fabricated shifts retained for simple demos and regression tests; use the five-day shift register for general production questions.
tags: [synthetic, manufacturing, production-line, compact-example, regression-test]
status: stable
provenance: Fully fabricated example data; no real facility, worker, machine, or production records are represented.
time_zone: UTC
---

# Overview

This small, deterministic dataset represents two shifts on a fictional packaging line. Every value is invented for software examples, tests, and demonstrations. It must not be used for operational decisions, safety decisions, forecasting, or claims about actual manufacturing performance.

For general or multi-shift production questions, use the five-day [shift production register](shift-production-register.md) and [dataset overview](production-data-overview.md) instead.

# Schema

- `shift_id` (string): synthetic identifier for the observation window.
- `start_utc` (datetime): inclusive start of the shift in UTC.
- `duration_minutes` (integer): planned production duration in minutes.
- `units_produced` (integer): total units completed during the shift.
- `good_units` (integer): units meeting the fictional quality check.
- `downtime_minutes` (integer): accumulated unplanned downtime; excluded from planned duration.
- `planned_units_per_minute` (number): fictional ideal line rate used to calculate theoretical output.

# Examples

| shift_id | start_utc | duration_minutes | units_produced | good_units | downtime_minutes | planned_units_per_minute |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| SYN-LINE-A-2025-02-03-D | 2025-02-03T06:00:00Z | 480 | 7,920 | 7,801 | 24 | 18.0 |
| SYN-LINE-A-2025-02-03-N | 2025-02-03T14:00:00Z | 480 | 7,488 | 7,376 | 41 | 18.0 |

The figures are internally bounded for demonstration purposes: good units do not exceed produced units, and downtime does not exceed shift duration. They are not statistically sampled from a real production process.

```json
{
  "shift_id": "SYN-LINE-A-2025-02-03-D",
  "start_utc": "2025-02-03T06:00:00Z",
  "duration_minutes": 480,
  "units_produced": 7920,
  "good_units": 7801,
  "downtime_minutes": 24,
  "planned_units_per_minute": 18.0
}
```

# Safety and use

- The `SYN-` prefix and `provenance` metadata identify this as fictional data.
- Do not combine it with live plant records as if it were measured data.
- Do not infer real-world equipment capability, worker performance, or quality rates from these rows.

# Citations

No external source: all records and identifiers in this dataset were fabricated for this example.
