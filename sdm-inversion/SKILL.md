---
name: sdm-inversion
description: SDM2025 断层滑移反演完整工作流 — 从已有 ENU/LOS 形变场(grd/tif) → quadtree 降采样 → 写 inp → 反演(单段/多段、可选两阶段 DMCF+WBF 走廊策略) → 2D/3D/map-view 成图 → 棋盘/分辨率测试(固定尺度棋盘 + 手动放置单块)。用于同震/震后断层滑移分布反演与分辨率验证。
---

## SDM 断层滑移反演工作流

用 **SDM2025**(Rongjiang Wang，最速下降法 + 均匀半空间 Okada / 分层 / 用户 3D 格林) 从形变场反演断层滑移分布。涵盖：**已有形变场 → 后处理降采样 → 写 inp → 反演 → 成图** 全过程。

### 适用场景
- 已有 ENU 三维形变场(SM-VCE 等)或 LOS 形变场(grd/tif)，要反演断层滑移分布
- 单段 / 多段曲线断层；可选**两阶段**：主断层(DMCF)反演 → 残差 → 共轭/次级断层(WBF)走廊隔离反演
- 需要 2D 滑移剖面、3D 透视、map-view(DEM+迹线+余震) 出版级图件
- **分辨率/棋盘测试**(方法学验证)：固定尺度交替棋盘，或在任意走向/深度窗口手动放置单块、块内滑移取真实数据均值，正演+加噪+反演看恢复率

### 依赖与路径(自行配置)
| 项 | 说明 / 如何获得 |
|----|------|
| **sdm2025 可执行** | **第三方软件**(Rongjiang Wang, GFZ)，本仓库不分发。向作者/GFZ 索取 SDM2025 包，解压后记下 `$SDM2025/sdm2025`(Linux)；源码 `$SDM2025/SourceCode/*.f`、示例 `$SDM2025/InputFile/sdm2025_example_1/` |
| ZHYRELAX.txt | SDM2025 包内自带的松弛因子序列文件，拷到工作目录即可(也可用示例里的) |
| 本 skill 脚本 / 模板 / 参考 | 安装后位于 `<skill>/scripts/`、`<skill>/templates/`、`<skill>/reference/sdm_io_format.md`(见仓库根 README 的安装说明) |
| python 环境 | 任一含 `numpy / rasterio / pyshp / matplotlib`(原生 mplot3d) 的环境(推荐 conda)。下文 `PY` 指该环境的 python |
| 约定变量 | `SDM=$SDM2025/sdm2025`、`PY=<env>/bin/python`、`WORK=<干净工作目录>`；出图 `export MPLBACKEND=Agg` |

### 脚本清单(`scripts/`)
| 脚本 | 用途 |
|------|------|
| `prepare_data.py` | 形变场(grd/tif) → quadtree 自适应降采样 → SDM 数据文件(lat lon disp err) |
| `build_offset_grns.py` | 由各数据文件点数生成 ENU 常数 offset 的 corrgrn(`offset_grns.dat`) |
| `clip_residual_by_trace.py` | 沿断层迹线 ±D km 走廊裁剪残差(两阶段 WBF 用) |
| `plot_slip_2d.py` | 沿走向×深度 2D 滑移剖面(自动分段、含滑移矢量) |
| `plot_slip_3d.py` | 3D 透视(单/多断层) |
| `plot_map_view.py` | map-view(DEM 山影 + 投影 patches + 迹线 + 余震) |
| `checker_make_slip.py` | 棋盘真值构造：`cells`(固定尺度交替棋盘) 或 `block`(手动窗口单块、块内滑移默认取真实数据均值) |
| `checker_add_noise.py` | 由 SDM 正演输出 + 高斯噪声生成合成观测(σ 用真实场远场 std，可 ENU/LOS 通用)，打印 SNR |
| `checker_compare.py` | 多 case 真值/反演对比图(每行独立色条 + 块虚线框 + 恢复率/相关) |
| `checker_run.sh` | 单 case 一键：构造真值 → 正演 → 加噪 → 反演(env 参数化，可复用任意断层) |

---

## 工作流(5 阶段)

