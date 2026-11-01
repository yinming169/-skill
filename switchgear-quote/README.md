# 高低压柜报价 Skill

把电气图纸变成可报价的 Excel 材料清单，并自动配齐配套件。

## 能力

- **图纸解析**：DWG（经 LibreDWG 转 DXF）/ DXF / 矢量 PDF / 扫描件 OCR
- **元器件识别**：型号、数量、柜型、柜体尺寸、铜排规格
- **配套件自动配齐**：马达保护器、接触器、变频器、软启动器等按规则配附件
- **报价单生成**：按用户既有「分项报价表」格式输出，含分项、单价、加价率、利润
- **知识检索**：五本配电资料全文检索，查选型依据

## 目录

```
switchgear-quote/          skill 本体
├── SKILL.md               技能说明与工作流
├── scripts/               可执行脚本
│   ├── pipeline.py        一键：图纸 → 报价单
│   ├── dispatch.py        图纸分流
│   ├── extract_dxf.py     DXF 提取
│   ├── extract_pdf.py     PDF 提取
│   ├── classify.py        型号/柜型/尺寸识别
│   ├── price_match.py     价格库匹配 + 加价
│   ├── build_quote.py     生成报价 Excel
│   └── template_quote.py  按用户模板出表 + 配齐配套件
├── references/            规则与知识
│   ├── recognition-rules.md     型号识别规则库
│   ├── electrical-knowledge.md  选型知识库
│   ├── accessory_rules.json     配套件规则
│   └── markup_rates.json        加价率
└── assets/
    ├── price_db_template.xlsx   价格库模板
    └── 标准参考格式.xlsx        用户标准报价格式（单柜分项报价表）
```

## 快速开始

```bash
# 一键生成报价单
python scripts/pipeline.py --input <图纸或目录> --db <价格库.xlsx> --out 报价单.xlsx

# 按用户模板出配齐版
python scripts/template_quote.py <源清单.xlsx> --out <配齐版.xlsx>
```

## 依赖

```bash
python -c "import ezdxf, pdfplumber, fitz, openpyxl, pandas"
```

DWG 需先用 LibreDWG 转 DXF：

```bash
dwg2dxf.exe -o out.dxf in.dwg
```

## 免责与边界

- 本 skill 是**选型逻辑与流程工具**，不是参数手册。最终参数以厂家样本为准。
- 铜排用量、柜体部件数量为**推算值**，报价前必须人工复核。
- 价格只能来自用户自有价格库，不联网抓价、不猜价。
