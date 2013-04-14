#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import sys
import urllib
import urllib2
import httplib
import urlparse
import logging
import logging.handlers
import re
import cookielib
import time
import random
import string
import cgi
try:
    import simplejson as json
except ImportError:
    import json
import socket
socket.setdefaulttimeout(40)    # 40s
import msgfmt

__encoding__ = sys.getdefaultencoding()
if os.name == 'nt':
    __encoding__ = 'gbk'

def randomstr(n=10):
    seeds = string.lowercase + string.digits
    return ''.join(random.sample(seeds, n))

def timestamp():
    return int(time.time() * 1000)

def radix(n, base=36):
    digits = string.digits + string.lowercase
    def shortDiv(n, acc=list()):
        q, r = divmod(n, base)
        return [r] + acc if q == 0 else shortDiv(q, [r] + acc)
    return ''.join(digits[i] for i in shortDiv(n))

def timechecksum():
    return radix(timestamp())

def login_time(l):
    return (l + random.randint(1,l))*500 + random.randint(1,1000)

# init logger
logger = logging.getLogger('BaiduHi')
#logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(asctime)s: %(name)s * %(thread)d %(message)s',
                              datefmt='%m-%d %H:%M:%S')

ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.WatchedFileHandler('./baiduhi.log', encoding='gb18030')
fh.setFormatter(formatter)
logger.addHandler(fh)

__cookies__ = os.path.join(os.path.dirname(__file__), 'cookies.txt')

__default_answer_map__ = {
    u'你好': u'你也好~',
    u'hi'  : u'hi~',
    u'在么': u'呵呵',
    u'在不': u'在的~',
    u'在吗': u'在的~',
    u'再见': u'嗯. 再见!',
    u'谢谢': u'不客气~',
    u'天王盖地虎' : u'宝塔镇河妖',
    u'哈哈': u'你笑啥呢?',
    u'呵呵': u'好吧...呵呵...',
    u'怎么': u'我也不懂.',
    u'知道么': u'我也不知道',
    u'你傻': u'你才傻呢, 你们全家都傻!',
    u'笨蛋': u'你才笨蛋呢, 你们全家都是!',
    u'noah': u'恩.. noah上线吧~',
    u'测试': u'测试不到位... OP只能继续苦逼',
    u'你不是人': u'你才不是人呢, 你们都不是人',
    u'太高端了': u'哈...谢谢夸奖...',
    }

