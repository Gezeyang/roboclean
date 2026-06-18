import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'roboclean_navigation'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='RoboClean Dev',
    maintainer_email='user@roboclean.local',
    description='Navigation and SLAM for RoboClean',
    license='MIT',
    entry_points={
        'console_scripts': [
            'fence_follower = roboclean_navigation.fence_follower:main',
            'waypoint_navigator = roboclean_navigation.waypoint_navigator:main',
            'charging_dock = roboclean_navigation.charging_dock:main',
        ],
    },
)
