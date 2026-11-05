# P4-A GitHub 仓库与网站素材整理报告

**结论：PARTIAL** — 本地素材整理、数据映射、hash 与媒体检查完成；正式提交和未来公开发布仍需解决许可证/再分发授权，且部分 P3 运行脚本含本机绝对路径。本轮没有 `git add`、commit、push、发布仓库或启用 Pages。

## 1. 仓库现状与体量

- 本地分支：`main`；当前没有本地 commit，所有项目文件尚未进入版本历史。
- `origin` 指向 `https://github.com/suibianba12138/embodied-semantic-communication.git`。
- 本轮未访问 GitHub API；仓库当前可见性和远程体量没有重新核实。先前本地计划文件记录了一次 Private、空仓库检查，该记录可能已过时。
- 初始审查时工作区约 **231,433,760 bytes**；`artifacts/` 约 **164 MiB**。本轮新增素材集中于 `website/assets/`，完整 trace 和原始视频仍留在 `artifacts/`。
- 初始审查时没有 `.gitignore`；根 README 和项目 LICENSE 当前仍缺失。本轮新增了保守的 [.gitignore](.gitignore)，忽略 Python 缓存、虚拟环境、凭据文件模式、模型权重、`artifacts/` 和本地计划文件，不忽略 `website/assets/`。
- 仓库最大单文件扫描未发现超过 GitHub 常规文件 50 MiB 警告门槛的文件。建议白名单最大文件为网站 JSON/同步视频，均小于 2 MiB。
- 初始 `git status` 显示项目代码、文档和 artifacts 均为未跟踪；没有文件被暂存。

## 2. 文件分类与白名单建议

### INCLUDE（技术上适合进入仓库候选集）

- `src/esc/`：QPSK PHY、Wire v1、P3 link helper 和场景几何代码。
- P1/P2 离线实验脚本及小型配置，场景字幕/分屏脚本、工业场景配置、网站资产准备脚本。
- `tests/` 下的测试源码；`requirements-p1.txt`。
- P1 PHY README/报告、P3-S1-V2 报告、本报告、媒体 manifest、无私有路径的工业场景设计说明。
- `website/assets/` 精选视频、图片和展示 JSON。

### CONDITIONAL（先处理路径、依赖或授权）

- `experiments/p3_g1_integration.py`、`experiments/p3_s1_multi_obstacle.py`：包含 Linux home 目录绝对路径，并依赖外部旧项目与 Candidate B 环境；发布前应改为显式配置/环境变量，附可复现安装说明。算法逻辑无需因此改变。
- `P0A_*`、`P0B_*`、`P0C_*`、`G1_EMBODIED_COMM_REUSE_AUDIT.md`、`P2_*` 和早期 P3 审查报告：其中部分文件含本机路径、旧仓库内部路径或依赖文件；当前不纳入建议暂存白名单。可另做公开版脱敏副本。
- Candidate B 代码在既有 P3 报告中标记为 Apache-2.0，但 ONNX 与 G1 资产的单独再分发条款尚未确认；旧项目本身没有 LICENSE/LICENCE 文件。当前候选白名单没有包含旧项目源码、ONNX、机器人 XML/mesh 或虚拟环境。
- 本项目本身没有 LICENSE。仓库所有者需要明确项目原创代码的许可证并确认各自贡献者的发布权。
- 工业视频、封面及场景截图中能看到 G1 模型。即使场景与通信结果由本项目生成，公开展示仍需确认机器人外观/模型资产条款、上游署名要求和衍生录像使用范围。
- 当前只有 `requirements-p1.txt`，它覆盖 NumPy/SciPy/Matplotlib/pytest 的 P1 需求，不覆盖 Candidate B/MJLab/MuJoCo/Warp 的整套运行依赖。未固定的外部环境不应被描述为可开箱复现。

### EXCLUDE（不应纳入初始提交）

