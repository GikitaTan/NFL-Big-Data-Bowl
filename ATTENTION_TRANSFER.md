# Attention Transfer：完成传球回合分析

运行 `python3 attention_transfer.py` 会处理全部本地比赛。无需额外依赖。针对指定比赛或回合：

```bash
python3 attention_transfer.py --game-id 2021090900 --play-id 3909 --output-dir outputs/play_3909
python3 -m unittest discover -s tests -v
```

## 目标识别与质量控制

仅分析 `plays.csv` 中 `passResult == C` 的回合。在 `pass_outcome_caught` 帧取得 football 坐标，先在全部进攻球员中找最近者，再验证其 PFF 角色为 `Pass Route`。默认最近距离不超过 2 码，最近者相对第二近者的距离优势必须超过 0.1 码。这些是启发式阈值，可通过 `--max-catch-distance`、`--ambiguity-margin` 调整，不能视为已验证的接球身份标签。

缺失接球事件、球坐标异常、最近者不是路线参与者或目标不明确时排除。不能将 `pass_arrived` 直接视为接球成功事件，也不使用出手后最后一帧冒充接球帧。

`t0 = snapFrame + 3`，按 10 Hz 假定对应开球后约 0.3 秒；`t1 = passForwardFrame - 1`，严格使用出手前一帧。优先使用 `ball_snap`、`pass_forward` 人工标注；相应标注缺失时才使用 autoevent，具体事件来源保留在输出中。因此可能与旧脚本“取最早任一出手事件”的默认窗口不同，本脚本独立重算两个端点的注意力。

要求 t0 < t1、两个端点完整、路线候选人集合一致、11 名防守球员身份一致且坐标有效；否则排除，避免候选集变化产生虚假的权重转移。身体朝向缺失时沿用原模型的零方向项，并记录缺失次数。

## 分数方向

沿用图片中的公式，A 是未接球的路线参与者，B 是实际接球者，j 是防守球员：

```text
delta_jA = attention_jA(t1) - attention_jA(t0)
delta_jB = attention_jB(t1) - attention_jB(t0)
score(A, B) = sum_j max(0, delta_jA) * max(0, -delta_jB)
```

这个公式衡量 B 的注意力减少、A 的注意力增加，即 **B → A**。图片虽然写作 `T_A→B`，其文字解释和代码均对应 B → A。本实现保留图片的数值公式，以 `attractor` 和 `target` 命名参数，避免混淆。不会把不同防守球员的增量、减量相乘。

对每个非目标球员单独算分，再将这些分数求和作为回合的 `Transfer`；记录最大贡献者及其单独的 `maxAttractorTransfer`。完全相同时按 nflId 数值升序选一位，同时记录 `topScoreTieCount`；如果所有贡献均为 0，最大吸引者字段为空。分数是几何注意力变化的描述，不能解释为球员通过跑位造成接球者空位的因果证据。

## 输出表与 DataFrame

默认目录为 `outputs/attention_transfer/`：

| 文件 | 粒度与用途 |
| --- | --- |
| `plays.csv` | 每个有效完成传球回合一行；包含 gameId、playId、Target、Attractor、Transfer，以及球员 ID、姓名、帧号、距离和质量字段 |
| `attractors.csv` | 每个回合的每名非目标路线球员一行，Transfer 是该球员的单独分数 |
| `defenders.csv` | 每个回合、吸引者、防守者一行，保留两个端点的注意力、delta 与分数贡献，便于复算 |
| `excluded.csv` | 每个被排除的完成传球回合一行及原因 |
| `report.json` | 数据覆盖率、排除原因、参数及公式方向 |
| `example.json` | 单独吸引者得分最高的有效真实回合 |

`Target` 和 `Attractor` 是位置；ID 和姓名另设字段，避免同位置球员被合并。`Transfer` 不包含接球者本人的分数。同一 YAC 标签后续只需合并到 `plays.csv` 一次。此阶段不生成 YAC 标签，也不训练后续预测模型。

有 pandas 的 Python 环境中，可直接取得要求的 DataFrame：

```python
from attention_transfer import load_dataframe
df = load_dataframe()
print(df[['gameId', 'playId', 'Target', 'Attractor', 'Transfer']])
assert not df.duplicated(['gameId', 'playId']).any()
```

核心程序已直接导出同等结构的 CSV，不依赖 pandas。目标识别依赖未来接球事件，因此这些结果属于赛后分析；PFF 路线角色也是赛后标签。后续做预测评估时须明确这些信息的使用时点。