> 约定：先 `export` 好 `WORK`(干净工作目录)、`SDM`(=`$SDM2025/sdm2025`)、`PY`(目标 python)、`SKILL`(本 skill 的 `scripts/` 目录，安装见仓库根 README)；在 `$WORK` 内操作；出图必须 `export MPLBACKEND=Agg`(无显示环境)。

### 阶段 1 — 准备数据(形变场 → SDM 数据文件)
SDM 数据文件为 **4 列 `lat lon disp err`、无 header**(`err>0`，权重=1/err²)。用 quadtree 自适应降采样把稠密形变场降到 ~5000 点/数据集。

```bash
cd $WORK
# ENU 三维场(默认): enu_north→ns.dat, enu_east→ew.dat, enu_up→up.dat
$PY $SKILL/prepare_data.py \
    --src-dir /path/to/3D_field/geotiff --out-dir $WORK --target 5000
# LOS 场: 用 --comp 自定义 "源文件:输出名:err下限:err上限"
$PY $SKILL/prepare_data.py \
    --src-dir /path --out-dir $WORK \
    --comp "los_asc.grd:los_asc.dat:0.01:0.05" --comp "los_des.grd:los_des.dat:0.01:0.05"
```
- 支持 `.grd`(GMT netcdf，经 GDAL)与 `.tif`。`err = 块内 std/√n`，按分量上下限截断(ENU 默认 ns/ew[0.02,0.10]、up[0.04,0.12])。
- 若用 ENU 常数 offset 修正：生成 corrgrn(顺序须与 inp 中数据文件顺序一致 ns,ew,up)：
```bash
$PY $SKILL/build_offset_grns.py ns.dat ew.dat up.dat > offset_grns.dat
```
- 拷松弛因子：`cp $SDM2025/.../ZHYRELAX.txt $WORK/`(用 SDM2025 包内自带的；示例目录里也有)

### 阶段 2 — 写 inp
从 `templates/sdm_dmcf.inp.template`(多段/单段、ENU 三数据 + offset)或 `sdm_los.inp.template`(LOS 双轨)起改。**inp 格式详解见 `reference/sdm_io_format.md`**。要点：
- `iearth=0`(半空间) `poisson=0.25` `idisc=1`(自动离散)；
- 每段：`topdep width strike(-1000=自动) patchsize` / `rake1 rake2 max_slip` / `nft` / 各节点 `lat lon topdip botdip`；
- 迹线节点直接来自 shapefile(用 `ogrinfo -al` 或 pyshp 读)；`topdip>botdip`=antilistric(反铲)；
- 数据块：`ngd datunit nheader` 后每个数据集 `'file.dat'` + `weight type[ inc azi]`(type=1 常数 LOS；ENU 用 inc/azi 编码：N=90/0、E=90/90、U=0/0)；
- offset：`nusrp 'offset_grns.dat'` + 每参数 `min max`；
- 收尾：`niter 'ZHYRELAX.txt'` / `ismooth smoothing izhy`(ismooth=1 滑移平滑) / slip 输出名 / 三/二个 data-fit 输出名。
- **禁止空行；`#` 开头为注释**。

### 阶段 3 — 反演
```bash
echo 'sdm_dmcf.inp' | "$SDM" > stdout_dmcf.log 2>&1
tail -25 stdout_dmcf.log    # 看 Mw / data-model correlation / 各段 mean&max slip&rake / 应力
```
**质检**：`data-model correlation` 应接近 1(>0.9 好)；负相关=拟合噪声/几何反号(见下"陷阱")。检查 max-slip 是否触 cap、滑移峰深度是否物理(浅源应在 0–8km)。

