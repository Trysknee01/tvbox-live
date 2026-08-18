#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 TVBox / OK影视 可用的直播源 live.txt（增强版）
- 分类: 央视频道 / 卫视频道 / 网络频道 / 海外频道
- 多线路: 同频道不同分辨率保留为不同线路，按质量排序
- 健康检测: 并发测活，仅保留存活流
- EPG: 引用公共节目表源
用法: python3 make_live_source.py [--out live.txt] [--workers 32]
"""
import sys, re, os, argparse, urllib.request, concurrent.futures, ssl
from collections import defaultdict

IPTV_CN = "https://iptv-org.github.io/iptv/countries/cn.m3u"
SUPPRISE = "https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt"
TIMEOUT = 12
CT_OK = ("application/vnd.apple.mpegurl", "application/x-mpegurl",
         "application/mpegurl", "video/mp2t", "application/octet-stream")
EPG_URL = "https://epg.112114.xyz/epginfo"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ─── 频道分类规则 ────────────────────────────────────────────────
# 优先级从高到低匹配，命中第一个分类即停

CATEGORY_ORDER = ["央视频道", "卫视频道", "网络频道", "海外频道"]

# 央视频道关键词
CCTV_KEYWORDS = [
    "cctv", "央视", "中央",
    "cctv+", "cctv-", "cctv1", "cctv2", "cctv3", "cctv4", "cctv5",
    "cctv6", "cctv7", "cctv8", "cctv9", "cctv10", "cctv11", "cctv12",
    "cctv13", "cctv14", "cctv15", "cctv16", "cctv17",
    "cctv-8k", "cctv 8k",
    "cctv-billiards", "cctv-golf", "cctv-storm", "cctv-the first",
    "cctv-weapon", "cctv-women", "cctv-world",
]

# 卫视频道关键词（省名 + 卫视）
SATELLITE_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
    "深圳", "厦门", "大连", "青岛", "宁波",
]

OVERSEAS_KEYWORDS = [
    "abn", "cgtn", "凤凰", "凤凰卫视", "翡翠", "明珠", "明珠台",
    "澳亚", "澳卫视", "澳门", "台湾", "东森", "中天", "tvbs",
    "now", "hong kong", "hk", "macau", "taiwan",
    "星空", "viu", "channel v", "凤凰资讯", "凤凰香港",
    "南方卫视",  # 虽是大陆，但部分归类为海外
]

# ─── 工具函数 ──────────────────────────────────────────────────

def fetch(url):
    """用 curl 拉取（绕过 Python SSL 问题）"""
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(TIMEOUT), "-k", url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
        print(f"  ⚠ curl 失败 {url}: rc={r.returncode}")
        return ""
    except Exception as e:
        print(f"  ⚠ 拉取失败 {url}: {e}")
        return ""


def normalize_name(name):
    """统一频道名：去掉分辨率/质量标签、统一空格和标点"""
    name = name.strip()
    # 去掉 (720p) (1080p) 等分辨率标记
    name = re.sub(r'\s*\(\d+[pi]\)', '', name)
    # 去掉 [Not 24/7] 等备注
    name = re.sub(r'\s*\[[^\]]*\]', '', name)
    # 统一 CCTV 写法：CCTV1 → CCTV-1, CCTV 1 → CCTV-1
    name = re.sub(r'^CCTV\s*(\d)', r'CCTV-\1', name)
    # 去掉尾部空格
    name = name.strip()
    return name


def extract_resolution(name):
    """从原始频道名中提取分辨率信息，用于质量排序"""
    m = re.search(r'\((\d+)[pi]\)', name)
    if m:
        return int(m.group(1))
    # 从 URL 或上下文推断
    if "1080" in name:
        return 1080
    if "720" in name:
        return 720
    if "8k" in name.lower():
        return 8000
    return 0  # 未知


def classify_channel(name):
    """根据频道名判断分类"""
    lower = name.lower()

    # 央视
    for kw in CCTV_KEYWORDS:
        if kw in lower:
            return "央视频道"

    # 卫视
    for prov in SATELLITE_PROVINCES:
        if prov in name and "卫视" in name:
            return "卫视频道"

    # 海外
    for kw in OVERSEAS_KEYWORDS:
        if kw in lower:
            return "海外频道"

    # 默认归入网络频道
    return "网络频道"


def parse_iptv_org(text):
    """解析 m3u: 返回 {normalized_name: [(original_name, url), ...]}"""
    out = defaultdict(list)
    lines = text.splitlines()
    cur = None
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("#EXTINF"):
            m = re.search(r'tvg-name="([^"]*)"', ln)
            cur = (m.group(1).strip() if m and m.group(1).strip()
                   else ln.split(",")[-1].strip() or "未知台")
        elif ln and not ln.startswith("#"):
            if re.search(r"\.(png|jpg|jpeg|gif|webp)$", ln, re.I):
                continue
            if ln.startswith("http"):
                norm = normalize_name(cur or "未知台")
                out[norm].append((cur or "未知台", ln))
    return out


def parse_tvbox_txt(text):
    """解析 TVBox 格式: 频道名,http://url (支持 #genre# 分组)"""
    out = defaultdict(list)
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if "," not in ln:
            continue
        name, url = ln.split(",", 1)
        name, url = name.strip(), url.strip()
        if url.startswith("http"):
            norm = normalize_name(name)
            out[norm].append((name, url))
    return out


