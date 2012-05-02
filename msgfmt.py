#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import base64
import hashlib
import cgi

# <msg><font n="宋体" s="10" b="0" i="0" ul="0" c="0"/><text c="sdfasdffda"/><face n="撇嘴"/><text c="asdfsfd"/></msg>
# <msg><font n="宋体" s="10" b="0" i="0" ul="0" c="0"/><text c=""/><face n="囧"/><text c=""/></msg>
# <msg><font n="宋体" s="10" b="0" i="0" ul="0" c="0"/><text c=""/><face n="可爱 "/><text c="asdf"/><face n="困"/><text c="asdfasdf"/><face n="再见"/><text c="adsfasdf"/><face n="枯萎"/><text c="asdfasd"/></msg>
# <msg><font n="宋体" s="10" b="0" i="0" ul="0" c="0"/><img n="9BA5EC29F8" md5="2e7c9e476a849eb1c8d2bfed3a20ef52" t="png"/></msg>
# <msg><font n="宋体" s="10" b="0" i="0" ul="0" c="0"/><text c=""/><url ref="https://github.com/andelf/baiduhi"/><text c=""/></msg>
# <reply t="1" n="发送者的显示名称" c="哈哈" />
# t=1 回复
# t=2 引用
# t=其他, 无标签
# {u'n': u'b804396205', u'type': u'cface', u't': u'jpg', u'md5': u'b80439620592368b0874e7a7b3442059'}

def escape(content):
    return cgi.escape(content, quote=True).replace("'", '&#39;')

def font(name, size=10, color=0x000000, bold=False, italic=False, underline=False):
    # 0xff0000 -> blue
    # 0x00ff00 -> green
    # 0x0000ff -> red
    return u'<font n="%s" s="%d" b="%d" i="%d" ul="%d" c="%d"/>' % (
        name, size, bold, italic, underline, color)

def text(content=u''):
    return u'<text c="%s"/>' % escape(content)

def face(name=u'睡'):
    return u'<face n="%s"/>' % name

def cface(md5, type='jpg'):
    assert len(md5) == 32
    return u' <cface md5="%s" t="%s" n="%s"/>' % (md5, type, md5[:10])

def url(ref='http://www.baidu.com'):
    return u'<url ref="%s"/>' % ref

def reply(name, content=u'', type=1):
    return u'<reply t="%s" n="%s" c="%s"/>' % (type, name, escape(content))

def quote(name, content=u''):
    return reply(name, content, type=2)

def img(fpath):
    type = os.path.splitext(fpath.lower())[-1][1:]
    with open(fpath, 'rb') as fp:
        data = fp.read()
    md5 = hashlib.md5(data).hexdigest()
    imagedata = data.encode('base64').strip()
    data = u'<img md5="%s" t="%s" n="%s"><image imagedata="%s"/></img>' % (md5, type, md5[:10], imagedata)
    return data

def md5img(md5, type='jpg'):
    # msg.md5img('31A8743ADC827555A0A554EAB8EC0B9A', 'jpg')
    return u'<img md5="%s" t="%s" n="%s"></img>' % (md5, type, md5[:10])
    

class Message(object):
    """Wrapper for xml-msg format"""
    def __init__(self, fontname=u'宋体', size=10, color=0x000000, bold=False, italic=False, underline=False) :
        self._raw_lines = []
        self._raw_lines.append(font(fontname, size, color, bold, italic, underline))

        self._text_lines = []

        self.text = lambda t: (self._raw_lines.append(text(t)),
                               self._text_lines.append(t))
        self.face = lambda n: (self._raw_lines.append(face(n)),
                               self._text_lines.append('[%s]' % n))
        self.cface = lambda *args, **kwargs: self._raw_lines.append(cface(*args, **kwargs))
        self.url = lambda u: (self._raw_lines.append(url(u)),
                              self._text_lines.append(u))
        self.reply = lambda *args, **kwargs: self._raw_lines.append(reply(*args, **kwargs))
        self.quote = lambda *args, **kwargs: self._raw_lines.append(quote(*args, **kwargs))
        self.img = lambda *args, **kwargs: self._raw_lines.append(img(*args, **kwargs))
        self.md5img = lambda *args, **kwargs: self._raw_lines.append(md5img(*args, **kwargs))

    def toString(self):
        return u'<msg>%s</msg>' % (''.join(self._raw_lines))

    def __unicode__(self):
        return self.toString()

    def rawString(self):
        return u' '.join(self._text_lines)
                              

def parserJsonMessage(jsondata):
    #{ "type": "img" },
    #{ "type": "reply", "t":"1", "n":"nickname", "c":"content"}]"""
    raw_lines = []
    for item in jsondata:
        if item['type'] == 'text':
            raw_lines.append(item['c'])
        elif item['type'] == 'url':
            raw_lines.append(item['ref'])
        elif item['type'] == 'reply':
            raw_lines.append(u'@%s' % item['n'])
        elif item['type'].endswith('face'):
            raw_lines.append(u'[%s]' % item['n'])
    return u' '.join(raw_lines)
        

