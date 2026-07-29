#!/usr/bin/env python3
"""表情から検出した手でじゃんけんを進行するノード。

/janken/hand (janken_interfaces/Hand) を購読して最新のプレイヤーの手を保持し、
一定間隔で「最初はグー、じゃんけんぽん！」の掛け声とともに1ラウンドを実行する。
CPUはランダムに手を出し、勝敗を判定して /janken/result にpublishする。
掛け声・結果は /janken/status (std_msgs/String) にも流すので、GUI等から利用できる。
"""
import random

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from face_janken_ros2_msgs.msg import Hand, Result

JP = {'gu': 'グー', 'choki': 'チョキ', 'pa': 'パー', 'none': '？'}
# key の手が value の手に勝つ
BEATS = {'gu': 'choki', 'choki': 'pa', 'pa': 'gu'}
HANDS = ('gu', 'choki', 'pa')


class JankenNode(Node):
    def __init__(self):
        super().__init__('janken_node')

        self.declare_parameter('hand_topic', '/janken/hand')
        self.declare_parameter('result_topic', '/janken/result')
        self.declare_parameter('status_topic', '/janken/status')
        self.declare_parameter('round_interval_sec', 6.0)
        self.declare_parameter('hand_timeout_sec', 1.0)

        hand_topic = self.get_parameter('hand_topic').value
        result_topic = self.get_parameter('result_topic').value
        status_topic = self.get_parameter('status_topic').value
        self.round_interval = float(
            self.get_parameter('round_interval_sec').value)
        self.hand_timeout = float(
            self.get_parameter('hand_timeout_sec').value)

        self.sub = self.create_subscription(
            Hand, hand_topic, self.hand_callback, 10)
        self.result_pub = self.create_publisher(Result, result_topic, 10)
        self.status_pub = self.create_publisher(String, status_topic, 10)

        self._latest_hand = 'none'
        self._latest_conf = 0.0
        self._latest_stamp = self.get_clock().now()

        # フェーズ進行用タイマー（1秒ごとに1フェーズ進む）
        self._phase = 0
        self._n_phases = max(3, int(round(self.round_interval)))
        self.timer = self.create_timer(1.0, self.tick)

        self.get_logger().info(
            'janken_node 起動: 表情でじゃんけんを始めます！ '
            f'（{self.round_interval:.0f}秒ごとに1回）')

    def hand_callback(self, msg: Hand):
        self._latest_hand = msg.hand
        self._latest_conf = msg.confidence
        self._latest_stamp = self.get_clock().now()

    def _current_player_hand(self):
        """直近の検出が古すぎる場合は none 扱いにする。"""
        age = (self.get_clock().now() - self._latest_stamp).nanoseconds / 1e9
        if age > self.hand_timeout:
            return 'none'
        return self._latest_hand

    def tick(self):
        p = self._phase
        if p == 0:
            self._say('✊ 最初はグー！')
        elif p == 1:
            self._say('✊✌🖐  じゃんけん…')
        elif p == 2:
            self._play_round()
        # p >= 3 は結果を見せるためのインターバル

        self._phase = (self._phase + 1) % self._n_phases

    def _play_round(self):
        player = self._current_player_hand()
        if player in HANDS:
            player_used, note = player, ''
        else:
            player_used, note = 'gu', '（顔を認識できずグー扱い）'

        cpu = random.choice(HANDS)
        outcome = self._judge(player_used, cpu)

        self._say(
            f'✨ ぽん！  あなた: {JP[player_used]}{note} / '
            f'CPU: {JP[cpu]}  → {self._outcome_jp(outcome)}')

        msg = Result()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.player_hand = player_used
        msg.cpu_hand = cpu
        msg.result = outcome
        self.result_pub.publish(msg)

    @staticmethod
    def _judge(player, cpu):
        if player == cpu:
            return 'draw'
        if BEATS[player] == cpu:
            return 'win'
        return 'lose'

    @staticmethod
    def _outcome_jp(outcome):
        return {'win': 'あなたの勝ち🎉',
                'lose': 'あなたの負け😢',
                'draw': 'あいこ🤝'}.get(outcome, outcome)

    def _say(self, text):
        self.get_logger().info(text)
        self.status_pub.publish(String(data=text))


def main(args=None):
    rclpy.init(args=args)
    node = JankenNode()
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
