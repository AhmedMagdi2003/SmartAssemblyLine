from setuptools import find_packages, setup


package_name = "smart_assembly_camera_bridge"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", [
            "launch/pi_camera_bridge.launch.py",
            "launch/pc_stream_receiver.launch.py",
        ]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Smart Assembly Team",
    maintainer_email="you@example.com",
    description="ROS2 bridge package for Raspberry Pi camera streaming to the Smart Assembly Line PC.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "camera_publisher = smart_assembly_camera_bridge.camera_publisher:main",
            "stream_receiver = smart_assembly_camera_bridge.stream_receiver:main",
        ],
    },
)
