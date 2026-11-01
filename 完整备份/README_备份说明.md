# 开关柜报价技能 —— 完整备份说明

> 备份创建时间：2026-11-01
> 备份用途：交给 Codex 做二次修改，改完回传给 WorkBuddy（GLM）分析。
> 备份总大小：约 533 MB

---

## 一、本备份目录结构

```
D:\switchgear-quote-full-backup\
├── README_备份说明.md          ← 本文件（Codex 先读这个）
├── knowledge/                  知识库（最核心，二次修改的主对象）
│   ├── txt/                    五本书全文文本（按书一本一个 md）
│   │   ├── 资料1_低压供配电设备选型手册.md          (文字层，数字失真)
│   │   ├── 资料1_低压供配电设备选型手册_OCR.md      (断路器篇 OCR，数字可信)
│   │   ├── 资料2_电气控制工程师手册.md
│   │   ├── 资料3_低压成套开关设备_OCR.md            (全书 OCR，数字可信)
│   │   ├── 资料4_工业与民用配电设计手册.md          (文字层，数字失真)
│   │   └── 资料5_电机与拖动基础.md
│   ├── cards/                  8 张结构化知识卡片（深度学习成果）
│   │   ├── card-01-主母线铜排载流量.md
│   │   ├── card-02-断路器选型要点.md
│   │   ├── card-03-接触器与起动器选型.md
│   │   ├── card-04-级间选择性.md
│   │   ├── card-05-常用断路器参数速查.md
│   │   ├── card-06-电容补偿容量.md
│   │   ├── card-07-电缆压降与短路电流.md
│   │   └── card-08-RCD漏电断路器选型.md
│   ├── ocr/                    OCR 原始单页结果（含 资料4 短路计算 p130-170 复核）
│   ├── img/                    页面渲染图
│   ├── standards/              国标/行标 PDF 目录（待补）
│   ├── books/                  教材/手册 PDF 目录（待补）
│   ├── papers/                 论文/技术文章目录（待补）
│   ├── tools/                  ocr_pdf.py / search.py 等工具
│   ├── 00_知识边界与覆盖度.md   覆盖度清单（哪些能用、哪些空白）
│   └── README.md               知识库使用说明
├── skill/                      报价技能本体（WorkBuddy 的 skill）
│   ├── SKILL.md                技能入口与触发条件
│   ├── references/             选型规则表、电气知识、国标清单
│   ├── scripts/                Python 处理脚本
│   ├── assets/                 模板/样例
│   └── README.md
├── samples/                    示例图纸（两套低压配电 DWG + 已转 DXF）
│   ├── jinguan.dwg / .dxf      金工项目
│   └── yalv.dwg / .dxf         压滤机房项目
├── source_books/               五本书原 PDF + 1 份国标 PDF（357MB）
│   ├── 低压成套开关设备的原理及其控制技术.pdf      (78M, 资料3)
│   ├── 工业与民用配电设计手册第三版高清晰版.pdf    (65M, 资料4)
│   ├── 常用低压供配电设备选型与安装技术手册(1).pdf (20M, 资料1)
│   ├── 电机与拖动基础.pdf                          (92M, 资料5)
│   ├── 电气控制工程师手册(向晓汉).pdf              (101M, 资料2)
│   └── GBT+24275-2019.pdf                          (2.8M, 国标)
└── docs/                       参考文档
    ├── 高低压开关柜国标与教材资料清单.md          (用户整理的资料清单，含版本陷阱)
    ├── GitHub仓库README.md                        (GitHub 仓库说明)
    └── LICENSE
```

---

## 零、给 Codex 的说明（二次修改前必读）

**项目是什么**：这是一套"高低压开关柜报价技能"，用于 WorkBuddy AI 里根据客户图纸自动生成报价。核心组成：
- `skill/` = 技能本体（SKILL.md 是入口，references/ 是规则与知识）
- `knowledge/` = 五本配电书的数字化知识库（txt/ 全文 + cards/ 提炼卡片 + ocr/ 原始结果）
- `samples/` = 两套客户图纸样例（dwg 需 LibreDWG 转 dxf 才能解析，dxf 已转好）
- `source_books/` = 五本书的原 PDF（OCR 的事实来源）

**已完成的工作**：
1. 五本书全文提取（txt/），其中资料1、4 文字层数字失真，靠 OCR 救回（ocr/）
2. 资料4 p640-667（断路器/接触器/选择性）、p130-170（短路计算）已 OCR 复核
3. 8 张知识卡片提炼完成（cards/），是可直接调用的结构化知识
4. 覆盖度清单（00_知识边界与覆盖度.md）标明哪些知识可用、哪些空白

