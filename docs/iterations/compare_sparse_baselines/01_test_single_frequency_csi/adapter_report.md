# Native 24-pair CSI adapter

The circle table check stopped on 19 November 2026 at 03:09 UTC, before
the reader returned a field. No pair round trip, numerical field error or
inverse result was available from this attempt.

The 24-angle table reached upstream `ReadFreData.m`. With one receiver
per source, its reshaped index array is a row vector. MATLAB preserves
that orientation in `unique`, producing a 1-by-24 receiver coordinate
array. The tiled subtraction on line 384 expects a 24-by-1 column.

The operator builder reached the expected 166-by-166 grid. The sealed
input hashes and the pinned `CSI.m` bytes matched before launch. The
calculation stopped before it tested the source amplitude, phase or mask.
The coordinator received the discrepancy and all fits stayed on hold.

[Failed MATLAB log](../../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__clean/attempt_01/matlab.log)
· [Check record](../../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__clean/attempt_01/check.json)

At 03:11 UTC the owned TM configuration passed the new 48-reading
equivalence check. The receiver mask, both operators, incident field,
back-propagated currents and grid axes matched upstream exactly. The
starting susceptibility differed by 1.79e-17 in relative norm.

[Two-receiver equivalence record](../../../../results/csi/native_tg002/2026-11-19/checks/equivalence_upstream/check.json)
· [Upstream shape note](../../../../external/patches/cc-csi/native_single_receiver.md)
