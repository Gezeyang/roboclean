"""
导航启动文件 — SLAM + Nav2 + 途经点 + 回充
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
import os


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.realpath(__file__))

    # ── SLAM ──
    slam = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[os.path.join(pkg_dir, '..', 'config', 'slam_params.yaml')],
    )

    # ── Nav2 (需要 nav2_bringup 包) ──
    # 注: 需要先安装: sudo apt install ros-humble-nav2-bringup
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_dir, '..', '..', '..', '..', '..',
                         'opt', 'ros', 'humble', 'share', 'nav2_bringup',
                         'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'params_file': os.path.join(pkg_dir, '..', 'config', 'nav2_params.yaml'),
            'use_sim_time': 'false',
        }.items(),
    )

    # ── 围栏跟随 (推料核心) ──
    fence_follower = Node(
        package='roboclean_navigation',
        executable='fence_follower',
        name='fence_follower',
        output='screen',
        parameters=[{
            'fence_side': 'left',
            'target_distance': 0.50,
            'forward_speed': 0.25,
            'drum_rpm': 800,
        }],
    )

    # ── 途经点导航 (备用，App 路线模式) ──
    waypoint_nav = Node(
        package='roboclean_navigation',
        executable='waypoint_navigator',
        name='waypoint_navigator',
        output='screen',
    )

    # ── 回充控制器 ──
    charging = Node(
        package='roboclean_navigation',
        executable='charging_dock',
        name='charging_dock',
        output='screen',
        parameters=[{
            'dock_x': 0.0,
            'dock_y': 0.0,
            'dock_yaw': 0.0,
            'low_battery_v': 44.0,
        }],
    )

    # ── 镭神 N10P 驱动 (串口版) ──
    n10p = Node(
        package='lslidar_driver',
        executable='lslidar_driver_node',
        name='lslidar',
        output='screen',
        parameters=[{
            'serial_port': '/dev/ttyUSB0',
            'serial_baudrate': 460800,
            'frame_id': 'laser_frame',
            'lidar_type': 'n10p',
            'add_multicast': False,
        }],
    )

    return LaunchDescription([
        slam,
        # nav2,  # 取消注释需先安装 nav2_bringup
        waypoint_nav,
        charging,
        n10p,
    ])
