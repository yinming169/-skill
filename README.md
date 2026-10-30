# 高低压柜报价 Skill

从电气图纸提取材料信息，结合用户提供的价格库生成 Excel 报价清单。结果须经人工复核。

## 让 AI 使用

支持 Agent Skills 的工具：将 `switchgear-quote` 文件夹安装到该工具的技能目录，再按其加载方式启用。其他可以读取文件的 AI：提供本仓库并要求先阅读 `switchgear-quote/SKILL.md`，按其中流程执行；运行脚本需要可用的 Python 环境和相应依赖。不同 AI 的安装方式与执行能力各异。

## 使用

进入 `switchgear-quote` 目录：

```bash
pip install ezdxf pdfplumber pymupdf openpyxl pandas
python scripts/pipeline.py --input <图纸或目录> --db <价格库.xlsx> --out 报价单.xlsx
```

扫描图纸需要额外配置 PaddleOCR；DWG 需先转换成 DXF。价格由使用者提供，未识别项目及推算结果须复核。手册全文及 OCR 可从 `knowledge/handbooks-and-ocr.zip` 下载并解压后使用；其版权及使用条件由各自权利人决定。

## 许可证

MIT，见 LICENSE。

