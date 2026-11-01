"""统一入口：检查依赖、识别输入并调用现有报价流程。"""
import argparse, importlib.util, json, os, pathlib, shutil, subprocess, sys
from dispatch import scan
from common import setup_stdout

HERE = pathlib.Path(__file__).resolve().parent

def module(name):
    try: return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError): return False

def program(names, hints=()):
    for n in names:
        found = shutil.which(n)
        if found: return found
    return next((str(p) for p in map(pathlib.Path, hints) if p.is_file()), None)

def status():
    return {
      'python':sys.executable,
      'modules':{n:module(n) for n in ('ezdxf','fitz','pdfplumber','openpyxl','paddleocr','paddle')},
      'dwg2dxf':program(('dwg2dxf','dwg2dxf.exe')),
      'freecad':program(('FreeCAD.exe','freecad','FreeCADCmd.exe'),[r'C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe',r'D:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe']),
      'gelectrical':program(('GElectrical.exe','gelectrical')),
      'visual_model':'未配置：符号库为参考索引，不是识别模型',
      'note':'FreeCAD 和 GElectrical 当前仅做可用性检查，尚未建立自动调用接口。'
    }

def main():
    setup_stdout(); p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--status',action='store_true',help='检查工具可用性')
    p.add_argument('--input',help='图纸文件或目录')
    p.add_argument('--db',help='价格库文件，出报价单时需要')
    p.add_argument('--out',help='报价表输出路径')
    p.add_argument('--work',default='work',help='中间文件目录')
    a=p.parse_args(); report=status()
    if a.status or not a.input: print(json.dumps(report,ensure_ascii=False,indent=2))
    if not a.input: return 0
    if not os.path.exists(a.input): print('输入路径不存在',file=sys.stderr);return 2
    files=scan(a.input)
    if not files: print('没有找到支持的图纸',file=sys.stderr);return 2
    print('图纸分流：')
    for f in files: print(' -',f['name'],f['note'])
    if not a.db and not a.out: return 0
    if not a.db or not a.out: print('生成报价表须同时提供 --db 和 --out',file=sys.stderr);return 2
    if not os.path.isfile(a.db): print('价格库不存在',file=sys.stderr);return 2
    required={'openpyxl'}
    if any(f['kind']=='dxf' for f in files):required.add('ezdxf')
    if any(f['kind']=='pdf' for f in files):required.add('fitz')
    if any(f['kind']=='image' for f in files):required.update(('paddleocr','paddle'))
    missing=sorted(n for n in required if not report['modules'][n])
    if missing: print('当前 Python 缺少依赖：'+', '.join(missing),file=sys.stderr);return 2
    if any(f['kind']=='dwg_need_convert' for f in files):
        print('DWG 必须先转为 DXF 并核对转换警告；该入口目前不会自动转换。',file=sys.stderr);return 2
    cmd=[sys.executable,str(HERE/'pipeline.py'),'--input',os.path.abspath(a.input),'--db',os.path.abspath(a.db),'--out',os.path.abspath(a.out),'--work',os.path.abspath(a.work)]
    return subprocess.run(cmd).returncode
if __name__=='__main__': sys.exit(main())
