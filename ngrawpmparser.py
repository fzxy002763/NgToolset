#!/usr/bin/python3
# -*- encoding: utf-8 -*-

'''
File:
    ngrawpmparser.py
Description:
    Raw PM parser.
Change History:
    2019-3-21   v0.1    created.    github/zhenggao2
'''

import os
import xml.etree.ElementTree as ET
import ngmainwin
from PyQt5.QtWidgets import qApp

class NgRawPmParser(object):
    def __init(self, ngwin):
        self.ngwin = ngwin
