"""图片/扫描件 OCR 提取（可选链路）。

需要额外安装：pip install paddlepaddle paddleocr
未安装时 extract.py 会捕获 ImportError 并提示人工录入，不会中断流程。
"""


def _load_ocr():
    try:
        from paddleocr import PaddleOCR
    except ImportError as e:
        raise ImportError(
            "未安装 OCR 依赖。安装后再跑：pip install paddlepaddle paddleocr\n"
            "或改用矢量 PDF / DXF，准确率更高。"
        ) from e
    return PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)


def extract_image(path):
    ocr = _load_ocr()
    result = ocr.ocr(path, cls=True)
    rows = []
    for page in result or []:
        for item in page or []:
            box, (text, conf) = item[0], item[1]
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            rows.append({
                "text": text.strip(),
                "x": round(min(xs), 1),
                "y": round(min(ys), 1),
                "conf": round(float(conf), 3),
                "page": 1,
            })
    rows.sort(key=lambda r: (r["y"], r["x"]))
    low = [r for r in rows if r["conf"] < 0.8]
    return {
        "file": path,
        "source_type": "image_ocr",
        "rows": rows,
        "inserts": [],
        "tables": [],
        "low_confidence": len(low),
        "warning": f"{len(low)} 条 OCR 置信度 <0.8，必须人工复核" if low else "",
    }
