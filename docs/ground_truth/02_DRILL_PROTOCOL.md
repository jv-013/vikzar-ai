# Drill Protocol

Every drill segment must have a stable `drill_id` and `drill_protocol_version`.
The version defines the movement, prescribed repetitions, work/rest schedule,
surface, intensity instruction, and required operator event markers.

The initial controlled catalogue should cover standing baseline, jogging,
acceleration/deceleration, planned cutting, landing, and repeated sprint work.
Protocol changes create a new version rather than reusing a previous label.

Operator notes and deviations are stored as `DrillEvent` records. They are
context, not model-derived labels.
