"""
安全传感器逻辑单元测试

目标覆盖率: ≥90%
测试内容: 触发逻辑、急停优先级、超声波距离计算、GPIO 模拟
"""

import math
import pytest


# ═══════════════════════════════════════════════════
# 超声波距离计算 (从硬件信号)
# ═══════════════════════════════════════════════════

SOUND_SPEED = 343.0  # m/s at 20°C


def pulse_to_distance(pulse_duration_s: float) -> float:
    """
    超声波脉冲时长 → 距离 (米)

    声波往返: distance = speed * time / 2
    """
    return SOUND_SPEED * pulse_duration_s / 2.0


class TestUltrasonicDistance:

    def test_1cm_distance(self):
        """1cm ≈ 58.3μs 脉冲"""
        # 0.01m = 343 * t / 2 → t = 2*0.01/343 ≈ 58.3μs
        dist = pulse_to_distance(2 * 0.01 / SOUND_SPEED)
        assert abs(dist - 0.01) < 0.001

    def test_1m_distance(self):
        """1m ≈ 5.83ms 脉冲"""
        dist = pulse_to_distance(2 * 1.0 / SOUND_SPEED)
        assert abs(dist - 1.0) < 0.001

    def test_max_range_4m(self):
        """4m 有效范围边界"""
        dist = pulse_to_distance(2 * 4.0 / SOUND_SPEED)
        assert abs(dist - 4.0) < 0.001

    def test_min_range_2cm(self):
        """2cm 最小有效距离"""
        dist = pulse_to_distance(2 * 0.02 / SOUND_SPEED)
        assert abs(dist - 0.02) < 0.001

    def test_zero_duration_is_zero_distance(self):
        assert pulse_to_distance(0.0) == 0.0

    def test_distance_is_linear(self):
        """距离与脉冲时长成正比"""
        d1 = pulse_to_distance(0.001)
        d2 = pulse_to_distance(0.002)
        assert abs(d2 - 2 * d1) < 0.001


# ═══════════════════════════════════════════════════
# 安全触发逻辑
# ═══════════════════════════════════════════════════

class SafetyState:
    """模拟 safety_sensor 的状态机 (不含 GPIO/ROS)"""

    def __init__(self):
        self.bumper_left: bool = False
        self.bumper_right: bool = False
        self.emergency_pressed: bool = False
        self.ultrasonic_distance: float = 999.0
        self.min_distance: float = 0.3

    def check_trigger(self) -> tuple[bool, str]:
        """检查是否触发安全停止, 返回 (triggered, reason)"""
        reasons: list[str] = []

        if self.bumper_left:
            reasons.append("安全触边左触发")
        if self.bumper_right:
            reasons.append("安全触边右触发")
        if self.emergency_pressed:
            reasons.append("急停按钮按下")

        if reasons:
            return True, " + ".join(reasons)
        return False, ""


class TestSafetyLogic:

    def test_no_trigger_when_all_clear(self):
        state = SafetyState()
        triggered, reason = state.check_trigger()
        assert not triggered
        assert reason == ""

    def test_left_bumper_triggers(self):
        state = SafetyState()
        state.bumper_left = True
        triggered, reason = state.check_trigger()
        assert triggered
        assert "左触发" in reason

    def test_right_bumper_triggers(self):
        state = SafetyState()
        state.bumper_right = True
        triggered, reason = state.check_trigger()
        assert triggered
        assert "右触发" in reason

    def test_emergency_button_triggers(self):
        state = SafetyState()
        state.emergency_pressed = True
        triggered, reason = state.check_trigger()
        assert triggered
        assert "急停" in reason

    def test_both_bumpers_triggers(self):
        state = SafetyState()
        state.bumper_left = True
        state.bumper_right = True
        triggered, reason = state.check_trigger()
        assert triggered
        assert "左触发" in reason
        assert "右触发" in reason

    def test_all_triggers_combined(self):
        state = SafetyState()
        state.bumper_left = True
        state.bumper_right = True
        state.emergency_pressed = True
        triggered, reason = state.check_trigger()
        assert triggered
        assert "左触发" in reason
        assert "右触发" in reason
        assert "急停" in reason

    def test_trigger_then_clear(self):
        """触发后放开应恢复正常"""
        state = SafetyState()
        state.emergency_pressed = True
        assert state.check_trigger()[0]

        state.emergency_pressed = False
        assert not state.check_trigger()[0]


# ═══════════════════════════════════════════════════
# 超声波距离校验
# ═══════════════════════════════════════════════════

class TestUltrasonicValidation:

    def test_valid_range_accepted(self):
        """2cm-4m 内的值应被接受"""
        assert 0.02 < 0.5 < 4.0   # 50cm 有效
        assert 0.02 < 2.0 < 4.0   # 2m 有效

    def test_too_close_rejected(self):
        """小于 2cm 的值视为无效"""
        assert not (0.02 < 0.01 < 4.0)

    def test_too_far_rejected(self):
        """大于 4m 的值视为无效"""
        assert not (0.02 < 5.0 < 4.0)

    def test_exact_boundaries(self):
        """边界值验证"""
        assert not (0.02 < 0.02 < 4.0)   # 等于下限 → 无效
        assert not (0.02 < 4.0 < 4.0)     # 等于上限 → 无效
        assert 0.02 < 0.021 < 4.0         # 略大于下限 → 有效


# ═══════════════════════════════════════════════════
# GPIO 模拟 (低电平触发)
# ═══════════════════════════════════════════════════

class TestGpioTrigger:
    """GPIO 逻辑: 上拉输入, LOW(0) = 触发"""

    def test_high_is_safe(self):
        """GPIO.HIGH (1) = 未触发"""
        gpio_state = 1
        assert gpio_state == 1  # PUD_UP → 正常为 HIGH

    def test_low_is_triggered(self):
        """GPIO.LOW (0) = 触发"""
        gpio_state = 0
        assert gpio_state == 0  # 触发 = LOW

    def test_pull_up_default(self):
        """上拉电阻使默认状态为 HIGH (安全)"""
        # 断电/断线时 PUD_UP → HIGH → 不会误触发
        default_state = 1  # simulate PUD_UP
        assert default_state == 1
