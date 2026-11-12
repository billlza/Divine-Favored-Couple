# 苍云界：青云宗山门与剑阁洞府

两处都可在 Blender 单独打开，山体、建筑、道路和植被按集合组织。万青山溪谷继续使用[原场景](../wanqing-valley-2026-11-12/README.md)。

| 场景 | 可编辑源件 | Cycles 实渲 |
| --- | --- | --- |
| 青云宗 | [Cangyun_Qingyun.blend](Cangyun_Qingyun.blend) | [石阶望山门](Preview/Qingyun_approach.png) · [穿门看院落](Preview/Qingyun_courtyard.png) |
| 剑阁 | [Cangyun_Jiange.blend](Cangyun_Jiange.blend) | [贴崖小径](Preview/Jiange_cliff_path.png) · [远看崖居](Preview/Jiange_overlook.png) |

青云宗重铺了踏面和三处平台，细化了门翼木作，抬高镜头以看见正殿。剑阁收陡了崖沿，增加突出的岩层和石屋支路，镜头可同时看到洞口、灵田和峡谷。两处均采用分层体积云、近景针叶和风化岩面。地点取自原著，布局和尺度属于美术推定。[《上青云宗》](https://fanqienovel.com/reader/7447866946386674238) · [《选洞府》](https://fanqienovel.com/reader/7451809669565121086)

四个预览均为 Blender 5.2.1 LTS、Cycles Metal 54 采样实渲。画稿用于确定山门远景、崖台和峡谷的构图。[两联画稿](Reference/Mountain_landmarks_concept.png) · [原始提示词](Reference/Mountain_landmarks_concept.prompt.txt)

青云宗重开验证覆盖 45 级石阶的 135 个踏面采样、72 个平台露石采样点和山门的 12 条净空射线。剑阁验证覆盖 100 个崖台采样点、两处洞府内部和每处入口的 9 条净空射线。[青云宗核验](Qingyun_verification.json) · [剑阁核验](Jiange_verification.json)

`qingyun.py` 与 `jiange.py` 保存各自的布局和路线。石作、云雾、材质和植被由共用模块构建。通过 Blender 的 `-b --python <脚本>` 执行 `build_landmarks.py -- build <qingyun|jiange>` 或 `build_landmarks.py -- render <qingyun|jiange> --view <相机名> --image <路径>`。重开检查用 `verify_landmarks.py -- <qingyun|jiange> <源件> <报告路径>`。当前交付范围为独立的 Blender 美术场景。
