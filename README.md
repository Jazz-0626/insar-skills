# insar-skills

两个用于 **InSAR / SAR 同震形变与断层滑移反演** 的 [Claude Code](https://claude.com/claude-code) 技能（skills）。封装了从像素偏移追踪到断层滑移反演的完整、可复现工作流，便于在 Claude Code 里直接调用。

| 技能 | 作用 |
|------|------|
| [`pot-workflow`](pot-workflow/) | Sentinel-1 / LT-1 / ALOS-2 **像素偏移追踪 (POT)**：`xcorr_cc` 互相关 → 物理过滤 → 地理编码 → 去趋势 → GMT 成图 |
| [`sdm-inversion`](sdm-inversion/) | **SDM2025 断层滑移反演**：形变场 → quadtree 降采样 → 写 inp → 反演（单/多段、两阶段 DMCF+WBF）→ 2D/3D/map-view 成图 → 棋盘/分辨率测试 → PSGRN/PSCMP 同震库仑应力变化（ΔCFS）计算与 GMT 成图 |

## 安装

每个技能是一个独立目录（含 `SKILL.md` 及其 `scripts/` `templates/` `reference/`）。装进 Claude Code 的技能目录即可：

```bash
git clone https://github.com/<your-username>/insar-skills.git
# 拷贝（或软链）到个人技能目录
cp -r insar-skills/pot-workflow   ~/.claude/skills/
cp -r insar-skills/sdm-inversion  ~/.claude/skills/
# 或软链以便随仓库更新：
# ln -s "$PWD/insar-skills/pot-workflow"  ~/.claude/skills/pot-workflow
# ln -s "$PWD/insar-skills/sdm-inversion" ~/.claude/skills/sdm-inversion
```
之后在 Claude Code 中用 `/pot-workflow`、`/sdm-inversion` 触发，或让模型按需调用。

## 依赖（第三方软件，本仓库不分发）

这些技能编排现成的科学软件，需自行安装并放入 PATH / 配好路径：

| 依赖 | 用于 | 获取 |
|------|------|------|
| **GMTSAR** + **GMT (≥6)** | POT 地理编码、绘图 | <https://github.com/gmtsar/gmtsar> |
| **xcorr_cc** | POT 的 CUDA 互相关与 `pot_*.csh` 后处理 | 配套仓库 `xcorr_cc`（按其 README 编译，需 CUDA GPU + glib） |
| **SDM2025** | 断层滑移反演内核（Rongjiang Wang, GFZ） | 向作者 / GFZ 索取（非自由软件，勿转发） |
| **PSGRN/PSCMP 2020** | 库仑应力变化计算（仅 sdm-inversion 阶段 7 需要；同作者） | GitHub 搜 "PSGRN-PSCMP" 或向作者索取，`gfortran -o psgrn2020 *.f -O3` 编译 |
| **Python 环境** | 降采样 / 成图 / 棋盘测试脚本 | `numpy rasterio pyshp matplotlib`（推荐 conda；3D 图需原生 mplot3d） |

> 技能里的脚本/模板用 `$SDM2025`、`$SDM`、`$PY`、`$SKILL`、`$WORK` 等环境变量约定路径，不含任何机器特定绝对路径——使用前 `export` 好这些变量即可。

## 验证环境

本仓库脚本在以下环境端到端验证通过：Ubuntu，GMT 6.3.0 + GMTSAR，CUDA 12.2 / RTX 4090 (sm_89)，Python（numpy/rasterio/pyshp/matplotlib）。`sdm-inversion` 的全部 Python 脚本可正常字节编译；POT 链路与 SDM 反演链路均在真实数据（2025 定日 Mw 7.1 地震）上跑通。

## 案例

两技能均源自并验证于 **2025 定日 Mw 7.1 地震** 的多源 SAR 形变分析：LT-1/Sentinel-1 POT + Sentinel-1 InSAR 三维形变 → SM-VCE 融合 → SDM2025 单段直线反演（Mw 6.86）→ 棋盘/单块分辨率测试。

## 许可

见 [`LICENSE`](LICENSE)。第三方软件（GMTSAR、SDM2025 等）各自遵循其原始许可，不在本仓库分发。
