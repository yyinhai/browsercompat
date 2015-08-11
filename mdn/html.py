# coding: utf-8
"""Parser for HTML fragments used on MDN.

This is designed to be a foundation for more specific tasks, such as
extracting compatibility data from MDN pages, or validating API data when
an HTML subset is allowed.

HTML is actually unparsable, according to smart people:
http://trevorjim.com/a-grammar-for-html5/

So, this code is incomplete and impossible and possibly unreviewable.
"""
from __future__ import unicode_literals

from collections import OrderedDict
import re

from django.utils.functional import cached_property
from django.utils.encoding import python_2_unicode_compatible
from django.utils.six import text_type, string_types

from parsimonious.grammar import Grammar
from parsimonious.nodes import Node

from .utils import join_content
from .visitor import Visitor

# Parsimonious grammar for HTML fragments
html_grammar_source = r"""
#
# HTML tokens (only those used in compat tables)
#
html = html_block / empty_text
html_block = html_element+
html_element = a_element / br_element / code_element / dd_element /
    div_element / dl_element / dt_element / em_element / h1_element /
    h2_element / h3_element / h3_element / h4_element / h5_element/
    h6_element / img_element / li_element / p_element / pre_element /
    span_element / strong_element / sup_element / table_element /
    tbody_element / td_element / th_element / thead_element / tr_element /
    ul_element / text_block

a_element = a_open a_content a_close
a_open = "<a" _ attrs ">"
a_content = html
a_close = "</a>"

br_element = "<br" _ attrs ("/>" / ">") _

code_element = code_open code_content code_close
code_open = "<code" _ attrs ">"
code_content = ~r"(?P<content>.*?(?=</code>))"s
code_close = "</code>"

div_element = div_open div_content div_close
div_open = "<div" _ attrs ">"
div_content = html
div_close = "</div>"

dd_element = dd_open dd_content dd_close
dd_open = "<dd" _ attrs ">"
dd_content = html
dd_close = "</dd>"

dl_element = dl_open dl_content dl_close
dl_open = "<dl" _ attrs ">"
dl_content = html
dl_close = "</dl>"

dt_element = dt_open dt_content dt_close
dt_open = "<dt" _ attrs ">"
dt_content = html
dt_close = "</dt>"

em_element = em_open em_content em_close
em_open = "<em" _ attrs ">"
em_content = html
em_close = "</em>"

h1_element = h1_open h1_content h1_close
h1_open = "<h1" _ attrs ">"
h1_content = html
h1_close = "</h1>"

h2_element = h2_open h2_content h2_close
h2_open = "<h2" _ attrs ">"
h2_content = html
h2_close = "</h2>"

h3_element = h3_open h3_content h3_close
h3_open = "<h3" _ attrs ">"
h3_content = html
h3_close = "</h3>"

h4_element = h4_open h4_content h4_close
h4_open = "<h4" _ attrs ">"
h4_content = html
h4_close = "</h4>"

h5_element = h5_open h5_content h5_close
h5_open = "<h5" _ attrs ">"
h5_content = html
h5_close = "</h5>"

h6_element = h6_open h6_content h6_close
h6_open = "<h6" _ attrs ">"
h6_content = html
h6_close = "</h6>"

img_element = "<img" _ attrs ("/>" / ">") _

li_element = li_open li_content li_close
li_open = "<li" _ attrs ">"
li_content = html
li_close = "</li>"

p_element = p_open p_content p_close
p_open = "<p" _ attrs ">"
p_content = html
p_close = "</p>"

pre_element = pre_open pre_content pre_close
pre_open = "<pre" _ attrs ">"
pre_content = ~r"(?P<content>.*?(?=</pre>))"s
pre_close = "</pre>"

span_element = span_open span_content span_close
span_open = "<span" _ attrs ">"
span_content = html
span_close = "</span>"

strong_element = strong_open strong_content strong_close
strong_open = "<strong" _ attrs ">"
strong_content = html
strong_close = "</strong>"

sup_element = sup_open sup_content sup_close
sup_open = "<sup" _ attrs ">"
sup_close = "</sup>"
sup_content = html

table_element = table_open table_content table_close
table_open = "<table" _ attrs ">"
table_content = html
table_close = "</table>"

tbody_element = tbody_open tbody_content tbody_close
tbody_open = "<tbody" _ attrs ">"
tbody_content = html
tbody_close = "</tbody>"

td_element = td_open td_content td_close
td_open = "<td" _ attrs ">"
td_content = html
td_close = "</td>"

th_element = th_open th_content th_close
th_open = "<th" _ attrs ">"
th_content = html
th_close = "</th>"

thead_element = thead_open thead_content thead_close
thead_open = "<thead" _ attrs ">"
thead_content = html
thead_close = "</thead>"

tr_element = tr_open tr_content tr_close
tr_open = "<tr" _ attrs ">"
tr_content = html
tr_close = "</tr>"

ul_element = ul_open ul_content ul_close
ul_open = "<ul" _ attrs ">"
ul_content = html
ul_close = "</ul>"

#
# HTML tag attributes
#
attrs = attr*
attr = _ ident _ "=" _ value _
ident = ~r"(?P<content>[a-z][a-z0-9-:]*)"
value = (double_quoted_text / single_quoted_text / "0" / "1")

#
# Generic text
#
text = (double_quoted_text / single_quoted_text / bare_text)
bare_text = ~r"(?P<content>[^<]*)"
double_quoted_text = ~r'"(?P<content>[^"]*)"'
single_quoted_text = ~r"'(?P<content>[^']*)'"
# Whitespace
_ = ~r"[ \t\r\n]*"s

#
# Text segments
# Derived grammars can redefine text_token and text_item
#
text_block = text_token+
text_token = text_item
text_item = ~r"(?P<content>[^<]+)"s
empty_text = ""
"""
html_grammar = Grammar(html_grammar_source)


