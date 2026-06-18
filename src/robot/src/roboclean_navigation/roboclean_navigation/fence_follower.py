"""
围栏跟随导航节点 — 通道中线追踪 (v2)

传感器融合: 2D LiDAR (两侧通道中线) + 超声波 (辅助校验)
适用场景: 两侧都有围栏的饲喂通道, 围栏不一定是直线

算法:
  1. LiDAR 点云 → 分为左/右两侧区域
  2. 每侧提取围栏轮廓点 (去噪 + 平滑)
  3. 逐距离切片计算通道中线 = (左轮廓 + 右轮廓) / 2
  4. 拟合平滑中线路径
  5. PID 沿中线行驶 + 拐角降速

物理依赖 (装车后必须核实):
  channel_width ≈ 3.0m          ← 通道宽度 (两侧围栏间距)
  target_offset = 0.0m          ← 相对中线的偏移 (>0 = 偏右)
  forward_speed = 0.25 m/s      ← 推料速度
  超声波安装位置 = 两侧         ← 校验围栏距离
  LiDAR 安装高度/朝向           ← 影响角度筛选
"""

from __future__ import annotations

import math

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32, String


class FenceFollower(Node):
    """通道中线跟随控制器 (v2)"""

    def __init__(self):
        super().__init__('fence_follower')

        # ── 参数声明 ──
        self.declare_parameter('channel_width', 3.0)
        self.declare_parameter('target_offset', 0.0)
        self.declare_parameter('forward_speed', 0.25)
        self.declare_parameter('max_angular_speed', 0.6)
        # PID
        self.declare_parameter('pid_p_lateral', 1.2)
        self.declare_parameter('pid_i_lateral', 0.02)
        self.declare_parameter('pid_d_lateral', 0.3)
        self.declare_parameter('pid_p_angle', 0.8)
        # 围栏检测
        self.declare_parameter('left_angle_min_deg', -80)
        self.declare_parameter('left_angle_max_deg', -10)
        self.declare_parameter('right_angle_min_deg', 10)
        self.declare_parameter('right_angle_max_deg', 80)
        self.declare_parameter('min_fence_points', 5)
        self.declare_parameter('outlier_dist_m', 0.15)
        # 惯性
        self.declare_parameter('inertia_hold_frames', 50)
        self.declare_parameter('inertia_decel_factor', 0.9)
        # 超声波
        self.declare_parameter('use_ultrasonic', True)
        self.declare_parameter('ultrasonic_tolerance', 0.20)
        # 推料滚筒
        self.declare_parameter('drum_rpm', 800)

        # ── 读取参数 ──
        self.channel_w = self.get_parameter('channel_width').value
        self.target_offset = self.get_parameter('target_offset').value
        self.fwd_speed = self.get_parameter('forward_speed').value
        self.max_ang = self.get_parameter('max_angular_speed').value
        self.kp_lat = self.get_parameter('pid_p_lateral').value
        self.ki_lat = self.get_parameter('pid_i_lateral').value
        self.kd_lat = self.get_parameter('pid_d_lateral').value
        self.kp_ang = self.get_parameter('pid_p_angle').value
        self.left_ang_min = math.radians(self.get_parameter('left_angle_min_deg').value)
        self.left_ang_max = math.radians(self.get_parameter('left_angle_max_deg').value)
        self.right_ang_min = math.radians(self.get_parameter('right_angle_min_deg').value)
        self.right_ang_max = math.radians(self.get_parameter('right_angle_max_deg').value)
        self.min_points = self.get_parameter('min_fence_points').value
        self.outlier_dist = self.get_parameter('outlier_dist_m').value
        self.inertia_hold = self.get_parameter('inertia_hold_frames').value
        self.inertia_decel = self.get_parameter('inertia_decel_factor').value
        self.use_ultrasonic = self.get_parameter('use_ultrasonic').value
        self.ultrasonic_tolerance = self.get_parameter('ultrasonic_tolerance').value
        self.drum_rpm = self.get_parameter('drum_rpm').value

        # ── 检测状态 ──
        self.left_fence: np.ndarray | None = None  # N×2 左侧围栏点
        self.right_fence: np.ndarray | None = None  # N×2 右侧围栏点
        self.midline: np.ndarray | None = None  # N×2 中线点
        self.fence_detected: bool = False
        self.lateral_error: float = 0.0  # 到中线横向偏差
        self.angle_error: float = 0.0  # 中线方向偏差

        # ── 超声波 ──
        self.ultrasonic_left: float | None = None
        self.ultrasonic_right: float | None = None
        self.ultrasonic_valid: bool = False

        # ── PID 积分 ──
        self.lat_integral: float = 0.0
        self.lat_prev_error: float = 0.0

        # ── 惯性 ──
        self.lost_fence_count: int = 0
        self.inertia_active: bool = False
        self.inertia_linear: float = 0.0
        self.inertia_angular: float = 0.0

        # ── 导航仲裁 ──
        self._nav_active: bool = False
        self._task_enabled: bool = False

        # ── 订阅 ──
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.ultra_sub = self.create_subscription(
            Float32, '/ultrasonic/fence', self.ultrasonic_callback, 10
        )
        self.nav_sub = self.create_subscription(Bool, '/nav/active', self._nav_active_callback, 10)
        self.create_subscription(Bool, '/task/start', self._task_start_callback, 10)
        self.create_subscription(Bool, '/task/stop', self._task_stop_callback, 10)

        # ── 发布 ──
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.drum_pub = self.create_publisher(Bool, '/drum/run', 10)
        self.status_pub = self.create_publisher(String, '/fence/status', 10)

        # ── 定时器 20Hz ──
        self.control_timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info(
            f'通道中线跟随已启动 (v2) | 通道宽={self.channel_w}m ' f'| 速度={self.fwd_speed}m/s'
        )

    # ═════════════════════════════════════════════════════════
    # LiDAR 通道检测
    # ═════════════════════════════════════════════════════════

    def scan_callback(self, msg: LaserScan) -> None:
        """从 LiDAR 提取左右两侧围栏 + 计算中线"""
        xy = self._scan_to_xy(msg)
        if len(xy) < self.min_points * 2:
            self.fence_detected = False
            return

        # 分为左右两侧
        left_pts = self._filter_by_angle(xy, msg, self.left_ang_min, self.left_ang_max)
        right_pts = self._filter_by_angle(xy, msg, self.right_ang_min, self.right_ang_max)

        # 去噪: 移除孤立离群点
        left_clean = self._remove_outliers(left_pts)
        right_clean = self._remove_outliers(right_pts)

        if len(left_clean) < self.min_points or len(right_clean) < self.min_points:
            # 至少一侧围栏可见 → 尝试单侧模式
            if len(left_clean) >= self.min_points:
                self._single_side_detect(left_clean, side='left')
            elif len(right_clean) >= self.min_points:
                self._single_side_detect(right_clean, side='right')
            else:
                self.fence_detected = False
            return

        self.left_fence = left_clean
        self.right_fence = right_clean

        # 计算通道中线
        midline = self._compute_midline(left_clean, right_clean)
        if midline is None or len(midline) < 2:
            self.fence_detected = False
            return

        self.midline = midline

        # 计算横向偏差和角度偏差
        # 取中线最近的一段, 计算原点到中线的距离和角度
        a, b, c = self._fit_local_line(midline[:10])  # 最近 10 个点
        if a is None:
            self.fence_detected = False
            return

        dist = abs(c) / math.sqrt(a * a + b * b)
        self.lateral_error = dist - self.target_offset

        line_angle = math.atan2(-a, b)
        self.angle_error = line_angle

        self.fence_detected = True
        self.lost_fence_count = 0

    def _single_side_detect(self, pts: np.ndarray, side: str) -> None:
        """单侧围栏模式 (仅一侧有围栏时)"""
        a, b, c = self._fit_local_line(pts)
        if a is None:
            self.fence_detected = False
            return
        dist = abs(c) / math.sqrt(a * a + b * b)
        # 推定通道中线: 单侧围栏 + 半通道宽度偏移
        if side == 'left':
            self.lateral_error = (dist + self.channel_w / 2.0) - self.target_offset
        else:
            self.lateral_error = (dist - self.channel_w / 2.0) - self.target_offset
        self.angle_error = math.atan2(-a, b)
        self.left_fence = pts if side == 'left' else None
        self.right_fence = pts if side == 'right' else None
        self.midline = None
        self.fence_detected = True
        self.lost_fence_count = 0

    # ── 点云处理 ──

    def _scan_to_xy(self, msg: LaserScan) -> np.ndarray:
        """极坐标 → 直角坐标 (N×2), 滤除无效值"""
        angles = np.arange(msg.angle_min, msg.angle_max, msg.angle_increment)[: len(msg.ranges)]
        ranges = np.array(msg.ranges[: len(angles)])
        valid = (ranges > msg.range_min) & (ranges < msg.range_max)
        ang = angles[valid]
        rng = ranges[valid]
        x = rng * np.cos(ang)
        y = rng * np.sin(ang)
        return np.column_stack([x, y])

    def _filter_by_angle(
        self, xy: np.ndarray, msg: LaserScan, ang_min: float, ang_max: float
    ) -> np.ndarray:
        """筛选指定角度范围内的点"""
        if len(xy) == 0:
            return np.empty((0, 2))
        angles = np.arctan2(xy[:, 1], xy[:, 0])
        mask = (angles >= ang_min) & (angles <= ang_max)
        return xy[mask]

    def _remove_outliers(self, pts: np.ndarray) -> np.ndarray:
        """移除离群点: 距离最近邻超过阈值的点"""
        if len(pts) < 3:
            return pts
        # 按 y 坐标排序 (沿前进方向)
        order = np.argsort(pts[:, 1])
        sorted_pts = pts[order]
        # 相邻点间距
        diffs = np.abs(np.diff(sorted_pts[:, 0]))
        # 保留相邻间距不超过阈值的连续段
        mask = np.ones(len(sorted_pts), dtype=bool)
        for i in range(1, len(sorted_pts)):
            if diffs[i - 1] > self.outlier_dist:
                # 检查前后连续性
                if i + 1 < len(sorted_pts) and diffs[i] > self.outlier_dist:
                    mask[i] = False
        return sorted_pts[mask]

    def _compute_midline(self, left: np.ndarray, right: np.ndarray) -> np.ndarray | None:
        """
        计算通道中线: 沿前进方向切片, 每对 (左, 右) 取中点

        方法: 沿 y 轴 (前进方向) 等距切片, 每片内:
          - 找左围栏最近的 x
          - 找右围栏最近的 x
          - 中点 = (x_left + x_right) / 2
        """
        # 取前进方向的有效范围
        y_min = max(left[:, 1].min(), right[:, 1].min())
        y_max = min(left[:, 1].max(), right[:, 1].max())
        if y_max - y_min < 0.1:  # 重叠太少
            return None

        n_slices = 20
        y_edges = np.linspace(y_min, y_max, n_slices + 1)
        midline_pts: list[list[float]] = []

        for i in range(n_slices):
            y_lo, y_hi = y_edges[i], y_edges[i + 1]
            y_mid = (y_lo + y_hi) / 2.0

            # 左围栏在此切片内的点
            left_slice = left[(left[:, 1] >= y_lo) & (left[:, 1] < y_hi)]
            right_slice = right[(right[:, 1] >= y_lo) & (right[:, 1] < y_hi)]

            if len(left_slice) == 0 or len(right_slice) == 0:
                continue

            # 取中位数 x (比均值更抗离群点)
            x_left = np.median(left_slice[:, 0])
            x_right = np.median(right_slice[:, 0])

            midline_pts.append([float((x_left + x_right) / 2.0), float(y_mid)])

        if len(midline_pts) < 2:
            return None
        return np.array(midline_pts)

    def _fit_local_line(self, pts: np.ndarray) -> tuple[float | None, float | None, float | None]:
        """
        PCA 总体最小二乘拟合最近的一段 → ax + by + c = 0
        用于计算横向/角度偏差, 不受远处拐角影响
        """
        if len(pts) < 2:
            return None, None, None
        mean = pts.mean(axis=0)
        centered = pts - mean
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        normal = vh[-1]
        a, b = float(normal[0]), float(normal[1])
        c = float(-(a * mean[0] + b * mean[1]))
        if b < 0:
            a, b, c = -a, -b, -c
        return a, b, c

    # ═════════════════════════════════════════════════════════
    # 超声波
    # ═════════════════════════════════════════════════════════

    def ultrasonic_callback(self, msg: Float32) -> None:
        d = msg.data
        if 0.05 < d < 4.0:
            self.ultrasonic_left = d
            self.ultrasonic_valid = True
        else:
            self.ultrasonic_valid = False

    # ═════════════════════════════════════════════════════════
    # 导航仲裁
    # ═════════════════════════════════════════════════════════

    def _nav_active_callback(self, msg: Bool) -> None:
        self._nav_active = msg.data

    def _task_start_callback(self, msg: Bool) -> None:
        if msg.data:
            self._task_enabled = True
            self.get_logger().info('任务调度: 启动推料')

    def _task_stop_callback(self, msg: Bool) -> None:
        if msg.data:
            self._task_enabled = False
            self._stop(reset=True)
            self.get_logger().info('任务调度: 停止推料')

    # ═════════════════════════════════════════════════════════
    # PID 控制循环 (20Hz)
    # ═════════════════════════════════════════════════════════

    def control_loop(self) -> None:
        if self._nav_active or not self._task_enabled:
            return

        if self.fence_detected:
            self._pid_control()
            return

        # 围栏丢失
        self.lost_fence_count += 1

        if self.use_ultrasonic and self.ultrasonic_valid:
            ultra_err = (self.ultrasonic_left or 0.5) - self.channel_w / 2.0
            if abs(ultra_err) < self.ultrasonic_tolerance:
                self._ultrasonic_control(ultra_err)
                return

        if self.lost_fence_count <= self.inertia_hold:
            self._inertia_hold()
        else:
            self.get_logger().warn(f'围栏丢失 {self.lost_fence_count}帧 → 停车')
            self._stop(reset=True)

    def _pid_control(self) -> None:
        self.lat_integral += self.lateral_error * 0.05
        lat_derivative = (self.lateral_error - self.lat_prev_error) / 0.05
        self.lat_prev_error = self.lateral_error

        ang_lat = (
            self.kp_lat * self.lateral_error
            + self.ki_lat * self.lat_integral
            + self.kd_lat * lat_derivative
        )
        ang_ang = self.kp_ang * self.angle_error
        angular = ang_lat + ang_ang
        angular = max(-self.max_ang, min(self.max_ang, angular))

        # 拐角检测: 中线曲率大 → 降速
        curve_factor = 1.0
        if self.midline is not None and len(self.midline) >= 3:
            curve_factor = self._compute_curvature_factor(self.midline)

        speed = self.fwd_speed * max(0.3, min(1.0, 1.0 - abs(self.angle_error) / 0.5))
        speed *= curve_factor

        t = Twist()
        t.linear.x = speed
        t.angular.z = angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))

        sides = f'L={len(self.left_fence) if self.left_fence is not None else 0}'
        sides += f' R={len(self.right_fence) if self.right_fence is not None else 0}'
        self.status_pub.publish(
            String(
                data=f'CHANNEL|{sides} lat={self.lateral_error:.3f}m '
                f'ang={math.degrees(self.angle_error):.1f}deg '
                f'v={speed:.2f}m/s curve={curve_factor:.1f}'
            )
        )

    def _compute_curvature_factor(self, midline: np.ndarray) -> float:
        """计算中线曲率 → 曲率越大返回越小 (用于降速)"""
        if len(midline) < 3:
            return 1.0
        # 用前 5 个点的方向变化估计曲率
        pts = midline[: min(5, len(midline))]
        vectors = np.diff(pts, axis=0)
        angles = np.arctan2(vectors[:, 1], vectors[:, 0])
        if len(angles) < 2:
            return 1.0
        angle_change = np.abs(np.diff(angles)).mean()
        # 角度变化 >10° → 显著拐弯 → 降速
        return max(0.3, 1.0 - angle_change / 0.5)

    def _ultrasonic_control(self, ultra_err: float) -> None:
        angular = self.kp_lat * ultra_err * 0.5
        angular = max(-self.max_ang * 0.5, min(self.max_ang * 0.5, angular))
        t = Twist()
        t.linear.x = self.fwd_speed * 0.5
        t.angular.z = angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))
        self.status_pub.publish(String(data=f'ULTRA|err={ultra_err:.3f}m'))

    def _inertia_hold(self) -> None:
        if not self.inertia_active:
            self.inertia_active = True
            self.inertia_linear = self.fwd_speed
            ang = self.kp_lat * self.lateral_error + self.kp_ang * self.angle_error
            self.inertia_angular = max(-self.max_ang, min(self.max_ang, ang))
        self.inertia_linear *= self.inertia_decel
        t = Twist()
        t.linear.x = self.inertia_linear
        t.angular.z = self.inertia_angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))

    def _stop(self, reset: bool = False) -> None:
        self.cmd_pub.publish(Twist())
        self.drum_pub.publish(Bool(data=False))
        if reset:
            self.lat_integral = 0.0
            self.inertia_active = False
            self.inertia_linear = 0.0

    def destroy_node(self) -> None:
        self._stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(FenceFollower())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
