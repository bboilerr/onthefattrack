#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file is part of the web2py Web Framework
Copyrighted by Massimo Di Pierro <mdipierro@cs.depaul.edu>
License: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import cgi
import os
import re
import copy
import types
import urllib
import base64
import sanitizer
import rewrite
import itertools
import decoder
import copy_reg
import marshal
from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint
from contrib.markmin.markmin2html import render

from storage import Storage
from highlight import highlight
from utils import web2py_uuid

import hmac
import hashlib

regex_crlf = re.compile('\r|\n')

__all__ = [
    'A',
    'B',
    'BEAUTIFY',
    'BODY',
    'BR',
    'CENTER',
    'CODE',
    'DIV',
    'EM',
    'EMBED',
    'FIELDSET',
    'FORM',
    'H1',
    'H2',
    'H3',
    'H4',
    'H5',
    'H6',
    'HEAD',
    'HR',
    'HTML',
    'I',
    'IFRAME',
    'IMG',
    'INPUT',
    'LABEL',
    'LEGEND',
    'LI',
    'LINK',
    'OL',
    'UL',
    'MARKMIN',
    'MENU',
    'META',
    'OBJECT',
    'ON',
    'OPTION',
    'P',
    'PRE',
    'SCRIPT',
    'OPTGROUP',
    'SELECT',
    'SPAN',
    'STYLE',
    'TABLE',
    'TAG',
    'TD',
    'TEXTAREA',
    'TH',
    'THEAD',
    'TBODY',
    'TFOOT',
    'TITLE',
    'TR',
    'TT',
    'URL',
    'XHTML',
    'XML',
    'xmlescape',
    'embed64',
    ]


def xmlescape(data, quote = True):
    """
    returns an escaped string of the provided data

    :param data: the data to be escaped
    :param quote: optional (default False)
    """

    # first try the xml function
    if hasattr(data,'xml') and callable(data.xml):
        return data.xml()

    # otherwise, make it a string
    if not isinstance(data, (str, unicode)):
        data = str(data)
    elif isinstance(data, unicode):
        data = data.encode('utf8', 'xmlcharrefreplace')

    # ... and do the escaping
    data = cgi.escape(data, quote).replace("'","&#x27;")
    return data


def URL(
    a=None,
    c=None,
    f=None,
    r=None,
    args=[],
    vars={},
    anchor='',
    extension=None,
    env=None,
    hmac_key=None,
    hash_vars=True,
    _request=None,
    scheme=None,
    host=None,
    port=None,
    ):
    """
    generate a URL

    example::

        >>> str(URL(a='a', c='c', f='f', args=['x', 'y', 'z'],
        ...     vars={'p':1, 'q':2}, anchor='1'))
        '/a/c/f/x/y/z?p=1&q=2#1'

        >>> str(URL(a='a', c='c', f='f', args=['x', 'y', 'z'],
        ...     vars={'p':(1,3), 'q':2}, anchor='1'))
        '/a/c/f/x/y/z?p=1&p=3&q=2#1'

        >>> str(URL(a='a', c='c', f='f', args=['x', 'y', 'z'],
        ...     vars={'p':(3,1), 'q':2}, anchor='1'))
        '/a/c/f/x/y/z?p=3&p=1&q=2#1'

        >>> str(URL(a='a', c='c', f='f', anchor='1+2'))
        '/a/c/f#1%2B2'

        >>> str(URL(a='a', c='c', f='f', args=['x', 'y', 'z'],
        ...     vars={'p':(1,3), 'q':2}, anchor='1', hmac_key='key'))
        '/a/c/f/x/y/z?p=1&p=3&q=2&_signature=5d06bb8a4a6093dd325da2ee591c35c61afbd3c6#1'

    generates a url '/a/c/f' corresponding to application a, controller c
    and function f. If r=request is passed, a, c, f are set, respectively,
    to r.application, r.controller, r.function.

    The more typical usage is:

    URL(r=request, f='index') that generates a url for the index function
    within the present application and controller.

    :param a: application (default to current if r is given)
    :param c: controller (default to current if r is given)
    :param f: function (default to current if r is given)
    :param r: request (optional)
    :param args: any arguments (optional)
    :param vars: any variables (optional)
    :param anchor: anchorname, without # (optional)
    :param hmac_key: key to use when generating hmac signature (optional)
    :param hash_vars: which of the vars to include in our hmac signature
        True (default) - hash all vars, False - hash none of the vars,
        iterable - hash only the included vars ['key1','key2']
    :param _request: used internally for URL rewrite
    :param scheme: URI scheme (True, 'http' or 'https', etc); forces absolute URL (optional)
    :param host: string to force absolute URL with host (True means http_host)
    :param port: optional port number (forces absolute URL)

    :raises SyntaxError: when no application, controller or function is
        available
    :raises SyntaxError: when a CRLF is found in the generated url
    """

    args = args or []
    vars = vars or {}

    application = controller = function = None
    if r:
        application = r.application
        controller = r.controller
        function = r.function
        env = r.env
        if extension is None and r.extension != 'html':
            extension = r.extension
    if a:
        application = a
    if c:
        controller = c
    if f:
        if not isinstance(f, str):
            function = f.__name__
        elif '.' in f:
            function, extension = f.split('.', 1)
        else:
            function = f

    if not (application and controller and function):
        raise SyntaxError, 'not enough information to build the url'

    if not isinstance(args, (list, tuple)):
        args = [args]
    other = args and urllib.quote('/' + '/'.join([str(x) for x in args])) or ''
    if other.endswith('/'):
        other += '/'    # add trailing slash to make last trailing empty arg explicit

    if vars.has_key('_signature'): vars.pop('_signature')
    list_vars = []
    for (key, vals) in sorted(vars.items()):
        if not isinstance(vals, (list, tuple)):
            vals = [vals]
        for val in vals:
            list_vars.append((key, val))

    if hmac_key:
        # generate an hmac signature of the vars & args so can later
        # verify the user hasn't messed with anything

        h_args = '/%s/%s/%s%s' % (application, controller, function, other)

        # how many of the vars should we include in our hash?
        if hash_vars is True:       # include them all
            h_vars = list_vars
        elif hash_vars is False:    # include none of them
            h_vars = ''
        else:                       # include just those specified
            if hash_vars and not isinstance(hash_vars, (list, tuple)):
                hash_vars = [hash_vars]
            h_vars = [(k, v) for (k, v) in list_vars if k in hash_vars]

        # re-assembling the same way during hash authentication
        message = h_args + '?' + urllib.urlencode(sorted(h_vars))

        sig = hmac.new(hmac_key,message, hashlib.sha1).hexdigest()
        # add the signature into vars
        vars['_signature'] = sig
        list_vars.append(('_signature', sig))

    if extension:
        function += '.' + extension
    if vars:
        other += '?%s' % urllib.urlencode(list_vars)
    if anchor:
        other += '#' + urllib.quote(str(anchor))

    if regex_crlf.search(''.join([application, controller, function, other])):
        raise SyntaxError, 'CRLF Injection Detected'
    return XML(rewrite.url_out(r or _request, env, application, controller, function, args, other, scheme, host, port))

