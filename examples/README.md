# Example API runs

Actual `QueryResponse` JSON captured from the deployed service (`POST /api/query` on 2026-07-02).

| File | Query | Chart type |
|------|-------|------------|
| [01_breakdown_by_phase.json](01_breakdown_by_phase.json) | How many recruiting diabetes trials are there by phase? | `pie` |
| [02_trial_list_table.json](02_trial_list_table.json) | List recruiting Parkinson disease trials with NCT IDs | `table` |
| [03_network_graph.json](03_network_graph.json) | Show a network graph of sponsors and conditions for recruiting diabetes trials | `network` |
| [04_time_series.json](04_time_series.json) | Show a time series of lung cancer trials started per year | `timeseries` |
| [05_single_count.json](05_single_count.json) | How many active not recruiting COVID-19 vaccine trials are there? | `bar` |

Reproduce locally:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many recruiting diabetes trials are there by phase?"}'
```

Counts and trial metadata reflect live ClinicalTrials.gov data at capture time and may change on subsequent runs.
