import pytest
from src.generator.latex_converter import LaTeXConverter


class TestLaTeXConverter:
    """测试 LaTeX 公式转换器"""

    def test_init(self):
        """初始化应成功"""
        converter = LaTeXConverter()
        assert converter is not None

    def test_convert_inline_simple_letters(self):
        """转换简单的希腊字母"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\alpha") == "α"
        assert converter.convert_inline(r"\beta") == "β"
        assert converter.convert_inline(r"\gamma") == "γ"

    def test_convert_inline_math_symbols(self):
        """转换数学符号"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\pi") == "π"
        assert converter.convert_inline(r"\infty") == "∞"
        assert converter.convert_inline(r"\sum") == "∑"

    def test_convert_inline_operators(self):
        """转换运算符"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\times") == "×"
        assert converter.convert_inline(r"\div") == "÷"
        assert converter.convert_inline(r"\pm") == "±"

    def test_convert_inline_comparisons(self):
        """转换比较运算符"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\leq") == "≤"
        assert converter.convert_inline(r"\geq") == "≥"
        assert converter.convert_inline(r"\neq") == "≠"

    def test_convert_inline_arrows(self):
        """转换箭头符号"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\rightarrow") == "→"
        assert converter.convert_inline(r"\leftarrow") == "←"
        assert converter.convert_inline(r"\Rightarrow") == "⇒"

    def test_convert_inline_sets(self):
        """转换集合符号"""
        converter = LaTeXConverter()
        assert converter.convert_inline(r"\in") == "∈"
        assert converter.convert_inline(r"\subset") == "⊂"
        assert converter.convert_inline(r"\cup") == "∪"

    def test_convert_inline_complex_formula(self):
        """转换复杂公式"""
        converter = LaTeXConverter()
        result = converter.convert_inline(r"x \alpha y \beta z")
        assert "α" in result
        assert "β" in result
        assert "x" in result
        assert "y" in result
        assert "z" in result

    def test_convert_inline_empty_string(self):
        """空字符串应原样返回"""
        converter = LaTeXConverter()
        assert converter.convert_inline("") == ""

    def test_convert_inline_no_special_chars(self):
        """无特殊字符应原样返回"""
        converter = LaTeXConverter()
        assert converter.convert_inline("hello world") == "hello world"

    def test_convert_inline_braces_handling(self):
        """花括号应被正确处理"""
        converter = LaTeXConverter()
        result = converter.convert_inline(r"x_{1}^{2}")
        assert "1" in result
        assert "2" in result
        assert "{" not in result
        assert "}" not in result