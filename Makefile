.PHONY: help install run clean

help:
	@echo "可用命令:"
	@echo "  make install    - 安装依赖"
	@echo "  make run      - 运行CLI"
	@echo "  make clean   - 清理缓存"

install:
	pip install -r requirements.txt
	playwright install chromium

run:
	python -m src.cli

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true