- `artifacts/` 全目录、原始完整 traces、调试/失败视频、临时 render、`__pycache__`、`.pytest_cache`、`.venv`、本机凭据/配置、模型权重、ONNX、旧项目仓库及机器人资产。
- `ESC_GITHUB_ASSET_STAGING_PLAN.md` 含本机绝对路径和未核验的远程状态快照，作为本地准备记录保留，不直接发布。

## 3. 正式工业场景视频

源文件全部取自同一正式目录 `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/`，各视频分别与相同 stage 的 `result_wideview.json` 配对。压缩副本保留烧录字幕，不裁切、不重排、不改变 fps；统一使用 H.264/libx264、CRF 23、medium、yuv420p、faststart。原始文件没有音轨，导出不增加音轨。

| 条件 | 源视频大小 | 网站副本大小 | 节省 | 尺寸 / 帧率 | 帧数 / 时长 | 对应数据 |
|---|---:|---:|---:|---|---|---|
| 8 dB AWGN | 1,106,969 B | 820,921 B | 25.8% | 1280×720 / 25 fps | 656 / 26.24 s | `website/assets/data/awgn-8db.json` |
| 无噪声 QPSK | 1,094,782 B | 811,049 B | 25.9% | 1280×720 / 25 fps | 658 / 26.32 s | `website/assets/data/noiseless.json` |
| Ideal Message | 1,096,233 B | 809,330 B | 26.2% | 1280×720 / 25 fps | 658 / 26.32 s | `website/assets/data/ideal.json` |
| 8 dB 同步分屏（可选） | 1,517,741 B | 1,150,415 B | 24.2% | 1784×720 / 25 fps | 656 / 26.24 s | `website/assets/data/awgn-8db.json` |

三个第三人称压缩副本与源视频的整段 SSIM 为 `0.9973–0.9974`；逐一用 `ffprobe` 检查 codec、分辨率、fps、帧数、时长和音轨。8 dB 封面从同 run 带字幕第三人称视频的 21.0 s 提取，状态为 APPROACH；没有换用其他实验版本的画面。

## 4. 网站图片

图片都保存在 `website/assets/img/`。PNG 图表和场景截图以字节相同副本保存，所以没有改曲线、刻度、颜色或像素。8 dB 封面是视频单帧原样 PNG 导出。

| 网站文件 | 来源 |
|---|---|
| `industrial-overview.png` | 正式场景 `s1-0/scene_overview.png` |
| `industrial-front.png` | 正式场景 `s1-0/view_front_three_quarter.png` |
| `industrial-aerial.png` | 正式场景 `s1-0/view_raised_overview.png` |
| `industrial-awgn-8db-cover.png` | 正式 8 dB 字幕视频 21.0 s 帧 |
| `qpsk-ber.png` | P1 `artifacts/p1_phy/ber_theory_vs_simulation.png` |
| `rrc-psd.png` | P1 `artifacts/p1_phy/rrc_rolloff_psd.png` |
| `qpsk-waveform-constellation.png` | P1 `artifacts/p1_phy/passband_waveform_constellation.png` |
| `semantic-frame-metrics.png` | P2 `artifacts/p2_semantic/p2_end_to_end_metrics.png`（含帧接收/语义恢复指标） |

## 5. 精简展示 JSON 与视频同步

生成 `ideal.json`、`noiseless.json`、`awgn-8db.json`，逐个只读取正式场景对应的 P3-S1-V2 `result_wideview.json`。数据字段来自源 trace，未补造缺失字段。

每个 JSON 保留：

