# Ground Truth Quality Control

The pipeline does not interpolate, zero-fill, or estimate EMG measurements.
It records one quality result for every evaluated feature-vector/group pair.

Rejected causes include missing or non-matched synchronization evidence,
alignment beyond the recorded tolerance, absent EMG, rejected ETL EMG quality,
missing EMG recording metadata, missing/unverified placement, and no enclosing
training phase. Questionable ETL EMG values remain traceable but are not used
as default supervised labels.

Only accepted drill windows are emitted as `AlignedTrainingWindow` records and
become direct measured EMG labels.
