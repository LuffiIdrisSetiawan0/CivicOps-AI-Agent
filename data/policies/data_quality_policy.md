# Data Quality Policy

Analytical agents must reject destructive SQL and avoid exposing personally identifiable information. The demo dataset is synthetic and contains no real citizen records.

When a question cannot be answered from available SQL tables, documents, complaint logs, or mock APIs, the assistant should say what is missing and suggest the closest available metric.

Quality checks should verify that answers include evidence, do not overstate causality, and distinguish metric values from policy recommendations.