def verifyURL(request, hmac_key, hash_vars=True):
    """
    Verifies that a request's args & vars have not been tampered with by the user

    :param request: web2py's request object
    :param hmac_key: the key to authenticate with, must be the same one previously
                    used when calling URL()
    :param hash_vars: which vars to include in our hashing. (Optional)
                    Only uses the 1st value currently (it's really a hack for the _gURL.verify lambda)
                    True (or undefined) means all, False none, an iterable just the specified keys

    do not call directly. Use instead:

    URL.verify(hmac_key='...')

    the key has to match the one used to generate the URL.

        >>> r = Storage()
        >>> gv = Storage(p=(1,3),q=2,_signature='5d06bb8a4a6093dd325da2ee591c35c61afbd3c6')
        >>> r.update(dict(application='a', controller='c', function='f'))
        >>> r['args'] = ['x', 'y', 'z']
        >>> r['get_vars'] = gv
        >>> verifyURL(r, 'key')
        True
        >>> verifyURL(r, 'kay')
        False
        >>> r.get_vars.p = (3, 1)
        >>> verifyURL(r, 'key')
        True
        >>> r.get_vars.p = (3, 2)
        >>> verifyURL(r, 'key')
        False

    """

    if not request.get_vars.has_key('_signature'):
        return False # no signature in the request URL

    # get our sig from request.get_vars for later comparison
    original_sig = request.get_vars._signature

    # now generate a new hmac for the remaining args & vars
    vars, args = request.get_vars, request.args

    # remove the signature var since it was not part of our signed message
    request.get_vars.pop('_signature')

    # join all the args & vars into one long string

    # always include all of the args
    other = args and urllib.quote('/' + '/'.join([str(x) for x in args])) or ''
    h_args = '/%s/%s/%s%s' % (request.application,
                              request.controller,
                              request.function, other)

    # but only include those vars specified (allows more flexibility for use with
    # forms or ajax)

    list_vars = []
    for (key, vals) in sorted(vars.items()):
        if not isinstance(vals, (list, tuple)):
            vals = [vals]
        for val in vals:
            list_vars.append((key, val))

    # which of the vars are to be included?
    if hash_vars is True:       # include them all
        h_vars = list_vars
    elif hash_vars is False:    # include none of them
        h_vars = ''
    else:                       # include just those specified
        # wrap in a try - if the desired vars have been removed it'll fail
        try:
            if hash_vars and not isinstance(hash_vars, (list, tuple)):
                hash_vars = [hash_vars]
            h_vars = [(k, v) for (k, v) in list_vars if k in hash_vars]
        except:
            # user has removed one of our vars! Immediate fail
            return False
    # build the full message string with both args & vars
    message = h_args + '?' + urllib.urlencode(sorted(h_vars))
    # hash with the hmac_key provided
    sig = hmac.new(str(hmac_key), message, hashlib.sha1).hexdigest()

    # put _signature back in get_vars just in case a second call to URL.verify is performed
    # (otherwise it'll immediately return false)
    request.get_vars['_signature'] = original_sig

    # return whether or not the signature in the request matched the one we just generated
    # (I.E. was the message the same as the one we originally signed)
    return original_sig == sig

def _gURL(request):
    """
    A proxy function for URL which contains knowledge
    of a given request object.

    Usage is exactly like URL except you do not have
    to specify r=request!
    """
    def _URL(*args, **kwargs):
        # If they use URL as just passing along
        # args, we don't want to overwrite it and
        # cause issues.
        if not kwargs.has_key('r') and len(args) < 3:
            kwargs['r'] = request
            if len(args) == 1 and not 'f' in kwargs:
                kwargs['f'] = args[0]
                args = []
            if len(args) == 2 and not 'f' in kwargs and not 'c' in kwargs:
                kwargs['c'], kwargs['f'] = args[0], args[1]
                args = []
        kwargs['_request'] = request
        return URL(*args, **kwargs)
    _URL.__doc__ = URL.__doc__

    # probably ugly work-around for the lambda call. Want for hash_vars to be an optional argument
    _URL.verify = lambda request, hmac_key, *hash_vars: verifyURL(request, hmac_key, *hash_vars)

    return _URL


ON = True


class XmlComponent(object):
    """
    Abstract root for all Html components
    """

    # TODO: move some DIV methods to here

    def xml(self):
        raise NotImplementedError


class XML(XmlComponent):
    """
    use it to wrap a string that contains XML/HTML so that it will not be
    escaped by the template

    example:

    >>> XML('<h1>Hello</h1>').xml()
    '<h1>Hello</h1>'
    """

    def __init__(
        self,
        text,
        sanitize = False,
        permitted_tags = [
            'a',
            'b',
            'blockquote',
            'br/',
            'i',
            'li',
            'ol',
            'ul',
            'p',
            'cite',
            'code',
            'pre',
            'img/',
            ],
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt'],
            'blockquote': ['type']
            },
        ):
        """
        :param text: the XML text
        :param sanitize: sanitize text using the permitted tags and allowed
            attributes (default False)
        :param permitted_tags: list of permitted tags (default: simple list of
            tags)
        :param allowed_attributes: dictionary of allowed attributed (default
            for A, IMG and BlockQuote).
            The key is the tag; the value is a list of allowed attributes.
        """

        if sanitize:
            text = sanitizer.sanitize(text, permitted_tags,
                    allowed_attributes)
        if isinstance(text, unicode):
            text = text.encode('utf8', 'xmlcharrefreplace')
        elif not isinstance(text, str):
            text = str(text)
        self.text = text

    def xml(self):
        return self.text

    def __str__(self):
        return self.xml()

    def __add__(self,other):
        return '%s%s' % (self,other)

    def __radd__(self,other):
        return '%s%s' % (other,self)

    def __cmp__(self,other):
        return cmp(str(self),str(other))

    def __hash__(self):
        return hash(str(self))

    def __getattr__(self,name):
        return getattr(str(self),name)

    def __getitem__(self,i):
        return str(self)[i]

    def __getslice__(self,i,j):
        return str(self)[i:j]

    def __iter__(self):
        for c in str(self): yield c

    def __len__(self):
        return len(str(self))

    def flatten(self,render=None):
        """
        return the text stored by the XML object rendered by the render function
        """
        if render:
            return render(self.text,None,{})
        return self.text

    def elements(self, *args, **kargs):
        """
        to be considered experimental since the behavior of this method is questionable
        another options could be TAG(self.text).elements(*args,**kargs)
        """
        return []

### important to allow safe session.flash=T(....)
def XML_unpickle(data):
    return marshal.loads(data)
def XML_pickle(data):
    return XML_unpickle, (marshal.dumps(str(data)),)
copy_reg.pickle(XML, XML_pickle, XML_unpickle)



