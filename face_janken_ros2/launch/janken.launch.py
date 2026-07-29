"""表情じゃんけん一式を起動する launch ファイル。

usb_cam_node → mediapipe_face_node → janken_node をまとめて立ち上げる。

例:
    ros2 launch janken_expression janken.launch.py \\
        video_device:=/dev/video0 pixel_format:=yuyv2rgb
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory('janken_expression')
    default_model = os.path.join(pkg_share, 'models', 'face_landmarker.task')
    default_calib = os.path.expanduser('~/.config/janken/calibration.yaml')

    video_device = LaunchConfiguration('video_device')
    pixel_format = LaunchConfiguration('pixel_format')
    image_topic = LaunchConfiguration('image_topic')
    model_path = LaunchConfiguration('model_path')
    calibration_file = LaunchConfiguration('calibration_file')
    round_interval = LaunchConfiguration('round_interval_sec')
    publish_debug = LaunchConfiguration('publish_debug_image')

    args = [
        DeclareLaunchArgument('video_device', default_value='/dev/video0',
                              description='使用するカメラデバイス'),
        DeclareLaunchArgument('pixel_format', default_value='yuyv2rgb',
                              description='usb_cam のピクセルフォーマット '
                                          '(yuyv2rgb / mjpeg2rgb など)'),
        DeclareLaunchArgument('image_topic', default_value='/image_raw',
                              description='カメラ画像トピック'),
        DeclareLaunchArgument('model_path', default_value=default_model,
                              description='face_landmarker.task のパス'),
        DeclareLaunchArgument('calibration_file', default_value=default_calib,
                              description='表情校正ファイル(YAML)。無ければ'
                                          'ルール方式にフォールバック'),
        DeclareLaunchArgument('round_interval_sec', default_value='6.0',
                              description='1ラウンドの間隔（秒）'),
        DeclareLaunchArgument('publish_debug_image', default_value='true',
                              description='デバッグ画像をpublishするか'),
    ]

    usb_cam = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam_node',
        parameters=[{
            'video_device': video_device,
            'pixel_format': pixel_format,
            'image_width': 640,
            'image_height': 480,
            'framerate': 30.0,
            'camera_frame_id': 'usb_cam',
        }],
        output='screen',
    )

    face = Node(
        package='janken_expression',
        executable='mediapipe_face_node',
        name='mediapipe_face_node',
        parameters=[{
            'model_path': model_path,
            'image_topic': image_topic,
            'hand_topic': '/janken/hand',
            'calibration_file': calibration_file,
            'match_threshold': 0.0,
            'jaw_open_threshold': 0.4,
            'smile_threshold': 0.4,
            'publish_debug_image': ParameterValue(publish_debug,
                                                  value_type=bool),
        }],
        output='screen',
    )

    janken = Node(
        package='janken_expression',
        executable='janken_node',
        name='janken_node',
        parameters=[{
            'hand_topic': '/janken/hand',
            'result_topic': '/janken/result',
            'round_interval_sec': ParameterValue(round_interval,
                                                 value_type=float),
        }],
        output='screen',
    )

    return LaunchDescription(args + [usb_cam, face, janken])
