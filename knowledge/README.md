# 手册全文与 OCR（完整版）

`handbooks-and-ocr.zip`（**46 MB，958 个文件**）包含全部内容：

| 目录 | 内容 | 文件数 |
|---|---|---|
| `txt/` | 五本书全文 Markdown | 6 |
| `ocr/` | 逐页 OCR 文本（675）+ 254 张页面原图（png） | 929 |
| `img/` | 书中插图 | 若干 |
| `tools/` | OCR / 检索 / 打包脚本 | 4 |
| 根目录 | `配电柜知识库.md`、`00_知识边界与覆盖度.md`、`README.md` | 3 |

## 解压

```bash
unzip handbooks-and-ocr.zip
```

解压后得到 `knowledge/` 目录，可直接被 AI 读取。

## 检索

```bash
cd knowledge
python tools/search.py "Emax 附件"
```

## 版权

手册及其 OCR 的版权和使用条件由各自权利人决定，仓库的 MIT 许可不授予第三方手册的权利。本仓库仅供个人与朋友内部使用，请勿外传。