### 阶段 4 —(可选)两阶段 WBF 走廊反演
主断层(DMCF)反演后，用残差反演共轭/次级断层(WBF)，**仅用 WBF 迹线附近走廊内的点**以隔离 DMCF 系统残差污染。
```bash
# 4a 提取真实残差(= output col3-col5-col6；陷阱:col4不含correction)
for c in ns:un ew:ue up:uz; do d=${c%%:*}; o=${c##*:};
  awk 'FNR==NR{e[FNR]=$4;next} FNR>1{i=FNR-1;printf"%.8f %.8f %.6f %.4f\n",$1,$2,$3-$5-$6,e[i]}' \
    $d.dat output_u$o.dat > ${d}_res.dat; done
# 4b 沿 WBF 迹线 ±10km 走廊裁剪
$PY $SKILL/clip_residual_by_trace.py \
    --trace WBF.shp --dist 10 --comps ns ew up --work $WORK
# 4c WBF 反演(数据用 *_res_w10.dat) + 合并
echo 'sdm_wbf.inp' | "$SDM" > stdout_wbf.log 2>&1
head -1 slip_model.dat > slip_model_merged.dat
tail -n +2 slip_model.dat >> slip_model_merged.dat
tail -n +2 wbf_slip.dat  >> slip_model_merged.dat
```

### 阶段 5 — 成图
```bash
export MPLBACKEND=Agg; mkdir -p figs
# 脚本在 cwd 输出固定名(slip_distribution.*)，多图时进各自子目录再 mv 改名，$SKILL 用绝对路径更稳
$PY $SKILL/plot_slip_2d.py slip_model.dat   # 2D(自动分段)
$PY $SKILL/plot_slip_3d.py slip_model_merged.dat  # 3D(单/多断层)
$PY $SKILL/plot_map_view.py \
    --slip slip_model_merged.dat --dem dem.tif --traces DMCF.shp WBF.shp \
    --aftershocks Aftershocks.txt --out figs/slip_map_view.png
```
- `plot_slip_2d.py`/`plot_slip_3d.py` 取 slip 文件为第一参数；2D 输出 `slip_distribution.png/pdf`、3D 输出 `slip_distribution_3d.png/pdf`(在 cwd，自行 mv 改名)。
- map-view 的 DEM：若只有 `dem.grd`，先 `gdal_translate dem.grd dem.tif`。
- **slip 文件 16 列**含义见 reference(col8 走滑、col9 倾滑[正断>0]、col10 幅值、col11 走向、col12 倾角、col13 rake)。

### 阶段 6 —(可选)棋盘 / 分辨率测试(方法学验证)
检验"数据 + 几何"能分辨多大尺度 / 哪些位置的滑移。思路：在**真实反演的网格**(`slip_model.dat`)上构造已知合成滑移 → SDM 正演到真实观测点位 → 加与真实场同量级的噪声 → 用**同几何同平滑**反演 → 看恢复率。独立子目录(如 `Checkerboard/`)，每个 case 一个子目录。

**两种构造模式(`checker_make_slip.py`)**：
- `cells` 固定尺度**交替棋盘**(经典)：`--cell C --amp A`，整面断层 C×C km 单元交替纯正断 A m；扫多个 C 画"恢复率–棋盘尺寸"曲线。
- `block` **手动放置单块**：`--xmin/--xmax/--zmin/--zmax` 指定走向/深度窗口，块内滑移**默认取真实数据在该窗口的均值**(走滑+倾滑、保留 rake)，可 `--strk/--ddip` 覆盖；用于论证某尺寸/某位置的滑移特征能否分辨。

**先备两个 inp**：从生产 `sdm_dmcf.inp` 派生 `sdm_checker_forward.inp`(niter=0、nusrp=0、数据文件用真实 ns/ew/up 绝对路径只取点位、slip 行=`slip_dmcf_runtime.dat` 为输入、输出 `fwd_*`)与 `sdm_checker_invert.inp`(数据=`*_synth.dat`、nusrp=0、输出 `slip_dmcf_inverted.dat`/`inv_*`)。模板见 `templates/sdm_checker_{forward,invert}.inp.template`(改绝对路径与几何后即用)。

