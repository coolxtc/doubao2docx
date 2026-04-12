"""
LaTeX公式转换器

这个模块提供 LaTeX 公式到 Word 格式的转换功能。

主要功能：
- 检查系统依赖（pandoc）是否安装
- 将 LaTeX 公式转换为 Word 原生公式（OMML）
- Fallback：将公式转换为 Unicode 字符表示

核心概念：
- OMML：Office Math Markup Language，Word 的内置公式格式
- pandoc：文档格式转换工具，支持 LaTeX 到 docx 的转换

依赖：
- brew install pandoc
"""

from typing import Optional


class LaTeXConverter:
    """LaTeX转Word转换器
    
    将 LaTeX 数学公式转换为 Word 文档可以显示的格式。
    
    转换策略：
    1. 优先使用 pandoc 转换为 Word 原生公式（OMML）
    2. 如果失败，使用 Unicode 字符作为 fallback
    """
    
    def __init__(self) -> None:
        pass
    
    def check_dependencies(self) -> tuple[bool, str]:
        """检查依赖是否安装 - pandoc 是公式转换的关键依赖
        
        Returns:
            (是否可用, 错误信息)
        """
        import subprocess
        for cmd in ["pandoc", "pandoc-crossref"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return False, f"{cmd} 未正确安装"
            except FileNotFoundError:
                return False, f"{cmd} 未安装，请运行: brew install {cmd}"
        return True, ""
    
    def convert_inline(self, latex_formula: str) -> str:
        """转换行内公式为Unicode表示 - Fallback 方案
        
        当 pandoc 转换失败时，使用 Unicode 字符近似显示公式。
        这不是完整的解决方案，但至少可以显示一些基本符号。
        
        支持的符号：
        - 希腊字母：α, β, γ, δ, π, θ, λ, σ, ω
        - 运算符：∑, ∫, ∞, √, ×, ÷, ±
        - 关系符：≤, ≥, ≠, ≈, →, ←, ⇒
        - 集合符：∀, ∃, ∈, ⊂, ∪, ∩
        
        Args:
            latex_formula: LaTeX 公式字符串
            
        Returns:
            转换后的 Unicode 字符串
        """
        replacements = {
            r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
            r"\pi": "π", r"\theta": "θ", r"\lambda": "λ", r"\sigma": "σ",
            r"\omega": "ω", r"\sum": "∑", r"\int": "∫", r"\infty": "∞",
            r"\sqrt": "√", r"\frac": "½", r"\times": "×", r"\div": "÷",
            r"\pm": "±", r"\leq": "≤", r"\geq": "≥", r"\neq": "≠",
            r"\approx": "≈", r"\rightarrow": "→", r"\leftarrow": "←",
            r"\Rightarrow": "⇒", r"\forall": "∀", r"\exists": "∃",
            r"\in": "∈", r"\subset": "⊂", r"\cup": "∪", r"\cap": "∩",
        }
        result = latex_formula
        for k, v in replacements.items():
            result = result.replace(k, v)
        
        # 简化花括号：_{abc} -> _abc, ^{abc} -> ^abc, {abc} -> abc
        result = result.replace("_{", "_").replace("^{", "^").replace("{", "").replace("}", "")
        return result