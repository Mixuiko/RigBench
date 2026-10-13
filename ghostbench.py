#!/usr/bin/env python3
"""GHOSTBENCH MVP v0.1: safe, repeatable local benchmarks; Python stdlib only."""
import argparse, hashlib, html, json, os, platform, statistics, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"
RESULTS = Path("results")

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def memory_info():
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            class M(ctypes.Structure):
                _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = M(); m.dwLength = ctypes.sizeof(M)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return {"total_physical_bytes": int(m.ullTotalPhys), "available_physical_bytes": int(m.ullAvailPhys)}
        except Exception:
            pass
    p = Path("/proc/meminfo")
    if p.exists():
        d = {}
        for line in p.read_text(errors="replace").splitlines():
            a = line.split()
            if len(a) > 1 and a[1].isdigit(): d[a[0].rstrip(":")] = int(a[1]) * 1024
        return {"total_physical_bytes": d.get("MemTotal"), "available_physical_bytes": d.get("MemAvailable")}
    return {"total_physical_bytes": None, "available_physical_bytes": None}

def system_info():
    return {"app":"GHOSTBENCH", "app_version":VERSION, "timestamp_utc":now(),
        "os":platform.platform(), "os_name":platform.system(), "os_release":platform.release(),
        "python_version":platform.python_version(), "python_implementation":platform.python_implementation(),
        "machine":platform.machine(), "processor":platform.processor() or "Not reported by OS",
        "logical_cpu_count":os.cpu_count(), **memory_info()}

def cpu_workload(n):
    """Deterministic Python integer workload; not a universal CPU score."""
    x, mask = 0x12345678, 0xFFFFFFFF
    for i in range(n):
        x = (x * 1664525 + 1013904223 + (i & 0xFFFF)) & mask
        x ^= x >> 13
        x = (x * 2246822519) & mask
    return x

def summary(vals, lower=True):
    return {"count":len(vals), "median":round(statistics.median(vals),6),
        "mean":round(statistics.mean(vals),6),
        "stdev":round(statistics.stdev(vals),6) if len(vals)>1 else 0.0,
        "min":round(min(vals),6), "max":round(max(vals),6), "lower_is_better":lower}

