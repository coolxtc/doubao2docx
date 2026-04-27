"""
pytest 配置文件

配置 pytest 的行为：
- asyncio 模式
- 测试数据目录
"""
import sys
from pathlib import Path

# 将 src 目录加入 Python 路径，以便导入项目模块
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))