@python_2_unicode_compatible
class HTMLInterval(object):
    """A span of HTML content, from a tag to text."""

    def __init__(self, raw='', start=0):
        self.raw = raw
        self.start = start

    @property
    def end(self):
        return self.start + len(self.raw)

    def __str__(self):
        return self.raw

    def to_html(self):
        """Convert to HTML."""
        return text_type(self)

    def to_text(self):
        """Convert to non-HTML text."""
        return ""

    @property
    def issues(self):
        return []


@python_2_unicode_compatible
class HTMLText(HTMLInterval):
    """A plain text section of HTML"""

    def __init__(self, **kwargs):
        super(HTMLText, self).__init__(**kwargs)
        self.cleaned = self.cleanup_whitespace(self.raw)

    def __str__(self):
        return self.cleaned

    re_whitespace = re.compile(r'''(?x)  # Be verbose
    (\s|                # Any whitespace, or
     (<\s*br\s*/?>)|    # A variant of <br>, or
     \xa0|              # Unicode non-breaking space, or
     (\&nbsp;)          # HTML nbsp character
    )+                  # One or more in a row
    ''')

    def to_text(self):
        return self.cleaned

    def cleanup_whitespace(self, text):
        """Normalize whitespace"""
        normal = self.re_whitespace.sub(' ', text)
        assert '  ' not in normal
        return normal.strip()


@python_2_unicode_compatible
class HTMLEmptyText(HTMLText):
    """An empty text section of HTML"""

    def __init__(self, **kwargs):
        super(HTMLEmptyText, self).__init__(**kwargs)
        assert self.raw == ''

    def __str__(self):
        return ''


@python_2_unicode_compatible
class HTMLBaseTag(HTMLInterval):
    """An HTML tag, such as <li>, <br/>, or </code>"""

    def __init__(self, tag, **kwargs):
        super(HTMLBaseTag, self).__init__(**kwargs)
        assert tag in self.raw
        self.tag = tag

    def __str__(self):
        return "<{}>".format(self.tag)


@python_2_unicode_compatible
class HTMLAttribute(HTMLInterval):
    """An attribute of an HTML tag."""

    def __init__(self, ident, value, **kwargs):
        super(HTMLAttribute, self).__init__(**kwargs)
        assert ident in self.raw
        assert text_type(value) in self.raw
        self.ident = ident
        self.value = value

    def __str__(self):
        if isinstance(self.value, string_types):
            fmt = '{}="{}"'
        else:
            fmt = '{}={}'
        return fmt.format(self.ident, self.value)


@python_2_unicode_compatible
class HTMLAttributes(HTMLInterval):
    """A collection of attributes."""

    def __init__(self, attributes=None, **kwargs):
        super(HTMLAttributes, self).__init__(**kwargs)
        self.attrs = OrderedDict()
        for attr in attributes or []:
            self.attrs[attr.ident] = attr

    def __str__(self):
        return ' '.join([str(attr) for attr in self.attrs.values()])

    def as_dict(self):
        return OrderedDict((k, v.value) for k, v in self.attrs.items())