def health_check(item):
    """item = (norm_name, original_name, url) → (norm_name, original_name, url, alive)"""
    norm_name, orig_name, url = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            code = r.status
            if code >= 400:
                return (norm_name, orig_name, url, False)
            body = r.read(2048).decode("utf-8", "ignore")
            if "#EXTM3U" in body or ".ts" in body or "EXT-X-STREAM-INF" in body:
                return (norm_name, orig_name, url, True)
            if code in (301, 302, 307):
                loc = r.headers.get("Location")
                if loc:
                    try:
                        req2 = urllib.request.Request(loc, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req2, timeout=TIMEOUT, context=ctx) as r2:
                            b2 = r2.read(2048).decode("utf-8", "ignore")
                            if "#EXTM3U" in b2 or ".ts" in b2:
                                return (norm_name, orig_name, url, True)
                    except Exception:
                        pass
            return (norm_name, orig_name, url, False)
    except Exception:
        return (norm_name, orig_name, url, False)


def sort_streams_by_quality(streams):
    """按分辨率降序排列，1080p > 720p > 其他"""
    def key(item):
        orig_name, _ = item
        return -extract_resolution(orig_name)
    return sorted(streams, key=key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.txt"))
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    print("[1/5] 拉取数据源 ...")
    s1 = fetch(IPTV_CN)
    s2 = fetch(SUPPRISE)
    print(f"  iptv-org: {len(s1)} 字节 | Supprise: {len(s2)} 字节")

    print("[2/5] 解析 + 合并（保留多线路）...")
    merged = defaultdict(list)
    for norm_name, streams in parse_iptv_org(s1).items():
        merged[norm_name].extend(streams)
    for norm_name, streams in parse_tvbox_txt(s2).items():
        merged[norm_name].extend(streams)

    # 去重（同 norm_name + 同 url 只保留一条）
    for norm_name in merged:
        seen_urls = set()
        deduped = []
        for orig, url in merged[norm_name]:
            if url not in seen_urls:
                seen_urls.add(url)
                deduped.append((orig, url))
        merged[norm_name] = deduped

    # 展开为健康检测任务列表
    tasks = []
    for norm_name, streams in merged.items():
        for orig, url in streams:
            tasks.append((norm_name, orig, url))

    print(f"  合并后频道组: {len(merged)} | 总流数: {len(tasks)}")

    print(f"[3/5] 并发健康检测 ({args.workers} 线程) ...")
    alive_streams = defaultdict(list)  # norm_name → [(orig, url), ...]
    dead = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for norm_name, orig_name, url, ok in ex.map(health_check, tasks):
            if ok:
                alive_streams[norm_name].append((orig_name, url))
            else:
                dead += 1
    total_alive = sum(len(v) for v in alive_streams.values())
    print(f"  存活: {total_alive} 流 / {len(alive_streams)} 频道 | 死亡: {dead}")

    print("[4/5] 分类 + 排序 ...")
    categories = {cat: [] for cat in CATEGORY_ORDER}
    for norm_name, streams in alive_streams.items():
        cat = classify_channel(norm_name)
        sorted_streams = sort_streams_by_quality(streams)
        categories[cat].append((norm_name, sorted_streams))

    # 各分类内按名称排序
    for cat in categories:
        categories[cat].sort(key=lambda x: x[0])

    print("[5/5] 写入 live.txt ...")
    with open(args.out, "w", encoding="utf-8") as f:
        for cat in CATEGORY_ORDER:
            channels = categories[cat]
            if not channels:
                continue
            f.write(f"{cat},#genre#\n")
            for norm_name, streams in channels:
                # 多线路：同频道多 URL 直接列出，TVBox 会自动轮询
                for orig, url in streams:
                    f.write(f"{norm_name},{url}\n")
            f.write("\n")

    print(f"完成 -> {args.out}")
    for cat in CATEGORY_ORDER:
        count = len(categories[cat])
        if count:
            print(f"  {cat}: {count} 个频道")


if __name__ == "__main__":
    main()
