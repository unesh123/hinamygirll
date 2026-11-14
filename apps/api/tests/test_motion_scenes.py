import pytest
from pydantic import ValidationError
from hinaa_api.creative.motion import MotionScene, motion_frame, render_motion_frames
from hinaa_api.creative.models import CreativeJobSpec


def test_motion_is_deterministic_and_changes_over_time():
    scenes=[MotionScene(title="Hello",duration=2)]
    assert motion_frame(scenes,.5,320,180).tobytes()==motion_frame(scenes,.5,320,180).tobytes()
    assert motion_frame(scenes,.5,320,180).tobytes()!=motion_frame(scenes,1,320,180).tobytes()


def test_scene_contract_and_frame_budget():
    with pytest.raises(ValidationError):MotionScene(title="Hi",accent="javascript:bad")
    with pytest.raises(ValidationError):MotionScene(title="Hi",layout="execute_code")
    with pytest.raises(ValueError):render_motion_frames([MotionScene(title="Hi")],1920,1080,24)
    with pytest.raises(ValueError):render_motion_frames([MotionScene(title="Hi",duration=10)]*4,320,180,24)


def test_creative_request_preserves_editable_scenes():
    spec=CreativeJobSpec(operation="TIMELINE_EXPORT",prompt="Animate",motion_scenes=[{"title":"Hello","layout":"bars"}])
    assert spec.motion_scenes[0].layout=="bars"
    assert len(render_motion_frames([MotionScene(title="Hi",duration=1)],128,128,2))==2
