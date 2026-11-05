# P1 QPSK 数字通信物理层实现报告

日期：2026-11-04
实现规范：`P0C_EMBODIED_SEMANTIC_COMM_FROZEN_SPEC.md` v1.0
范围：仅 PHY；未开发语义帧、机器人接口、MuJoCo 联动或网站。

## 最终结论：PASS

按冻结的 P0-C 参数实现并实际执行了 Gray QPSK、161-tap 单位能量 RRC、复基带与实带通离散 AWGN、理想相干解调、匹配滤波/定时抽样、BER 统计和图表生成。16 个 pytest 用例通过。正式 baseband BER 的 0–10 dB 六个点均与未编码 QPSK 理论相符；实带通在 0/4/8 dB 的对照也与理论和 baseband 结果相符。

10 dB baseband 只观测到 3 个误码，报告其实测 BER `1.504e-6` 和单侧 95% 上界 `3.886e-6`，没有把有限样本写成 BER=0。实带通对照按 P0-C 取 0/4/8 dB，未运行实带通 2/6/10 dB；该范围与 P0-C 的对照要求一致。

## 1. 实际实现功能

核心实现位于 `src/esc/phy.py`：

- P0-C 明确的 Gray QPSK 映射、硬判决与符号解映射；每符号平均能量为 1。
- RRC 设计：roll-off 可配，P1 默认 `α=0.35`、span 10 symbols、sps 16、161 taps；对称 taps 按离散平方和归一化为 1。
- 全卷积零插值发射滤波、接收匹配滤波、TX+RX 群延迟补偿与符号抽样。
- 复基带 AWGN 和实数带通 AWGN，两者均由冻结的 Eb/N0 约定得到噪声方差，并接受显式 `numpy.random.Generator`。
- 实通带升频、实噪声、理想相干下变频、RRC 匹配滤波和硬判决。
- 理论 BER、实测 BER/error count、单侧 95% Clopper–Pearson BER 上界、Welch PSD。
- 可分块的 full RRC waveform BER 仿真。每个独立 chunk 的头尾各舍弃 10 symbols，以排除有限级联滤波器的边界瞬态；结果分母记录实际比较 bit 数。

实验入口为 `experiments/p1_phy.py`，参数位于 `experiments/p1_phy_config.json`。所有运行固定 master seed 20261104，脚本从 master seed 与实验 mode/EbN0 派生各子实验 seed，并将实际 seed 写入 summary。`requirements-p1.txt` 记录本次环境版本。

## 2. 数学公式与归一化约定

实现直接遵循 P0-C §2：

1. 映射：`00→(+1+j)/√2`、`01→(+1−j)/√2`、`11→(−1−j)/√2`、`10→(−1+j)/√2`；`b0` 控制 I，`b1` 控制 Q，`Es=1`、`Eb=Es/2=0.5`。
2. RRC taps：`L=10×16+1=161`，`Σh[n]²=1`；TX 与 RX 使用同一实对称抽头。单边每级群延迟 `80/fs=1.041667 ms`，级联群延迟 `160/fs=2.083333 ms`。
3. Eb/N0：`γb=10^(EbN0_dB/10)`，`N0=Eb/γb=0.5/γb`。复基带每样本噪声 `w=√(N0/2)(nI+j nQ)`，因此 `E|w|²=N0`，每个 I/Q 样本方差 `N0/2`；实带通每样本噪声方差为 `N0/2`。
4. 通带调制：`x_pb[n]=√2 Re{x_bb[n] exp(j2πfc n/fs)}`；接收用 `√2 x_pb[n] exp(−j2πfc n/fs)` 理想相干混频，再经 RRC matched filter 和已知定时抽样。`fs=76800 Hz`、`fc=20000 Hz`。
5. 理论未编码 Gray-QPSK BER：`Pb=Q(√(2γb))=0.5 erfc(√γb)`。

96-bit frame 的发送波形长度另作数学核对但本轮未实现 frame：48 symbols 的零插值 buffer 为 768 samples，Tx full FIR 输出 928 samples，时长 `12.083333 ms`；这包括 TX FIR tail，不把 Tx+Rx 群延迟误作 airtime。理想 null-to-null 带宽 `6480 Hz`，载波上边缘 `23240 Hz < fs/2=38400 Hz`。

## 3. 测试数量与结果

命令：`PYTHONPATH=src pytest -q tests/test_phy.py`

结果：**16 passed**。用例覆盖：

- 四种 Gray pair 映射和完整回环；非法 bit 值、奇数长度拒绝；
- P1 三个 roll-off taps 的有限值、对称/单位能量、161 taps；
- TX/RX full convolution 长度、160-sample 群延迟、无噪声恢复和残余 ISI；
- 复/实噪声方差、独立 seed 可复现；
- 理论 BER closed form；
- 实带通无噪声调制/解调完整回环；
- 两种 BER 模式的 seed 稳定性及 0 dB 仿真统计与理论的合理性；
- 非法 PHY 参数拒绝。

