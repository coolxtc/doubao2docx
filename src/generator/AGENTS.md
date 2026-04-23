# src/generator/

## 模块职责

TextBlock[] → Word 文档。LaTeX → OMML（via pandoc）。

## 关键模块

| 文件 | 类 | 用途 |
|------|-----|------|
| `docx_builder.py` | `DocxBuilder`, `DocumentConfig` | 文档构建器 |
| `latex_converter.py` | `LaTeXConverter` | LaTeX → Unicode fallback |
| `doc_namer.py` | `DocNamer` | 文件名 + 序号管理 |
| `batch_report.py` | `BatchReport` | 批量导出报告 |

## python-docx 模式

### 中文字体支持
```python
run.font.name = self.font_name
run._element.rPr.rFonts.set(qn('w:eastAsia'), self.font_name)  # 关键！
```

### 公式插入（pandoc → OMML）
```python
# 1. LaTeX → tex → docx（pandoc）
# 2. 从 docx 提取 oMath 元素
# 3. deepcopy 到目标文档
```

### 手动有序列表
不依赖 Word 样式，手动拼接序号：
```python
para.add_run(f"{self._list_counter}. {content}")
```

## 配置

字体、字号、图片宽度等通过 `config.yaml` → `GlobalConfig.document_style` 传递。

## 导出结构

```
data/export/YYYYMMDD/
├── 260412-1 标题.docx
└── link_index.json
```

## 导出

```python
from src.generator import DocxBuilder, DocumentConfig, DocNamer
```
