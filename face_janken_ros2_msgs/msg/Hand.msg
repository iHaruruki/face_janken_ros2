# じゃんけんの手を表すメッセージ（表情から推定した結果）
std_msgs/Header header
string hand         # "gu"(グー) / "choki"(チョキ) / "pa"(パー) / "none"(顔検出なし)
float32 confidence  # 認識の確信度 (0.0〜1.0)
