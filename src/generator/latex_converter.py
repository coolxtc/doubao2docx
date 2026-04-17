"""
LaTeX公式转换器模块

提供 LaTeX 公式到 Word 格式的转换功能。

主要功能：
1. check_dependencies: 检查 pandoc 是否安装
2. convert_inline: 将 LaTeX 公式转换为 Unicode 字符（fallback 方案）

核心概念：
- pandoc: 文档格式转换工具，支持 LaTeX 到 docx 的转换
- OMML: Office Math Markup Language，Word 的内置公式格式

依赖：
- brew install pandoc（公式转换的关键依赖）
"""

from typing import Optional


class LaTeXConverter:
    """
    LaTeX转Word转换器

    将 LaTeX 数学公式转换为 Word 文档可以显示的格式。

    转换策略：
    1. 优先使用 pandoc 转换为 Word 原生公式（OMML）
    2. 如果失败，使用 Unicode 字符作为 fallback

    注意：OMML 转换在 docx_builder.py 中实现，
    这里只负责 Unicode fallback 和依赖检查。
    """

    # LaTeX 命令到 Unicode 字符的映射表
    # 用于 pandoc 不可用时的 fallback
    _UNICODE_REPLACEMENTS = {
        r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
        r"\pi": "π", r"\theta": "θ", r"\lambda": "λ", r"\sigma": "σ",
        r"\omega": "ω", r"\sum": "∑", r"\int": "∫", r"\infty": "∞",
        r"\sqrt": "√", r"\frac": "½", r"\times": "×", r"\div": "÷",
        r"\pm": "±", r"\leq": "≤", r"\geq": "≥", r"\neq": "≠",
        r"\approx": "≈", r"\rightarrow": "→", r"\leftarrow": "←",
        r"\Rightarrow": "⇒", r"\forall": "∀", r"\exists": "∃",
        r"\in": "∈", r"\subset": "⊂", r"\cup": "∪", r"\cap": "∩",
    }

    def __init__(self) -> None:
        pass

    def check_dependencies(self) -> tuple[bool, str]:
        """
        检查 pandoc 是否安装

        pandoc 是公式转换的关键依赖。

        Returns:
            (是否可用, 错误信息)
        """
        import subprocess
        try:
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, "pandoc 未正确安装"
        except FileNotFoundError:
            return False, "pandoc 未安装"
        return True, ""

    def convert_inline(self, latex_formula: str) -> str:
        """
        转换行内公式为 Unicode 表示 - Fallback 方案

        当 pandoc 转换失败时，使用 Unicode 字符近似显示公式。
        这不是完整的解决方案，但至少可以显示一些基本符号。

        支持的符号映射：
        - 希腊字母：α, β, γ, δ, π, θ, λ, σ, ω
        - 运算符：∑, ∫, ∞, √, ×, ÷, ±
        - 关系符：≤, ≥, ≠, ≈, →, ←, ⇒
        - 集合符：∀, ∃, ∈, ⊂, ∪, ∩

        Args:
            latex_formula: LaTeX 公式字符串

        Returns:
            转换后的 Unicode 字符串
        """
        result = latex_formula

        # 替换 LaTeX 命令为 Unicode 字符
        for k, v in self._UNICODE_REPLACEMENTS.items():
            result = result.replace(k, v)

        # 简化花括号语法：
        # - _{abc} -> _abc（下标）
        # - ^{abc} -> ^abc（上标）
        # - {abc} -> abc（组）
        result = result.replace("_{", "_").replace("^{", "^").replace("{", "").replace("}", "")

        return result