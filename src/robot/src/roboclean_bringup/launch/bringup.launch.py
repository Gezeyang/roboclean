"""
RoboClean 主启动文件 — 全节点启动

启动所有核心节点:
  - CANopen 电机控制 + 编码器里程计
  - 安全传感器
  - 围栏跟随 (推料核心)
  - 途经点导航 (App 路线模式)
  - 自动回充
  - 蓝牙通信服务
  - 镭神 N10P LiDAR
  - SLAM (slam_toolbox)
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(pkg_dir, '..', 'config')

    # ── 启动参数 ──
    can_channel_arg = DeclareLaunchArgument(
        'can_channel', default_value='can0', description='CAN 接口名称'
    )
    use_hardware_arg = DeclareLaunchArgument(
        'use_hardware', default_value='false', description='启用真实硬件 (GPIO / CAN / 蓝牙)'
    )

    can_channel = LaunchConfiguration('can_channel')
    use_hardware = LaunchConfiguration('use_hardware')

    # ── 电机控制 ──
    motor_controller = Node(
        package='roboclean_driver',
        executable='motor_controller',
        name='motor_controller',
        output='screen',
        parameters=[
            os.path.join(config_dir, 'robot_params.yaml'),
            {
                'can_channel': can_channel,
            },
        ],
    )

    # ── 编码器里程计 ──
    encoder_odom = Node(
        package='roboclean_driver',
        executable='encoder_odom',
        name='encoder_odom',
        output='screen',
        parameters=[
            os.path.join(config_dir, 'robot_params.yaml'),
            {
                'can_channel': can_channel,
            },
        ],
    )

    # ── 安全传感器 ──
    safety_sensor = Node(
        package='roboclean_sensors',
        executable='safety_sensor',
        name='safety_sensor',
        output='screen',
        parameters=[
            {
                'use_hardware': use_hardware,
            }
        ],
    )

    # ── 围栏跟随 (推料核心) ──
    fence_follower = Node(
        package='roboclean_navigation',
        executable='fence_follower',
        name='fence_follower',
        output='screen',
        parameters=[
            os.path.join(
                config_dir, '..', '..', 'roboclean_navigation', 'config', 'nav2_params.yaml'
            ),
            os.path.join(config_dir, 'robot_params.yaml'),
        ],
    )

    # ── 途经点导航 (App 路线模式) ──
    waypoint_navigator = Node(
        package='roboclean_navigation',
        executable='waypoint_navigator',
        name='waypoint_navigator',
        output='screen',
    )

    # ── 自动回充 ──
    charging_dock = Node(
        package='roboclean_navigation',
        executable='charging_dock',
        name='charging_dock',
        output='screen',
        parameters=[os.path.join(config_dir, 'robot_params.yaml')],
    )

    # ── 蓝牙 SPP 服务 ──
    bt_server = Node(
        package='roboclean_bt',
        executable='bt_server',
        name='bt_server',
        output='screen',
        parameters=[
            {
                'bt_name': 'RoboClean-001',
            }
        ],
    )

    # ── 镭神 N10P LiDAR ──
    n10p_lidar = Node(
        package='lslidar_driver',
        executable='lslidar_driver_node',
        name='lslidar',
        output='screen',
        parameters=[
            {
                'serial_port': '/dev/ttyUSB0',
                'serial_baudrate': 460800,
                'frame_id': 'laser_frame',
                'lidar_type': 'n10p',
                'add_multicast': False,
            }
        ],
    )

    return LaunchDescription(
        [
            can_channel_arg,
            use_hardware_arg,
            motor_controller,
            encoder_odom,
            safety_sensor,
            fence_follower,
            waypoint_navigator,
            charging_dock,
            bt_server,
            n10p_lidar,
        ]
    )
