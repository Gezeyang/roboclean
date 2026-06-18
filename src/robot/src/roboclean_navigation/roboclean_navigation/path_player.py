"""
路径回放节点 — 复现录制的路径

加载录制的路径文件 → Pure Pursuit 跟踪 → 发布 /cmd_vel

触发方式:
  - /bt/command: {"cmd":"manual_control","data":{"action":"playback_start","file":"path_xxx.json"}}
  - task_scheduler: /task/start → 自动加载最新路径

订阅: /odom (Odometry)  /bt/command (String)
发布: /cmd_vel (Twist)  /drum/run (Bool)  /path/status (String)
"""

import json
import math
import os

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String


class PathPlayer(Node):
    """路径回放器 — Pure Pursuit"""

    def __init__(self):
        super().__init__('path_player')

        self.declare_parameter('path_dir', os.path.expanduser('~/roboclean_paths'))
        self.declare_parameter('lookahead_distance', 0.8)  # 前视距离 (m)
        self.declare_parameter('max_speed', 0.25)  # 最大速度 (m/s)
        self.declare_parameter('goal_tolerance', 0.3)  # 终点容忍度 (m)
        self.declare_parameter('max_angular', 0.6)

        self._path_dir = self.get_parameter('path_dir').value
        self._lookahead = self.get_parameter('lookahead_distance').value
        self._max_speed = self.get_parameter('max_speed').value
        self._goal_tol = self.get_parameter('goal_tolerance').value
        self._max_ang = self.get_parameter('max_angular').value

        # 状态
        self._playing: bool = False
        self._paused: bool = False
        self._path: list[dict] = []
        self._current_idx: int = 0
        self._path_name: str = ''

        # 当前位置
        self._x: float = 0.0
        self._y: float = 0.0
        self._yaw: float = 0.0

        # 订阅
        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)
        self.create_subscription(String, '/bt/command', self._cmd_callback, 10)
        # 离线任务触发
        self.create_subscription(Bool, '/task/start', self._task_start_callback, 10)
        self.create_subscription(Bool, '/task/stop', self._task_stop_callback, 10)

        # 发布
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._drum_pub = self.create_publisher(Bool, '/drum/run', 10)
        self._status_pub = self.create_publisher(String, '/path/status', 10)

        # 控制循环 20Hz
        self._timer = self.create_timer(0.05, self._control_loop)

        self.get_logger().info(f'路径回放器已启动 | 前视={self._lookahead}m')

    # ── 订阅 ──

    def _odom_callback(self, msg: Odometry) -> None:
        self._x = msg.pose.pose.position.x
        self._y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self._yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )

    def _cmd_callback(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        cmd = data.get('cmd', '')
        ctrl = data.get('data', {})

        if cmd == 'manual_control':
            action = ctrl.get('action', '')
            if action == 'playback_start':
                filename = ctrl.get('file', '')
                self.start_playback(filename)
            elif action == 'playback_stop':
                self.stop_playback()
            elif action == 'playback_pause':
                self._paused = not self._paused

    def _task_start_callback(self, msg: Bool) -> None:
        if msg.data and not self._playing:
            # 自动加载最新路径文件
            latest = self._find_latest_path()
            if latest:
                self.start_playback(latest)
                self.get_logger().info(f'任务调度: 自动回放 {latest}')

    def _task_stop_callback(self, msg: Bool) -> None:
        if msg.data:
            self.stop_playback()

    # ── 路径管理 ──

    def _find_latest_path(self) -> str:
        """找到最新的路径文件"""
        try:
            files = [
                f
                for f in os.listdir(self._path_dir)
                if f.startswith('path_') and f.endswith('.json')
            ]
            if not files:
                return ''
            files.sort(reverse=True)
            return os.path.join(self._path_dir, files[0])
        except OSError:
            return ''

    def start_playback(self, filename: str) -> None:
        """加载并开始回放"""
        if not filename:
            return
        # 支持仅文件名 (相对于 path_dir)
        if not os.path.isabs(filename):
            filename = os.path.join(self._path_dir, filename)

        try:
            with open(filename, encoding='utf-8') as f:
                data = json.load(f)
            poses = [p for p in data['path'] if p['type'] == 'pose']
            if len(poses) < 2:
                self.get_logger().warn('路径点数不足')
                return
            self._path = poses
            self._current_idx = 0
            self._playing = True
            self._paused = False
            self._path_name = os.path.basename(filename)
            self._status_pub.publish(String(data=f'playing:{self._path_name}'))
            self.get_logger().info(f'▶ 开始回放: {self._path_name} ({len(poses)} 点)')
        except (OSError, json.JSONDecodeError, KeyError) as e:
            self.get_logger().error(f'加载失败: {e}')

    def stop_playback(self) -> None:
        self._playing = False
        self._paused = False
        self._path = []
        self._cmd_pub.publish(Twist())
        self._drum_pub.publish(Bool(data=False))
        self._status_pub.publish(String(data='stopped'))
        self.get_logger().info('⏹ 回放停止')

    # ── Pure Pursuit ──

    def _control_loop(self) -> None:
        if not self._playing or self._paused or len(self._path) < 2:
            return

        # 找前视目标点
        target = self._find_lookahead_point()
        if target is None:
            # 到达终点
            self.get_logger().info('到达路径终点')
            self.stop_playback()
            return

        tx, ty, brush = target

        # 目标在机器人坐标系下的位置
        dx = tx - self._x
        dy = ty - self._y
        # 转到机器人坐标系
        cos_yaw = math.cos(self._yaw)
        sin_yaw = math.sin(self._yaw)
        local_x = dx * cos_yaw + dy * sin_yaw
        local_y = -dx * sin_yaw + dy * cos_yaw

        # Pure Pursuit: 角速度 = 2 * v * lateral_error / L^2
        # lateral_error = local_y (横向偏差)
        ld = max(self._lookahead, math.sqrt(local_x**2 + local_y**2) + 0.1)
        angular = 2.0 * self._max_speed * local_y / (ld * ld)
        angular = max(-self._max_ang, min(self._max_ang, angular))

        # 接近终点时降速
        dist_to_end = math.sqrt(
            (self._path[-1]['x'] - self._x) ** 2 + (self._path[-1]['y'] - self._y) ** 2
        )
        speed = self._max_speed
        if dist_to_end < 1.0:
            speed = self._max_speed * max(0.2, dist_to_end)

        t = Twist()
        t.linear.x = speed
        t.angular.z = angular
        self._cmd_pub.publish(t)
        self._drum_pub.publish(Bool(data=brush))

    def _find_lookahead_point(self) -> tuple[float, float, bool] | None:
        """找前视距离外的最近路径点"""
        if self._current_idx >= len(self._path):
            return None

        best_idx = self._current_idx

        for i in range(self._current_idx, len(self._path)):
            p = self._path[i]
            d = math.sqrt((p['x'] - self._x) ** 2 + (p['y'] - self._y) ** 2)
            if d >= self._lookahead:
                best_idx = i
                break
            # 跟踪最近的已过点, 跳过
            self._current_idx = i

        # 如果所有剩余点都在前视距离内 → 取最后一个
        if best_idx == self._current_idx:
            p = self._path[-1]
            d = math.sqrt((p['x'] - self._x) ** 2 + (p['y'] - self._y) ** 2)
            if d < self._goal_tol:
                return None
            return float(p['x']), float(p['y']), bool(p.get('brush', False))

        p = self._path[best_idx]
        self._current_idx = best_idx
        return float(p['x']), float(p['y']), bool(p.get('brush', False))


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(PathPlayer())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
