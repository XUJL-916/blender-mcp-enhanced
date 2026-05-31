#================================================================
#  ================================================================
#  test_fcurves_compatibility.py
#  ================================================================
#
#  Copyright (c) 2026  XUJL
#  Affiliation:  Shenzhen University (SZU)
#
#  Project:        Blender-MCP Enhanced (v1.5.5-enh)
#  Repository:     https://github.com/XUJL-916/blender-mcp-enhanced
#  Created:        2026
#  License:        MIT
#
#  Description:
#      [File purpose description]
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

import pytest


# ---------------------------------------------------------------------------
#  Stand-in fakes for bpy types
# ---------------------------------------------------------------------------

class _FakeFCurve:
    """Minimal FCurve stub."""

    def __init__(self, data_path: str, array_index: int, kp_count: int):
        self.data_path = data_path
        self.array_index = array_index
        self._kp_count = kp_count

    def __repr__(self):
        return f"FCurve({self.data_path}[{self.array_index}], kp={self._kp_count})"


class _FakeKeyframePoint:
    """Minimal keyframe point stub (simulates keyframe_points)."""

    def __init__(self, frame: float, value: float):
        self.co = (frame, value)


class _FakeKeyPoints:
    """A list-like container of keyframe points."""

    def __init__(self, points: list):
        self._points = points

    def __iter__(self):
        return iter(self._points)

    def __len__(self):
        return len(self._points)

    def __getitem__(self, idx):
        return self._points[idx]


class _FakeLegacyFCurve(_FakeFCurve):
    """FCurve with legacy data_points attribute."""

    def __init__(self, data_path, array_index, kp_count):
        super().__init__(data_path, array_index, kp_count)
        self.data_points = _FakeKeyPoints([_FakeKeyframePoint(1, 0)] * kp_count)


class _Fake5xFCurve(_FakeFCurve):
    """FCurve with Blender 5.x keyframe_points attribute."""

    def __init__(self, data_path, array_index, kp_count):
        super().__init__(data_path, array_index, kp_count)
        self.keyframe_points = _FakeKeyPoints([_FakeKeyframePoint(1, 0)] * kp_count)


class _FakeChannelbag:
    """Blender 5.x ActionChannelbag stub."""

    def __init__(self, fcurves):
        self.fcurves = fcurves


class _FakeStrip:
    """Blender 5.x ActionKeyframeStrip stub."""

    def __init__(self, channelbags):
        self.channelbags = channelbags
        self.type = "KEYFRAME"


class _FakeLayer:
    """Blender 5.x ActionLayer stub."""

    def __init__(self, strips):
        self.strips = strips
        self.name = "Layer"


class _FakeLegacyAction:
    """Simulates a Blender 4.x Action with direct .fcurves attribute."""

    def __init__(self, fcurves):
        self.fcurves = fcurves
        self.name = "TestAction"


class _Fake5xAction:
    """Simulates a Blender 5.x Action with layers/strips/channelbags hierarchy."""

    def __init__(self, fcurves):
        self.name = "TestAction"
        channelbag = _FakeChannelbag(fcurves)
        strip = _FakeStrip([channelbag])
        layer = _FakeLayer([strip])
        self.layers = [layer]


class _FakeEmptyAction:
    """Action with no fcurves (empty layers or empty fcurves list)."""

    def __init__(self, structure="legacy_empty"):
        self.name = "EmptyAction"
        if structure == "legacy_empty":
            self.fcurves = []
        elif structure == "legacy_no_attr":
            pass
        elif structure == "5x_no_layers":
            self.layers = []
        elif structure == "5x_empty_bag":
            channelbag = _FakeChannelbag([])
            strip = _FakeStrip([channelbag])
            layer = _FakeLayer([strip])
            self.layers = [layer]


# ---------------------------------------------------------------------------
#  Compatibility functions (mirrors addon.py — must stay in sync)
# ---------------------------------------------------------------------------

def get_action_fcurves(action):
    """Retrieve FCurves from a Blender Action — Blender 4.x / 5.x compatible.

    Parameters
    ----------
    action : bpy.types.Action or None

    Returns
    -------
    list
        A list of FCurve objects (may be empty). Never raises.
    """
    if action is None:
        return []

    # ---- Legacy: Blender 4.x and earlier ----
    try:
        legacy = action.fcurves
        if hasattr(legacy, "__iter__") or hasattr(legacy, "__len__"):
            return list(legacy)
    except AttributeError:
        pass

    # ---- Blender 5.x+ ----
    try:
        layers = action.layers
        if not layers or len(layers) == 0:
            return []
        layer = layers[0]
        strips = layer.strips
        if not strips or len(strips) == 0:
            return []
        strip = strips[0]
        bags = strip.channelbags
        if not bags or len(bags) == 0:
            return []
        bag = bags[0]
        fcurves = bag.fcurves
        if fcurves:
            return list(fcurves)
    except (AttributeError, IndexError, TypeError):
        pass

    return []


def get_action_keyframe_count(action):
    """Count total keyframes across all FCurves in an Action.

    Parameters
    ----------
    action : bpy.types.Action or None

    Returns
    -------
    int
        Total number of keyframe_points across all fcurves.
    """
    if action is None:
        return 0

    fcurves = get_action_fcurves(action)
    count = 0
    for fc in fcurves:
        if hasattr(fc, "keyframe_points"):
            count += len(fc.keyframe_points)
        elif hasattr(fc, "data_points"):
            count += len(fc.data_points)
    return count