@python_2_unicode_compatible
class HTMLOpenTag(HTMLBaseTag):
    """An HTML tag, such as <a href="#foo">"""

    def __init__(
            self, attributes, attribute_actions=None, drop_tag=False,
            scope=None, **kwargs):
        """Initialize an HTML open tag

        Keyword Arguments:
        attributes - An HTMLAttributes instance
        attribute_actions - A optional dictionary of attribute identifiers to
            validation actions (see validate_attributes).
        drop_tag - If true, the containing tag will be dropped in to_html()
        scope - The scope for issues
        """
        super(HTMLOpenTag, self).__init__(**kwargs)
        self.attributes = attributes
        self.drop_tag = drop_tag
        self.scope = scope

        if self.drop_tag:
            self._issues = (
                ('tag_dropped', self.start, self.end,
                 {'scope': self.scope, 'tag': self.tag}),)
        elif attribute_actions:
            self._issues = self.validate_attributes(
                attributes, attribute_actions)
        else:
            self._issues = []

    def __str__(self):
        attrs = str(self.attributes)
        if attrs:
            return '<{} {}>'.format(self.tag, attrs)
        else:
            return '<{}>'.format(self.tag)

    def validate_attributes(self, attributes, actions):
        """Validate attributes for an open tag.

        Attribute validation is controlled by actions, which is a
        dictionary of attribute identifiers ('class', 'href', etc.) to
        validation strategies.  The None identifier entry gives a default
        validation.

        Valid validation actions are:
        - 'ban': Drop the attribute, and add unexpected_attribute issue
        - 'drop': Drop the attribute
        - 'keep': Keep the attribute
        - 'must': Add missing_attribute issue if not present

        Return is a list of issues found in the attributes
        """
        # Verify attribute actions
        assert None in actions
        assert actions[None] in ('ban', 'drop', 'keep')

        # Are all actions 'keep' actions? Do nothing.
        if all([action == 'keep' for action in actions.values()]):
            return []

        # Look for missing 'must' attributes
        must_idents = set(
            ident for ident, action in actions.items() if action == 'must')
        has_idents = set(attributes.attrs.keys())
        missing_idents = must_idents - has_idents

        # Look for attributes to drop
        drop_idents = []
        for attr in attributes.attrs.values():
            ident = attr.ident
            action = actions.get(ident, actions[None])
            assert action in ('ban', 'drop', 'keep', 'must')
            if action in ('ban', 'drop'):
                drop_idents.append((ident, action))

        # Construct the expected attributes string
        if drop_idents:
            expected = sorted(must_idents)
            if len(expected) > 1:
                expected_text = (
                    'the attributes ' + ', '.join(expected[:-1]) + ' or ' +
                    expected[-1])
            elif len(expected) == 1:
                expected_text = 'the attribute ' + expected[0]
            else:
                expected_text = 'no attributes'

        # Drop attributes, and add issues for banned attributes
        issues = []
        for ident, action in drop_idents:
            if action == 'ban':
                attr = attributes.attrs[ident]
                issues.append((
                    'unexpected_attribute', attr.start, attr.end,
                    {'node_type': self.tag, 'ident': ident,
                     'value': attr.value, 'expected': expected_text}))
            del attributes.attrs[ident]

        # Add issues for missing required attributes
        for ident in missing_idents:
            issues.append((
                'missing_attribute', self.start, self.end,
                {'node_type': self.tag, 'ident': ident}))

        return issues

    @property
    def issues(self):
        return self._issues


@python_2_unicode_compatible
class HTMLCloseTag(HTMLBaseTag):
    """An HTML closing tag, such as </a>"""
    pass

    def __str__(self):
        return "</{}>".format(self.tag)


class HTMLSelfClosingElement(HTMLOpenTag):
    """An HTML element that is just a tag, such as <br> and <img>."""
    pass


