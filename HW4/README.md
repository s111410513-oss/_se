# Git Flow 與 GitHub Flow 用法說明

本文件以 [se-test-examples/git-examples](https://github.com/se-test-examples/git-examples) 與 [ccckmit/git-examples](https://github.com/ccckmit/git-examples) 的實際歷史作為案例，說明「分支」「合併」「fork」「pull request」如何操作，以及對應哪種 Git 流程。

## 參考資料

- [阮一峰：Git 工作流程](https://www.ruanyifeng.com/blog/2015/12/git-workflow.html)
- [ByteByteGo：How does Git work?](https://bytebytego.com/guides/how-does-git-work/)

---

## 流程概觀

### 1. Git Flow（傳統 Vincent Driessen 模式）
Git Flow 適合有明確版本發布週期（release cycle）的專案。常用長期分支：
- `main`（或 `master`）：僅用於已釋出的穩定版本
- `develop`：整合各功能分支的開發主線
- `feature/*`：功能開發分支，從 `develop` 切出，完成後合併回 `develop`
- `release/*`：從 `develop` 切出，用於預發布測試與版本調整，測試通過後同時合併回 `develop` 與 `main`，並打 tag
- `hotfix/*`：從 `main` 切出，用於緊急修復上線版本，修復後合併回 `main` 與 `develop`

**特點：** 分支較多、流程嚴謹，合併多半採用 `--no-ff` 來保留分支歷史。

### 2. GitHub Flow（輕量化流程）
GitHub Flow 適合持續部署（CD）的專案。結構簡單：
- `main`：永遠處於可部署狀態
- `feature/*`（或任意描述性名稱）：從 `main` 切出，直接在此分支開發
- 完成後開啟 Pull Request，經審查、討論、測試通過後直接合併回 `main` 並可立即部署

**特點：** 僅有 `main` + 功能分支，強調小而快的 PR、持續整合與持續部署。

---

## 實際案例對照

本案例中的關係：
- 母專案（原始倉庫）：[se-test-examples/git-examples](https://github.com/se-test-examples/git-examples)
  - `main`：最終有 `Initial commit` → `add gitBranch.md` → `Merge pull request #1`（引入 fork 的變更）
  - `developGitBranch`：`Initial commit` → `add gitBranch.md`（僅此分支上的歷史）
- 子專案（fork 後的倉庫）：[ccckmit/git-examples](https://github.com/ccckmit/git-examples)
  - `main`：從母專案 fork 後，加入 `add gitBranch.md`、`add ccckmitFork.md`，再透過 PR 回饋給母專案

觀察提交時間與結構，可以判斷這個案例比較符合 **GitHub Flow** 的做法（fork + 功能分支 + PR 合併回母專案 `main`），而非完整的 Git Flow（沒有從 `develop` 切出 release/hotfix、也沒有同時合併至 develop/main 的多重合併模式）。

---

## 操作步驟與對應指令

以下分為「本地 Git CLI」與「GitHub 網頁操作」兩種方式來說明。實際做法多半是兩者混用。

### 1. 分支（Branch）

#### 使用本地 Git
```bash
# 確認目前分支
git branch

# 從目前分支建立並切換到新分支（建議用描述性名稱）
git checkout -b feature/add-something
# 或使用較新的指令
git switch -c feature/add-something

# 將新分支推送到遠端（首次推送需設定上游）
git push -u origin feature/add-something
```

#### GitHub 網頁操作
1. 前往倉庫頁面 → 點選 `Branch: main` 下拉選單
2. 輸入新分支名稱（例如 `developGitBranch`）並點選 `Create branch`
3. 切換到新分支後即可開始新增/修改檔案並 commit

**案例對照：** 母專案曾出現 `developGitBranch`，從 commits 可見其僅包含 `Initial commit` 與 `add gitBranch.md`，顯示以該分支進行開發後的提交。

### 2. 合併（Merge）

#### 使用本地 Git（將功能分支合併回目標分支）
```bash
# 切換到要合併進去的目標分支（例如 main）
git switch main

# 確保目標分支是最新的
git pull origin main

# 合併功能分支（預設 fast-forward，若要保留分支歷史可加 --no-ff）
git merge feature/add-something
# 或保留 merge commit：git merge --no-ff feature/add-something

# 推送合併後的結果
git push origin main

# （可選）刪除已合併的分支
git branch -d feature/add-something
git push origin --delete feature/add-something
```

#### GitHub 網頁操作（透過 Pull Request 合併最常見）
1. 在 PR 頁面點選 `Merge pull request`（可選擇 `Create a merge commit`、`Squash and merge`、`Rebase and merge`）
2. 確認合併訊息後點選 `Confirm merge`
3. 可選擇刪除來源分支

**案例對照：** 母專案 `main` 出現 `Merge pull request #1 from ccckmit/main`，這正是透過 PR 合併 fork 來源分支的結果。

### 3. Fork（複製他人倉庫到自己的帳號下）

#### GitHub 網頁操作（最常用）
1. 前往母專案頁面：[se-test-examples/git-examples](https://github.com/se-test-examples/git-examples)
2. 點選右上角 `Fork` → 選擇自己的帳號
3. 等待 GitHub 建立 fork（會產生 `https://github.com/<你的帳號>/git-examples`）

Fork 完成後，就能在自己的帳號下自由地 push、建立分支，不會直接影響原始倉庫。

#### 本地設定（fork 後的工作流）
```bash
# 複製自己的 fork 到本地
git clone https://github.com/ccckmit/git-examples.git
cd git-examples

# 新增原始倉庫為 upstream（方便日後同步）
git remote add upstream https://github.com/se-test-examples/git-examples.git

# 確認 remotes
git remote -v
# origin    -> https://github.com/ccckmit/git-examples.git (你的 fork)
# upstream  -> https://github.com/se-test-examples/git-examples.git (原始倉庫)

# 同步 upstream 的最新變更到本地
git fetch upstream
git switch main
git merge upstream/main  # 或 git rebase upstream/main
git push origin main
```

**案例對照：** [ccckmit/git-examples](https://github.com/ccckmit/git-examples) 即為從母專案 fork 出來的子專案。

### 4. Pull Request（請求原始倉庫合併你的變更）

#### GitHub 網頁操作（標準流程）
1. 在自己的 fork（子專案）中，將變更 commit 並 push 到某個分支（通常是 `main` 或功能分支）
2. 前往 GitHub，會自動出現 `Compare & pull request` 按鈕，或手動到母專案的 `Pull requests` → `New pull request` → 選擇 `compare across forks`
3. 選擇 base repository（母專案）、base branch（通常是 `main`）、head repository（你的 fork）、compare branch（你的變更所在分支）
4. 填寫標題與說明，說明變更內容與原因
5. 點選 `Create pull request`，等待審查者 review、討論
6. 審查通過後，由母專案維護者點選 `Merge pull request` 完成合併

#### 本地補充（可在 PR 中持續更新）
```bash
# 在你的 fork 分支上繼續修改、提交
git add .
git commit -m "update: ..."
git push origin <你的分支>
# 推送後 PR 會自動更新
```

**案例對照：** `ccckmit/git-examples/main` 新增了 `ccckmitFork.md`，並發起 PR 合併到 `se-test-examples/git-examples/main`，最終產生 merge commit `Merge pull request #1 from ccckmit/main`。

---

## 案例歷史對照表

| 倉庫/分支 | 提交歷史 | 對應操作 |
|---|---|---|
| [se-test-examples/git-examples/main](https://github.com/se-test-examples/git-examples/commits/main/) | `Initial commit` → `add gitBranch.md` → `add ccckmitFork.md`（經 PR 合併） → `Merge pull request #1` | 母專案原始狀態 + 接受 fork 的貢獻並合併 |
| [se-test-examples/git-examples/developGitBranch](https://github.com/se-test-examples/git-examples/commits/developGitBranch/) | `Initial commit` → `add gitBranch.md` | 母專案上建立的開發分支（`add gitBranch.md` 僅在此分支） |
| [ccckmit/git-examples/main](https://github.com/ccckmit/git-examples/commits/main/) | `Initial commit` → `add gitBranch.md` → `add ccckmitFork.md` | fork 後在子專案上開發並新增貢獻檔案，準備發起 PR |

---

## 結論：屬於哪種 Git 流程？

這個案例屬於 **GitHub Flow**。

理由：
- 只有 `main` 作為主要整合分支（母專案接受來自 fork 的 PR 直接合併至 `main`），沒有長期的 `develop` 分支作為唯一整合線再往 `main` 發佈的 Git Flow 結構。
- 使用 `fork` + `Pull Request` 的協作模式，這是 GitHub 生態系中最典型的開源協作方式，也正是 GitHub Flow 所推崇的「從 `main` 切分支 → PR 審查 → 合併回 `main`」思路。
- 雖然母專案也有 `developGitBranch`，但從整體合併路徑（最終合併至 `main`）以及僅有一個 merge commit 的情況來看，並非完整的 Git Flow（Git Flow 通常會有 feature/develop/release/main 多層合併），比較接近 GitHub Flow 的輕量做法。
- 更符合「持續整合到 `main`」的概念，而非「積累到 `develop` 待 release」的釋出導向流程。

若要套用 Git Flow 的話，預期會看到 `feature/*` 合併到 `develop`、`release/*` 合併到 `develop` 和 `main`、以及 tag 等步驟；本案例並未顯示這些跡象，因此判定為 GitHub Flow。
