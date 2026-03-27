# Cloud-Navidrome 🎵☁️

> **Navidrome 官方分支** — 原生支持 `.strm` 文件完整播放、云端元数据抓取、零带宽 302 重定向。

## 特性对比

| 功能 | 原版 Navidrome | Cloud-Navidrome |
| :--- | :---: | :---: |
| `.strm` 文件扫描 | ❌ 忽略 | ✅ 原生识别 |
| 远端 ID3/FLAC 标签抓取 | ❌ 报错 | ✅ HTTP Range 远端萃取 |
| 零带宽 302 直链播放 | ❌ 经服务器转发 | ✅ HTTP 302 直接重定向 |
| Feishin / 音流 等客户端 | ✅ | ✅ |
| 多语言 WebUI | ✅ | ✅ |
| MusicBrainz / LastFM | ✅ | ✅ |

## 快速部署（Docker）

```bash
mkdir navidrome-data
# 修改下方 /your/strm/music 为您实际存放 .strm 文件的目录
docker run -d \
  --name cloud-navidrome \
  --restart unless-stopped \
  -p 4533:4533 \
  -v /your/strm/music:/music:ro \
  -v $(pwd)/navidrome-data:/data \
  liheng6668/cloud-navidrome:latest
```

或使用 `docker-compose.yml`：

```yaml
services:
  navidrome:
    image: liheng6668/cloud-navidrome:latest
    restart: unless-stopped
    ports:
      - "4533:4533"
    volumes:
      - /your/strm/music:/music:ro
      - ./navidrome-data:/data
```

然后运行：
```bash
docker compose up -d
```

## 访问 Web 界面

打开 `http://服务器IP:4533`，首次访问自动设置管理员账号。

## .strm 文件格式

每个 `.strm` 文件只需一行，内容为云盘媒体的直链 URL：

```
https://your-alist-server.com/dav/Music/Song.mp3?sign=xxxxx
```

可使用 [AList](https://github.com/alist-org/alist) / [OpenList](https://github.com/OpenListTeam/OpenList) 等工具批量生成。

## 工作原理

1. **文件扫描**：`.strm` 被识别为音频文件加入库
2. **元数据**：扫描时对目标 URL 发送 `Range: bytes=0-131071` 请求，用前 128KB 解析 ID3/FLAC 标签
3. **播放**：点击播放时，服务器读取 `.strm` 中的 URL，返回 `HTTP 302` 重定向给客户端，零带宽消耗

## 修改的核心文件

| 文件 | 修改内容 |
| :--- | :--- |
| `model/file_types.go` | 新增 `.strm` 音频 MIME 白名单 |
| `adapters/gotaglib/gotaglib.go` | HTTP Range 远端 ID3 标签代理 |
| `server/subsonic/stream.go` | `.strm` → HTTP 302 重定向逻辑 |

## 构建自定义镜像

```bash
git clone https://github.com/liheng-lk/navidrome-strm
cd navidrome-strm
docker buildx build -f Dockerfile.strm --platform linux/amd64,linux/arm64 \
  -t myrepo/cloud-navidrome:latest --push .
```

## License

基于 [Navidrome](https://github.com/navidrome/navidrome) (GPL-3.0) 分支构建，遵循相同开源协议。
