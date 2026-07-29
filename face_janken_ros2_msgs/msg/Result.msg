# じゃんけん1ラウンドの結果（プレイヤー視点）
std_msgs/Header header
string player_hand  # プレイヤーの手 (gu/choki/pa)
string cpu_hand     # CPUの手       (gu/choki/pa)
string result       # "win"(勝ち) / "lose"(負け) / "draw"(あいこ)
