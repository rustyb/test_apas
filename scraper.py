# this is a base scraper for SwiftLG system planning applications for use by Openly Local

# there are 20 authorities using this system, all are defined here but only the first 10 are scraped

import scraperwiki
from datetime import timedelta
from datetime import date
from datetime import datetime
import re
import dateutil.parser
import random
import urllib
import urlparse
import sys

#scrapemark = scraperwiki.utils.swimport("scrapemark_09")

# this is scrapemark 0.9 from: http://arshaw.com/scrapemark/download/
# the scraperwiki version of scrapemark seems to be the feb 9 2011 pre-release version from: https://github.com/arshaw/scrapemark
# the two versions can be distinguished by the 'verbose' flag which is on by default in the pre-release version
# the pre-release version has some bugs which are shown in the test code at the bottom of this module

import re
import unicodedata
import urllib, urllib2
import urlparse
import cgi
import cookielib
from htmlentitydefs import name2codepoint

verbose = False
user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.8.1.3) Gecko/20070309 Firefox/2.0.0.3'

# todo: throw invalid arguments error if neither html nor url ar given

# todo: better support for comment stuff (js in javascript)?

def scrape(pattern, html=None, url=None, get=None, post=None, headers=None, cookie_jar=None):
    """
    *Pattern* is either a string or a :class:`ScrapeMarkPattern` object and is applied
    to *html*. If *html* is not present, *url* is used to fetch the html, along with
    the optional parameters *get*, *post*, *header*, and *cookie_jar*. If specified,
    *get*, *post*, and *header* must be dictionary-like objects. If specified,
    *cookie_jar* must be an instance of :class:`cookielib.CookieJar`.

    If a match is found, this function returns a dictionary, list, string, int, float or
    bool, depending upon *pattern*. See the notes on :ref:`PatternSyntax` for more
    information. If no match is found, ``None`` is returned.

    To effectively simulate a browser request when fetching the html at *url*, if
    ``headers['User-Agent']`` is not specified, :data:`scrapemark.user_agent` is used
    instead. Also, if *cookie_jar* is not specified, an empty :class:`cookielib.CookieJar`
    is instantiated and used in the http transaction.
    """
    if type(pattern) == str:
        pattern = compile(pattern)
    return pattern.scrape(html, url, get, post, headers, cookie_jar)
    
def compile(pattern):
    """
    Compiles a pattern into a :class:`ScrapeMarkPattern` object.
    Using this object is optimal if you want to apply a single pattern multiple
    times.
    """
    return _Pattern(_compile(pattern, True))
    
def fetch_html(url, get=None, post=None, headers=None, cookie_jar=None):
    """
    Fetches and returns the html at the given *url*, optionally using *get*, *post*,
    *header*, and *cookie_jar*. No scraping occurs. This function is used internally
    by :func:`scrapemark.scrape`. For the behavior of ``headers['User-Agent']`` and *cookie_jar*, read
    the :func:`scrapemark.scrape` documentation.
    """
    if get:
        if type(get) == str:
            get = cgi.parse_qs(get)
        l = list(urlparse.urlparse(url))
        g = cgi.parse_qs(l[4])
        g.update(get)
        l[4] = urllib.urlencode(g)
        url = urlparse.urlunparse(l)
    if post and type(post) != str:
        post = urllib.urlencode(post)
    if cookie_jar == None:
        cookie_jar = cookielib.CookieJar()
    if not headers:
        headers = {'User-Agent': user_agent}
    else:
        if 'User-Agent' not in headers:
            headers['User-Agent'] = user_agent
    if verbose:
        print 'fetching', url, '...'
    request = urllib2.Request(url, post, headers)
    request.add_header('Accept', 'text/html')
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    res = opener.open(request).read()
    if verbose:
        print 'DONE fetching.'
    return res


# INTERNALS
# ----------------------------------------------------------------------

class _Pattern:

    def __init__(self, nodes):
        self._nodes = nodes
    
    def scrape(self, html=None, url=None, get=None, post=None, headers=None, cookie_jar=None):
        if cookie_jar == None:
            cookie_jar = cookielib.CookieJar()
        if html == None:
            html = fetch_html(url, get, post, headers, cookie_jar)
        captures = {}
        if _match(self._nodes, _remove_comments(html), 0, captures, url, cookie_jar) == -1:
            return None
        if len(captures) == 1 and '' in captures:
            return captures['']
        return captures
        

# node types     # information in tuple
_TEXT = 1        # (_TEXT, regex)
_TAG = 2         # (_TAG, open_regex, close_regex, skip, attributes, children)   attributes {name: (regex, [[special_nodes]]) ...}
_CAPTURE = 3     # (_CAPTURE, name_parts, filters)
_SCAN = 4        # (_SCAN, children)
_GOTO = 5        # (_GOTO, filters, children)

_space_re = re.compile(r'\s+')
_tag_re = re.compile(r'<[^>]*>')
_tag_skip_re = re.compile(r'\((.*)\)$')
_attr_re = re.compile(r'([\w-]+)(?:\s*=\s*(?:(["\'])(.*?)\2|(\S+)))?', re.S)
_attr_start_re = re.compile(r'([\w-]+)(?:\s*=\s*)?')
_comment_re = re.compile(r'<!--.*?-->', re.S)
_script_re = re.compile(r'<script[^>]*>.*?</script>', re.S | re.I)
_entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
_closure_start_re = re.compile(r'<|\{[\{\*\@\#]')
_capture_list_re = re.compile(r'\[(\w*)\]')


# functions for compiling a pattern into nodes
# --------------------------------------------------------------

def _compile(s, re_compile):
    slen = len(s)
    i = 0
    nodes = []
    stack = []
    while i < slen:
        m = _closure_start_re.search(s, i)
        if not m:
            break
        closure_name = m.group(0)
        # text since last closure
        text = s[i:m.start()].strip()
        if text:
            nodes.append((_TEXT, _make_text_re(text, re_compile)))
        i = m.end()
        # an HTML tag
        if closure_name == '<':
            inner, i = _next_closure(s, i, '<', '>')
            inner = inner.strip()
            if inner:
                # end tag
                if inner[0] == '/':
                    if stack:
                        nodes = stack.pop()
                # standalone tag
                elif inner[-1] == '/':
                    l = inner[:-1].split(None, 1)
                    name = l[0].strip()
                    name, skip = _tag_skip(name)
                    attrs = {} if len(l) == 1 else _compile_attrs(l[1], re_compile)
                    nodes.append((_TAG, _make_start_tag_re(name, re_compile), _make_end_tag_re(name, re_compile), skip, attrs, []))
                # start tag
                else:
                    l = inner.split(None, 1)
                    name = l[0].strip()
                    name, skip = _tag_skip(name)
                    attrs = {} if len(l) == 1 else _compile_attrs(l[1], re_compile)
                    new_nodes = []
                    nodes.append((_TAG, _make_start_tag_re(name, re_compile), _make_end_tag_re(name, re_compile), skip, attrs, new_nodes))
                    stack.append(nodes)
                    nodes = new_nodes
        # special brackets
        else:
            special_type = closure_name[1]
            # capture
            if special_type == '{':
                inner, i = _next_closure(s, i, '{{', '}}')
                nodes.append(_compile_capture(inner))
            # scan
            elif special_type == '*':
                inner, i = _next_closure(s, i, '{*', '*}')
                nodes.append((_SCAN, _compile(inner, re_compile)))
            # goto
            elif special_type == '@':
                inner, i = _next_closure(s, i, '{@', '@}')
                if inner:
                    filters = []
                    if inner[0] == '|':
                        filters, inner = (inner.split(None, 1) + [''])[:2]
                        filters = filters.split('|')[1:]
                    nodes.append((_GOTO, filters, _compile(inner, True)))
            # comment
            elif special_type == '#':
                i = s.find('#}')
                if i == -1:
                    break
                i += 2
    # ending text
    text = s[i:].strip()
    if text:
        nodes.append((_TEXT, _make_text_re(text, re_compile)))
    stack.append(nodes)
    return stack[0]
    
def _compile_capture(s): # returns the tuple with _CAPTURE
    filters = s.strip().split('|')
    name = filters.pop(0)
    name_parts = []
    for part in name.split('.'):
        m = _capture_list_re.match(part)
        if m:
            name_parts.append((m.group(1),))
        else:
            name_parts.append(part)
    return (_CAPTURE, name_parts, filters)
    
def _compile_attrs(s, re_compile):
    attrs = {}
    i = 0
    slen = len(s)
    while i < slen:
        m = _attr_start_re.search(s, i)
        if not m:
            break
        name = m.group(1).lower()
        i = m.end()
        if i >= slen:
            break
        quote = s[i]
        # no quotes, value ends at next whitespace
        if quote != '"' and quote != "'":
            m = _space_re.search(s, i)
            if m:
                val = s[i:m.start()]
                i = m.end()
            else:
                val = s[i:]
                i = slen
        # quotes
        else:
            i += 1
            start = i
            # find the ending quote, skipping over { }
            while i < slen:
                quote_i = s.find(quote, i)
                bracket_i = s.find('{', i)
                if quote_i == -1:
                    i = slen
                    break
                elif bracket_i == -1 or quote_i < bracket_i:
                    i = quote_i
                    break
                else:
                    inner, i = _next_closure(s, bracket_i + 1, '{', '}')
            val = s[start:i]
        val = val.strip()
        regex = ''
        special_nodes = []
        if val: # if there is no value, empty regex string won't be compiled
            nodes = _compile(val, False)
            prev_special = False
            # concatenate regexes
            for node in nodes:
                if node[0] == _TEXT:
                    regex += node[1]
                    prev_special = False
                elif node[0] != _TAG:
                    if prev_special:
                        special_nodes[-1].append(node)
                    else:
                        regex += '(.*)'
                        special_nodes.append([node])
                        prev_special = True
            if regex != '(.*)':
                regex = '(?:^|\s)' + regex + '(?:\s|$)' # match must be flush with whitespace or start/end
            if re_compile:
                regex = re.compile(regex, re.I)
        attrs[name] = (regex, special_nodes)
    return attrs
    
def _tag_skip(name):
    match = _tag_skip_re.search(name)
    if match:
        try:
            val = match.group(1)
            return name[:match.start()], -1 if val == 'last' else int(val)
        except ValueError:
            return name[:match.start()], 0
    return name, 0
    
def _make_start_tag_re(name, re_compile):
    regex = r'<\s*' + re.escape(name) + r'(?:\s+([^>]*?)|\s*)(/)?>'
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
def _make_end_tag_re(name, re_compile):
    regex = r'</\s*' + re.escape(name) + r'\s*>'
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
def _make_text_re(text, re_compile):
    regex = r'\s+'.join([re.escape(w) for w in text.split()])
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
    
# functions for running pattern nodes on html
# ---------------------------------------------------------------

def _match(nodes, html, i, captures, base_url, cookie_jar): # returns substring index after match, -1 if no match
    anchor_i = i
    special = []
    for node in nodes:
        # match text node
        if node[0] == _TEXT:
            m = node[1].search(html, i)
            if not m:
                return -1
            # run previous special nodes
            if not _run_special_nodes(special, html[anchor_i:m.start()], captures, base_url, cookie_jar):
                return -1
            special = []
            i = anchor_i = m.end()
        # match html tag
        elif node[0] == _TAG:
            if node[3] < 0:
                # backwards from last tag
                starts = []
                while True:
                    m = node[1].search(html, i)
                    if not m:
                        break
                    starts.append(m.start())
                    i = m.end()
                    if not m.group(2): # not standalone
                        body, i = _next_tag(html, i, node[1], node[2])
                i = starts[max(node[3], -len(starts))] # todo::::::::::::::::should throw -1 if not enough
            else:
                # skip forward
                for skip in range(node[3]):
                    m = node[1].search(html, i)
                    if not m:
                        return -1
                    i = m.end()
                    if not m.group(2): # not standalone
                        body, i = _next_tag(html, i, node[1], node[2])
            while True:
                # cycle through tags until all attributes match
                while True:
                    nested_captures = {}
                    m = node[1].search(html, i)
                    if not m:
                        return -1
                    i = m.end()
                    attrs = _parse_attrs(m.group(1) or '')
                    attrs_matched = _match_attrs(node[4], attrs, nested_captures, base_url, cookie_jar)
                    if attrs_matched == -1:
                        return -1
                    if attrs_matched:
                        break
                if m.group(2): # standalone tag
                    _merge_captures(captures, nested_captures)
                    break
                else: # make sure children match
                    body, i = _next_tag(html, i, node[1], node[2])
                    if _match(node[5], body, 0, nested_captures, base_url, cookie_jar) != -1:
                        _merge_captures(captures, nested_captures)
                        break
            # run previous special nodes
            if not _run_special_nodes(special, html[anchor_i:m.start()], captures, base_url, cookie_jar):
                return -1
            special = []
            anchor_i = i
        else:
            special.append(node)
    if not _run_special_nodes(special, html[i:], captures, base_url, cookie_jar):
        return -1
    return i
        
def _match_attrs(attr_nodes, attrs, captures, base_url, cookie_jar): # returns True/False, -1 if failed _run_special_node
    for name, attr_node in attr_nodes.items():
        if name not in attrs:
            return False
        if attr_node[0]: # if attr_node[0] is empty string, done matching
            if not attrs[name]: # bug fix added by AJS to deal with empty attribute
                return False # bug fix added by AJS to deal with empty attribute
            m = attr_node[0].match(attrs[name])
            if not m:
                return False
            # run regex captures over parallel list of special nodes
            for i, special_nodes in enumerate(attr_node[1]):
                for n in special_nodes:
                    if not _run_special_node(n, m.group(i+1), captures, base_url, cookie_jar):
                        return -1
    return True

def _run_special_nodes(nodes, s, captures, base_url, cookie_jar): # returns True/False
    for node in nodes:
        if not _run_special_node(node, s, captures, base_url, cookie_jar):
            return False
    return True
        
def _run_special_node(node, s, captures, base_url, cookie_jar): # returns True/False
    if node[0] == _CAPTURE:
        s = _apply_filters(s, node[2], base_url)
        _set_capture(captures, node[1], s)
    elif node[0] == _SCAN:
        i = 0
        while True:
            nested_captures = {}
            i = _match(node[1], s, i, nested_captures, base_url, cookie_jar)
            if i == -1:
                break
            else:
                _merge_captures(captures, nested_captures)
        # scan always ends with an usuccessful match, so fill in captures that weren't set
        _fill_captures(node[1], captures)
    elif node[0] == _GOTO:
        s = s.strip()
        if not s:
            return False
        new_url = _apply_filters(s, node[1] + ['abs'], base_url)
        new_html = fetch_html(new_url, cookie_jar=cookie_jar)
        if _match(node[2], new_html, 0, captures, new_url, cookie_jar) == -1:
            return False
    return True
    
def _set_capture(captures, name_parts, val, list_append=True):
    obj = captures
    last = len(name_parts) - 1
    for i, part in enumerate(name_parts):
        if i == last:
            new_obj = val
        else:
            new_obj = {}
        if type(part) == tuple:
            if part[0] not in obj:
                if list_append:
                    obj[part[0]] = [new_obj]
                else:
                    obj[part[0]] = []
                    break
            else:
                if type(obj[part[0]]) != list:
                    break
                if i == last or len(obj[part[0]]) == 0 or name_parts[i+1] in obj[part[0]][-1]:
                    if list_append:
                        obj[part[0]].append(new_obj)
                    else:
                        break
                else:
                    new_obj = obj[part[0]][-1]
        else:
            if part not in obj:
                obj[part] = new_obj
            else:
                new_obj = obj[part]
        obj = new_obj
        
def _merge_captures(master, slave):
    for name, val in slave.items():
        if name not in master:
            master[name] = val
        else:
            if type(val) == dict and type(master[name]) == dict:
                _merge_captures(master[name], val)
            elif type(val) == list and type(master[name]) == list:
                for e in val:
                    if type(e) == dict:
                        for n, v in e.items():
                            if len(master[name]) == 0 or type(master[name][-1]) != dict or n in master[name][-1]:
                                master[name].append({n: v})
                            else:
                                master[name][-1][n] = v
                    else:
                        master[name].append(e)
        
def _fill_captures(nodes, captures):
    for node in nodes:
        if node[0] == _TAG:
            _fill_captures(node[5], captures)
            for attr in node[4].values():
                for special_nodes in attr[1]:
                    _fill_captures(special_nodes, captures)
        elif node[0] == _CAPTURE:
            _set_capture(captures, node[1], _apply_filters(None, node[2], None), False)
        elif node[0] == _SCAN:
            _fill_captures(node[1], captures)
        elif node[0] == _GOTO:
            _fill_captures(node[2], captures)
        
def _apply_filters(s, filters, base_url):
    if 'html' not in filters and issubclass(type(s), basestring):
        s = _remove_html(s)
    for f in filters:
        if f == 'unescape':
            if issubclass(type(s), basestring):
                s = s.decode('string_escape')
        elif f == 'abs':
            if issubclass(type(s), basestring):
                s = urlparse.urljoin(base_url, s)
        elif f == 'int':
            try:
                s = int(s)
            except:
                s = 0
        elif f == 'float':
            try:
                s = float(s)
            except:
                s = 0.0
        elif f == 'bool':
            s = bool(s)
    return s
    
    
# html/text utilities
# ---------------------------------------------------------------

def _remove_comments(s):
    return _comment_re.sub('', s)

def _remove_html(s):
    s = _comment_re.sub('', s)
    s = _script_re.sub('', s)
    s = _tag_re.sub('', s)
    s = _space_re.sub(' ', s)
    s = _decode_entities(s)
    s = s.strip()
    return s
    
def _decode_entities(s):
    if type(s) is not unicode:
        s = unicode(s, 'utf-8', 'ignore')
        s = unicodedata.normalize('NFKD', s)
    return _entity_re.sub(_substitute_entity, s)
    
def _substitute_entity(m):
    ent = m.group(2)
    if m.group(1) == "#":
        return unichr(int(ent))
    else:
        cp = name2codepoint.get(ent)
        if cp:
            return unichr(cp)
        else:
            return m.group()
            
def _parse_attrs(s):
    attrs = {}
    for m in _attr_re.finditer(s):
        # next 4 lines are bug fix from Internet to deal with empty attributes AJS
        value = m.group(3)
        if value is None:
            value = m.group(4)
        attrs[m.group(1)] = value
        #attrs[m.group(1)] = m.group(3) or m.group(4)
    return attrs
    
def _next_tag(s, i, tag_open_re, tag_close_re, depth=1): # returns (tag body, substring index after tag)
    slen = len(s)
    start = i
    while i < slen:
        tag_open = tag_open_re.search(s, i)
        tag_close = tag_close_re.search(s, i)
        if not tag_close:
            i = len(s)
            break
        elif not tag_open or tag_close.start() < tag_open.start():
            i = tag_close.end()
            depth -= 1
            if depth == 0:
                return s[start:tag_close.start()], i
        else:
            if not (tag_open and tag_open.group(2)): # not a standalone tag
                depth += 1
            i = tag_open.end()
    return s[start:i], i

def _next_closure(s, i, left_str, right_str, depth=1): # returns (closure body, substring index after closure)
    slen = len(s)
    start = i
    while i < slen:
        left = s.find(left_str, i)
        right = s.find(right_str, i)
        if right == -1:
            i = len(s)
            break
        elif left == -1 or right < left:
            i = right + len(right_str)
            depth -= 1
            if depth == 0:
                return s[start:right], i
        else:
            depth += 1
            i = left + len(left_str)
    return s[start:i], i
    

#testing scrapemark feature to obtain adjacent special markup as follows:
# <a href='{{ variablename }}{@ subpattern @}'></a>
# which is documented on this page -> http://arshaw.com/scrapemark/docs/
# but which does not seem to work on scraperwiki
# this is because scraperwiki seems not to be using the released 0.9 version of scrapemark

#html = """<a href="http://www.google.co.uk"></a>"""
#target = """<a href="{{ variablename }}{@ <p>{{ subpattern }}</p> @}"></a>"""

#print scrape(target, html) # use scrapemark 0.9 code above - SUCCEEDS

#import scrapemark
#print scrapemark.scrape(target, html) # use scraperwiki version - FAILS
# this is scrapemark 0.9 from: http://arshaw.com/scrapemark/download/
# the scraperwiki version of scrapemark seems to be the feb 9 2011 pre-release version from: https://github.com/arshaw/scrapemark
# the two versions can be distinguished by the 'verbose' flag which is on by default in the pre-release version
# the pre-release version has some bugs which are shown in the test code at the bottom of this module

import re
import unicodedata
import urllib, urllib2
import urlparse
import cgi
import cookielib
from htmlentitydefs import name2codepoint

verbose = False
user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.8.1.3) Gecko/20070309 Firefox/2.0.0.3'

# todo: throw invalid arguments error if neither html nor url ar given

# todo: better support for comment stuff (js in javascript)?

def scrape(pattern, html=None, url=None, get=None, post=None, headers=None, cookie_jar=None):
    """
    *Pattern* is either a string or a :class:`ScrapeMarkPattern` object and is applied
    to *html*. If *html* is not present, *url* is used to fetch the html, along with
    the optional parameters *get*, *post*, *header*, and *cookie_jar*. If specified,
    *get*, *post*, and *header* must be dictionary-like objects. If specified,
    *cookie_jar* must be an instance of :class:`cookielib.CookieJar`.

    If a match is found, this function returns a dictionary, list, string, int, float or
    bool, depending upon *pattern*. See the notes on :ref:`PatternSyntax` for more
    information. If no match is found, ``None`` is returned.

    To effectively simulate a browser request when fetching the html at *url*, if
    ``headers['User-Agent']`` is not specified, :data:`scrapemark.user_agent` is used
    instead. Also, if *cookie_jar* is not specified, an empty :class:`cookielib.CookieJar`
    is instantiated and used in the http transaction.
    """
    if type(pattern) == str:
        pattern = compile(pattern)
    return pattern.scrape(html, url, get, post, headers, cookie_jar)
    
def compile(pattern):
    """
    Compiles a pattern into a :class:`ScrapeMarkPattern` object.
    Using this object is optimal if you want to apply a single pattern multiple
    times.
    """
    return _Pattern(_compile(pattern, True))
    
def fetch_html(url, get=None, post=None, headers=None, cookie_jar=None):
    """
    Fetches and returns the html at the given *url*, optionally using *get*, *post*,
    *header*, and *cookie_jar*. No scraping occurs. This function is used internally
    by :func:`scrapemark.scrape`. For the behavior of ``headers['User-Agent']`` and *cookie_jar*, read
    the :func:`scrapemark.scrape` documentation.
    """
    if get:
        if type(get) == str:
            get = cgi.parse_qs(get)
        l = list(urlparse.urlparse(url))
        g = cgi.parse_qs(l[4])
        g.update(get)
        l[4] = urllib.urlencode(g)
        url = urlparse.urlunparse(l)
    if post and type(post) != str:
        post = urllib.urlencode(post)
    if cookie_jar == None:
        cookie_jar = cookielib.CookieJar()
    if not headers:
        headers = {'User-Agent': user_agent}
    else:
        if 'User-Agent' not in headers:
            headers['User-Agent'] = user_agent
    if verbose:
        print 'fetching', url, '...'
    request = urllib2.Request(url, post, headers)
    request.add_header('Accept', 'text/html')
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    res = opener.open(request).read()
    if verbose:
        print 'DONE fetching.'
    return res


# INTERNALS
# ----------------------------------------------------------------------

class _Pattern:

    def __init__(self, nodes):
        self._nodes = nodes
    
    def scrape(self, html=None, url=None, get=None, post=None, headers=None, cookie_jar=None):
        if cookie_jar == None:
            cookie_jar = cookielib.CookieJar()
        if html == None:
            html = fetch_html(url, get, post, headers, cookie_jar)
        captures = {}
        if _match(self._nodes, _remove_comments(html), 0, captures, url, cookie_jar) == -1:
            return None
        if len(captures) == 1 and '' in captures:
            return captures['']
        return captures
        

