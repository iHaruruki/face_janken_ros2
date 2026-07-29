# MediaPipe FaceLandmarker の blendshape スコア（キャリブレーション用の特徴ベクトル）
std_msgs/Header header
string[]  names    # blendshape 名（例: jawOpen, mouthSmileLeft, ...）
float32[] scores   # 対応するスコア (0.0〜1.0), names と同じ長さ