class DIV(XmlComponent):
    """
    HTML helper, for easy generating and manipulating a DOM structure.
    Little or no validation is done.

    Behaves like a dictionary regarding updating of attributes.
    Behaves like a list regarding inserting/appending components.

    example::

        >>> DIV('hello', 'world', _style='color:red;').xml()
        '<div style=\"color:red;\">helloworld</div>'

    all other HTML helpers are derived from DIV.

    _something=\"value\" attributes are transparently translated into
    something=\"value\" HTML attributes
    """

    # name of the tag, subclasses should update this
    # tags ending with a '/' denote classes that cannot
    # contain components
    tag = 'div'

    def __init__(self, *components, **attributes):
        """
        :param *components: any components that should be nested in this element
        :param **attributes: any attributes you want to give to this element

        :raises SyntaxError: when a stand alone tag receives components
        """

        if self.tag[-1:] == '/' and components:
            raise SyntaxError, '<%s> tags cannot have components'\
                 % self.tag
        if len(components) == 1 and isinstance(components[0], (list,tuple)):
            self.components = list(components[0])
        else:
            self.components = list(components)
        self.attributes = attributes
        self._fixup()
        # converts special attributes in components attributes
        self._postprocessing()
        self.parent = None
        for c in self.components:
            self._setnode(c)

    def update(self, **kargs):
        """
        dictionary like updating of the tag attributes
        """

        for (key, value) in kargs.items():
            self[key] = value
        return self

    def append(self, value):
        """
        list style appending of components

        >>> a=DIV()
        >>> a.append(SPAN('x'))
        >>> print a
        <div><span>x</span></div>
        """
        self._setnode(value)
        ret = self.components.append(value)
        self._fixup()
        return ret

    def insert(self, i, value):
        """
        list style inserting of components

        >>> a=DIV()
        >>> a.insert(0,SPAN('x'))
        >>> print a
        <div><span>x</span></div>
        """
        self._setnode(value)
        ret = self.components.insert(i, value)
        self._fixup()
        return ret

    def __getitem__(self, i):
        """
        gets attribute with name 'i' or component #i.
        If attribute 'i' is not found returns None

        :param i: index
           if i is a string: the name of the attribute
           otherwise references to number of the component
        """

        if isinstance(i, str):
            try:
                return self.attributes[i]
            except KeyError:
                return None
        else:
            return self.components[i]

    def __setitem__(self, i, value):
        """
        sets attribute with name 'i' or component #i.

        :param i: index
           if i is a string: the name of the attribute
           otherwise references to number of the component
        :param value: the new value
        """
        self._setnode(value)
        if isinstance(i, (str, unicode)):
            self.attributes[i] = value
        else:
            self.components[i] = value

    def __delitem__(self, i):
        """
        deletes attribute with name 'i' or component #i.

        :param i: index
           if i is a string: the name of the attribute
           otherwise references to number of the component
        """

        if isinstance(i, str):
            del self.attributes[i]
        else:
            del self.components[i]

    def __len__(self):
        """
        returns the number of included components
        """
        return len(self.components)

    def __nonzero__(self):
        """
        always return True
        """
        return True

    def _fixup(self):
        """
        Handling of provided components.

        Nothing to fixup yet. May be overridden by subclasses,
        eg for wrapping some components in another component or blocking them.
        """
        return

    def _wrap_components(self, allowed_parents,
                         wrap_parent = None,
                         wrap_lambda = None):
        """
        helper for _fixup. Checks if a component is in allowed_parents,
        otherwise wraps it in wrap_parent

        :param allowed_parents: (tuple) classes that the component should be an
            instance of
        :param wrap_parent: the class to wrap the component in, if needed
        :param wrap_lambda: lambda to use for wrapping, if needed

        """
        components = []
        for c in self.components:
            if isinstance(c, allowed_parents):
                pass
            elif wrap_lambda:
                c = wrap_lambda(c)
            else:
                c = wrap_parent(c)
            if isinstance(c,DIV):
                c.parent = self
            components.append(c)
        self.components = components

    def _postprocessing(self):
        """
        Handling of attributes (normally the ones not prefixed with '_').

        Nothing to postprocess yet. May be overridden by subclasses
        """
        return

    def _traverse(self, status, hideerror=False):
        # TODO: docstring
        newstatus = status
        for c in self.components:
            if hasattr(c, '_traverse') and callable(c._traverse):
                c.vars = self.vars
                c.request_vars = self.request_vars
                c.errors = self.errors
                c.latest = self.latest
                c.session = self.session
                c.formname = self.formname
                c['hideerror']=hideerror
                newstatus = c._traverse(status,hideerror) and newstatus

        # for input, textarea, select, option
        # deal with 'value' and 'validation'

        name = self['_name']
        if newstatus:
            newstatus = self._validate()
            self._postprocessing()
        elif 'old_value' in self.attributes:
            self['value'] = self['old_value']
            self._postprocessing()
        elif name and name in self.vars:
            self['value'] = self.vars[name]
            self._postprocessing()
        if name:
            self.latest[name] = self['value']
        return newstatus

    def _validate(self):
        """
        nothing to validate yet. May be overridden by subclasses
        """
        return True

    def _setnode(self,value):
        if isinstance(value,DIV):
            value.parent = self

    def _xml(self):
        """
        helper for xml generation. Returns separately:
        - the component attributes
        - the generated xml of the inner components

        Component attributes start with an underscore ('_') and
        do not have a False or None value. The underscore is removed.
        A value of True is replaced with the attribute name.

        :returns: tuple: (attributes, components)
        """

        # get the attributes for this component
        # (they start with '_', others may have special meanings)
        fa = ''
        for key in sorted(self.attributes):
            value = self[key]
            if key[:1] != '_':
                continue
            name = key[1:]
            if value is True:
                value = name
            elif value is False or value is None:
                continue
            fa += ' %s="%s"' % (name, xmlescape(value, True))

        # get the xml for the inner components
        co = ''.join([xmlescape(component) for component in
                     self.components])

        return (fa, co)

    def xml(self):
        """
        generates the xml for this component.
        """

        (fa, co) = self._xml()

        if not self.tag:
            return co

        if self.tag[-1:] == '/':
            # <tag [attributes] />
            return '<%s%s />' % (self.tag[:-1], fa)

        # else: <tag [attributes]>  inner components xml </tag>
        return '<%s%s>%s</%s>' % (self.tag, fa, co, self.tag)

    def __str__(self):
        """
        str(COMPONENT) returns equals COMPONENT.xml()
        """

        return self.xml()

    def flatten(self, render=None):
        """
        return the text stored by the DIV object rendered by the render function
        the render function must take text, tagname, and attributes
        render=None is equivalent to render=lambda text, tag, attr: text

        >>> markdown = lambda text,tag=None,attributes={}: \
                        {None: re.sub('\s+',' ',text), \
                         'h1':'#'+text+'\\n\\n', \
                         'p':text+'\\n'}.get(tag,text)
        >>> a=TAG('<h1>Header</h1><p>this is a     test</p>')
        >>> a.flatten(markdown)
        '#Header\\n\\nthis is a test\\n'
        """

        text = ''
        for c in self.components:
            if isinstance(c,XmlComponent):
                s=c.flatten(render)
            elif render:
                s=render(str(c))
            else:
                s=str(c)
            text+=s
        if render:
            text = render(text,self.tag,self.attributes)
        return text

    regex_tag=re.compile('^[\w\-\:]+')
    regex_id=re.compile('#([\w\-]+)')
    regex_class=re.compile('\.([\w\-]+)')
    regex_attr=re.compile('\[([\w\-\:]+)=(.*?)\]')


    def elements(self, *args, **kargs):
        """
        find all component that match the supplied attribute dictionary,
        or None if nothing could be found

        All components of the components are searched.

        >>> a = DIV(DIV(SPAN('x'),3,DIV(SPAN('y'))))
        >>> for c in a.elements('span',first_only=True): c[0]='z'
        >>> print a
        <div><div><span>z</span>3<div><span>y</span></div></div></div>
        >>> for c in a.elements('span'): c[0]='z'
        >>> print a
        <div><div><span>z</span>3<div><span>z</span></div></div></div>

        It also supports a syntax compatible with jQuery

        >>> a=TAG('<div><span><a id="1-1" u:v=$>hello</a></span><p class="this is a test">world</p></div>')
        >>> for e in a.elements('div a#1-1, p.is'): print e.flatten()
        hello
        world
        >>> for e in a.elements('#1-1'): print e.flatten()
        hello
        >>> a.elements('a[u:v=$]')[0].xml()
        '<a id="1-1" u:v="$">hello</a>'

        >>> a=FORM( INPUT(_type='text'), SELECT(range(1)), TEXTAREA() )
        >>> for c in a.elements('input, select, textarea'): c['_disabled'] = 'disabled'
        >>> a.xml()
        '<form action="" enctype="multipart/form-data" method="post"><input disabled="disabled" type="text" /><select disabled="disabled"><option value="0">0</option></select><textarea cols="40" disabled="disabled" rows="10"></textarea></form>'
        """
        if len(args)==1:
            args = [a.strip() for a in args[0].split(',')]
        if len(args)>1:
            subset = [self.elements(a,**kargs) for a in args]
            return reduce(lambda a,b:a+b,subset,[])
        elif len(args)==1:
            items = args[0].split()
            if len(items)>1:
                subset=[a.elements(' '.join(items[1:]),**kargs) for a in self.elements(items[0])]
                return reduce(lambda a,b:a+b,subset,[])
            else:
                item=items[0]
                if '#' in item or '.' in item or '[' in item:
                    match_tag = self.regex_tag.search(item)
                    match_id = self.regex_id.search(item)
                    match_class = self.regex_class.search(item)
                    match_attr = self.regex_attr.finditer(item)
                    args = []
                    if match_tag: args = [match_tag.group()]
                    if match_id: kargs['_id'] = match_id.group(1)
                    if match_class: kargs['_class'] = re.compile('(?<!\w)%s(?!\w)' % \
                       match_class.group(1).replace('-','\\-').replace(':','\\:'))
                    for item in match_attr:
                        kargs['_'+item.group(1)]=item.group(2)
                    return self.elements(*args,**kargs)
        # make a copy of the components
        matches = []
        first_only = False
        if kargs.has_key("first_only"):
            first_only = kargs["first_only"]
            del kargs["first_only"]
        # check if the component has an attribute with the same
        # value as provided
        check = True
        tag = getattr(self,'tag').replace("/","")
        if args and tag not in args:
            check = False
        for (key, value) in kargs.items():
            if isinstance(value,(str,int)):
                if self[key] != str(value):
                    check = False
            elif key in self.attributes:
                if not value.search(str(self[key])):
                    check = False
            else:
                check = False
        if 'find' in kargs:
            find = kargs['find']
            for c in self.components:
                if isinstance(find,(str,int)):
                    if isinstance(c,str) and str(find) in c:
                        check = True
                else:
                    if isinstance(c,str) and find.search(c):
                        check = True
        # if found, return the component
        if check:
            matches.append(self)
            if first_only:
                return matches
        # loop the copy
        for c in self.components:
            if isinstance(c, XmlComponent):
                kargs['first_only'] = first_only
                child_matches = c.elements( *args,  **kargs )
                if first_only  and len(child_matches) != 0:
                    return child_matches
                matches.extend( child_matches )
        return matches


    def element(self, *args, **kargs):
        """
        find the first component that matches the supplied attribute dictionary,
        or None if nothing could be found

        Also the components of the components are searched.
        """
        kargs['first_only'] = True
        elements = self.elements(*args, **kargs)
        if not elements:
            # we found nothing
            return None
        return elements[0]

    def siblings(self,*args,**kargs):
        """
        find all sibling components that match the supplied argument list
        and attribute dictionary, or None if nothing could be found
        """
        sibs = [s for s in self.parent.components if not s == self]
        matches = []
        first_only = False
        if kargs.has_key("first_only"):
            first_only = kargs["first_only"]
            del kargs["first_only"]
        for c in sibs:
            try:
                check = True
                tag = getattr(c,'tag').replace("/","")
                if args and tag not in args:
                        check = False
                for (key, value) in kargs.items():
                    if c[key] != value:
                            check = False
                if check:
                    matches.append(c)
                    if first_only: break
            except:
                pass
        return matches

    def sibling(self,*args,**kargs):
        """
        find the first sibling component that match the supplied argument list
        and attribute dictionary, or None if nothing could be found
        """
        kargs['first_only'] = True
        sibs = self.siblings(*args, **kargs)
        if not sibs:
            return None
        return sibs[0]

