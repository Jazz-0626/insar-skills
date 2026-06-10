---
name: pot-workflow
description: Sentinel-1 像素偏移追踪 (POT) 完整工作流 — xcorr_cc → 物理过滤 → 地理编码 → 去趋势 → GMT 成图。用于地震/冰川/滑坡形变场提取。
---

## POT (Pixel Offset Tracking) 工作流

### 适用场景
- Sentinel-1 TOPS IW（及 LT-1 / ALOS-2 条带）像素偏移追踪（振幅互相关）
- 同震形变场、冰川流速、滑坡位移提取
- 需要从 SLC 影像对 → `freq_xcorr.dat` → 地理编码偏移场 → GMT 图的完整流程

### 依赖与部署
| 依赖 | 用途 | 获取 / 验证 |
|------|------|-------------|
| **xcorr_cc** + `pot_geocode.csh` + `pot_merge.csh` | CUDA 互相关 + 后处理/拼接 | 配套仓库 **xcorr_cc**（见其 README 编译；把可执行与两个 `.csh` 放进 PATH） |
| **GMTSAR**（`proj_ra2ll.csh` 等，需在 PATH） | 地理编码、PRM/trans.dat | 已验证 GMTSAR + GMT 6.3.0 |
| CUDA GPU | 跑 xcorr_cc | 已验证 RTX 4090 (sm_89), CUDA 12.2 |

> 约定：下文假设 `xcorr_cc`、`pot_geocode.csh`、`pot_merge.csh`、GMTSAR 工具均已在 PATH。xcorr_cc 的参数选取（nx/ny/xsearch/各卫星推荐方案）详见 xcorr_cc 仓库 README，本文只给 POT 编排。

### 脚本清单（均来自 xcorr_cc 配套仓库）
| 脚本 | 用途 |
|------|------|
| `xcorr_cc master.PRM aligned.PRM [opts]` | CUDA 加速二维互相关 → `freq_xcorr.dat` |
| `pot_geocode.csh nx ny master.PRM trans.dat [snr xsearch ysearch ri]` | SNR+边界过滤 → blockmedian 网格化 → 像素转米 → `proj_ra2ll.csh` 地理编码 |
| `pot_merge.csh north_dir south_dir output_dir` | 南北两帧地理编码偏移场重叠区估偏置→校正→blockmedian 融合 |

---

### 工作流步骤

#### 1. 目录设置
```bash
mkdir -p intf/{date1}_{date2}/pot
cd intf/{date1}_{date2}/pot
ln -s ../../../raw/S1_{date1}_*_F{1,2,3}.SLC .
ln -s ../../../raw/S1_{date2}_*_F{1,2,3}.SLC .
ln -s ../../../topo/trans.dat .
cp ../../../topo/*.PRM .
```
SLC 须已配准（GMTSAR `p2p` 的 align 步骤产物）；`trans.dat` 来自 `topo/`。

#### 2. 参数选取
- nx ≈ `SLC_width/8`，ny ≈ `SLC_lines/8`（具体随采样密度；各卫星推荐 nx/ny/xsearch 见 xcorr_cc README 的“卫星参数推荐”表）。
- `xsearch/ysearch` 由预期最大形变量决定（2 的幂：32/64/128/256）。
- 已配准影像测残余形变 → 加 `-noshift`（忽略 PRM 的 rshift/ashift）。
- **关键**：`pot_geocode.csh` 的 `nx ny xsearch ysearch ri` 必须与 `xcorr_cc` 完全一致。
- 预计运行时间：RTX 4090 上约 1.5–2.5 小时处理 ~4000 万点（xsearch=64）。

#### 3. 运行互相关
```bash
# 单帧（示例: S1-B 标准密度，影像 25792×13536）
xcorr_cc master.PRM aligned.PRM -nx 3173 -ny 13151 -xsearch 64 -ysearch 64 -noshift
# 产物: freq_xcorr.dat  （列: x_pix x_off y_pix y_off corr）
```

