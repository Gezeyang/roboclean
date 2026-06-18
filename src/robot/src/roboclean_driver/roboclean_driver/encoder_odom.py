"""
编码器 / 里程计 ROS 2 节点 — 精度增强版

内置: 打滑检测(3层)、异常丢弃、标定参数、诊断输出

物理依赖 (装车后必须核实):
  wheel_radius = 0.19m     ← 300-8 轮胎实际半径 (需装车实测!)
  wheel_separation = 0.65m ← 左右驱动轮中心距 (需装车实测!)
  gear_ratio = 56.0        ← 减速机速比 (核对铭牌)
  encoder_resolution = 131072 ← 绝对值编码器位数 (核对手册)
  encoder_register = 0x2104  ← ⚠️ 最后阶段: 核实编码器位置寄存器地址!

发布: /odom (Odometry)  /tf  /total_distance (Float32)  /diagnostics/odom (String)
"""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32, String
from tf2_ros import TransformBroadcaster

from .canopen_driver import C20Driver, get_shared_network


class EncoderOdomNode(Node):
    """绝对值编码器里程计节点（精度增强版）"""

    def __init__(self):
        super().__init__('encoder_odom')

        # ── 几何参数 ──
        self.declare_parameter('can_channel', 'can0')
        self.declare_parameter('wheel_radius', 0.19)
        self.declare_parameter('wheel_separation', 0.65)
        self.declare_parameter('gear_ratio', 56.0)
        self.declare_parameter('encoder_resolution', 131072)

        # ── 打滑检测阈值 ──
        self.declare_parameter('max_accel_mss', 2.0)  # 最大线加速度
        self.declare_parameter('max_angular_accel_radss', 4.0)  # 最大角加速度
        self.declare_parameter('max_slip_ratio', 0.30)  # 左右轮速比阈值
        self.declare_parameter('max_instant_jump_m', 0.05)  # 单帧最大位移

        # ── 标定修正系数 ──
        self.declare_parameter('wheel_radius_calib_left', 1.0)
        self.declare_parameter('wheel_radius_calib_right', 1.0)

        can_ch = self.get_parameter('can_channel').value
        self.radius = self.get_parameter('wheel_radius').value
        self.sep = self.get_parameter('wheel_separation').value
        self.gear = self.get_parameter('gear_ratio').value
        self.res = self.get_parameter('encoder_resolution').value

        self.max_accel = self.get_parameter('max_accel_mss').value
        self.max_ang_accel = self.get_parameter('max_angular_accel_radss').value
        self.max_slip_ratio = self.get_parameter('max_slip_ratio').value
        self.max_jump = self.get_parameter('max_instant_jump_m').value

        self.calib_left = self.get_parameter('wheel_radius_calib_left').value
        self.calib_right = self.get_parameter('wheel_radius_calib_right').value

        self.get_logger().info(
            f'有效半径 L={self.radius*self.calib_left:.4f}m '
            f'R={self.radius*self.calib_right:.4f}m 轮距={self.sep:.3f}m'
        )

        # 连接驱动器（只读，共享 Network）
        network = get_shared_network(can_ch)
        self.left = C20Driver(1, can_ch, network=network)
        self.right = C20Driver(2, can_ch, network=network)
        self.left.enter_operational()
        self.right.enter_operational()

        # 状态
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_left_pos: float | None = None
        self.last_right_pos: float | None = None
        self.total_distance = 0.0
        self.last_time = self.get_clock().now()
        self.last_vx = 0.0
        self.last_vth = 0.0

        # 统计
        self.slip_count = 0
        self.jump_count = 0
        self.read_error_count = 0
        self.update_count = 0

        self.tf_broadcaster = TransformBroadcaster(self)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.distance_pub = self.create_publisher(Float32, '/total_distance', 10)
        self.diag_pub = self.create_publisher(String, '/diagnostics/odom', 10)

        self.timer = self.create_timer(0.02, self.update_odometry)
        # ⚠️ 最后阶段: 寄存器地址 0x2104 需对照驱动手册确认
        # 当前假设 0x2104 = 编码器位置 (绝对值, raw counts)
        self.ENCODER_REG: int = 0x2104

        self.diag_timer = self.create_timer(1.0, self.publish_diagnostics)

        self.get_logger().info('里程计节点已启动 (精度增强版)')

    # ── 编码器读取 ──

    def _read_encoder_rad(self, driver: C20Driver) -> float | None:
        try:
            pos_raw = driver.node.sdo[self.ENCODER_REG].raw
            return (pos_raw / self.res) * 2.0 * math.pi / self.gear
        except Exception:
            self.read_error_count += 1
            return None

    # ── 核心更新 ──

    def update_odometry(self) -> None:
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        if dt <= 0:
            return
        self.last_time = now
        self.update_count += 1

        left_rad = self._read_encoder_rad(self.left)
        right_rad = self._read_encoder_rad(self.right)
        if left_rad is None or right_rad is None:
            return

        if self.last_left_pos is None:
            self.last_left_pos = left_rad
            self.last_right_pos = right_rad
            return

        d_left = left_rad - self.last_left_pos
        d_right = right_rad - self.last_right_pos

        d_left_dist = d_left * self.radius * self.calib_left
        d_right_dist = d_right * self.radius * self.calib_right

        # ── 检测1: 瞬时跳跃 ──
        if abs(d_left_dist) > self.max_jump or abs(d_right_dist) > self.max_jump:
            self.get_logger().warn(
                f'[JUMP] L={d_left_dist:.4f}m R={d_right_dist:.4f}m ' f'(>{self.max_jump}m) -> skip'
            )
            self.jump_count += 1
            return

        # ── 检测2: 加速度超限 ──
        d_center = (d_left_dist + d_right_dist) / 2.0
        d_theta = (d_right_dist - d_left_dist) / self.sep
        vx = d_center / dt
        vth = d_theta / dt
        ax = (vx - self.last_vx) / dt
        ath = (vth - self.last_vth) / dt

        if abs(ax) > self.max_accel or abs(ath) > self.max_ang_accel:
            self.get_logger().warn(
                f'[SLIP] ax={ax:.1f} ath={ath:.1f} (>{self.max_accel}/{self.max_ang_accel}) -> skip'
            )
            self.slip_count += 1
            self.last_left_pos = left_rad
            self.last_right_pos = right_rad
            self.last_vx = vx
            self.last_vth = vth
            return

        # ── 检测3: 左右轮速比 ──
        avg = (abs(d_left_dist) + abs(d_right_dist)) / 2.0
        diff = abs(d_left_dist - d_right_dist)
        if avg > 0.001 and diff / avg > self.max_slip_ratio:
            self.get_logger().warn(
                f'[RATIO] L/R diff ratio={diff/avg:.3f} (>{self.max_slip_ratio}) -> avg-only'
            )
            d_left_dist = d_right_dist = d_center
            d_theta = 0.0
            self.slip_count += 1

        # ── 正常更新 ──
        self.last_left_pos = left_rad
        self.last_right_pos = right_rad
        self.last_vx = vx
        self.last_vth = vth

        self.x += d_center * math.cos(self.theta + d_theta / 2.0)
        self.y += d_center * math.sin(self.theta + d_theta / 2.0)
        self.theta += d_theta
        self.total_distance += abs(d_center)

        self._publish(now, vx, vth)
        self.distance_pub.publish(Float32(data=self.total_distance))

    def _publish(self, now: rclpy.time.Time, vx: float, vth: float) -> None:
        q = self._q(self.theta)

        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.x = q[0]
        t.transform.rotation.y = q[1]
        t.transform.rotation.z = q[2]
        t.transform.rotation.w = q[3]
        self.tf_broadcaster.sendTransform(t)

        o = Odometry()
        o.header.stamp = now.to_msg()
        o.header.frame_id = 'odom'
        o.child_frame_id = 'base_link'
        o.pose.pose.position.x = self.x
        o.pose.pose.position.y = self.y
        o.pose.pose.orientation.x = q[0]
        o.pose.pose.orientation.y = q[1]
        o.pose.pose.orientation.z = q[2]
        o.pose.pose.orientation.w = q[3]
        o.twist.twist.linear.x = vx
        o.twist.twist.angular.z = vth
        o.pose.covariance[0] = 0.01
        o.pose.covariance[7] = 0.01
        o.pose.covariance[35] = 0.02
        o.twist.covariance[0] = 0.005
        o.twist.covariance[35] = 0.01
        self.odom_pub.publish(o)

    def publish_diagnostics(self) -> None:
        if self.update_count == 0:
            return
        s = self.slip_count / self.update_count * 100
        j = self.jump_count / self.update_count * 100
        e = self.read_error_count / self.update_count * 100
        msg = (
            f'Odom|N={self.update_count} '
            f'slip={self.slip_count}({s:.1f}%) '
            f'jump={self.jump_count}({j:.1f}%) '
            f'err={self.read_error_count}({e:.1f}%) '
            f'dist={self.total_distance:.2f}m '
            f'xy=({self.x:.2f},{self.y:.2f}) '
            f'yaw={math.degrees(self.theta):.1f}deg'
        )
        self.diag_pub.publish(String(data=msg))
        if s > 5.0:
            self.get_logger().error(f'打滑率 {s:.1f}% > 5%!')
        if e > 10.0:
            self.get_logger().error(f'编码器错误率 {e:.1f}% > 10%!')

    @staticmethod
    def _q(yaw: float) -> tuple[float, float, float, float]:
        return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))

    def destroy_node(self) -> None:
        self.left.disconnect()
        self.right.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(EncoderOdomNode())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
