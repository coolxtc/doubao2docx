"""
LaTeX 公式转换器模块

提供 LaTeX 公式的 Unicode fallback 转换。
pandoc 不可用时，将 LaTeX 公式转换为 Unicode 字符近似显示。
"""


class LaTeXConverter:
    """LaTeX 公式 Unicode 转换器"""

    _UNICODE_REPLACEMENTS: dict[str, str] = {
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
        """初始化 LaTeX 转换器"""

    def check_dependencies(self) -> tuple[bool, str]:
        """检查 pandoc 是否可用"""
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
        """转换 LaTeX 公式为 Unicode 表示"""
        result = latex_formula

        # 替换 LaTeX 命令为 Unicode 字符
        for k, v in self._UNICODE_REPLACEMENTS.items():
            result = result.replace(k, v)

        # 简化花括号语法
        result = result.replace("_{", "_").replace("^{", "^").replace("{", "").replace("}", "")

        return result