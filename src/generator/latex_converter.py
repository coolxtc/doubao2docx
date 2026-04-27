"""LaTeX 公式 Unicode 转换器模块"""

import subprocess


class LaTeXConverter:
    """LaTeX 公式 Unicode fallback 转换器"""

    # LaTeX 命令到 Unicode 字符的映射表
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

    def check_dependencies(self) -> tuple[bool, str]:
        """
        检查 pandoc 依赖是否可用

        Returns:
            tuple[bool, str]: (是否可用, 错误信息)
        """
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
        将 LaTeX 公式转换为 Unicode 表示

        Args:
            latex_formula: LaTeX 公式文本

        Returns:
            str: Unicode 表示的公式文本
        """
        result = latex_formula

        # 替换 LaTeX 命令为 Unicode 字符
        for k, v in self._UNICODE_REPLACEMENTS.items():
            result = result.replace(k, v)

        # 简化花括号语法
        result = result.replace("_{", "_").replace("^{", "^").replace("{", "").replace("}", "")

        return result
