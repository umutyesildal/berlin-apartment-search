"""Small tolerant HTML tree for search cards and snapshot attributes."""

from html.parser import HTMLParser


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self, scripts=False):
        if self.tag in ('script', 'style', 'svg') and not scripts:
            return ''
        parts = [child.text(scripts) if isinstance(child, Node) else child for child in self.children]
        return ' '.join(part for part in parts if part.strip()).strip()


class Document(HTMLParser):
    VOID = {'img', 'input', 'br', 'hr', 'meta', 'link', 'source', 'wbr', 'area', 'base', 'embed', 'param', 'col', 'track'}

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        self.stack[-1].children.append(text)
