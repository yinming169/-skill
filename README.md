# 高低压柜报价 Skill

从电气图纸（DWG / DXF / PDF）提取元器件，按定稿的**标号规则**生成**每台柜/箱单独一张**的分项报价表。

## 仓库内容（完整）

```
├── switchgear-quote/              技能本体（24 文件）
│   ├── SKILL.md                   主入口
│   ├── scripts/                   12 个 Python 脚本
│   ├── references/                7 份规则文档
│   │   ├── 标号规则.md            ★ 型号写法标准（最高优先级）
│   │   ├── 元器件物料表规则.xlsx  原始规则表（40 条子类码）
│   │   ├── 开源项目参考.md        开源项目研判
│   │   ├── recognition-rules.md
│   │   ├── electrical-knowledge.md
│   │   ├── accessory_rules.json
│   │   └── markup_rates.json
│   └── assets/                    价格库模板 / 标准参考格式 / 标准样例
├── knowledge/                     知识库（完整）
│   ├── handbooks-and-ocr.zip      46 MB，958 文件（五本书全文 + OCR + 页面图）
│   └── README.md
└── README.md
```

## 在其他电脑使用

### 1. 克隆

```bash
git clone https://github.com/yinming169/Stupid-company-arrogant-boss-ridiculous-job-sikll.git
cd Stupid-company-arrogant-boss-ridiculous-job-sikll
```

### 2. 安装 Python 依赖

```bash
pip install ezdxf pdfplumber pymupdf openpyxl pandas
# 扫描件 OCR（可选）
pip install paddlepaddle paddleocr
```

### 3. 安装 DWG 转换工具（仅 DWG 图纸需要）

本仓库**不包含** LibreDWG 二进制（第三方 GPL 工具 + 体积 93 MB），按需安装：

- 从 [LibreDWG releases](https://github.com/LibreDWG/libredwg/releases) 下载，把 `dwg2dxf` 所在目录加入 PATH
- 或先把 DWG 转成 DXF（AutoCAD / ODA File Converter / 在线转换），本工具直接读 DXF

### 4. 解压知识库（供 AI 检索，可选）

```bash
cd knowledge && unzip handbooks-and-ocr.zip
```

### 5. 跑起来

```bash
cd switchgear-quote
python scripts/pipeline.py --input <图纸或目录> --db <价格库.xlsx> --out 报价单.xlsx
```

- 默认：一个工作簿，**每柜一个 sheet**
- `--split-files`：每柜一个独立 xlsx
- `--format detail`：内部核价用 7 表
- `--cabinet-type`：强制柜体型号（XL-21 / JXF / GGD / MNS抽屉式 / MNS固定式）

## 关于「不包含的内容」

以下内容**有意不放入仓库**，不是私藏：

| 内容 | 原因 |
|---|---|
| 客户图纸（`.dwg` / `.dxf`） | **商业机密**，绝不能公开 |
| LibreDWG 二进制（93 MB） | 第三方 GPL 工具，官方 releases 可下载 |
| Python wheels（253 MB） | PyPI 公开可下载，`pip install` 即可 |

## 让 AI 使用

支持 Agent Skills 的工具：把 `switchgear-quote` 安装到技能目录后启用。
其他能读文件的 AI：提供本仓库，要求先读 `switchgear-quote/SKILL.md`，按其中流程执行。

## 许可证

MIT，见 LICENSE。手册 OCR 的版权归各自权利人，本仓库仅供个人与朋友内部使用。