- `condition`：实际运行标签、Eb/N0（源值为空时仍为空）、scenario、seed、目标颜色和实际布局随机化配置。
- `summary`：任务成功/终止、路径长度、目标最终 range/bearing、PHY bit/BER/FER、帧接受率、正确/错误语义接受数、reject 分类、command hold/TTL 超时计数、障碍物接触和距离采样统计。
- `events`：每一条 OBS/CMD link event，保留上/下行方向、TX/RX/采集时间、96-bit TX/RX bit string、bit error、接收状态、已接受消息及 episode-end 投递标记。拒帧不抽样、不省略。
- `ticks`：每个真实 policy tick 的时间、控制器状态、原始/控制器输入中的观测值（仅保留源字段）、实际应用命令、发送/接收命令、command age、hold/expired、OBS/CMD 状态、机器人位置/偏航和 fall 标志。
- `video_clock.frame_map`：每个视频帧的 frame index、视频时间、原始 trace index/step 和对应仿真时钟值。与字幕生成脚本相同，帧 `i` 对应 `trace[i*2]`，仿真时刻为该行 `time_s - 0.02 s`。R2 视频末帧 26.20 s、视频 duration 26.24 s，差异来自视频帧周期，不是另一组 trace。

| 数据 | 原始 trace | 导出 JSON | policy ticks | video frames | OBS/CMD events | 所有 reject |
|---|---:|---:|---:|---:|---:|---:|
| Ideal | 3,834,337 B | 1,427,475 B | 1316 | 658 | 527 | 0 |
| 无噪声 QPSK | 3,992,388 B | 1,484,543 B | 1316 | 658 | 527 | 0 |
| 8 dB AWGN | 3,975,415 B | 1,478,082 B | 1311 | 656 | 525 | 11（CRC 7、Preamble 4） |

每组是一对一 video/data 对应关系；来源 trace hash、来源视频 hash、导出媒体 hash 和数据 JSON hash 均写在 manifest 和下方表格。原始 trace 和正式 P3 工件保持原处未改。

## 6. 源文件与导出文件 SHA256

以下表列出每个网页素材的源与导出字节数及完整 SHA256。详细 codec、尺寸、格式、处理方式和 run 映射也见 [WEBSITE_MEDIA_MANIFEST.json](WEBSITE_MEDIA_MANIFEST.json)。