正式实验又独立检查了 `Σh²=1.0`、tap 最大非对称差 `0.0`、级联抽样主峰 `1.0` 和最大抽样残余 ISI `0.00638764`。这些是实际执行的数值结果，并非只由静态代码推断。

## 4. 理论 BER 与实测 BER

复基带每点配置 bit budget 为 2,000,000。每个实验产生 1,000,000 symbols，分 123 chunks 执行；边界舍弃后实际比较 **1,995,080 bits**。BER 上界为单侧 95% 精确二项 Clopper–Pearson 上界。

| Eb/N0 (dB) | Theory BER | BB errors / bits | BB BER | BB 95% upper |
|---:|---:|---:|---:|---:|
| 0 | 0.0786496 | 156588 / 1995080 | 0.0784871 | 0.0788010 |
| 2 | 0.0375061 | 75102 / 1995080 | 0.0376436 | 0.0378660 |
| 4 | 0.0125008 | 25037 / 1995080 | 0.0125494 | 0.0126798 |
| 6 | 0.00238829 | 4720 / 1995080 | 0.00236582 | 0.00242318 |
| 8 | 0.000190908 | 367 / 1995080 | 0.000183953 | 0.000200548 |
| 10 | 0.00000387211 | 3 / 1995080 | 0.00000150370 | 0.00000388638 |

0–8 dB 实测点和理论值差异与有限样本统计相符。10 dB 仅 3 个误码，点估计不精确；其单侧 95% 上界约等于理论值，因此只报告样本、误码和上界，不声称该点精确估计 BER。

## 5. 复基带与实带通对照

实带通每点配置 500,000 bit，实际比较 498,760 bits（分块边缘舍弃）。下表 BB 是同 Eb/N0 的正式 baseband 结果；PB 是实际 20 kHz 实数载波、实噪声、理想相干混频和匹配滤波所得。

| Eb/N0 (dB) | Theory BER | BB BER (errors/bits) | PB BER (errors/bits) | PB 95% upper |
|---:|---:|---:|---:|---:|
| 0 | 0.0786496 | 0.0784871 (156588/1995080) | 0.0786270 (39216/498760) | 0.0792567 |
| 4 | 0.0125008 | 0.0125494 (25037/1995080) | 0.0124128 (6191/498760) | 0.0126738 |
| 8 | 0.000190908 | 0.000183953 (367/1995080) | 0.000188467 (94/498760) | 0.000223711 |

三点的两种模式均与理论相符；P1 的实带通结果是真实数值载波波形上的离散 AWGN 仿真，不是仅用复基带曲线代替。该模型仍是 P0-C 定义的离散理想相干仿真，不代表无线硬件或连续时间射频设备。

## 6. 实验图表

正式命令：

```bash
MPLCONFIGDIR=/tmp/p1_mpl_cache PYTHONPATH=src \
  python experiments/p1_phy.py \
  --config experiments/p1_phy_config.json \
  --output artifacts/p1_phy
```

- BER 理论、复基带和实带通：[ber_theory_vs_simulation.png](artifacts/p1_phy/ber_theory_vs_simulation.png)
- α=0.2/0.35/0.5 实带通 PSD：[rrc_rolloff_psd.png](artifacts/p1_phy/rrc_rolloff_psd.png)
- 20 kHz 带通时域波形和接收星座：[passband_waveform_constellation.png](artifacts/p1_phy/passband_waveform_constellation.png)
- 完整结果、精确 seed、数值 filter metrics：[p1_phy_summary.json](artifacts/p1_phy/p1_phy_summary.json)
- 实际运行配置副本：[p1_phy_config.json](artifacts/p1_phy/p1_phy_config.json)

以上图由 `experiments/p1_phy.py` 在本轮运行生成，可由相同命令重建。

## 7. 未解决问题与范围限制

- 符号定时、帧起点、载波频率和相位由接收端理想已知；未实现载波/定时恢复、同步搜索、FEC、重传或衰落信道，符合 P0-C P1 范围。
- 实带通 BER 只在 0/4/8 dB 做了与 baseband 对照；10 dB 只做 baseband，避免把昂贵计算扩展成 P0-C 未要求的完整实带通扫点。
- 10 dB 只有 3 个误码，置信范围较宽；若需更精确高 SNR BER，应增加 bit budget 并保留真实误码统计。
- 未实现 P2 的 96-bit 序列化/CRC、OBS/CMD；未接入旧项目、Candidate B 或 MuJoCo。
- PSD 是有限长度随机 QPSK burst 的 Welch 估计，有限 RRC 有旁瓣；图不是严格砖墙带宽证明。

本轮未修改旧项目、未安装依赖、未训练模型、未提交或推送 Git。P1 完成后停止；不自动进入 P2。
