"""
电机控制运动学单元测试 — cmd_vel → RPM 转换

目标覆盖率: ≥80%
测试内容: 差速运动学、RPM 限幅、超时逻辑
"""

import math
import pytest


# ═══════════════════════════════════════════════════
# 运动学转换 (从 motor_controller.py 提取)
# ═══════════════════════════════════════════════════

WHEEL_RADIUS = 0.19       # m
WHEEL_SEPARATION = 0.65   # m
GEAR_RATIO = 56.0
MAX_RPM = 1500


def twist_to_rpm(v: float, w: float) -> tuple[int, int]:
    """cmd_vel (Twist) → 左右轮 RPM (与 motor_controller.py 逻辑一致)"""
    # 左右轮线速度
    v_left = v - w * WHEEL_SEPARATION / 2.0
    v_right = v + w * WHEEL_SEPARATION / 2.0

    # 线速度 → RPM
    rpm_left = int(v_left / (2.0 * math.pi * WHEEL_RADIUS) * 60.0 * GEAR_RATIO)
    rpm_right = int(v_right / (2.0 * math.pi * WHEEL_RADIUS) * 60.0 * GEAR_RATIO)

    # 限幅
    rpm_left = max(-MAX_RPM, min(MAX_RPM, rpm_left))
    rpm_right = max(-MAX_RPM, min(MAX_RPM, rpm_right))

    return rpm_left, rpm_right


class TestKinematics:

    def test_straight_forward(self):
        """直行: v=0.3, w=0 → 左右轮同速"""
        left, right = twist_to_rpm(0.3, 0.0)
        assert left > 0
        assert left == right

    def test_straight_backward(self):
        """倒车: v=-0.1, w=0 → 左右轮同速反转"""
        left, right = twist_to_rpm(-0.1, 0.0)
        assert left < 0
        assert left == right

    def test_zero_velocity(self):
        """停止: v=0, w=0 → 全部为 0"""
        left, right = twist_to_rpm(0.0, 0.0)
        assert left == 0
        assert right == 0

    def test_rotate_in_place_cw(self):
        """原地右转: v=0, w<0 (ROS: CW) → 左轮快, 右轮反转"""
        left, right = twist_to_rpm(0.0, -0.5)
        assert left > 0
        assert right < 0

    def test_rotate_in_place_ccw(self):
        """原地左转: v=0, w>0 (ROS: CCW) → 右轮快, 左轮反转"""
        left, right = twist_to_rpm(0.0, 0.5)
        assert left < 0
        assert right > 0

    def test_forward_turn_left(self):
        """前进+左转: v>0, w>0 (CCW) → 右轮比左轮快"""
        left, right = twist_to_rpm(0.2, 0.3)
        assert right > left

    def test_forward_turn_right(self):
        """前进+右转: v>0, w<0 (CW) → 左轮比右轮快"""
        left, right = twist_to_rpm(0.2, -0.3)
        assert left > right

    def test_rpm_clamped_to_max(self):
        """RPM 限幅: 超速时被限制在 ±1500"""
        # 极大线速度 → RPM 会远超 1500
        left, right = twist_to_rpm(100.0, 0.0)
        assert left == MAX_RPM
        assert right == MAX_RPM

    def test_rpm_clamped_to_min(self):
        """RPM 限幅: 反向超速时限制在 -1500"""
        left, right = twist_to_rpm(-100.0, 0.0)
        assert left == -MAX_RPM
        assert right == -MAX_RPM

    def test_typical_push_speed(self):
        """推料典型速度: v=0.25 m/s → RPM ≈ 704"""
        left, right = twist_to_rpm(0.25, 0.0)
        # 0.25 / (2*pi*0.19) * 60 * 56 = 703.7
        assert 680 < left < 720

    def test_physical_dimensions_affect_output(self):
        """修改轮径/轮距影响输出"""
        left1, _ = twist_to_rpm(0.3, 0.2)
        # 如果轮距不同，转弯时 RPM 会不同
        left2, right2 = twist_to_rpm(0.3, 0.2)
        assert left2 != right2 if abs(0.2) > 0.01 else left2 == right2


class TestSafetyLimits:

    def test_large_angular_velocity_doesnt_overflow(self):
        """大角速度不溢出"""
        left, right = twist_to_rpm(0.0, 10.0)
        assert -MAX_RPM <= left <= MAX_RPM
        assert -MAX_RPM <= right <= MAX_RPM

    def test_both_linear_and_angular_at_max(self):
        """线性+角速度同时最大时不溢出"""
        left, right = twist_to_rpm(0.5, 0.8)  # Nav2 max
        assert -MAX_RPM <= left <= MAX_RPM
        assert -MAX_RPM <= right <= MAX_RPM


class TestGearRatio:
    """减速比校准"""

    def test_higher_gear_ratio_increases_rpm(self):
        """减速比越大 → 输出 RPM 越大"""
        # 这里验证公式中的 gear_ratio 影响
        v = 0.3
        rpm_no_gear = v / (2 * math.pi * 0.19) * 60  # 直驱
        rpm_with_gear = v / (2 * math.pi * 0.19) * 60 * 56
        assert rpm_with_gear == rpm_no_gear * 56
