from setuptools import find_packages, setup

package_name = 'roboclean_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'python-can', 'canopen'],
    zip_safe=True,
    maintainer='RoboClean Dev',
    maintainer_email='user@roboclean.local',
    description='CANopen motor driver for ZBLD.C20-800LRC',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'motor_controller = roboclean_driver.motor_controller:main',
            'encoder_odom = roboclean_driver.encoder_odom:main',
        ],
    },
)