class __TAG__(XmlComponent):

    """
    TAG factory example::

        >>> print TAG.first(TAG.second('test'), _key = 3)
        <first key=\"3\"><second>test</second></first>

    """

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __getattr__(self, name):
        if name[-1:] == '_':
            name = name[:-1] + '/'
        if isinstance(name,unicode):
            name = name.encode('utf-8')
        class __tag__(DIV):
            tag = name

        return lambda *a, **b: __tag__(*a, **b)

    def __call__(self,html):
        return web2pyHTMLParser(decoder.decoder(html)).tree

TAG = __TAG__()


class HTML(DIV):
    """
    There are four predefined document type definitions.
    They can be specified in the 'doctype' parameter:

    -'strict' enables strict doctype
    -'transitional' enables transitional doctype (default)
    -'frameset' enables frameset doctype
    -'html5' enables HTML 5 doctype
    -any other string will be treated as user's own doctype

    'lang' parameter specifies the language of the document.
    Defaults to 'en'.

    See also :class:`DIV`
    """

    tag = 'html'

    strict = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n'
    transitional = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">\n'
    frameset = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Frameset//EN" "http://www.w3.org/TR/html4/frameset.dtd">\n'
    html5 = '<!DOCTYPE HTML>\n'

    def xml(self):
        lang = self['lang']
        if not lang:
            lang = 'en'
        self.attributes['_lang'] = lang
        doctype = self['doctype']
        if doctype:
            if doctype == 'strict':
                doctype = self.strict
            elif doctype == 'transitional':
                doctype = self.transitional
            elif doctype == 'frameset':
                doctype = self.frameset
            elif doctype == 'html5':
                doctype = self.html5
            else:
                doctype = '%s\n' % doctype
        else:
            doctype = self.transitional
        (fa, co) = self._xml()
        return '%s<%s%s>%s</%s>' % (doctype, self.tag, fa, co, self.tag)