@python_2_unicode_compatible
class HTMLElement(HTMLInterval):
    """An HTML element that contains child elements"""

    def __init__(
            self, open_tag, close_tag=None, children=None, drop_tag=False,
            scope=None, **kwargs):
        super(HTMLElement, self).__init__(**kwargs)
        self.open_tag = open_tag
        self.close_tag = close_tag
        assert self.open_tag.tag == self.close_tag.tag
        self.tag = self.open_tag.tag
        self.children = []
        for child in (children or []):
            self.children.append(child)
        self.drop_tag = drop_tag

    def __str__(self):
        content = join_content(text_type(child) for child in self.children)
        return "{}{}{}".format(self.open_tag, content, self.close_tag)

    @cached_property
    def attributes(self):
        return self.open_tag.attributes.as_dict()

    def to_html(self, drop_tag=None):
        content = join_content(child.to_html() for child in self.children)
        if drop_tag is None:
            drop_tag = self.drop_tag
        if drop_tag:
            return content
        else:
            return "{}{}{}".format(self.open_tag, content, self.close_tag)

    def to_text(self):
        content = join_content(child.to_text() for child in self.children)
        return content


class HnElement(HTMLElement):
    """An HTML header, such as <h2>"""
    def __init__(self, **kwargs):
        super(HnElement, self).__init__(**kwargs)
        self.level = int(self.tag[1:])


