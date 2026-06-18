from setuptools import find_packages, setup

package_name = 'roboclean_bt'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'pybluez'],
    zip_safe=True,
    maintainer='RoboClean Dev',
    maintainer_email='user@roboclean.local',
    description='Bluetooth SPP server',
    license='MIT',
    entry_points={
        'console_scripts': [
            'bt_server = roboclean_bt.bt_server:main',
        ],
    },
)
