# Avatar Calibration Findings

Local browser inspection on the preferred `model_6164.vrm` showed that the model renders **backward-facing** in the current avatar scene. The camera also frames it too tightly and too low for a conversational portrait: the back of the head and oversized lower-body geometry dominate the avatar pane, while the face is unavailable.

The current procedural arm pose is not appropriate for this rig before its front-facing orientation and neutral rest pose are calibrated. The next change must apply a model-specific 180-degree root rotation, an upward portrait framing adjustment, and reduced pose strength for the selected model. The avatar should preserve the procedural fallback if the preferred model cannot load.


After the model-specific 180-degree root rotation and portrait calibration, `model_6164.vrm` renders **front-facing**. The face and upper torso are now visible and the prior backward-facing presentation is corrected. There is a brief initial load frame before the VRM settles, but the stable model render is correct. The current framing is an upper-body portrait; subsequent polish should make it slightly more spacious only if the user wants more shoulder/hand visibility.
