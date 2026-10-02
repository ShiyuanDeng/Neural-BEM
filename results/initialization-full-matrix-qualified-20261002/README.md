# Superseded full-matrix diagnostic

This diagnostic matches the original physical constants but retains singular
directions below the measured matrix accuracy. Near the discrepancy boundary,
roundoff changed the set of eligible LSM probes between resolutions.

The [final comparison](../initialization-full-matrix-resolved-20261002/README.md)
uses an explicit 1e-12 relative singular-value floor and obtains identical
eligibility masks at both resolutions. These earlier arrays remain available
as evidence of why that qualification was needed.
