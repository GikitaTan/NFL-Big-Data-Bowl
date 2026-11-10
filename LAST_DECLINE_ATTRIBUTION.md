# 最后一次注意力下降：队友贡献计算

运行 `python3 last_decline_attribution.py`，对 `outputs/receiver_trends/series.jsonl` 中全部 4,465 个实际接球者回合执行分析。接球者身份、分析窗口和排除标准沿用此前的全数据趋势统计。

## 时间段

在开球至出手前的总注意力序列中，沿用 5 帧平滑、绝对变化 0.1 与相对极差 10% 取较大值、极值到反转确认至少 3 帧的判定规则，找到**最后一段已确认的显著下降**，以该段峰值和随后谷值为两个端点。

“最后一段下降”不是“从整回合最高点到出手”，也不要求曲线最终处于下降状态。例如 UDU 使用中间那段 D，即便其后还有回升。无显著下降的回合标记 `no_significant_decline`，不强行指定吸引者。

## 贡献分数

先重算两个端点附近各 5 帧的完整防守者×路线参与者注意力矩阵，按与总曲线完全相同的窗口做平均，再计算：

```text
loss_jB = max(0, attention_jB(start) - attention_jB(end))
gain_jA = max(0, attention_jA(end) - attention_jA(start))
Transfer_A = sum_j loss_jB * gain_jA
```

B 是实际接球者，A 遍历其他所有路线参与者。只统计同一防守者对接球者减小、对队友增加的同步变化，不把不同防守者的增量和减量相乘。本步骤不另加“开球时盯防者”筛选，以免漏掉最后下降段之前才开始关注接球者的防守球员。

`scoreShare = Transfer_A / sum_A Transfer_A` 是**分数份额**，不是该球员导致注意力下降的因果百分比，也不是注意力流量的守恒分解。总注意力净下降与各防守者正向损失总和分别输出，避免把部分防守者的回升忽略。

最高分并列时全部保留在 `topAttractorIds` / `topAttractorNames`。另将按得分降序累计达到 80% 的最少队友集合标为主要吸引者，边界并列全部保留；这是为了方便筛选的一项展示规则，可用 `--major-share` 调整。无论是否进入主要集合，所有其他路线参与者及其分数均保留。

## 输出

- `outputs/last_decline/plays.csv`：每回合一行，包括状态、下降起止帧和时间、净下降、最高分者、主要吸引者集合与得分份额。
- `outputs/last_decline/attractors.csv`：每回合每位非目标路线参与者一行，包含排名、分数、份额、是否最高及是否主要。
- `outputs/last_decline/defenders.csv`：逐防守者、逐队友的起止注意力、delta 和贡献，可直接复算。
- `outputs/last_decline/example.json`：前面可视化的 2021101700 / 1621 回合的结果。
- `outputs/last_decline/report.json`：全数据覆盖、状态及主要吸引者数量分布。
- `outputs/last_decline/RESULTS.md`：实际运行摘要和示例。

计算会核验端点矩阵中每名防守者的权重之和为 1，并核验矩阵得到的接球者总权重与原平滑曲线端点一致。该结果仍是几何模型内的同步变化，不能用作真实视线或因果归因的真值。
