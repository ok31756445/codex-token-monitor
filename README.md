# Codex Token Monitor

以唯讀方式解析 Codex CLI 本機 session JSONL，顯示輸入、輸出、快取與總 Token，並計算同一 session 自上次檢查後的增量。

> 這是非官方工具。本機 session log 並不是穩定的公開介面，不同 Codex CLI 版本可能使用不同欄位。解析器目前支援實測到的新版 `token_usage_record`、`event_msg/token_count`，以及可安全加總的 API-style `usage`；遇到未知或只有單次、沒有 session 累計語意的格式時會明確報錯，不會把缺失值當成零使用量。

## 功能

- 自動尋找 `~/.codex/sessions` 中最後更新的 session。
- 顯示輸入 Token、輸出 Token、快取輸入 Token 與總 Token。
- 將快取 Token 標示為輸入 Token 的子集，避免重複相加。
- 保存最小本機狀態，計算跨次執行或持續監控時的 session 增量。
- 略過個別損壞的 JSONL 行；整份檔案沒有可辨識 usage 時回傳錯誤。
- 僅使用 Python 標準函式庫，讀取 session log 時不會修改原檔。

## 安裝

需要 Python 3.10 以上版本。

```powershell
python -m pip install -e .
```

## 使用方式

掃描最後更新的 Codex session：

```powershell
codex-token-monitor
```

持續監控（每 2 秒更新）：

```powershell
codex-token-monitor --watch
```

指定 session 或自訂 Codex sessions 目錄：

```powershell
codex-token-monitor --session C:\path\to\rollout.jsonl
codex-token-monitor --sessions-dir C:\path\to\.codex\sessions
```

其他選項：

```text
--interval 1       監控更新間隔（秒）
--json             輸出單行 JSON
--no-cache         不讀寫跨次執行的增量狀態
```

預設狀態檔位於：

- Windows：`%LOCALAPPDATA%\codex-token-monitor\state.json`
- Linux/macOS：`$XDG_CACHE_HOME/codex-token-monitor/state.json`，未設定時使用 `~/.cache`

第一次看到某個 session 時，「自上次檢查增量」等於當下 session 累計值。後續執行只顯示增加量；如果 log 被截斷或計數重設，畫面會標示重設並以目前值重新建立基準。

## Token 語意

- 輸入 Token 包含快取輸入 Token。
- 快取 Token 是輸入 Token 的子集，不應再加到總 Token。
- 總 Token 通常為輸入加輸出；若 log 提供 `total_tokens`，工具保留該值。
- Usage 可能尚未寫入或延後出現；缺少 usage 不代表實際使用量為零。

## 測試

不需讀取真實 Codex log：

```powershell
python -m unittest discover -s tests -v
```

測試涵蓋新版與舊版格式、API-style 欄位、損壞 JSON、未知格式、session 選擇、增量與計數重設。

## 已知限制

- 本工具依賴 Codex CLI 的本機 JSONL 實作細節；未來版本新增格式時，需要加入對應解析規則與 fixture。
- 統計資料是 session log 中已記錄的值，不是最終帳單，也不估算 ChatGPT 訂閱或 API 費用。
- 自動模式以檔案最後修改時間選擇 session；同時執行多個 Codex session 時，建議使用 `--session` 明確指定。
