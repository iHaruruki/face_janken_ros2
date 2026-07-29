# 表情じゃんけん (janken_expression)

ROS 2 **Jazzy** 用。カメラに映った**表情**からじゃんけんの手を判定して、CPU と対戦するパッケージです。

```
usb_cam_node ──/image_raw──▶ mediapipe_face_node ──/janken/hand──▶ janken_node
 (カメラ映像)                  (表情→手を判定)              (勝敗判定)──▶ /janken/result
```

## パッケージ構成

| パッケージ | 種類 | 内容 |
|---|---|---|
| `janken_interfaces` | ament_cmake | メッセージ定義 `Hand.msg` / `Result.msg` |
| `janken_expression` | ament_python | `mediapipe_face_node`, `janken_node`, launch |

`usb_cam_node` は既存の [`usb_cam`](https://github.com/ros-drivers/usb_cam) パッケージをそのまま使います（自作しません）。

## 表情 → 手 の判定方式

判定方式は2つあり、**校正ファイルの有無で自動的に切り替わります**。

### 1. キャリブレーション方式（推奨）

`calibration_node` でグー/チョキ/パーの表情を実際に登録すると、その3つの
blendshape ベクトル（テンプレート）が保存されます。実行時は現在の表情を
各テンプレートと比較し、**最も近いもの**を手として選びます。好きな表情を
自由に割り当てられ、個人差にも強いのが利点です。

### 2. ルール方式（フォールバック）

校正ファイルが無い場合は、blendshape のしきい値で判定します。

| 手 | 表情 | 使用する blendshape |
|---|---|---|
| パー (pa) | 口を大きく開ける | `jawOpen` |
| チョキ (choki) | 笑顔になる | `mouthSmileLeft/Right` |
| グー (gu) | 無表情（自然な顔） | 上記どちらのしきい値も超えない場合 |

しきい値は `jaw_open_threshold` / `smile_threshold` で調整できます。

## キャリブレーション手順

`usb_cam` と `mediapipe_face_node` が動いている状態（＝通常の launch を起動中）で、
**別のターミナル**から対話ノードを実行します。

```bash
# ターミナル1: パイプラインを起動（この時点では校正ファイルが無ければルール方式）
ros2 launch janken_expression janken.launch.py

# ターミナル2: 表情を登録
source ~/janken_ws/install/setup.bash
ros2 run janken_expression calibration_node
```

画面の指示に従って「グー」「チョキ」「パー」に対応させたい表情を順に作り、
その都度 Enter を押します。各表情は約1.5秒ぶんのフレームを平均して登録されます。
登録が終わると `~/.config/janken/calibration.yaml` に保存され、`mediapipe_face_node`
の `~/reload_calibration` サービスが自動で呼ばれて即座に反映されます。

以降は launch のデフォルトでこの校正ファイルが読み込まれます。やり直したいときは
`calibration_node` を再実行するだけです。

保存される YAML の例:

```yaml
labels:
  gu:    {jawOpen: 0.02, mouthSmileLeft: 0.03, browDownLeft: 0.41, ...}
  choki: {jawOpen: 0.05, mouthSmileLeft: 0.88, mouthSmileRight: 0.86, ...}
  pa:    {jawOpen: 0.79, mouthSmileLeft: 0.10, ...}
```

## セットアップ

```bash
# 1) 依存パッケージ (usb_cam, cv_bridge 等)
sudo apt update
sudo apt install ros-jazzy-usb-cam ros-jazzy-cv-bridge

# 2) MediaPipe / OpenCV (pip)
pip install mediapipe opencv-python

# 3) ワークスペースへ配置
mkdir -p ~/janken_ws/src
cp -r janken_interfaces janken_expression ~/janken_ws/src/

# 4) MediaPipe モデルをダウンロード（colcon build の前に）
~/janken_ws/src/janken_expression/scripts/download_model.sh

# 5) ビルド
cd ~/janken_ws
rosdep install --from-paths src --ignore-src -r -y   # 任意
colcon build
source install/setup.bash
```

## 実行

```bash
ros2 launch janken_expression janken.launch.py
```

USB カメラのフォーマットに合わせて引数を変えられます。

```bash
ros2 launch janken_expression janken.launch.py \
    video_device:=/dev/video0 pixel_format:=mjpeg2rgb round_interval_sec:=5.0
```

数秒ごとに「最初はグー、じゃんけん…ぽん！」と進行し、`ぽん！`の瞬間の表情が
あなたの手になります。結果は端末ログと `/janken/result` に出ます。

デバッグ画像（検出した手とスコアを重畳）は `/janken/debug_image` で確認できます。

```bash
ros2 run rqt_image_view rqt_image_view /janken/debug_image
```

## トピック

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
