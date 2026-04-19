from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("camera_device", default_value="0"),
        DeclareLaunchArgument("width", default_value="1280"),
        DeclareLaunchArgument("height", default_value="720"),
        DeclareLaunchArgument("fps", default_value="15.0"),
        DeclareLaunchArgument("publish_raw", default_value="false"),
        DeclareLaunchArgument("publish_compressed", default_value="true"),
        DeclareLaunchArgument("jpeg_quality", default_value="80"),
        Node(
            package="smart_assembly_camera_bridge",
            executable="camera_publisher",
            name="smart_assembly_camera_publisher",
            output="screen",
            parameters=[{
                "camera_device": LaunchConfiguration("camera_device"),
                "width": LaunchConfiguration("width"),
                "height": LaunchConfiguration("height"),
                "fps": LaunchConfiguration("fps"),
                "publish_raw": LaunchConfiguration("publish_raw"),
                "publish_compressed": LaunchConfiguration("publish_compressed"),
                "jpeg_quality": LaunchConfiguration("jpeg_quality"),
            }],
        ),
    ])
