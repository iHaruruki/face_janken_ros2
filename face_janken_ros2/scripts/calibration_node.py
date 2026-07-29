#!/usr/bin/env python3
"""じゃんけんの手（グー/チョキ/パー）に対応する表情を登録するノード。

/janken/blendshapes (janken_interfaces/Blendshapes) を購読し、各手について
対話的に表情を撮影→平均ベクトルを算出して YAML に保存する。
保存後、mediapipe_face_node の ~/reload_calibration サービスを呼んで
再読み込みさせる（reload_after_save が true のとき）。

前提: usb_cam と mediapipe_face_node が起動していること（blendshapes が流れる）。

使い方（別ターミナルで）:
    ros2 run janken_expression calibration_node
画面の指示に従って各表情を作り Enter を押す。
"""
import os
import time

import yaml
from ament_index_python import get_package_share_directory
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from janken_interfaces.msg import Blendshapes

JP = {'gu': 'グー ✊', 'choki': 'チョキ ✌', 'pa': 'パー 🖐'}
DEFAULT_LABELS = ['gu', 'choki', 'pa']
pkg_share = get_package_share_directory('janken_expression')
DEFAULT_PATH = os.path.join(pkg_share, 'config', 'calibration.yaml')


class CalibrationNode(Node):
    def __init__(self):
        super().__init__('calibration_node')

        self.declare_parameter('blendshapes_topic', '/janken/blendshapes')
        self.declare_parameter('calibration_file', DEFAULT_PATH)
        self.declare_parameter('capture_sec', 1.5)
        self.declare_parameter('labels', DEFAULT_LABELS)
        self.declare_parameter('reload_after_save', True)
        self.declare_parameter(
            'reload_service', '/mediapipe_face_node/reload_calibration')

        bs_topic = self.get_parameter('blendshapes_topic').value
        self.out_path = os.path.expanduser(
            self.get_parameter('calibration_file').value)
        self.capture_sec = float(self.get_parameter('capture_sec').value)
        self.labels = list(self.get_parameter('labels').value)
        self.reload_after_save = bool(
            self.get_parameter('reload_after_save').value)
        self.reload_service = self.get_parameter('reload_service').value

        self._collecting = False
        self._buffer = []          # 収集中フレームの [{name: score}, ...]
        self._got_any = False

        self.sub = self.create_subscription(
            Blendshapes, bs_topic, self._bs_callback, 10)

    # ------------------------------------------------------------------
    def _bs_callback(self, msg: Blendshapes):
        self._got_any = True
        if self._collecting:
            self._buffer.append(dict(zip(msg.names, msg.scores)))

    def _spin(self, seconds):
        end = time.time() + seconds
        while time.time() < end and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.02)

    def _collect(self):
        self._buffer = []
        self._collecting = True
        self._spin(self.capture_sec)
        self._collecting = False
        return list(self._buffer)

    @staticmethod
    def _average(frames):
        acc = {}
        for fr in frames:
            for name, score in fr.items():
                acc.setdefault(name, []).append(float(score))
        return {name: sum(v) / len(v) for name, v in acc.items()}

    def _wait_for_topic(self, timeout=10.0):
        print(f'blendshapes を待機中...（{self._param_topic()}）')
        end = time.time() + timeout
        while not self._got_any and time.time() < end and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
        return self._got_any

    def _param_topic(self):
        return self.get_parameter('blendshapes_topic').value

    # ------------------------------------------------------------------
    def run_interactive(self):
        print('=' * 56)
        print(' 表情キャリブレーション')
        print('=' * 56)
        if not self._wait_for_topic():
            print('!! blendshapes を受信できません。')
            print('   usb_cam と mediapipe_face_node が起動しているか確認してください。')
            return

        results = {}
        for label in self.labels:
            jp = JP.get(label, label)
            while True:
                input(f'\n▶ 「{jp}」に対応する表情を作って Enter を押してください...')
                print('   撮影中... 表情をキープ')
                frames = self._collect()
                if len(frames) < 3:
                    print(f'   !! フレームが少なすぎます（{len(frames)}）。'
                          'もう一度お願いします。')
                    continue
                results[label] = self._average(frames)
                print(f'   ✓ 「{jp}」を登録しました（{len(frames)} フレーム平均）')
                break

        self._save(results)
        if self.reload_after_save:
            self._call_reload()
        print('\nキャリブレーション完了！ じゃんけんを始められます。')

    # ------------------------------------------------------------------
    def _save(self, results):
        os.makedirs(os.path.dirname(self.out_path) or '.', exist_ok=True)
        data = {'labels': results}
        with open(self.out_path, 'w') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=True)
        print(f'\n保存しました: {self.out_path}')

    def _call_reload(self):
        client = self.create_client(Trigger, self.reload_service)
        if not client.wait_for_service(timeout_sec=3.0):
            print(f'（{self.reload_service} が見つかりません。'
                  'face_node を再起動すれば反映されます）')
            return
        future = client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is not None:
            print(f'再読み込み: {future.result().message}')
        else:
            print('（再読み込みサービスの応答がありませんでした）')


def main(args=None):
    rclpy.init(args=args)
    node = CalibrationNode()
    try:
        node.run_interactive()
    except KeyboardInterrupt:
        print('\n中断しました。')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