class XHTML(DIV):
    """
    This is XHTML version of the HTML helper.

    There are three predefined document type definitions.
    They can be specified in the 'doctype' parameter:

    -'strict' enables strict doctype
    -'transitional' enables transitional doctype (default)
    -'frameset' enables frameset doctype
    -any other string will be treated as user's own doctype

    'lang' parameter specifies the language of the document and the xml document.
    Defaults to 'en'.

    'xmlns' parameter specifies the xml namespace.
    Defaults to 'http://www.w3.org/1999/xhtml'.

    See also :class:`DIV`
    """

    tag = 'html'

    strict = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n'
    transitional = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
    frameset = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">\n'
    xmlns = 'http://www.w3.org/1999/xhtml'

    def xml(self):
        xmlns = self['xmlns']
        if xmlns:
            self.attributes['_xmlns'] = xmlns
        else:
            self.attributes['_xmlns'] = self.xmlns
        lang = self['lang']
        if not lang:
            lang = 'en'
        self.attributes['_lang'] = lang
        self.attributes['_xml:lang'] = lang
        doctype = self['doctype']
        if doctype:
            if doctype == 'strict':
                doctype = self.strict
            elif doctype == 'transitional':
                doctype = self.transitional
            elif doctype == 'frameset':
                doctype = self.frameset
            else:
                doctype = '%s\n' % doctype
        else:
            doctype = self.transitional
        (fa, co) = self._xml()
        return '%s<%s%s>%s</%s>' % (doctype, self.tag, fa, co, self.tag)


class HEAD(DIV):

    tag = 'head'

class TITLE(DIV):

    tag = 'title'


class META(DIV):

    tag = 'meta/'


class LINK(DIV):

    tag = 'link/'


class SCRIPT(DIV):

    tag = 'script'

    def xml(self):
        (fa, co) = self._xml()
        # no escaping of subcomponents
        co = '\n'.join([str(component) for component in
                       self.components])
        if co:
            # <script [attributes]><!--//--><![CDATA[//><!--
            # script body
            # //--><!]]></script>
            # return '<%s%s><!--//--><![CDATA[//><!--\n%s\n//--><!]]></%s>' % (self.tag, fa, co, self.tag)
            return '<%s%s><!--\n%s\n//--></%s>' % (self.tag, fa, co, self.tag)
        else:
            return DIV.xml(self)


class STYLE(DIV):

    tag = 'style'

    def xml(self):
        (fa, co) = self._xml()
        # no escaping of subcomponents
        co = '\n'.join([str(component) for component in
                       self.components])
        if co:
            # <style [attributes]><!--/*--><![CDATA[/*><!--*/
            # style body
            # /*]]>*/--></style>
            return '<%s%s><!--/*--><![CDATA[/*><!--*/\n%s\n/*]]>*/--></%s>' % (self.tag, fa, co, self.tag)
        else:
            return DIV.xml(self)


class IMG(DIV):

    tag = 'img/'


class SPAN(DIV):

    tag = 'span'


class BODY(DIV):

    tag = 'body'


class H1(DIV):

    tag = 'h1'


class H2(DIV):

    tag = 'h2'


class H3(DIV):

    tag = 'h3'


class H4(DIV):

    tag = 'h4'


class H5(DIV):

    tag = 'h5'


class H6(DIV):

    tag = 'h6'


class P(DIV):
    """
    Will replace ``\\n`` by ``<br />`` if the `cr2br` attribute is provided.

    see also :class:`DIV`
    """

    tag = 'p'

    def xml(self):
        text = DIV.xml(self)
        if self['cr2br']:
            text = text.replace('\n', '<br />')
        return text


class B(DIV):

    tag = 'b'


class BR(DIV):

    tag = 'br/'


class HR(DIV):

    tag = 'hr/'


class A(DIV):
    tag = 'a'
    def xml(self):
        if self['cid']:
            self['_onclick']='web2py_component("%s","%s");return false;' % \
                (self['_href'],self['cid'])
        return DIV.xml(self)

class EM(DIV):

    tag = 'em'


class EMBED(DIV):

    tag = 'embed/'


class TT(DIV):

    tag = 'tt'


class PRE(DIV):

    tag = 'pre'


class CENTER(DIV):

    tag = 'center'


class CODE(DIV):

    """
    displays code in HTML with syntax highlighting.

    :param attributes: optional attributes:

        - language: indicates the language, otherwise PYTHON is assumed
        - link: can provide a link
        - styles: for styles

    Example::

        {{=CODE(\"print 'hello world'\", language='python', link=None,
            counter=1, styles={}, highlight_line=None)}}


    supported languages are \"python\", \"html_plain\", \"c\", \"cpp\",
    \"web2py\", \"html\".
    The \"html\" language interprets {{ and }} tags as \"web2py\" code,
    \"html_plain\" doesn't.

    if a link='/examples/global/vars/' is provided web2py keywords are linked to
    the online docs.

    the counter is used for line numbering, counter can be None or a prompt
    string.
    """

    def xml(self):
        language = self['language'] or 'PYTHON'
        link = self['link']
        counter = self.attributes.get('counter', 1)
        highlight_line = self.attributes.get('highlight_line', None)
        styles = self['styles'] or {}
        return highlight(
            ''.join(self.components),
            language=language,
            link=link,
            counter=counter,
            styles=styles,
            attributes=self.attributes,
            highlight_line=highlight_line,
            )


class LABEL(DIV):

    tag = 'label'


class LI(DIV):

    tag = 'li'


class UL(DIV):
    """
    UL Component.

    If subcomponents are not LI-components they will be wrapped in a LI

    see also :class:`DIV`
    """

    tag = 'ul'

    def _fixup(self):
        self._wrap_components(LI, LI)


class OL(UL):

    tag = 'ol'


class TD(DIV):

    tag = 'td'


class TH(DIV):

    tag = 'th'


class TR(DIV):
    """
    TR Component.

    If subcomponents are not TD/TH-components they will be wrapped in a TD

    see also :class:`DIV`
    """

    tag = 'tr'

    def _fixup(self):
        self._wrap_components((TD, TH), TD)

class THEAD(DIV):

    tag = 'thead'

    def _fixup(self):
        self._wrap_components(TR, TR)


class TBODY(DIV):

    tag = 'tbody'

    def _fixup(self):
        self._wrap_components(TR, TR)


class TFOOT(DIV):

    tag = 'tfoot'

    def _fixup(self):
        self._wrap_components(TR, TR)


class TABLE(DIV):
    """
    TABLE Component.

    If subcomponents are not TR/TBODY/THEAD/TFOOT-components
    they will be wrapped in a TR

    see also :class:`DIV`
    """

    tag = 'table'

    def _fixup(self):
        self._wrap_components((TR, TBODY, THEAD, TFOOT), TR)

class I(DIV):

    tag = 'i'

class IFRAME(DIV):

    tag = 'iframe'


