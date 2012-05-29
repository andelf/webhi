#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  FileName    : main.py
#  Author      : Feather.et.ELF <fledna@qq.com>
#  Created     : Fri Apr 13 21:04:22 2012 by Feather.et.ELF
#  Copyright   : Feather Workshop (c) 2012
#  Description : Baidu hi client
#  Time-stamp: <2012-05-29 18:58:00 wangshuyu>


import lib
import sys
import argparse
import atexit
import time
import threading
import urllib2
import urllib
import json
import msgfmt


class HiThread(threading.Thread):
    name = "baiduhi"
    daemon = False
    client = None
    running_flag = True
    def __init__(self, client):
        threading.Thread.__init__(self)
        self.client = client
    def run(self, *args, **kwargs):
        client = self.client or None
        if client is None:
            raise RuntimeError('no client yet')

        while self.running_flag:
            client.tick()

    def quit(self):
        """safe quit"""
        self.running_flag = False
        self.client.log.info("Got quit signal. Waiting for current call...")


if __name__ == '__main__':
    parser = parser = argparse.ArgumentParser(description='`fledna` is a baidu-hi robot using web-hi protocol.')
    parser.add_argument('-u', '--username', help='baidu hi username', required=True)
    parser.add_argument('-p', '--password', help='baidu hi password', required=True)

    args = parser.parse_args()

    client = lib.BaiduHi(args.username, args.password)

    # register
    #client.registerKeyword('http', do_http)
    #client.registerKeyword('deploy.query', do_deploy_query)
    #client.registerKeyword('deploy.goon:', do_deploy_goon)
    #client.registerKeyword('deploy.stop:', do_deploy_stop)

    if not client.login():      # if login fail
        raise RuntimeError('Login fail!')

    atexit.register(lambda : client.logout())
    client.init()
    hi = HiThread(client)
    hi.client._apiReqest('modifyself', comment=u'IM 机器人服务中.')
    hi.start()


    while 1:
        try:
           hi.join(5.0)
        except KeyboardInterrupt:
           hi.quit()
           hi.client._apiReqest('modifyself', comment=u'IM 机器人已离线.')
           sys.exit(0)
           raise SystemExit
