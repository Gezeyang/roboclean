"""
充电桩回充节点

物理依赖 (装车后必须核实):
  dock_x / dock_y           ← 充电桩在地图上的坐标 (建图后标定!)
  dock_yaw                  ← 充电桩朝向
  low_battery_v = 44.0V     ← 低电量阈值 (48V 系统)
  充电触点位置 (车尾)       ← 泊入方向与触点对接
  反光标记位置 (充电桩)     ← LiDAR 检测反光标记定位

⚠️ 最后阶段待办:
  - LiDAR 反光标记检测 (当前为简化版直线倒车)
  - 接触器/电流检测确认物理对接
  - 泊入路径规划 (非直线场景)
"""

import math

import rclpy
from geometry_msgs.msg import PoseStamped, Quaternion, Twist
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Float32, String


class ChargingDockController(Node):
    """自动回充控制器"""

    def __init__(self):
        super().__init__('charging_dock')

        # 参数
        self.declare_parameter('dock_x', 0.0)
        self.declare_parameter('dock_y', 0.0)
        self.declare_parameter('dock_yaw', 0.0)
        self.declare_parameter('low_battery_v', 44.0)
        self.declare_parameter('critical_battery_v', 42.0)
        self.declare_parameter('approach_distance', 1.0)
        self.declare_parameter('dock_speed', 0.08)
        self.declare_parameter('full_charge_v', 54.0)

        self.dock_x = self.get_parameter('dock_x').value
        self.dock_y = self.get_parameter('dock_y').value
        self.dock_yaw = self.get_parameter('dock_yaw').value
        self.low_v = self.get_parameter('low_battery_v').value
        self.critical_v = self.get_parameter('critical_battery_v').value
        self.approach_dist = self.get_parameter('approach_distance').value
        self.dock_speed = self.get_parameter('dock_speed').value
        self.full_v = self.get_parameter('full_charge_v').value

        # 状态机
        self.state: str = 'IDLE'  # IDLE → NAVIGATING → APPROACHING → DOCKING → CHARGING
        self.battery_voltage: float = self.full_v

        # Nav2 客户端
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # 预连接 Nav2 (避免在回调中阻塞)
        self._nav_ready: bool = False
        self._nav_connect_timer = self.create_timer(1.0, self._try_connect_nav)

        # 发布
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/charging/status', 10)

        # 订阅电池电压 + App 指令
        self.create_subscription(Float32, '/battery/voltage', self.battery_callback, 10)
        self.create_subscription(String, '/bt/command', self._on_bt_command, 10)

        # 定时器 (10Hz)
        self.timer = self.create_timer(0.1, self.state_machine)

        self.get_logger().info(
            f'回充控制器已启动 | 充电桩: ({self.dock_x},{self.dock_y}) '
            f'| 低电阈值: {self.low_v}V | 充满阈值: {self.full_v}V'
        )

    def _try_connect_nav(self) -> None:
        """尝试连接 Nav2 action server (非阻塞)"""
        if self._nav_ready:
            return
        if self.nav_client.server_is_ready():
            self._nav_ready = True
            self.get_logger().info('Nav2 已就绪')
            self._nav_connect_timer.cancel()
        else:
            self.get_logger().debug('等待 Nav2...')

    def battery_callback(self, msg: Float32) -> None:
        self.battery_voltage = msg.data

    def _on_bt_command(self, msg: String) -> None:
        """App 远程设置充电桩位置"""
        import json

        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        if data.get('cmd') == 'set_dock':
            pos = data.get('data', {})
            self.dock_x = float(pos.get('x', self.dock_x))
            self.dock_y = float(pos.get('y', self.dock_y))
            self.dock_yaw = float(pos.get('yaw', self.dock_yaw))
            self.get_logger().info(
                f'充电桩位置更新: ({self.dock_x:.2f}, {self.dock_y:.2f}), '
                f'yaw={math.degrees(self.dock_yaw):.1f}°'
            )

    def state_machine(self) -> None:
        v = self.battery_voltage

        if self.state == 'IDLE':
            if v < self.low_v:
                self.get_logger().warn(f'低电量 {v:.1f}V < {self.low_v}V → 触发回充')
                self.state = 'NAVIGATING'
                self._navigate_to_dock()

        elif self.state == 'NAVIGATING':
            pass  # 等待导航完成 (回调中切换状态)

        elif self.state == 'APPROACHING':
            self._dock_approach()

        elif self.state == 'DOCKING':
            self.cmd_vel_pub.publish(Twist())  # 停车
            self.status_pub.publish(String(data='docked'))
            self.get_logger().info('已泊入充电桩，开始充电')
            self.state = 'CHARGING'

        elif self.state == 'CHARGING':
            if v > self.full_v:
                self.get_logger().info('充电完成')
                self.state = 'IDLE'
                self.status_pub.publish(String(data='charged'))

    def _navigate_to_dock(self) -> None:
        """导航到充电桩附近"""
        if not self._nav_ready:
            self.get_logger().warn('Nav2 未就绪，等待中...')
            self.state = 'NAVIGATING'  # 保持重试
            return

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        # 导航到充电桩前方 1m (approach_distance)
        goal.pose.pose.position.x = self.dock_x - self.approach_dist * math.cos(self.dock_yaw)
        goal.pose.pose.position.y = self.dock_y - self.approach_dist * math.sin(self.dock_yaw)
        q = self._yaw_to_q(self.dock_yaw)
        goal.pose.pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])

        self.status_pub.publish(String(data='navigating_to_dock'))
        self.get_logger().info(f'导航到充电桩附近 ({self.approach_dist}m)...')

        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(self._dock_nav_done)

    def _dock_nav_done(self, future) -> None:
        goal_handle = future.result()
        if goal_handle is not None and goal_handle.accepted:
            goal_handle.get_result_async().add_done_callback(self._dock_nav_result)
        else:
            self.get_logger().error('导航目标被拒绝')
            self.state = 'IDLE'

    def _dock_nav_result(self, future) -> None:
        self.state = 'APPROACHING'
        self.get_logger().info('到达充电桩附近 → 精确定位阶段')

    def _dock_approach(self) -> None:
        """
        激光反光标记精确定位 + 倒车泊入

        ⚠️ 最后阶段: 当前为简化版直线倒车。
        实际需要:
          1. 订阅 /scan，检测反光标记 (3M 钻石级)
          2. 根据反光标记位置修正横向偏差
          3. GPIO 检测充电触点接触 → 切换 DOCKING
        """
        # TODO(2026-06-18): 集成 LiDAR 反光标记检测 — 最后阶段
        t = Twist()
        t.linear.x = self.dock_speed
        self.cmd_vel_pub.publish(t)

    @staticmethod
    def _yaw_to_q(yaw: float) -> tuple[float, float, float, float]:
        return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(ChargingDockController())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
