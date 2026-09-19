# 薄膜分析專題：完成任務後發布流程

本專題來源為 https://github.com/toby20040915-sketch/thinfilm-lab.git 。
正式網站 https://toby-thinfilm-lab.streamlit.app/ 由 Streamlit Community Cloud 追蹤 `main`，主程式為 `app.py`。

## 固定規則

1. 使用者要求修改專題功能，已包含完成後 Commit／Push 的授權，不需要每次再詢問。若當次明確要求唯讀、只改本機或不要發布，優先遵守當次限制。
2. 先檢查 Git 狀態並 fetch `origin/main`；保留使用者其他修改。完成一項任務、執行必要測試且確認正常後，僅提交該任務的檔案，正常 push 到 `origin/main`。
3. 程式未完成、測試失敗或含未釐清的非本次變更時，不得 Push。不得 force-push，不得覆蓋他人更新。
4. Push 後確認遠端 commit ID，等待 Streamlit 自動取得更新。由伺服器日誌 `THINFILM_DEPLOYMENT commit=<完整 SHA>` 核對執行版本，不可只憑網站能開啟便宣稱更新成功。
5. 實際開啟正式網站，檢查本次修改是否出現及功能是否正常。若只修改文件或部署資訊，核對版本並測試既有流程；不要改變分析內容來製造測試差異。
6. 部署失敗時停止可能影響網站的後續操作，回報錯誤原因及已確認的狀態。可唯讀查錯；不得盲目重新部署、重啟、刪除或回滾。
7. 每次交付明確回報：Git commit ID、Push 是否成功、Streamlit 是否取得最新版、線上驗證是否通過。無法驗證的階段必須標明。

## 測試與版本保護

- 目前工作區 Python 環境：專題目錄相對路徑 `../../work/venv/Scripts/python.exe`。其他環境可使用已安裝 requirements-dev.txt 的 Python。
- 分析介面變更執行 `python -m pytest tests/test_app.py -q`；數學模型變更執行相關 physics、fit、analysis 測試。必要時執行完整測試。
- 不上傳密碼、secrets、私人 PDF、未獲准的實驗資料、虛擬環境、快取或分析輸出。
- 若 shell Push 認證不可用，可以現有 GitHub connector 發布經檢查的相同變更，但需以最新遠端為父提交、保留無關檔案、不強制更新，並如實回報使用 connector 而非 shell Push；之後安全同步本機。
- 這是助理完成任務時執行的流程，不是每次存檔便發布的背景監聽器。任務中斷、測試失敗或其他工具修改不會自動發布。
