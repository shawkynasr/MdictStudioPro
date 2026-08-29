# Mdict Studio Pro

[English](README.md) | **简体中文** | [繁體中文](README.zh-TW.md) | [العربية](README.ar.md)

**一款现代化、跨平台的桌面工具，用于制作、转换和检查 MDict 词典文件。**

Mdict Studio Pro 将完整的 MDict 工作流程整合在一个独立的图形界面中——打包与解包 `.mdx`/`.mdd` 文件、将原始词典数据转换为 MDict 源文本、管理基于 SQLite 的查询，以及检查已编译的词典。它专为语言学工作者、词典爱好者以及处理结构化词汇数据的开发者而设计。

![转换器标签页](docs/screenshots/converters-tab.png)

---

## 目录

- [V2.0 版本新特性](#v20-版本新特性)
- [功能特性](#功能特性)
- [界面截图](#界面截图)
- [安装方法](#安装方法)
- [使用说明](#使用说明)
- [编写自定义插件](#编写自定义插件)
- [效果示例](#效果示例)
- [贡献指南](#贡献指南)
- [许可证与作者](#许可证与作者)

---

## V2.0 版本新特性

V2.0 的核心亮点是全新的**转换器插件系统**——一套模块化的执行引擎，取代了以往硬编码、单一格式的解析方式。

只需将插件文件放入应用的插件文件夹，Mdict Studio Pro 便会自动发现并加载它，根据插件声明的元数据生成对应的输入表单，并在后台线程中运行——无需修改核心程序的任何代码。这意味着任何人都可以为应用原生不支持的词典格式编写转换器，而无需 fork 整个代码库。

## 功能特性

- **模块化转换器插件**——只需编写一个继承自 `BaseConverterPlugin` 的 Python 类，即可解析任意来源格式（Excel、CSV、XML 或自定义文本排版）并生成 MDict 源文件。图形界面会根据插件自动生成对应的输入表单。
- **打包／解包 `.mdx` 与 `.mdd`**——从源文本编译生成词典（可选配套资源文件夹用于 `.mdd`），或将现有词典还原为源文件。
- **高级排版控制**——插件可生成语义化的 HTML，包括用于注音符号／拼音标注的 `<ruby>` 标签、结构化的 `<ol>` 释义列表，以及基于 CSS 的排版布局。
- **稳健的 CJK 编码支持**——可靠处理 UTF-8、UTF-16LE、Big5、GBK 及 GB18030 编码的源文件。
- **SQLite 数据库集成**——在原始文本／MDX 源文件与 SQLite 数据库之间相互转换，实现快速的程序化查询。
- **MDX 检查工具**——从已编译的 `.mdx` 文件中提取内嵌元数据与 `.style`（CSS）样式表，或直接在界面中对词典执行测试查询。
- **词形变化支持**——集成外部词形变化数据（`addflex.py`、`wordforms.txt`），用于制作支持词形还原的词典。
- **跨平台**——可在 macOS、Windows 与 Linux 上运行。

## 界面截图

| 打包（Pack） | 转换器（插件） | 工具 |
|---|---|---|
| ![打包标签页](docs/screenshots/pack-tab.png) | ![转换器标签页，已选中 CC-CEDICT 插件](docs/screenshots/converters-tab-cedict.png) | ![工具标签页](docs/screenshots/tools-tab.png) |

## 安装方法

**环境要求：**
- Python 3.8 及以上版本
- [mdict-utils](https://github.com/liuyug/mdict-utils)（提供 `mdict` 命令行工具，打包／解包／数据库相关操作均依赖它）

**1. 克隆仓库**
```bash
git clone https://github.com/shawkynasr/MdictStudioPro.git
cd MdictStudioPro
```

**2. 安装依赖**
```bash
pip install -r requirements.txt
```

**3. 运行程序**
```bash
python MdictStudio.py
```

> **macOS 打包说明：** 可使用 PyInstaller 将本应用打包为原生 `.app`／`.dmg`。具体步骤请参见 [`docs/BUILD.md`](docs/BUILD.md)，或直接从 [Releases 页面](https://github.com/shawkynasr/MdictStudioPro/releases) 下载预编译版本。

## 使用说明

应用界面共分为六个标签页，分别对应 MDict 工作流程的各个环节：

| 标签页 | 功能说明 |
|---|---|
| **打包（Pack）** | 将源文本（及可选资源文件）编译为 `.mdx`／`.mdd`。 |
| **解包（Unpack）** | 将现有 `.mdx`／`.mdd` 反编译还原为源文件。 |
| **转换器（插件）** | 运行转换器插件，将原始数据转换为 MDict 源文件。 |
| **数据库（SQLite）** | 在文本／MDX 源文件与 SQLite 数据库之间转换。 |
| **词形变化** | 构建词形变化数据，支持词形还原查询。 |
| **工具** | 检查 MDX 元数据／样式表，或执行测试查询。 |

## 编写自定义插件

制作一个新的词典转换器只需要一个文件。在插件文件夹中新建一个 `.py` 文件，并继承 `BaseConverterPlugin`：

```python
from base_plugin import BaseConverterPlugin

class MyCustomDictPlugin(BaseConverterPlugin):
    id = "my_custom_dict_v1"                 # 内部唯一标识符
    name = "My Custom Dictionary"             # 显示在转换器下拉菜单中的名称
    description = "解析特定格式的词典数据并生成 MDict HTML。"
    file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
    default_encodings = ["utf-8"]

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        # 1. 在此编写解析逻辑
        # 2. 汇报进度：progress_callback(50)
        # 3. 输出日志：log_callback("正在处理词条...")

        return "MDict 源文件生成成功！"
```

Mdict Studio Pro 会在下次启动时（或点击转换器标签页中的**刷新插件**按钮）自动检测该插件，并完全根据类中声明的内容自动生成输入表单——包括文件选择器、编码选择器以及任何自定义选项。

**插件存放位置：**
- 从源码运行时：放入 `MdictStudio.py` 同级目录下的 `plugins/` 文件夹。
- 运行打包后的应用时：使用 `~/Documents/Mdict Studio Pro/plugins`（首次启动时会自动创建——点击转换器标签页中的**打开插件文件夹**按钮即可快速跳转）。

`id` 在所有已安装插件中必须唯一；`name` 仅作为显示标签，可以自由描述（也支持非拉丁文字，参见下方示例插件）。

> **插件作者注意事项：** 由于 Mdict Studio Pro 采用 AGPL-3.0 许可证发布（详见下文），随应用一同加载与分发的插件应与该许可证兼容。若你仅制作私人／内部使用的插件，则不受此影响。

## 效果示例

以下是使用社区／示例转换器插件制作的部分词典，展示了 HTML 排版管线所支持的细节效果——带声调标记的拼音、彩色词性标签，以及结构化的相互参见链接：

<table>
<tr>
<td><img src="docs/screenshots/sample-cc-cedict.png" alt="CC-CEDICT 转换器生成的“和”字条目"></td>
<td><img src="docs/screenshots/sample-idiom.png" alt="成语词典生成的“入木三分”条目"></td>
</tr>
</table>

## 致谢与参考来源 (Credits & References)

Mdict Studio Pro 的诞生离不开开源词典社区诸多优秀项目的支持与启发：

- **核心与底层引擎：**
  - 界面基础设计参考了 **jekovcar** 开发的 *mdictGui* 原版项目。
  - 底层词典处理引擎基于 libukai 开发的 **[mdtt](https://github.com/libukai/mdtt)** 与 **[mdict-utils](https://github.com/liuyug/mdict-utils)**[cite: 10]。

- **样式表与排版设计：**
  - `cbgycd.css` (WFG 风格) 基于 **DFL** 的原始样式设计。
  - `jybcb.css` 词典排版布局基于 **bmcc718** 的样式表方案。

- **插件与数据解析：**
  - `edudict_plugin.py` 解析逻辑基于 **kking** 的原始脚本方案。
  - CC-CEDICT 数据转换处理基于 **shbf@PDAWIKI** 的制作方案。

## 贡献指南

欢迎提交贡献、反馈问题与功能建议——请前往 [issues 页面](https://github.com/shawkynasr/MdictStudioPro/issues) 开始参与。

如果你为某个知名词典格式编写了转换器插件，欢迎发起 Pull Request，将其收录为默认／示例插件。

## 许可证与作者

- **作者：** Shawky Nasr
- **联系方式：** shawkynasr@126.com
- **许可证：** [GNU Affero 通用公共许可证 v3.0（AGPL-3.0）](LICENSE)

本项目使用 [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)，该库采用 GPL v3 与商业许可证双重授权模式。因此 Mdict Studio Pro 相应地采用 AGPL-3.0 许可证发布。
