"""
途经点导航节点

接收途经点列表 → 依次导航 → 完成后触发清洁

订阅: /route/waypoints (String, JSON格式)
发布: /cmd_vel (通过 Nav2 NavigateToPose action)
       /nav/active (Bool) — 导航中时 True, fence_follower 收到后停止
       /brush/run (Bool) — 导航期间启动清洁刷
"""

import json
import math
from typing import Any
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Point, Quaternion
from std_msgs.msg import String, Bool


class WaypointNavigator(Node):
    """途经点序列导航节点"""

    def __init__(self):
        super().__init__('waypoint_navigator')

        # Nav2 导航客户端
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # 途经点
        self.waypoints: list[dict[str, Any]] = []
        self.current_index: int = 0
        self.navigating: bool = False

        # 订阅途经点列表
        self.create_subscription(String, '/route/waypoints', self.waypoints_callback, 10)

        # 发布清洁刷控制
        self.brush_pub = self.create_publisher(Bool, '/brush/run', 10)

        # 发布导航状态 (用于 cmd_vel 仲裁)
        self.nav_active_pub = self.create_publisher(Bool, '/nav/active', 10)

        # 状态发布
        self.status_pub = self.create_publisher(String, '/route/status', 10)

        self.get_logger().info('途经点导航节点已启动')

    def waypoints_callback(self, msg: String) -> None:
        """接收 App 发来的途经点列表 (JSON)"""
        try:
            data = json.loads(msg.data)
            self.waypoints = data.get('waypoints', [])
            self.get_logger().info(f'收到 {len(self.waypoints)} 个途经点')
            self.current_index = 0
            self.navigate_next()
        except json.JSONDecodeError:
            self.get_logger().error(f'JSON 解析失败: {msg.data}')

    def _set_nav_active(self, active: bool) -> None:
        """设置导航活动状态 → fence_follower 据此决定是否暂停"""
        self.navigating = active
        self.nav_active_pub.publish(Bool(data=active))

    def navigate_next(self) -> None:
        """导航到下一个途经点"""
        if self.current_index >= len(self.waypoints):
            self.get_logger().info('所有途经点已完成')
            self.brush_pub.publish(Bool(data=False))
            self._set_nav_active(False)
            self.status_pub.publish(String(data='all_done'))
            return

        wp = self.waypoints[self.current_index]
        self.get_logger().info(
            f'导航到 [{self.current_index + 1}/{len(self.waypoints)}]: '
            f'{wp.get("name", "?")}')

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(wp['x'])
        goal.pose.pose.position.y = float(wp['y'])
        q = self._yaw_to_quaternion(float(wp.get('yaw', 0.0)))
        goal.pose.pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])

        self.nav_client.wait_for_server()
        send_goal_future = self.nav_client.send_goal_async(
            goal, feedback_callback=self.feedback_callback)
        send_goal_future.add_done_callback(self.goal_response_callback)

        # 启动清洁刷 + 标记导航活动
        self.brush_pub.publish(Bool(data=True))
        self._set_nav_active(True)

    def goal_response_callback(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('导航目标被拒绝，跳过')
            self.current_index += 1
            self.navigate_next()
            return
        self.get_logger().info('导航目标已接受')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future) -> None:
        result = future.result().result
        self.get_logger().info(f'到达途经点 [{self.current_index + 1}]')
        self.status_pub.publish(String(data=f'arrived:{self.current_index}'))

        # 短暂停留后去下一个
        self.current_index += 1
        self.create_timer(2.0, lambda: self.navigate_next())

    def feedback_callback(self, feedback_msg) -> None:
        dist = feedback_msg.feedback.distance_remaining
        self.status_pub.publish(String(data=f'navigating:{dist:.1f}m'))

    @staticmethod
    def _yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
        return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(WaypointNavigator())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