# node types     # information in tuple
_TEXT = 1        # (_TEXT, regex)
_TAG = 2         # (_TAG, open_regex, close_regex, skip, attributes, children)   attributes {name: (regex, [[special_nodes]]) ...}
_CAPTURE = 3     # (_CAPTURE, name_parts, filters)
_SCAN = 4        # (_SCAN, children)
_GOTO = 5        # (_GOTO, filters, children)

_space_re = re.compile(r'\s+')
_tag_re = re.compile(r'<[^>]*>')
_tag_skip_re = re.compile(r'\((.*)\)$')
_attr_re = re.compile(r'([\w-]+)(?:\s*=\s*(?:(["\'])(.*?)\2|(\S+)))?', re.S)
_attr_start_re = re.compile(r'([\w-]+)(?:\s*=\s*)?')
_comment_re = re.compile(r'<!--.*?-->', re.S)
_script_re = re.compile(r'<script[^>]*>.*?</script>', re.S | re.I)
_entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
_closure_start_re = re.compile(r'<|\{[\{\*\@\#]')
_capture_list_re = re.compile(r'\[(\w*)\]')


# functions for compiling a pattern into nodes
# --------------------------------------------------------------

def _compile(s, re_compile):
    slen = len(s)
    i = 0
    nodes = []
    stack = []
    while i < slen:
        m = _closure_start_re.search(s, i)
        if not m:
            break
        closure_name = m.group(0)
        # text since last closure
        text = s[i:m.start()].strip()
        if text:
            nodes.append((_TEXT, _make_text_re(text, re_compile)))
        i = m.end()
        # an HTML tag
        if closure_name == '<':
            inner, i = _next_closure(s, i, '<', '>')
            inner = inner.strip()
            if inner:
                # end tag
                if inner[0] == '/':
                    if stack:
                        nodes = stack.pop()
                # standalone tag
                elif inner[-1] == '/':
                    l = inner[:-1].split(None, 1)
                    name = l[0].strip()
                    name, skip = _tag_skip(name)
                    attrs = {} if len(l) == 1 else _compile_attrs(l[1], re_compile)
                    nodes.append((_TAG, _make_start_tag_re(name, re_compile), _make_end_tag_re(name, re_compile), skip, attrs, []))
                # start tag
                else:
                    l = inner.split(None, 1)
                    name = l[0].strip()
                    name, skip = _tag_skip(name)
                    attrs = {} if len(l) == 1 else _compile_attrs(l[1], re_compile)
                    new_nodes = []
                    nodes.append((_TAG, _make_start_tag_re(name, re_compile), _make_end_tag_re(name, re_compile), skip, attrs, new_nodes))
                    stack.append(nodes)
                    nodes = new_nodes
        # special brackets
        else:
            special_type = closure_name[1]
            # capture
            if special_type == '{':
                inner, i = _next_closure(s, i, '{{', '}}')
                nodes.append(_compile_capture(inner))
            # scan
            elif special_type == '*':
                inner, i = _next_closure(s, i, '{*', '*}')
                nodes.append((_SCAN, _compile(inner, re_compile)))
            # goto
            elif special_type == '@':
                inner, i = _next_closure(s, i, '{@', '@}')
                if inner:
                    filters = []
                    if inner[0] == '|':
                        filters, inner = (inner.split(None, 1) + [''])[:2]
                        filters = filters.split('|')[1:]
                    nodes.append((_GOTO, filters, _compile(inner, True)))
            # comment
            elif special_type == '#':
                i = s.find('#}')
                if i == -1:
                    break
                i += 2
    # ending text
    text = s[i:].strip()
    if text:
        nodes.append((_TEXT, _make_text_re(text, re_compile)))
    stack.append(nodes)
    return stack[0]
    
def _compile_capture(s): # returns the tuple with _CAPTURE
    filters = s.strip().split('|')
    name = filters.pop(0)
    name_parts = []
    for part in name.split('.'):
        m = _capture_list_re.match(part)
        if m:
            name_parts.append((m.group(1),))
        else:
            name_parts.append(part)
    return (_CAPTURE, name_parts, filters)
    
def _compile_attrs(s, re_compile):
    attrs = {}
    i = 0
    slen = len(s)
    while i < slen:
        m = _attr_start_re.search(s, i)
        if not m:
            break
        name = m.group(1).lower()
        i = m.end()
        if i >= slen:
            break
        quote = s[i]
        # no quotes, value ends at next whitespace
        if quote != '"' and quote != "'":
            m = _space_re.search(s, i)
            if m:
                val = s[i:m.start()]
                i = m.end()
            else:
                val = s[i:]
                i = slen
        # quotes
        else:
            i += 1
            start = i
            # find the ending quote, skipping over { }
            while i < slen:
                quote_i = s.find(quote, i)
                bracket_i = s.find('{', i)
                if quote_i == -1:
                    i = slen
                    break
                elif bracket_i == -1 or quote_i < bracket_i:
                    i = quote_i
                    break
                else:
                    inner, i = _next_closure(s, bracket_i + 1, '{', '}')
            val = s[start:i]
        val = val.strip()
        regex = ''
        special_nodes = []
        if val: # if there is no value, empty regex string won't be compiled
            nodes = _compile(val, False)
            prev_special = False
            # concatenate regexes
            for node in nodes:
                if node[0] == _TEXT:
                    regex += node[1]
                    prev_special = False
                elif node[0] != _TAG:
                    if prev_special:
                        special_nodes[-1].append(node)
                    else:
                        regex += '(.*)'
                        special_nodes.append([node])
                        prev_special = True
            if regex != '(.*)':
                regex = '(?:^|\s)' + regex + '(?:\s|$)' # match must be flush with whitespace or start/end
            if re_compile:
                regex = re.compile(regex, re.I)
        attrs[name] = (regex, special_nodes)
    return attrs
    
def _tag_skip(name):
    match = _tag_skip_re.search(name)
    if match:
        try:
            val = match.group(1)
            return name[:match.start()], -1 if val == 'last' else int(val)
        except ValueError:
            return name[:match.start()], 0
    return name, 0
    
def _make_start_tag_re(name, re_compile):
    regex = r'<\s*' + re.escape(name) + r'(?:\s+([^>]*?)|\s*)(/)?>'
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
def _make_end_tag_re(name, re_compile):
    regex = r'</\s*' + re.escape(name) + r'\s*>'
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
def _make_text_re(text, re_compile):
    regex = r'\s+'.join([re.escape(w) for w in text.split()])
    if re_compile:
        regex = re.compile(regex, re.I)
    return regex
    
    
# functions for running pattern nodes on html
# ---------------------------------------------------------------

def _match(nodes, html, i, captures, base_url, cookie_jar): # returns substring index after match, -1 if no match
    anchor_i = i
    special = []
    for node in nodes:
        # match text node
        if node[0] == _TEXT:
            m = node[1].search(html, i)
            if not m:
                return -1
            # run previous special nodes
            if not _run_special_nodes(special, html[anchor_i:m.start()], captures, base_url, cookie_jar):
                return -1
            special = []
            i = anchor_i = m.end()
        # match html tag
        elif node[0] == _TAG:
            if node[3] < 0:
                # backwards from last tag
                starts = []
                while True:
                    m = node[1].search(html, i)
                    if not m:
                        break
                    starts.append(m.start())
                    i = m.end()
                    if not m.group(2): # not standalone
                        body, i = _next_tag(html, i, node[1], node[2])
                i = starts[max(node[3], -len(starts))] # todo::::::::::::::::should throw -1 if not enough
            else:
                # skip forward
                for skip in range(node[3]):
                    m = node[1].search(html, i)
                    if not m:
                        return -1
                    i = m.end()
                    if not m.group(2): # not standalone
                        body, i = _next_tag(html, i, node[1], node[2])
            while True:
                # cycle through tags until all attributes match
                while True:
                    nested_captures = {}
                    m = node[1].search(html, i)
                    if not m:
                        return -1
                    i = m.end()
                    attrs = _parse_attrs(m.group(1) or '')
                    attrs_matched = _match_attrs(node[4], attrs, nested_captures, base_url, cookie_jar)
                    if attrs_matched == -1:
                        return -1
                    if attrs_matched:
                        break
                if m.group(2): # standalone tag
                    _merge_captures(captures, nested_captures)
                    break
                else: # make sure children match
                    body, i = _next_tag(html, i, node[1], node[2])
                    if _match(node[5], body, 0, nested_captures, base_url, cookie_jar) != -1:
                        _merge_captures(captures, nested_captures)
                        break
            # run previous special nodes
            if not _run_special_nodes(special, html[anchor_i:m.start()], captures, base_url, cookie_jar):
                return -1
            special = []
            anchor_i = i
        else:
            special.append(node)
    if not _run_special_nodes(special, html[i:], captures, base_url, cookie_jar):
        return -1
    return i
        
def _match_attrs(attr_nodes, attrs, captures, base_url, cookie_jar): # returns True/False, -1 if failed _run_special_node
    for name, attr_node in attr_nodes.items():
        if name not in attrs:
            return False
        if attr_node[0]: # if attr_node[0] is empty string, done matching
            if not attrs[name]: # bug fix added by AJS to deal with empty attribute
                return False # bug fix added by AJS to deal with empty attribute
            m = attr_node[0].match(attrs[name])
            if not m:
                return False
            # run regex captures over parallel list of special nodes
            for i, special_nodes in enumerate(attr_node[1]):
                for n in special_nodes:
                    if not _run_special_node(n, m.group(i+1), captures, base_url, cookie_jar):
                        return -1
    return True

def _run_special_nodes(nodes, s, captures, base_url, cookie_jar): # returns True/False
    for node in nodes:
        if not _run_special_node(node, s, captures, base_url, cookie_jar):
            return False
    return True
        
def _run_special_node(node, s, captures, base_url, cookie_jar): # returns True/False
    if node[0] == _CAPTURE:
        s = _apply_filters(s, node[2], base_url)
        _set_capture(captures, node[1], s)
    elif node[0] == _SCAN:
        i = 0
        while True:
            nested_captures = {}
            i = _match(node[1], s, i, nested_captures, base_url, cookie_jar)
            if i == -1:
                break
            else:
                _merge_captures(captures, nested_captures)
        # scan always ends with an usuccessful match, so fill in captures that weren't set
        _fill_captures(node[1], captures)
    elif node[0] == _GOTO:
        s = s.strip()
        if not s:
            return False
        new_url = _apply_filters(s, node[1] + ['abs'], base_url)
        new_html = fetch_html(new_url, cookie_jar=cookie_jar)
        if _match(node[2], new_html, 0, captures, new_url, cookie_jar) == -1:
            return False
    return True
    
def _set_capture(captures, name_parts, val, list_append=True):
    obj = captures
    last = len(name_parts) - 1
    for i, part in enumerate(name_parts):
        if i == last:
            new_obj = val
        else:
            new_obj = {}
        if type(part) == tuple:
            if part[0] not in obj:
                if list_append:
                    obj[part[0]] = [new_obj]
                else:
                    obj[part[0]] = []
                    break
            else:
                if type(obj[part[0]]) != list:
                    break
                if i == last or len(obj[part[0]]) == 0 or name_parts[i+1] in obj[part[0]][-1]:
                    if list_append:
                        obj[part[0]].append(new_obj)
                    else:
                        break
                else:
                    new_obj = obj[part[0]][-1]
        else:
            if part not in obj:
                obj[part] = new_obj
            else:
                new_obj = obj[part]
        obj = new_obj
        
def _merge_captures(master, slave):
    for name, val in slave.items():
        if name not in master:
            master[name] = val
        else:
            if type(val) == dict and type(master[name]) == dict:
                _merge_captures(master[name], val)
            elif type(val) == list and type(master[name]) == list:
                for e in val:
                    if type(e) == dict:
                        for n, v in e.items():
                            if len(master[name]) == 0 or type(master[name][-1]) != dict or n in master[name][-1]:
                                master[name].append({n: v})
                            else:
                                master[name][-1][n] = v
                    else:
                        master[name].append(e)
        
def _fill_captures(nodes, captures):
    for node in nodes:
        if node[0] == _TAG:
            _fill_captures(node[5], captures)
            for attr in node[4].values():
                for special_nodes in attr[1]:
                    _fill_captures(special_nodes, captures)
        elif node[0] == _CAPTURE:
            _set_capture(captures, node[1], _apply_filters(None, node[2], None), False)
        elif node[0] == _SCAN:
            _fill_captures(node[1], captures)
        elif node[0] == _GOTO:
            _fill_captures(node[2], captures)
        
def _apply_filters(s, filters, base_url):
    if 'html' not in filters and issubclass(type(s), basestring):
        s = _remove_html(s)
    for f in filters:
        if f == 'unescape':
            if issubclass(type(s), basestring):
                s = s.decode('string_escape')
        elif f == 'abs':
            if issubclass(type(s), basestring):
                s = urlparse.urljoin(base_url, s)
        elif f == 'int':
            try:
                s = int(s)
            except:
                s = 0
        elif f == 'float':
            try:
                s = float(s)
            except:
                s = 0.0
        elif f == 'bool':
            s = bool(s)
    return s
    
    
# html/text utilities
# ---------------------------------------------------------------

def _remove_comments(s):
    return _comment_re.sub('', s)

def _remove_html(s):
    s = _comment_re.sub('', s)
    s = _script_re.sub('', s)
    s = _tag_re.sub('', s)
    s = _space_re.sub(' ', s)
    s = _decode_entities(s)
    s = s.strip()
    return s
    
def _decode_entities(s):
    if type(s) is not unicode:
        s = unicode(s, 'utf-8', 'ignore')
        s = unicodedata.normalize('NFKD', s)
    return _entity_re.sub(_substitute_entity, s)
    
def _substitute_entity(m):
    ent = m.group(2)
    if m.group(1) == "#":
        return unichr(int(ent))
    else:
        cp = name2codepoint.get(ent)
        if cp:
            return unichr(cp)
        else:
            return m.group()
            
def _parse_attrs(s):
    attrs = {}
    for m in _attr_re.finditer(s):
        # next 4 lines are bug fix from Internet to deal with empty attributes AJS
        value = m.group(3)
        if value is None:
            value = m.group(4)
        attrs[m.group(1)] = value
        #attrs[m.group(1)] = m.group(3) or m.group(4)
    return attrs
    
def _next_tag(s, i, tag_open_re, tag_close_re, depth=1): # returns (tag body, substring index after tag)
    slen = len(s)
    start = i
    while i < slen:
        tag_open = tag_open_re.search(s, i)
        tag_close = tag_close_re.search(s, i)
        if not tag_close:
            i = len(s)
            break
        elif not tag_open or tag_close.start() < tag_open.start():
            i = tag_close.end()
            depth -= 1
            if depth == 0:
                return s[start:tag_close.start()], i
        else:
            if not (tag_open and tag_open.group(2)): # not a standalone tag
                depth += 1
            i = tag_open.end()
    return s[start:i], i

def _next_closure(s, i, left_str, right_str, depth=1): # returns (closure body, substring index after closure)
    slen = len(s)
    start = i
    while i < slen:
        left = s.find(left_str, i)
        right = s.find(right_str, i)
        if right == -1:
            i = len(s)
            break
        elif left == -1 or right < left:
            i = right + len(right_str)
            depth -= 1
            if depth == 0:
                return s[start:right], i
        else:
            depth += 1
            i = left + len(left_str)
    return s[start:i], i
    

#testing scrapemark feature to obtain adjacent special markup as follows:
# <a href='{{ variablename }}{@ subpattern @}'></a>
# which is documented on this page -> http://arshaw.com/scrapemark/docs/
# but which does not seem to work on scraperwiki
# this is because scraperwiki seems not to be using the released 0.9 version of scrapemark

#html = """<a href="http://www.google.co.uk"></a>"""
#target = """<a href="{{ variablename }}{@ <p>{{ subpattern }}</p> @}"></a>"""

#print scrape(target, html) # use scrapemark 0.9 code above - SUCCEEDS

#import scrapemark
#print scrapemark.scrape(target, html) # use scraperwiki version - FAILS

########################################




#util = scraperwiki.utils.swimport("utility_library")

# a library of utility functions

import scraperwiki
import lxml.html
import lxml.html.soupparser
from lxml import etree
import re
from datetime import date
import urllib, urllib2, urlparse
from datetime import datetime
from datetime import timedelta
import time
import json
import mechanize
from pytz import timezone
from BeautifulSoup import BeautifulSoup
#from BeautifulSoup import MinimalSoup
from cStringIO import StringIO
from csv import reader
import random
import cookielib
#import matplotlib.pyplot as pl
import base64
import sys
import cPickle

