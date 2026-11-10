# Attention Transfer 实际运行结果

完成传球 4620 个；有效 21 个；排除 4599 个。主要限制：4579 个回合缺少接球事件。有效样本覆盖率约 0.45%，不宜直接外推到全部完成传球。

计算沿用给定公式，实际方向为接球者 B 的注意力减少、吸引者 A 的注意力增加。回合总分为所有非接球路线参与者的个人分数之和。

| gameId | playId | 接球者 | 最高分吸引者 | 个人分数 | 回合总分 |
| --- | --- | --- | --- | ---: | ---: |
| 2021101700 | 1621 | Laviska Shenault (WR) | Laquon Treadwell (WR) | 0.557051 | 0.855016 |
| 2021091904 | 2682 | Albert Okwuegbunam (TE) | Tim Patrick (WR) | 0.539311 | 0.711734 |
| 2021110100 | 79 | Travis Kelce (TE) | Darrel Williams (RB) | 0.526193 | 0.951477 |
| 2021101006 | 1912 | Eric Ebron (TE) | Najee Harris (RB) | 0.327129 | 0.765269 |
| 2021092610 | 3806 | Jaylen Waddle (WR) | Will Fuller (WR) | 0.281244 | 0.350276 |
| 2021092604 | 1629 | Byron Pringle (WR) | Clyde Edwards-Helaire (RB) | 0.273149 | 0.386701 |
| 2021102405 | 1050 | Geoff Swaim (TE) | Nick Westbrook-Ikhine (WR) | 0.259486 | 0.669662 |
| 2021091300 | 1226 | Sammy Watkins (WR) | Marquise Brown (WR) | 0.252076 | 0.269640 |
| 2021092604 | 3134 | Noah Gray (TE) | Blake Bell (TE) | 0.225220 | 0.442116 |
| 2021103111 | 2554 | Cameron Brate (TE) | Leonard Fournette (RB) | 0.197181 | 0.457253 |
| 2021092610 | 3990 | Jaylen Waddle (WR) | Malcolm Brown (RB) | 0.194356 | 0.334477 |
| 2021093000 | 2608 | James Robinson (RB) | Marvin Jones (WR) | 0.153041 | 0.420683 |
| 2021091300 | 1075 | Josh Jacobs (RB) | Bryan Edwards (WR) | 0.146874 | 0.244676 |
| 2021101400 | 675 | Leonard Fournette (RB) | Antonio Brown (WR) | 0.116440 | 0.238312 |
| 2021101400 | 627 | Leonard Fournette (RB) | Antonio Brown (WR) | 0.084662 | 0.171081 |
| 2021092604 | 1460 | Austin Ekeler (RB) | Gabe Nabers (FB) | 0.083839 | 0.212465 |
| 2021091910 | 976 | Chris Godwin (WR) | Rob Gronkowski (TE) | 0.066770 | 0.140322 |
| 2021090900 | 3909 | Leonard Fournette (RB) | Mike Evans (WR) | 0.066067 | 0.170778 |
| 2021102405 | 4201 | Mecole Hardman (WR) | Byron Pringle (WR) | 0.060507 | 0.144155 |
| 2021091905 | 3049 | Myles Gaskin (RB) | Mike Gesicki (TE) | 0.048099 | 0.120433 |
| 2021091600 | 1426 | Saquon Barkley (RB) | Kyle Rudolph (TE) | 0.016716 | 0.036378 |

14 项单元测试通过。已核验回合唯一性、起止帧、接球距离阈值，并从逐防守者贡献复算全部个人及回合总分。

明细见同目录 plays.csv、attractors.csv、defenders.csv、excluded.csv。参数和排除统计见 report.json。目标身份来自最近距离启发式，注意力权重来自几何基线，均未经独立真值验证。
