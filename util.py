#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  FileName    : util.py
#  Author      : Feather.et.ELF <fledna@qq.com>
#  Created     : Thu Jun 14 20:23:14 2012 by Feather.et.ELF
#  Copyright   : Feather Workshop (c) 2012
#  Description : description
#  Time-stamp: <2012-06-14 20:54:34 andelf>

import getpass
import re

def getpass_or_quit(msg):
    try:
        value = getpass.getpass(msg)
    except KeyboardInterrupt:
        print 'Interrupt!'
        sys.exit(1)
    return value.strip()

def extract_deploy_id(url):
    return extract_ci_id(url) or extract_noah_id(url)

def extract_ci_id(url):
    matches = re.findall(r'http://.*?noah\.baidu\.com/ci-web/index.php\?r=ProcessView/QueryTask&listid=(\d+)', url)
    if matches:
        return int(matches[0])
    else:
        return 0                # or to return False?

def extract_noah_id(url):
    matches = re.findall(r'http://.*?noah\.baidu\.com.*?ViewDeployProcess.*?id=(\d+)', url)
    if matches:
        return int(matches[0])
    else:
        return 0                # or to return False?
