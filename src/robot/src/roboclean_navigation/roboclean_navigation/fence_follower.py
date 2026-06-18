"""
围栏跟随导航节点 — 推料机器人核心

传感器融合: 2D LiDAR (RANSAC + PCA 直线拟合) + 超声波 (辅助校验)
沿饲喂通道行驶 → 推料滚筒把饲料推向围栏

物理依赖 (装车后必须核实):
  fence_side = 'left'          ← 围栏在小车的哪一侧 (left/right)
  target_distance = 0.50m      ← 离围栏的目标距离 (取决于推料滚筒伸出量!)
  fence_angle_min/max = ±45°   ← LiDAR 搜索围栏的扇形角度范围
  forward_speed = 0.25 m/s     ← 推料行驶速度
  超声波安装位置 = 面向围栏一侧 ← 关联 /ultrasonic/fence
  LiDAR 安装位置/朝向 ← 影响 scan_callback 中的角度筛选
"""

import math
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32, String


def pca_line(xy: np.ndarray) -> tuple:
    """
    PCA 总体最小二乘直线拟合 (ax + by + c = 0)

    相比 y = f(x) 回归，PCA 对垂直/水平线都没有奇异性。
    """
    if len(xy) < 2:
        return None
    mean = xy.mean(axis=0)
    centered = xy - mean
    # SVD 分解: U @ diag(S) @ V^T
    # V 的行是主成分方向
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]               # 最小奇异值对应的方向 = 法向量
    a, b = normal[0], normal[1]
    c = -(a * mean[0] + b * mean[1])
    # 归一化符号: 让 c 在围栏侧为正
    if b < 0:
        a, b, c = -a, -b, -c
    return (float(a), float(b), float(c))


def ransac_line(xy: np.ndarray, min_samples: int = 10,
                residual_threshold: float = 0.05,
                max_trials: int = 100) -> tuple | None:
    """
    自实现 RANSAC 直线拟合 — 替代 sklearn.linear_model.RANSACRegressor

    Args:
        xy: N×2 点集
        min_samples: 每次采样点数
        residual_threshold: 内点距离阈值 (m)
        max_trials: 最大迭代次数

    Returns:
        (a, b, c) 满足 ax + by + c = 0，或 None
    """
    n = len(xy)
    if n < min_samples:
        return None

    best_inliers = 0
    best_line = None

    rng = np.random.default_rng()
    for _ in range(max_trials):
        # 随机采样 min_samples 个点
        idx = rng.choice(n, size=min(min_samples, n), replace=False)
        sample = xy[idx]
        line = pca_line(sample)
        if line is None:
            continue
        a, b, c = line
        # 计算所有点到直线的距离
        dists = np.abs(a * xy[:, 0] + b * xy[:, 1] + c) / math.sqrt(a * a + b * b)
        inliers = int(np.sum(dists < residual_threshold))
        if inliers > best_inliers:
            best_inliers = inliers
            best_line = line

    if best_line is None:
        return None

    # 用所有内点重新拟合
    a0, b0, c0 = best_line
    all_dists = np.abs(a0 * xy[:, 0] + b0 * xy[:, 1] + c0) / math.sqrt(a0 * a0 + b0 * b0)
    inlier_mask = all_dists < residual_threshold
    if np.sum(inlier_mask) >= min_samples:
        best_line = pca_line(xy[inlier_mask])

    return best_line