| 类型 / 条件 | 源文件（字节） | 源 SHA256 | 导出文件（字节） | 导出 SHA256 |
|---|---|---|---|---|
| run_data / ideal | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-1/result_wideview.json` (3834337 B) | `4512fb5c166d5f2ae4ed4627eefad1621cb4c85636b834a3869a4eaecb69df32` | `website/assets/data/ideal.json` (1427475 B) | `578bed9912df85d79368c3e8d4c096d89b14226a29960dd02588c9fe930d11b7` |
| video / ideal | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-1/s1-1_B_-30deg_seed0_captioned.mp4` (1096233 B) | `844aeef38fd82f60e27dd83a1ac0816039097aa3e530f2bada8fa8dafa3e2ac7` | `website/assets/video/industrial-ideal.mp4` (809330 B) | `c7fbaea4dd75f50e0cf321ca847d8ecbe4de8b5acbff7b1c8f263cdc06e94cff` |
| run_data / noiseless | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-2/result_wideview.json` (3992388 B) | `773fff0c7db441d397dbb3da85c14d938ac677320cc785c7a620709042774203` | `website/assets/data/noiseless.json` (1484543 B) | `7ec88d98d427ed2fdd21541aa68db630b7cba102c4ac1b7439772d88e32125a8` |
| video / noiseless | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-2/s1-2_B_-30deg_seed0_captioned.mp4` (1094782 B) | `786eb29e81829c96f208222d60a77a98732e7b3e8614515108f1320706a0d688` | `website/assets/video/industrial-noiseless.mp4` (811049 B) | `67181c2fd91d9c77dfdcb19a1a2d6e34c366b655e47da0fada519a5cfe28eae0` |
| run_data / awgn-8db | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/result_wideview.json` (3975415 B) | `ffe653697f5c13ae242fd94e589762743609bf6215eb5d418e61ebeea28d18c2` | `website/assets/data/awgn-8db.json` (1478082 B) | `89f93e6f0fb1e58e943f588e77e94e72fe9496d853d4fc8c5a827f82a53b9282` |
| video / awgn-8db | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/s1-3_B_-30deg_seed0_captioned.mp4` (1106969 B) | `8a5769769decf0fa5aa922a89d9b3b66b3be580964e4e7a5a34142318ca95ba3` | `website/assets/video/industrial-awgn-8db.mp4` (820921 B) | `a896b141533be0fc051cef7516771730538685902e03fc53edce9a3f6ebcbe21` |
| video / awgn-8db | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/s1-3_B_-30deg_seed0_split_view.mp4` (1517741 B) | `8c2d1e0d634249371bbda6c6f402471550139306eb70798e1ea2876c9bdfba4c` | `website/assets/video/industrial-awgn-8db-split.mp4` (1150415 B) | `7647b3c65cec7c4cfd7d7d5d639407854a14501916543cc8f74d1b77bcab4b3a` |
| image / industrial-overview.png | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/scene_overview.png` (254760 B) | `927b15c140cdfe3a63ad1c35171362446b75905a8860a4e18fc6cd7f51195fa5` | `website/assets/img/industrial-overview.png` (254760 B) | `927b15c140cdfe3a63ad1c35171362446b75905a8860a4e18fc6cd7f51195fa5` |
| image / industrial-front.png | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/view_front_three_quarter.png` (250604 B) | `c8b35697ecddb281e102a84b6900ab8797afc7375461ea8c3b87c55bf56e1482` | `website/assets/img/industrial-front.png` (250604 B) | `c8b35697ecddb281e102a84b6900ab8797afc7375461ea8c3b87c55bf56e1482` |
| image / industrial-aerial.png | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-0/view_raised_overview.png` (282398 B) | `cc6e2253c9a27a66f12671663d4847e3965e500241644a8e71b6096936ccb86b` | `website/assets/img/industrial-aerial.png` (282398 B) | `cc6e2253c9a27a66f12671663d4847e3965e500241644a8e71b6096936ccb86b` |
| image / qpsk-ber.png | `artifacts/p1_phy/ber_theory_vs_simulation.png` (90791 B) | `144ee28039fd70be1dd230d153a20747a18c62468d4a79125079cd2eb438ad16` | `website/assets/img/qpsk-ber.png` (90791 B) | `144ee28039fd70be1dd230d153a20747a18c62468d4a79125079cd2eb438ad16` |
| image / rrc-psd.png | `artifacts/p1_phy/rrc_rolloff_psd.png` (224117 B) | `91194f0282316cf0dfd9e5f1757e8aa64361ee56a9ab54443a5a796ec2c2b221` | `website/assets/img/rrc-psd.png` (224117 B) | `91194f0282316cf0dfd9e5f1757e8aa64361ee56a9ab54443a5a796ec2c2b221` |
| image / qpsk-waveform-constellation.png | `artifacts/p1_phy/passband_waveform_constellation.png` (221635 B) | `59686b31d4cd334229e2892398fe92fb3788b419a59995be49cc1857b093906d` | `website/assets/img/qpsk-waveform-constellation.png` (221635 B) | `59686b31d4cd334229e2892398fe92fb3788b419a59995be49cc1857b093906d` |
| image / semantic-frame-metrics.png | `artifacts/p2_semantic/p2_end_to_end_metrics.png` (105534 B) | `1e9306ec6b84dafdea54df9de0ca8065d096f540db646c0933d824941033d00f` | `website/assets/img/semantic-frame-metrics.png` (105534 B) | `1e9306ec6b84dafdea54df9de0ca8065d096f540db646c0933d824941033d00f` |
| video_cover / awgn-8db | `artifacts/p3_s1_v2_industrial/randomized_seed_20261105/s1-3/s1-3_B_-30deg_seed0_captioned.mp4` (1106969 B) | `8a5769769decf0fa5aa922a89d9b3b66b3be580964e4e7a5a34142318ca95ba3` | `website/assets/img/industrial-awgn-8db-cover.png` (388822 B) | `b64a34c10e78722204920d4e36a6293a4ebc7dd513916c3d369e5c5890843909` |

## 7. GitHub 安全与发布风险

