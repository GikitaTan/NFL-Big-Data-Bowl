# Defensive Attention Model

这是无需安装依赖、可直接运行的几何基线。每一帧，对每名防守球员分别计算其对候选接球人的相对注意力。

## 数学定义

防守球员 i 的位置为 p_i，候选接球人 j 的位置为 p_j：

```text
d_ij = ||p_j - p_i||₂
h_i = [sin(o_i), cos(o_i)]
c_ij = h_i · (p_j - p_i) / d_ij
z_ij = -d_ij / distance_scale + direction_weight × c_ij
A_ij = exp((z_ij - max_k z_ik) / temperature)
       / Σ_k exp((z_ik - max_k z_ik) / temperature)
```

角度先转为弧度，采用 NFL 坐标约定：0° 指向 +y，90° 指向 +x。`c_ij` 在 [-1, 1] 之间，正前方为 1，侧面为 0，背后为 -1。默认用身体朝向 `o`；可以改用运动方向 `dir`，但球员后退移动时两者含义不同，低速时运动方向也可能不稳定。

默认 `distance_scale=5` 码、`direction_weight=2`、`temperature=1`。距离每增加 5 码，原始分数减 1；相同距离下，正前方相对正后方的注意力比为 exp(4)，约 54.6。温度越低，分配越集中。这些是可调整的启发式参数，尚未通过盯防标签拟合或校准。

## 运行

从本项目根目录运行：

```bash
python3 defensive_attention.py --game-id 2021090900 --play-id 97
python3 defensive_attention.py --game-id 2021090900 --candidate-mode position --output outputs/game_attention.csv
python3 -m unittest discover -s tests -v
```

不传 `--play-id` 时处理整场比赛。默认数据目录是本项目的数据文件夹，可通过 `--data-dir` 指定其他目录。只保留开球到首次出手或终止事件之间的帧，含两端；缺少开球事件的 play 跳过，缺少结束事件时使用剩余观测帧。`--window all` 可保留所有帧。

候选集有两种模式：

- `route`（默认）：使用当前 play 中 PFF `Pass Route` 标签。这是赛后路线参与者标注，适合描述性分析；不能直接宣称为在线预测。
- `position`：使用进攻方 WR、TE、RB、FB、HB，不使用 PFF 路线标签。这只是位置代理，可能包含留守阻挡者，也无法识别临时合格的其他位置球员；不等同于裁判判定的合法接球资格。

防守方按 `possessionTeam` 的对手识别，纳入所有防守球员，包含冲传者；football 不参与计算。候选人之间不按距离做硬阈值筛选，以保留远距离的深区路线威胁。

输出 `outputs/defensive_attention.csv`：每行是一个 game/play/frame/defender/receiver 配对，包含距离、方向余弦、朝向缺失标记、softmax 前分数和最终 attention。每名防守球员在每一帧对有效候选人的 attention 之和为 1。无效坐标的球员被排除；朝向缺失或两人位置重合时方向项记为 0；没有候选人时不输出配对。

## 解读与限制

attention=0.7 表示该防守球员在当前候选集合中分配给此接球人的相对几何权重为 70%，不是其有 70% 的概率在看该球员。身体朝向不是眼睛视线，也不能仅凭该分数判定人盯人责任或真实战术意图。模型在候选集中强制分配全部权重，即便防守球员正在看 QB、冲传或守空区；一个候选人时权重必然为 1。

模型使用当前帧位置，没有使用未来接球点、实际传球目标或未来轨迹。这里的“接球路线上的进攻球员”指候选路线参与者，不是对传球飞行线路的预测。后续如需预测未来路线，可以另行加入明确预测时长的外推，并单独验证其收益。

若有独立的注意力或覆盖责任标注，可按比赛拆分训练/验证集，以交叉熵拟合距离和方向权重及温度；注意参数整体缩放与温度存在冗余，应固定一个尺度。不要用实际接球目标作为防守球员真实注意力的替代真值。
