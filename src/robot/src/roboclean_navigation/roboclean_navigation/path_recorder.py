"""
路径录制节点 — 示教模式

工人在 App 上手动静音机器人走一圈 → 自动记录路径 → 之后复现

记录内容:
  - 里程计位置 (x, y, yaw) @ 10Hz
  - 动作事件 (刷子/速度)

订阅: /odom (Odometry)  /drum/run (Bool)
发布: /path/status (String)
"""

import json
import math
import os
import time
from datetime import datetime

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String


class PathRecorder(Node):
    """路径录制器"""

    def __init__(self):
        super().__init__('path_recorder')

        self.declare_parameter('path_dir', os.path.expanduser('~/roboclean_paths'))
        self._path_dir = self.get_parameter('path_dir').value
        os.makedirs(self._path_dir, exist_ok=True)

        # 录制状态
        self._recording: bool = False
        self._path: list[dict] = []  # [{x, y, yaw, t, brush, speed}, ...]
        self._start_time: float = 0.0
        self._last_sample_time: float = 0.0
        self._sample_interval: float = 0.1  # 10Hz

        # 当前状态
        self._current_x: float = 0.0
        self._current_y: float = 0.0
        self._current_yaw: float = 0.0
        self._brush_on: bool = False
        self._current_speed: float = 0.0

        # 订阅
        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)
        self.create_subscription(Bool, '/drum/run', self._brush_callback, 10)
        # 控制指令 (来自 App / bt_server)
        self.create_subscription(String, '/bt/command', self._cmd_callback, 10)

        # 发布
        self._status_pub = self.create_publisher(String, '/path/status', 10)

        # 定时器: 10Hz 采样
        self._timer = self.create_timer(self._sample_interval, self._sample)

        self.get_logger().info(f'路径录制器已启动 | 保存目录: {self._path_dir}')

    # ── 订阅 ──

    def _odom_callback(self, msg: Odometry) -> None:
        self._current_x = msg.pose.pose.position.x
        self._current_y = msg.pose.pose.position.y
        # yaw from quaternion
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self._current_yaw = math.atan2(siny, cosy)

    def _brush_callback(self, msg: Bool) -> None:
        if msg.data != self._brush_on:
            self._brush_on = msg.data
            if self._recording:
                self._path.append(
                    {
                        'type': 'action',
                        'action': 'brush',
                        'on': msg.data,
                        't': time.time() - self._start_time,
                    }
                )

    def _cmd_callback(self, msg: String) -> None:
        """App 控制指令"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        cmd = data.get('cmd', '')
        ctrl = data.get('data', {})

        if cmd == 'manual_control':
            action = ctrl.get('action', '')
            if action == 'record_start':
                self.start_recording(ctrl.get('name', '未命名'))
            elif action == 'record_stop':
                self.stop_recording()

    # ── 采样循环 ──

    def _sample(self) -> None:
        if not self._recording:
            return
        now = time.time()
        if now - self._last_sample_time < self._sample_interval:
            return
        self._last_sample_time = now

        self._path.append(
            {
                'type': 'pose',
                'x': round(self._current_x, 4),
                'y': round(self._current_y, 4),
                'yaw': round(self._current_yaw, 4),
                'brush': self._brush_on,
                't': round(now - self._start_time, 2),
            }
        )

    # ── 控制 ──

    def start_recording(self, name: str = '未命名') -> None:
        self._path = []
        self._start_time = time.time()
        self._last_sample_time = 0.0
        self._recording = True
        self._status_pub.publish(String(data=f'recording:{name}'))
        self.get_logger().info(f'🔴 开始录制: {name}')

    def stop_recording(self) -> str:
        self._recording = False
        duration = time.time() - self._start_time

        if len(self._path) < 10:
            self.get_logger().warn('录制点数太少, 丢弃')
            self._status_pub.publish(String(data='record_failed:too_short'))
            return ''

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(self._path_dir, f'path_{timestamp}.json')

        data = {
            'version': 1,
            'created': datetime.now().isoformat(),
            'duration_s': round(duration, 1),
            'points': len(self._path),
            'path': self._path,
        }
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.get_logger().info(
                f'⏹ 录制完成: {len(self._path)} 点, {duration:.1f}s → {filename}'
            )
            self._status_pub.publish(String(data=f'recorded:{filename}'))
            return filename
        except OSError as e:
            self.get_logger().error(f'保存失败: {e}')
            self._status_pub.publish(String(data='record_failed:io_error'))
            return ''

    def destroy_node(self) -> None:
        if self._recording:
            self.stop_recording()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(PathRecorder())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
