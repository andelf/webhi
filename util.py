#!/usr/bin/env python
# -*- coding: utf-8 -*-

#import os
#module = type(os)
import time
import exceptions

orgin_sleep = time.sleep

def safe_xrange(*args):
    if len(args) == 1:
        assert args[0] < 100, "YOU CANNOT DO THAT!"
    elif len(args) == 2:
        assert args[-1] - args[0] < 100, "YOU CANNOT DO THAT!"
    elif len(args) == 3:
        assert (args[-2] - args[0]) / args[-1] < 100,  "YOU CANNOT DO THAT!"
    return xrange(*args)
safe_xrange.func_name = 'xrange'

def safe_range(*args):
    if len(args) == 1:
        assert args[0] < 100, "YOU CANNOT DO THAT!"
    elif len(args) == 2:
        assert args[-1] - args[0] < 100, "YOU CANNOT DO THAT!"
    elif len(args) == 3:
        assert (args[-2] - args[0]) / args[-1] < 100,  "YOU CANNOT DO THAT!"
    return range(*args)
safe_range.func_name = 'range'

def safe_import(*args):
    assert args[0] in ['string', 're', 'struct', 'codecs', 'datetime',
                       'calendar', 'pprint', 'time', 'math', 'cmath'], "YOU CANNOT IMPORT THAT!"
    ret = __import__(*args)
    if args[0] == 'time':
        ret.sleep = lambda *_: None
    return ret
safe_import.func_name = '__import__'

def same_type(arg1, *args):
    '''Compares the class or type of two or more objects.'''
    t = getattr(arg1, '__class__', type(arg1))
    for arg in args:
        if getattr(arg, '__class__', type(arg)) is not t:
            return 0
    return 1


#fake_builtins = module('__fake_builtins__', "A fake __builtins__ module :)")
import __builtin__
#__builtin__.__dict__,
fake_builtins = dict(
                     xrange = safe_xrange,
                     range = safe_range,
                     __import__ = safe_import,
                     same_type = same_type,
                     )

unsafe = 'compile copyright delattr dir dreload eval execfile ' + \
    'exit file getattr globals help input intern license locals memoryview open ' + \
    'reload raw_input setattr super type vars'

safe =  ['False', 'None', 'True', 'abs', 'basestring', 'bool', 'callable',
         'chr', 'cmp', 'complex', 'divmod', 'float', 'hash',
         'hex', 'id', 'int', 'isinstance', 'issubclass', 'len',
         'long', 'oct', 'ord', 'pow', 'range', 'repr', 'round',
         'str', 'tuple', 'unichr', 'unicode', 'xrange', 'zip']

for key in safe:
    if key not in fake_builtins:
        fake_builtins[key] = getattr(__builtin__, key)

# exceptions
for name in dir(exceptions):
    if name[0] != "_":
        fake_builtins[name] = getattr(exceptions, name)


        #      31 GET_ITER
        # >>   32 FOR_ITER                11 (to 46)
        #      35 STORE_FAST               1 (b)


def inject_code(code):
    import byteplay
    import pprint
    def inject_byteplay_code(c):
        #pprint.pprint( c.code )
        i = 0
        while i < len(c.code):
            v = c.code[i]
            if type(v[1]) == type(c): # if a nested code obj
                #print 'nested!'
                c.code[i] = (v[0], inject_byteplay_code(v[1]))
            elif v[0] != byteplay.POP_JUMP_IF_FALSE:
                i += 1
                continue

            while_jump_index = i
            c.code[while_jump_index+1:while_jump_index+1] = [
                (byteplay.LOAD_NAME, '__timing_func'),
                (byteplay.CALL_FUNCTION, 0),
                c.code[while_jump_index],
                ]                   # add jump
            i += 4
        return c

    c = byteplay.Code.from_code(code)
    c = inject_byteplay_code(c)
    code = c.to_code()
    return code

def exec_output(codestr):
    import sys
    import StringIO
    import traceback
    import os
    import codeop

    buf = StringIO.StringIO()
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = os.devnull
    sys.stdout = buf
    sys.stderr = buf
    #import util
    startTime = time.time()
    try:
        code = codeop.compile_command(codestr)
    except SyntaxError, e:
        print 'COMPILE ERROR!'
        #print e
    try:
        #exec code in dict(__builtins__={'xrange': xrange})#util.fake_builtins)
        #code = codeop.compile_command(codestr)
        code = compile(codestr, '<hi-input>', 'exec')
        code = inject_code(code)
        def __timing_func():
            #orgin_sleep(0.1)    # orgin sleep~
            if time.time() - startTime > 2:
                print u'\nERROR: 循环次数受限!!',
                return False
            return True
        #raise SystemExit
        exec code in dict(__builtins__=dict(fake_builtins), __timing_func=__timing_func )
    except Exception, e:
        import traceback
        traceback.print_exc()
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    reload(time)
    ret = buf.getvalue()
    lines = ret.split('\n')
    if len(lines) > 12:
        lines = lines[:4] + ['........'] + lines[-5:]
    ret = '\n'.join(lines)
    if len(ret) > 80 * 11:
        ret = u'亲, 你那坨代码输出太多了.... 不给你看了. 自己跑去!'
    if isinstance(ret, unicode):
        return ret
    else:
        # FIXED: encoding replace
        return unicode(ret, 'utf8', 'replace')

demo = '''
# fuck
import time
def a():
  while 1==1:
    print 'ok'
a()

while 1==1:
    print 1
while 1==1:
    print 1
while 1==1:
    print 1

'''

if __name__ == '__main__':
    print exec_output(demo)


def queryUser(keyword):

    if isinstance(keyword, unicode):
        keyword = keyword.encode('utf8')
    url = 'http://family.baidu.com/addressbook/searchuser.do'
    data = 'pagesize=10&pageNum=1&isByStart=0&q=%s&limit=10&timestamp=%s&s=%s' % (keyword, timestamp(), keyword)
    cp = urllib2.HTTPCookieProcessor()
    opener = urllib2.build_opener(cp)
    opener.addheaders = [
        ('User-agent', 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.24 ' \
             '(KHTML, like Gecko) Chrome/19.0.1056.0 Safari/535.24'),
        ('X-Requested-With', 'XMLHttpRequest'),
        ('Referer', 'http://family.baidu.com/core/index.jsp'),
        ('Origin', 'http://family.baidu.com'),
        ]
    opener.open('http://family.baidu.com/')
    opener.open('http://family.baidu.com/core/index.jsp?chc=1603971430')

    req = urllib2.Request(url, data=data)
    global ret
    ret = opener.open(req)
    html = ret.read()
    print ret
    data = json.loads(html)
    print data
    return data
# following need to wrap
# __import__
# apply
# dict
# enumerate
# filter
# getattr
# hasattr
# iter
# list
# map
# max
# min
# sum
# all
# any
