# 豆包导出 Web 服务镜像（linux/amd64，适配绿联 DXP4800 / Intel N100）
#
# 采用两阶段：先在 playwright 官方镜像内完成安装并删除未用浏览器，
# 再把整个文件系统压平为单层。分层镜像里后续层的 rm 不会回收下层空间，
# 只有压平才能真正把 firefox/webkit 的体积省掉。
# 基础镜像选 mcr 而非 docker.io：mcr 国内可直连，docker.io 在本机网络下被 DNS 污染。

FROM mcr.microsoft.com/playwright/python:v1.60.0-noble AS build

# Ubuntu apt 镜像站：直连 archive.ubuntu.com 拉 universe 大索引会中断，
# 其它网络环境可用 --build-arg APT_MIRROR=... 覆盖
ARG APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu

# pandoc 负责 LaTeX → OMML 公式转换，缺失时公式会静默退化为 Unicode 而不报错
# fonts-noto-cjk 为中文提供字体度量，避免页面布局高度异常影响懒加载
RUN sed -i "s|^URIs: http://archive.ubuntu.com/ubuntu/|URIs: ${APT_MIRROR}/|; \
            s|^URIs: http://security.ubuntu.com/ubuntu/|URIs: ${APT_MIRROR}/|" \
        /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        pandoc \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 运行依赖与 pyproject.toml 保持一致。源码不走 pip install：
# pyproject 未声明 setuptools 包布局，且项目入口本就是直接执行模块
RUN pip install --no-cache-dir \
    "playwright==1.60.0" \
    "python-docx>=1.1.0" \
    "beautifulsoup4>=4.12.0" \
    "lxml>=5.0.0" \
    "pyyaml>=6.0" \
    "rich>=13.0" \
    "requests>=2.31.0" \
    "fastapi>=0.136.0" \
    "uvicorn>=0.49.0" \
    "sse-starlette>=3.4.0" \
    "jinja2>=3.1.0"

WORKDIR /app

# config.yaml 六个 section 全必填、无默认值，内置一份兜底，运行时可由 compose 挂载覆盖
COPY config.yaml ./
COPY src ./src
COPY web ./web

# 只保留 chromium headless shell：已实测 launch(headless=True) 仅需该二进制，
# firefox/webkit/ffmpeg 与完整 chromium 合计约 940MB 全部用不到。
# 模式 chromium-* 不会误伤 chromium_headless_shell-*（下划线不匹配连字符）
RUN rm -rf /ms-playwright/firefox-* /ms-playwright/webkit-* \
           /ms-playwright/ffmpeg-* /ms-playwright/chromium-* /ms-playwright/.links \
    && rm -rf /tmp/* /var/tmp/* /var/cache/apt \
    && du -sh /ms-playwright

# ---- 压平阶段 ----
FROM scratch

# 特殊目录不复制：设备节点与伪文件系统由容器运行时提供
COPY --from=build --exclude=/proc --exclude=/sys --exclude=/dev \
     --exclude=/tmp --exclude=/run --exclude=/mnt --exclude=/media / /

# 恢复 build 阶段镜像的运行时元数据（COPY 不带 Config）
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    DOUBAO_OUTPUT_DIR=/app/data

WORKDIR /app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "web.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
