# TVBox / OK影视 直播源

自动从 iptv-org 拉取中国公开频道，测活后生成 TVBox 标准直播源 `live.txt`。

## 用法

把下面地址填进 TVBox / OK影视 的「直播源」：

```
https://Trysknee01.github.io/tvbox-live/live.txt
```

（把 `Trysknee01` 换成你的 GitHub 用户名；仓库名 `tvbox-live` 与实际一致）

## 自动更新

GitHub Actions 每天 06:00 (UTC) 自动重拉数据源、剔除死链、重新生成并 push `live.txt`，
所以源永远是最新的、可播的。

手动触发：仓库 Actions 页 → Update Live Source → Run workflow

## 文件说明

- `make_live_source.py` 生成脚本（拉源→测活→输出 `live.txt`）
- `live.txt` 生成的直播源（TVBox 格式：`频道名,URL`，`#genre#` 分组）
- `.github/workflows/update.yml` 每日自动更新
