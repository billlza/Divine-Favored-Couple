# 李清然：头肩相似度校形

[可编辑 Blender 源件](LiQingran_Likeness.blend) · [原图／上一版／本版同机位对照](Preview/Reference_Comparison.png) · [白衣肖像](Preview/Portrait.png) · [斜侧](Preview/Quarter.png) · [侧面灰模](Preview/Profile_clay.png)

本轮统一了头顶到鬓角的梳发方向，软化发际支撑面的边缘，并把刘海下缘梳得更松散。眼部按原图瞳孔位置校准虹膜，皮肤增加了细微的凹凸、粗糙度和唇部光泽。三张有材质的图使用有方向的主光与窄边光，侧面灰模使用中性灰材质。比较图左侧为原图，中间为上轮实渲，右侧为本轮实渲。[780 × 640 近照](../HeadShoulders_2026-09-30/Preview/Original_Reference.png)

`fit_likeness.py` 是构建与渲染入口，脸部、毛发和相机灯光分别由 `face_fit.py`、`portrait_groom.py`、`portrait_views.py` 负责。用 Blender 的 `-b --python <脚本>` 执行，支持 `-- build --blend <新文件>` 与 `-- render --blend <源件> --view <portrait|matched|quarter|clay> --image <路径>`。发束和眼睫为原生曲线，头部校形滑杆归零可精确恢复校形前的几何。

重开检查覆盖形态键回退、原图打包、发髻接合和四张 Cycles 实渲。眼角和下颌的投影测量沿用上轮校形基准。侧后方的深度和发型由单图推定，当前交付范围为静态头肩。[重开核验](Verification.json)

人体底模使用 CC0 许可。[人体底模许可](../Portrait_2026-11-12/Licenses/BODY_LICENSE.ASSETS.md)
