"""switchgear-quote 公共工具。"""
import json
import os
import re
import sys

# ---------- 型号归一化 ----------

_SEP = re.compile(r"[\s\-_·]+")
_TIMES = re.compile(r"[×xX*✕]")


def norm_model(s):
    """型号归一化：统一乘号、大写、去空格与多余分隔符。"""
    if not s:
        return ""
    s = str(s).strip()
    s = _TIMES.sub("×", s)
    s = _SEP.sub("", s)
    return s.upper()


def norm_name(s):
    if not s:
        return ""
    return re.sub(r"\s+", "", str(s))


def num(x, default=0.0):
    if x is None or x == "":
        return default
    try:
        return float(str(x).replace(",", "").replace("，", ""))
    except Exception:
        return default


def clean_money(x):
    """保留两位小数，None 返回 None（不写 0，避免把"未报价"变成"免费"）。"""
    if x is None or x == "":
        return None
    return round(float(x), 2)


# ---------- IO ----------

def setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def ensure_dir(path):
    if path:
        os.makedirs(path, exist_ok=True)
    return path


# ---------- 柜型 ----------

HV_KEYS = ["KYN28", "KYN61", "XGN", "HXGN", "SF6", "环网柜", "10KV", "35KV",
           "12KV", "24KV", "40.5KV", "中置柜", "手车柜", "固定柜"]
LV_KEYS = ["GGD", "GCK", "GCS", "MNS", "XL-21", "XL21", "PZ30", "PZ-30",
           "0.4KV", "400V", "380V", "低压", "抽屉柜", "动力柜", "照明箱",
           "配电箱", "双电源箱", "控制箱"]


def detect_voltage_class(text):
    """返回 '高压' / '低压' / '未知'。"""
    up = (text or "").upper()
    hv = sum(1 for k in HV_KEYS if k in up)
    lv = sum(1 for k in LV_KEYS if k in up)
    if hv > lv:
        return "高压"
    if lv > hv:
        return "低压"
    return "未知"


# ---------- 柜体尺寸 ----------

_SIZE_RE = re.compile(r"(\d{3,4})\s*[×xX*✕]\s*(\d{3,4})\s*[×xX*✕]\s*(\d{3,4})")
_LABELED_RE = re.compile(
    r"[（(]?\s*[Ww宽]\s*[:：]?\s*(\d{3,4}).{0,12}?[Hh高]\s*[:：]?\s*(\d{3,4}).{0,12}?[Dd深]\s*[:：]?\s*(\d{3,4})"
)
_MM_RE = re.compile(r"(mm|毫米)", re.I)


def parse_cabinet_size(lines):
    """从文本行里找柜体尺寸，返回 (宽, 高, 深) 或 None。

    国内习惯 宽×高×深；带 W/H/D 标签的直接按标签取。
    """
    for ln in lines:
        m = _LABELED_RE.search(ln)
        if m:
            w, h, d = (int(g) for g in m.groups())
            return (w, h, d, "带W/H/D标签")
    for ln in lines:
        m = _SIZE_RE.search(ln)
        if m:
            a, b, c = (int(g) for g in m.groups())
            # 高度通常最大；若第二个不是最大，按 宽×深×高 重排
            if b >= a and b >= c:
                return (a, b, c, "宽×高×深")
            if c >= a and c >= b:
                return (a, c, b, "宽×深×高(已重排)")
            return (a, b, c, "原样")
    return None


# ---------- 铜排 ----------

# (额定电流上限 A, 规格, 单根截面积 mm²)
COPPER_TABLE = [
    (250, "TMY-30×4", 120),
    (400, "TMY-40×5", 200),
    (630, "TMY-50×6", 300),
    (800, "TMY-60×8", 480),
    (1000, "TMY-80×10", 800),
    (1250, "TMY-100×10", 1000),
    (1600, "TMY-120×10", 1200),
    (2000, "TMY-2×(100×10)", 2000),
    (2500, "TMY-2×(120×10)", 2400),
    (3200, "TMY-3×(100×10)", 3000),
]

COPPER_DENSITY = 8.9  # g/cm³


def copper_spec_by_current(current):
    for limit, spec, area in COPPER_TABLE:
        if current <= limit:
            return spec, area
    return COPPER_TABLE[-1][1], COPPER_TABLE[-1][2]


def copper_weight_kg(length_m, area_mm2, strands=1):
    """长度(m) × 截面积(mm²) → kg。kg = 8.9 * L * A / 1000 * 股数"""
    return round(COPPER_DENSITY * length_m * area_mm2 * strands / 1000, 2)


# ---------- 输出 ----------

def banner(msg):
    print(f"\n=== {msg} ===")
