# Mdict Studio Pro

[English](README.md) | [简体中文](README.zh-CN.md) | **繁體中文** | [العربية](README.ar.md)

**一款現代化、跨平台的桌面工具，用於製作、轉換與檢視 MDict 詞典檔案。**

Mdict Studio Pro 將完整的 MDict 工作流程整合在單一獨立的圖形介面中——打包與解包 `.mdx`／`.mdd` 檔案、將原始詞典資料轉換為 MDict 原始文字、管理以 SQLite 為基礎的查詢，以及檢視已編譯的詞典。它專為語言學工作者、詞典愛好者，以及處理結構化詞彙資料的開發者而設計。

![轉換器分頁](docs/screenshots/converters-tab.png)

---

## 目錄

- [V2.0 版本新功能](#v20-版本新功能)
- [功能特色](#功能特色)
- [介面截圖](#介面截圖)
- [安裝方式](#安裝方式)
- [使用說明](#使用說明)
- [撰寫自訂外掛](#撰寫自訂外掛)
- [範例輸出](#範例輸出)
- [貢獻方式](#貢獻方式)
- [授權條款與作者](#授權條款與作者)

---

## V2.0 版本新功能

V2.0 的核心亮點是全新的**轉換器外掛系統**——一套模組化的執行引擎，取代了以往寫死在程式中、只支援單一格式的解析方式。

只要將外掛檔案放入應用程式的外掛資料夾，Mdict Studio Pro 便會自動偵測並載入，依據外掛宣告的中繼資料自動產生對應的輸入表單，並在背景執行緒中執行——完全不需修改核心程式的任何程式碼。這代表任何人都能為應用程式原生不支援的詞典格式撰寫轉換器，而不必 fork 整個程式碼庫。

## 功能特色

- **模組化轉換器外掛**——只需撰寫一個繼承自 `BaseConverterPlugin` 的 Python 類別，即可解析任意來源格式（Excel、CSV、XML 或自訂文字排版）並產生 MDict 原始檔。圖形介面會依據外掛自動產生對應的輸入表單。
- **打包／解包 `.mdx` 與 `.mdd`**——從原始文字編譯產生詞典（可搭配選用的資源資料夾以支援 `.mdd`），或將現有詞典還原為原始檔。
- **進階排版控制**——外掛可產生語意化的 HTML，包括用於注音／拼音標註的 `<ruby>` 標籤、結構化的 `<ol>` 釋義清單，以及以 CSS 驅動的排版樣式。
- **穩健的 CJK 編碼支援**——可靠處理 UTF-8、UTF-16LE、Big5、GBK 及 GB18030 編碼的原始檔。
- **SQLite 資料庫整合**——在原始文字／MDX 來源與 SQLite 資料庫之間互相轉換，實現快速的程式化查詢。
- **MDX 檢視工具**——從已編譯的 `.mdx` 檔案中擷取內嵌中繼資料與 `.style`（CSS）樣式表，或直接在介面中對詞典執行測試查詢。
- **詞形變化支援**——整合外部詞形變化資料（`addflex.py`、`wordforms.txt`），用於製作支援詞形還原的詞典。
- **跨平台**——可於 macOS、Windows 與 Linux 上執行。

## 介面截圖

| 打包（Pack） | 轉換器（外掛） | 工具 |
|---|---|---|
| ![打包分頁](docs/screenshots/pack-tab.png) | ![轉換器分頁，已選取 CC-CEDICT 外掛](docs/screenshots/converters-tab-cedict.png) | ![工具分頁](docs/screenshots/tools-tab.png) |

## 安裝方式

**環境需求：**
- Python 3.8 以上版本
- [mdict-utils](https://github.com/liuyug/mdict-utils)（提供 `mdict` 命令列工具，打包／解包／資料庫相關操作皆依賴於此）

**1. 複製儲存庫**
```bash
git clone https://github.com/shawkynasr/MdictStudioPro.git
cd MdictStudioPro
```

**2. 安裝相依套件**
```bash
pip install -r requirements.txt
```

**3. 執行應用程式**
```bash
python MdictStudio.py
```

> **macOS 打包說明：** 可使用 PyInstaller 將本應用程式打包為原生 `.app`／`.dmg`。詳細步驟請參見 [`docs/BUILD.md`](docs/BUILD.md)，或直接從 [Releases 頁面](https://github.com/shawkynasr/MdictStudioPro/releases) 下載預先編譯好的版本。

## 使用說明

應用程式介面共分為六個分頁，分別對應 MDict 工作流程的各個階段：

| 分頁 | 功能說明 |
|---|---|
| **打包（Pack）** | 將原始文字（及選用的資源檔案）編譯為 `.mdx`／`.mdd`。 |
| **解包（Unpack）** | 將現有的 `.mdx`／`.mdd` 反編譯還原為原始檔。 |
| **轉換器（外掛）** | 執行轉換器外掛，將原始資料轉換為 MDict 原始檔。 |
| **資料庫（SQLite）** | 在文字／MDX 來源與 SQLite 資料庫之間互相轉換。 |
| **詞形變化** | 建立詞形變化資料，支援詞形還原查詢。 |
| **工具** | 檢視 MDX 中繼資料／樣式表，或執行測試查詢。 |

## 撰寫自訂外掛

製作一個新的詞典轉換器只需要一個檔案。在外掛資料夾中新增一個 `.py` 檔案，並繼承 `BaseConverterPlugin`：

```python
from base_plugin import BaseConverterPlugin

class MyCustomDictPlugin(BaseConverterPlugin):
    id = "my_custom_dict_v1"                 # 內部唯一識別碼
    name = "My Custom Dictionary"             # 顯示於轉換器下拉選單中的名稱
    description = "解析特定格式的詞典資料並產生 MDict HTML。"
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        # 1. 在此撰寫解析邏輯
        # 2. 回報進度：progress_callback(50)
        # 3. 輸出記錄：log_callback("正在處理詞條...")

        return "MDict 原始檔產生成功！"
```

Mdict Studio Pro 會在下次啟動時（或點選轉換器分頁中的**重新整理外掛**按鈕）自動偵測該外掛，並完全依據類別中宣告的內容自動產生輸入表單——包括檔案選擇器、編碼選擇器，以及任何自訂選項。

**外掛存放位置：**
- 從原始碼執行時：放入 `MdictStudio.py` 同層目錄下的 `plugins/` 資料夾。
- 執行打包後的應用程式時：使用 `~/Documents/Mdict Studio Pro/plugins`（首次啟動時會自動建立——點選轉換器分頁中的**開啟外掛資料夾**按鈕即可快速跳轉）。

`id` 在所有已安裝的外掛中必須是唯一的；`name` 僅作為顯示標籤，可自由描述（也支援非拉丁文字，請參見下方範例外掛）。

> **外掛作者須知：** 由於 Mdict Studio Pro 採用 AGPL-3.0 授權條款發布（詳見下文），隨應用程式一併載入與散布的外掛應與該授權條款相容。若您僅製作私人／內部使用的外掛，則不受此限制影響。

## 範例輸出

以下是使用社群／範例轉換器外掛製作的部分詞典，展示了 HTML 排版流程所支援的細節效果——帶聲調標記的拼音、彩色詞性標籤，以及結構化的參見連結：

<table>
<tr>
<td><img src="docs/screenshots/sample-cc-cedict.png" alt="CC-CEDICT 轉換器產生的「和」字條目"></td>
<td><img src="docs/screenshots/sample-idiom.png" alt="成語詞典產生的「入木三分」條目"></td>
</tr>
</table>

## 致謝與參考來源 (Credits & References)

Mdict Studio Pro 的誕生離不開開源詞典社群諸多優秀專案的啟發與貢獻：

- **核心與底層引擎：**
  - 使用者介面基礎架構參考自 **jekovcar** 開發的 *mdictGui* 原版專案。
  - 底層引擎技術基於 libukai 的 **[mdtt](https://github.com/libukai/mdtt)** 與 **[mdict-utils](https://github.com/liuyug/mdict-utils)**。

- **樣式表與排版設計：**
  - `cbgycd.css`（WFG 排版風格）基於 **DFL** 的原始樣式設計。
  - `jybcb.css` 詞典排版佈局基於 **bmcc718** 的樣式表方案。

- **外掛與資料解析：**
  - `edudict_plugin.py` 解析邏輯基於 **kking** 的原始處理腳本。
  - CC-CEDICT 資料轉換處理基於 **shbf@PDAWIKI** 的製作方案。

## 貢獻方式

歡迎提出貢獻、回報問題與功能建議——請前往 [issues 頁面](https://github.com/shawkynasr/MdictStudioPro/issues) 開始參與。

若您為某個知名詞典格式撰寫了轉換器外掛，歡迎發起 Pull Request，將其收錄為預設／範例外掛。

## 授權條款與作者

- **作者：** Shawky Nasr
- **聯絡方式：** shawkynasr@126.com
- **授權條款：** [GNU Affero 通用公共授權條款 v3.0（AGPL-3.0）](LICENSE)

本專案使用 [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)，該套件採用 GPL v3 與商業授權雙重授權模式。因此 Mdict Studio Pro 相應地採用 AGPL-3.0 授權條款發布。
