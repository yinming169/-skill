# 示例图纸

供学习与功能验证使用。图纸版权归原权利人，请勿用于商业用途或对外传播。

| 文件 | 说明 | 大小 |
|---|---|---|
| `jinguan.dwg` / `jinguan.dxf` | 低压配电工程图纸 | 1.3 MB / 14 MB |
| `yalv.dwg` / `yalv.dxf` | 压滤机房低压配电图纸 | 1.3 MB / 14 MB |

## 用途

- 验证 `switchgear-quote` 全链路：DWG → DXF → 图块识别 → 分柜 → 出表
- 对比 `switchgear-quote/assets/标准样例_实验柜.xlsx` 检查型号写法是否符合标号规则

## 用法

DXF 已转换好，**无需安装 LibreDWG** 即可直接解析：

```bash
cd switchgear-quote
python scripts/pipeline.py --input ../samples/yalv.dxf --db assets/price_db_template.xlsx --out 报价单.xlsx
```

需要重新从 DWG 转换时，才需要 LibreDWG（见仓库根 README）。

## 识别结果参考

`yalv.dxf` 实测：电气图层 61 个图块，匹配 57 个（召回 93%），识别 43 项元器件，自动分出 13 个柜。