class FenceFollower(Node):
    """围栏跟随控制器"""

    def __init__(self):
        super().__init__('fence_follower')

        # ── 围栏跟随参数 ──
        self.declare_parameter('fence_side', 'left')
        self.declare_parameter('target_distance', 0.50)
        self.declare_parameter('forward_speed', 0.25)
        self.declare_parameter('max_angular_speed', 0.6)

        # ── PID 参数 ──
        self.declare_parameter('pid_p_lateral', 1.2)
        self.declare_parameter('pid_i_lateral', 0.02)
        self.declare_parameter('pid_d_lateral', 0.3)
        self.declare_parameter('pid_p_angle', 0.8)

        # ── 围栏检测参数 ──
        self.declare_parameter('ransac_min_samples', 10)
        self.declare_parameter('ransac_residual_threshold', 0.05)
        self.declare_parameter('fence_angle_min_deg', -45)
        self.declare_parameter('fence_angle_max_deg', 45)
        self.declare_parameter('min_fence_points', 8)

        # ── 惯性保持参数 ──
        self.declare_parameter('inertia_hold_frames', 50)
        self.declare_parameter('inertia_decel_factor', 0.9)

        # ── 超声波辅助参数 ──
        self.declare_parameter('use_ultrasonic', True)
        self.declare_parameter('ultrasonic_tolerance', 0.20)

        # ── 推料滚筒参数 ──
        self.declare_parameter('drum_rpm', 800)

        # 读取参数
        self.fence_side = self.get_parameter('fence_side').value
        self.target_dist = self.get_parameter('target_distance').value
        self.fwd_speed = self.get_parameter('forward_speed').value
        self.max_ang = self.get_parameter('max_angular_speed').value

        self.kp_lat = self.get_parameter('pid_p_lateral').value
        self.ki_lat = self.get_parameter('pid_i_lateral').value
        self.kd_lat = self.get_parameter('pid_d_lateral').value
        self.kp_ang = self.get_parameter('pid_p_angle').value

        self.ransac_min = self.get_parameter('ransac_min_samples').value
        self.ransac_thresh = self.get_parameter('ransac_residual_threshold').value
        self.fence_ang_min = math.radians(self.get_parameter('fence_angle_min_deg').value)
        self.fence_ang_max = math.radians(self.get_parameter('fence_angle_max_deg').value)
        self.min_points = self.get_parameter('min_fence_points').value

        self.inertia_hold = self.get_parameter('inertia_hold_frames').value
        self.inertia_decel = self.get_parameter('inertia_decel_factor').value

        self.use_ultrasonic = self.get_parameter('use_ultrasonic').value
        self.ultrasonic_tolerance = self.get_parameter('ultrasonic_tolerance').value

        self.drum_rpm = self.get_parameter('drum_rpm').value

        # ── 导航仲裁: waypoint_navigator 活动时暂停 ──
        self._nav_active: bool = False

        # ── 超声波数据 ──
        self.ultrasonic_distance: float | None = None
        self.ultrasonic_valid: bool = False

        # ── PID 状态 ──
        self.lat_integral: float = 0.0
        self.lat_prev_error: float = 0.0
        self.lost_fence_count: int = 0
        self.inertia_active: bool = False
        self.inertia_linear: float = 0.0
        self.inertia_angular: float = 0.0

        # 当前检测
        self.fence_detected: bool = False
        self.lateral_error: float = 0.0
        self.angle_error: float = 0.0

        # ── 订阅 ──
        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10)
        self.ultra_sub = self.create_subscription(
            Float32, '/ultrasonic/fence', self.ultrasonic_callback, 10)
        self.nav_sub = self.create_subscription(
            Bool, '/nav/active', self._nav_active_callback, 10)

        # ── 发布 ──
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.drum_pub = self.create_publisher(Bool, '/drum/run', 10)
        self.status_pub = self.create_publisher(String, '/fence/status', 10)

        # ── 定时器 20Hz ──
        self.control_timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info(
            f'围栏跟随已启动 | 侧: {self.fence_side} '
            f'| 目标距: {self.target_dist}m | 速度: {self.fwd_speed}m/s')

    # ═════════════════════════════════════════════════════════
    # LiDAR 围栏检测
    # ═════════════════════════════════════════════════════════

    def scan_callback(self, msg: LaserScan) -> None:
        """从激光数据中提取围栏线段"""
        angles, ranges = self._scan_to_xy(msg)

        if len(angles) < self.min_points:
            self.fence_detected = False
            return

        xy = self._filter_fence_region(angles, ranges)

        if len(xy) < self.min_points:
            self.fence_detected = False
            return

        # RANSAC 直线拟合 (自实现, PCA 总体最小二乘)
        line = ransac_line(xy, self.ransac_min, self.ransac_thresh)

        if line is None:
            self.fence_detected = False
            return

        a, b, c = line  # ax + by + c = 0

        # 横向误差: 原点到直线距离 - 目标距离
        dist = abs(c) / math.sqrt(a * a + b * b)
        self.lateral_error = dist - self.target_dist

        # 角度误差: 直线方向与机器人前进方向(y轴)的夹角
        fence_angle = math.atan2(-a, b)
        self.angle_error = fence_angle

        # 符号修正 (围栏在左侧时 lateral_error > 0 表示太远)
        if self.fence_side == 'left':
            if c > 0:
                self.lateral_error = -self.lateral_error
        else:
            if c < 0:
                self.lateral_error = -self.lateral_error

        self.fence_detected = True
        self.lost_fence_count = 0

    def _scan_to_xy(self, msg: LaserScan) -> tuple[np.ndarray, np.ndarray]:
        """极坐标 → 直角坐标, 过滤无效值"""
        angles = np.arange(msg.angle_min, msg.angle_max, msg.angle_increment)
        ranges = np.array(msg.ranges)
        valid = (ranges > msg.range_min) & (ranges < msg.range_max)
        return angles[valid], ranges[valid]

    def _filter_fence_region(self, angles: np.ndarray, ranges: np.ndarray) -> np.ndarray:
        """筛选围栏侧感兴趣区域内的点 → N×2 直角坐标数组"""
        xy_list: list[list[float]] = []
        for a, r in zip(angles, ranges):
            if self.fence_side == 'left':
                if not (self.fence_ang_min < a < self.fence_ang_max):
                    continue
            else:
                if not (-self.fence_ang_max < a < -self.fence_ang_min):
                    continue
            xy_list.append([r * math.cos(a), r * math.sin(a)])
        return np.array(xy_list) if xy_list else np.empty((0, 2))

    # ═════════════════════════════════════════════════════════
    # 超声波辅助
    # ═════════════════════════════════════════════════════════

    def _nav_active_callback(self, msg: Bool) -> None:
        """waypoint_navigator 活动时暂停围栏跟随"""
        self._nav_active = msg.data

    def ultrasonic_callback(self, msg: Float32) -> None:
        """接收侧方超声波距离 (m)"""
        d = msg.data
        if 0.05 < d < 4.0:
            self.ultrasonic_distance = d
            self.ultrasonic_valid = True
        else:
            self.ultrasonic_valid = False

    # ═════════════════════════════════════════════════════════
    # PID 控制 + 超声波辅助 + 惯性保持
    # ═════════════════════════════════════════════════════════

    def control_loop(self) -> None:
        """PID 控制主循环 (20Hz)"""

        # waypoint_navigator 活动时暂停围栏跟随，让其独占 /cmd_vel
        if self._nav_active:
            return

        if self.fence_detected:
            self._pid_control()
            return

        # 围栏丢失
        self.lost_fence_count += 1

        # 尝试超声波辅助
        if self.use_ultrasonic and self.ultrasonic_valid:
            ultra_err = self.ultrasonic_distance - self.target_dist  # type: ignore[operator]
            if abs(ultra_err) < self.ultrasonic_tolerance:
                self._ultrasonic_control(ultra_err)
                return

        # 惯性保持 → 超时停车
        if self.lost_fence_count <= self.inertia_hold:
            self._inertia_hold()
        else:
            self.get_logger().warn(
                f'围栏丢失 {self.lost_fence_count}帧 惯性超时 → 停车')
            self._stop(reset=True)

    def _pid_control(self) -> None:
        """完整 PID 跟随 (围栏正常)"""
        self.lat_integral += self.lateral_error * 0.05
        lat_derivative = (self.lateral_error - self.lat_prev_error) / 0.05
        self.lat_prev_error = self.lateral_error

        ang_from_lat = (self.kp_lat * self.lateral_error +
                        self.ki_lat * self.lat_integral +
                        self.kd_lat * lat_derivative)
        ang_from_angle = self.kp_ang * self.angle_error
        angular = ang_from_lat + ang_from_angle
        angular = max(-self.max_ang, min(self.max_ang, angular))

        speed_factor = 1.0 - abs(self.angle_error) / 0.5
        speed_factor = max(0.3, min(1.0, speed_factor))
        linear = self.fwd_speed * speed_factor

        t = Twist()
        t.linear.x = linear
        t.angular.z = angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))
        self.status_pub.publish(String(
            data=f'LIDAR|lat={self.lateral_error:.3f}m '
                 f'ang={math.degrees(self.angle_error):.1f}deg '
                 f'v={linear:.2f}m/s'))

    def _ultrasonic_control(self, ultra_err: float) -> None:
        """超声波单独跟随 (仅距离修正, 无角度)"""
        angular = self.kp_lat * ultra_err * 0.5
        angular = max(-self.max_ang * 0.5, min(self.max_ang * 0.5, angular))
        linear = self.fwd_speed * 0.6

        t = Twist()
        t.linear.x = linear
        t.angular.z = angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))
        self.status_pub.publish(String(
            data=f'ULTRA|dist={self.ultrasonic_distance:.2f}m '
                 f'err={ultra_err:.3f}m v={linear:.2f}m/s'))

    def _inertia_hold(self) -> None:
        """惯性保持 (围栏短暂丢失)"""
        if not self.inertia_active:
            self.inertia_active = True
            self.inertia_linear = self.fwd_speed
            self.inertia_angular = self._get_last_angular()
            self.get_logger().info(
                f'围栏+超声波均丢失 → 惯性 {self.inertia_hold}帧')

        self.inertia_linear *= self.inertia_decel
        t = Twist()
        t.linear.x = self.inertia_linear
        t.angular.z = self.inertia_angular
        self.cmd_pub.publish(t)
        self.drum_pub.publish(Bool(data=True))
        self.status_pub.publish(String(
            data=f'INERTIA|{self.lost_fence_count}/{self.inertia_hold} '
                 f'v={self.inertia_linear:.2f}m/s'))

    def _get_last_angular(self) -> float:
        ang = (self.kp_lat * self.lateral_error +
               self.kp_ang * self.angle_error)
        return float(max(-self.max_ang, min(self.max_ang, ang)))

    def _stop(self, reset: bool = False) -> None:
        t = Twist()
        self.cmd_pub.publish(t)
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
