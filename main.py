#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  FileName    : main.py
#  Author      : Feather.et.ELF <fledna@qq.com>
#  Created     : Fri Apr 13 21:04:22 2012 by Feather.et.ELF
#  Copyright   : Feather Workshop (c) 2012
#  Description : Baidu hi client
#  Time-stamp: <2012-04-13 21:04:30 andelf>


import lib
import sys
import argparse
import atexit
import time
import threading


class HiThread(threading.Thread):
    name = "baiduhi"
    daemon = False
    client = None

    def run(self, *args, **kwargs):
        client = self.client
        if client is None:
            raise RuntimeError('no client yet')
        if client.login():
            atexit.register(lambda : client.logout())
            client.init()
            client.loop()
        else:
            raise RuntimeError('login error')



if __name__ == '__main__':
    parser = parser = argparse.ArgumentParser(description='`fledna` is a baidu-hi robot using web-hi protocol.')
    parser.add_argument('-u', '--username', help='baidu hi username', required=True)
    parser.add_argument('-p', '--password', help='baidu hi password', required=True)

    args = parser.parse_args()
    client = lib.BaiduHi(args.username, args.password)
    
    hi = HiThread()
    hi.client = client
    hi.start()