- 敏感信息检查仅报告扫描结果，不输出任何匹配值：没有发现凭据赋值/私钥 block；没有发现 `.env`、私钥或 token/credential 类文件名。该检查属于基于模式的本地扫描，不能替代上线前 secret scanner。
- Linux home 目录绝对路径存在于 P0A/P0B/P0C、复用审查、P2/P3 历史报告/README 和 P3 runner 中；建议白名单刻意避开这些原件。新的 website 数据、media manifest、P3-S1-V2 交付报告和资源路径使用项目相对路径。
- `git status` 没有已暂存或已提交内容；本轮的暂存清单只是建议，并没有执行 `git add`。
- 项目许可证、Candidate B ONNX/G1 资产以及视频/截图的公开展示权限尚未解决。因仓库未来可能公开，素材可本地预备，但在得到明确再分发授权并确定本项目许可证前，不应切换为 Public 或启用公开 Pages。

## 8. 精确建议暂存白名单

下面是建议的 **43-file technical candidate whitelist**（包含本报告本身，合计 `9997769` bytes；仅用于后续人工复核）。命令没有执行。白名单不包含整个 `artifacts/`，也不包含有本机路径的 P3 MuJoCo launcher；发布 G1 复现流程前需先完成路径参数化和依赖说明。

```bash
git add -- \
  .gitignore \
  P1_PHY_README.md \
  P1_PHY_IMPLEMENTATION_REPORT.md \
  P3_S1_V2_INDUSTRIAL_SHOWCASE_REPORT.md \
  P4_REPOSITORY_ASSET_PREP_REPORT.md \
  WEBSITE_MEDIA_MANIFEST.json \
  requirements-p1.txt \
  docs/superpowers/specs/2026-11-05-industrial-showcase-design.md \
  src/esc/__init__.py src/esc/phy.py src/esc/frame.py src/esc/p3_link.py src/esc/p3_s1_scene.py \
  experiments/p1_phy.py experiments/p1_phy_config.json \
  experiments/p2_semantic.py experiments/p2_semantic_config.json \
  experiments/p2_r1_recheck.py experiments/p2_r1_config.json \
  experiments/p3_s1_v_overlay.py experiments/p3_s1_v2_industrial_config.json \
  experiments/prepare_website_assets.py \
  tests/test_phy.py tests/test_frame.py tests/test_p2_experiment.py \
  tests/test_p2_r1_recheck.py tests/test_p3_link.py tests/test_p3_s1_scene.py \
  website/assets/data/ideal.json website/assets/data/noiseless.json website/assets/data/awgn-8db.json \
  website/assets/img/industrial-overview.png website/assets/img/industrial-front.png \
  website/assets/img/industrial-aerial.png website/assets/img/industrial-awgn-8db-cover.png \
  website/assets/img/qpsk-ber.png website/assets/img/rrc-psd.png \
  website/assets/img/qpsk-waveform-constellation.png website/assets/img/semantic-frame-metrics.png \
  website/assets/video/industrial-awgn-8db.mp4 website/assets/video/industrial-noiseless.mp4 \
  website/assets/video/industrial-ideal.mp4 website/assets/video/industrial-awgn-8db-split.mp4
```

这只是推荐文件集合，不代表当前已获得内容许可，也不代表所有文件适合直接公开。投稿前应由仓库所有者确认本项目 LICENSE、G1 相关再分发权、署名和根 README/依赖说明；如任何权利不能确认，应从暂存白名单移除对应视频/截图。

## 9. 结论

- 本地网站资产准备与 trace 对应：**PASS**。
- 源/导出 hash 和视频 metadata 检查：**PASS**。
- 文件安全、许可证和公开再分发准备：**PARTIAL**。
- 最终：**PARTIAL**。所有要求的本地素材和清单已生成，但授权和若干本机路径问题仍是正式公开前置条件。本轮无旧项目修改、仿真重跑、网页开发、Git staging/commit/push 或 Pages 操作。
