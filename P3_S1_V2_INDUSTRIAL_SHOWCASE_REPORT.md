# P3-S1-V2 工业机器人实验室场景升级报告

**结论：PASS（固定随机布局下的单场景展示通过）**

本轮把 `B_-30deg_seed0` 视野外目标搜索场景布置为工业实验室，并复用原 V1.1 感知/控制、Candidate B G1 policy、P2 Wire v1 和 QPSK 链路。理想消息、无噪声 QPSK、8 dB AWGN 三次真实 MuJoCo 仿真均到达目标停止条件。场景使用真实 MuJoCo 碰撞几何，三次运行均未记录到机器人与障碍物接触。

结论只适用于本文的固定 layout seed、场景和机器人 seed。场景有保留的通行路线，不验证自主避障或路径规划。

## 场景结构与布局

场景包含六组工业物件和一组非碰撞背景墙：

| 物件 | 外观与组成 | 碰撞几何 |
|---|---|---:|
| 多层货架 | 蓝灰支架、三层横板、局部黄色边条 | 6 个 box |
| 控制柜 | 青绿色柜体、面板、屏幕和指示灯 | 1 个 box；面板细节为视觉几何 |
| 物流箱堆 | 不同尺寸的棕黄纸箱、胶带与标签 | 3 个 box |
| 安全护栏 | 黄黑横梁与三根立柱 | 5 个 box |
| 工业桶 | 蓝色与银灰圆桶，带环形细节 | 2 个 cylinder |
| 实验工作台 | 灰白桌面、四腿、仪器外形 | 5 个 box |
| 背景墙 | 灰色实验室墙面、蓝绿色窗格、上沿 | 0 个；全部视觉装饰 |

共 **42 个 primitive geom**：22 个可碰撞，20 个视觉装饰。障碍物碰撞使用 MuJoCo 原生 box/cylinder，碰撞 geom 的 `contype=1`、`conaffinity=1`。没有加入外部 mesh 或第三方场景资产。Box 配置尺寸采用 MuJoCo 半尺寸，例如工作台面 `[0.88, 0.43, 0.075]` 对应约 `1.76 × 0.86 × 0.15 m`；圆桶配置为半径 `0.25–0.28 m`、半高 `0.39–0.48 m`。

布局使用固定随机种子 `20261105`，每个主要物件的 XY 平移扰动范围为 ±0.42 m、偏航扰动为 ±38°。这使物件相对基准坐标产生不规则偏移和朝向，同时保证重新运行时位置完全一致。地面沿用原 MuJoCo 地面并改为混凝土灰配色；背景墙、指示灯和道具面板均为视觉几何，不改变机器人动力学。

![工业实验室主展示视角](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/scene_overview.png)

其他真实 MuJoCo 视角：

- [正面斜视](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/view_front_three_quarter.png)
- [反向斜视](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/view_opposite_three_quarter.png)
- [高位总览](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/view_raised_overview.png)

主展示视角为 1280×720，完整覆盖机器人、红色目标及主要道具。货架、控制柜、纸箱、护栏、圆桶和工作台轮廓与颜色可辨，但画面仍是 primitive 风格的实验室布景，不是写实渲染。原地面棋盘纹理和少量阴影/边缘伪影仍可见。

## 碰撞与感知检查

S1-0 场景 smoke 结果为 PASS：

- MuJoCo 成功加载全部物件；机器人初始位置 `(0, 0, 0.8 m)`，初始障碍物接触数为 0。
- 初始机器人碰撞几何与障碍物几何的最小距离为 `1.664 m`。
- RGB-D 感知相机保持原始 `64×48`，RGB shape 为 `[48, 64, 3]`，depth shape 为 `[48, 64]`；未修改相机参数或视觉模型。
- t=0 的红色目标观测无效，与 `B_-30deg_seed0` 初始目标在视野外的设置相符。机器人旋转搜索后在约 0.22 s 出现短暂 4-pixel 检测，随后恢复 SEARCH；持续重新发现发生在约 16.74–17.04 s，17.74 s 进入 APPROACH。因初次检测面积很小，不能把它解释成稳定获取。
- 轨迹检查器通过；它只用于核对已知参考路线的空间余量，不代表控制器能绕开任意障碍。

场景 smoke、各物件实际解析位置、碰撞标记、相机截图和 RGB-D 样本保存在 [S1-0 证据目录](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/)，汇总为 [scene_smoke.json](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/scene_smoke.json)。

## 真实 MuJoCo 任务与通信结果

| 阶段 | 任务结果 | 仿真时间 / policy ticks | 轨迹长度 | 最终目标距离 | 通信结果 | 障碍物接触 / 最小采样距离 |
|---|---|---:|---:|---:|---|---|
| 理想消息 S1-1 | 成功，STOP | 26.32 s / 1316 | 3.207 m | 0.567 m | 无 PHY；OBS 264/264、CMD 263/263 接受 | 0 / 0.960 m |
| 无噪声 QPSK S1-2 | 成功，STOP | 26.32 s / 1316 | 3.209 m | 0.570 m | 50,592 bit，0 错误；527/527 帧接受，BER=0 | 0 / 0.960 m |
| 8 dB AWGN S1-3 | 成功，STOP | 26.22 s / 1311 | 3.202 m | 0.570 m | 50,400 bit，11 错误，BER=`2.1825e-4`；514/525 帧接受（97.90%） | 0 / 0.961 m |

