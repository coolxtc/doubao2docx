# src/scraper/

## 模块职责

Playwright 浏览器自动化层：启动浏览器 → 访问页面 → 滚动加载 → 展开代码 → 提取 HTML。

## 入口

`DoubaoSpider`（`crawler.py`）—— 异步上下文管理器。

## 关键模块

| 文件 | 类/函数 | 用途 |
|------|---------|------|
| `browser.py` | `BrowserManager` | 浏览器生命周期 |
| `crawler.py` | `DoubaoSpider` | 爬虫核心，`DOUBAN_URL_PATTERN` 定义 URL 验证规则 |
| `steps.py` | `FetchStep` 枚举 | 进度步骤（0-7 + COMPLETED） |
| `page_actions.py` | `PageActions` | `scroll()`, `expand_code_blocks()` |
| `extractor.py` | `DataExtractor` | `extract_chat_data()` → `ChatData` |
| `anti_detect.py` | `AntiDetectMiddleware` | 隐藏 webdriver 标识 |

## FetchStep 枚举

```
0: 任务开始 → 1: 收到任务 → 2: 访问页面 → 3: 加载完成
→ 4: 滚动加载 → 5: 展开代码 → 6: 提取数据 → 7: 爬取完成
```

## 页面交互（page_actions.py）

- **滚动**：`PageActions.scroll()` → 触发懒加载
- **展开代码**：注入 JS 查找含"已生成代码"的按钮并点击
- **超时配置**：`config.yaml` 中 `crawler.*` 系列参数

## 反爬（anti_detect.py）

- `low`：随机 User-Agent
- `medium`：随机 UA + 隐藏 `navigator.webdriver`
- `high`：可扩展更多措施

## 浏览器池（pool.py）

单浏览器多标签页模式，`asyncio.Semaphore` 控制并发数。

## 导出

```python
from src.scraper import DoubaoSpider, FetchStep, ChatData, ChatMessage, BrowserPool
```