class INPUT(DIV):

    """
        INPUT Component

        examples::

            >>> INPUT(_type='text', _name='name', value='Max').xml()
            '<input name=\"name\" type=\"text\" value=\"Max\" />'

            >>> INPUT(_type='checkbox', _name='checkbox', value='on').xml()
            '<input checked=\"checked\" name=\"checkbox\" type=\"checkbox\" value=\"on\" />'

            >>> INPUT(_type='radio', _name='radio', _value='yes', value='yes').xml()
            '<input checked=\"checked\" name=\"radio\" type=\"radio\" value=\"yes\" />'

            >>> INPUT(_type='radio', _name='radio', _value='no', value='yes').xml()
            '<input name=\"radio\" type=\"radio\" value=\"no\" />'

        the input helper takes two special attributes value= and requires=.

        :param value: used to pass the initial value for the input field.
            value differs from _value because it works for checkboxes, radio,
            textarea and select/option too.

            - for a checkbox value should be '' or 'on'.
            - for a radio or select/option value should be the _value
                of the checked/selected item.

        :param requires: should be None, or a validator or a list of validators
            for the value of the field.
        """

    tag = 'input/'

    def _validate(self):

        # # this only changes value, not _value

        name = self['_name']
        if name is None or name == '':
            return True
        name = str(name)

        if self['_type'] != 'checkbox':
            self['old_value'] = self['value'] or self['_value'] or ''
            value = self.request_vars.get(name, '')
            self['value'] = value
        else:
            self['old_value'] = self['value'] or False
            value = self.request_vars.get(name)
            if isinstance(value, (tuple, list)):
                self['value'] = self['_value'] in value
            else:
                self['value'] = self['_value'] == value
        requires = self['requires']
        if requires:
            if not isinstance(requires, (list, tuple)):
                requires = [requires]
            for validator in requires:
                (value, errors) = validator(value)
                if errors != None:
                    self.vars[name] = value
                    self.errors[name] = errors
                    break
        if not name in self.errors:
            self.vars[name] = value
            return True
        return False

    def _postprocessing(self):
        t = self['_type']
        if not t:
            t = self['_type'] = 'text'
        t = t.lower()
        value = self['value']
        if self['_value'] == None:
            _value = None
        else:
            _value = str(self['_value'])
        if t == 'checkbox':
            if not _value:
                _value = self['_value'] = 'on'
            if not value:
                value = []
            elif value is True:
                value = [_value]
            elif not isinstance(value,(list,tuple)):
                value = str(value).split('|')
            self['_checked'] = _value in value and 'checked' or None
        elif t == 'radio':
            if str(value) == str(_value):
                self['_checked'] = 'checked'
            else:
                self['_checked'] = None
        elif t == 'text' or t == 'hidden':
            if value != None:
                self['_value'] = value
            else:
                self['value'] = _value

    def xml(self):
        name = self.attributes.get('_name', None)
        if name and hasattr(self, 'errors') \
                and self.errors.get(name, None) \
                and self['hideerror'] != True:
            return DIV.xml(self) + DIV(self.errors[name], _class='error',
                errors=None, _id='%s__error' % name).xml()
        else:
            return DIV.xml(self)


class TEXTAREA(INPUT):

    """
    example::

        TEXTAREA(_name='sometext', value='blah '*100, requires=IS_NOT_EMPTY())

    'blah blah blah ...' will be the content of the textarea field.
    """

    tag = 'textarea'

    def _postprocessing(self):
        if not '_rows' in self.attributes:
            self['_rows'] = 10
        if not '_cols' in self.attributes:
            self['_cols'] = 40
        if self['value'] != None:
            self.components = [self['value']]
        elif self.components:
            self['value'] = self.components[0]


class OPTION(DIV):

    tag = 'option'

    def _fixup(self):
        if not '_value' in self.attributes:
            self.attributes['_value'] = str(self.components[0])


class OBJECT(DIV):

    tag = 'object'

class OPTGROUP(DIV):

    tag = 'optgroup'

    def _fixup(self):
        components = []
        for c in self.components:
            if isinstance(c, OPTION):
                components.append(c)
            else:
                components.append(OPTION(c, _value=str(c)))
        self.components = components


class SELECT(INPUT):

    """
    example::

        >>> from validators import IS_IN_SET
        >>> SELECT('yes', 'no', _name='selector', value='yes',
        ...    requires=IS_IN_SET(['yes', 'no'])).xml()
        '<select name=\"selector\"><option selected=\"selected\" value=\"yes\">yes</option><option value=\"no\">no</option></select>'

    """

    tag = 'select'

    def _fixup(self):
        components = []
        for c in self.components:
            if isinstance(c, (OPTION, OPTGROUP)):
                components.append(c)
            else:
                components.append(OPTION(c, _value=str(c)))
        self.components = components

    def _postprocessing(self):
        component_list = []
        for c in self.components:
            if isinstance(c, OPTGROUP):
                component_list.append(c.components)
            else:
                component_list.append([c])
        options = itertools.chain(*component_list)

        value = self['value']
        if value != None:
            if not self['_multiple']:
                for c in options: # my patch
                    if value and str(c['_value'])==str(value):
                        c['_selected'] = 'selected'
                    else:
                        c['_selected'] = None
            else:
                if isinstance(value,(list,tuple)):
                    values = [str(item) for item in value]
                else:
                    values = [str(value)]
                for c in options: # my patch
                    if value and str(c['_value']) in values:
                        c['_selected'] = 'selected'
                    else:
                        c['_selected'] = None


class FIELDSET(DIV):

    tag = 'fieldset'


class LEGEND(DIV):

    tag = 'legend'


class FORM(DIV):

    """
    example::

        >>> from validators import IS_NOT_EMPTY
        >>> form=FORM(INPUT(_name=\"test\", requires=IS_NOT_EMPTY()))
        >>> form.xml()
        '<form action=\"\" enctype=\"multipart/form-data\" method=\"post\"><input name=\"test\" type=\"text\" /></form>'

    a FORM is container for INPUT, TEXTAREA, SELECT and other helpers

    form has one important method::

        form.accepts(request.vars, session)

    if form is accepted (and all validators pass) form.vars contains the
    accepted vars, otherwise form.errors contains the errors.
    in case of errors the form is modified to present the errors to the user.
    """

    tag = 'form'

    def __init__(self, *components, **attributes):
        DIV.__init__(self, *components,  **attributes)
        self.vars = Storage()
        self.errors = Storage()
        self.latest = Storage()

    def accepts(
        self,
        vars,
        session=None,
        formname='default',
        keepvalues=False,
        onvalidation=None,
        hideerror=False,
        ):
        if vars.__class__.__name__ == 'Request':
            vars=vars.post_vars
        self.errors.clear()
        self.request_vars = Storage()
        self.request_vars.update(vars)
        self.session = session
        self.formname = formname
        self.keepvalues = keepvalues

        # if this tag is a form and we are in accepting mode (status=True)
        # check formname and formkey

        status = True
        if self.session:
            formkey = self.session.get('_formkey[%s]' % self.formname, None)
            # check if user tampering with form and void CSRF
            if formkey != self.request_vars._formkey:
                status = False
        if self.formname != self.request_vars._formname:
            status = False
        if status and self.session:
            # check if editing a record that has been modified by the server
            if hasattr(self,'record_hash') and self.record_hash != formkey:
                status = False
                self.record_changed = True
        status = self._traverse(status,hideerror)
        if onvalidation:
            if isinstance(onvalidation, dict):
                onsuccess = onvalidation.get('onsuccess', None)
                onfailure = onvalidation.get('onfailure', None)
                if onsuccess and status:
                    onsuccess(self)
                if onfailure and vars and not status:
                    onfailure(self)
                    status = len(self.errors) == 0
            elif status:
                if isinstance(onvalidation, (list, tuple)):
                    [f(self) for f in onvalidation]
                else:
                    onvalidation(self)
        if self.errors:
            status = False
        if session != None:
            if hasattr(self,'record_hash'):
                formkey = self.record_hash
            else:
                formkey = web2py_uuid()

            keyname = '_formkey[%s]' % formname

            if not keyname in session:
                self.formkey = session[keyname] = formkey
            else:
                self.formkey = session[keyname]

        if status and not keepvalues:
            self._traverse(False,hideerror)
        return status

    def _postprocessing(self):
        if not '_action' in self.attributes:
            self['_action'] = ''
        if not '_method' in self.attributes:
            self['_method'] = 'post'
        if not '_enctype' in self.attributes:
            self['_enctype'] = 'multipart/form-data'

    def hidden_fields(self):
        c = []
        if 'hidden' in self.attributes:
            for (key, value) in self.attributes.get('hidden',{}).items():
                c.append(INPUT(_type='hidden', _name=key, _value=value))

        if hasattr(self, 'formkey') and self.formkey:
            c.append(INPUT(_type='hidden', _name='_formkey',
                     _value=self.formkey))
        if hasattr(self, 'formname') and self.formname:
            c.append(INPUT(_type='hidden', _name='_formname',
                     _value=self.formname))
        return DIV(c, _class="hidden")

    def xml(self):
        newform = FORM(*self.components, **self.attributes)
        hidden_fields = self.hidden_fields()
        if hidden_fields.components:
            newform.append(hidden_fields)
        return DIV.xml(newform)


