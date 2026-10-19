# tests/

## 模块职责

自动化测试，覆盖核心逻辑的各个模块。19 个测试文件，使用 pytest + pytest-asyncio + pytest-cov。

## 测试结构

```
tests/
├── conftest.py                      # 共享 fixture
├── test_crawler.py                  # 爬虫集成测试
├── test_browser.py                  # 浏览器管理测试
├── test_extractor.py                # 数据提取器测试
├── test_page_actions.py             # 页面操作测试（100% 覆盖率）
├── test_pool.py                     # 浏览器池测试
├── test_anti_detect.py              # 反爬中间件测试
├── test_steps.py                    # 进度步骤枚举测试
├── test_models.py                   # 数据模型测试
├── test_preprocessor.py             # 预处理集成测试
├── test_base_extended.py            # BaseParser 扩展测试（MockParser，90% 覆盖率）
├── test_doubao_parser.py            # 豆包解析器测试
├── test_docx_builder.py             # Word 文档构建测试
├── test_doc_namer.py                # 文件命名 + 序号管理测试
├── test_latex_converter.py          # LaTeX 转换测试
├── test_batch_report.py             # 批量报告测试（92% 覆盖率）
├── test_config.py                   # 配置加载测试（94% 覆盖率）
├── test_exceptions.py               # 自定义异常测试
├── test_playwright_api.py           # Playwright API 测试
└── test_utils.py                    # 工具函数测试
```

## 运行方式

```bash
# 运行所有测试
python3 -m pytest tests/

# 运行单个测试文件
python3 -m pytest tests/test_base_extended.py -v

# 查看覆盖率
python3 -m pytest tests/ --cov=src --cov-report=term

# 带 HTML 报告
python3 -m pytest tests/ --cov=src --cov-report=html
```

## 测试配置（pyproject.toml）

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
]
```

## 覆盖率目标

| 模块 | 目标 | 测试文件 |
|------|------|---------|
| preprocessor/base.py | ≥90% | test_base_extended.py |
| scraper/crawler.py | ≥87% | test_crawler.py |
| scraper/page_actions.py | 100% | test_page_actions.py |
| scraper/extractor.py | 100% | test_extractor.py |
| generator/batch_report.py | ≥92% | test_batch_report.py |
| config.py | ≥94% | test_config.py |
| scraper/* 其余 | ≥50% | - |
| generator/* 其余 | ≥50% | - |

## 测试模式

### MockParser 模式

用于扩展 `BaseParser` 的测试，定义在 `conftest.py` 或 `test_base_extended.py` 中：

```python
class MockParser(BaseParser):
    def __init__(self):
        self.config = PlatformConfig()
    def _get_title_selectors(self): return ["h1"]
    def _is_math_element(self, el): return el.has_attr("copy-text")
    def _is_display_math(self, el): return "display" in (el.get("class") or [])
    def _is_code_container(self, el): return "code-container" in (el.get("class") or [])
    def _is_paragraph_container(self, el): return "paragraph" in (el.get("class") or [])
    def _is_code_button(self, el): return "button-" in (el.get("class") or [])
    def _extract_latex_content(self, el): return el.get("copy-text", "")
    def _is_image_element(self, el): return el.name == "picture"
    def _extract_image_url(self, el): return el.get("src", "")
```

### conftest.py

共享 fixture 文件，包含测试用的 HTML 样本路径和临时目录等。

## 测试数据

- `tests/test2.html`：真实豆包 HTML 结构样本，包含嵌套 ul、line-break div、header 等
- 测试用的 HTML 文件存放在 `tests/` 目录下

## 注意

- **禁止删除测试使测试通过**
- 新增功能需同步添加对应测试文件
- 覆盖率下降需补充测试