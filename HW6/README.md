# HW6：網站應用與三種測試

本作業使用 **Rust + Axum** 建立 Server，前端使用 HTML、CSS、JavaScript，並示範三種不同層級的測試。網站是一個簡易待辦事項清單，可以新增、完成、篩選及刪除事項。

## 專案架構

```text
HW6/
├── src/
│   ├── lib.rs
│   └── main.rs
├── tests/
│   └── api_tests.rs
├── web/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── e2e/
│   └── task-board.spec.js
├── Cargo.toml
├── package.json
└── playwright.config.js
```

## 使用技術

- Server：Rust、Axum、Tokio
- Client：HTML、CSS、JavaScript
- 單元測試：Rust 內建 `#[test]`
- 系統測試：Rust integration test，透過 HTTP Request 呼叫 Web API Router
- E2E 測試：Playwright + Chromium（Headless）

## 先決條件

請先安裝：
1. Rust（含 Cargo）：<https://www.rust-lang.org/tools/install>
2. Node.js 及 npm：<https://nodejs.org/>

## 啟動網站

在終端機進入 `HW6` 資料夾：

```bash
cargo run
```

開啟瀏覽器前往：<http://127.0.0.1:3000>

## 三種測試

### 1. 單元測試（Unit Test）— Server 必測

位置：`src/lib.rs` 的 `unit_tests` 模組。

測試內容：
- 待辦事項文字會去除前後空白。
- 不允許空白標題。
- 標題不可超過 80 個字。
- 新增事項會取得編號，預設為未完成。
- 完成狀態可以切換。
- 刪除事項後，清單中不再有該事項。

執行：

```bash
cargo test --lib
```

### 2. 系統測試（System Test / Web API Test）

位置：`tests/api_tests.rs`。

透過 HTTP Request 呼叫 Axum Router，測試 API 回應狀態碼與 JSON 資料，不需要開啟真正的瀏覽器。

| Method | API | 用途 |
|---|---|---|
| GET | `/api/health` | 檢查 Server 狀態 |
| GET | `/api/tasks` | 取得所有事項 |
| POST | `/api/tasks` | 新增事項 |
| POST | `/api/tasks/{id}/toggle` | 切換完成狀態 |
| DELETE | `/api/tasks/{id}` | 刪除事項 |

執行：

```bash
cargo test --test api_tests
```

### 3. E2E 測試（End-to-End Test）— Playwright

位置：`e2e/task-board.spec.js`。

Playwright 會啟動 Chromium 無頭瀏覽器，模擬使用者實際操作網站，從前端一路測試到 Server API。

測試內容：
- 網站首頁與空清單顯示。
- 新增待辦事項。
- 完成事項並切換篩選條件。
- 刪除待辦事項。

第一次使用先安裝套件及瀏覽器：

```bash
npm install
npx playwright install chromium
```

執行 E2E 測試：

```bash
npm run test:e2e
```

Playwright 設定會自動執行 `cargo run` 啟動 Server，測試完成後會關閉測試程序。

## 一次執行全部 Server 測試

```bash
cargo test
```

## GitHub Actions

根目錄的 `.github/workflows/hw6-tests.yml` 會在 Push 或 Pull Request 時自動執行 Rust 單元測試、API 系統測試及 Playwright E2E 測試。

## API 範例

新增事項：

```http
POST /api/tasks
Content-Type: application/json

{"title":"完成作業"}
```

成功時回傳 HTTP `201 Created`：

```json
{
  "id": 1,
  "title": "完成作業",
  "completed": false
}
```

> 注意：目前資料儲存在 Server 記憶體中，重新啟動 Server 後會清空。這份作業的重點是展示網站功能與三種測試方式。