**一键跑一个 case**(`checker_run.sh`，env 参数化 → 可复用任意断层)：
```bash
export SDM=$SDM2025/sdm2025 PY=<env>/bin/python SKILL=<skill>/scripts
export SRC=$WORK/slip_model.dat FWD=$WORK/sdm_checker_forward.inp INV=$WORK/sdm_checker_invert.inp
export NOISE="--map un:ns:0.107 --map ue:ew:0.023 --map uz:up:0.018"   # SHORT:OUT:sigma(m)，σ=真实场远场 std
bash $SKILL/checker_run.sh block1_s0-30_z0-10 block --xmin 0 --xmax 30 --zmin 0 --zmax 10
bash $SKILL/checker_run.sh cell8 cells --cell 8 --amp 2.0
```
**出图 + 恢复率**(`checker_compare.py`，多 case 一张；block 给窗口画虚线框，cells 省略窗口)：
```bash
$PY $SKILL/checker_compare.py \
   --case "block1_s0-30_z0-10:0,30,0,10:Block 1" \
   --case "block2_s40-end_z2-7:40,48,2,7:Block 2" \
   --out figs/manual_blocks_summary.png
```
**判读**：① `checker_add_noise.py` 打印的 **SNR<~1** 说明该分量地表信号在噪声级以下、该处不可分辨(恢复率再高也不可信)；② 恢复率 = 块内平均反演/块内平均真值；leakage(块外平均)被全断层稀释会偏乐观，务必结合**图上的虚假斑块与深部下涂**判读；③ 弱约束区(端部/深部)即便位置可辨，深度/幅度也不可靠。
- 参考实现:定日 `Checkerboard/case_manual_block/`(block1 中部浅源恢复 88% 干净；block2 远 NE 深角 SNR≈0 仅位置可辨) 与 `case_2026_single3D/`(cell 5/8/10/12 扫描)。

---

## 关键陷阱与经验(务必读)

1. **残差公式**：data-fit 输出 `output_u*.dat` 的 **col4 = obs − slip_pred，不含 correction**；SDM 内部真实残差 = `col3 − col5 − col6`。两阶段 WBF 必须用真实残差，否则 correction 信号(每点+offset)污染残差 → 次级断层 Mw 被高估。

2. **负的 data-model correlation = 危险信号**：模型在拟合噪声或几何系统反号。例:正断层若走廊残差为净抬升(与正断所需沉降反号)→ 强负相关，说明该断层**在此数据下不可分辨**，不要强行合并(会把噪声当滑移注入)。先查残差量级/符号是否有该断层应有的相干信号。

3. **深部虚假滑移(底边堆积)**：弱约束段(数据稀疏的端部)或迹线**急弯**处，反演会把滑移堆到断层面最深边缘(可触 cap、深度远超物理破裂深度)。调宽度/平滑/分量权重通常**只搬不消**。根治：① 缩短断层使其不伸入弱信号区；② **急弯改为单段直线**(单段曲线在急弯处离散畸变)；③ 宽度收到物理破裂深度对应值(如 0–8km 用 width≈10–12km)。诊断:看 stdout 的 `pos_z`(max-slip 深度)与 `pos_lat`。

4. **分段 vs 单段**：参数全同的多段 ≈ 单段曲线(SDM 都按迹线离散)，分段主要用于输出分段 slip(s0i_*)与分段 rake 统计。**急弯优先单段直线**避免交汇/急弯伪影。

5. **rake 触界**：若 max-slip 的 rake 落在 [rake1,rake2] 边界，说明 rake 范围在约束解；据需放宽。

6. **绘图环境**：①无显示必须 `MPLBACKEND=Agg`；②`plot_slip_3d.py` 用原生 mplot3d(smvce_tiff 自带)，旧脚本若有指向 `~/.local/python3.10` 的 mpl_toolkits 硬编码会在别的 python 下失效——本 skill 版已改"原生优先"；③ 2D 分段检测按 `x_local` 负跳变，短段(<10km)需把阈值设到 `dx<-5` 或更小(本 skill 版默认 -5)。

7. **inp 严格**:无空行、`#` 注释、路径相对 cwd、`mean_strike=-1000` 自动走向、`topdip>botdip` 反铲。

---

## 参考实现 / 案例
2025 定日 Mw 7.1 地震：3 分量 ENU(SM-VCE) → 单段直线 DMCF 反演 → Mw 6.86、最大滑移 ~4.5 m@4 km 浅源；WBF 共轭段在该数据下负相关不可分辨(教训见上)。分辨率测试见阶段 6：中部浅源 30×10 km 块恢复 88%、远端深部块处于噪声级。该端到端流程即本 skill 各脚本/模板的来源与验证。
