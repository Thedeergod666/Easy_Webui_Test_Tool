# WEBUI自动化测试框架使用指南
这是一个基于 [Playwright](https://playwright.dev/python/) 和 [Pytest](https://docs.pytest.org/) 构建的 **关键字+数据驱动的 Web UI 自动化测试框架**。
其核心目标是通过简洁的 Excel 表格来管理和执行复杂的 Web UI 测试流程，适用于各类平台的回归和冒烟测试，显著降低自动化测试的门槛和维护成本。
中文wiki：
https://zread.ai/Thedeergod666/Easy_Webui_Test_Tool
English wiki：
https://deepwiki.com/Thedeergod666/Easy_Webui_Test_Tool
## 核心特色
* **极简用例编写**：测试步骤存储在 **Excel** 中，业务人员也能轻松参与。
* **强大的 Playwright 集成**：充分利用 Playwright 的跨浏览器支持、自动等待、强大的 `get_by_role` 语义化定位等特性。
* **灵活的关键字驱动**：封装了丰富的 UI 操作关键字（点击、输入、验证、多 Tab 管理等），支持链式定位和 Playwright Codegen 直接导入。
* **智能执行与配置**：通过 `test_config.json` 灵活配置测试流程、目标浏览器、有头/无头模式等；内置 Function (软断言) 和 Session (硬断言) 两种执行模式。
* **便捷的环境与测试管理**：提供 `install.bat/.sh` 脚本一键配置环境，`main.bat/.sh` 脚本统一管理测试执行入口（支持交互式与命令行调用）。
* **高效的用例生成**：内置工具可将 Playwright Codegen 录制的脚本一键转换为 Excel 测试用例。
## 快速开始
在使用之前，请确保你的电脑上已经安装了 Python 3.11或者更高版本（ 推荐 Python 3.13.1，我开发环境用的就是这个 ）和对应的 pip 版本，并将 Python 路径添加到系统环境变量中。
#### 首次使用
1. 双击运行 `install.bat` 文件，它会自动为你配置好所有环境。
   macOS/Linux 系统用户请先在命令行里执行 `chmod +x *.sh`，然后运行 `install.sh`。
2. 等待所有安装完成，看到成功提示后按任意键关闭窗口。
#### 日常运行测试
1. 修改 `test_data` 目录下的 Excel 文件来编写你的测试用例。
2. 首次接手项目或配置损坏时，可运行 `main.bat init` / `main.sh init` 自动初始化或修复 `test_data/test_config.json`。
3. 修改 `test_data` 目录下的 `test_config.json` 文件来启用或禁用你想测试的流程、切换有头无头模式，以及配置测试浏览器内核。
4. 运行 `main.bat validate` / `main.sh validate`，先检查配置文件、Excel 路径和 Sheet 是否可用。
5. 双击运行 `main.bat` 文件进入交互菜单。
   macOS/Linux 系统下运行 `main.sh`。
6. 测试结束后，报告会生成在 `reports/reports_YYYY-MM-DD/` 目录下，文件名格式类似 `report_2026-03-16_18-30-00_chromium_Passed.html`。
#### 进阶参考
* [🔧 关键字参考 (Keyword Reference)](./docs/自动化框架关键字使用指南.md)：所有可用关键字的详细说明、参数和使用示例。
* [📍 定位器参考 (Locator Reference)](./docs/自动化框架定位器使用指南.md)：详解框架支持的各种元素定位策略及最佳实践。
#### 更新框架
- 如果框架有更新，你需要联系开发人员获取最新的代码包，一般来说解压后覆盖就行。

## 框架介绍
#### 框架主要特点
1. **配置管理**：使用JSON文件（test_config.json）管理测试流程、浏览器设置等。
2. **环境安装**：提供了install.bat（Windows）和install.sh（macOS/Linux）脚本，用于一键安装依赖和浏览器驱动。
3. **测试执行**：提供了main.bat和main.sh脚本，支持交互式和非交互式（CI/CD）两种模式，可以选择Function模式（软断言）或Session模式（硬断言）。
4. **关键字驱动**：Keywords.py定义了丰富的关键字，如点击、输入、验证等，并支持多页面操作和多种定位方式（包括Playwright的get_by_role等高级定位）。
5. **测试用例管理**：测试用例存储在Excel文件中，通过pytest读取并执行。
6. **报告生成**：测试结束后生成HTML报告，报告文件名包含时间戳和测试结果状态（Passed/Failed）。
7. **多浏览器支持**：支持Chromium, Firefox, WebKit。
8. **软断言和硬断言**：Function模式（软断言）会收集所有错误并在最后统一报告；Session模式（硬断言）则在每一步失败时立即停止。
此外，框架还包含了一些**高级功能**：
- **多页面切换**（switch_to_page）
- 关闭页面（close_page）
- 在新标签页打开（open_in_new_page）
- **执行Playwright Codegen生成的代码**（expect_codegen）
- 强制等待（sleep）在无头模式下自动跳过，并记录总等待时间

#### 目录文件介绍
*   `.` (项目根目录)
    *   `.venv/` - 虚拟环境，由 `install.bat` / `install.sh` 自动生成。
    *   `docs/` - 使用文档。
    *   `framework/` - 架构。
        *   `utils/` - 其他工具。
        *   `Keywords.py` - 关键字。
    *   `page_objects/` - 后续升级 POM 用。
    *   `reports/` - 报告，脚本生成的报告存放的地方，记得用浏览器打开。
        *   `report_README.md` - 报告使用说明。
    *   `test_data/` - 存放测试文件、配置浏览器打开方式。
        *   `test_config.json` - 配置浏览器打开方式，测试数据文件路径。
    *   `tests/` - 具体实现脚本。
        *   `test_flows/` - 测试/调试代码。
            *   `test_flow_by_function.py` - 整体测试快速调试用，已弃用。
            *   `test_flow_by_function_json.py` - JSON 解析、`bat` 脚本直接调用。
            *   `test_steps_by_session.py` - 单步测试快速调试用，已弃用。
            *   `test_steps_by_session_json.py` - JSON 解析、`bat` 脚本直接调用。
        *   `conftest.py` - 脚本测试配置。
    ---
	*   `.gitignore` - 忽略文件。
	*   `requirements.txt` - 待安装库。
	*   `install.bat` - #Windows 环境安装/更新 第一步，双击这个文件。
	*   `main.bat` - #Windows 启动测试脚本 后续只需双击这里即可开始测试。
	*   `install.sh` - #macOS #Linux 环境安装/更新 第一步，双击这个文件。
	*   `main.sh` - #macOS #Linux 启动测试脚本 后续只需双击这里即可开始测试。
	*   `README.md` - 读我。
#### 脚本介绍
- install.bat / install.sh
	- 自动根据requirements.txt使用清华源镜像安装脚本所需虚拟环境
	- 使用清华源镜像自动升级pip
- main.bat / main.sh
	- **交互式:** 直接双击 `main.bat` / `main.sh`，会出现菜单
	- **非交互式 (给CI/CD或自动化脚本用):**
	    - `main.bat 1` / `main.sh 1` (执行 Function 模式)
	    - `main.bat 2 1` / `main.sh 2 1` (执行指定流程的 Session 模式)
	    - `main.bat init` / `main.sh init` (初始化或修复 `test_config.json`)
	    - `main.bat validate` / `main.sh validate` (校验配置和测试数据)
	    - 非交互式报告后缀会带 `_CI` 字样
	- 目前**支持的操作**：
    1. Function模式 (软断言，执行所有启用的流程)
    2. Session模式  (硬断言，执行指定启用的流程)
       示例: 2 1 (执行第一个流程), 2 -1 (执行最后一个流程)
    3. Session模式-Browsers (硬断言，指定流程在所有浏览器上执行)
       示例: 3 1 (第一个流程在所有浏览器上执行), 3 -1 (最后一个流程在所有浏览器上执行)
    4. Session模式-All (硬断言，执行所有启用的流程)
    5. 从现有Python文件转换成excel
    6. 启动Playwright录制并转换excel
    7. test_config.json用例快速查看
    8. 清理残留临时文件
#### 目前playwright-codegen内录**不支持**或录制的功能
	视频播放：不支持html5，无法支持bilibili、抖音这类的视频网站播放
	bar类控件精准点击：
	    `page6.locator(".progress-bar.volumn-bar > .progress-track").click()`
	    `page6.locator(".progress-bar.volumn-bar > .progress-pass").click()`
	    - [ ] 音频bar点击
	元素拖拽
	关闭网页页面
