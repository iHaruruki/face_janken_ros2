
Install Python packages
```bash
cd ~/ros2_ws/src/face_janken_ros2/face_janken_ros2
uv sync
```

Install ROS 2 packages
```bash
sudo apt update
sudo apt install ros-jazzy-usb-cam ros-jazzy-cv-bridge
```

## How to use
### Play
Run camera
```bash
ros2 run usb_cam usb_cam_node_exe
```
Run `mediapipe_face_node`
```bash
cd ~/ros2_ws/src/face_janken_ros2/face_janken_ros2/
source .venv/bin/activate
ros2 run face_janken_ros2 mediapipe_face_node.py
```
Run `janken_node`
```bash
cd ~/ros2_ws/src/face_janken_ros2/face_janken_ros2/
source .venv/bin/activate
ros2 run face_janken_ros2 janken_node.py
```

## calibration
Run camera
```bash
ros2 run usb_cam usb_cam_node_exe
```
Run `mediapipe_face_node`
```bash
cd ~/ros2_ws/src/face_janken_ros2/face_janken_ros2/
source .venv/bin/activate
ros2 run face_janken_ros2 mediapipe_face_node.py
```
Run `calibration_node`
```bash
cd ~/ros2_ws/src/face_janken_ros2/face_janken_ros2/
source .venv/bin/activate
ros2 run face_janken_ros2 calibration_node.py
```

## Topics

| トピック | 型 | 説明 |
|---|---|---|
| `/image_raw` | `sensor_msgs/Image` | カメラ映像（usb_cam が publish） |
| `/janken/hand` | `janken_interfaces/Hand` | 表情から判定した手 |
| `/janken/blendshapes` | `janken_interfaces/Blendshapes` | blendshape スコア（校正用の特徴量） |
| `/janken/result` | `janken_interfaces/Result` | 勝敗結果 |
| `/janken/status` | `std_msgs/String` | 掛け声・結果テキスト（GUI 連携用） |
| `/janken/debug_image` | `sensor_msgs/Image` | 判定結果を重畳したデバッグ画像 |

## 主なパラメータ

**mediapipe_face_node**

| 名前 | 既定 | 説明 |
|---|---|---|
| `model_path` | (launch が自動設定) | `face_landmarker.task` のパス |
| `calibration_file` | `~/.config/janken/calibration.yaml` | 校正ファイル。無ければルール方式 |
| `match_threshold` | 0.0 | >0 のとき、最近傍距離がこれを超えたら `none`（棄却） |
| `jaw_open_threshold` | 0.4 | パー判定のしきい値（ルール方式時） |
| `smile_threshold` | 0.4 | チョキ判定のしきい値（ルール方式時） |
| `publish_debug_image` | true | デバッグ画像を出すか |

サービス `~/reload_calibration` (`std_srvs/Trigger`) を呼ぶと校正ファイルを再読み込みします。

**calibration_node**

| 名前 | 既定 | 説明 |
|---|---|---|
| `calibration_file` | `~/.config/janken/calibration.yaml` | 保存先 |
| `capture_sec` | 1.5 | 1表情あたりの撮影時間（秒） |
| `labels` | `[gu, choki, pa]` | 登録する手の順番 |
| `reload_after_save` | true | 保存後に face_node へ reload 要求を送る |

**janken_node**

| 名前 | 既定 | 説明 |
|---|---|---|
| `round_interval_sec` | 6.0 | 1ラウンドの間隔（秒） |
| `hand_timeout_sec` | 1.0 | この秒数より古い手は「認識なし」とみなす |