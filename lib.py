#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
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

# init logger
logger = logging.getLogger('BaiduHi')
#logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
formatter = logging.Formatter('%(asctime)s:%(levelname)s (%(name)s) %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')

ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.WatchedFileHandler('./baiduhi.log', encoding='gb18030')
fh.setFormatter(formatter)
logger.addHandler(fh)

__cookies__ = os.path.join(os.path.dirname(__file__), 'cookies.txt')

class BaiduHi(object):
    """BaiduHi Client"""
    def __init__(self, username, password, logger=logger):

        self.username = username
        self.password = password
        self.log = logger

        #cj = cookielib.CookieJar() # nor FileCookieJar
        cj = cookielib.LWPCookieJar(__cookies__)
        cp = urllib2.HTTPCookieProcessor(cj)
        # TODO: add ProxyHandler
        opener = urllib2.build_opener(cp)
        opener.addheaders = [
            ('User-agent', 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.24 ' \
             '(KHTML, like Gecko) Chrome/19.0.1056.0 Safari/535.24'),
            ]
        self._cookiejar = cj
        self._opener = opener
        self._seq = 0
        self._apidata = dict()
        self._pickack = ''

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
        req = urllib2.Request('http://passport.baidu.com/api/?login&tpl=mn&time=%d' % timestamp())
        data = self._opener.open(req).read().strip()[1:-1] # remove brackets
        data = eval(data, type('Dummy', (dict,), dict(__getitem__=lambda s,n:n))())
        if int(data['error_no']) == 0:
            param_out = data['param_out']
            param_in = data['param_in']
            params = {v: param_out[k.replace('name', 'contex')] \
                          for k, v in param_out.items() \
                          if k.endswith('_name')}
            params.update({v: param_in[k.replace('name', 'value')] \
                          for k, v in param_in.items() \
                          if k.endswith('_name')})
            self.log.debug('Login params: %s', params)
            #{'username': '', 'safeflg': '', 'tpl': 'mn', 'verifycode': '1', 'mem_pass': '',
            # 'token': '06e01bdc91ebcccfafed5b9a317e8d97', 'time': '1331917294', 'password': ''}
            params['username'] = self.username
            params['password'] = self.password
            params['safeflg'] = '' # 1 -> True
            params['mem_pass'] = 'on'
            if int(params['verifycode']) == 1:
                # neet verify code
                params['verifycode'] = self.getVerifyCode()
            # 似乎第一次登陆总会失败
            params['staticpage'] = 'http://web.im.baidu.com/popup/src/login_jump.htm'
            self.log.debug('Login Params after filling: %s', params)
            req = urllib2.Request('https://passport.baidu.com/api/?login',
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
        self._apiReqest('oldsystem', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('oldmessage', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('oldnotify', lastMessageId=0, lastMessageTime=0)
        self._apiReqest('blocklist', page=0)
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
                self.log.error('kicked by system!')
                raise SystemExit
            return
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
            reply = getAnswerByQuestion(income, sender=field['from']) or None
            if reply is None:
                return
            self.log.info('Message reply <uid:%s>: %s', sender, reply.rawString())
            self._apiReqest('message', method='POST', extraData={'from': self.username},
                            messageid=self._seq, to=field['from'], body=unicode(reply))

        elif field['command'] == 'groupmessage':
            # group msg has a {content: {content: {}}} structure
            cnt = field['content']
            sender = cnt['from']
            gid = cnt['gid']
            income = msgfmt.parserJsonMessage(cnt['content']).strip()
            self.log.info('Group message from %s@%s: %s', sender, gid, income)
            reply = getAnswerByQuestion(income, sender=cnt['from'], gid=cnt['gid']) or None
            if reply is None:
                return
            self.log.info('Group message reply %s@%s: %s', sender, gid, reply.rawString())
            self._apiReqest('groupmessage', method='POST', extraData={'from': self.username},
                                  messageid=self._seq, gid=cnt['gid'], body=unicode(reply))
            
        elif field['command'] == 'activity':
            print u'动态消息', field
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
                self._apiReqest('verifyfriend', method='POST',
                                username=username, agreen=0,
                                comment=cmt)
            else:
                cmt = u'接受'
                self.log.info('Friendship apply accepted <uid:%s>: %s', username, cmt)
                self._apiReqest('verifyfriend', method='POST',
                                username=username, agree=1,
                                comment=cmt)
                self.addFriend(cnt['username'])

        elif field['command'] == 'addgroupmembernotify':
            #print u'添加群成员后的通知'
            #{u'content': {u'memberList': [{u'username': u'fledna'}], u'gid': u'1368022', u'managerName': u'andelf', u'time': 1335687504}, u'command': u'addgroupmembernotify', u'result': u'ok'}
            self.log.info("Added to <gid:%s> by %s", field['content']['gid'], field['content']['managerName'])
        elif field['command'] == 'deletegroupmembernotify':
            #print u'删除群成员后的通知'
            #{u'content': {u'memberList': [{u'username': u'fledna'}], u'groupName': u'Test', u'gid': u'1368022', u'managerName': u'andelf', u'time': 1335687280}, u'command': u'deletegroupmembernotify', u'result': u'ok'}
            self.log.info("Deleted from %s<gid:%s> by %s", field['content']['groupName'], field['content']['gid'], field['content']['managerName'])
        elif field['command'] == 'friendstatus':
            #print u'好友(个人)状态改变'
            #print field
            cnt = field['content']
            username = cnt['username']
            status_map = dict(online=u'上线了', offline=u'下线', away=u'离开',
                              busy=u'忙碌', hide=u'隐身')
            if 'status' in cnt:
                # STATUS = "online"|"offline"|"away"|"busy"|"hide"
                status = status_map[cnt['status']]
                self.log.info('Status changed <uid:%s>: %s', username, status)
            if 'webStatus' in cnt:
                webStatus = u'Web状态', status_map[cnt['webStatus']]
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

    def logout(self):
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

    def getVerifyCode(self):
        """验证码处理"""
        url = 'https://passport.baidu.com/?verifypic&t=%d' % timestamp()
        req = urllib2.Request(url)
        data = self._opener.open(req).read()
        with open('./pic.png', 'wb') as fp:
            fp.write(data)
            self.log.info('Verify code pic download ok! `./pic.png`')
        return raw_input('plz input code:').strip()

    def _apiReqest(self, api, method='GET', extraData=dict(), **params):
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
        ret = self._opener.open(req)
        raw = ret.read()
        try:
            data = json.loads(raw)
        except:
            # bad json format
            data = eval(raw, type('Dummy', (dict,), dict(__getitem__=lambda s,n:n))())
        self.log.debug('API response `%s`: %s TT=%.2fs', api, data, time.time() - start)
        return data

    def tick(self):
        try:
            self.pick()
        except httplib.HTTPException, e:
            self.log.error('http exception: %s', e)
        time.sleep(1)


            # # 0xff0000 -> blue
            # # 0x00ff00 -> green
            # # 0x0000ff -> red
            # if reply is None:
            #     return
            # self.log.info('Message reply <uid:%s>: %s', sender, reply)
            # msg = msgfmt.Message(fontname=u'黑体', bold=True, size=12, color=0x6B4C3F)
            # msg.text(reply)

def getAnswerByQuestion(income, sender, gid=None):
    msg = msgfmt.Message(fontname=u'幼圆', bold=True, size=12, color=0x6B4C3F)
    
    if u'天王盖地虎' in income:
        ret = u'宝塔镇河妖'
    elif gid:
        msg.reply(sender, income)
        msg.text('\n')
        ret = u'测试机器人自动回复.'
    else:
        ret = u'然后呢?'

    
    msg.text(ret)
    #kmsg.md5img('0D01966D3517836037E24B74C44304C7', 'jpg')

    return msg



# 表情获取
# http://file.im.baidu.com/get/file/content/old_image/5058c18b15e80449483771873d1b4441?from=page&rnd=16oi67o5b
#http://file.im.baidu.com/get/file/content/old_image/9180AAE4712AD6228C1B9ACA492117E1?from=page
# 文件:
#http://file.im.baidu.com/crossdomain.xml
#Referer:http://web.im.baidu.com/resources/common/flashes/upload_pic.swf

#client._apiReqest('modifyself', comment='Under Robot Mode.')        
