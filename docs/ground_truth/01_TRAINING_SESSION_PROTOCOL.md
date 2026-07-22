# Ground Truth Training Session Protocol

## Purpose

Produce one immutable `CaptureSession` containing all evidence required to
prepare verified Smart Pod and measured EMG ground truth. This protocol is for
controlled training only; it is not used during gameplay.

## Required sequence

1. Create the capture identifier and confirm player consent/reference, session
   conditions, devices, firmware, and operator identity.
2. Record `CalibrationSession` metadata and perform the approved EMG reference
   procedure before movement drills.
3. Record a warm-up segment.
4. Run versioned drill segments, recording drill start/end and repetitions.
5. Record recovery segments between drill blocks and a final cooldown segment.
6. Verify sensor fixation and complete the acquisition record before closing
   the immutable capture.

`Calibration`, `warm_up`, `drill`, `recovery`, and `cool_down` are explicit
session phases. Only fully verified `drill` windows are eligible for future
supervised dataset construction; all other phases remain traceable evidence.