def cpu_bench(runs, iterations):
    warmup = cpu_workload(max(1, iterations//10))
    samples=[]
    for i in range(runs):
        t=time.perf_counter(); checksum=cpu_workload(iterations); sec=time.perf_counter()-t
        samples.append({"run":i+1,"seconds":round(sec,6),"iterations":iterations,
            "iterations_per_second":round(iterations/sec,2) if sec else None,"checksum":checksum})
    return {"benchmark":"cpu","method":"deterministic Python integer loop",
        "parameters":{"runs":runs,"iterations_per_run":iterations},"warmup_checksum":warmup,
        "samples":samples,"metrics":{"seconds":summary([s["seconds"] for s in samples]),
        "iterations_per_second":summary([s["iterations_per_second"] for s in samples],False)},
        "checksums_match":len({s["checksum"] for s in samples})==1}

def memory_workload(size_mib, block_kib):
    size=size_mib*1024*1024; blocksize=block_kib*1024
    block=bytes(i%251 for i in range(blocksize))
    t=time.perf_counter(); data=bytearray(size); alloc=time.perf_counter()-t
    t=time.perf_counter()
    for off in range(0,size,blocksize):
        end=min(off+blocksize,size); data[off:end]=block[:end-off]
    write=time.perf_counter()-t
    digest=hashlib.sha256(data[::max(1,size//4096)]).hexdigest()
    del data
    return {"allocation_seconds":round(alloc,6),"write_seconds":round(write,6),
        "size_mib":size_mib,"write_mib_per_second":round(size_mib/write,2) if write else None,
        "sample_sha256":digest}

def memory_bench(runs,size_mib,block_kib):
    memory_workload(min(size_mib,16),block_kib) # warm-up
    samples=[{"run":i+1,**memory_workload(size_mib,block_kib)} for i in range(runs)]
    return {"benchmark":"memory","method":"bytearray allocation and block writes",
        "parameters":{"runs":runs,"size_mib_per_run":size_mib,"block_kib":block_kib},
        "samples":samples,"metrics":{
        "allocation_seconds":summary([s["allocation_seconds"] for s in samples]),
        "write_seconds":summary([s["write_seconds"] for s in samples]),
        "write_mib_per_second":summary([s["write_mib_per_second"] for s in samples],False)},
        "checksums_match":len({s["sample_sha256"] for s in samples})==1}

def save_result(obj, output=None):
    RESULTS.mkdir(exist_ok=True)
    if output is None:
        output=RESULTS/f'{obj["benchmark_result"]["benchmark"]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6]}.json'
    else: output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(obj,indent=2),encoding="utf-8")
    return output

def run_bench(args):
    if args.kind=="cpu": b=cpu_bench(args.runs,args.iterations)
    else: b=memory_bench(args.runs,args.size_mib,args.block_kib)
    obj={"schema_version":1,"app":"GHOSTBENCH","app_version":VERSION,"run_id":str(uuid.uuid4()),
        "label":args.label,"created_at_utc":now(),"system":system_info(),"benchmark_result":b,
        "notes":["Close unrelated apps and keep power mode consistent.",
        "Do not compare results with different workload parameters.",
        "Results vary with temperature and background activity."]}
    path=save_result(obj,args.output); print("Saved result:",path)
    for k,v in b["metrics"].items():
        print(f'{k}: median={v["median"]}')
    print("Checksums consistent:",b["checksums_match"])

def load_result(path):
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict) or "benchmark_result" not in obj or "system" not in obj:
        raise ValueError(f"{path} is not a GHOSTBENCH result file")
    return obj

def compare(a_path,b_path):
    a,b=load_result(a_path),load_result(b_path); x,y=a["benchmark_result"],b["benchmark_result"]
    if x["benchmark"]!=y["benchmark"]: raise ValueError("Benchmark types differ.")
    if x["parameters"]!=y["parameters"]: raise ValueError("Parameters differ; use matching settings.")
    rows=[]
    for k,v in x["metrics"].items():
        w=y["metrics"].get(k)
        if not isinstance(v,dict) or not isinstance(w,dict) or "median" not in v or "median" not in w: continue
        before,after=float(v["median"]),float(w["median"])
        pct=(after-before)/before*100 if before else None
        improved=(pct<0 if v.get("lower_is_better",True) else pct>0) if pct is not None else None
        rows.append({"metric":k,"baseline_median":before,"candidate_median":after,
            "change_percent":round(pct,3) if pct is not None else None,
            "interpretation":"improved on this metric" if improved else ("worsened on this metric" if improved is False and pct!=0 else "no clear change")})
    return {"benchmark":x["benchmark"],"baseline_file":str(a_path),"candidate_file":str(b_path),
        "baseline_label":a.get("label"),"candidate_label":b.get("label"),"comparison":rows,
        "warning":"A difference is not proof of causation. Control background load, temperature, power settings and software versions."}

def report(path, output=None):
    obj=load_result(path); b=obj["benchmark_result"]; sysinfo=obj["system"]
    esc=lambda x:html.escape(str(x))
    metrics=[]
    for k,v in b["metrics"].items():
        if isinstance(v,dict) and "median" in v:
            metrics.append(f'<tr><td>{esc(k)}</td><td>{esc(v["median"])}</td><td>{esc(v["mean"])}</td><td>{esc(v["stdev"])}</td></tr>')
    samples=b["samples"]; headers="".join(f"<th>{esc(k)}</th>" for k in samples[0])
    rows=["<tr>"+"".join(f"<td>{esc(v)}</td>" for v in s.values())+"</tr>" for s in samples]
    sysrows="".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k,v in sysinfo.items())
    page=f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>GHOSTBENCH Report</title><style>body{{font:16px/1.5 system-ui;max-width:950px;margin:30px auto;padding:0 16px;color:#222}}section{{border:1px solid #ccc;border-radius:9px;padding:15px;margin:15px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;border-bottom:1px solid #ddd;padding:7px;overflow-wrap:anywhere}}.note{{background:#fff6dc;padding:12px}}</style>
<h1>GHOSTBENCH Report</h1><p>Version {esc(obj.get("app_version"))} · {esc(obj.get("created_at_utc"))}</p>
<section><h2>Run details</h2><p>Label: {esc(obj.get("label"))}<br>Benchmark: {esc(b.get("benchmark"))}<br>Method: {esc(b.get("method"))}<br>Parameters: {esc(json.dumps(b.get("parameters"),sort_keys=True))}</p></section>
<section><h2>System</h2><table>{sysrows}</table></section>
<section><h2>Metrics</h2><table><tr><th>Metric</th><th>Median</th><th>Mean</th><th>Stdev</th></tr>{"".join(metrics)}</table></section>
<section><h2>Samples</h2><table><tr>{headers}</tr>{"".join(rows)}</table></section>
<p class="note">Interpretation: results are specific to this machine and workload. Repeat tests and control background load before attributing differences to configuration changes.</p></html>"""
    out=output or path.with_suffix(".html"); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(page,encoding="utf-8"); print("Saved report:",out)

def main():
    p=argparse.ArgumentParser(description="GHOSTBENCH: safe local benchmarks")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("system",help="show system info")
    q=sub.add_parser("bench",help="run a benchmark"); q.add_argument("kind",choices=["cpu","memory"])
    q.add_argument("--runs",type=int,default=5); q.add_argument("--output",type=Path)
    q.add_argument("--label",default="baseline"); q.add_argument("--iterations",type=int,default=2_000_000)
    q.add_argument("--size-mib",type=int,default=128); q.add_argument("--block-kib",type=int,default=64)
    c=sub.add_parser("compare",help="compare two compatible JSON results"); c.add_argument("baseline",type=Path); c.add_argument("candidate",type=Path); c.add_argument("--output",type=Path)
    r=sub.add_parser("report",help="create an HTML report"); r.add_argument("input",type=Path); r.add_argument("--output",type=Path)
    a=p.parse_args()
    try:
        if a.cmd=="system": print(json.dumps(system_info(),indent=2))
        elif a.cmd=="bench":
            if not 1<=a.runs<=30: p.error("--runs must be 1..30")
            if not 10_000<=a.iterations<=100_000_000: p.error("--iterations must be 10000..100000000")
            if not 1<=a.size_mib<=512: p.error("--size-mib must be 1..512 MiB")
            if not 1<=a.block_kib<=1024: p.error("--block-kib must be 1..1024 KiB")
            run_bench(a)
        elif a.cmd=="compare":
            result=compare(a.baseline,a.candidate); print(json.dumps(result,indent=2))
            if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
        elif a.cmd=="report": report(a.input,a.output)
    except (OSError,ValueError,json.JSONDecodeError) as e:
        print("Error:",e,file=sys.stderr); return 2
    return 0

if __name__=="__main__": raise SystemExit(main())
