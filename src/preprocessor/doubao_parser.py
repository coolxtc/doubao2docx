from .base import BaseParser, PlatformConfig


class DoubaoHTMLParser(BaseParser):
    config = PlatformConfig()
    
    def parse(self, html: str) -> 'ParsedPage':
        return self._parse_impl(html)