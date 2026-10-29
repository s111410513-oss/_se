# HW5：Docker 微服務系統建置

> 學習目標：學會使用 Docker、撰寫 `Dockerfile`、`docker-compose.yml`，並整合多個服務建構一個微服務系統。

## 1. 學習筆記（Docker 學習記錄）

在這次作業中學習到以下 Docker 核心概念：

| 概念 | 說明 |
|---|---|
| **Image（映像檔）** | Docker 的靜態模板，包含應用程式執行所需的程式碼、環境、套件等。可透過 `Dockerfile` 建置。 |
| **Container（容器）** | 由 Image 建立的執行實例。每個容器都是隔離的，可獨立執行且不影響其他容器。 |
| **Dockerfile** | 用來定義如何建置 Image 的腳本檔案，常用指令有 `FROM`、`WORKDIR`、`COPY`、`RUN`、`EXPOSE`、`CMD` 等。 |
| **docker-compose.yml** | 用 YAML 格式定義多個容器服務（Service）、網路（Network）、資料卷（Volume），可一次啟動整個系統。 |
| **Network（網路）** | Docker 內部的虛擬網路，讓同一個網路下的容器能透過服務名稱（Service Name）互相溝通（DNS 解析）。 |
| **Volume（資料卷）** | 用來持久化資料，避免容器刪除後資料遺失。此專案使用 Volume 保存 PostgreSQL 的資料。 |
| **Reverse Proxy（反向代理）** | 透過 Nginx 將外部請求轉發到內部不同的微服務，統一由單一入口（Port 80）對外提供服務。 |

### 常用指令

```bash
# 建置並啟動所有服務（背景執行）
docker compose up -d --build

# 查看執行中的容器
docker compose ps

# 查看各服務日誌
docker compose logs -f

# 停止並移除容器、網路（保留 Volume）
docker compose down

# 停止並移除容器、網路、Volume（完全清除資料）
docker compose down -v

# 進入容器內部
docker compose exec node-api sh
```

## 2. 系統架構

本系統採用 **微服務（Microservices）** 架構，所有服務皆運行於同一個自訂 Docker Network `se_hw5_net` 中，由 Nginx 統一作為 Web Server 與 Reverse Proxy。

```text
瀏覽器 (http://localhost:8080)
            │
           ▼
        [ Nginx :80 ]
            │
            ├── /                -> Web 靜態介面
            ├── /api/node/*      -> node-api (Node.js + Express) :3000
            ├── /api/rust/*      -> rust-api  (Rust + Actix Web)   :8081
            ├── /api/python/*    -> python-api (Python + Flask)    :5000
            └── (db 查詢由各 API 連接) 
                      │
                     ▼
                [ PostgreSQL :5432 ]
```

### 服務清單

| 服務 | 類型 | 說明 |
|---|---|---|
| **nginx** | Web Server / Reverse Proxy | 對外唯一入口，負責路由請求至對應的微服務與靜態網頁。 |
| **postgres** | 資料庫 | 使用 `postgres:16-alpine`，透過 `init.sql` 初始化 `services` 資料表。 |
| **node-api** | 微服務（Node.js） | 使用 Node.js + Express，提供 REST API 並查詢 PostgreSQL。 |
| **rust-api** | 微服務（Rust） | 使用 Rust + Actix Web，示範以 Rust 撰寫的 API 服務並連接資料庫。 |
| **python-api** | 微服務（Python） | 使用 Python + Flask，示範以 Python 撰寫的 API 服務並連接資料庫。 |
| **web** | 前端靜態介面 | 簡易 HTML/JS 頁面，用來展示本 Docker 微服務系統的架構與即時 API 狀態。 |

## 3. 檔案結構

```text
HW5/
├── README.md
├── docker-compose.yml
├── .env
├── db/
│   └── init.sql
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
├── web/
│   └── index.html
├── node-api/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       └── index.js
├── rust-api/
│   ├── Dockerfile
│   ├── Cargo.toml
│   └── src/
│       └── main.rs
└── python-api/
    ├── Dockerfile
    ├── requirements.txt
    └── app.py
```

## 4. 環境變數

根目錄的 `.env` 設定 PostgreSQL 連線資訊：

```env
POSTGRES_USER=se_user
POSTGRES_PASSWORD=se_password
POSTGRES_DB=se_hw5
```

## 5. 啟動方式

### 前置需求
- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### 操作步驟

1. 進入 HW5 資料夾
   ```bash
   cd HW5
   ```

2. 建置並啟動所有服務
   ```bash
   docker compose up -d --build
   ```

3. 開啟瀏覽器訪問簡易 Web 介面
   ```
   http://localhost:8080
   ```

4. 測試個別 API
   ```bash
   curl http://localhost:8080/api/node/health
   curl http://localhost:8080/api/node/services
   curl http://localhost:8080/api/rust/health
   curl http://localhost:8080/api/python/health
   ```

5. 停止系統
   ```bash
   docker compose down
   ```

## 6. 簡易 Web 介面說明

訪問 `http://localhost:8080` 後，頁面會顯示：

- **系統架構概覽**：列出 Nginx、PostgreSQL、Node.js、Rust、Python 等服務
- **Docker 學習重點**：簡短說明本次實作用到的概念
- **即時 API 測試**：透過 JavaScript 呼叫 `/api/node/health`、`/api/rust/health`、`/api/python/health` 並顯示回應結果
- **資料庫資料展示**：從 Node API 取得 `services` 表內容，展示微服務清單

## 7. 心得

透過這次作業，從零開始學習 Docker 的使用方式，體會到：

- 使用 `Dockerfile` 將不同語言（Node.js、Rust、Python）的應用打包成獨立 Image
- 透過 `docker-compose` 一鍵管理多個微服務，大幅簡化啟動流程
- 利用 Nginx Reverse Proxy 統一入口，讓前端能用同一個 Port 存取不同的 API
- 使用 PostgreSQL + Volume 實現資料持久化
- 在容器間透過 Service Name 溝通比直接用 IP 更具可維護性

整體而言，Docker 確實很適合用來建構、測試與整合微服務系統，對於未來開發與部署都相當實用。
