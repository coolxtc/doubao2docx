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
| `steps.py` | `FetchStep` 枚举 | 进度步骤 |
| `page_actions.py` | `PageActions` | `scroll_all()` 组合多个 JS 操作 |
| `extractor.py` | `DataExtractor` | `extract_all()` → `ChatData` |
| `anti_detect.py` | `AntiDetectMiddleware` | 隐藏 webdriver 标识 |
| `pool.py` | `BrowserPool` | 单浏览器多标签页池 |

## 设计模式

### 异步上下文管理器
```python
class DoubaoSpider:
    async def __aenter__(self): await self.start(); return self
    async def __aexit__(self, ...): await self.close()
```

### 浏览器层级
```
Playwright → Browser → BrowserContext → Page
```

### JavaScript 封装（page_actions.py）
JS 代码作为模块级字符串常量，格式 `() => {...}`：
```python
SCROLL_IMAGES_JS = """
() => {
    const imgs = document.querySelectorAll('picture img');
    imgs.forEach(img => img.scrollIntoView({ block: 'center' }));
}
"""
```

### 反爬工厂模式
```python
create_anti_detect_middleware(level="medium")  # low/medium/high
```

### 资源池（pool.py）
```python
pool = BrowserPool()
page = await pool.acquire(5)  # Semaphore 控制并发
# ... 执行任务 ...
await pool.release(page)
```

## FetchStep 枚举

```
STARTING → LOADING_PAGE → LOADING_IMAGES → EXPANDING_CODE
```

映射：`FETCH_STEP_NAMES = {"任务开始": 0, "加载网页": 1, ...}`

## 反爬级别（anti_detect.py）

- `low`：随机 User-Agent
- `medium`：随机 UA + 隐藏 `navigator.webdriver`（默认）
- `high`：可扩展更多措施

## 外部页面注入

BrowserPool 复用浏览器时，通过 `external_page` 参数注入页面：
```python
spider = DoubaoSpider(external_page=page)  # 跳过浏览器启动
```

## 导出

```python
from src.scraper import DoubaoSpider, FetchStep, ChatData, ChatMessage, BrowserPool
```
