# 第 8 章 · Agent 的自我進化

> 不改權重也能成長：經驗學習、從工具使用者到創造者

← [返回主目錄](../README.md) · 📖 [讀本章正文](../book/chapter8.md)

## 配套專案

| 專案 | 型別 | 一句話說明 |
| --- | :--: | --- |
| [gaia-experience](gaia-experience/) | ✅ | 基於 AWorld + GAIA 的「學習-應用」閉環：自動總結成功軌跡為結構化經驗，在新任務中檢索應用 |
| [browser-use-rpa](browser-use-rpa/) | ✅ | 瀏覽器工作流錄製系統，把重複操作封裝為引數化工具，從 LLM 推理切換到自動化執行可加速 3–5 倍 |
| [prompt-distillation](prompt-distillation/) | ✅ | 將複雜提示的效果蒸餾進模型引數，減少推理提示長度，把上下文經驗固化為引數化知識 |
| [prompt-auto-optimization](prompt-auto-optimization/) | ✅ | 以 tau-bench 航空客服「過度轉接」為例，Coding Agent 讀/改 prompt 檔案 → 重新評測 → 驗證閉環 |
| [self-evolving-tools](self-evolving-tools/) | ✅ | Alita 式「最小預定義，最大自我進化」：五個通用元工具，自己上網找庫/讀文件/沙箱測試並封裝複用 |
| [self-evolution-eval](self-evolution-eval/) | ✅ | 20 個跨領域任務 + 四層分層驗證 harness + 可控參考 Agent，考察發現/創造/複用品質 |

## 專案型別說明

| 圖示 | 型別 | 含義 |
| :--: | --- | --- |
| ✅ | **可獨立執行** | 本倉庫自帶完整程式碼，配置好 API Key 即可執行 |
| 📖 | **復現指南** | 依賴需自行 `git clone` 的**外部倉庫**（訓練框架、評測基準等） |
| 🚧 | **設計文件** | 僅包含架構與實現方案，可執行程式碼仍在完善中 |
