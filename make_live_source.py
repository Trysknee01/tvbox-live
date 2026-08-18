#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 TVBox / OK影视 可用的直播源 live.txt
- 数据源1: iptv-org 中国频道 (干净、无时效签名，长期可用)
- 数据源2: Supprise0901/TVBox_live 的 live.txt (含 CCTV/卫视直链，部分带时效签名)
- 步骤: 拉取 -> 解析 -> 合并去重 -> 并发健康检测 -> 仅保留存活 -> 写 live.txt
用法: python3 make_live_source.py [--out live.txt]
"""
import sys, re, os, argparse, urllib.request, concurrent.futures, ssl

IPTV_CN = "https://iptv-org.github.io/iptv/countries/cn.m3u"
SUPPRISE = "https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt"
TIMEOUT = 12
CT_OK = ("application/vnd.apple.mpegurl", "application/x-mpegurl",
         "application/mpegurl", "video/mp2t", "application/octet-stream")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        return ""


def parse_iptv_org(text):
    """解析 m3u: #EXTINF 后取频道名 + 紧随其后的流URL"""
    out = {}
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
                # 同频多源去重保留第一条
                out.setdefault(cur or "未知台", ln)
    return out


def parse_tvbox_txt(text):
    """解析 TVBox 格式: 频道名,http://url (支持 #genre# 分组)"""
    out = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if "," not in ln:
            continue
        name, url = ln.split(",", 1)
        name, url = name.strip(), url.strip()
        if url.startswith("http"):
            out.setdefault(name, url)
    return out


def health_check(name_url):
    name, url = name_url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            code = r.status
            if code >= 400:
                return (name, url, False)
            body = r.read(2048).decode("utf-8", "ignore")
            # 必须是真·m3u8 播放列表正文（排除空响应/错误页/HTML）
            if "#EXTM3U" in body or ".ts" in body or "EXT-X-STREAM-INF" in body:
                return (name, url, True)
            # 302 跳转: 跟随一次再判（很多直链靠 CDN 跳转）
            if code in (301, 302, 307):
                loc = r.headers.get("Location")
                if loc:
                    try:
                        req2 = urllib.request.Request(loc, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req2, timeout=TIMEOUT, context=ctx) as r2:
                            b2 = r2.read(2048).decode("utf-8", "ignore")
                            if "#EXTM3U" in b2 or ".ts" in b2:
                                return (name, url, True)
                    except Exception:
                        pass
            return (name, url, False)
    except Exception:
        return (name, url, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.txt"))
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    print("[1/4] 拉取数据源 ...")
    s1 = fetch(IPTV_CN)
    s2 = fetch(SUPPRISE)
    print(f"  iptv-org: {len(s1)} 字节 | Supprise: {len(s2)} 字节")

    print("[2/4] 解析 + 合并去重 ...")
    merged = {}
    merged.update(parse_iptv_org(s1))
    merged.update(parse_tvbox_txt(s2))
    items = list(merged.items())
    print(f"  合并后频道数: {len(items)}")

    print(f"[3/4] 并发健康检测 ({args.workers} 线程) ...")
    alive = []
    dead = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for name, url, ok in ex.map(health_check, items):
            if ok:
                alive.append((name, url))
            else:
                dead += 1
    print(f"  存活: {len(alive)} | 死亡: {dead}")

    print(f"[4/4] 写入 {args.out} ...")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("#genre#\n")
        for name, url in alive:
            f.write(f"{name},{url}\n")
    print(f"完成 -> {args.out} ({len(alive)} 个可用频道)")


if __name__ == "__main__":
    main()