8 dB AWGN 的理论 QPSK BER 为 `1.9091e-4`。本次约 50k bit 的单 episode 样本略高于理论值；不把单次仿真视作统计等价证明。11 次拒帧由 7 次 CRC reject（OBS 4、CMD 3）和 4 次 preamble reject（OBS 2、CMD 2）组成。514 个接受帧均正确，accepted-but-wrong 为 0。没有 TTL 超时归零事件；最大命令年龄约 185 ms，低于 200 ms TTL。三次运行均无跌倒、非有限状态或异常终止。

机器人按 50 Hz policy tick 执行，语义通信/相机为 10 Hz；配置中的 policy tick 为 20 ms、camera period 为 100 ms。搜索段累计偏航变化约 313.5°，状态经历 SEARCH、ALIGN、APPROACH、STOP。通信变化没有改变任务路径的总体结果。

障碍物接触监视每 10 Hz 从同步后的 MuJoCo 状态采样。上述“0 接触”和最小距离是本次运行记录，不是连续时间碰撞证明或一般性安全结论。目标接触事件也为 0。

完整 trace、语义消息、帧结果、机器人状态、命令年龄、接触记录和解析后的 layout 坐标分别位于：

- [理想消息 S1-1 trace](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-1/result_wideview.json)
- [无噪声 QPSK S1-2 trace](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-2/result_wideview.json)
- [8 dB AWGN S1-3 trace](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/result_wideview.json)

## 视频

视频均由对应 episode 的实时 `env.sim.data` 同步渲染，不使用静态姿态或预编排运动；字幕取自同次运行 trace。主视频为 1280×720、25 fps，658/656 帧，时长约 26.3 s。同步分屏为 1784×720，右侧为同次仿真的真实 64×48 G1 相机 RGB 帧。

- S1-1 理想消息：[第三人称字幕视频](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-1/s1-1_B_-30deg_seed0_captioned.mp4) · [同步第一视角分屏](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-1/s1-1_B_-30deg_seed0_split_view.mp4)
- S1-2 无噪声 QPSK：[第三人称字幕视频](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-2/s1-2_B_-30deg_seed0_captioned.mp4) · [同步第一视角分屏](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-2/s1-2_B_-30deg_seed0_split_view.mp4)
- S1-3 8 dB AWGN：[第三人称字幕视频](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/s1-3_B_-30deg_seed0_captioned.mp4) · [同步第一视角分屏](artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/s1-3_B_-30deg_seed0_split_view.mp4)

分辨率、帧率、帧数和时长已用 `ffprobe` 检查。未在报告中引用任何中断生成的损坏视频。

## 保留的失败证据与限制

较早的固定布局版本（平移扰动 ±0.28 m、偏航扰动 ±32°）在理想控制下出现 horizon timeout：机器人未进入 STOP，路径长 3.972 m，结束位置约 `(-1.55, -1.12) m`，曾采样到距障碍物几何约 0.066 m，接触事件仍为 0。该 run 保存在 [早期失败 trace](artifacts/p3_s1_v2_industrial/debug_no_video2/s1-1/result.json)。仅凭该轨迹不能确认具体根因；它说明控制结果对 clutter 下的感知/运动耦合敏感。随后调整为本文记录的固定 seed 布局、扩大物件扰动，并降低箱体颜色的红色饱和度；再从 smoke 开始重新验证，最终三组均通过。失败记录未删除，也未用它替代最终结果。

主要限制：

- 只有一个场景和一个固定布局 seed；没有做多 seed 鲁棒性搜索。
- 道具布置在参考路线周边保留通路；该结果是 obstacle-rich showcase，不是自主绕障导航。
- 部分棕黄色物件可能与简单颜色阈值检测有交互风险，当前只验证本文固定颜色和布局。
- primitive 物件、棋盘地面及阴影伪影仍有可见的合成感；若目标是更写实的工业实验室，需要单独进行后续美术资产工作，但本轮未引入外部 mesh 或改变动力学。
- 实际视频输出依赖 CPU 离屏渲染，速度较慢。新项目适配器对 FFmpeg 信息日志进行了收敛，未改旧项目 runner。

## 代码、依赖与边界

本轮变更限于新项目：

- [工业场景配置](experiments/p3_s1_v2_industrial_config.json)
- [场景装配、随机布局与验证](src/esc/p3_s1_scene.py)
- [S1 smoke/episode runner](experiments/p3_s1_multi_obstacle.py)
- [视频字幕和同步分屏](experiments/p3_s1_v_overlay.py)
- [场景单元测试](tests/test_p3_s1_scene.py)

沿用旧项目 Candidate B/V1.1 代码和现有 ONNX policy；本轮没有修改旧项目、P1 PHY、Wire v1、G1 ONNX、原导航控制器或机器人动力学，没有增加外部模型、mesh 或训练步骤。旧仓库工作区检查无未提交改动。没有 Git commit 或 push。

最终验证：`tests/test_p3_s1_scene.py` **5 passed**；Python compile 检查通过；S1-0 smoke PASS；S1-1/S1-2/S1-3 真实仿真 PASS。结论为 **PASS（单场景、单固定 seed 的展示验证）**。