class BEAUTIFY(DIV):

    """
    example::

        >>> BEAUTIFY(['a', 'b', {'hello': 'world'}]).xml()
        '<div><table><tr><td><div>a</div></td></tr><tr><td><div>b</div></td></tr><tr><td><div><table><tr><td style="font-weight:bold;">hello</td><td valign="top">:</td><td><div>world</div></td></tr></table></div></td></tr></table></div>'

    turns any list, dictionary, etc into decent looking html.
    Two special attributes are
    :sorted: a function that takes the dict and returned sorted keys
    :keyfilter: a funciton that takes a key and returns its representation
                or None if the key is to be skipped. By default key[:1]=='_' is skipped.
    """

    tag = 'div'

    @staticmethod
    def no_underscore(key):
        if key[:1]=='_':
            return None
        return key

    def __init__(self, component, **attributes):
        self.components = [component]
        self.attributes = attributes
        sorter = attributes.get('sorted',sorted)
        keyfilter = attributes.get('keyfilter',BEAUTIFY.no_underscore)
        components = []
        attributes = copy.copy(self.attributes)
        level = attributes['level'] = attributes.get('level',6) - 1
        if '_class' in attributes:
            attributes['_class'] += 'i'
        if level == 0:
            return
        for c in self.components:
            if hasattr(c,'xml') and callable(c.xml):
                components.append(c)
                continue
            elif hasattr(c,'keys') and callable(c.keys):
                rows = []
                try:
                    keys = (sorter and sorter(c)) or c
                    for key in keys:
                        if isinstance(key,(str,unicode)) and keyfilter:
                            filtered_key = keyfilter(key)
                        else:
                            filtered_key = str(key)
                        if filtered_key is None:
                            continue
                        value = c[key]
                        if type(value) == types.LambdaType:
                            continue
                        rows.append(TR(TD(filtered_key, _style='font-weight:bold;'),
                                       TD(':',_valign='top'),
                                       TD(BEAUTIFY(value, **attributes))))
                    components.append(TABLE(*rows, **attributes))
                    continue
                except:
                    pass
            if isinstance(c, str):
                components.append(str(c))
            elif isinstance(c, unicode):
                components.append(c.encode('utf8'))
            elif isinstance(c, (list, tuple)):
                items = [TR(TD(BEAUTIFY(item, **attributes)))
                         for item in c]
                components.append(TABLE(*items, **attributes))
            elif isinstance(c, cgi.FieldStorage):
                components.append('FieldStorage object')
            else:
                components.append(repr(c))
        self.components = components


class MENU(DIV):
    """
    Used to build menus

    Optional arguments
      _class: defaults to 'web2py-menu web2py-menu-vertical'
      ul_class: defaults to 'web2py-menu-vertical'
      li_class: defaults to 'web2py-menu-expand'

    Example:
        menu = MENU([['name', False, URL(...), [submenu]], ...])
        {{=menu}}
    """

    tag = 'ul'

    def __init__(self, data, **args):
        self.data = data
        self.attributes = args
        if not '_class' in self.attributes:
            self['_class'] = 'web2py-menu web2py-menu-vertical'
        if not 'ul_class' in self.attributes:
            self['ul_class'] = 'web2py-menu-vertical'
        if not 'li_class' in self.attributes:
            self['li_class'] = 'web2py-menu-expand'
        if not 'li_active' in self.attributes:
            self['li_active'] = 'web2py-menu-active'

    def serialize(self, data, level=0):
        if level == 0:
            ul = UL(**self.attributes)
        else:
            ul = UL(_class=self['ul_class'])
        for item in data:
            (name, active, link) = item[:3]
            if isinstance(link,DIV):
                li = LI(link)
            elif 'no_link_url' in self.attributes and self['no_link_url']==link:
                li = LI(DIV(name))
            elif link:
                li = LI(A(name, _href=link))
            else:
                li = LI(A(name, _href='#',
                          _onclick='javascript:void(0):return false'))
            if len(item) > 3 and item[3]:
                li['_class'] = self['li_class']
                li.append(self.serialize(item[3], level+1))
            if active or ('active_url' in self.attributes and self['active_url']==link):
                if li['_class']:
                    li['_class'] = li['_class']+' '+self['li_active']
                else:
                    li['_class'] = self['li_active']
            ul.append(li)
        return ul

    def xml(self):
        return self.serialize(self.data, 0).xml()


def embed64(
    filename = None,
    file = None,
    data = None,
    extension = 'image/gif',
    ):
    """
    helper to encode the provided (binary) data into base64.

    :param filename: if provided, opens and reads this file in 'rb' mode
    :param file: if provided, reads this file
    :param data: if provided, uses the provided data
    """

    if filename and os.path.exists(file):
        fp = open(filename, 'rb')
        data = fp.read()
        fp.close()
    data = base64.b64encode(data)
    return 'data:%s;base64,%s' % (extension, data)


