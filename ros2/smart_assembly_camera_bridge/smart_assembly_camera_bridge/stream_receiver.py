import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image


class StreamReceiver(Node):
    def __init__(self):
        super().__init__("smart_assembly_stream_receiver")

        self.declare_parameter("prefer_compressed", True)
        self.declare_parameter("raw_topic", "/smart_assembly/camera/image_raw")
        self.declare_parameter("compressed_topic", "/smart_assembly/camera/image_compressed")
        self.declare_parameter("window_name", "Smart Assembly ROS Camera")

        self.bridge = CvBridge()
        self.window_name = str(self.get_parameter("window_name").value)
        prefer_compressed = bool(self.get_parameter("prefer_compressed").value)
        raw_topic = str(self.get_parameter("raw_topic").value)
        compressed_topic = str(self.get_parameter("compressed_topic").value)

        if prefer_compressed:
            self.subscription = self.create_subscription(
                CompressedImage,
                compressed_topic,
                self.handle_compressed_frame,
                10,
            )
            self.get_logger().info(f"Subscribed to compressed topic: {compressed_topic}")
        else:
            self.subscription = self.create_subscription(
                Image,
                raw_topic,
                self.handle_raw_frame,
                10,
            )
            self.get_logger().info(f"Subscribed to raw topic: {raw_topic}")

    def handle_raw_frame(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        self.show_frame(frame)

    def handle_compressed_frame(self, msg):
        np_buffer = np.frombuffer(msg.data, dtype=np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if frame is None:
            self.get_logger().warning("Failed to decode compressed frame.")
            return
        self.show_frame(frame)

    def show_frame(self, frame):
        cv2.imshow(self.window_name, frame)
        cv2.waitKey(1)

    def destroy_node(self):
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = StreamReceiver()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
