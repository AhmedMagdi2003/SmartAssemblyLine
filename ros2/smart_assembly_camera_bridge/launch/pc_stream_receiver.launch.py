from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("prefer_compressed", default_value="true"),
        DeclareLaunchArgument("raw_topic", default_value="/smart_assembly/camera/image_raw"),
        DeclareLaunchArgument("compressed_topic", default_value="/smart_assembly/camera/image_compressed"),
        Node(
            package="smart_assembly_camera_bridge",
            executable="stream_receiver",
            name="smart_assembly_stream_receiver",
            output="screen",
            parameters=[{
                "prefer_compressed": LaunchConfiguration("prefer_compressed"),
                "raw_topic": LaunchConfiguration("raw_topic"),
                "compressed_topic": LaunchConfiguration("compressed_topic"),
            }],
        ),
    ])
