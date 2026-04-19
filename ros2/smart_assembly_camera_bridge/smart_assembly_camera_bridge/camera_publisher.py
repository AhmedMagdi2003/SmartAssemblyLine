import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image


class CameraPublisher(Node):
    def __init__(self):
        super().__init__("smart_assembly_camera_publisher")

        self.declare_parameter("camera_device", 0)
        self.declare_parameter("width", 1280)
        self.declare_parameter("height", 720)
        self.declare_parameter("fps", 15.0)
        self.declare_parameter("frame_id", "smart_assembly_camera")
        self.declare_parameter("publish_raw", False)
        self.declare_parameter("publish_compressed", True)
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("topic_prefix", "/smart_assembly/camera")

        camera_device = int(self.get_parameter("camera_device").value)
        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)
        fps = float(self.get_parameter("fps").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.publish_raw_enabled = bool(self.get_parameter("publish_raw").value)
        self.publish_compressed_enabled = bool(self.get_parameter("publish_compressed").value)
        self.jpeg_quality = int(self.get_parameter("jpeg_quality").value)
        topic_prefix = str(self.get_parameter("topic_prefix").value).rstrip("/")

        self.bridge = CvBridge()
        self.capture = cv2.VideoCapture(camera_device)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.capture.set(cv2.CAP_PROP_FPS, fps)

        if not self.capture.isOpened():
            raise RuntimeError(f"Could not open camera device {camera_device}.")

        self.raw_publisher = None
        if self.publish_raw_enabled:
            self.raw_publisher = self.create_publisher(Image, f"{topic_prefix}/image_raw", 10)

        self.compressed_publisher = None
        if self.publish_compressed_enabled:
            self.compressed_publisher = self.create_publisher(
                CompressedImage,
                f"{topic_prefix}/image_compressed",
                10,
            )

        timer_period = 1.0 / max(fps, 1.0)
        self.timer = self.create_timer(timer_period, self.publish_frame)
        self.get_logger().info(
            f"Camera publisher started on device {camera_device} at {width}x{height} @{fps:.1f} FPS."
        )

    def publish_frame(self):
        ok, frame = self.capture.read()
        if not ok:
            self.get_logger().warning("Failed to read frame from camera.")
            return

        stamp = self.get_clock().now().to_msg()

        if self.raw_publisher is not None:
            image_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            image_msg.header.stamp = stamp
            image_msg.header.frame_id = self.frame_id
            self.raw_publisher.publish(image_msg)

        if self.compressed_publisher is not None:
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
            )
            if not ok:
                self.get_logger().warning("Failed to encode compressed frame.")
                return

            compressed_msg = CompressedImage()
            compressed_msg.header.stamp = stamp
            compressed_msg.header.frame_id = self.frame_id
            compressed_msg.format = "jpeg"
            compressed_msg.data = encoded.tobytes()
            self.compressed_publisher.publish(compressed_msg)

    def destroy_node(self):
        if self.capture is not None:
            self.capture.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