DATE_FORMAT = "%d/%m/%Y"
RFC822_DATE = "%a, %d %b %Y %H:%M:%S %z"
ISO8601_DATE = "%Y-%m-%d"
RFC3339_DATE = "%Y-%m-%dT%H:%M:%SZ"
TABLE_REGEX = re.compile(r'create\s+table\s+(\S+)\s*\(([^\)]+)\)', re.I) # ignore case
INDEX_REGEX = re.compile(r'(create\s+(?:unique\s+)?index)\s+(\S+)\s+on\s+(\S+)\s+\(([^\)]+)\)', re.I) # ignore case
TAGS_REGEX = re.compile(r'<[^<]+?>')
GAPS_REGEX = re.compile(r'\s+', re.U) # unicode spaces include html &nbsp;
TZ = timezone('Europe/London')
AUTHOR = 'AS' # for Atom feeds 
WEEKDAYS = { 'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6 }
DEFAULT_CACHE_AGE = 43200 # default cache expiry in secs = 12 hours
SLOT_TIME = 60 # max processing time for processing slots = secs
NUM_SLOTS = 2 # number of processes
CACHE = {} # local memory cache
    
all_rss_fields = { # default map from data fields to RSS, to be overridden
        'title': 'title',
        'description': 'description',
        'link': 'link',
        'items': 'items',
        'item': 'item',
        'sub_item': {
            'title': 'title',
            'description': 'description',
            'link': 'link',
            'guid': 'id',
            },
        'geo_item': {
            'point': 'point'
            }
        }

all_atom_fields = { # default map from data fields to ATOM, to be overridden
        'title': 'title',
        'subtitle': 'description',
        'link': 'link',
        'id': 'id',
        'items': 'items',
        'item': 'item',
        'sub_item': {
            'title': 'title',
            'content': 'description',
            'link': 'link',
            'id': 'id',
            },
        'geo_item': {
            'point': 'point'
            }
        }

# import a full CSV file into a table or if match is set, update the one row where the key values match
def import_csv(csv_file_url, table_name, keys, match = None): 
    if not keys or not isinstance(keys, list):
        return 0
    if not isinstance(keys, list):
        keys = [ keys ]
    if match and not isinstance(match, list):
        match = [ match ]
    # NB no-cache headers do not work
    #headers =  { 'Cache-Control': 'no-cache',  'Pragma': 'no-cache',  }
    # instead add random url string to short circuit cache
    nocache = "%04x" % random.randint(0, 65535)
    url = add_to_query(csv_file_url, { 'nocache': nocache })
    csv_text = scraperwiki.scrape(url)
    #response = get_response(csv_file_url, None, headers, 'text/csv')
    #csv_text = response.read()
    lines = reader(StringIO(csv_text))
    headings = lines.next()
    add_list = []
    if match:
        matchup = dict(zip(keys, match))
    else:
        matchup = None
    for line in lines:
        values = dict(zip(headings, line)) 
        if matchup:
            use_values = True
            for key in keys:
                if matchup[key] != values[key]:
                    use_values = False
                    break # exit the keys loop, match condition failed
            if use_values: # all keys matched
                add_list.append(values)
                break # key matched so no need to continue with lines loop
        else:
            add_list.append(values)
    if add_list: 
        if not matchup:
            scraperwiki.sqlite.execute("drop table if exists " + table_name)
            scraperwiki.sqlite.commit()
        scraperwiki.sqlite.save(keys, add_list, table_name, verbose=0) # one save operation (= list of dics), not many
    return len(add_list)

# set content type for JSON, XML or RSS formats
def set_content(fmt = 'xml'): 
    if fmt == 'json':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/json")
    elif fmt == 'jsonp':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/javascript")
    elif fmt == 'rss':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/rss+xml")
    elif fmt == 'atom':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/atom+xml")
    elif fmt == 'html':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/html")
    elif fmt == 'csv':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/csv")   
    elif fmt == 'tsv':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/tab-separated-values")   
    else: # XML always the default - see data_output()
        scraperwiki.utils.httpresponseheader("Content-Type", "text/xml")

# redirect to another web page
def redirect(url, code=303): 
    if code <= 307 and code >= 300:
        scraperwiki.utils.httpresponseheader("Location", url)
        scraperwiki.utils.httpstatuscode(code)
    else:
        scraperwiki.utils.httpresponseheader("Content-Type", "text/html")
        print """
        <html>
        <head>
        <meta http-equiv="Refresh" content="0; url=%s" />
        </head>
        <body>
        <p>Please follow this link: <a href="%s">%s</a>.</p>
        </body>
        </html>""" % (url, url, url)
    sys.exit()

# output a data dict in JSON, XML or RSS formats
def data_output(data, fmt = 'xml', options = None):
    if fmt == 'object':
        return data
    elif fmt == 'json':
        if options: # if this is set it's really JSONP
            return options + '(' + json.dumps(data, indent=4) + ');'
        else:
            return json.dumps(data, indent=4)
    elif fmt == 'jsonp':
        if not options: options = 'callback'
        return options + '(' + json.dumps(data, indent=4) + ');'
    elif fmt == 'rss':
        root = to_rss(data, options, ISO8601_DATE)
        root.addprevious(etree.PI('xml-stylesheet', 'type="text/xsl" title="XSL stylesheet" href="http://www.speakman.org.uk/rss.xsl"'))
        return etree.tostring(root.getroottree(), encoding="utf-8", xml_declaration=True, pretty_print=True)
    elif fmt == 'atom': 
        root = to_atom(data, options, ISO8601_DATE) 
        return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    elif fmt == 'html':
        if not options:
            options = 'data'
        html_string = to_html('', data, options)
        root = lxml.html.fromstring(html_string)
        return etree.tostring(root, pretty_print=True, method="html")
        #return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    else: # XML always the default - see set_content()
        if not options:
            options = 'root'
        root = to_xml(options, data)
        return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    
# use data to fill out an RSS 2.0 feed (with option for GeoRSS)
def to_rss(data, map, in_date_fmt = ISO8601_DATE):
    GEORSS_NAMESPACE = "http://www.georss.org/georss"
    GEORSS = "{%s}" % GEORSS_NAMESPACE
    NSMAP = { 'georss': GEORSS_NAMESPACE }
    feed_type = 'rss'
    for i in data[map['items']][map['item']]:
        for k, v in map['geo_item'].items():
            if v in i:
                feed_type = 'georss'
                break
    if feed_type == 'georss':
        root = etree.Element('rss', nsmap=NSMAP)
    else:
        root = etree.Element('rss')
    root.set("version", "2.0")
    branch = etree.SubElement(root, "channel")
    for k, v in map.items():
        if k <> 'item' and  k <> 'items' and k <> 'geo_item' and k <> 'sub_item' and v in data:
            twig = etree.SubElement(branch, k)
            twig.text = vstr(data[v])
    pubdate = datetime.now(TZ).strftime(RFC822_DATE)
    twig = etree.SubElement(branch, 'pubDate')
    twig.text = vstr(pubdate)
    for i in data[map['items']][map['item']]:
        twig = etree.SubElement(branch, "item")
        no_date = True
        for k, v in map['sub_item'].items():
            if v in i:
                leaf = etree.SubElement(twig, k)
                if k == 'pubDate':
                    no_date = False
                    if in_date_fmt ==  ISO8601_DATE:
                        leaf.text = convert_dt(vstr(i[v])+'T12:00:00Z', RFC3339_DATE, RFC822_DATE) #  make time noon
                    else:
                        leaf.text = convert_dt(vstr(i[v]), in_date_fmt, RFC822_DATE) 
                else:
                    leaf.text = vstr(i[v])
                if k == 'guid':
                    leaf.set("isPermaLink", "false")
        if no_date:
            leaf = etree.SubElement(twig, 'pubDate')
            leaf.text = vstr(pubdate)
        for k, v in map['geo_item'].items():
            if v in i:
                leaf = etree.SubElement(twig, GEORSS+k)
                leaf.text = vstr(i[v])
    return root

# use data to fill out an ATOM feed (with option for GeoRSS)
def to_atom(data, map, in_date_fmt = ISO8601_DATE):
    GEORSS_NAMESPACE = "http://www.georss.org/georss"
    ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
    GEORSS = "{%s}" % GEORSS_NAMESPACE
    GEONSMAP = { None: ATOM_NAMESPACE, 'georss': GEORSS_NAMESPACE }
    NSMAP = { None: ATOM_NAMESPACE }
    feed_type = 'atom'
    for i in data[map['items']][map['item']]:
        for k, v in map['geo_item'].items():
            if v in i:
                feed_type = 'georss'
                break
    if feed_type == 'georss':
        root = etree.Element('feed', nsmap=GEONSMAP)
    else:
        root = etree.Element('feed', nsmap=NSMAP)
    for k, v in map.items():
        if k <> 'item' and  k <> 'items' and k <> 'geo_item' and k <> 'sub_item' and v in data:
            branch = etree.SubElement(root, k)
            if k == 'link':
                branch.set("href", vstr(data[v]))
                branch.set("rel", "self")
            else:
                branch.text = vstr(data[v])
    pubdate = datetime.now(TZ).strftime(RFC3339_DATE)
    branch = etree.SubElement(root, 'updated')
    branch.text = vstr(pubdate)
    for i in data[map['items']][map['item']]:
        branch = etree.SubElement(root, "entry")
        no_date = True
        for k, v in map['sub_item'].items():
            if v in i:
                leaf = etree.SubElement(branch, k)
                if k == 'link':
                    leaf.set("href", vstr(i[v]))
                elif k == 'published' or k == 'updated':
                    no_date = False
                    if in_date_fmt ==  ISO8601_DATE:
                        leaf.text = convert_dt(vstr(i[v])+'T12:00:00Z', RFC3339_DATE, RFC3339_DATE) #  make time noon
                    else:
                        leaf.text = convert_dt(vstr(i[v]), in_date_fmt, RFC3339_DATE) 
                else:
                    leaf.text = vstr(i[v])
                if k == 'summary' or k == 'content':
                    leaf.set("type", "html")
        if no_date:
            leaf = etree.SubElement(branch, 'updated')
            leaf.text = vstr(pubdate)
        leaf = etree.SubElement(branch, 'author')
        #end = etree.SubElement(leaf, 'name')
        #end.text = vstr(AUTHOR)
        for k, v in map['geo_item'].items():
            if v in i:
                leaf = etree.SubElement(branch, GEORSS+k)
                leaf.text = vstr(i[v])
    return root

# unserialize an XML document to a dictionary (containing dicts, strings or lists)
def from_xml(element):
    if len(element) > 0:
        outdict = {}
        if element.get('type') == 'list':
            value = []
            for i in element:
                value.append(from_xml(i))
            outdict[element[0].tag] = value
        else:
            for i in element:
                outdict[i.tag] = from_xml(i)
        return outdict
    else:
        return element.text

# serialise the contents of a dictionary as simple XML
def to_xml(element_name, data):
    element_name = re.sub('\s', '_', element_name) # replace any spaces in the tag name with underscores
    element = etree.Element(element_name)
    if isinstance (data, dict):
        keys = data.keys()
        keys.sort() # output is in alphab order 
        for key in keys: # output simple string elements first
            if not isinstance(data[key], list) and not isinstance(data[key], dict):
                element.append(to_xml(key, data[key]))
        for key in keys: # any lists and dicts come afterwards
            if isinstance(data[key], list): # lists stay in original order
                element.set('type', 'list')
                for i in data[key]:
                    element.append(to_xml(key, i))
            elif isinstance(data[key], dict):
                element.append(to_xml(key, data[key]))
    else:
        element.text = vstr(data)
    return element

# serialise the contents of a dictionary as simple HTML (NB string output)
def to_html(container, data, title = ''):
    if title:
        title = re.sub('_', ' ', title) # replace any underscores with spaces
        title = title.title()
    if not container:
        output = "<html><head>"
        if title:
            output = output+"<title>"+title+"</title>"
        output = output+'</head><body>'
        if title:
            output = output+"<h1>"+title+"</h1>"
        output = output+to_html('body', data)
        return output+"</body></html>"
    elif isinstance (data, dict):
        output = ''
        if title:
            output = output+'<h2>'+title+'</h2>'
        list_strings = []
        list_structs = []
        keys = data.keys()
        for key in keys: # separate simple string elements from rest
            if isinstance(data[key], list) or isinstance(data[key], dict):
                list_structs.append(key)
            else:
                list_strings.append(key)
        if list_strings:
            list_strings.sort()
            output = output+'<ul>'
            for key in list_strings: # output simple string elements first
                output = output+to_html('ul', data[key], key)
            output = output+'</ul>'
        if list_structs:
            list_structs.sort()
            for key in list_structs: # output list and dict elements next
                output = output+to_html('body', data[key], key)
        return output
    elif isinstance (data, list):
        output = ''
        db_table = False
        if len(data) >= 1 and isinstance(data[0], dict):
            headers = data[0].keys()
            db_table = True
            test_len = len(headers)
            for i in data:
                if not isinstance(i, dict) or len(i) <> test_len:
                    db_table = False
                    break
        else:
            db_table = False
        if db_table:
            headers.sort()
            output = output+'<table><tr>'
            for i in headers:
                output = output+to_html('tr1', i)
            output = output+'</tr>'
            for i in data:
                output = output+'<tr>'
                for j in headers:
                    output = output+to_html('tr', i[j])
                output = output+'</tr>'
            return output+'</table>'
        else:
            if title:
                output = output+'<h2>'+title+'</h2>'
            output = output+'<ul>'
            for i in data:
                output = output+to_html('ul', i)
            return output+'</ul>'
    else:
        output = ''
        if container == 'body':
            if title:
                output = output+'<h3>'+title+'</h3>'
            return output+vstr(data)
        elif container == 'dl':
            if title:
                output = output+'<dt>'+title+'</dt>'
            return output+'<dd>'+vstr(data)+'</dd>'
        elif container == 'tr':
            output = output+'<td>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</td>'
        elif container == 'tr1':
            output = output+'<th>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</th>'
        elif container == 'ul':
            output = output+'<li>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</li>'

# return valid string/unicode if not null, otherwise empty string
def vstr(s):
    if s:
        try:
            return unicode(s)
        except UnicodeDecodeError:
            return str(s)
    else:
        return u''

# remove any non ascii characters
def ascii(s): return "".join(i for i in s if ord(i)<128)

# add new data elements to the existing query of a URL
def add_to_query(url, data = {}):
    u = urlparse.urlsplit(url)
    qdict = dict(urlparse.parse_qsl(u.query))
    qdict.update(data)
    query = urllib.urlencode(qdict)
    url = urlparse.urlunsplit((u.scheme, u.netloc, u.path, query, u.fragment))
    return url

# get a date in standard format or None if the string cannot be parsed
def get_dt(date_string, date_format=DATE_FORMAT):
    try:
        dt = datetime.strptime(date_string, date_format)
        return dt.date()
    except:
        return None

# convert a date string from one format to another
def convert_dt(date_string, in_date_format=DATE_FORMAT, out_date_format=RFC822_DATE, on_error_original=True):
    if on_error_original and in_date_format == out_date_format:
        return date_string
    else:
        try:
            dt = datetime.strptime(date_string, in_date_format)
            dt = dt.replace(tzinfo=TZ)
            return dt.strftime(out_date_format)
        except:
            if on_error_original:
                return date_string
            else:
                return None

# increment a date by a number OR to the next available weekday if a string
# return the start and end dates of the permissible range
def inc_dt(date_string, date_format=DATE_FORMAT, increment=1):
    try:
        start_dt = datetime.strptime(date_string, date_format)
        if not increment:
            increment = 0
        if isinstance(increment, int) or increment.isdigit() or (increment.startswith('-') and increment[1:].isdigit()):
            day_inc = int(increment)
            if day_inc < 0:
                end_dt = start_dt
                start_dt = end_dt + timedelta(days=day_inc)
            else:
                end_dt = start_dt + timedelta(days=day_inc)
        elif increment == 'Year':
            start_dt = date(start_dt.year, 1, 1) # first day of this year
            end_dt = date(start_dt.year, 12, 31) # last day of this year
        elif increment == 'Month': 
            start_dt = date(start_dt.year, start_dt.month, 1) # first day of this month
            if start_dt.month == 12:
                end_dt = date(start_dt.year+1, 1, 1) # first day of next year
            else:
                end_dt = date(start_dt.year, start_dt.month+1, 1) # first day of next month
            end_dt = end_dt - timedelta(days=1)
        elif increment.startswith('-'): 
            wday = WEEKDAYS.get(increment[1:4].capitalize(), 0) # supplied is a week day defining beginning of week for a weekly list
            day_inc = wday - start_dt.weekday()
            if day_inc > 0: 
                day_inc = day_inc - 7
            start_dt = start_dt + timedelta(days=day_inc)
            end_dt = start_dt + timedelta(days=6)
        else:
            wday = WEEKDAYS.get(increment[0:3].capitalize(), 6) # supplied is a week day defining end of week for a weekly list
            day_inc = wday - start_dt.weekday()
            if day_inc < 0:
                day_inc = day_inc + 7
            end_dt = start_dt + timedelta(days=day_inc)
            start_dt = end_dt - timedelta(days=6)
        return start_dt.strftime(date_format), end_dt.strftime(date_format)
    except:
        return date_string, date_string

# test if a date is within a permissible range
def match_dt(date_to_test, date_from, date_to, date_format=DATE_FORMAT):
    try:
        test_dt = datetime.strptime(date_to_test, date_format)
        from_dt = datetime.strptime(date_from, date_format)
        to_dt = datetime.strptime(date_to, date_format)
        if test_dt <= to_dt and test_dt >= from_dt:
            return True
        else:
            return False
    except:
        return False

# test if a date is before or after a reference date
def test_dt(date_to_test, ref_date, date_format=DATE_FORMAT):
    try:
        test_dt = datetime.strptime(date_to_test, date_format)
        ref_dt = datetime.strptime(ref_date, date_format)
        if test_dt > ref_dt:
            return 1
        elif test_dt < ref_dt:
            return -1
        elif test_dt == ref_dt:
            return 0
        else:
            return None
    except:
        return None

# get a response from a url
def get_response(url, data = None, headers = None, accept = 'text/html', timeout = None):
    request = urllib2.Request(url)
    request.add_header('Accept', accept)
    if headers:
        for k, v in headers.items():
            request.add_header(k, v)
    """if multipart:
        opener = urllib2.build_opener(MultipartPostHandler)
        if timeout:
            response = opener.open(request, data, timeout)
        else:
            response = opener.open(request, data)
    else:
    """
    if timeout:
        response = urllib2.urlopen(request, data, timeout)
    else:
        response = urllib2.urlopen(request, data)
    return response

# get JSON data from a url
def json_get(url, data = None, timeout = None):
    try:
        sf = urllib2.urlopen(url, data, timeout)
        result = json.load(sf)  
    except:
        result = None; sf = None
    finally:
        if sf: sf.close()
    return result

# put a cookie in the jar
def set_cookie(cookie_jar, cname, cvalue, cdomain=None, cpath='/'):
    ck = cookielib.Cookie(version=0, name=str(cname), value=str(cvalue), domain=cdomain, path=cpath, 
            port=None, port_specified=False, domain_specified=False, expires=None, 
            domain_initial_dot=False, path_specified=True, secure=False, 
            discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
    cookie_jar.set_cookie(ck)

# gets a mechanize browser 
# NB the internal handler contains an lxml Html Element that can be used for DOM based methods
def get_browser(headers = None, factory = '', proxy = ''):
    if factory == 'robust':
        br = mechanize.Browser(factory=mechanize.RobustFactory()) # using BeautifulSoup 2 parser
    elif factory == 'xhtml':
        br = mechanize.Browser(factory=mechanize.DefaultFactory(i_want_broken_xhtml_support=True))
    else:
        br = mechanize.Browser()

    cj = cookielib.LWPCookieJar()
    br.set_cookiejar(cj)

    if proxy:
        # see http://www.publicproxyservers.com/proxy/list_uptime1.html
        br.set_proxies({"https": proxy, "http": proxy}) 
        # https tunnel via http proxy not working - bug fixed below but same problem?
        # http://sourceforge.net/mailarchive/forum.php?thread_name=alpine.DEB.2.00.0910062211230.8646%40alice&forum_name=wwwsearch-general
    br.set_handle_robots(False)
    if headers: 
        br.addheaders = headers.items() # Note addheaders is a data object (list of tuples) not a method
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    handler = EtreeHandler()
    br.add_handler(handler)
    return br, handler, cj

# selects a form and sets up its fields, action, method etc
# in the case of HTML select tags, the particular control used is always selected by name
# e.g. <select name="name"> <option value="value"> label </option> </select>
# however the option selected can be via the value attribute or by label (if the key starts with #)
# controls can be disabled by setting them to None
def setup_form(br, form = None, fields = None, action = None, method = None):
    if not form:
        br.select_form(nr=0)
    elif form.isdigit():
        br.select_form(nr=int(form))
    else:
        br.select_form(name=form)
    if action:
        current_action = br.form.action
        new_action = urlparse.urljoin(current_action, action)
        br.form.action = new_action
    if method and method.upper() == 'GET':
        br.form.method = method
    #print br.form
    if fields:
        add_controls = []
        for k, v in fields.items():
            try:
                if k.startswith('#'):
                    control = br.find_control(name=k[1:], nr=0) # find first control named k
                else:
                    control = br.find_control(name=k, nr=0) # find first control named k
            except mechanize._form.ControlNotFoundError as e: # if the control does not exist, we create a dummy hidden control to hold the value
                if k.startswith('#'):
                    add_controls.append(k[1:])
                else:
                    add_controls.append(k)
        if add_controls:
            for k in add_controls:
                br.form.new_control('hidden', k, {'value':''} )
            br.form.fixup()
        br.form.set_all_readonly(False)
        for k, v in fields.items():
            if k.startswith('#'): # used to set a named control using option label
                control = br.find_control(name=k[1:], nr=0) # find first control named k
                if v is None:
                    control.disabled = True
                elif isinstance(v, list):
                    if control.disabled: control.disabled = False
                    for i in v:
                        control.get(label=i, nr=0).selected = True # set the value by selecting its label (v[i])
                else:
                    if control.disabled: control.disabled = False
                    control.get(label=v, nr=0).selected = True # set the value by selecting its label (v)
                    # NB label matches any white space compressed sub string so there is potential for ambiguity errors
            else:
                #br[k] = v # default is to directly assign the named control a value (v)
                control = br.find_control(name=k, nr=0) # find first control named k
                if v is None:
                    control.disabled = True
                elif (control.type == 'radio' or control.type == 'checkbox' or control.type == 'select') and not isinstance (v, list):
                    if control.disabled: control.disabled = False
                    control.value = [ v ]
                elif (control.type != 'radio' and control.type != 'checkbox' and control.type != 'select') and v and isinstance (v, list):
                    if control.disabled: control.disabled = False
                    control.value = v [0]
                else:
                    if control.disabled: control.disabled = False
                    control.value = v
        # NB throws except mechanize._form.ItemNotFoundError as e: if field select/check/radio option does not exist


# returns response after submitting a form via a mechanize browser
# submit parameter is a submit control name/number or an id (if it starts with a '#')
def submit_form(br, submit = None):
    if not submit:
        response = br.submit()
    elif submit.isdigit():
        response = br.submit(nr=int(submit))
    elif submit.startswith('#'):
        control = br.find_control(id=submit[1:], nr=0) # find first control with id submit
        if control.disabled: control.disabled = False
        response = br.submit(id=submit[1:], nr=0)
    else:
        control = br.find_control(name=submit, nr=0) # find first control named submit
        if control.disabled: control.disabled = False
        response = br.submit(name=submit, nr=0)
    return response

# returns a response after following a link via a mechanize browser
# link paramter is a link text value or number or a name (if it starts with a '!')
def process_link(br, link = None):
    if not link:
        response = br.follow_link()
    elif link.isdigit():
        response = br.follow_link(nr=int(link))
    elif link.startswith('!'):
        response = br.follow_link(name=str(link[1:]))
    else:
        response = br.follow_link(text=str(link))
    return response

# makes a direct url request via the browser supplying GET or POST parameters
def open_url(br, url, data = None, method = None):
    if data:
        for k, v in data.items():
            if v and isinstance(v, list):
                data[k] = v[0]
    else:
        return br.open(url)
    if method and method.upper() == 'GET':
        url = add_to_query(url, data)
        return br.open(url)
    else:
        return br.open(url, urllib.urlencode(data))

# return an HTML Element document from an html string
def get_doc(raw_html, url = ''):
    doc = lxml.html.fromstring(raw_html) # lxml fast parser
    if url:
        doc.make_links_absolute(url)
    return doc

# return an XML Element document from an xml string
def get_doc_xml(raw_xml):
    doc = etree.fromstring(raw_xml)
    return doc

# returns a child dictionary updated with any missing values specified in its parents
def dict_inherited(container, child_name, parent_key = 'parent'):
    child_dict = {}
    if child_name in container:
        child_dict.update(container[child_name])
        while child_dict.get(parent_key):
            next_dict = container[child_dict[parent_key]]
            del child_dict[parent_key]
            for k, v in next_dict.items():
                if not child_dict.get(k):
                    child_dict[k] = v
                elif child_dict[k] == '__None__':
                    child_dict[k] = None
                elif child_dict[k] == '__Clear__':
                    del child_dict[k]
    return child_dict 

# return the text value of an xpath or cssselect expression
def xpath_text(element, expression, thistype='xpath'):
    if element is None or not expression:
            return ''
    if thistype == 'css':
        value = element.cssselect(expression)
    else:
        value = element.xpath(expression)
    return text_content(value)
        
# returns trimmed html content with tags removed, entities converted
def text_content(value):
    if value is None:
        return ''
    if isinstance (value, list):
        if len(value) > 0:
            value = value[0]
        else:
            return ''
    if isinstance (value, lxml.html.HtmlElement):
        text = lxml.html.tostring(value)
        text = TAGS_REGEX.sub(' ', text) # replace any html tag content with spaces
        # use beautiful soup to convert html entities to unicode strings
        text = BeautifulSoup(text, convertEntities="html").contents[0].string
    else:
        text = vstr(value)
        text = TAGS_REGEX.sub(' ', text) # replace any html tag content with spaces
        # use beautiful soup to convert html entities to unicode strings
        text = BeautifulSoup(text, convertEntities="html").contents[0].string
    return trim(text)
    
# return text with internal white space compressed and external space stripped off
def trim(text):
    str_trim = GAPS_REGEX.sub(' ', text) # replace internal gaps with single spaces
    return str_trim.strip() # remove space at left and right

# return text with all internal white space removed
def no_space(text):
    return GAPS_REGEX.sub('', text) # remove internal gaps

#get selected table fields from database as list of maps
def get_table_vals(table = '', fields = '', where = '', orderetc = ''):
    if not fields:
        sql_fields = '*'
    elif isinstance(fields, list):
        sql_fields = ",".join(fields)
    elif isinstance(fields, dict):
        sql_fields = ''
        for k, v in fields.items():
            sql_fields = sql_fields+","+v+" as "+k
        sql_fields = sql_fields[1:]
    else:
        sql_fields = fields
    if where:
        where = " where "+where+' '+orderetc
    else:
        where = ' '+orderetc
    return scraperwiki.sqlite.select(sql_fields+" from "+table+where)

#convert list of maps resulting from SQL query to keyed dictionary (alternatively source is a table name)
def get_map(source, key, value=None):
    data = {}
    if not isinstance(source, list):
        source = get_table_vals(source)
    for map in source:
        if value:
            data[map[key]] = map[value]
        else:
            data[map[key]] = map
    return data

#convert list of maps resulting from SQL query to simple list (alternatively source is a table name)
def get_list(source, key):
    data = []
    if not isinstance(source, list):
        source = get_table_vals(source)
    for map in source:
        if map.get(key):
            data.append(map[key])
    return data 

# replace matching values with a substitution string in a single table column
# if no replace type is specified, it just prints the number of matching rows
def replace_vals(table, field, match, subst, replace_type= '', confirm = None):
    match = match.replace("'", "''")
    if replace_type.lower() == 'prefix':
        where = " where "+field+" like '"+match+"%'"
    elif replace_type.lower() == 'suffix':
        where = " where "+field+" like '%"+match+"'"
    else:
        where = " where "+field+" like '%"+match+"%'"
    subst = subst.replace("'", "''")
    if replace_type.lower() == 'prefix':
        where2 = " where "+field+" like '"+subst+"%'"
    elif replace_type.lower() == 'suffix':
        where2 = " where "+field+" like '%"+subst+"'"
    else:
        where2 = " where "+field+" like '%"+subst+"%'"
    sql = "select count(*) from "+table+where
    result1 = scraperwiki.sqlite.execute(sql)
    sql = "select count(*) from "+table+where2
    result2 = scraperwiki.sqlite.execute(sql)
    print "Found %d match strings and %d substitution strings before replacement" % (result1['data'][0][0], result2['data'][0][0])
    if confirm:
        sql = "update "+table+" set "+field+" = replace ("+field+", '"+match+"', '"+subst+"')"+where
        scraperwiki.sqlite.execute(sql)
        scraperwiki.sqlite.commit()
        sql = "select count(*) from "+table+where
        result1 = scraperwiki.sqlite.execute(sql)
        sql = "select count(*) from "+table+where2
        result2 = scraperwiki.sqlite.execute(sql)
        print "Found %d match strings and %d substitution strings after replacement" % (result1['data'][0][0], result2['data'][0][0])
    else:
        print "No substitutions made"

# list distinct URL prefixes in a field
def list_url_prefixes(table, field = 'url'):
    dump = get_list(table, field)
    prefixes = []
    for i in dump:
        parsed = urlparse.urlparse(i)
        prefix = 'http://' + parsed.netloc + parsed.path
        if prefix not in prefixes:
            prefixes.append(prefix)
    print "Distinct URL prefixes found in the '" + field + "' field of the " + table + " table:"
    for p in prefixes:
        print p

# set map values in a database table NB stores values as unicode strings
def set_table_vals(table, map, where = ''):
    clause = ''
    for k, v in map.items():
        if v:
            store = vstr(v).replace("'", "''")
            clause = clause+', '+k+"='"+store+"'"
        else:
            clause = clause+', '+k+"=''"
    clause = clause[2:]
    if where:
        where = " where "+where
    else:
        where = ''
    scraperwiki.sqlite.execute("update "+table+" set "+clause+where)
    scraperwiki.sqlite.commit()

# return a simple list of database table columns
def get_table_cols(table):
    result = scraperwiki.sqlite.execute("select * from "+table+" limit 1")
    return result['keys']

# return columns for a table - new version returns dict of columns with constraints as values
def get_table_columns(table='swdata'):
    schemas = scraperwiki.sqlite.select("sql from sqlite_master where type='table' and name='"+table+"'")
    columns = {}
    for schema in schemas:
        table_match = TABLE_REGEX.search(schema['sql'].replace('`', ''))
        if table_match:
            if table_match.group(1) == table:
                fields = table_match.group(2).split(',')
                for field in fields:
                    parts = field.split()
                    column = parts[0]
                    if len(parts) > 0:
                        columns[column] = ' '.join(parts[1:])
                    else:
                        columns[column] = ''
                break
    return columns

# get a create table schema
def create_table_schema(columns, table='swdata'):
    if not columns:
        return None
    elif isinstance(columns, dict):
        fields = []
        for k, v in columns.items():
            fields.append("`" + k + "` " + v)
        return "create table `" + table + "` (" + ', '.join(fields) + ')'
    elif isinstance(columns, list):
        return "create table `" + table + "` (" + ', '.join(columns) + ')'
    else:
        return None

# get a create index schema
def create_index_schemas(indices, table='swdata'):
    if indices and isinstance(indices, dict):
        results = []
        for k, v in indices.items():
            if v['unique']:
                create = 'create unique index '
            else:
                create = 'create index '
            results.append(create + v['name'] + " on " + table + " (" + k + ")")
        return results
    else:
        return []

# return column indexes for a table - returns dict of indexed columns with name and whether unique as values
def get_table_indices(table='swdata'):
    schemas = scraperwiki.sqlite.select("sql from sqlite_master where type='index' and tbl_name='"+table+"'")
    indices = {}
    for schema in schemas:
        index_match = INDEX_REGEX.search(schema['sql'].replace('`', ''))
        if index_match:
            if index_match.group(3) == table:
                unique = False
                if 'unique' in index_match.group(1).lower(): unique = True
                result = { 'name': index_match.group(2), 'unique': unique }
                indices[index_match.group(4)] = result
    return indices

# adds column(s) to a database table if found not to exist
def update_columns(table, columns, constraint = 'text'):
    existing = get_table_columns(table)
    if not constraint: constraint = ''
    if isinstance(columns, list):
        for col in columns:
            if not col in existing.keys():
                scraperwiki.sqlite.execute("alter table "+table+" add column "+col+" "+constraint)
                scraperwiki.sqlite.commit()
    elif isinstance(columns, str) or isinstance(columns, unicode):
        if not columns in existing.keys():
                scraperwiki.sqlite.execute("alter table "+table+" add column "+columns+" "+constraint)
                scraperwiki.sqlite.commit()

# renames a column by copying data to a temp table and renaming
# note if new _column is null or empty the column is deleted
def rename_column(table, column, new_column, temp_table = 'temp_copy'):
    scraperwiki.sqlite.execute("drop table if exists "+temp_table)
    columns = get_table_columns(table)
    #print columns
    if not column in columns.keys(): return
    old_fields = []; new_fields = []; # note array used because order is important
    for k, v in columns.items():
        if k == column:
            del columns[column]
            if new_column:
                columns[new_column] = v
                new_fields.append(new_column)
                old_fields.append(column)
        else:
            new_fields.append(k)
            old_fields.append(k)
    sql_new_schema = create_table_schema(columns, temp_table)
    #print sql_new_schema
    scraperwiki.sqlite.execute(sql_new_schema)
    index_schemas = get_table_indices(table) # save index details before rename
    new_index_schemas = {}
    for k, v in index_schemas.items(): # filter out non-applicable indices
        field_list = k.split(',')
        new_field_list = []
        for field in field_list:
            if field == column:
                if new_column: 
                    new_field_list.append(new_column)
            else:
                new_field_list.append(field)
        if new_field_list:
            new_index_schemas[', '.join(new_field_list)] = v
    #print new_index_schemas
    sql_index_schemas = create_index_schemas(new_index_schemas, table)
    #print sql_index_schemas
    insert = "insert into "+temp_table+" ("+", ".join(new_fields)+") select "+", ".join(old_fields)+" from "+table
    #print insert
    scraperwiki.sqlite.execute(insert)
    scraperwiki.sqlite.execute("drop table "+table) # deletes associated indexes
    scraperwiki.sqlite.execute("alter table " + temp_table + " rename to " + table)
    for sql in sql_index_schemas: # re-apply indices
        scraperwiki.sqlite.execute(sql)
    scraperwiki.sqlite.commit()

# query the database cache table
def cache_fetch(key):
    tstamp = time.time()
    #if isinstance(key, dict):
    #    key = hash(tuple(sorted(key.iteritems())))
    #elif isinstance(key, list):
    #    key = hash(tuple(key))
    #else:
    #    key = hash(key)
    ser_key = cPickle.dumps(key)
    try:
        sql = "value from cache where key = '" + ser_key.replace("'", "''") + "' and expires >= " + str(tstamp)
        results = scraperwiki.sqlite.select(sql)
    except:
        results = None
    if results:
        return cPickle.loads(str(results[0]['value']))
    else:
        return None

# clear the database cache table
def cache_clear():
    scraperwiki.sqlite.execute("delete from cache")
    scraperwiki.sqlite.commit()

# insert a value in the database cache table
# this is a slow operation, so we also take the opportunity to clear stale cache entries
def cache_put(key, value, age = DEFAULT_CACHE_AGE): # default expiry in 12 hours
    tstamp = time.time()
    try:
        scraperwiki.sqlite.execute("delete from cache where expires < "+str(tstamp))
        scraperwiki.sqlite.commit()
    except:
        pass
    if age and age > 0:
        expires = tstamp + age
    else:
        expires = tstamp + DEFAULT_CACHE_AGE
    #if isinstance(key, dict):
    #    key = hash(tuple(sorted(key.iteritems())))
    #elif isinstance(key, list):
    #    key = hash(tuple(key))
    #else:
    #    key = hash(key)
    store = { 'key': cPickle.dumps(key), 'value': cPickle.dumps(value), 'expires': expires }
    scraperwiki.sqlite.save(unique_keys=['key'], data=store, table_name='cache', verbose=0)

# get a processing slot
def get_slot(num_slots = NUM_SLOTS, slot_time = SLOT_TIME):
    timestamp = time.time()
    next_free_slot = slot_time
    for i in range(0, num_slots):
        slot_name = "slot" + str(i)
        slot_expires = scraperwiki.sqlite.get_var(slot_name, 0)
        if not slot_expires or slot_expires < timestamp:
            scraperwiki.sqlite.save_var(slot_name, timestamp + slot_time) # we have the lock, so just block it for the next slot_time secs
            return i, slot_time
        else:
            this_expires = slot_expires - timestamp
            if this_expires > 0 and this_expires < next_free_slot: 
                next_free_slot = this_expires
    return -1, next_free_slot # time until next available slot is free

# free up a processing slot
def free_slot(slot_num):
    slot_name = "slot" + str(slot_num)
    scraperwiki.sqlite.save_var(slot_name, 0)

# put an item into the local memory cache
# make copy, otherwise the cached version is mutable
def mcache_put(key, value):
    if isinstance(key, dict):
        keyhash = hash(tuple(sorted(key.iteritems())))
    elif isinstance(key, list):
        keyhash = hash(tuple(key))
    else:
        keyhash = hash(key)
    CACHE[keyhash] = copy.deepcopy(value)

# get an item from the local memory cache
# make copy, otherwise the cached version is mutable
def mcache_fetch(key):
    if isinstance(key, dict):
        keyhash = hash(tuple(sorted(key.iteritems())))
    elif isinstance(key, list):
        keyhash = hash(tuple(key))
    else:
        keyhash = hash(key)
    return copy.deepcopy(CACHE.get(keyhash))


def base_css():
    css = """
body {
    margin: 10 20;
    padding: 0;
    background: #FFF;
    color: #191919;
    font-weight: normal;
    font-family: Helvetica, Arial, sans-serif;
    font-size: 75%;
}
    /*------------------- HEADERS -------------------*/
h1, h2, h3, h4, h5, h6 {
  margin: 6px 0;
  padding: 0;
  font-weight: normal;
  font-family: Helvetica, Arial, sans-serif;
}

h1 {font-size: 2em;}
h2 {font-size: 1.8em; line-height: 1.8em;}
h3 {font-size: 1.6em;}
h4 {font-size: 1.4em;}
h5 {font-size: 1.2em;}
h6 {font-size: 1em;}
/*------------------- HEADERS -------------------*/

/*------------------- TEXT/LINKS/IMG -------------------*/
p {margin: 10px 0 18px; padding: 10px;}

em {font-style:italic;}

strong {font-weight:bold;}

a:link, a:visited {color: #027AC6; text-decoration: none; outline:none;}

a:hover {color: #0062A0; text-decoration: underline;}

a:active, a.active {color: #5895be;}

img, a img {border: none;}

abbr,acronym {
    /*indicating to users that more info is available */
    border-bottom:1px dotted #000;
    cursor:help;
}

/*------------------- TEXT/LINKS/IMG -------------------*/

hr {
  margin: 0;
  padding: 0;
  border: none;
  height: 1px;
  background: #5294c1;
}

/*Change in format*/
ul, blockquote, quote, code, fieldset {margin: 16px 0;}

pre {  padding: 0; margin: 0; font-size: 1.3em; 
    white-space: -moz-pre-wrap !important; /* Mozilla, supported since 1999 */
    white-space: -pre-wrap; /* Opera 4 - 6 */
    white-space: -o-pre-wrap; /* Opera 7 */
    white-space: pre-wrap; /* CSS3 */
    word-wrap: break-word; /* IE 5.5+ */
}


/*------------------- LISTS -------------------*/

ul {margin-left:32px;}

ol,ul,dl {margin-left:32px;}
ol, ul, dl {margin-left:32px;}
ul, ol {margin: 8px 0 16px; padding: 0;}
ol li, ul li {margin: 7px 0 7px 32px;}
ul ul li {margin-left: 10px;}

ul li {padding: 0 0 4px 6px; list-style: disc outside;}
ul li ul li {list-style: circle outside;}

ol li {padding: 0 0 5px; list-style: decimal outside;}

dl {margin: 8px 0 16px 24px;}
dl dt {font-weight:bold;}
dl dd {margin: 0 0 8px 20px;}

/*------------------- LISTS -------------------*/


/*------------------- FORMS -------------------*/
input {
  font: 1em/1.2em Verdana, sans-serif;
  color: #191919;
}
textarea, select {
  font: 1em/1.2em Verdana, sans-serif;
  color: #191919;
}
textarea {resize:none;}
/*------------------- FORMS -------------------*/


/*------------------- TABLES -------------------*/

table {margin: 16px 0; width: 90%; font-size: 0.92em; border-collapse:collapse; }

th {
  border:1px solid #000; 
  background-color: #d3e7f4;
  font-weight: bold;
}

td {padding: 4px 6px; margin: 0; border:1px solid #000;}

caption {margin-bottom:8px; text-align:center;}

/*------------------- TABLES -------------------*/
    """
    return css

"""
class MinimalSoupHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            soup = MinimalSoup (response.get_data())
            response.set_data(soup.prettify())
        return response
"""

class BeautifulSoupHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            #soup = BeautifulSoup (response.get_data())
            self.element = lxml.html.soupparser.fromstring(response.get_data())
            #response.set_data(soup.prettify())
            response.set_data(etree.tostring(self.element, pretty_print=True, method="html"))
        return response

class EtreeHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            #clean_up = lxml.html.clean.clean_html(response.get_data()) # not tested yet ? put in new EtreeCleanHandler
            #self.element = etree.HTML(response.get_data())
            tag_soup = response.get_data()
            try:
                self.element = lxml.html.fromstring(tag_soup)
                ignore = etree.tostring(self.element, encoding=unicode) # check the unicode entity conversion has worked
            except (UnicodeDecodeError, etree.XMLSyntaxError):
                self.element = lxml.html.soupparser.fromstring(tag_soup) # fall back to beautiful soup if there is an error    
            response.set_data(etree.tostring(self.element, pretty_print=True, method="html"))      
        return response


# a library of utility functions

import scraperwiki
import lxml.html
import lxml.html.soupparser
from lxml import etree
import re
from datetime import date
import urllib, urllib2, urlparse
from datetime import datetime
from datetime import timedelta
import time
import json
import mechanize
from pytz import timezone
from BeautifulSoup import BeautifulSoup
#from BeautifulSoup import MinimalSoup
from cStringIO import StringIO
from csv import reader
import random
import cookielib
#import matplotlib.pyplot as pl
import base64
import sys
import cPickle

DATE_FORMAT = "%d/%m/%Y"
RFC822_DATE = "%a, %d %b %Y %H:%M:%S %z"
ISO8601_DATE = "%Y-%m-%d"
RFC3339_DATE = "%Y-%m-%dT%H:%M:%SZ"
TABLE_REGEX = re.compile(r'create\s+table\s+(\S+)\s*\(([^\)]+)\)', re.I) # ignore case
INDEX_REGEX = re.compile(r'(create\s+(?:unique\s+)?index)\s+(\S+)\s+on\s+(\S+)\s+\(([^\)]+)\)', re.I) # ignore case
TAGS_REGEX = re.compile(r'<[^<]+?>')
GAPS_REGEX = re.compile(r'\s+', re.U) # unicode spaces include html &nbsp;
TZ = timezone('Europe/London')
AUTHOR = 'AS' # for Atom feeds 
WEEKDAYS = { 'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6 }
DEFAULT_CACHE_AGE = 43200 # default cache expiry in secs = 12 hours
SLOT_TIME = 60 # max processing time for processing slots = secs
NUM_SLOTS = 2 # number of processes
CACHE = {} # local memory cache
    
all_rss_fields = { # default map from data fields to RSS, to be overridden
        'title': 'title',
        'description': 'description',
        'link': 'link',
        'items': 'items',
        'item': 'item',
        'sub_item': {
            'title': 'title',
            'description': 'description',
            'link': 'link',
            'guid': 'id',
            },
        'geo_item': {
            'point': 'point'
            }
        }

all_atom_fields = { # default map from data fields to ATOM, to be overridden
        'title': 'title',
        'subtitle': 'description',
        'link': 'link',
        'id': 'id',
        'items': 'items',
        'item': 'item',
        'sub_item': {
            'title': 'title',
            'content': 'description',
            'link': 'link',
            'id': 'id',
            },
        'geo_item': {
            'point': 'point'
            }
        }

# import a full CSV file into a table or if match is set, update the one row where the key values match
def import_csv(csv_file_url, table_name, keys, match = None): 
    if not keys or not isinstance(keys, list):
        return 0
    if not isinstance(keys, list):
        keys = [ keys ]
    if match and not isinstance(match, list):
        match = [ match ]
    # NB no-cache headers do not work
    #headers =  { 'Cache-Control': 'no-cache',  'Pragma': 'no-cache',  }
    # instead add random url string to short circuit cache
    nocache = "%04x" % random.randint(0, 65535)
    url = add_to_query(csv_file_url, { 'nocache': nocache })
    csv_text = scraperwiki.scrape(url)
    #response = get_response(csv_file_url, None, headers, 'text/csv')
    #csv_text = response.read()
    lines = reader(StringIO(csv_text))
    headings = lines.next()
    add_list = []
    if match:
        matchup = dict(zip(keys, match))
    else:
        matchup = None
    for line in lines:
        values = dict(zip(headings, line)) 
        if matchup:
            use_values = True
            for key in keys:
                if matchup[key] != values[key]:
                    use_values = False
                    break # exit the keys loop, match condition failed
            if use_values: # all keys matched
                add_list.append(values)
                break # key matched so no need to continue with lines loop
        else:
            add_list.append(values)
    if add_list: 
        if not matchup:
            scraperwiki.sqlite.execute("drop table if exists " + table_name)
            scraperwiki.sqlite.commit()
        scraperwiki.sqlite.save(keys, add_list, table_name, verbose=0) # one save operation (= list of dics), not many
    return len(add_list)

# set content type for JSON, XML or RSS formats
def set_content(fmt = 'xml'): 
    if fmt == 'json':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/json")
    elif fmt == 'jsonp':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/javascript")
    elif fmt == 'rss':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/rss+xml")
    elif fmt == 'atom':
        scraperwiki.utils.httpresponseheader("Content-Type", "application/atom+xml")
    elif fmt == 'html':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/html")
    elif fmt == 'csv':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/csv")   
    elif fmt == 'tsv':
        scraperwiki.utils.httpresponseheader("Content-Type", "text/tab-separated-values")   
    else: # XML always the default - see data_output()
        scraperwiki.utils.httpresponseheader("Content-Type", "text/xml")

# redirect to another web page
def redirect(url, code=303): 
    if code <= 307 and code >= 300:
        scraperwiki.utils.httpresponseheader("Location", url)
        scraperwiki.utils.httpstatuscode(code)
    else:
        scraperwiki.utils.httpresponseheader("Content-Type", "text/html")
        print """
        <html>
        <head>
        <meta http-equiv="Refresh" content="0; url=%s" />
        </head>
        <body>
        <p>Please follow this link: <a href="%s">%s</a>.</p>
        </body>
        </html>""" % (url, url, url)
    sys.exit()

# output a data dict in JSON, XML or RSS formats
def data_output(data, fmt = 'xml', options = None):
    if fmt == 'object':
        return data
    elif fmt == 'json':
        if options: # if this is set it's really JSONP
            return options + '(' + json.dumps(data, indent=4) + ');'
        else:
            return json.dumps(data, indent=4)
    elif fmt == 'jsonp':
        if not options: options = 'callback'
        return options + '(' + json.dumps(data, indent=4) + ');'
    elif fmt == 'rss':
        root = to_rss(data, options, ISO8601_DATE)
        root.addprevious(etree.PI('xml-stylesheet', 'type="text/xsl" title="XSL stylesheet" href="http://www.speakman.org.uk/rss.xsl"'))
        return etree.tostring(root.getroottree(), encoding="utf-8", xml_declaration=True, pretty_print=True)
    elif fmt == 'atom': 
        root = to_atom(data, options, ISO8601_DATE) 
        return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    elif fmt == 'html':
        if not options:
            options = 'data'
        html_string = to_html('', data, options)
        root = lxml.html.fromstring(html_string)
        return etree.tostring(root, pretty_print=True, method="html")
        #return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    else: # XML always the default - see set_content()
        if not options:
            options = 'root'
        root = to_xml(options, data)
        return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    
# use data to fill out an RSS 2.0 feed (with option for GeoRSS)
def to_rss(data, map, in_date_fmt = ISO8601_DATE):
    GEORSS_NAMESPACE = "http://www.georss.org/georss"
    GEORSS = "{%s}" % GEORSS_NAMESPACE
    NSMAP = { 'georss': GEORSS_NAMESPACE }
    feed_type = 'rss'
    for i in data[map['items']][map['item']]:
        for k, v in map['geo_item'].items():
            if v in i:
                feed_type = 'georss'
                break
    if feed_type == 'georss':
        root = etree.Element('rss', nsmap=NSMAP)
    else:
        root = etree.Element('rss')
    root.set("version", "2.0")
    branch = etree.SubElement(root, "channel")
    for k, v in map.items():
        if k <> 'item' and  k <> 'items' and k <> 'geo_item' and k <> 'sub_item' and v in data:
            twig = etree.SubElement(branch, k)
            twig.text = vstr(data[v])
    pubdate = datetime.now(TZ).strftime(RFC822_DATE)
    twig = etree.SubElement(branch, 'pubDate')
    twig.text = vstr(pubdate)
    for i in data[map['items']][map['item']]:
        twig = etree.SubElement(branch, "item")
        no_date = True
        for k, v in map['sub_item'].items():
            if v in i:
                leaf = etree.SubElement(twig, k)
                if k == 'pubDate':
                    no_date = False
                    if in_date_fmt ==  ISO8601_DATE:
                        leaf.text = convert_dt(vstr(i[v])+'T12:00:00Z', RFC3339_DATE, RFC822_DATE) #  make time noon
                    else:
                        leaf.text = convert_dt(vstr(i[v]), in_date_fmt, RFC822_DATE) 
                else:
                    leaf.text = vstr(i[v])
                if k == 'guid':
                    leaf.set("isPermaLink", "false")
        if no_date:
            leaf = etree.SubElement(twig, 'pubDate')
            leaf.text = vstr(pubdate)
        for k, v in map['geo_item'].items():
            if v in i:
                leaf = etree.SubElement(twig, GEORSS+k)
                leaf.text = vstr(i[v])
    return root

# use data to fill out an ATOM feed (with option for GeoRSS)
def to_atom(data, map, in_date_fmt = ISO8601_DATE):
    GEORSS_NAMESPACE = "http://www.georss.org/georss"
    ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
    GEORSS = "{%s}" % GEORSS_NAMESPACE
    GEONSMAP = { None: ATOM_NAMESPACE, 'georss': GEORSS_NAMESPACE }
    NSMAP = { None: ATOM_NAMESPACE }
    feed_type = 'atom'
    for i in data[map['items']][map['item']]:
        for k, v in map['geo_item'].items():
            if v in i:
                feed_type = 'georss'
                break
    if feed_type == 'georss':
        root = etree.Element('feed', nsmap=GEONSMAP)
    else:
        root = etree.Element('feed', nsmap=NSMAP)
    for k, v in map.items():
        if k <> 'item' and  k <> 'items' and k <> 'geo_item' and k <> 'sub_item' and v in data:
            branch = etree.SubElement(root, k)
            if k == 'link':
                branch.set("href", vstr(data[v]))
                branch.set("rel", "self")
            else:
                branch.text = vstr(data[v])
    pubdate = datetime.now(TZ).strftime(RFC3339_DATE)
    branch = etree.SubElement(root, 'updated')
    branch.text = vstr(pubdate)
    for i in data[map['items']][map['item']]:
        branch = etree.SubElement(root, "entry")
        no_date = True
        for k, v in map['sub_item'].items():
            if v in i:
                leaf = etree.SubElement(branch, k)
                if k == 'link':
                    leaf.set("href", vstr(i[v]))
                elif k == 'published' or k == 'updated':
                    no_date = False
                    if in_date_fmt ==  ISO8601_DATE:
                        leaf.text = convert_dt(vstr(i[v])+'T12:00:00Z', RFC3339_DATE, RFC3339_DATE) #  make time noon
                    else:
                        leaf.text = convert_dt(vstr(i[v]), in_date_fmt, RFC3339_DATE) 
                else:
                    leaf.text = vstr(i[v])
                if k == 'summary' or k == 'content':
                    leaf.set("type", "html")
        if no_date:
            leaf = etree.SubElement(branch, 'updated')
            leaf.text = vstr(pubdate)
        leaf = etree.SubElement(branch, 'author')
        #end = etree.SubElement(leaf, 'name')
        #end.text = vstr(AUTHOR)
        for k, v in map['geo_item'].items():
            if v in i:
                leaf = etree.SubElement(branch, GEORSS+k)
                leaf.text = vstr(i[v])
    return root

# unserialize an XML document to a dictionary (containing dicts, strings or lists)
def from_xml(element):
    if len(element) > 0:
        outdict = {}
        if element.get('type') == 'list':
            value = []
            for i in element:
                value.append(from_xml(i))
            outdict[element[0].tag] = value
        else:
            for i in element:
                outdict[i.tag] = from_xml(i)
        return outdict
    else:
        return element.text

# serialise the contents of a dictionary as simple XML
def to_xml(element_name, data):
    element_name = re.sub('\s', '_', element_name) # replace any spaces in the tag name with underscores
    element = etree.Element(element_name)
    if isinstance (data, dict):
        keys = data.keys()
        keys.sort() # output is in alphab order 
        for key in keys: # output simple string elements first
            if not isinstance(data[key], list) and not isinstance(data[key], dict):
                element.append(to_xml(key, data[key]))
        for key in keys: # any lists and dicts come afterwards
            if isinstance(data[key], list): # lists stay in original order
                element.set('type', 'list')
                for i in data[key]:
                    element.append(to_xml(key, i))
            elif isinstance(data[key], dict):
                element.append(to_xml(key, data[key]))
    else:
        element.text = vstr(data)
    return element

# serialise the contents of a dictionary as simple HTML (NB string output)
def to_html(container, data, title = ''):
    if title:
        title = re.sub('_', ' ', title) # replace any underscores with spaces
        title = title.title()
    if not container:
        output = "<html><head>"
        if title:
            output = output+"<title>"+title+"</title>"
        output = output+'</head><body>'
        if title:
            output = output+"<h1>"+title+"</h1>"
        output = output+to_html('body', data)
        return output+"</body></html>"
    elif isinstance (data, dict):
        output = ''
        if title:
            output = output+'<h2>'+title+'</h2>'
        list_strings = []
        list_structs = []
        keys = data.keys()
        for key in keys: # separate simple string elements from rest
            if isinstance(data[key], list) or isinstance(data[key], dict):
                list_structs.append(key)
            else:
                list_strings.append(key)
        if list_strings:
            list_strings.sort()
            output = output+'<ul>'
            for key in list_strings: # output simple string elements first
                output = output+to_html('ul', data[key], key)
            output = output+'</ul>'
        if list_structs:
            list_structs.sort()
            for key in list_structs: # output list and dict elements next
                output = output+to_html('body', data[key], key)
        return output
    elif isinstance (data, list):
        output = ''
        db_table = False
        if len(data) >= 1 and isinstance(data[0], dict):
            headers = data[0].keys()
            db_table = True
            test_len = len(headers)
            for i in data:
                if not isinstance(i, dict) or len(i) <> test_len:
                    db_table = False
                    break
        else:
            db_table = False
        if db_table:
            headers.sort()
            output = output+'<table><tr>'
            for i in headers:
                output = output+to_html('tr1', i)
            output = output+'</tr>'
            for i in data:
                output = output+'<tr>'
                for j in headers:
                    output = output+to_html('tr', i[j])
                output = output+'</tr>'
            return output+'</table>'
        else:
            if title:
                output = output+'<h2>'+title+'</h2>'
            output = output+'<ul>'
            for i in data:
                output = output+to_html('ul', i)
            return output+'</ul>'
    else:
        output = ''
        if container == 'body':
            if title:
                output = output+'<h3>'+title+'</h3>'
            return output+vstr(data)
        elif container == 'dl':
            if title:
                output = output+'<dt>'+title+'</dt>'
            return output+'<dd>'+vstr(data)+'</dd>'
        elif container == 'tr':
            output = output+'<td>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</td>'
        elif container == 'tr1':
            output = output+'<th>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</th>'
        elif container == 'ul':
            output = output+'<li>'
            if title:
                output = output+'<strong>'+title+':</strong> '
            return output+vstr(data)+'</li>'

# return valid string/unicode if not null, otherwise empty string
def vstr(s):
    if s:
        try:
            return unicode(s)
        except UnicodeDecodeError:
            return str(s)
    else:
        return u''

# remove any non ascii characters
def ascii(s): return "".join(i for i in s if ord(i)<128)

# add new data elements to the existing query of a URL
def add_to_query(url, data = {}):
    u = urlparse.urlsplit(url)
    qdict = dict(urlparse.parse_qsl(u.query))
    qdict.update(data)
    query = urllib.urlencode(qdict)
    url = urlparse.urlunsplit((u.scheme, u.netloc, u.path, query, u.fragment))
    return url

# get a date in standard format or None if the string cannot be parsed
def get_dt(date_string, date_format=DATE_FORMAT):
    try:
        dt = datetime.strptime(date_string, date_format)
        return dt.date()
    except:
        return None

# convert a date string from one format to another
def convert_dt(date_string, in_date_format=DATE_FORMAT, out_date_format=RFC822_DATE, on_error_original=True):
    if on_error_original and in_date_format == out_date_format:
        return date_string
    else:
        try:
            dt = datetime.strptime(date_string, in_date_format)
            dt = dt.replace(tzinfo=TZ)
            return dt.strftime(out_date_format)
        except:
            if on_error_original:
                return date_string
            else:
                return None

# increment a date by a number OR to the next available weekday if a string
# return the start and end dates of the permissible range
def inc_dt(date_string, date_format=DATE_FORMAT, increment=1):
    try:
        start_dt = datetime.strptime(date_string, date_format)
        if not increment:
            increment = 0
        if isinstance(increment, int) or increment.isdigit() or (increment.startswith('-') and increment[1:].isdigit()):
            day_inc = int(increment)
            if day_inc < 0:
                end_dt = start_dt
                start_dt = end_dt + timedelta(days=day_inc)
            else:
                end_dt = start_dt + timedelta(days=day_inc)
        elif increment == 'Year':
            start_dt = date(start_dt.year, 1, 1) # first day of this year
            end_dt = date(start_dt.year, 12, 31) # last day of this year
        elif increment == 'Month': 
            start_dt = date(start_dt.year, start_dt.month, 1) # first day of this month
            if start_dt.month == 12:
                end_dt = date(start_dt.year+1, 1, 1) # first day of next year
            else:
                end_dt = date(start_dt.year, start_dt.month+1, 1) # first day of next month
            end_dt = end_dt - timedelta(days=1)
        elif increment.startswith('-'): 
            wday = WEEKDAYS.get(increment[1:4].capitalize(), 0) # supplied is a week day defining beginning of week for a weekly list
            day_inc = wday - start_dt.weekday()
            if day_inc > 0: 
                day_inc = day_inc - 7
            start_dt = start_dt + timedelta(days=day_inc)
            end_dt = start_dt + timedelta(days=6)
        else:
            wday = WEEKDAYS.get(increment[0:3].capitalize(), 6) # supplied is a week day defining end of week for a weekly list
            day_inc = wday - start_dt.weekday()
            if day_inc < 0:
                day_inc = day_inc + 7
            end_dt = start_dt + timedelta(days=day_inc)
            start_dt = end_dt - timedelta(days=6)
        return start_dt.strftime(date_format), end_dt.strftime(date_format)
    except:
        return date_string, date_string

# test if a date is within a permissible range
def match_dt(date_to_test, date_from, date_to, date_format=DATE_FORMAT):
    try:
        test_dt = datetime.strptime(date_to_test, date_format)
        from_dt = datetime.strptime(date_from, date_format)
        to_dt = datetime.strptime(date_to, date_format)
        if test_dt <= to_dt and test_dt >= from_dt:
            return True
        else:
            return False
    except:
        return False

# test if a date is before or after a reference date
def test_dt(date_to_test, ref_date, date_format=DATE_FORMAT):
    try:
        test_dt = datetime.strptime(date_to_test, date_format)
        ref_dt = datetime.strptime(ref_date, date_format)
        if test_dt > ref_dt:
            return 1
        elif test_dt < ref_dt:
            return -1
        elif test_dt == ref_dt:
            return 0
        else:
            return None
    except:
        return None

# get a response from a url
def get_response(url, data = None, headers = None, accept = 'text/html', timeout = None):
    request = urllib2.Request(url)
    request.add_header('Accept', accept)
    if headers:
        for k, v in headers.items():
            request.add_header(k, v)
    """if multipart:
        opener = urllib2.build_opener(MultipartPostHandler)
        if timeout:
            response = opener.open(request, data, timeout)
        else:
            response = opener.open(request, data)
    else:
    """
    if timeout:
        response = urllib2.urlopen(request, data, timeout)
    else:
        response = urllib2.urlopen(request, data)
    return response

# get JSON data from a url
def json_get(url, data = None, timeout = None):
    try:
        sf = urllib2.urlopen(url, data, timeout)
        result = json.load(sf)  
    except:
        result = None; sf = None
    finally:
        if sf: sf.close()
    return result

# put a cookie in the jar
def set_cookie(cookie_jar, cname, cvalue, cdomain=None, cpath='/'):
    ck = cookielib.Cookie(version=0, name=str(cname), value=str(cvalue), domain=cdomain, path=cpath, 
            port=None, port_specified=False, domain_specified=False, expires=None, 
            domain_initial_dot=False, path_specified=True, secure=False, 
            discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
    cookie_jar.set_cookie(ck)

# gets a mechanize browser 
# NB the internal handler contains an lxml Html Element that can be used for DOM based methods
def get_browser(headers = None, factory = '', proxy = ''):
    if factory == 'robust':
        br = mechanize.Browser(factory=mechanize.RobustFactory()) # using BeautifulSoup 2 parser
    elif factory == 'xhtml':
        br = mechanize.Browser(factory=mechanize.DefaultFactory(i_want_broken_xhtml_support=True))
    else:
        br = mechanize.Browser()

    cj = cookielib.LWPCookieJar()
    br.set_cookiejar(cj)

    if proxy:
        # see http://www.publicproxyservers.com/proxy/list_uptime1.html
        br.set_proxies({"https": proxy, "http": proxy}) 
        # https tunnel via http proxy not working - bug fixed below but same problem?
        # http://sourceforge.net/mailarchive/forum.php?thread_name=alpine.DEB.2.00.0910062211230.8646%40alice&forum_name=wwwsearch-general
    br.set_handle_robots(False)
    if headers: 
        br.addheaders = headers.items() # Note addheaders is a data object (list of tuples) not a method
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    handler = EtreeHandler()
    br.add_handler(handler)
    return br, handler, cj

# selects a form and sets up its fields, action, method etc
# in the case of HTML select tags, the particular control used is always selected by name
# e.g. <select name="name"> <option value="value"> label </option> </select>
# however the option selected can be via the value attribute or by label (if the key starts with #)
# controls can be disabled by setting them to None
def setup_form(br, form = None, fields = None, action = None, method = None):
    if not form:
        br.select_form(nr=0)
    elif form.isdigit():
        br.select_form(nr=int(form))
    else:
        br.select_form(name=form)
    if action:
        current_action = br.form.action
        new_action = urlparse.urljoin(current_action, action)
        br.form.action = new_action
    if method and method.upper() == 'GET':
        br.form.method = method
    #print br.form
    if fields:
        add_controls = []
        for k, v in fields.items():
            try:
                if k.startswith('#'):
                    control = br.find_control(name=k[1:], nr=0) # find first control named k
                else:
                    control = br.find_control(name=k, nr=0) # find first control named k
            except mechanize._form.ControlNotFoundError as e: # if the control does not exist, we create a dummy hidden control to hold the value
                if k.startswith('#'):
                    add_controls.append(k[1:])
                else:
                    add_controls.append(k)
        if add_controls:
            for k in add_controls:
                br.form.new_control('hidden', k, {'value':''} )
            br.form.fixup()
        br.form.set_all_readonly(False)
        for k, v in fields.items():
            if k.startswith('#'): # used to set a named control using option label
                control = br.find_control(name=k[1:], nr=0) # find first control named k
                if v is None:
                    control.disabled = True
                elif isinstance(v, list):
                    if control.disabled: control.disabled = False
                    for i in v:
                        control.get(label=i, nr=0).selected = True # set the value by selecting its label (v[i])
                else:
                    if control.disabled: control.disabled = False
                    control.get(label=v, nr=0).selected = True # set the value by selecting its label (v)
                    # NB label matches any white space compressed sub string so there is potential for ambiguity errors
            else:
                #br[k] = v # default is to directly assign the named control a value (v)
                control = br.find_control(name=k, nr=0) # find first control named k
                if v is None:
                    control.disabled = True
                elif (control.type == 'radio' or control.type == 'checkbox' or control.type == 'select') and not isinstance (v, list):
                    if control.disabled: control.disabled = False
                    control.value = [ v ]
                elif (control.type != 'radio' and control.type != 'checkbox' and control.type != 'select') and v and isinstance (v, list):
                    if control.disabled: control.disabled = False
                    control.value = v [0]
                else:
                    if control.disabled: control.disabled = False
                    control.value = v
        # NB throws except mechanize._form.ItemNotFoundError as e: if field select/check/radio option does not exist


# returns response after submitting a form via a mechanize browser
# submit parameter is a submit control name/number or an id (if it starts with a '#')
def submit_form(br, submit = None):
    if not submit:
        response = br.submit()
    elif submit.isdigit():
        response = br.submit(nr=int(submit))
    elif submit.startswith('#'):
        control = br.find_control(id=submit[1:], nr=0) # find first control with id submit
        if control.disabled: control.disabled = False
        response = br.submit(id=submit[1:], nr=0)
    else:
        control = br.find_control(name=submit, nr=0) # find first control named submit
        if control.disabled: control.disabled = False
        response = br.submit(name=submit, nr=0)
    return response

# returns a response after following a link via a mechanize browser
# link paramter is a link text value or number or a name (if it starts with a '!')
def process_link(br, link = None):
    if not link:
        response = br.follow_link()
    elif link.isdigit():
        response = br.follow_link(nr=int(link))
    elif link.startswith('!'):
        response = br.follow_link(name=str(link[1:]))
    else:
        response = br.follow_link(text=str(link))
    return response

# makes a direct url request via the browser supplying GET or POST parameters
def open_url(br, url, data = None, method = None):
    if data:
        for k, v in data.items():
            if v and isinstance(v, list):
                data[k] = v[0]
    else:
        return br.open(url)
    if method and method.upper() == 'GET':
        url = add_to_query(url, data)
        return br.open(url)
    else:
        return br.open(url, urllib.urlencode(data))

# return an HTML Element document from an html string
def get_doc(raw_html, url = ''):
    doc = lxml.html.fromstring(raw_html) # lxml fast parser
    if url:
        doc.make_links_absolute(url)
    return doc

# return an XML Element document from an xml string
def get_doc_xml(raw_xml):
    doc = etree.fromstring(raw_xml)
    return doc

# returns a child dictionary updated with any missing values specified in its parents
def dict_inherited(container, child_name, parent_key = 'parent'):
    child_dict = {}
    if child_name in container:
        child_dict.update(container[child_name])
        while child_dict.get(parent_key):
            next_dict = container[child_dict[parent_key]]
            del child_dict[parent_key]
            for k, v in next_dict.items():
                if not child_dict.get(k):
                    child_dict[k] = v
                elif child_dict[k] == '__None__':
                    child_dict[k] = None
                elif child_dict[k] == '__Clear__':
                    del child_dict[k]
    return child_dict 

# return the text value of an xpath or cssselect expression
def xpath_text(element, expression, thistype='xpath'):
    if element is None or not expression:
            return ''
    if thistype == 'css':
        value = element.cssselect(expression)
    else:
        value = element.xpath(expression)
    return text_content(value)
        
# returns trimmed html content with tags removed, entities converted
def text_content(value):
    if value is None:
        return ''
    if isinstance (value, list):
        if len(value) > 0:
            value = value[0]
        else:
            return ''
    if isinstance (value, lxml.html.HtmlElement):
        text = lxml.html.tostring(value)
        text = TAGS_REGEX.sub(' ', text) # replace any html tag content with spaces
        # use beautiful soup to convert html entities to unicode strings
        text = BeautifulSoup(text, convertEntities="html").contents[0].string
    else:
        text = vstr(value)
        text = TAGS_REGEX.sub(' ', text) # replace any html tag content with spaces
        # use beautiful soup to convert html entities to unicode strings
        text = BeautifulSoup(text, convertEntities="html").contents[0].string
    return trim(text)
    
# return text with internal white space compressed and external space stripped off
def trim(text):
    str_trim = GAPS_REGEX.sub(' ', text) # replace internal gaps with single spaces
    return str_trim.strip() # remove space at left and right

# return text with all internal white space removed
def no_space(text):
    return GAPS_REGEX.sub('', text) # remove internal gaps

#get selected table fields from database as list of maps
def get_table_vals(table = '', fields = '', where = '', orderetc = ''):
    if not fields:
        sql_fields = '*'
    elif isinstance(fields, list):
        sql_fields = ",".join(fields)
    elif isinstance(fields, dict):
        sql_fields = ''
        for k, v in fields.items():
            sql_fields = sql_fields+","+v+" as "+k
        sql_fields = sql_fields[1:]
    else:
        sql_fields = fields
    if where:
        where = " where "+where+' '+orderetc
    else:
        where = ' '+orderetc
    return scraperwiki.sqlite.select(sql_fields+" from "+table+where)

#convert list of maps resulting from SQL query to keyed dictionary (alternatively source is a table name)
def get_map(source, key, value=None):
    data = {}
    if not isinstance(source, list):
        source = get_table_vals(source)
    for map in source:
        if value:
            data[map[key]] = map[value]
        else:
            data[map[key]] = map
    return data

#convert list of maps resulting from SQL query to simple list (alternatively source is a table name)
def get_list(source, key):
    data = []
    if not isinstance(source, list):
        source = get_table_vals(source)
    for map in source:
        if map.get(key):
            data.append(map[key])
    return data 

# replace matching values with a substitution string in a single table column
# if no replace type is specified, it just prints the number of matching rows
def replace_vals(table, field, match, subst, replace_type= '', confirm = None):
    match = match.replace("'", "''")
    if replace_type.lower() == 'prefix':
        where = " where "+field+" like '"+match+"%'"
    elif replace_type.lower() == 'suffix':
        where = " where "+field+" like '%"+match+"'"
    else:
        where = " where "+field+" like '%"+match+"%'"
    subst = subst.replace("'", "''")
    if replace_type.lower() == 'prefix':
        where2 = " where "+field+" like '"+subst+"%'"
    elif replace_type.lower() == 'suffix':
        where2 = " where "+field+" like '%"+subst+"'"
    else:
        where2 = " where "+field+" like '%"+subst+"%'"
    sql = "select count(*) from "+table+where
    result1 = scraperwiki.sqlite.execute(sql)
    sql = "select count(*) from "+table+where2
    result2 = scraperwiki.sqlite.execute(sql)
    print "Found %d match strings and %d substitution strings before replacement" % (result1['data'][0][0], result2['data'][0][0])
    if confirm:
        sql = "update "+table+" set "+field+" = replace ("+field+", '"+match+"', '"+subst+"')"+where
        scraperwiki.sqlite.execute(sql)
        scraperwiki.sqlite.commit()
        sql = "select count(*) from "+table+where
        result1 = scraperwiki.sqlite.execute(sql)
        sql = "select count(*) from "+table+where2
        result2 = scraperwiki.sqlite.execute(sql)
        print "Found %d match strings and %d substitution strings after replacement" % (result1['data'][0][0], result2['data'][0][0])
    else:
        print "No substitutions made"

# list distinct URL prefixes in a field
def list_url_prefixes(table, field = 'url'):
    dump = get_list(table, field)
    prefixes = []
    for i in dump:
        parsed = urlparse.urlparse(i)
        prefix = 'http://' + parsed.netloc + parsed.path
        if prefix not in prefixes:
            prefixes.append(prefix)
    print "Distinct URL prefixes found in the '" + field + "' field of the " + table + " table:"
    for p in prefixes:
        print p

# set map values in a database table NB stores values as unicode strings
def set_table_vals(table, map, where = ''):
    clause = ''
    for k, v in map.items():
        if v:
            store = vstr(v).replace("'", "''")
            clause = clause+', '+k+"='"+store+"'"
        else:
            clause = clause+', '+k+"=''"
    clause = clause[2:]
    if where:
        where = " where "+where
    else:
        where = ''
    scraperwiki.sqlite.execute("update "+table+" set "+clause+where)
    scraperwiki.sqlite.commit()

# return a simple list of database table columns
def get_table_cols(table):
    result = scraperwiki.sqlite.execute("select * from "+table+" limit 1")
    return result['keys']

# return columns for a table - new version returns dict of columns with constraints as values
def get_table_columns(table='swdata'):
    schemas = scraperwiki.sqlite.select("sql from sqlite_master where type='table' and name='"+table+"'")
    columns = {}
    for schema in schemas:
        table_match = TABLE_REGEX.search(schema['sql'].replace('`', ''))
        if table_match:
            if table_match.group(1) == table:
                fields = table_match.group(2).split(',')
                for field in fields:
                    parts = field.split()
                    column = parts[0]
                    if len(parts) > 0:
                        columns[column] = ' '.join(parts[1:])
                    else:
                        columns[column] = ''
                break
    return columns

# get a create table schema
def create_table_schema(columns, table='swdata'):
    if not columns:
        return None
    elif isinstance(columns, dict):
        fields = []
        for k, v in columns.items():
            fields.append("`" + k + "` " + v)
        return "create table `" + table + "` (" + ', '.join(fields) + ')'
    elif isinstance(columns, list):
        return "create table `" + table + "` (" + ', '.join(columns) + ')'
    else:
        return None

# get a create index schema
def create_index_schemas(indices, table='swdata'):
    if indices and isinstance(indices, dict):
        results = []
        for k, v in indices.items():
            if v['unique']:
                create = 'create unique index '
            else:
                create = 'create index '
            results.append(create + v['name'] + " on " + table + " (" + k + ")")
        return results
    else:
        return []

# return column indexes for a table - returns dict of indexed columns with name and whether unique as values
def get_table_indices(table='swdata'):
    schemas = scraperwiki.sqlite.select("sql from sqlite_master where type='index' and tbl_name='"+table+"'")
    indices = {}
    for schema in schemas:
        index_match = INDEX_REGEX.search(schema['sql'].replace('`', ''))
        if index_match:
            if index_match.group(3) == table:
                unique = False
                if 'unique' in index_match.group(1).lower(): unique = True
                result = { 'name': index_match.group(2), 'unique': unique }
                indices[index_match.group(4)] = result
    return indices

# adds column(s) to a database table if found not to exist
def update_columns(table, columns, constraint = 'text'):
    existing = get_table_columns(table)
    if not constraint: constraint = ''
    if isinstance(columns, list):
        for col in columns:
            if not col in existing.keys():
                scraperwiki.sqlite.execute("alter table "+table+" add column "+col+" "+constraint)
                scraperwiki.sqlite.commit()
    elif isinstance(columns, str) or isinstance(columns, unicode):
        if not columns in existing.keys():
                scraperwiki.sqlite.execute("alter table "+table+" add column "+columns+" "+constraint)
                scraperwiki.sqlite.commit()

# renames a column by copying data to a temp table and renaming
# note if new _column is null or empty the column is deleted
def rename_column(table, column, new_column, temp_table = 'temp_copy'):
    scraperwiki.sqlite.execute("drop table if exists "+temp_table)
    columns = get_table_columns(table)
    #print columns
    if not column in columns.keys(): return
    old_fields = []; new_fields = []; # note array used because order is important
    for k, v in columns.items():
        if k == column:
            del columns[column]
            if new_column:
                columns[new_column] = v
                new_fields.append(new_column)
                old_fields.append(column)
        else:
            new_fields.append(k)
            old_fields.append(k)
    sql_new_schema = create_table_schema(columns, temp_table)
    #print sql_new_schema
    scraperwiki.sqlite.execute(sql_new_schema)
    index_schemas = get_table_indices(table) # save index details before rename
    new_index_schemas = {}
    for k, v in index_schemas.items(): # filter out non-applicable indices
        field_list = k.split(',')
        new_field_list = []
        for field in field_list:
            if field == column:
                if new_column: 
                    new_field_list.append(new_column)
            else:
                new_field_list.append(field)
        if new_field_list:
            new_index_schemas[', '.join(new_field_list)] = v
    #print new_index_schemas
    sql_index_schemas = create_index_schemas(new_index_schemas, table)
    #print sql_index_schemas
    insert = "insert into "+temp_table+" ("+", ".join(new_fields)+") select "+", ".join(old_fields)+" from "+table
    #print insert
    scraperwiki.sqlite.execute(insert)
    scraperwiki.sqlite.execute("drop table "+table) # deletes associated indexes
    scraperwiki.sqlite.execute("alter table " + temp_table + " rename to " + table)
    for sql in sql_index_schemas: # re-apply indices
        scraperwiki.sqlite.execute(sql)
    scraperwiki.sqlite.commit()

# query the database cache table
def cache_fetch(key):
    tstamp = time.time()
    #if isinstance(key, dict):
    #    key = hash(tuple(sorted(key.iteritems())))
    #elif isinstance(key, list):
    #    key = hash(tuple(key))
    #else:
    #    key = hash(key)
    ser_key = cPickle.dumps(key)
    try:
        sql = "value from cache where key = '" + ser_key.replace("'", "''") + "' and expires >= " + str(tstamp)
        results = scraperwiki.sqlite.select(sql)
    except:
        results = None
    if results:
        return cPickle.loads(str(results[0]['value']))
    else:
        return None

# clear the database cache table
def cache_clear():
    scraperwiki.sqlite.execute("delete from cache")
    scraperwiki.sqlite.commit()

# insert a value in the database cache table
# this is a slow operation, so we also take the opportunity to clear stale cache entries
def cache_put(key, value, age = DEFAULT_CACHE_AGE): # default expiry in 12 hours
    tstamp = time.time()
    try:
        scraperwiki.sqlite.execute("delete from cache where expires < "+str(tstamp))
        scraperwiki.sqlite.commit()
    except:
        pass
    if age and age > 0:
        expires = tstamp + age
    else:
        expires = tstamp + DEFAULT_CACHE_AGE
    #if isinstance(key, dict):
    #    key = hash(tuple(sorted(key.iteritems())))
    #elif isinstance(key, list):
    #    key = hash(tuple(key))
    #else:
    #    key = hash(key)
    store = { 'key': cPickle.dumps(key), 'value': cPickle.dumps(value), 'expires': expires }
    scraperwiki.sqlite.save(unique_keys=['key'], data=store, table_name='cache', verbose=0)

# get a processing slot
def get_slot(num_slots = NUM_SLOTS, slot_time = SLOT_TIME):
    timestamp = time.time()
    next_free_slot = slot_time
    for i in range(0, num_slots):
        slot_name = "slot" + str(i)
        slot_expires = scraperwiki.sqlite.get_var(slot_name, 0)
        if not slot_expires or slot_expires < timestamp:
            scraperwiki.sqlite.save_var(slot_name, timestamp + slot_time) # we have the lock, so just block it for the next slot_time secs
            return i, slot_time
        else:
            this_expires = slot_expires - timestamp
            if this_expires > 0 and this_expires < next_free_slot: 
                next_free_slot = this_expires
    return -1, next_free_slot # time until next available slot is free

# free up a processing slot
def free_slot(slot_num):
    slot_name = "slot" + str(slot_num)
    scraperwiki.sqlite.save_var(slot_name, 0)

# put an item into the local memory cache
# make copy, otherwise the cached version is mutable
def mcache_put(key, value):
    if isinstance(key, dict):
        keyhash = hash(tuple(sorted(key.iteritems())))
    elif isinstance(key, list):
        keyhash = hash(tuple(key))
    else:
        keyhash = hash(key)
    CACHE[keyhash] = copy.deepcopy(value)

# get an item from the local memory cache
# make copy, otherwise the cached version is mutable
def mcache_fetch(key):
    if isinstance(key, dict):
        keyhash = hash(tuple(sorted(key.iteritems())))
    elif isinstance(key, list):
        keyhash = hash(tuple(key))
    else:
        keyhash = hash(key)
    return copy.deepcopy(CACHE.get(keyhash))


#default css for views
def base_css():
    css = """
body {
    margin: 10 20;
    padding: 0;
    background: #FFF;
    color: #191919;
    font-weight: normal;
    font-family: Helvetica, Arial, sans-serif;
    font-size: 75%;
}
    /*------------------- HEADERS -------------------*/
h1, h2, h3, h4, h5, h6 {
  margin: 6px 0;
  padding: 0;
  font-weight: normal;
  font-family: Helvetica, Arial, sans-serif;
}

h1 {font-size: 2em;}
h2 {font-size: 1.8em; line-height: 1.8em;}
h3 {font-size: 1.6em;}
h4 {font-size: 1.4em;}
h5 {font-size: 1.2em;}
h6 {font-size: 1em;}
/*------------------- HEADERS -------------------*/

/*------------------- TEXT/LINKS/IMG -------------------*/
p {margin: 10px 0 18px; padding: 10px;}

em {font-style:italic;}

strong {font-weight:bold;}

a:link, a:visited {color: #027AC6; text-decoration: none; outline:none;}

a:hover {color: #0062A0; text-decoration: underline;}

a:active, a.active {color: #5895be;}

img, a img {border: none;}

abbr,acronym {
    /*indicating to users that more info is available */
    border-bottom:1px dotted #000;
    cursor:help;
}

/*------------------- TEXT/LINKS/IMG -------------------*/

hr {
  margin: 0;
  padding: 0;
  border: none;
  height: 1px;
  background: #5294c1;
}

/*Change in format*/
ul, blockquote, quote, code, fieldset {margin: 16px 0;}

pre {  padding: 0; margin: 0; font-size: 1.3em; 
    white-space: -moz-pre-wrap !important; /* Mozilla, supported since 1999 */
    white-space: -pre-wrap; /* Opera 4 - 6 */
    white-space: -o-pre-wrap; /* Opera 7 */
    white-space: pre-wrap; /* CSS3 */
    word-wrap: break-word; /* IE 5.5+ */
}


/*------------------- LISTS -------------------*/

ul {margin-left:32px;}

ol,ul,dl {margin-left:32px;}
ol, ul, dl {margin-left:32px;}
ul, ol {margin: 8px 0 16px; padding: 0;}
ol li, ul li {margin: 7px 0 7px 32px;}
ul ul li {margin-left: 10px;}

ul li {padding: 0 0 4px 6px; list-style: disc outside;}
ul li ul li {list-style: circle outside;}

ol li {padding: 0 0 5px; list-style: decimal outside;}

dl {margin: 8px 0 16px 24px;}
dl dt {font-weight:bold;}
dl dd {margin: 0 0 8px 20px;}

/*------------------- LISTS -------------------*/


/*------------------- FORMS -------------------*/
input {
  font: 1em/1.2em Verdana, sans-serif;
  color: #191919;
}
textarea, select {
  font: 1em/1.2em Verdana, sans-serif;
  color: #191919;
}
textarea {resize:none;}
/*------------------- FORMS -------------------*/


/*------------------- TABLES -------------------*/

table {margin: 16px 0; width: 90%; font-size: 0.92em; border-collapse:collapse; }

th {
  border:1px solid #000; 
  background-color: #d3e7f4;
  font-weight: bold;
}

td {padding: 4px 6px; margin: 0; border:1px solid #000;}

caption {margin-bottom:8px; text-align:center;}

/*------------------- TABLES -------------------*/
    """
    return css

"""
class MinimalSoupHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            soup = MinimalSoup (response.get_data())
            response.set_data(soup.prettify())
        return response
"""

class BeautifulSoupHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            #soup = BeautifulSoup (response.get_data())
            self.element = lxml.html.soupparser.fromstring(response.get_data())
            #response.set_data(soup.prettify())
            response.set_data(etree.tostring(self.element, pretty_print=True, method="html"))
        return response

class EtreeHandler(mechanize.BaseHandler):
    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = mechanize.response_seek_wrapper(response)
        # only use if response is html
        if response.info().dict.has_key('content-type') and ('html' in response.info().dict['content-type']):
            #clean_up = lxml.html.clean.clean_html(response.get_data()) # not tested yet ? put in new EtreeCleanHandler
            #self.element = etree.HTML(response.get_data())
            tag_soup = response.get_data()
            try:
                self.element = lxml.html.fromstring(tag_soup)
                ignore = etree.tostring(self.element, encoding=unicode) # check the unicode entity conversion has worked
            except (UnicodeDecodeError, etree.XMLSyntaxError):
                self.element = lxml.html.soupparser.fromstring(tag_soup) # fall back to beautiful soup if there is an error    
            response.set_data(etree.tostring(self.element, pretty_print=True, method="html"))      
        return response


#base = scraperwiki.utils.swimport("openlylocal_base_scraper")
# this is a set of base classes intended to be subclassed and used by Openly Local planning application scrapers

# the actual work is done in the run() function of the BaseScraper

import scraperwiki
from datetime import timedelta
from datetime import date
from datetime import datetime
import time
import re
#import DateParser
from BeautifulSoup import BeautifulSoup
import unittest

#util = scraperwiki.utils.swimport("utility_library")
#scrapemark = scraperwiki.utils.swimport("scrapemark_09")

class BaseScraper(): # scraper template class to be subclassed by all children

    # default settings for all scrapers
    ID_ORDER = 'rowid asc' # defines order for id only records to return the most recent records first - example 'uid desc' or 'url desc'
    START_SEQUENCE = ''
    TABLE_NAME = 'swdata'
    DATA_START_MARKER = 'earliest'
    DATA_END_MARKER = 'latest'
    MAX_ID_BATCH = 600 # max application ids to fetch in one go
    MAX_UPDATE_BATCH = 350 # max application details to scrape in one go
    STABLE_INTERVAL = 60 # number of days before application detail is considered stable
    DEBUG = False
    HEADERS = None
    PROXY = ''
    JSESS_REGEX = re.compile(r';jsessionid=\w*')
    TIMEOUT = 30

    request_date_format = '%d/%m/%Y'

    # scrapemark config items to be provided in children
    scrape_data_block = "" # captures HTML block encompassing all fields to be gathered
    scrape_min_data = "" # the minimum acceptable valid dataset on an application page
    scrape_optional_data = "" # other optional parameters that can appear on an application page

    def __init__(self, table_name = None):
        self.br, self.handler, self.cj = get_browser(self.HEADERS, '', self.PROXY)
        if table_name:
            self.TABLE_NAME = table_name
        if self.TABLE_NAME != 'swdata':
            self.DATA_START_MARKER = 'earliest-' + self.TABLE_NAME
            self.DATA_END_MARKER = 'latest-' + self.TABLE_NAME

    # optionally try to get a batch of missing early IDs back to start of the sequence
    def gather_early_ids (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if current_earliest_sequence and current_earliest_sequence > self.START_SEQUENCE: # only takes place when some current data has been gathered
            earliest, latest, count = self.gather_ids(self.START_SEQUENCE, current_earliest_sequence)
            scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
            if latest and not current_latest_sequence:
                scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
            print "Gathered " + str(count) + " early ids from " + str(earliest) + " to " +  str(latest)
        elif current_earliest_sequence:
            print "Gathered no early ids: earliest (" + str(current_earliest_sequence) + ") <= target (" +  str(self.START_SEQUENCE) + ")"
        
    # always make an attempt to get some current IDs from the most recent part of the sequence
    def gather_current_ids (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if not current_latest_sequence: # set up the swvariables table by saving something
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, None)
        earliest, latest, count = self.gather_ids(current_latest_sequence)
        scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
        if not current_earliest_sequence:
            scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
        print "Gathered " + str(count) + " current ids from " + str(earliest) + " to " +  str(latest)

    # optionally try to get a batch of missing early IDs back to start of the sequence
    def gather_early_ids2 (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if current_earliest_sequence and current_earliest_sequence > self.START_SEQUENCE: # only takes place when some current data has been gathered
            earliest, latest, count = self.gather_ids2(self.START_SEQUENCE, current_earliest_sequence)
            if count:
                scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
                if not current_latest_sequence:
                    scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
                print "Gathered %d early ids from %s to %s" % (count, earliest, latest)
            else:
                print "Warning - gathered no early ids before %s" % latest
        elif current_earliest_sequence:
            print "Gathered no early ids: earliest (%s) <= target (%s)" % (current_earliest_sequence, self.START_SEQUENCE)
        
    # always make an attempt to get some current IDs from the most recent part of the sequence
    def gather_current_ids2 (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if not current_latest_sequence: # set up the swvariables table by saving something
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, None)
        earliest, latest, count = self.gather_ids2(current_latest_sequence)
        if count:
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
            if not current_earliest_sequence:
                scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
            print "Gathered %d current ids from %s to %s" % (count, earliest, latest)
        else:
            print "Warning - gathered no current ids later than %s" % earliest
            
    # gathers IDs, function to be implemented in the children
    def gather_ids (self, sequence_from, sequence_to):
        return '', '', 0

    # gathers IDs, function to be implemented in the children
    def gather_ids2 (self, sequence_from, sequence_to):
        return '', '', 0

    # try to fill the application detail in any empty records
    def populate_missing_applications(self):
        try:
            result = scraperwiki.sqlite.select("count(*) as count, max(rowid) as max, min(rowid) as min from " + self.TABLE_NAME + " where date_scraped is null")
            missing_count = int(result[0]['count'])
            maxr = int(result[0]['max'])
            minr = int(result[0]['min'])
        except:
            missing_count = 0; maxr = 0; minr = 0
        try:
            missing_applications = scraperwiki.sqlite.select("""
                * from """ + self.TABLE_NAME + " where date_scraped is null order by " + self.ID_ORDER + """
                limit """ + str(self.MAX_UPDATE_BATCH))
            scraperwiki.sqlite.execute("create index if not exists date_scraped_manual_index on " + self.TABLE_NAME + " (date_scraped)")
            scraperwiki.sqlite.execute("create index if not exists start_date_manual_index on " + self.TABLE_NAME + " (start_date)")
        except:
            missing_applications = scraperwiki.sqlite.select("""
                * from """ + self.TABLE_NAME + " order by " + self.ID_ORDER + """
                limit """ + str(self.MAX_UPDATE_BATCH))
        count = 0
        for applic in missing_applications:
            if self.update_application_detail(applic):
                count = count + 1
        print "Populated " + str(count) + " empty applications (out of " + str(len(missing_applications)) + " tried and " + str(missing_count) + " found)", maxr, minr
        if count == 0 and len(missing_applications) == self.MAX_UPDATE_BATCH:
            print "First bad empty application:", missing_applications[0]['uid']
                
    # always update the details of the most current applications not previously scraped today
    def update_current_applications(self):
        cutoff_date = date.today() - timedelta(days=self.STABLE_INTERVAL)
        current_test = """
        (date_scraped is not null and date_scraped < '""" + date.today().strftime(ISO8601_DATE) + """') and
        (start_date is null or start_date > '""" + cutoff_date.strftime(ISO8601_DATE) + "')"
        #print current_test
        try:
            result = scraperwiki.sqlite.select("count(*) as count from " + self.TABLE_NAME + " where " + current_test)
            update_count = int(result[0]['count'])
        except:
            update_count = 0; maxr = 0; minr = 0
        current_applications = scraperwiki.sqlite.select("* from " + self.TABLE_NAME + " where " + current_test + " order by date_scraped asc limit " + str(self.MAX_UPDATE_BATCH))
        count = 0
        for applic in current_applications:
            if self.update_application_detail(applic):
                count = count + 1
        print "Updated " + str(count) + " other current applications (out of " + str(len(current_applications)) + " tried and " + str(update_count) + " found)" 

    # fetches and stores the details of one application
    def update_application_detail(self, applic):
        result = None
        if applic.get('url'):
            result = self.get_detail_from_url(applic['url'])
        if not result:
            result = self.get_detail_from_uid(applic['uid'])
        if result:
            applic.update(result)
            if applic.get('date_received') and applic.get('date_validated'):
                if applic['date_received'] < applic['date_validated']:
                    applic['start_date'] = applic['date_received']
                else:
                    applic['start_date'] = applic['date_validated']
            elif applic.get('date_received'):
                applic['start_date'] = applic['date_received']
            elif applic.get('date_validated'):
                applic['start_date'] = applic['date_validated']
            applic['date_scraped'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            scraperwiki.sqlite.save(unique_keys=['uid'], data=applic, table_name=self.TABLE_NAME)
            return True
        else:
            if self.DEBUG:
                print "Cannot update details for:", applic
            if self.is_zombie(applic['uid']):
                scraperwiki.sqlite.execute("delete from %s where uid = '%s'" % (self.TABLE_NAME, applic['uid']))
                scraperwiki.sqlite.commit()
                print 'Deleted', applic['uid']
            return False

    # tests for zombie applications (that don't lead anywhere) using the uid, to be implemented in the children
    def is_zombie(self, uid):
        return False

    # get application data using the UID, to be implemented in the children
    def get_detail_from_uid(self, uid):
        return None

    # scrape detailed information on one record via its access URL
    def get_detail_from_url (self, url):
        if self.DEBUG: start = time.time()
        try:
            response = self.br.open(url, None, self.TIMEOUT) # a shortish timeout, as we then fall back via the uid if it fails
            html = response.read()
            url = response.geturl()
            if self.DEBUG:
                print "Html obtained from url:", html
        except:
            if self.DEBUG: raise
            else: return None
        result = self.get_detail(html, url)
        if self.DEBUG:
            print "Secs to fetch detail from url and process:", time.time() - start
        return result

    # scrape detailed information on one record given its HTML and URL
    def get_detail (self, html, url, scrape_data_block = None, scrape_min_data = None, scrape_optional_data = []):
        # use class defaults if none supplied
        scrape_data_block = scrape_data_block or self.scrape_data_block
        scrape_min_data = scrape_min_data or self.scrape_min_data
        scrape_optional_data = scrape_optional_data or self.scrape_optional_data
        result = scrape(scrape_data_block, html, url)
        if result and result.get('block'):
            data_block = result['block']
            if self.DEBUG:
                print "Scraped data block:", data_block
            result = scrape(scrape_min_data, data_block, url)
            if self.DEBUG:
                print "Scraped min data:", result
            if result:
                for i in scrape_optional_data:
                    next_val = scrape(i, data_block, url)
                    if next_val:
                        result.update(next_val)
                self.clean_record(result)
                return result
            else:
                return None
        else:
            return None

    # post process a scraped record: parses dates, converts to ISO8601 format, strips spaces, tags etc
    def clean_record (self, record):
        if self.DEBUG: print "Raw record", record
        for k, v in record.items(): 
            if v:
                if isinstance(v, list):
                    v = ' '.join(v)

                if not GAPS_REGEX.sub('', v): # first test for and remove any fields with space only strings - see dates below
                    v = None
                elif k == 'uid':
                    v = GAPS_REGEX.sub('', v) # strip any spaces in uids
                elif k == 'url' or k.endswith('_url'):
                    text = GAPS_REGEX.sub('', v) # strip any spaces in urls
                    v = self.JSESS_REGEX.sub('', text) # strip any jsessionid parameter
                elif k.endswith('_date') or k.startswith('date_'):
                    text = GAPS_REGEX.sub(' ', v) # normalise any internal space (allows date conversion to handle non-breakable spaces)
                    try: # note bug: the date parser turns an all spaces string into today's date
                        dt = DateParser.parse(text, dayfirst=True).date()
                        v = dt.strftime(ISO8601_DATE)
                    except:
                        v = None # badly formatted dates are stripped out
                else:
                    text = TAGS_REGEX.sub(' ', v) # replace any html tag content with spaces
                    try:
                        text = BeautifulSoup(text, convertEntities="html").contents[0].string
                        # use beautiful soup to convert html entities to unicode strings
                    except:
                        pass
                    text = GAPS_REGEX.sub(' ', text) # normalise any internal space
                    v = text.strip() # strip leading and trailing space
            if not v: # delete if the cleaned record is empty
                del record[k]
            else:
                record[k] = v
        if self.DEBUG: print "Cleaned record", record

    # post process a set of uid/url records: strips spaces in the uid etc - now uses clean_record above
    def clean_ids (self, records):
        for record in records:
            record = self.clean_record(record)

    # main run function for all scrapers
    def run (self):
        self.gather_current_ids2()
        self.gather_early_ids2()
        self.populate_missing_applications()
        self.update_current_applications()

    # care = reset scraping by zeroing sequence counters
    def reset (self, earliest = None, latest = None):
        scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
        scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
        earliest = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        latest = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        print "Successfuly reset the sequence counters for " + self.TABLE_NAME + ": earliest = " + str(earliest) + ", latest = " + str(latest)

    # care = completely clear the current scraped data
    def clear_all (self):
        scraperwiki.sqlite.execute("delete from swvariables where name = '" + self.DATA_START_MARKER + "' or name = '" + self.DATA_END_MARKER + "'")
        scraperwiki.sqlite.execute("drop table if exists " + self.TABLE_NAME)
        scraperwiki.sqlite.commit()
        print "Successfuly cleared out " + self.TABLE_NAME

    # replace the current planning data with all the data from another planning scraper
    def replace_all_with(self, scraper_name = None, remote_table = None):
        if not remote_table:
            remote_table = self.TABLE_NAME
        if not scraper_name and remote_table == self.TABLE_NAME:
            print "Cannot replace the scraped data with itself"
            return
        scraper = ''
        if scraper_name:
            try:
                scraper = 'scraper.'
                scraperwiki.sqlite.attach(scraper_name, 'scraper') 
                scraper_name = scraper_name + ':'
            except:
                pass
        else:
            scraper_name = ''
        if remote_table != 'swdata':
            remote_start_marker = 'earliest-' + remote_table
            remote_end_marker = 'latest-' + remote_table
        else:
            remote_start_marker = 'earliest'
            remote_end_marker = 'latest'
        result = scraperwiki.sqlite.select("* from " + scraper + "swvariables where name = '" + remote_start_marker + "'")
        earliest = result[0]
        result = scraperwiki.sqlite.select("* from " + scraper + "swvariables where name = '" + remote_end_marker + "'")
        latest = result[0]
        earliest['name'] = self.DATA_START_MARKER
        latest['name'] = self.DATA_END_MARKER
        scraperwiki.sqlite.save(unique_keys=['name'], data=earliest, table_name='swvariables') 
        scraperwiki.sqlite.save(unique_keys=['name'], data=latest, table_name='swvariables')
        try:
            scraperwiki.sqlite.execute("drop table if exists " + self.TABLE_NAME)
        except:
            pass
        scraperwiki.sqlite.execute("create table if not exists " + self.TABLE_NAME + " as select * from " + scraper + remote_table) # indices?
        scraperwiki.sqlite.commit()
        result = scraperwiki.sqlite.select("count(*) as count from " + self.TABLE_NAME)
        count = result[0]['count']
        earliest = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        latest = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        print "Successfuly cloned " + self.TABLE_NAME + " from " + scraper_name + remote_table + ": count = " + str(count) + ", earliest = " + earliest + ", latest = " + latest
        
# Telford, Nuneaton, Brighton, East Sussex, Braintree, Hyndburn, South Hams, Kirklees, Ceredigion, Monmouthshire
# Redcar/Cleveland, Glamorgan, North Lincs, Nottinghamshire,  ... and more ...
class DateScraper(BaseScraper): # for those sites that can return applications between two arbitrary search dates 

    START_SEQUENCE = '2000-01-01' # gathers id data by working backwards from the current date towards this one
    BATCH_DAYS = 14 # batch size for each scrape - number of days to gather to produce at least one result each time
    MIN_DAYS = 14 # min number of days to get when gathering current ids

    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather backwards from today towards 'from', returning the real date range found
    def gather_ids (self, sequence_from = None, sequence_to = None):
        original_current_target = None
        if not sequence_to: # gathering current dates
            get_current_dates = True
            current_period_begins = date.today() - timedelta(days=self.MIN_DAYS)
            start = date.today()
            original_current_target = get_dt(sequence_from, ISO8601_DATE)
            if original_current_target:
                target = original_current_target
                if target < current_period_begins:
                    start = target + timedelta(days=self.MIN_DAYS)
                elif target > current_period_begins:
                    target = current_period_begins
            else:
                target = current_period_begins
        else: # gathering early dates
            get_current_dates = False
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start 
        while (get_current_dates or count < self.MAX_ID_BATCH) and current > target: # only take account of max batch if gathering early dates
            next = current - timedelta(days=self.BATCH_DAYS)
            result = self.get_id_batch(next, current)
            if result:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + next.strftime(ISO8601_DATE) + " to " + current.strftime(ISO8601_DATE)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                if self.DEBUG: print sequence_from, sequence_to
                if get_current_dates: # latest applications are updated on the spot
                    for i in result:
                        self.update_application_detail(i)
                count = count + len(result)
                current = next - timedelta(days=1)
            else:
                break
        if original_current_target and current > original_current_target: # error if not gathered enough current data to fully fill data gap
            return original_current_target.strftime(ISO8601_DATE), original_current_target.strftime(ISO8601_DATE), 0
        else:
            return current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        # note 'current' date is exclusive, 'start' date is inclusive

    # Improved version of gather_ids()
    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from' towards today, returning the real date range found
    # always expects to gather some data - returned count of zero is an error
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        if not sequence_to: # gathering current dates - going forward
            move_forward = True
            target = date.today()
            start = get_dt(sequence_from, ISO8601_DATE)
            current_period_begins = target - timedelta(days=self.MIN_DAYS)
            if not start or start > current_period_begins:
                start = current_period_begins
            start = start + timedelta(days=1) # begin one day after supplied date
        else: # gathering early dates - going backward
            move_forward = False
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            else:
                start = start - timedelta(days=1) # begin one day before supplied date
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and ((not move_forward and current >= target) or (move_forward and current <= target)): 
            if not move_forward:
                next = current - timedelta(days=self.BATCH_DAYS-1)
                result = self.get_id_batch(next, current)
            else:
                next = current + timedelta(days=self.BATCH_DAYS-1)
                result = self.get_id_batch(current, next)
            if result:
                if self.DEBUG:
                    if not move_forward:
                        print "Storing " + str(len(result)) + " ids gathered from " + next.strftime(ISO8601_DATE) + " to " + current.strftime(ISO8601_DATE)
                    else:
                        print "Storing " + str(len(result)) + " ids gathered from " + current.strftime(ISO8601_DATE) + " to " + next.strftime(ISO8601_DATE)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                count = count + len(result)
                ok_current = next
                if not move_forward:
                    current = next - timedelta(days=1)
                else:
                    current = next + timedelta(days=1)
                    for i in result:
                        self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        else:
            if ok_current > date.today():
                ok_current = date.today()
            return start.strftime(ISO8601_DATE), ok_current.strftime(ISO8601_DATE), count

    # retrieves a batch of IDs betwen two sequence dates, to be implemented in the children
    # NB dates should be inclusive
    def get_id_batch (self, date_from, date_to):
        return [] # empty or None is an invalid result - means try again next time

# annual = Weymouth - now date scraper - see dorsetforyou
# monthly = Wokingham, Sedgemoor, Wychavon, Peak District
# 20 days = Gosport
# weekly = Kensington, Tower Hamlets, West Lothian, Colchester, Nottingham, Stevenage, Hastings, Copeland (PDFs), Swale (some PDFs), Isle of Man, Solihull, Exmoor
# weekly and monthly = Cotswold
class PeriodScraper(BaseScraper): # for those sites that return a fixed period of applications (weekly, monthly) around a search date

    START_SEQUENCE = '2000-01-01' # gathers id data by working backwards from the current date towards this one
    #PERIOD_TYPE = 'Month' # calendar month including the specified date
    #PERIOD_TYPE = 'Saturday' # 7 day week ending on the specified day and including the supplied date
    #PERIOD_TYPE = '-Saturday' # 7 day week beginning on the specified day and including the supplied date
    #PERIOD_TYPE = '14' # 2 weeks beginning on the specified date
    #PERIOD_TYPE = '-14' # 2 weeks ending on the specified date
    MIN_DAYS = 14 # min number of days to get when gathering current ids

    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather backwards from today towards 'from', returning the real date range found
    def gather_ids (self, sequence_from = None, sequence_to = None):
        original_current_target = None
        if not sequence_to: # gathering current dates
            get_current_dates = True
            current_period_begins = date.today() - timedelta(days=self.MIN_DAYS)
            start = date.today()
            original_current_target = get_dt(sequence_from, ISO8601_DATE)
            if original_current_target:
                target = original_current_target
                if target < current_period_begins:
                    start = target + timedelta(days=self.MIN_DAYS)
                elif target > current_period_begins:
                    target = current_period_begins
            else:
                target = current_period_begins
        else: # gathering early dates
            get_current_dates = False
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        while (get_current_dates or count < self.MAX_ID_BATCH) and current > target: # only take account of max batch if gathering early dates
            result, from_dt, to_dt = self.get_id_period(current) 
            if from_dt and to_dt:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_dt) + " to " + str(to_dt)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    if self.DEBUG: print sequence_from, sequence_to
                    if get_current_dates: # latest applications are updated on the spot
                        for i in result:
                            self.update_application_detail(i)
                    count = count + len(result)
                current = from_dt - timedelta(days=1)
            else:
                break
        if original_current_target and current > original_current_target: # error if not gathered enough current data to fully fill data gap
            return original_current_target.strftime(ISO8601_DATE), original_current_target.strftime(ISO8601_DATE), 0
        else:
            return current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count

    # Improved version of gather_ids()
    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from' towards today, returning the real date range found
    # always expects to gather some data - returned count of zero is an error
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        if not sequence_to: # gathering current dates - going forward
            move_forward = True
            target = date.today()
            start = get_dt(sequence_from, ISO8601_DATE)
            current_period_begins = target - timedelta(days=self.MIN_DAYS)
            if not start or start > current_period_begins:
                start = current_period_begins
            start = start + timedelta(days=1) # begin one day after supplied date
        else: # gathering early dates - going backward
            move_forward = False
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            else:
                start = start - timedelta(days=1) # begin one day before supplied date
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and ((not move_forward and current > target) or (move_forward and current < target)): 
            result, from_dt, to_dt = self.get_id_period(current)
            if from_dt and to_dt:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_dt) + " to " + str(to_dt)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    count = count + len(result)
                if not move_forward: # if moving backward continue even with no result, as some periods might be legitimately empty?
                    ok_current = from_dt
                    current = from_dt - timedelta(days=1)
                else:
                    if not result: break # however if moving forward we expect to get some data on each scrape
                    ok_current = to_dt
                    current = to_dt + timedelta(days=1)
                    for i in result:
                        self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        else:
            if ok_current > date.today():
                ok_current = date.today()
            return start.strftime(ISO8601_DATE), ok_current.strftime(ISO8601_DATE), count

    # retrieves a batch of IDs around one date, to be implemented in the children
    # can return zero records if no data found for the requested period, but applicable (inclusive) dates must be returned
    def get_id_period (self, date):
        return [], None, None # invalid if return dates are not set - means try again next time

# YYYYNNNN (year + 4/5 digit sequence number) = Hereford, Tewkesbury, Walsall, Waverley, Rotherham, Ashfield, Jersey, Pembrokeshire Coast
# incrementing numeric ids = Isle of Wight, Surrey, Scilly Isles, Purbeck, Hampshire, 
# fixed one page lists = Derbyshire, Northamptonshire
# old ones not working now = Merthyr Tydfil, Newport
# now weekly = Solihull
class ListScraper(BaseScraper): # for those sites that return a full paged list of all applications 

    START_SEQUENCE = 1 # gathering back to this record number 
    PAGE_SIZE = 25
    START_POINT = 1 # the default first scrape point if the scraper is empty (only required if max_sequence is not implemented)
    MIN_RECS = 50 # min number of records to get when gathering current ids

    # process id batches working through a numeric sequence
    # (where the earliest record is nominally record number 1)
    # note 'from' is smaller than 'to'
    def gather_ids (self, sequence_from = None, sequence_to = None):
        start = sequence_to
        target = sequence_from
        if target is not None and target < self.START_SEQUENCE: # target can legitimately be null (when no data has been gathered before)
            target = self.START_SEQUENCE
        count = 0
        current = start
        while count < self.MAX_ID_BATCH and (current is None or target is None or current > target):
            result, from_rec, to_rec = self.get_id_records(target, current) # both can be null (when no data has been gathered before)
            if not start: start = to_rec
            if not current: current = to_rec
            if not target: target = self.START_SEQUENCE
            if from_rec and to_rec:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_rec) + " to " + str(to_rec)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                if sequence_from and not sequence_to: # latest applications are updated on the spot
                    for i in result:
                        self.update_application_detail(i)
                count = count + len(result)
                current = from_rec - 1
            else:
                break
        return current, start, count

    # Improved version of gather_ids()
    # process id batches working through a numeric sequence (where the earliest record is nominally record number 1)
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real sequence range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from', returning the real sequence range found
    # note 'from' is always smaller than 'to'
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        max = self.get_max_sequence()
        if not sequence_to: # gathering current sequence numbers - going forward
            move_forward = True
            target = max
            start = sequence_from
            if max:
                current_period_begins = max - self.MIN_RECS
                if not start or start > current_period_begins:
                    start = current_period_begins
            if start:
                start = start + 1 # begin one after supplied sequence number
            else:
                start = self.START_POINT
        else: # gathering early sequence numbers - going backward
            move_forward = False
            start = sequence_to
            target = sequence_from
            if max and (not start or start > max):
                start = max
            else:
                start = start - 1 # begin one before supplied sequence number
            if not target or target < self.START_SEQUENCE:
                target = self.START_SEQUENCE
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and (not current or not target or (not move_forward and current > target) or (move_forward and current < target)): 
            result, from_rec, to_rec = self.get_id_records2(current, move_forward)
            if not start: 
                if not move_forward:
                    start = to_rec
                else:
                    start = from_rec
                ok_current = start
            if from_rec and to_rec:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_rec) + " to " + str(to_rec)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    count = count + len(result)
                    if not move_forward:
                        ok_current = from_rec
                        current = from_rec - 1
                    else:
                        ok_current = to_rec
                        current = to_rec + 1
                        for i in result:
                            self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current, start, count
        else:
            return start, ok_current, count

    # returns current max record number - can be overridden in the children
    def get_max_sequence (self):
        return scraperwiki.sqlite.get_var(self.DATA_END_MARKER)

    # retrieves records between two sequence numbers - to be defined in the children
    # can return zero records if no data found for the requested interval, but applicable (inclusive) sequences must be returned
    def get_id_records (self, from_rec, to_rec):
        return [], None, None # invalid if return sequences are not set - means try again next time


# this is a set of base classes intended to be subclassed and used by Openly Local planning application scrapers

# the actual work is done in the run() function of the BaseScraper

import scraperwiki
from datetime import timedelta
from datetime import date
from datetime import datetime
import time
import re
#import DateParser
from BeautifulSoup import BeautifulSoup
import unittest

#util = scraperwiki.utils.swimport("utility_library")
#scrapemark = scraperwiki.utils.swimport("scrapemark_09")

class BaseScraper(): # scraper template class to be subclassed by all children

    # default settings for all scrapers
    ID_ORDER = 'rowid asc' # defines order for id only records to return the most recent records first - example 'uid desc' or 'url desc'
    START_SEQUENCE = ''
    TABLE_NAME = 'swdata'
    DATA_START_MARKER = 'earliest'
    DATA_END_MARKER = 'latest'
    MAX_ID_BATCH = 600 # max application ids to fetch in one go
    MAX_UPDATE_BATCH = 350 # max application details to scrape in one go
    STABLE_INTERVAL = 60 # number of days before application detail is considered stable
    DEBUG = False
    HEADERS = None
    PROXY = ''
    JSESS_REGEX = re.compile(r';jsessionid=\w*')
    TIMEOUT = 30

    request_date_format = '%d/%m/%Y'

    # scrapemark config items to be provided in children
    scrape_data_block = "" # captures HTML block encompassing all fields to be gathered
    scrape_min_data = "" # the minimum acceptable valid dataset on an application page
    scrape_optional_data = "" # other optional parameters that can appear on an application page

    def __init__(self, table_name = None):
        self.br, self.handler, self.cj = get_browser(self.HEADERS, '', self.PROXY)
        if table_name:
            self.TABLE_NAME = table_name
        if self.TABLE_NAME != 'swdata':
            self.DATA_START_MARKER = 'earliest-' + self.TABLE_NAME
            self.DATA_END_MARKER = 'latest-' + self.TABLE_NAME

    # optionally try to get a batch of missing early IDs back to start of the sequence
    def gather_early_ids (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if current_earliest_sequence and current_earliest_sequence > self.START_SEQUENCE: # only takes place when some current data has been gathered
            earliest, latest, count = self.gather_ids(self.START_SEQUENCE, current_earliest_sequence)
            scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
            if latest and not current_latest_sequence:
                scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
            print "Gathered " + str(count) + " early ids from " + str(earliest) + " to " +  str(latest)
        elif current_earliest_sequence:
            print "Gathered no early ids: earliest (" + str(current_earliest_sequence) + ") <= target (" +  str(self.START_SEQUENCE) + ")"
        
    # always make an attempt to get some current IDs from the most recent part of the sequence
    def gather_current_ids (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if not current_latest_sequence: # set up the swvariables table by saving something
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, None)
        earliest, latest, count = self.gather_ids(current_latest_sequence)
        scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
        if not current_earliest_sequence:
            scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
        print "Gathered " + str(count) + " current ids from " + str(earliest) + " to " +  str(latest)

    # optionally try to get a batch of missing early IDs back to start of the sequence
    def gather_early_ids2 (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if current_earliest_sequence and current_earliest_sequence > self.START_SEQUENCE: # only takes place when some current data has been gathered
            earliest, latest, count = self.gather_ids2(self.START_SEQUENCE, current_earliest_sequence)
            if count:
                scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
                if not current_latest_sequence:
                    scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
                print "Gathered %d early ids from %s to %s" % (count, earliest, latest)
            else:
                print "Warning - gathered no early ids before %s" % latest
        elif current_earliest_sequence:
            print "Gathered no early ids: earliest (%s) <= target (%s)" % (current_earliest_sequence, self.START_SEQUENCE)
        
    # always make an attempt to get some current IDs from the most recent part of the sequence
    def gather_current_ids2 (self):
        current_earliest_sequence = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        current_latest_sequence = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        if not current_latest_sequence: # set up the swvariables table by saving something
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, None)
        earliest, latest, count = self.gather_ids2(current_latest_sequence)
        if count:
            scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
            if not current_earliest_sequence:
                scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
            print "Gathered %d current ids from %s to %s" % (count, earliest, latest)
        else:
            print "Warning - gathered no current ids later than %s" % earliest
            
    # gathers IDs, function to be implemented in the children
    def gather_ids (self, sequence_from, sequence_to):
        return '', '', 0

    # gathers IDs, function to be implemented in the children
    def gather_ids2 (self, sequence_from, sequence_to):
        return '', '', 0

    # try to fill the application detail in any empty records
    def populate_missing_applications(self):
        try:
            result = scraperwiki.sqlite.select("count(*) as count, max(rowid) as max, min(rowid) as min from " + self.TABLE_NAME + " where date_scraped is null")
            missing_count = int(result[0]['count'])
            maxr = int(result[0]['max'])
            minr = int(result[0]['min'])
        except:
            missing_count = 0; maxr = 0; minr = 0
        try:
            missing_applications = scraperwiki.sqlite.select("""
                * from """ + self.TABLE_NAME + " where date_scraped is null order by " + self.ID_ORDER + """
                limit """ + str(self.MAX_UPDATE_BATCH))
            scraperwiki.sqlite.execute("create index if not exists date_scraped_manual_index on " + self.TABLE_NAME + " (date_scraped)")
            scraperwiki.sqlite.execute("create index if not exists start_date_manual_index on " + self.TABLE_NAME + " (start_date)")
        except:
            missing_applications = scraperwiki.sqlite.select("""
                * from """ + self.TABLE_NAME + " order by " + self.ID_ORDER + """
                limit """ + str(self.MAX_UPDATE_BATCH))
        count = 0
        for applic in missing_applications:
            if self.update_application_detail(applic):
                count = count + 1
        print "Populated " + str(count) + " empty applications (out of " + str(len(missing_applications)) + " tried and " + str(missing_count) + " found)", maxr, minr
        if count == 0 and len(missing_applications) == self.MAX_UPDATE_BATCH:
            print "First bad empty application:", missing_applications[0]['uid']
                
    # always update the details of the most current applications not previously scraped today
    def update_current_applications(self):
        cutoff_date = date.today() - timedelta(days=self.STABLE_INTERVAL)
        current_test = """
        (date_scraped is not null and date_scraped < '""" + date.today().strftime(ISO8601_DATE) + """') and
        (start_date is null or start_date > '""" + cutoff_date.strftime(ISO8601_DATE) + "')"
        #print current_test
        try:
            result = scraperwiki.sqlite.select("count(*) as count from " + self.TABLE_NAME + " where " + current_test)
            update_count = int(result[0]['count'])
        except:
            update_count = 0; maxr = 0; minr = 0
        current_applications = scraperwiki.sqlite.select("* from " + self.TABLE_NAME + " where " + current_test + " order by date_scraped asc limit " + str(self.MAX_UPDATE_BATCH))
        count = 0
        for applic in current_applications:
            if self.update_application_detail(applic):
                count = count + 1
        print "Updated " + str(count) + " other current applications (out of " + str(len(current_applications)) + " tried and " + str(update_count) + " found)" 

    # fetches and stores the details of one application
    def update_application_detail(self, applic):
        result = None
        if applic.get('url'):
            result = self.get_detail_from_url(applic['url'])
        if not result:
            result = self.get_detail_from_uid(applic['uid'])
        if result:
            applic.update(result)
            if applic.get('date_received') and applic.get('date_validated'):
                if applic['date_received'] < applic['date_validated']:
                    applic['start_date'] = applic['date_received']
                else:
                    applic['start_date'] = applic['date_validated']
            elif applic.get('date_received'):
                applic['start_date'] = applic['date_received']
            elif applic.get('date_validated'):
                applic['start_date'] = applic['date_validated']
            applic['date_scraped'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            scraperwiki.sqlite.save(unique_keys=['uid'], data=applic, table_name=self.TABLE_NAME)
            return True
        else:
            if self.DEBUG:
                print "Cannot update details for:", applic
            if self.is_zombie(applic['uid']):
                scraperwiki.sqlite.execute("delete from %s where uid = '%s'" % (self.TABLE_NAME, applic['uid']))
                scraperwiki.sqlite.commit()
                print 'Deleted', applic['uid']
            return False

    # tests for zombie applications (that don't lead anywhere) using the uid, to be implemented in the children
    def is_zombie(self, uid):
        return False

    # get application data using the UID, to be implemented in the children
    def get_detail_from_uid(self, uid):
        return None

    # scrape detailed information on one record via its access URL
    def get_detail_from_url (self, url):
        if self.DEBUG: start = time.time()
        try:
            response = self.br.open(url, None, self.TIMEOUT) # a shortish timeout, as we then fall back via the uid if it fails
            html = response.read()
            url = response.geturl()
            if self.DEBUG:
                print "Html obtained from url:", html
        except:
            if self.DEBUG: raise
            else: return None
        result = self.get_detail(html, url)
        if self.DEBUG:
            print "Secs to fetch detail from url and process:", time.time() - start
        return result

    # scrape detailed information on one record given its HTML and URL
    def get_detail (self, html, url, scrape_data_block = None, scrape_min_data = None, scrape_optional_data = []):
        # use class defaults if none supplied
        scrape_data_block = scrape_data_block or self.scrape_data_block
        scrape_min_data = scrape_min_data or self.scrape_min_data
        scrape_optional_data = scrape_optional_data or self.scrape_optional_data
        result = scrape(scrape_data_block, html, url)
        if result and result.get('block'):
            data_block = result['block']
            if self.DEBUG:
                print "Scraped data block:", data_block
            result = scrape(scrape_min_data, data_block, url)
            if self.DEBUG:
                print "Scraped min data:", result
            if result:
                for i in scrape_optional_data:
                    next_val = scrape(i, data_block, url)
                    if next_val:
                        result.update(next_val)
                self.clean_record(result)
                return result
            else:
                return None
        else:
            return None

    # post process a scraped record: parses dates, converts to ISO8601 format, strips spaces, tags etc
    def clean_record (self, record):
        if self.DEBUG: print "Raw record", record
        for k, v in record.items(): 
            if v:
                if isinstance(v, list):
                    v = ' '.join(v)

                if not GAPS_REGEX.sub('', v): # first test for and remove any fields with space only strings - see dates below
                    v = None
                elif k == 'uid':
                    v = GAPS_REGEX.sub('', v) # strip any spaces in uids
                elif k == 'url' or k.endswith('_url'):
                    text = GAPS_REGEX.sub('', v) # strip any spaces in urls
                    v = self.JSESS_REGEX.sub('', text) # strip any jsessionid parameter
                elif k.endswith('_date') or k.startswith('date_'):
                    text = GAPS_REGEX.sub(' ', v) # normalise any internal space (allows date conversion to handle non-breakable spaces)
                    try: # note bug: the date parser turns an all spaces string into today's date
                        dt = DateParser.parse(text, dayfirst=True).date()
                        v = dt.strftime(ISO8601_DATE)
                    except:
                        v = None # badly formatted dates are stripped out
                else:
                    text = TAGS_REGEX.sub(' ', v) # replace any html tag content with spaces
                    try:
                        text = BeautifulSoup(text, convertEntities="html").contents[0].string
                        # use beautiful soup to convert html entities to unicode strings
                    except:
                        pass
                    text = GAPS_REGEX.sub(' ', text) # normalise any internal space
                    v = text.strip() # strip leading and trailing space
            if not v: # delete if the cleaned record is empty
                del record[k]
            else:
                record[k] = v
        if self.DEBUG: print "Cleaned record", record

    # post process a set of uid/url records: strips spaces in the uid etc - now uses clean_record above
    def clean_ids (self, records):
        for record in records:
            record = self.clean_record(record)

    # main run function for all scrapers
    def run (self):
        self.gather_current_ids2()
        self.gather_early_ids2()
        self.populate_missing_applications()
        self.update_current_applications()

    # care = reset scraping by zeroing sequence counters
    def reset (self, earliest = None, latest = None):
        scraperwiki.sqlite.save_var(self.DATA_START_MARKER, earliest)
        scraperwiki.sqlite.save_var(self.DATA_END_MARKER, latest)
        earliest = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        latest = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        print "Successfuly reset the sequence counters for " + self.TABLE_NAME + ": earliest = " + str(earliest) + ", latest = " + str(latest)

    # care = completely clear the current scraped data
    def clear_all (self):
        scraperwiki.sqlite.execute("delete from swvariables where name = '" + self.DATA_START_MARKER + "' or name = '" + self.DATA_END_MARKER + "'")
        scraperwiki.sqlite.execute("drop table if exists " + self.TABLE_NAME)
        scraperwiki.sqlite.commit()
        print "Successfuly cleared out " + self.TABLE_NAME

    # replace the current planning data with all the data from another planning scraper
    def replace_all_with(self, scraper_name = None, remote_table = None):
        if not remote_table:
            remote_table = self.TABLE_NAME
        if not scraper_name and remote_table == self.TABLE_NAME:
            print "Cannot replace the scraped data with itself"
            return
        scraper = ''
        if scraper_name:
            try:
                scraper = 'scraper.'
                scraperwiki.sqlite.attach(scraper_name, 'scraper') 
                scraper_name = scraper_name + ':'
            except:
                pass
        else:
            scraper_name = ''
        if remote_table != 'swdata':
            remote_start_marker = 'earliest-' + remote_table
            remote_end_marker = 'latest-' + remote_table
        else:
            remote_start_marker = 'earliest'
            remote_end_marker = 'latest'
        result = scraperwiki.sqlite.select("* from " + scraper + "swvariables where name = '" + remote_start_marker + "'")
        earliest = result[0]
        result = scraperwiki.sqlite.select("* from " + scraper + "swvariables where name = '" + remote_end_marker + "'")
        latest = result[0]
        earliest['name'] = self.DATA_START_MARKER
        latest['name'] = self.DATA_END_MARKER
        scraperwiki.sqlite.save(unique_keys=['name'], data=earliest, table_name='swvariables') 
        scraperwiki.sqlite.save(unique_keys=['name'], data=latest, table_name='swvariables')
        try:
            scraperwiki.sqlite.execute("drop table if exists " + self.TABLE_NAME)
        except:
            pass
        scraperwiki.sqlite.execute("create table if not exists " + self.TABLE_NAME + " as select * from " + scraper + remote_table) # indices?
        scraperwiki.sqlite.commit()
        result = scraperwiki.sqlite.select("count(*) as count from " + self.TABLE_NAME)
        count = result[0]['count']
        earliest = scraperwiki.sqlite.get_var(self.DATA_START_MARKER)
        latest = scraperwiki.sqlite.get_var(self.DATA_END_MARKER)
        print "Successfuly cloned " + self.TABLE_NAME + " from " + scraper_name + remote_table + ": count = " + str(count) + ", earliest = " + earliest + ", latest = " + latest
        
# Telford, Nuneaton, Brighton, East Sussex, Braintree, Hyndburn, South Hams, Kirklees, Ceredigion, Monmouthshire
# Redcar/Cleveland, Glamorgan, North Lincs, Nottinghamshire,  ... and more ...
class DateScraper(BaseScraper): # for those sites that can return applications between two arbitrary search dates 

    START_SEQUENCE = '2000-01-01' # gathers id data by working backwards from the current date towards this one
    BATCH_DAYS = 14 # batch size for each scrape - number of days to gather to produce at least one result each time
    MIN_DAYS = 14 # min number of days to get when gathering current ids

    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather backwards from today towards 'from', returning the real date range found
    def gather_ids (self, sequence_from = None, sequence_to = None):
        original_current_target = None
        if not sequence_to: # gathering current dates
            get_current_dates = True
            current_period_begins = date.today() - timedelta(days=self.MIN_DAYS)
            start = date.today()
            original_current_target = get_dt(sequence_from, ISO8601_DATE)
            if original_current_target:
                target = original_current_target
                if target < current_period_begins:
                    start = target + timedelta(days=self.MIN_DAYS)
                elif target > current_period_begins:
                    target = current_period_begins
            else:
                target = current_period_begins
        else: # gathering early dates
            get_current_dates = False
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start 
        while (get_current_dates or count < self.MAX_ID_BATCH) and current > target: # only take account of max batch if gathering early dates
            next = current - timedelta(days=self.BATCH_DAYS)
            result = self.get_id_batch(next, current)
            if result:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + next.strftime(ISO8601_DATE) + " to " + current.strftime(ISO8601_DATE)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                if self.DEBUG: print sequence_from, sequence_to
                if get_current_dates: # latest applications are updated on the spot
                    for i in result:
                        self.update_application_detail(i)
                count = count + len(result)
                current = next - timedelta(days=1)
            else:
                break
        if original_current_target and current > original_current_target: # error if not gathered enough current data to fully fill data gap
            return original_current_target.strftime(ISO8601_DATE), original_current_target.strftime(ISO8601_DATE), 0
        else:
            return current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        # note 'current' date is exclusive, 'start' date is inclusive

    # Improved version of gather_ids()
    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from' towards today, returning the real date range found
    # always expects to gather some data - returned count of zero is an error
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        if not sequence_to: # gathering current dates - going forward
            move_forward = True
            target = date.today()
            start = get_dt(sequence_from, ISO8601_DATE)
            current_period_begins = target - timedelta(days=self.MIN_DAYS)
            if not start or start > current_period_begins:
                start = current_period_begins
            start = start + timedelta(days=1) # begin one day after supplied date
        else: # gathering early dates - going backward
            move_forward = False
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            else:
                start = start - timedelta(days=1) # begin one day before supplied date
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and ((not move_forward and current >= target) or (move_forward and current <= target)): 
            if not move_forward:
                next = current - timedelta(days=self.BATCH_DAYS-1)
                result = self.get_id_batch(next, current)
            else:
                next = current + timedelta(days=self.BATCH_DAYS-1)
                result = self.get_id_batch(current, next)
            if result:
                if self.DEBUG:
                    if not move_forward:
                        print "Storing " + str(len(result)) + " ids gathered from " + next.strftime(ISO8601_DATE) + " to " + current.strftime(ISO8601_DATE)
                    else:
                        print "Storing " + str(len(result)) + " ids gathered from " + current.strftime(ISO8601_DATE) + " to " + next.strftime(ISO8601_DATE)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                count = count + len(result)
                ok_current = next
                if not move_forward:
                    current = next - timedelta(days=1)
                else:
                    current = next + timedelta(days=1)
                    for i in result:
                        self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        else:
            if ok_current > date.today():
                ok_current = date.today()
            return start.strftime(ISO8601_DATE), ok_current.strftime(ISO8601_DATE), count

    # retrieves a batch of IDs betwen two sequence dates, to be implemented in the children
    # NB dates should be inclusive
    def get_id_batch (self, date_from, date_to):
        return [] # empty or None is an invalid result - means try again next time

# annual = Weymouth - now date scraper - see dorsetforyou
# monthly = Wokingham, Sedgemoor, Wychavon, Peak District
# 20 days = Gosport
# weekly = Kensington, Tower Hamlets, West Lothian, Colchester, Nottingham, Stevenage, Hastings, Copeland (PDFs), Swale (some PDFs), Isle of Man, Solihull, Exmoor
# weekly and monthly = Cotswold
class PeriodScraper(BaseScraper): # for those sites that return a fixed period of applications (weekly, monthly) around a search date

    START_SEQUENCE = '2000-01-01' # gathers id data by working backwards from the current date towards this one
    #PERIOD_TYPE = 'Month' # calendar month including the specified date
    #PERIOD_TYPE = 'Saturday' # 7 day week ending on the specified day and including the supplied date
    #PERIOD_TYPE = '-Saturday' # 7 day week beginning on the specified day and including the supplied date
    #PERIOD_TYPE = '14' # 2 weeks beginning on the specified date
    #PERIOD_TYPE = '-14' # 2 weeks ending on the specified date
    MIN_DAYS = 14 # min number of days to get when gathering current ids

    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather backwards from today towards 'from', returning the real date range found
    def gather_ids (self, sequence_from = None, sequence_to = None):
        original_current_target = None
        if not sequence_to: # gathering current dates
            get_current_dates = True
            current_period_begins = date.today() - timedelta(days=self.MIN_DAYS)
            start = date.today()
            original_current_target = get_dt(sequence_from, ISO8601_DATE)
            if original_current_target:
                target = original_current_target
                if target < current_period_begins:
                    start = target + timedelta(days=self.MIN_DAYS)
                elif target > current_period_begins:
                    target = current_period_begins
            else:
                target = current_period_begins
        else: # gathering early dates
            get_current_dates = False
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        while (get_current_dates or count < self.MAX_ID_BATCH) and current > target: # only take account of max batch if gathering early dates
            result, from_dt, to_dt = self.get_id_period(current) 
            if from_dt and to_dt:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_dt) + " to " + str(to_dt)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    if self.DEBUG: print sequence_from, sequence_to
                    if get_current_dates: # latest applications are updated on the spot
                        for i in result:
                            self.update_application_detail(i)
                    count = count + len(result)
                current = from_dt - timedelta(days=1)
            else:
                break
        if original_current_target and current > original_current_target: # error if not gathered enough current data to fully fill data gap
            return original_current_target.strftime(ISO8601_DATE), original_current_target.strftime(ISO8601_DATE), 0
        else:
            return current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count

    # Improved version of gather_ids()
    # process id batches working through a date sequence
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real date range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from' towards today, returning the real date range found
    # always expects to gather some data - returned count of zero is an error
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        if not sequence_to: # gathering current dates - going forward
            move_forward = True
            target = date.today()
            start = get_dt(sequence_from, ISO8601_DATE)
            current_period_begins = target - timedelta(days=self.MIN_DAYS)
            if not start or start > current_period_begins:
                start = current_period_begins
            start = start + timedelta(days=1) # begin one day after supplied date
        else: # gathering early dates - going backward
            move_forward = False
            start = get_dt(sequence_to, ISO8601_DATE)
            target = get_dt(sequence_from, ISO8601_DATE)
            if not start or start > date.today():
                start = date.today()
            else:
                start = start - timedelta(days=1) # begin one day before supplied date
            full_sequence_begins = get_dt(self.START_SEQUENCE, ISO8601_DATE)
            if not target or target < full_sequence_begins:
                target = full_sequence_begins
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and ((not move_forward and current > target) or (move_forward and current < target)): 
            result, from_dt, to_dt = self.get_id_period(current)
            if from_dt and to_dt:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_dt) + " to " + str(to_dt)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    count = count + len(result)
                if not move_forward: # if moving backward continue even with no result, as some periods might be legitimately empty?
                    ok_current = from_dt
                    current = from_dt - timedelta(days=1)
                else:
                    if not result: break # however if moving forward we expect to get some data on each scrape
                    ok_current = to_dt
                    current = to_dt + timedelta(days=1)
                    for i in result:
                        self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current.strftime(ISO8601_DATE), start.strftime(ISO8601_DATE), count
        else:
            if ok_current > date.today():
                ok_current = date.today()
            return start.strftime(ISO8601_DATE), ok_current.strftime(ISO8601_DATE), count

    # retrieves a batch of IDs around one date, to be implemented in the children
    # can return zero records if no data found for the requested period, but applicable (inclusive) dates must be returned
    def get_id_period (self, date):
        return [], None, None # invalid if return dates are not set - means try again next time

# YYYYNNNN (year + 4/5 digit sequence number) = Hereford, Tewkesbury, Walsall, Waverley, Rotherham, Ashfield, Jersey, Pembrokeshire Coast
# incrementing numeric ids = Isle of Wight, Surrey, Scilly Isles, Purbeck, Hampshire, 
# fixed one page lists = Derbyshire, Northamptonshire
# old ones not working now = Merthyr Tydfil, Newport
# now weekly = Solihull
class ListScraper(BaseScraper): # for those sites that return a full paged list of all applications 

    START_SEQUENCE = 1 # gathering back to this record number 
    PAGE_SIZE = 25
    START_POINT = 1 # the default first scrape point if the scraper is empty (only required if max_sequence is not implemented)
    MIN_RECS = 50 # min number of records to get when gathering current ids

    # process id batches working through a numeric sequence
    # (where the earliest record is nominally record number 1)
    # note 'from' is smaller than 'to'
    def gather_ids (self, sequence_from = None, sequence_to = None):
        start = sequence_to
        target = sequence_from
        if target is not None and target < self.START_SEQUENCE: # target can legitimately be null (when no data has been gathered before)
            target = self.START_SEQUENCE
        count = 0
        current = start
        while count < self.MAX_ID_BATCH and (current is None or target is None or current > target):
            result, from_rec, to_rec = self.get_id_records(target, current) # both can be null (when no data has been gathered before)
            if not start: start = to_rec
            if not current: current = to_rec
            if not target: target = self.START_SEQUENCE
            if from_rec and to_rec:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_rec) + " to " + str(to_rec)
                scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                if sequence_from and not sequence_to: # latest applications are updated on the spot
                    for i in result:
                        self.update_application_detail(i)
                count = count + len(result)
                current = from_rec - 1
            else:
                break
        return current, start, count

    # Improved version of gather_ids()
    # process id batches working through a numeric sequence (where the earliest record is nominally record number 1)
    # if two parameters are supplied this is a request to gather backwards from 'to' towards 'from', returning the real sequence range found
    # if one parameter is supplied it's a request to gather forwards beyond 'from', returning the real sequence range found
    # note 'from' is always smaller than 'to'
    def gather_ids2 (self, sequence_from = None, sequence_to = None):
        max = self.get_max_sequence()
        if not sequence_to: # gathering current sequence numbers - going forward
            move_forward = True
            target = max
            start = sequence_from
            if max:
                current_period_begins = max - self.MIN_RECS
                if not start or start > current_period_begins:
                    start = current_period_begins
            if start:
                start = start + 1 # begin one after supplied sequence number
            else:
                start = self.START_POINT
        else: # gathering early sequence numbers - going backward
            move_forward = False
            start = sequence_to
            target = sequence_from
            if max and (not start or start > max):
                start = max
            else:
                start = start - 1 # begin one before supplied sequence number
            if not target or target < self.START_SEQUENCE:
                target = self.START_SEQUENCE
        count = 0
        current = start
        ok_current = start
        while count < self.MAX_ID_BATCH and (not current or not target or (not move_forward and current > target) or (move_forward and current < target)): 
            result, from_rec, to_rec = self.get_id_records2(current, move_forward)
            if not start: 
                if not move_forward:
                    start = to_rec
                else:
                    start = from_rec
                ok_current = start
            if from_rec and to_rec:
                if self.DEBUG:
                    print "Storing " + str(len(result)) + " ids gathered from " + str(from_rec) + " to " + str(to_rec)
                if result:
                    scraperwiki.sqlite.save(unique_keys=['uid'], data=result, table_name=self.TABLE_NAME)
                    count = count + len(result)
                    if not move_forward:
                        ok_current = from_rec
                        current = from_rec - 1
                    else:
                        ok_current = to_rec
                        current = to_rec + 1
                        for i in result:
                            self.update_application_detail(i) # latest applications are updated on the spot
            else:
                break
        if not move_forward:
            return ok_current, start, count
        else:
            return start, ok_current, count

    # returns current max record number - can be overridden in the children
    def get_max_sequence (self):
        return scraperwiki.sqlite.get_var(self.DATA_END_MARKER)

    # retrieves records between two sequence numbers - to be defined in the children
    # can return zero records if no data found for the requested interval, but applicable (inclusive) sequences must be returned
    def get_id_records (self, from_rec, to_rec):
        return [], None, None # invalid if return sequences are not set - means try again next time




systems = {
    'Dlrcoco': 'DlrcocoScraper', # fixed IP for URLs
     }

class SwiftLGScraper(DateScraper):

    MAX_ID_BATCH = 200 # max application ids to fetch in one go
    MAX_UPDATE_BATCH = 300 # max application details to scrape in one go

    field_dot_suffix = False
    date_from_field = 'REGFROMDATE.MAINBODY.WPACIS.1'
    date_to_field = 'REGTODATE.MAINBODY.WPACIS.1'
    search_form = '0'
    scrape_ids = """
    <form> <table> <tr />
    {* <tr>
    <td> <a href="{{ [records].url|abs }}"> {{ [records].uid }} </a> </td>
    </tr> *}
    </table> </form>
    """
    scrape_next_link = [
        'Pages : <a href="{{ next_link }}"> </a>',
        '<p> Pages: <a href="#" /> <a href="{{ next_link }}"> </a> </p>',
        '<p> Pages: <a href="{{ next_link }}"> </a> </p>',
    ]
    detail_page = 'WPHAPPDETAIL.DisplayUrl'
    scrape_max_recs = [
        'returned {{ max_recs }} matches',
        'found {{ max_recs }} matching',
        '<p>Search results: {{ max_recs }} <br>',
        'returned {{ max_recs }} matche(s).'
    ]
    html_subs = {
    r'<a href="([^"]*?)&(?:amp;)*[bB]ackURL=[^"]*?">': r'<a href="\1">',
    }

    # captures HTML block encompassing all fields to be gathered
    scrape_data_block = '<body> {{ block|html }} </body>'
    # flags defining field boundaries
    start_flag = '<label>'
    mid_flag = '</label>'
    end_flag = '<label/>'
    # the minimum acceptable valid dataset on the details page
    #scrape_min_dates = """
    #<div class="tabContent"> <label> Decision </label> {{ decision }} <br> <label> Decision Date </label> {{ decision_date }} <div /> </div>
    #""
    #scrape_min_appeal = """
    #<label> Appeal Lodged Date </label> {{ appeal_date }} <br> 
    #""
    # config scrape templates for all fields
    scrape_config = {
    'reference': "__start__ Application Reference __mid__ {{ __field__ }} __end__",
    'date_validated': "__start__ Registration __mid__ {{ __field__ }} __end__",
    'address': "__start__ Location __mid__ {{ __field__ }} __end__",
    'application_type': "__start__ Application Type __mid__ {{ __field__ }} __end__",
    'date_received': "__start__ Application Date __mid__ {{ __field__ }} __end__",
    'description': "__start__ Proposal __mid__ {{ __field__ }} __end__",
    'status': "__start__ Status __mid__ {{ __field__ }} __end__",
    'ward_name': "__start__ Ward __mid__ {{ __field__ }} __end__",
    'parish': "__start__ Parish __mid__ {{ __field__ }} __end__",
    'district': "__start__ Area __mid__ {{ __field__ }} __end__",
    'case_officer': "__start__ Case Officer __mid__ {{ __field__ }} __end__",
    'applicant_name': "Applicant Details __start__ Company __mid__ {{ __field__ }} __end__", 
    'agent_name': "Agent Details __start__ Company __mid__ {{ __field__ }} __end__",
    #'applicant_name': "Applicant Details {* __start__ __mid__ {{ [__field__] }} __end__ *} __start__ Address __mid__ ",
    #'agent_name': "Agent Details {* __start__ __mid__ {{ [__field__] }} __end__ *}  __start__ Address __mid__ ",
    'applicant_address': "Applicant Details __start__ Address __mid__ {{ __field__ }} __end__",
    'agent_address': "Agent Details __start__ Address __mid__ {{ __field__ }} __end__",
    'decision_date': "__start__ Decision Date __mid__ {{ __field__ }} __end__",
    'consultation_start_date': "__start__ Publicity Start Date __mid__ {{ __field__ }} __end__",
    'consultation_end_date': "__start__ Publicity End Date __mid__ {{ __field__ }} __end__",
    }
    scrape_variants = {}
    #scrape_optional_dates = [
    #"<label> Publicity Start Date </label> {{ consultation_start_date }} <br>",
    #"<label> Publicity End Date </label> {{ consultation_end_date }} <br>",
    #]
    #scrape_optional_appeal = [
    #"<label> Appeal Decision </label> {{ appeal_result }} <br> <label> Appeal Decision Date </label> {{ appeal_decision_date }} <br>",
    #]

    def __init__(self, table_name = None):
        DateScraper.__init__(self, table_name)
        self.scrape_config.update(self.scrape_variants)
        self.scrape_optional_data = []
        for k, v in self.scrape_config.items():
            v = v.replace('__start__', self.start_flag)
            v = v.replace('__mid__', self.mid_flag)
            v = v.replace('__end__', self.end_flag)
            v = v.replace('__field__', k)
            if k == 'reference':
                self.scrape_min_data = v
            else:
                self.scrape_optional_data.append(v)

    def get_id_batch (self, date_from, date_to):

        if self.DEBUG: self.br.set_debug_http(True)

        response = self.br.open(self.search_url)

        fields = {}
        if self.field_dot_suffix:
            fields[self.date_from_field + '.'] = date_from.strftime(self.request_date_format)
            fields[self.date_to_field + '.'] = date_to.strftime(self.request_date_format)
        else:
            fields[self.date_from_field] = date_from.strftime(self.request_date_format)
            fields[self.date_to_field] = date_to.strftime(self.request_date_format)
        setup_form(self.br, self.search_form, fields)
        if self.DEBUG: print self.br.form
        response = submit_form(self.br)
        html = response.read()
        url = response.geturl()
        for k, v in self.html_subs.items():
            html = re.sub(k, v, html, 0, re.U|re.S|re.I) # unicode|dot matches new line|ignore case
        if self.DEBUG: print html
        max_recs = 0
        for scrape in self.scrape_max_recs:
            try:
                result = scrape(scrape, html)
                if self.DEBUG: print result
                max_recs = int(result['max_recs'])
                break
            except:
                pass
        final_result = []
        while len(final_result) < max_recs:
            result = scrape(self.scrape_ids, html, url)
            if result and result.get('records'):
                self.clean_ids(result['records'])
                final_result.extend(result['records'])
            else:
                break
            if len(final_result) >= max_recs:
                break
            try:
                for scrape in self.scrape_next_link:
                    result = scrape(scrape, html, url)
                    if result: break
                #print result
                #next_url = self.BACK_REGEX.sub('', result['next_link'])
                next_batch = len(final_result) + 1
                replacement = '&StartIndex=' + str(next_batch) + '&SortOrder'
                next_url = re.sub(r'&StartIndex=\d+&SortOrder', replacement, result['next_link'])
                #print next_url
                response = self.br.open(next_url)
                html = response.read()
                url = response.geturl()
                for k, v in self.html_subs.items():
                    html = re.sub(k, v, html, 0, re.U|re.S|re.I) # unicode|dot matches new line|ignore case
                if self.DEBUG: print html
            except:
                break
        return final_result

    def get_detail_from_uid (self, uid):
        url = urlparse.urljoin(self.search_url, self.detail_page) + '?theApnID=' + urllib.quote_plus(uid)
        return self.get_detail_from_url(url)

    # scrape detailed information on one record via its access URL
    def get_detail_from_url (self, url):
        if self.DEBUG: print "Url:", url
        try:
            response = self.br.open(url)
            html = response.read()
            this_url = response.geturl()
            if self.DEBUG:
                print "Html obtained from details url:", html
        except:
            if self.DEBUG: raise
            else: return None
        return self.get_detail(html, this_url)

class DlrcocoScraper(SwiftLGScraper):

    search_url = 'http://www2.slough.gov.uk/swiftlg/apas/run/wphappcriteria.display'
    TABLE_NAME = 'Dlrcoco'
    scrape_variants = { 
        'reference': "__start__ Application Ref __mid__ {{ __field__ }} __end__",
        'description': "__start__ Full Description __mid__ {{ __field__ }} __end__",
        'case_officer': "__start__ Case Officer __mid__ {{ __field__ }} <h2/>",
        'agent_address': "Agent Details __start__ Address __mid__ <p> {{ __field__ }} </p>",
    }



if __name__ == 'scraper':
    scraper = DlrcocoScraper()
    scraper.reset('2014-08-14', '2013-09-01')
    scraper.run()

    #scraperwiki.sqlite.execute("update Slough set date_scraped = null, address = null, status = null where uid = 'P/00162/056'")
    #scraperwiki.sqlite.commit()
    #scraper = MoleValleyScraper('MoleValley')
    #scraper = EnfieldScraper('Enfield')
    #scraper.reset('2004-07-14', '2012-11-01')
    #scraper.reset('2006-08-07', '2012-11-01')
    #scraper.DEBUG = True
    #scraper.gather_current_ids()
    #scraper.MAX_UPDATE_BATCH = 1000
    #scraper.ID_ORDER = 'rowid desc'
    #scraper.populate_missing_applications()
    #scraper.reset('2004-07-14', '2012-11-01')

    #util.rename_column('Daventry', 'appeal_decision', 'appeal_result')
    #sys.exit()

    #util.replace_vals('Boston', 'url', 'http://194.72.114.25/', 'http://93.93.220.239/', 'prefix', 'yes')
    #scraper = BostonScraper()
    #scraper.run()
    #scraper = DaventryScraper()
    #scraper.run()
    #scraper = DudleyScraper()
    #scraper.run()
    #sys.exit()

    sys_list = []
    for k, v in systems.items(): # get latest date scraped for each system
        sys_list.append( (k, v, scraperwiki.sqlite.get_var('latest-' + k)) )
    sort_sys = sorted(sys_list, key=lambda system: system[2]) # sort so least recent are first
    for auth in sort_sys[:6]: # do max 6 per run
        strexec = auth[1] + "('" + auth[0] + "')"
        print "Scraping from:", strexec
        try:
            scraper = eval(strexec)
            scraper.run()
        except Exception as err:
            print "Error - skipping this authority -", str(err)
    print "Finished"