#### 4. 后处理 + 地理编码（pot_geocode.csh）
```bash
# nx ny 与第 3 步一致；snr=相关阈值(默认10)，xsearch/ysearch/ri 与 xcorr_cc 一致
pot_geocode.csh 3173 13151 master.PRM trans.dat 10 64 64 2
```
脚本内部完成：
- **物理/边界过滤**：相关 `>snr`，且偏移未触搜索窗边界（`|rng|<xsearch/ri-2`、`|azi|<ysearch-2`）；
- **网格化**：`blockmedian -Wi`（相关加权中值）→ `xyz2grd`（雷达坐标网格）；
- **像素 → 米**：azi `× ground_vel/PRF`、rng `× c/(2·rng_samp_rate)`（自 PRM 计算）；
- **地理编码**：`proj_ra2ll.csh trans.dat {azi,rng}_offset.grd …_ll.grd`。
- 产物：`azi_offset_ll.grd`、`rng_offset_ll.grd`（地理坐标）。

可选去趋势（去除轨道/电离层平面漂移，远场归零）：
```bash
gmt grdtrend azi_offset_ll.grd -N1 -Dazi_detrended_ll.grd   # GMT6: 用 -D 输出残差
gmt grdtrend rng_offset_ll.grd -N1 -Drng_detrended_ll.grd
```

#### 5.（多帧）轨道拼接（pot_merge.csh）
南北两帧各自跑完第 3–4 步后：
```bash
pot_merge.csh north_pot_dir south_pot_dir merged_out
# 对 azi_offset / rng_offset / snr 各分量产出 *_merged.grd（重叠区估偏置并校正南帧）
```

#### 6. 成图（GMT，自备脚本/命令）
本 skill 不附带绘图脚本；用 GMT 直接出图，例：
```bash
gmt begin pot_range pdf,png
  gmt makecpt -Cpolar -T-2/2/0.1 -Z          # ±2 m 覆盖同震形变
  gmt grdimage rng_offset_ll.grd -C -JM12c -Baf -I+d
  gmt colorbar -C -Baf+l"Range offset (m)"
gmt end show
```
方位向同理换 `azi_offset_ll.grd`；如需 DEM 山影背景，先 `gmt grdgradient`。

#### 7. 质量评估
```bash
gmt grdinfo rng_offset_ll.grd -C
# 远场零值检查（去趋势后均值应 ≈0）
gmt grd2xyz rng_offset_ll.grd -s | awk '{s+=$3;n++}END{print "mean="s/n}'
```
- 相关直方图评估整体匹配质量；位移矢量图判断形变方向。
- 去趋势后远场均值应接近 0。

### 故障排除
| 问题 | 原因 | 解决 |
|------|------|------|
| `freq_xcorr.dat` 行数不匹配 | nx/ny 参数错误 | 确认 `SLC_width/8`、`SLC_lines/8`，并与 `pot_geocode.csh` 的 nx ny 一致 |
| 地理编码失败 (`proj_ra2ll.csh`) | `trans.dat` 符号链接断裂 / 不在 PATH | 检查 `topo/trans.dat`；确认 GMTSAR 在 PATH |
| `pot_geocode.csh` 过滤后 0 点 | snr 阈值过高或偏移全触边界 | 降低 snr；确认 xsearch/ysearch/ri 与 xcorr_cc 一致 |
| 形变场整体偏移（系统性趋势） | 轨道/电离层趋势 | 跑 `grdtrend -N1`（GMT6 用 `-D` 输出残差） |
| `pot_merge.csh` 偏置异常 | 两帧重叠区太小/有外点 | 检查南北 grd 的 lat 重叠范围；必要时先各自去趋势 |
| GPU 架构报错 | nvcc 架构不匹配 | 重新 `make CUDA_ARCH=sm_XX`（见 xcorr_cc README） |
