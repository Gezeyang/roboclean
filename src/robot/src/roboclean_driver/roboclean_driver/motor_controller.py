"""
电机控制 ROS 2 节点 — 精度增强版

物理依赖 (装车后必须核实):
  wheel_radius = 0.19m     ← 300-8 轮胎实际半径
  wheel_separation = 0.65m ← 左右轮距
  gear_ratio = 56.0        ← 减速比
  max_rpm = 1500           ← 安全转速上限 (取决于电机+驱动参数)
  cmd_timeout_s = 0.5      ← 指令超时自动停车

订阅: /cmd_vel (Twist)  /safety/stop (Bool)
发布: /motor/status  /battery/voltage  /diagnostics/motor
"""

from __future__ import annotations

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String

from .canopen_driver import DriveSystem


class MotorControllerNode(Node):
    """差速驱动控制节点（精度增强版）"""

    def __init__(self):
        super().__init__('motor_controller')

        # ── 参数 ──
        self.declare_parameter('can_channel', 'can0')
        self.declare_parameter('wheel_radius', 0.19)
        self.declare_parameter('wheel_separation', 0.65)
        self.declare_parameter('max_rpm', 1500)
        self.declare_parameter('gear_ratio', 56.0)
        self.declare_parameter('cmd_timeout_s', 0.5)  # 指令超时
        self.declare_parameter('rpm_deviation_warn_pct', 15.0)  # RPM 偏差告警阈值%

        can_ch = self.get_parameter('can_channel').value
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.wheel_sep = self.get_parameter('wheel_separation').value
        self.max_rpm = self.get_parameter('max_rpm').value
        self.gear_ratio = self.get_parameter('gear_ratio').value
        self.cmd_timeout = self.get_parameter('cmd_timeout_s').value
        self.rpm_warn_pct = self.get_parameter('rpm_deviation_warn_pct').value

        self.get_logger().info(f'CAN: {can_ch} | 超时={self.cmd_timeout}s')

        # ── 驱动 ──
        try:
            self.drives = DriveSystem(left_id=1, right_id=2, brush_id=3, channel=can_ch)
            self.drives.enter_operational_all()
            self.get_logger().info('三驱动器就绪')
        except Exception as e:
            self.get_logger().error(f'驱动初始化失败: {e}')
            self.drives = None

        # ── 指令追踪 ──
        self.cmd_left_rpm = 0
        self.cmd_right_rpm = 0
        self.last_cmd_time = time.time()
        self.last_cmd_stamp = self.get_clock().now()

        # ── 偏差统计 ──
        self.deviation_count = 0
        self.status_count = 0

        # ── 定时器 ──
        self.status_timer = self.create_timer(0.1, self.publish_status)  # 10Hz
        self.watchdog_timer = self.create_timer(
            self.cmd_timeout / 2.0, self.cmd_watchdog
        )  # 超时检测

        # ── 订阅 ──
        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.safety_sub = self.create_subscription(Bool, '/safety/stop', self.safety_callback, 10)

        # ── 发布 ──
        self.status_pub = self.create_publisher(String, '/motor/status', 10)
        self.voltage_pub = self.create_publisher(Float32, '/battery/voltage', 10)
        self.diag_pub = self.create_publisher(String, '/diagnostics/motor', 10)

        self.get_logger().info('电机控制节点已启动 (精度增强版)')

    # ═══════════════════════════════════════════════════════════
    # 速度指令
    # ═══════════════════════════════════════════════════════════

    def cmd_vel_callback(self, msg: Twist) -> None:
        if self.drives is None:
            return

        v = msg.linear.x
        w = msg.angular.z

        v_left = v - w * self.wheel_sep / 2.0
        v_right = v + w * self.wheel_sep / 2.0

        rpm_left = int(v_left / (2.0 * math.pi * self.wheel_radius) * 60.0 * self.gear_ratio)
        rpm_right = int(v_right / (2.0 * math.pi * self.wheel_radius) * 60.0 * self.gear_ratio)

        rpm_left = max(-self.max_rpm, min(self.max_rpm, rpm_left))
        rpm_right = max(-self.max_rpm, min(self.max_rpm, rpm_right))

        self.drives.set_wheel_speeds(rpm_left, rpm_right)

        self.cmd_left_rpm = rpm_left
        self.cmd_right_rpm = rpm_right
        self.last_cmd_time = time.time()
        self.last_cmd_stamp = self.get_clock().now()

    # ═══════════════════════════════════════════════════════════
    # 安全急停
    # ═══════════════════════════════════════════════════════════

    def safety_callback(self, msg: Bool) -> None:
        if msg.data and self.drives:
            self.get_logger().error('收到安全停止信号 → 紧急停止!')
            self.drives.emergency_stop()
            self.cmd_left_rpm = 0
            self.cmd_right_rpm = 0

    # ═══════════════════════════════════════════════════════════
    # 指令超时看门狗
    # ═══════════════════════════════════════════════════════════

    def cmd_watchdog(self) -> None:
        """检查是否超时未收到新指令"""
        if self.drives is None:
            return
        elapsed = time.time() - self.last_cmd_time
        if elapsed > self.cmd_timeout and (self.cmd_left_rpm != 0 or self.cmd_right_rpm != 0):
            self.get_logger().warn(f'[TIMEOUT] {elapsed:.2f}s 未收到指令 → 自动停车')
            self.drives.stop_all()
            self.cmd_left_rpm = 0
            self.cmd_right_rpm = 0

    # ═══════════════════════════════════════════════════════════
    # 状态 + RPM 反馈监控
    # ═══════════════════════════════════════════════════════════

    def publish_status(self) -> None:
        if self.drives is None:
            return
        self.status_count += 1

        try:
            s = self.drives.get_all_status()
            bus_v = s.get('bus_voltage', 0.0)
            self.voltage_pub.publish(Float32(data=bus_v))

            # ── RPM 反馈监控 ──
            # 从驱动器读取实际转速进行比较（实际寄存器映射需 EDS 确认）
            try:
                act_left = self.drives.left.get_actual_speed()
                act_right = self.drives.right.get_actual_speed()
            except Exception:
                act_left = self.cmd_left_rpm
                act_right = self.cmd_right_rpm

            # 计算偏差百分比
            dev_left = abs(act_left - self.cmd_left_rpm) / max(abs(self.cmd_left_rpm), 1.0) * 100
            dev_right = (
                abs(act_right - self.cmd_right_rpm) / max(abs(self.cmd_right_rpm), 1.0) * 100
            )
            max_dev = max(dev_left, dev_right)

            if max_dev > self.rpm_warn_pct and (self.cmd_left_rpm != 0 or self.cmd_right_rpm != 0):
                self.deviation_count += 1
                self.get_logger().warn(
                    f'[RPM-DEV] cmd=({self.cmd_left_rpm},{self.cmd_right_rpm}) '
                    f'act=({act_left},{act_right}) '
                    f'dev=({dev_left:.0f}%,{dev_right:.0f}%)'
                )

            # 状态消息
            elapsed = self.get_clock().now() - self.last_cmd_stamp
            age = elapsed.nanoseconds / 1e9
            status_str = (
                f"cmd=({self.cmd_left_rpm},{self.cmd_right_rpm})rpm "
                f"act=({act_left},{act_right})rpm "
                f"V={bus_v:.1f}V "
                f"IL={s.get('left_current',0):.1f}A "
                f"IR={s.get('right_current',0):.1f}A "
                f"age={age:.2f}s"
            )
            self.status_pub.publish(String(data=status_str))

            # 诊断 (每 10 次发一次，约 1Hz)
            if self.status_count % 10 == 0:
                dev_rate = self.deviation_count / self.status_count * 100
                diag = (
                    f"Motor|N={self.status_count} "
                    f"dev={self.deviation_count}({dev_rate:.1f}%) "
                    f"V={bus_v:.1f}V "
                    f"PL={s.get('left_temp',0)}C "
                    f"PR={s.get('right_temp',0)}C"
                )
                self.diag_pub.publish(String(data=diag))

        except Exception as e:
            self.get_logger().warn(f'状态异常: {e}')

    def destroy_node(self) -> None:
        if self.drives:
            self.drives.emergency_stop()
            self.drives.shutdown()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
