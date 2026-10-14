---
type: Synthetic Dataset Overview
title: Production dataset overview and metrics
description: Scope, interpretation, and calculation rules for the fictional five-day Line A production dataset.
tags: [synthetic, manufacturing, production, metrics]
status: stable
provenance: Fully fabricated for examples and tests; no real facility, worker, machine, or production records are represented.
time_zone: UTC
---

# Scope

This dataset describes a fictional packaging line, `SYN-LINE-A`, over five consecutive sample dates, 2025-02-03 through 2025-02-07. Each date has a day and night shift. All records and identifiers are invented. They are not plant telemetry and must not be used for operational, staffing, maintenance, quality-release, forecasting, or safety decisions.

The [shift production register](shift-production-register.md) is the source of the sample's shift counts. The [quality defect rollup](quality-defect-rollup.md) groups rejected units, and the [downtime reason rollup](downtime-reason-rollup.md) groups downtime minutes. Both daily rollups reconcile to the two shifts on the same date.

# Dataset conventions

- Shift start times are UTC. Each record represents a scheduled 480-minute shift.
- The example ideal rate is 18 units per running minute; this is an invented constant, not a machine specification.
- `units_produced` counts completed units before the fictional quality inspection.
- `good_units` and `rejected_units` partition `units_produced`; therefore `units_produced = good_units + rejected_units`.
- `downtime_minutes` is unplanned downtime within the scheduled shift. The register records a rolled-up amount, not event timestamps.
- Daily quality and downtime tables are categorical aggregates, not independent measurements or source-system extracts.

# Metric definitions

These formulas demonstrate common production reporting conventions only. They do not establish a site's official KPI definitions.

- **Reject rate** = rejected units / total produced units.
- **Availability** = (scheduled minutes - downtime minutes) / scheduled minutes.
- **Performance** = total produced units / ((scheduled minutes - downtime minutes) × ideal units per minute).
- **Quality** = good units / total produced units.
- **Illustrative OEE** = Availability × Performance × Quality, equivalently good units / (scheduled minutes × ideal units per minute) for this dataset's definitions.

Do not compare these illustrative values with a real facility's KPIs unless its approved definitions, time exclusions, and data lineage have been independently established.

# Reconciliation

Across the ten sample shifts, the register totals 79,860 units produced, 78,456 good units, 1,404 rejected units, and 257 downtime minutes. The daily quality categories sum to 1,404 rejected units, and the daily downtime categories sum to 257 minutes. These totals are arithmetic checks on fabricated records, not verification of real production.