def test():
    """
    Example:

    >>> from validators import *
    >>> print DIV(A('click me', _href=URL(a='a', c='b', f='c')), BR(), HR(), DIV(SPAN(\"World\"), _class='unknown')).xml()
    <div><a href=\"/a/b/c\">click me</a><br /><hr /><div class=\"unknown\"><span>World</span></div></div>
    >>> print DIV(UL(\"doc\",\"cat\",\"mouse\")).xml()
    <div><ul><li>doc</li><li>cat</li><li>mouse</li></ul></div>
    >>> print DIV(UL(\"doc\", LI(\"cat\", _class='feline'), 18)).xml()
    <div><ul><li>doc</li><li class=\"feline\">cat</li><li>18</li></ul></div>
    >>> print TABLE(['a', 'b', 'c'], TR('d', 'e', 'f'), TR(TD(1), TD(2), TD(3))).xml()
    <table><tr><td>a</td><td>b</td><td>c</td></tr><tr><td>d</td><td>e</td><td>f</td></tr><tr><td>1</td><td>2</td><td>3</td></tr></table>
    >>> form=FORM(INPUT(_type='text', _name='myvar', requires=IS_EXPR('int(value)<10')))
    >>> print form.xml()
    <form action=\"\" enctype=\"multipart/form-data\" method=\"post\"><input name=\"myvar\" type=\"text\" /></form>
    >>> print form.accepts({'myvar':'34'}, formname=None)
    False
    >>> print form.xml()
    <form action="" enctype="multipart/form-data" method="post"><input name="myvar" type="text" value="34" /><div class="error" id="myvar__error">invalid expression</div></form>
    >>> print form.accepts({'myvar':'4'}, formname=None, keepvalues=True)
    True
    >>> print form.xml()
    <form action=\"\" enctype=\"multipart/form-data\" method=\"post\"><input name=\"myvar\" type=\"text\" value=\"4\" /></form>
    >>> form=FORM(SELECT('cat', 'dog', _name='myvar'))
    >>> print form.accepts({'myvar':'dog'}, formname=None, keepvalues=True)
    True
    >>> print form.xml()
    <form action=\"\" enctype=\"multipart/form-data\" method=\"post\"><select name=\"myvar\"><option value=\"cat\">cat</option><option selected=\"selected\" value=\"dog\">dog</option></select></form>
    >>> form=FORM(INPUT(_type='text', _name='myvar', requires=IS_MATCH('^\w+$', 'only alphanumeric!')))
    >>> print form.accepts({'myvar':'as df'}, formname=None)
    False
    >>> print form.xml()
    <form action=\"\" enctype=\"multipart/form-data\" method=\"post\"><input name=\"myvar\" type=\"text\" value=\"as df\" /><div class=\"error\" id=\"myvar__error\">only alphanumeric!</div></form>
    >>> session={}
    >>> form=FORM(INPUT(value=\"Hello World\", _name=\"var\", requires=IS_MATCH('^\w+$')))
    >>> if form.accepts({}, session,formname=None): print 'passed'
    >>> if form.accepts({'var':'test ', '_formkey': session['_formkey[None]']}, session, formname=None): print 'passed'
    """
    pass


class web2pyHTMLParser(HTMLParser):
    """
    obj = web2pyHTMLParser(text) parses and html/xml text into web2py helpers.
    obj.tree contains the root of the tree, and tree can be manipulated

    >>> str(web2pyHTMLParser('hello<div a="b" c=3>wor&lt;ld<span>xxx</span>y<script/>yy</div>zzz').tree)
    'hello<div a="b" c="3">wor&lt;ld<span>xxx</span>y<script></script>yy</div>zzz'
    >>> str(web2pyHTMLParser('<div>a<span>b</div>c').tree)
    '<div>a<span>b</span></div>c'
    >>> tree = web2pyHTMLParser('hello<div a="b">world</div>').tree
    >>> tree.element(_a='b')['_c']=5
    >>> str(tree)
    'hello<div a="b" c="5">world</div>'
    """
    def __init__(self,text,closed=('input','link')):
        HTMLParser.__init__(self)
        self.tree = self.parent = TAG['']()
        self.closed = closed
        self.tags = [x for x in __all__ if isinstance(eval(x),DIV)]
        self.last = None
        self.feed(text)
    def handle_starttag(self, tagname, attrs):
        if tagname.upper() in self.tags:
            tag=eval(tagname.upper())
        else:
            if tagname in self.closed: tagname+='/'
            tag = TAG[tagname]()
        for key,value in attrs: tag['_'+key]=value
        tag.parent = self.parent
        self.parent.append(tag)
        if not tag.tag.endswith('/'):
            self.parent=tag
        else:
            self.last = tag.tag[:-1]
    def handle_data(self,data):
        try:
            self.parent.append(data.encode('utf8','xmlcharref'))
        except:
            self.parent.append(data.decode('latin1').encode('utf8','xmlcharref'))
    def handle_charref(self,name):
        if name[1].lower()=='x':
            self.parent.append(unichr(int(name[2:], 16)).encode('utf8'))
        else:
            self.parent.append(unichr(int(name[1:], 10)).encode('utf8'))
    def handle_entityref(self,name):
        self.parent.append(unichr(name2codepoint[name]).encode('utf8'))
    def handle_endtag(self, tagname):
        # this deals with unbalanced tags
        if tagname==self.last:
            return
        while True:
            try:
                parent_tagname=self.parent.tag
                self.parent = self.parent.parent
            except:
                raise RuntimeError, "unable to balance tag %s" % tagname
            if parent_tagname[:len(tagname)]==tagname: break

def markdown_serializer(text,tag=None,attr={}):
    if tag is None: return re.sub('\s+',' ',text)
    if tag=='br': return '\n\n'
    if tag=='h1': return '#'+text+'\n\n'
    if tag=='h2': return '#'*2+text+'\n\n'
    if tag=='h3': return '#'*3+text+'\n\n'
    if tag=='h4': return '#'*4+text+'\n\n'
    if tag=='p': return text+'\n\n'
    if tag=='b' or tag=='strong': return '**%s**' % text
    if tag=='em' or tag=='i': return '*%s*' % text
    if tag=='tt' or tag=='code': return '`%s`' % text
    if tag=='a': return '[%s](%s)' % (text,attr.get('_href',''))
    if tag=='img': return '![%s](%s)' % (attr.get('_alt',''),attr.get('_src',''))
    return text

def markmin_serializer(text,tag=None,attr={}):
    if tag is None: return re.sub('\s+',' ',text)
    if tag=='br': return '\n\n'
    if tag=='h1': return '# '+text+'\n\n'
    if tag=='h2': return '#'*2+' '+text+'\n\n'
    if tag=='h3': return '#'*3+' '+text+'\n\n'
    if tag=='h4': return '#'*4+' '+text+'\n\n'
    if tag=='p': return text+'\n\n'
    if tag=='li': return '\n- '+text.replace('\n',' ')
    if tag=='tr': return text[3:].replace('\n',' ')+'\n'
    if tag in ['table','blockquote']: return '\n-----\n'+text+'\n------\n'
    if tag in ['td','th']: return ' | '+text
    if tag in ['b','strong','label']: return '**%s**' % text
    if tag in ['em','i']: return "''%s''" % text
    if tag in ['tt','code']: return '``%s``' % text
    if tag=='a': return '[[%s %s]]' % (text,attr.get('_href',''))
    if tag=='img': return '[[%s %s left]]' % (attr.get('_alt','no title'),attr.get('_src',''))
    return text


class MARKMIN(XmlComponent):
    """
    For documentation: http://web2py.com/examples/static/markmin.html
    """
    def __init__(self, text, extra={}, allowed={}, sep='p'):
        self.text = text
        self.extra = extra
        self.allowed = allowed
        self.sep = sep

    def xml(self):
        """
        calls the gluon.contrib.markmin render function to convert the wiki syntax
        """
        return render(self.text,extra=self.extra,allowed=self.allowed,sep=self.sep)

    def __str__(self):
        return self.xml()

    def flatten(self,render=None):
        """
        return the text stored by the MARKMIN object rendered by the render function
        """
        return self.text

    def elements(self, *args, **kargs):
        """
        to be considered experimental since the behavior of this method is questionable
        another options could be TAG(self.text).elements(*args,**kargs)
        """
        return [self.text]


if __name__ == '__main__':
    import doctest
    doctest.testmod()