**二次修改的建议方向**（参考）：
- 检查 cards/ 里数字与 source_books/ 原 PDF 是否一致（OCR 可能有错）
- 补齐覆盖度清单里的空白项（柜体结构、主回路方案、二次回路等）
- 修正 references/ 里规则表与国标清单的版本问题（见 docs/高低压开关柜国标与教材资料清单.md 的"版本陷阱"节）
- 注意：资料1、4 的 txt/ 文字层版数字不可信，必须以 ocr/ 或 source_books/ 原 PDF 为准

**改完怎么交还**：保持目录结构不变，改哪些文件在返回时说明清楚即可。

---

## 二、本项目所有内容的"原位置"清单

| 内容 | 原位置（当前机器） | 说明 |
|---|---|---|
| 知识库本体 | `D:\Users\Administrator\2026-10-29-22-09-23\knowledge\` | 工作区，最新最全 |
| 用户级 skill | `C:\Users\Administrator\.workbuddy-ai\skills\switchgear-quote\` | 加载进 WorkBuddy 的技能 |
| GitHub 发布副本 | `D:\Users\Administrator\2026-10-29-22-09-23\.workbuddy-ai\tmp_repo\` | 已 push 到 GitHub |
| 旧 D 盘备份 | `D:\switchgear-quote\` | 早期备份，不如本备份完整 |
| **GitHub 仓库** | `yinming169/Stupid-company-arrogant-boss-ridiculous-job-sikll` | **注意：当前是 PUBLIC（公开）** |

---

## 三、换模型实验后"交还"给我时

1. 把你改完的内容放在这个备份目录对应位置（或整个目录打包）
2. 告诉我"备份已改完"，我直接从这里读取
3. 如果换到新电脑，把整个 `switchgear-quote-full-backup` 目录拷过去即可
4. 恢复成 skill：把 `skill/` 目录内容复制到新机器的
   `C:\Users\<用户名>\.workbuddy-ai\skills\switchgear-quote\`

---

## 四、关于 G 盘

创建本备份时，**G 盘未挂载**（当前机器只有 C、D 盘）。
操作建议：
- 把 G 盘（移动硬盘/U盘/网盘）插上后，把整个 `D:\switchgear-quote-full-backup\`
  目录复制进去即可。目录名可改为你喜欢的（如 `G:\开关柜报价备份\`）。
- 复制完成后，本备份在 D 盘仍保留，作为双保险。

---

## 五、深度学习已完成的卡片速查

| 问题 | 读哪张卡片 |
|---|---|
| 铜排该选多大？载流量多少？ | `knowledge/cards/card-01-主母线铜排载流量.md` |
| 断路器怎么选？Icu/Ics/Icw？ | `knowledge/cards/card-02-断路器选型要点.md` |
| 接触器 AC-3/AC-4 区别？ | `knowledge/cards/card-03-接触器与起动器选型.md` |
| 上下级怎么配合不越级跳闸？ | `knowledge/cards/card-04-级间选择性.md` |
| 这个电流配什么型号断路器？ | `knowledge/cards/card-05-常用断路器参数速查.md` |
| 电容补偿柜配多大容量？ | `knowledge/cards/card-06-电容补偿容量.md` |
| 电缆压降够不够？短路电流多大？ | `knowledge/cards/card-07-电缆压降与短路电流.md` |
| 漏电保护怎么分级？ | `knowledge/cards/card-08-RCD漏电断路器选型.md` |

---

## 六、尚未深度学习（空白项，实验中可补）

- 资料4 短路计算章节 p130–170 已 OCR，尚未提炼成卡片（ocr/复核_资料4_短路计算/ 有原始结果）
- 资料4 防爆环境选型（p613–631）
- 资料2 电气控制工程师手册（向晓汉）尚未提炼卡片
- 资料3 二次回路/控制原理（第6章 p297–378）
- 28 项国标 + 5 本教材清单已列，文件待补（见 references/国标与教材清单.md §九）

---

## 七、重要提醒

⚠️ **GitHub 仓库目前是 PUBLIC（公开）**，里面有五本书 OCR 全文 + 两套客户图纸。
如果换模型实验期间不想公开，建议先改私有（仓库 Settings → Danger Zone →
Change repository visibility → Change to private）。
