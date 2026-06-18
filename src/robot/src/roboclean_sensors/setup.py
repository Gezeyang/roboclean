from setuptools import find_packages, setup

package_name = 'roboclean_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='RoboClean Dev',
    maintainer_email='user@roboclean.local',
    description='Safety sensors for RoboClean',
    license='MIT',
    entry_points={
        'console_scripts': [
            'safety_sensor = roboclean_sensors.safety_sensor:main',
        ],
    },
)
