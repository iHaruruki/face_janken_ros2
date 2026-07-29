#!/usr/bin/env python3
"""表情を認識してじゃんけんの手をpublishするノード。

/image_raw (sensor_msgs/Image) を購読し、MediaPipe Face Landmarker で
顔の blendshape を取得して、表情をじゃんけんの手（グー/チョキ/パー）に
変換し /janken/hand (janken_interfaces/Hand) にpublishする。

判定方式は2つ:
  1. キャリブレーション方式（推奨）
     calibration_file に登録済みテンプレートがあれば、現在の表情を
     各テンプレート（gu/choki/pa）と比較し、最も近いものを手とする。
  2. ルール方式（フォールバック）
     校正ファイルが無い場合は blendshape のしきい値で判定する。
       パー(pa)=jawOpen / チョキ(choki)=mouthSmile / グー(gu)=無表情

キャリブレーション用に blendshape ベクトルを /janken/blendshapes へ常時publishする。
校正ファイルを更新したら ~/reload_calibration サービスで再読み込みできる。
"""
import os

import cv2
import numpy as np
import yaml
import rclpy
from rclpy.node import Node

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_srvs.srv import Trigger

from janken_interfaces.msg import Hand, Blendshapes

HANDS = ('gu', 'choki', 'pa')


class MediapipeFaceNode(Node):
    def __init__(self):
        super().__init__('mediapipe_face_node')

        # --- パラメータ ---
        self.declare_parameter('model_path', '')
        self.declare_parameter('image_topic', '/image_raw')
        self.declare_parameter('hand_topic', '/janken/hand')
        self.declare_parameter('blendshapes_topic', '/janken/blendshapes')
        self.declare_parameter('calibration_file', '')
        self.declare_parameter('match_threshold', 0.0)   # 0 なら距離での棄却なし
        self.declare_parameter('jaw_open_threshold', 0.4)
        self.declare_parameter('smile_threshold', 0.4)
        self.declare_parameter('publish_debug_image', True)
        self.declare_parameter('debug_image_topic', '/janken/debug_image')

        model_path = self.get_parameter('model_path').value
        image_topic = self.get_parameter('image_topic').value
        hand_topic = self.get_parameter('hand_topic').value
        bs_topic = self.get_parameter('blendshapes_topic').value
        self.calibration_file = os.path.expanduser(
            self.get_parameter('calibration_file').value or '')
        self.match_threshold = float(self.get_parameter('match_threshold').value)
        self.jaw_th = float(self.get_parameter('jaw_open_threshold').value)
        self.smile_th = float(self.get_parameter('smile_threshold').value)
        self.publish_debug = bool(self.get_parameter('publish_debug_image').value)
        debug_topic = self.get_parameter('debug_image_topic').value

        if not model_path or not os.path.isfile(model_path):
            self.get_logger().error(
                f'FaceLandmarker のモデルが見つかりません: "{model_path}"\n'
                '  scripts/download_model.sh を実行するか、'
                'model_path パラメータで .task ファイルのパスを指定してください。')
            raise FileNotFoundError(model_path)

        # --- MediaPipe FaceLandmarker の初期化 ---
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            running_mode=mp_vision.RunningMode.IMAGE,
        )
        self.landmarker = mp_vision.FaceLandmarker.create_from_options(options)

        self.bridge = CvBridge()

        # --- キャリブレーション読み込み ---
        self._calib = {}          # {label: {name: score}}
        self._calib_names = []    # 特徴として使う blendshape 名（ソート済み）
        self._load_calibration(log=True)

        # --- pub/sub/service ---
        self.hand_pub = self.create_publisher(Hand, hand_topic, 10)
        self.bs_pub = self.create_publisher(Blendshapes, bs_topic, 10)
        self.debug_pub = (
            self.create_publisher(Image, debug_topic, 10)
            if self.publish_debug else None)
        self.sub = self.create_subscription(
            Image, image_topic, self.image_callback, 10)
        self.reload_srv = self.create_service(
            Trigger, '~/reload_calibration', self._on_reload)

        self._last_hand = None
        self.get_logger().info(
            f'mediapipe_face_node 起動: "{image_topic}" を購読し '
            f'"{hand_topic}" に手をpublishします。 '
            f'判定方式: {"キャリブレーション" if self._calib else "ルール"}')

    # ------------------------------------------------------------------
    # キャリブレーション
    # ------------------------------------------------------------------
    def _load_calibration(self, log=False):
        path = self.calibration_file
        if not path or not os.path.isfile(path):
            self._calib = {}
            self._calib_names = []
            if log:
                self.get_logger().info(
                    '校正ファイルが無いためルール方式で判定します。'
                    '（calibration_node で登録できます）')
            return False
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            labels = data.get('labels', {})
            calib = {k: v for k, v in labels.items() if k in HANDS and v}
            names = set()
            for v in calib.values():
                names.update(v.keys())
            self._calib = calib
            self._calib_names = sorted(names)
            missing = [h for h in HANDS if h not in calib]
            if log:
                self.get_logger().info(
                    f'校正ファイルを読み込みました: {path} '
                    f'(登録済み: {list(calib.keys())})')
                if missing:
                    self.get_logger().warn(f'未登録の手があります: {missing}')
            return True
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'校正ファイルの読み込みに失敗: {exc}')
            return False

    def _on_reload(self, request, response):
        ok = self._load_calibration(log=True)
        response.success = ok
        response.message = (
            f'再読み込み完了: {list(self._calib.keys())}' if ok
            else '校正ファイルが読み込めませんでした（ルール方式のまま）')
        return response

    # ------------------------------------------------------------------
    # 画像コールバック
    # ------------------------------------------------------------------
    def image_callback(self, msg: Image):
        try:
            rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f'画像の変換に失敗しました: {exc}')
            return

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                            data=np.ascontiguousarray(rgb))
        result = self.landmarker.detect(mp_image)

        scores = self._blendshape_dict(result)

        # blendshape をそのままpublish（キャリブレーション用）
        if scores:
            bs = Blendshapes()
            bs.header = msg.header
            bs.names = list(scores.keys())
            bs.scores = [float(scores[n]) for n in bs.names]
            self.bs_pub.publish(bs)

        hand, conf = self._classify(scores)

        out = Hand()
        out.header = msg.header
        out.hand = hand
        out.confidence = float(conf)
        self.hand_pub.publish(out)

        if hand != self._last_hand:
            self.get_logger().info(f'手を検出: {hand} (conf={conf:.2f})')
            self._last_hand = hand

        if self.debug_pub is not None:
            self._publish_debug(rgb, msg.header, hand, conf, scores)

    @staticmethod
    def _blendshape_dict(result):
        if not result.face_blendshapes:
            return {}
        return {c.category_name: c.score for c in result.face_blendshapes[0]}

    # ------------------------------------------------------------------
    # 判定
    # ------------------------------------------------------------------
    def _classify(self, scores):
        if not scores:
            return 'none', 0.0
        if self._calib:
            return self._classify_calibrated(scores)
        return self._classify_rule(scores)

    def _classify_calibrated(self, scores):
        """登録テンプレートへの最近傍で判定する。"""
        vec = np.array([scores.get(n, 0.0) for n in self._calib_names])
        dists = []
        for label, ref in self._calib.items():
            rvec = np.array([ref.get(n, 0.0) for n in self._calib_names])
            dists.append((label, float(np.linalg.norm(vec - rvec))))
        dists.sort(key=lambda kv: kv[1])

        best_label, best_d = dists[0]
        second_d = dists[1][1] if len(dists) > 1 else best_d + 1.0

        if self.match_threshold > 0.0 and best_d > self.match_threshold:
            return 'none', 0.0

        denom = best_d + second_d
        conf = 1.0 if denom == 0.0 else (second_d / denom)  # 差が大きいほど高い
        return best_label, conf

    def _classify_rule(self, scores):
        """blendshape のしきい値で判定する（フォールバック）。"""
        jaw = scores.get('jawOpen', 0.0)
        smile = 0.5 * (scores.get('mouthSmileLeft', 0.0) +
                       scores.get('mouthSmileRight', 0.0))
        if jaw >= self.jaw_th and jaw >= smile:
            return 'pa', jaw
        if smile >= self.smile_th:
            return 'choki', smile
        return 'gu', max(0.0, 1.0 - max(jaw, smile))

    # ------------------------------------------------------------------
    # デバッグ描画
    # ------------------------------------------------------------------
    def _publish_debug(self, rgb, header, hand, conf, scores):
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        mode = 'CALIB' if self._calib else 'RULE'
        label = {'gu': 'GU', 'choki': 'CHOKI',
                 'pa': 'PA', 'none': 'NONE'}.get(hand, hand)
        cv2.putText(bgr, f'[{mode}] {label} ({conf:.2f})', (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
        y = 78
        for key in ('jawOpen', 'mouthSmileLeft', 'mouthSmileRight'):
            cv2.putText(bgr, f'{key}: {scores.get(key, 0.0):.2f}', (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1,
                        cv2.LINE_AA)
            y += 22
        debug_msg = self.bridge.cv2_to_imgmsg(bgr, encoding='bgr8')
        debug_msg.header = header
        self.debug_pub.publish(debug_msg)


def main(args=None):
    rclpy.init(args=args)
    node = MediapipeFaceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
