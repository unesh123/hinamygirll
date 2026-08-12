# Avatar Calibration Findings

Local browser inspection on the preferred `model_6164.vrm` showed that the model renders **backward-facing** in the current avatar scene. The camera also frames it too tightly and too low for a conversational portrait: the back of the head and oversized lower-body geometry dominate the avatar pane, while the face is unavailable.

The current procedural arm pose is not appropriate for this rig before its front-facing orientation and neutral rest pose are calibrated. The next change must apply a model-specific 180-degree root rotation, an upward portrait framing adjustment, and reduced pose strength for the selected model. The avatar should preserve the procedural fallback if the preferred model cannot load.


After the model-specific 180-degree root rotation and portrait calibration, `model_6164.vrm` renders **front-facing**. The face and upper torso are now visible and the prior backward-facing presentation is corrected. There is a brief initial load frame before the VRM settles, but the stable model render is correct. The current framing is an upper-body portrait; subsequent polish should make it slightly more spacious only if the user wants more shoulder/hand visibility.


## Live UI portrait review — 2026-08-12

The active `model_6164.vrm` Hinaa portrait faces forward, but its frame still shows more of the torso than a premium companion portrait needs. `model_5447.vrm` (Hinaa Classic) is also forward-facing, but its authored rest pose shows the upper arms extending laterally, which looks like a T-pose in the side panel. Both models need a tighter portrait camera target/FOV and model-specific framing so the visual emphasis is on face, shoulders, and upper torso rather than exposed arms or lower body.


The first tighter portrait calibration successfully removes the distracting wide arms and lower-body geometry from the default Hinaa view. The default `model_6164.vrm` frame is now slightly too close for the 335px avatar panel, with the face nearly filling the pane; the final refinement should step the camera back modestly while retaining the face-and-shoulder focus.


Final live review: the adjusted default Hinaa portrait now has balanced space around the head with visible shoulders and upper torso, while the Hinaa Classic portrait retains a similarly composed face-and-shoulders frame. In both models, the side-panel crop removes the distracting lateral rest-pose arms and lower-body geometry without changing the VRM arm rig or live lip-sync behavior.
