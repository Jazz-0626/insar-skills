# SDM2025 IO 格式参考

(蒸馏自 `SDM/SDM_final/workflow.md §0`，源 `SDM2025/SourceCode/*.f` + 官方 example)

## 1. 可执行 / 调用
SDM2025 为第三方软件（R. Wang, GFZ；非本仓库分发，自行获取，见 `../SKILL.md`）。安装后记下两路径：
```
$SDM2025/sdm2025                    # Linux x86-64
$SDM2025/WindowsEXE/sdm2025.exe     # Windows
源码: $SDM2025/SourceCode/*.f   example: $SDM2025/InputFile/sdm2025_example_1/
```
调用：`echo 'sdm_xxx.inp' | $SDM2025/sdm2025 > stdout.log 2>&1`
sdm2025 仅从 stdin 读一个 inp 文件名；**所有路径相对当前工作目录**。

## 2. inp 格式（idisc=1 自动离散）
```
 iearth          # 0=halfspace 1=layered 2=user-3D-Green
 poisson         # e.g. 0.25
 idisc           # 0=从文件读 patches; 1=自动离散
 ns              # 断层段数
 # 每段(is=1..ns):
 is  topdep_km  width_km  mean_strike(-1000=auto)  patchsize_km
     rake1_deg  rake2_deg  max_slip_m
     nft                         # 迹线节点数 >=2
     lat1 lon1 topdip1 botdip1   # 各节点顶/底倾角
     lat2 lon2 topdip2 botdip2
     ...
 ngd  datunit  nheader          # 数据集数, 单位因子, header 行数
 # 每个数据集:
 'file.dat'
 weight type[ inc_deg azi_deg]  # type=1 -> 常数 LOS, 后跟 inc azi
 nusrp [ 'corrgrnfile' ]        # 修正参数数, 0=无
 min max                        # 每个修正参数一行
 niter  'zhyrelax_file'
 ismooth  smoothing  izhy       # ismooth: 1=slip(滑移平滑) 2=stress-drop
 'slipout.dat'
 'out1.dat' 'out2.dat' ['out3.dat'] ['offsets.dat']   # 每个数据集一个 data-fit 输出
```
**规则**：`#` 开头=注释(skipdoc.f)；**不允许空行**；`mean_strike=-1000`→由迹线自动算走向；`topdip>botdip`=antilistric(反铲)、`<`=listric(铲式)。
**ENU 当常数 LOS 编码**：N→inc90/azi0、E→inc90/azi90、U→inc0/azi0。

## 3. 数据文件格式
```
lat_deg  lon_deg  displacement  error
```
4 列、**无 header**(除非 nheader>0)；`error>0`(权重 wf=1/err²)；type=1(csconst) 时只读 4 列、inc/azi 由 inp 给。

## 4. corrgrn 文件(如 offset_grns.dat)
```
# 第一行 header(任意, SDM 跳过)
v1 v2 ... vN     # 第1行数据, N=nusrp, 对应观测点1
...              # 共 nobs 行 = 所有数据集观测数之和(按 inp 中数据集顺序拼接)
```
ENU 常数 offset：N 分量点→(1,0,0)、E→(0,1,0)、U→(0,0,1)。用 `scripts/build_offset_grns.py ns.dat ew.dat up.dat`。

## 5. 输出列定义(sdmoutput.f)
**slip 文件**(`slip_model.dat`, `s0i_slip_model.dat` 分段)：
```
1 lat  2 lon  3 depth_km  4 x_local_km(沿走向)  5 y_local_km(沿倾向)
6 length_km  7 width_km  8 slp_strike_m  9 slp_ddip_m(已取负,正断>0)
10 slp_amp_m(=√(strk²+ddip²))  11 strike  12 dip  13 rake
14 stress_strike_MPa  15 stress_downdip_MPa(已取负)  16 stress_normal_MPa
```
**data-fit 文件**(`output_un/ue/uz.dat`)：
```
1 lat  2 lon  3 obs(=datobs/unit)  4 residual(=obs-slip_pred, ⚠不含correction)
5 prediction(=datmdl/unit)  6 correction(=corrmdl/unit)
```
⚠ **真实残差** = `col3 − col5 − col6` = `col4 − col6`(SDM 内部 cost 用此, 见 sdmdatfit.f)。两阶段第二断层必须用真实残差。

## 6. ZHYRELAX.txt
最速下降迭代的松弛因子序列(Zhang 2025 优化算法, sdmzhy.f)。直接复用 `SDM/SDM_final/ZHYRELAX.txt`(180005 行, 够 niter≤5000)。

## 7. stdout 关键行(质检)
- `derived moment magnitude Mw = …`
- `fault_seg mean_slp mean_rake max_slp rake pos_lat pos_lon pos_z`(pos_z=max-slip 深度)
- `data-model correlation: …`(接近 1 好；**负=拟合噪声/几何反号**)
- `fault_seg average/std/max coseismic stress change [MPa]`
