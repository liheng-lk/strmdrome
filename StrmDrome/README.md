# StrmDrome

<div align="center">

![Version](https://img.shields.io/badge/StrmDrome-v2.0-6C63FF?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-amd64%20%7C%20arm64-lightgrey?style=flat-square)
[![Docker](https://img.shields.io/badge/docker-hub-2496ED?style=flat-square&logo=docker)](https://hub.docker.com/r/yourusername/strmdrome)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

**一体化 OpenList STRM 音乐流媒体服务器**  
*刮削 · 反代 · 播放 · 全功能 Subsonic API*

</div>

---

## ✨ 简介

StrmDrome 是专为 `.strm` 音乐文件打造的 **全功能 Navidrome 替代方案**。它解决了 Navidrome 无法识别 `.strm` 文件的根本问题，同时保留了所有您喜爱的功能。

| 功能 | 描述 |
|------|------|
| 🎵 **零带宽直链播放** | 读取 `.strm` 内链接，`302 Redirect` 直达 OpenList/网盘，服务器零流量 |
| 🔍 **智能文件名解析** | 自动识别任意杂乱命名（`Artist - Song`、`01. Song`、`[2020]` 等） |
| 📡 **5 级元数据刮削** | NFO → 本地缓存 → 网易云 → MusicBrainz → LastFM 逐级降级 |
| 🎨 **Subsonic API** | 50+ 端点，兼容 Feishin、音流、DSub 等所有主流客户端 |
| 👥 **多用户支持** | bcrypt 加密，完整用户管理 API |
| 📋 **播放列表/收藏** | 创建、共享播放列表，星标、评分、Scrobble 记录 |
| 🔎 **全库搜索** | 艺人、专辑、歌曲模糊搜索 (search3) |
| 🗂️ **目录完全隔离** | `/music` 只读，所有元数据写入 `/data/catalog` |
| 🐳 **Docker 多平台** | 支持 `linux/amd64` 和 `linux/arm64`（NAS 友好） |

---

## 🚀 快速开始

### Docker Compose（推荐）

```yaml
version: '3.8'
services:
  strmdrome:
    image: yourusername/strmdrome:latest
    container_name: strmdrome
    restart: unless-stopped
    ports:
      - "4533:4533"
    volumes:
      - /your/music:/music:ro     # ← 修改为你的 .strm 文件目录
      - ./data:/data
    environment:
      ADMIN_USER: admin
      ADMIN_PASS: changeme        # ← 务必修改此密码！
      NETEASE_ENABLED: "true"
      LASTFM_API_KEY: ""          # ← 可选，填入后开启艺人传记
```

```bash
docker compose up -d
```

### 本地运行（开发环境）

```bash
git clone https://github.com/yourusername/strmdrome
cd strmdrome/StrmDrome

pip install -r requirements.txt
touch db/__init__.py services/__init__.py api/__init__.py utils/__init__.py

export MUSIC_DIR="/your/music"
export DATA_DIR="./data"
python main.py
```

---

## 📂 目录结构 & 命名规范

StrmDrome 内置智能解析器，无需手动整理文件：

```
/music/ (只读挂载)
  Taylor Swift/
    1989/
      01 - Style.strm            ✅ 推荐：艺人/专辑/曲目-标题
      02 Blank Space.strm        ✅ 无连字符也可
  Artist - Song.strm             ✅ 扁平 艺人-歌曲 格式
  Song [2020] (feat. X).strm    ✅ 括号标记年份/特约

/data/ (可写，自动创建)
  strmdrome.db                   ← SQLite 主库
  catalog/
    Taylor Swift/
      1989/
        cover.jpg                ← 自动下载封面
        01 - Style.json          ← 刮削缓存（防重复）
        01 - Style.lrc           ← 同步歌词（若存在）
```

---

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MUSIC_DIR` | `/music` | `.strm` 文件根目录（只读） |
| `DATA_DIR` | `/data` | 数据目录（DB、封面、缓存） |
| `ADMIN_USER` | `admin` | 默认管理员用户名 |
| `ADMIN_PASS` | `admin` | 默认管理员密码（**请务必修改！**） |
| `PORT` | `4533` | 服务监听端口 |
| `NETEASE_ENABLED` | `true` | 是否启用网易云音乐刮削 |
| `LASTFM_API_KEY` | `` | LastFM API Key（可选） |
| `SCAN_ON_STARTUP` | `true` | 启动时自动扫描 |
| `SCAN_INTERVAL_HOURS` | `24` | 自动重扫间隔（小时） |
| `SCRAPE_CONCURRENCY` | `4` | 并行刮削线程数 |

---

## 📱 推荐客户端

| 客户端 | 平台 | 推荐度 |
|--------|------|--------|
| [Feishin](https://github.com/jeffvli/feishin) | Desktop | ⭐⭐⭐⭐⭐ |
| [音流](https://apps.apple.com/app/id1635975990) | iOS / Android | ⭐⭐⭐⭐⭐ |
| [DSub](https://play.google.com/store/apps/details?id=github.daneren2005.dsub) | Android | ⭐⭐⭐⭐ |
| [play:Sub](https://apps.apple.com/app/id955329386) | iOS | ⭐⭐⭐⭐ |

**连接信息：** `http://server-ip:4533` · 用 `docker-compose.yml` 中设置的账号密码

---

## 🐳 Docker Hub

```bash
# 自动选择 amd64 / arm64
docker pull yourusername/strmdrome:latest

# 指定版本
docker pull yourusername/strmdrome:2.0.0
```

---

## 🔧 API 端点总览

<details>
<summary>展开查看完整端点列表（50+）</summary>

- **System:** `ping` `getLicense` `getMusicFolders` `getScanStatus` `startScan`
- **Browsing:** `getArtists` `getArtist` `getAlbum` `getSong` `getGenres` `getArtistInfo` `getMusicDirectory` `getIndexes`
- **Album Lists:** `getAlbumList2` (random / newest / recent / frequent / starred / byGenre / byYear)
- **Discovery:** `getRandomSongs` `getSongsByGenre` `getNowPlaying` `getStarred` `getStarred2`
- **Search:** `search` `search2` `search3`
- **Media:** `stream` (302) `download` `getCoverArt` `getLyrics` `getAvatar`
- **Playlists:** `getPlaylists` `getPlaylist` `createPlaylist` `updatePlaylist` `deletePlaylist`
- **Annotations:** `star` `unstar` `setRating` `scrobble`
- **Users:** `getUser` `getUsers` `createUser` `updateUser` `deleteUser` `changePassword`

</details>

---

## 📝 License

MIT License — Copyright (c) 2026 StrmDrome Contributors