class BaiduHi(object):
    """BaiduHi Client"""
    def __init__(self, username, password, logger=logger):

        self.username = username
        self.password = password
        self.log = logger

        #cj = cookielib.CookieJar() # nor FileCookieJar
        cj = cookielib.LWPCookieJar(__cookies__)
        cp = urllib2.HTTPCookieProcessor(cj)
        opener = urllib2.build_opener(cp)
        opener.addheaders = [
            ('User-agent', 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.24 ' \
             '(KHTML, like Gecko) Chrome/19.0.1056.0 Safari/535.24'),]
        self._cookiejar = cj
        self._opener = opener
        self._seq = 0
        self._apidata = dict()
        self._pickack = ''
        self._lastMessageTimestamp = 0

        self._answer_map = __default_answer_map__.copy()
        self._default_handler = None # TODO
        # handler
        self.registerKeyword('time', do_time)
        self.registerKeyword('help', self.handleHelp)
        self.registerKeyword('about', do_about)


    @property
    def seq(self):
        ret = self._seq
        self._seq += 1
        return ret

    @seq.setter
    def seq(self, value):
        self._seq = value

    def login(self, stage=0):
        # clean api common data
        self._apidata = dict()
        req = urllib2.Request('http://web.im.baidu.com/')
        ret = self._opener.open(req)
        ret.read()
        ret = self._apiReqest('check', v=30, time=timechecksum())
        if ret['result'] == 'ok':
            self._cookiejar.save()
            # self.password = None
            return True
        elif stage >= 2:
            return False
        assert ret['result'] == 'offline'

        req = urllib2.Request('https://passport.baidu.com/v2/api/?getapi&class=login&tpl=mn&tangram=false') # get BAIDUID cookie
        self._opener.open(req).read()

        req = urllib2.Request('https://passport.baidu.com/v2/api/?getapi&class=login&tpl=mn&tangram=false')
        html = self._opener.open(req).read()
        token = re.findall(r"login_token\s*=\s*'([^']+)", html)[0]
        if not re.match('^[0-9a-zA-Z]+$', token):
            self.log.fatal('Get passport token error: %s', token)
            return False

        self.log.debug('Login token: %s', token)

        req = urllib2.Request('https://passport.baidu.com/v2/api/?logincheck&tpl=mn&charset=UTF-8&index=0&username=%s&time=%s' % (self.username, timestamp()))
        data = self._opener.open(req).read().strip()[1:-1] # remove brackets
        data = eval(data, type('Dummy', (dict,), dict(__getitem__=lambda s,n:n))())
        if int(data['errno']) != 0:
            # FATAL error
            self.log.fatal('Login passport error: %s', data)
            return False

        verifycode = ''
        if data['codestring'] != '':
            verifycode = self.getVerifyCode(data['codestring'])

        params = data.copy()
        params['username'] = self.username
        params['password'] = self.password
        params['ppui_logintime'] = login_time(len(params['username'] + params['password']))
        params['verifycode'] = verifycode
        params['safeflg'] = '0' # 1 -> True
        params['mem_pass'] = 'on'
        params['charset'] = 'UTF-8'
        params['token'] = token
        params['isPhone'] = 'false'
        params['u'] = ''
        params['mem_pass'] = 'on'
        params['staticpage'] = 'http://web.im.baidu.com/popup/src/v2Jump.html'
        params['loginType'] = '1'
        params['tpl'] = 'mn'
        self.log.debug('Login Params after filling: %s', params)
        req = urllib2.Request('https://passport.baidu.com/v2/api/?login',
                              data=urllib.urlencode(params))
        html = self._opener.open(req).read()
        url = re.findall(r"encodeURI\('(.*?)'\)", html)[0]
        self.log.debug('Login jump popup url: %s', url)
        self._opener.open(url).read()
        # 2次登陆校验
        return self.login(stage=stage+1)

    def init(self):
        # 登陆后初始化
        self.seq = 0
        guid = timechecksum()
        # api 请求公用数据
        self._apidata = dict(v=30, session='', source=22, guid=guid,
                             seq=lambda : self.seq) # dynamic callable
        # 开始登陆过程
        self._apiReqest('welcome', method='POST', extraData={'from': 0},
                        seq=self.seq, force='true')
        ret = self._apiReqest('init', method='POST',
                              status='online')
        if ret['result'] == 'ok':
            self.log.info('Login ok: username=%s, nick=%s', ret['content']['username'], ret['content']['nickname'])
        # 第一次pick 自己是否登陆成功, ack = 0
        self.pick()
        # 好友分组
        self._apiReqest('getmultiteaminfo')
        self._apiReqest('blocklist', page=0)
        self._apiReqest('oldsystem', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('oldmessage', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('oldnotify', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('getsystemmessage')
        self._apiReqest('oldgroupmessage', lastGid=0, lastMessageId=0, lastMessageTime=0)
        # 好友分组列出
        #self._apiReqest('getmultifriendlist', data=commondata, seq=self.seq,
        #                tid=0, page=0, field='relationship,username,showname,showtype,status')
        return True

    def pick(self):
        """main callback func"""
        ret = self._apiReqest('pick', type=23, flag=1, ack=self._pickack)
        if ret['result'] != 'ok':
            if ret['result'] == 'kicked':
                self.log.error('Kicked by system!')
                raise SystemExit
            elif ret['result'] == 'networkerror':
                self.log.fatal('Network error')
                raise SystemExit
            else:
                self.log.error('Pick() error: %s', ret)
        if ret['content']:      # if has content
            # ack 必须传输
            self._pickack = ret['content']['ack'] # to be acked
            for field in ret['content']['fields']:
                self._handlePickField(field)

    def _handlePickField(self, field):
        if field['result'] != 'ok':
            self.log.error('handlePickFiled error: %s', field)
            return
        if field['command'] == 'message':
            # 普通消息
            sender = field['from']
            cnt = field['content']
            income = msgfmt.parserJsonMessage(cnt).strip()
            self.log.info('Message from <uid:%s>: %s', sender, income)
            reply = self.getAnswerByQuestion(income, sender=field['from']) or None
            if reply is None:
                return
            # self.log.info('Message reply <uid:%s>: %s', sender, reply.rawString())
            self.sendMessage(sender, reply)

        elif field['command'] == 'groupmessage':
            # group msg has a {content: {content: {}}} structure
            cnt = field['content']
            sender = cnt['from']
            gid = cnt['gid']
            income = msgfmt.parserJsonMessage(cnt['content']).strip()
            self.log.info('Group message from %s@%s: %s', sender, gid, income)
            reply = self.getAnswerByQuestion(income, sender=cnt['from'], gid=cnt['gid']) or None
            if reply is None:
                return
            self.sendGroupMessage(cnt['gid'], reply)
            #self.log.info('Group message reply %s@%s: %s', sender, gid, reply.rawString())
            #self._apiReqest('groupmessage', method='POST', extraData={'from': self.username},
            #                      messageid=self._seq, gid=cnt['gid'], body=unicode(reply))


        elif field['command'] == 'activity':
            # print u'动态消息', field
            self.log.info('Activity Update: %s', field)
        elif field['command'] == 'friendaddnotify':
            #print u'来自别人的好友申请'
            # print cnt['username'], u'添加好友, 验证消息:', cnt['comment']
            cnt = field['content']
            username = cnt['username']
            comment = cnt['comment'].strip()
            self.log.info('Friendship apply from <uid:%s>: %s', username, comment)
            if u'宝塔镇河妖' not in comment: # 验证 fail
                cmt = u'天王盖地虎?'
                #self.deleteFriend(username)
                self.log.info('Friendship apply rejected <uid:%s>: %s', username, cmt)
                self._apiReqest('verifyfriend', method='POST', username=username, agreen=0, comment=cmt)
            else:
                cmt = u'接受'
                self.log.info('Friendship apply accepted <uid:%s>: %s', username, cmt)
                self._apiReqest('verifyfriend', method='POST', username=username, agree=1, comment=cmt)
                self.addFriend(cnt['username'])

        elif field['command'] == 'addgroupmembernotify':
            #print u'添加群成员后的通知'
            #{u'content': {u'memberList': [{u'username': u'fledna'}], u'gid': u'1368022',
            # u'managerName': u'andelf', u'time': 1335687504}, u'command': u'addgroupmembernotify', u'result': u'ok'}
            self.log.info("Added to <gid:%s> by %s", field['content']['gid'], field['content']['managerName'])
        elif field['command'] == 'deletegroupmembernotify':
            #print u'删除群成员后的通知'
            #{u'content': {u'memberList': [{u'username': u'fledna'}], u'groupName': u'Test', u'gid': u'1368022',
            #u'managerName': u'andelf', u'time': 1335687280}, u'command': u'deletegroupmembernotify', u'result': u'ok'}
            self.log.info("Deleted from %s<gid:%s> by %s", field['content']['groupName'], field['content']['gid'], field['content']['managerName'])
        elif field['command'] == 'friendstatus':
            #print u'好友(个人)状态改变'
            #print field
            cnt = field['content']
            username = cnt['username']
            # STATUS = "online"|"offline"|"away"|"busy"|"hide"
            status_map = dict(online=u'上线', offline=u'下线', away=u'离开',
                              busy=u'忙碌', hide=u'隐身')
            if 'status' in cnt:
                status = status_map[cnt['status']]
                self.log.info('Status changed <uid:%s>: %s', username, status)
            if 'webStatus' in cnt:
                webStatus = status_map[cnt['webStatus']]
                #self.log.info('WebStatus changed <uid:%s>: %s', username, webStatus)
                # web status changes too often.
            if 'personalComment' in cnt:
                personalComment = cnt['personalComment'].strip()
                self.log.info('Personal Comment changed <uid:%s>: %s', username, personalComment)
            if 'nickname' in cnt:
                nickname = cnt['nickname']
                self.log.info('Nickname changed <uid:%s>: %s', username, nickname)
            # TODO
        elif field['command'] == 'friendinfonotify':
            cnt = field['content']
            self.log.info('Friend info notify %s', cnt)
        else:
            print field['command'], 'unhandled'
            print field

    def sendMessage(self, to, msg):
        self.log.info('Send message <uid:%s>: %s', to, msg.rawString())
        if time.time() - self._lastMessageTimestamp < 1.0:
            time.sleep(1)
        ret = self._apiReqest('message', method='POST', extraData={'from': self.username},
                              to=to, body=unicode(msg), friend='true')
                              #messageid=self._seq, to=to, body=unicode(msg), friend='true',)
        if ret['result'] != 'ok':
            self.log.error('sendMessage fail: %s', ret)
        self._lastMessageTimestamp = time.time()
        return ret

    def sendGroupMessage(self, to, msg):
        self.log.info('Send group message <gid:%s>: %s', to, msg.rawString())
        if time.time() - self._lastMessageTimestamp < 1.0:
            time.sleep(1)
        ret = self._apiReqest('groupmessage', method='POST', extraData={'from': self.username},
                              messageid='', gid=to, body=unicode(msg))
        if ret['result'] != 'ok':
            self.log.error('sendGroupMessage fail: %s', ret)
        self._lastMessageTimestamp = time.time()
        return ret

    def logout(self):
        self.log.info("Logout called.")
        try:
            return self._apiReqest('logout')['result'] == 'ok'
        except urllib2.URLError, e:
            self.log.fatal('logout error: str(e)')
            return False

    def verifycode(self, type, **params):
        ret = self._apiReqest('verifycode', type=type, **params)
        vdata = ret['content']['validate']

        if vdata.get('v_code', None):
            return ','.join([vdata['v_url'], vdata['v_period'], vdata['v_time'], vdata['v_code']])
        else:
            self.log.error('Verifycode not implemented! type=%s, args=%s', type, params)
            return None
        # return validate
        imgurl = 'http://vcode.im.baidu.com/cgi-bin/genimg?%s&_time=%s' % \
            (vdata['v_url'], timechecksum())
        data = self._opener.open(imgurl).read()
        with open('./pic.jpg', 'wb') as fp:
            fp.write(data)
            self.log.info('Verify code pic download ok! `./pic.jpg`')
        code = 'abcd' # raw_input('plz input code:').strip()
        return ','.join([vdata['v_url'], vdata['v_period'], vdata['v_time'], code])

    def queryInfo(self, username):
        ret = self._apiReqest('queryinfo', username=username,
                              field='relationship,username,showname,showtype,status')
        if ret['result'] == 'ok':
            return ret['content']['fields']
        return None

    def addFriend(self, username, tid=0, comment=u'回加'):
        users = self.queryInfo(username)
        if users is None:
            self.log.error('Add friend <uid:%s> failed: aquire userinfo fail', username)
            return False
        info = users[0]
        #if info['relationship'] != 2:
        #    self.log.error('Add friend <uid:%s> failed: relationship != 2', username)
        #    return False
        validate = self.verifycode(type='addfriend', username=username)
        ret = self._apiReqest('addfriend', username=username, tid=tid, comment=comment, validate=validate)
        if ret['result'] == 'ok':
            return True
        else:
            self.log.error('Add friend <uid:%s> failed: %s', username, ret)
        return False

    def deleteFriend(self, username):
        validate = self.verifycode(type='deletefriend', username=username)
        ret = self._apiReqest('deletefriend', username=username, validate=validate)
        if ret['result'] == 'ok':
            #print ret
            return True
        else:
            self.log.error('Delete friend <uid:%s> failed: %s', username, ret)
        return False

    def getVerifyCode(self, codestring):
        """验证码处理"""
        #url = 'https://passport.baidu.com/?verifypic&t=%d' % timestamp()
        url = 'https://passport.baidu.com/cgi-bin/genimage?%s&v=%s' % (codestring, timestamp())
        req = urllib2.Request(url)
        data = self._opener.open(req).read()
        with open('./pic.png', 'wb') as fp:
            fp.write(data)
            self.log.info('Verify code pic download ok! `./pic.png`')
        return raw_input('plz input code:').strip()

    def _apiReqest(self, api, method='GET', extraData=dict(), _retryLimit=2, **params):
        url = urlparse.urljoin('http://web.im.baidu.com/', api)
        data = self._apidata.copy()
        data.update(extraData)
        data.update(params)
        for key in data:
            # dynamic callable item
            if callable(data[key]):
                data[key] = data[key]() # call it :)
            # flatten list value
            if isinstance(data[key], (list, tuple, set)):
                data[key] = ','.join(map(str, list(data[key])))
            if isinstance(data[key], unicode):
                data[key] = data[key].encode('utf-8')
        self.log.debug('API request `%s`: %s', api, data)
        if method == 'GET':
            query = urllib.urlencode(data)
            url = '%s?%s' % (url, query)
            req = urllib2.Request(url)
        elif method == 'POST':
            body = urllib.urlencode(data)
            req = urllib2.Request(url, data=body)
        start = time.time()
        try:
            ret = self._opener.open(req)
        except Exception, e:
            if _retryLimit == 0:
                self.log.fatal('Api request error: url=%s error=%s', url, e)
                # make it {result: xxx}
                return dict(result='networkerror')
            else:
                _retryLimit -= 1
                self.log.error('Api request error, retry!')
                return self._apiReqest(api, method, extraData, _retryLimit, **params)
        raw = ret.read()
        try:
            data = json.loads(raw)
        except:
            # bad json format
            data = eval(raw, type('Dummy', (dict,), dict(__getitem__=lambda s,n:n))())
        self.log.debug('API response `%s`: %s TT=%.3fs', api, data, time.time() - start)
        return data

    def tick(self):
        """tick: heartbeat & msg pull"""
        try:
            self.pick()
        except httplib.HTTPException, e:
            self.log.error('http exception: %s', e)
        except socket.error, e:
            self.log.error('socket error: %s', e)
        time.sleep(1)

    def getAnswerByQuestion(self, income, sender, gid=None):
        time.sleep(0.1)         # sync wait
        ret = None
        stripped_income = income.replace(u'@' + unicode(self.username, __encoding__), '').strip().lower()
        for keyword in self._answer_map:
            #if keyword in income.lower():
            if stripped_income.startswith(keyword):
                ret = self._answer_map[keyword]
                # if is a function
                if callable(ret):
                    # func(income:unicode, sender:unicode, gid:int)
                    ret = ret(income, sender, gid, )
                break
        if ret is None:
            if callable(self._default_handler):
                return self._default_handler(income, sender, gid)
            return None
        # a group msg, but not to me
        if gid and (u'@' + self.username) not in income:
            return None
        # if already a Message Object, directy return
        if isinstance(ret, msgfmt.Message):
            return ret
        msg = msgfmt.Message(fontname=u'黑体', bold=False, size=11, color=0x6B4C3F)
        if gid:
            msg.reply(sender, income.replace('\n', ' ').replace('\r', ''))
            msg.text(u'\n')
        msg.text(ret)
        return msg

    def registerKeyword(self, keyword, handleFunction, withColon=False):
        assert keyword.replace(':', '').replace('.', '').isalnum()
        assert keyword.count('.') <= 1
        assert keyword.islower()
        if withColon and not keyword.endswith(':'):
            keyword = keyword + u':'
        self._answer_map[keyword] = handleFunction

    def unregisterKeyword(self, keyword):
        if keyword in self._answer_map:
            del self._answer_map[keyword]
        keyword = keyword + u':'
        if keyword in self._answer_map:
            del self._answer_map[keyword]

    def registerDefault(self, handler):
        self._default_handler = handler

    def handleHelp(self, income, sender, gid):
        u"""显示帮助信息."""
        words = []
        funcs = []
        for k, v in self._answer_map.items():
            if isinstance(v, (unicode, str, basestring, msgfmt.Message)):
                words.append(k)
            elif callable(v):
                funcs.append((k, v))
        funcs_doc = [u"%s -> %s" % (name, func.__doc__) for name, func in funcs]
        doc = u"""====聊天机器人帮助====
直接对话就可以激活我。群聊天请使用Hi的回复功能或者 @ 我。
{匹配回复}：
%s
{功能调用}：
%s""" % (u', '.join(words[::-1]), u'\n'.join(funcs_doc))
        msg = msgfmt.Message(fontname=u'黑体', bold=False, size=11, color=0x3C1FD0)
        #msg.face(u"花痴")
        msg.cface('b80439620592368b0874e7a7b3442059', 'jpg')
        msg.text(u'你好, 我是小丫~~~')
        msg.text(u'\n')
        #msg.face(u"疑问")
        msg.text(doc)

        return msg

def stripKeyword(income, keyword='time:'):
    income = income.replace(keyword, '$$$').split('$$$')[-1].strip()
    # .encode('gb18030')
    return income

def do_time(income, sender, gid):
    u"""显示当前日期时间."""
    question = stripKeyword(income, 'time:')
    return unicode(time.strftime("%Y年%m月%d日 %H:%M:%S"), 'utf-8')

def do_about(income, sender, gid):
    u"""显示机器人关于信息."""
    msg = msgfmt.Message(fontname=u'黑体', bold=False, size=11, color=0x3C1FD0)
    msg.cface('b80439620592368b0874e7a7b3442059', 'jpg')
    msg.text(u"关于小丫……")
    msg.text(u'\n')
    msg.text(u'''姓名：小丫
性别：不祥
年龄：不祥
爱好：瞎扯淡
协议：WebHi
版本：v0.2
作者：andelf''')
    return msg

#msg.md5img('0D01966D3517836037E24B74C44304C7', 'jpg')
# # 0xff0000 -> blue
# # 0x00ff00 -> green
# # 0x0000ff -> red
# if reply is None:
#     return
# self.log.info('Message reply <uid:%s>: %s', sender, reply)
# msg = msgfmt.Message(fontname=u'黑体', bold=True, size=12, color=0x6B4C3F)
# msg.text(reply)



# 表情获取
# http://file.im.baidu.com/get/file/content/old_image/5058c18b15e80449483771873d1b4441?from=page&rnd=16oi67o5b
#http://file.im.baidu.com/get/file/content/old_image/9180AAE4712AD6228C1B9ACA492117E1?from=page
# 文件:
#http://file.im.baidu.com/crossdomain.xml
#Referer:http://web.im.baidu.com/resources/common/flashes/upload_pic.swf

#client._apiReqest('modifyself', comment='Under Robot Mode.')

# vim: se ts=4 sw=4 et :