class HTMLVisitor(Visitor):
    """Extract HTML structure from an HTML fragment.

    Handles the limited HTML structure allowed by the parser. If the HTML
    fragment is inside of a document, then an offset can be applied so that
    positions are reported relative to the whole document.
    """
    _default_attribute_actions = {None: 'keep'}

    def process(self, cls, node, **kwargs):
        """Convert a node to an HTML* instance"""
        processed = cls(
            raw=node.text, start=node.start + self.offset, **kwargs)
        for issue in processed.issues:
            self.add_raw_issue(issue)
        return processed

    #
    # Basic visitors
    #
    def generic_visit(self, node, visited_children):
        """Visitor when none is specified."""
        return visited_children or node

    def _visit_content(self, node, children):
        """Visitor for re nodes with a named (?P<content>) section."""
        return node.match.group('content')

    def _visit_block(self, node, tokens):
        """Visit a 1-or-more block of tokens."""
        assert isinstance(tokens, list)
        for token in tokens:
            assert isinstance(token, HTMLInterval)
        return tokens

    def _visit_token(self, node, children):
        """Visit a single (possibly list-wrapped) token."""
        assert len(children) == 1
        item = children[0]
        if isinstance(item, HTMLInterval):
            return item
        else:
            assert len(item) == 1, item
            assert isinstance(item[0], HTMLInterval), item[0]
            return item[0]

    #
    # HTML tokens
    #
    def visit_html(self, node, children):
        assert isinstance(children, list)
        assert len(children) == 1
        return children[0]

    visit_html_block = _visit_block
    visit_html_element = _visit_token
    visit_hn_element = _visit_token

    def _visit_open(self, node, children, actions=None, cls=None, **kwargs):
        """Parse an opening tag with an optional attributes list"""
        open_tag_node, ws, attrs, close = children
        assert isinstance(open_tag_node, Node), type(open_tag_node)
        open_tag = open_tag_node.text
        assert open_tag.startswith('<')
        tag = open_tag[1:]
        assert isinstance(attrs, HTMLAttributes), type(attrs)
        cls = cls or HTMLOpenTag
        return self.process(
            cls, node, tag=tag, attributes=attrs,
            attribute_actions=actions or self._default_attribute_actions,
            **kwargs)

    visit_a_open = _visit_open
    visit_code_open = _visit_open
    visit_dd_open = _visit_open
    visit_div_open = _visit_open
    visit_dl_open = _visit_open
    visit_dt_open = _visit_open
    visit_em_open = _visit_open
    visit_h1_open = _visit_open
    visit_h2_open = _visit_open
    visit_h3_open = _visit_open
    visit_h4_open = _visit_open
    visit_h5_open = _visit_open
    visit_h6_open = _visit_open
    visit_li_open = _visit_open
    visit_p_open = _visit_open
    visit_pre_open = _visit_open
    visit_span_open = _visit_open
    visit_strong_open = _visit_open
    visit_sup_open = _visit_open
    visit_table_open = _visit_open
    visit_tbody_open = _visit_open
    visit_td_open = _visit_open
    visit_th_open = _visit_open
    visit_thead_open = _visit_open
    visit_tr_open = _visit_open
    visit_ul_open = _visit_open

    def _visit_self_closing_element(self, node, children, **kwargs):
        return self._visit_open(
            node, children[:-1], cls=HTMLSelfClosingElement, **kwargs)

    visit_br_element = _visit_self_closing_element
    visit_img_element = _visit_self_closing_element

    def _visit_close(self, node, empty):
        close_tag = node.text
        assert close_tag.startswith('</')
        assert close_tag.endswith('>')
        tag = close_tag[2:-1]
        return self.process(HTMLCloseTag, node, tag=tag)

    visit_a_close = _visit_close
    visit_code_close = _visit_close
    visit_dd_close = _visit_close
    visit_div_close = _visit_close
    visit_dl_close = _visit_close
    visit_dt_close = _visit_close
    visit_em_close = _visit_close
    visit_h1_close = _visit_close
    visit_h2_close = _visit_close
    visit_h3_close = _visit_close
    visit_h4_close = _visit_close
    visit_h5_close = _visit_close
    visit_h6_close = _visit_close
    visit_li_close = _visit_close
    visit_p_close = _visit_close
    visit_pre_close = _visit_close
    visit_span_close = _visit_close
    visit_strong_close = _visit_close
    visit_sup_close = _visit_close
    visit_table_close = _visit_close
    visit_tbody_close = _visit_close
    visit_td_close = _visit_close
    visit_th_close = _visit_close
    visit_thead_close = _visit_close
    visit_tr_close = _visit_close
    visit_ul_close = _visit_close

    def _visit_element(self, node, children, **kwargs):
        """Parse a <tag>content</tag> element."""
        open_tag, content, close_tag = children
        assert isinstance(open_tag, HTMLOpenTag), open_tag
        if isinstance(content, (HTMLText, HTMLEmptyText)):
            children = [content]
        else:
            assert isinstance(content, list)
            for child in content:
                assert isinstance(child, HTMLInterval), child
            children = content
        assert isinstance(close_tag, HTMLCloseTag), close_tag
        element_class = kwargs.pop('element_class', HTMLElement)
        return self.process(
            element_class, node, open_tag=open_tag, close_tag=close_tag,
            children=children, **kwargs)

    visit_a_element = _visit_element
    visit_dd_element = _visit_element
    visit_div_element = _visit_element
    visit_dl_element = _visit_element
    visit_dt_element = _visit_element
    visit_em_element = _visit_element
    visit_li_element = _visit_element
    visit_p_element = _visit_element
    visit_span_element = _visit_element
    visit_strong_element = _visit_element
    visit_sup_element = _visit_element
    visit_table_element = _visit_element
    visit_tbody_element = _visit_element
    visit_td_element = _visit_element
    visit_th_element = _visit_element
    visit_thead_element = _visit_element
    visit_tr_element = _visit_element
    visit_ul_element = _visit_element

    def _visit_text_element(self, node, children, **kwargs):
        """Parse a <tag>unparsed text</tag> element."""
        open_tag, content, close_tag = children
        assert isinstance(content, HTMLText)
        return self._visit_element(node, children, **kwargs)

    visit_code_element = _visit_text_element
    visit_pre_element = _visit_text_element

    def _visit_hn_element(self, node, children, **kwargs):
        return self._visit_element(
            node, children, element_class=HnElement, **kwargs)

    visit_h1_element = _visit_hn_element
    visit_h2_element = _visit_hn_element
    visit_h3_element = _visit_hn_element
    visit_h4_element = _visit_hn_element
    visit_h5_element = _visit_hn_element
    visit_h6_element = _visit_hn_element

    #
    # HTML tag attributes
    #
    def visit_attrs(self, node, attrs):
        """Parse an attribute list."""
        return self.process(HTMLAttributes, node, attributes=attrs)

    def visit_attr(self, node, children):
        """Parse a single ident=value attribute."""
        ws1, ident, ws2, eq, ws3, value, ws4 = children
        assert isinstance(ident, text_type), type(ident)
        assert isinstance(value, (text_type, int)), type(value)
        return self.process(HTMLAttribute, node, ident=ident, value=value)

    visit_ident = _visit_content

    def visit_value(self, node, valnode):
        value = valnode[0]
        if isinstance(value, text_type):
            return value
        else:
            return int(value.text)

    #
    # Generic text
    #
    visit_bare_text = _visit_content
    visit_single_quoted_text = _visit_content
    visit_double_quoted_text = _visit_content

    #
    # Text segments
    #

    visit_text_block = _visit_block
    visit_text_token = _visit_token

    def visit_text_item(self, node, empty):
        assert empty == []
        return self.process(HTMLText, node)

    visit_code_content = visit_text_item
    visit_pre_content = visit_text_item

    def visit_empty_text(self, node, empty):
        assert empty == []
        return self.process(HTMLEmptyText, node)
