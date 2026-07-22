# Sensor Placement Protocol

Record one placement record for every Smart Pod and EMG device. The record
includes body side, anatomical location, orientation, fixation, channel-to-
muscle mapping, operator verification, and device identity.

EMG placement is governed by the approved hardware-specific procedure. The
procedure must document skin preparation, electrode/strap orientation,
reference method, fixation, and signal check. A placement that is not verified
is retained in the capture but its windows are not eligible as ground truth.

The normalization/reference method is recorded in both `CalibrationSession`
and `EMGRecording`; values with different normalization states must not be
silently combined.