# ============================================================
#  Tests: get_action_fcurves
# ============================================================

class TestGetActionFCurves:
    """Test the compatibility function get_action_fcurves()."""

    def test_none_action(self):
        """Should return empty list for None."""
        result = get_action_fcurves(None)
        assert result == []

    def test_legacy_fcurves(self):
        """Legacy Blender 4.x: action.fcurves is a direct list."""
        fcurves = [_FakeLegacyFCurve("location", 0, 3),
                   _FakeLegacyFCurve("rotation_euler", 2, 3)]
        action = _FakeLegacyAction(fcurves)
        result = get_action_fcurves(action)
        assert len(result) == 2
        assert result[0].data_path == "location"
        assert result[1].data_path == "rotation_euler"

    def test_blender_5x_fcurves(self):
        """Blender 5.x: fcurves nested in layers/strips/channelbags."""
        fcurves = [_Fake5xFCurve("location", 0, 3),
                   _Fake5xFCurve("scale", 0, 3)]
        action = _Fake5xAction(fcurves)
        result = get_action_fcurves(action)
        assert len(result) == 2
        assert result[0].data_path == "location"
        assert result[1].data_path == "scale"
        assert hasattr(result[0], "keyframe_points")
        assert len(result[0].keyframe_points) == 3

    def test_empty_legacy(self):
        """Legacy action with empty fcurves list."""
        action = _FakeEmptyAction("legacy_empty")
        result = get_action_fcurves(action)
        assert result == []

    def test_legacy_no_fcurves_attr(self):
        """Legacy action without fcurves attribute — falls through to 5.x."""
        action = _FakeEmptyAction("legacy_no_attr")
        result = get_action_fcurves(action)
        # No .fcurves → falls through to 5.x path
        # No .layers → returns []
        assert result == []

    def test_5x_no_layers(self):
        """5.x action with empty layers list."""
        action = _FakeEmptyAction("5x_no_layers")
        result = get_action_fcurves(action)
        assert result == []

    def test_5x_empty_channelbag(self):
        """5.x action with layers but empty fcurves in channelbag."""
        action = _FakeEmptyAction("5x_empty_bag")
        result = get_action_fcurves(action)
        assert result == []

    def test_mixed_legacy_and_5x_fcurves(self):
        """Some fcurves use data_points, some use keyframe_points."""
        mixed = [_FakeLegacyFCurve("location", 0, 2),
                 _Fake5xFCurve("rotation_euler", 0, 3),
                 _FakeLegacyFCurve("scale", 0, 1)]
        action = _FakeLegacyAction(mixed)
        result = get_action_fcurves(action)
        assert len(result) == 3
        assert result[0].data_points[0].co[0] == 1
        assert len(result[1].keyframe_points) == 3
        assert result[2].data_points[0].co[0] == 1

    def test_returns_list_not_collection(self):
        """Result should always be a Python list, not the original collection."""
        fcurves = [_FakeLegacyFCurve("location", 0, 3)]
        action = _FakeLegacyAction(fcurves)
        result = get_action_fcurves(action)
        assert isinstance(result, list)
        assert result is not fcurves


class TestGetActionKeyframeCount:
    """Test the keyframe counting helper."""

    def test_none_action(self):
        assert get_action_keyframe_count(None) == 0

    def test_legacy_fcurves_count(self):
        """Count keyframes via legacy data_points."""
        fcurves = [_FakeLegacyFCurve("location", 0, 5),
                   _FakeLegacyFCurve("scale", 0, 3)]
        action = _FakeLegacyAction(fcurves)
        assert get_action_keyframe_count(action) == 8

    def test_5x_fcurves_count(self):
        """Count keyframes via Blender 5.x keyframe_points."""
        fcurves = [_Fake5xFCurve("location", 0, 5),
                   _Fake5xFCurve("rotation_euler", 2, 4)]
        action = _Fake5xAction(fcurves)
        assert get_action_keyframe_count(action) == 9

    def test_empty_action(self):
        """Empty action returns 0."""
        action = _FakeEmptyAction("legacy_empty")
        assert get_action_keyframe_count(action) == 0

    def test_mixed_keyframe_types(self):
        """Mixed legacy/5.x fcurves in the same action."""
        mixed = [_FakeLegacyFCurve("location", 0, 3),
                 _Fake5xFCurve("scale", 0, 4)]
        action = _FakeLegacyAction(mixed)
        assert get_action_keyframe_count(action) == 7


class TestFunctionSignatures:
    """Verify the compatibility functions have correct signatures."""

    def test_get_action_fcurves_callable(self):
        assert callable(get_action_fcurves)

    def test_get_action_keyframe_count_callable(self):
        assert callable(get_action_keyframe_count)

    def test_get_action_fcurves_docstring(self):
        assert get_action_fcurves.__doc__ is not None
        assert "compatible" in get_action_fcurves.__doc__.lower()

    def test_get_action_keyframe_count_docstring(self):
        assert get_action_keyframe_count.__doc__ is not None
        assert "count" in get_action_keyframe_count.__doc__.lower()
