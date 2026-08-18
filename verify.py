#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽 6 条 live.txt 里的源，深度验证返回的是真·m3u8 播放列表"""
import urllib.request, ssl, re
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

# 抽几个代表性频道
picks = [
    ("CCTV-1",  "http://74.91.26.218:82/live/cctv1hd.m3u8"),
    ("CCTV-13", "http://74.91.26.218:82/live/cctv13hd.m3u8"),
]
# 从 live.txt 再补几条
try:
    for ln in open("/opt/data/live_source/live.txt", encoding="utf-8"):
        ln=ln.strip()
        if not ln or ln.startswith("#"): continue
        n,u = ln.split(",",1)
        if any(k in n for k in ["北京卫视","湖南卫视","东方卫视","广东卫视"]):
            picks.append((n,u))
        if len(picks)>=6: break
except Exception as e:
    print("read err", e)

for name,url in picks[:6]:
    try:
        req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
            body=r.read(600).decode("utf-8","ignore")
        ok = "#EXTM3U" in body or ".ts" in body or "EXT-X-STREAM-INF" in body
        print(f"[{'OK' if ok else 'XX'}] {name}")
        print("    "+body.replace(chr(10),' | ')[:140])
    except Exception as e:
        print(f"[ER] {name}: {e}")
