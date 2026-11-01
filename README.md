# 高低压柜报价 Skill

从电气图纸（DWG / DXF / PDF）提取元器件，按定稿的**标号规则**生成**每台柜/箱单独一张**的分项报价表。

## 核心能力

- **图纸识别**：DWG → LibreDWG(dwg2dxf) → DXF → 图块 + 文字；图块就近匹配型号，召回 93%
- **型号规范化**：厂家系列统一成通用代号（MCB / MCCB / ACB），剥离 M/L/H 分断等级，便于换牌比价
- **分柜**：按柜号标注坐标聚类，自动区分 AL1 / WD1 / WP0 等；排除继电器、按钮、PLC 点等元件代号误判
- **标号规则**：严格按 `switchgear-quote/references/标号规则.md` 执行（2026-11-01 定稿）
- **出表**：每柜一张完整表，7 列（序号 / 名称 / 型号规格 / 单位 / 数量 / 备注 / 金额），**备注列永久空白**
- **汇总**：每柜独立核算 材料小计 → 制造费 → 利润 → 税费 13% → 产品报价

## 让 AI 使用

支持 Agent Skills 的工具：把 `switchgear-quote` 安装到技能目录后启用。
其他能读文件的 AI：提供本仓库，要求先读 `switchgear-quote/SKILL.md`，按其中流程执行。

## 使用

```bash
cd switchgear-quote
pip install ezdxf pdfplumber pymupdf openpyxl pandas
python scripts/pipeline.py --input <图纸或目录> --db <价格库.xlsx> --out 报价单.xlsx
```

- 默认：一个工作簿，**每柜一个 sheet**
- `--split-files`：每柜一个独立 xlsx 文件
- `--format detail`：内部核价用的 7 表工作簿
- `--cabinet-type`：强制柜体型号（XL-21 / JXF / GGD / MNS抽屉式 / MNS固定式）

扫描图纸需额外配置 PaddleOCR；DWG 需先转 DXF。价格由使用者提供，未识别项与推算结果须复核。

## 关键文档

| 文件 | 作用 |
|---|---|
| `switchgear-quote/references/标号规则.md` | **型号写法标准（最高优先级）** |
| `switchgear-quote/references/元器件物料表规则.xlsx` | 原始规则表（40 条子类码） |
| `switchgear-quote/references/开源项目参考.md` | 开源项目研判（取精华去糟粕） |
| `switchgear-quote/assets/标准样例_实验柜.xlsx` | 定稿样例（31 项物料） |

手册全文及 OCR 见 `knowledge/handbooks-and-ocr.zip`，其版权及使用条件由各自权利人决定。

## 许可证

MIT，见 LICENSE。
