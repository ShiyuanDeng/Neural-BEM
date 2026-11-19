# One receiver per source in the TM reader

On the native TG-002 ring, `ReadFreData.m` reshapes 24 receiver angles
to one row. MATLAB's `unique` preserves the orientation of that row.
The TM receiver kernel on line 384 expects a column and the tiled
distance subtraction fails before the reader returns the data.

The owned [TM configuration](../../../experiments/baselines/csi/native_tg002/native_ring_tm.m)
sets the unique receiver angles to a column. It uses the pinned FDFD
builder and the native full-receiver back-propagation equations. The
[shape-error log](../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__clean/attempt_01/matlab.log)
records the upstream failure. No external checkout file was edited.
