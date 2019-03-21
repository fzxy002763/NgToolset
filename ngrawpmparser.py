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
from datetime import datetime
import tarfile
import xml.etree.ElementTree as ET
import ngmainwin
from PyQt5.QtWidgets import qApp

class NgRawPmParser(object):
    def __init__(self, ngwin, rat):
        self.ngwin = ngwin
        self.rat = rat 
        self.inDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/raw_pm')
        self.outDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        if not os.path.exists(self.outDir):
            os.mkdir(self.outDir)
        
        #extract tar.gz
        for root, dirs, files in os.walk(self.inDir):
            self.tgzs = sorted([os.path.join(root, fn) for fn in files if fn.endswith('tar.gz')], key=str.lower) 
            for tgz in self.tgzs:
                tar = tarfile.open(tgz, 'r:gz')
                fns = tar.getnames()
                for fn in fns:
                    tar.extract(fn, self.inDir)
        
        #parse raw pm xml
        self.data = dict()
        for root, dirs, files in os.walk(self.inDir):
            self.xmls = sorted([os.path.join(root, fn) for fn in files if fn.endswith('xml')], key=str.lower) 
            for fn in self.xmls:
                self.parseRawPmXml(fn, self.rat)
        
        #print self.data
        for key,val in self.data.items():
            self.ngwin.logEdit.append('|--key=%s' % key)
            for item in val:
                self.ngwin.logEdit.append('|----%s' % item)
            qApp.processEvents()
    
    def parseRawPmXml(self, fn, rat):
        self.ngwin.logEdit.append('Parsing %s (rat=%s)' % (fn, rat))
        qApp.processEvents()
        
        if rat == '5g':
            try:
                root = ET.parse(fn).getroot() #root='OMes'
                '''
                self.ngwin.logEdit.append('tag=%s,attrib=%s' % (root.tag, root.attrib))
                for child in root:
                    self.ngwin.logEdit.append('|--tag=%s,attrib=%s' % (child.tag, child.attrib))
                '''
            
                for pms in root.findall('PMSetup'):
                    startTime = datetime.fromisoformat(pms.get('startTime')).strftime('%Y-%m-%d_%H:%M:%S')
                    interval = pms.get('interval')
                    for pmmoresult in pms.findall('PMMOResult'):
                        '''
                        <MO dimension="network_element">
                            <DN>PLMN-PLMN/MRBTS-53775/NRBTS-1</DN>
                        </MO>
                        '''
                        mo = pmmoresult.find('MO')
                        dn = mo.find('DN')
                            
                        pmtarget = pmmoresult.find('PMTarget')
                        measType = pmtarget.get('measurementType')
                        for child in pmtarget:
                            key = '%s_%s_%s' % (dn.text[len('PLMN-PLMN/'):], measType, child.tag)
                            if key not in self.data:
                                self.data[key] = [{'startTime':startTime, 'interval':interval, 'value':child.text}]
                            else:
                                self.data[key].append({'startTime':startTime, 'interval':interval, 'value':child.text})
                            #self.ngwin.logEdit.append('dn=%s,measType=%s,tag=%s,text=%s' % (dn.text[len('PLMN-PLMN/'):], measType, child.tag, child.text))
            except Exception as e:
                self.ngwin.logEdit.append(str(e))
                return
        else:
            try:
                root = ET.parse(fn).getroot() #root='OMes'
                '''
                self.ngwin.logEdit.append('tag=%s,attrib=%s' % (root.tag, root.attrib))
                for child in root:
                    self.ngwin.logEdit.append('|--tag=%s,attrib=%s' % (child.tag, child.attrib))
                '''
            
                for pms in root.findall('PMSetup'):
                    startTime = datetime.fromisoformat(pms.get('startTime')).strftime('%Y-%m-%d_%H:%M:%S')
                    interval = pms.get('interval')
                    for pmmoresult in pms.findall('PMMOResult'):
                        '''
                        <MO>
                            <baseId>NE-MRBTS-833150</baseId>
                            <localMoid>DN:NE-LNBTS-833150/FTM-1/IPNO-1/IEIF-1</localMoid>
                        </MO>
                        '''
                        mo = pmmoresult.find('MO')
                        dn = mo.find('localMoid').text.split(':')[1]
                            
                        pmtarget = pmmoresult.find('NE-WBTS_1.0')
                        measType = pmtarget.get('measurementType')
                        for child in pmtarget:
                            key = '%s_%s_%s' % (dn.text[len('NE-'):], measType, child.tag)
                            if key not in self.data:
                                self.data[key] = [{'startTime':startTime, 'interval':interval, 'value':child.text}]
                            else:
                                self.data[key].append({'startTime':startTime, 'interval':interval, 'value':child.text})
                            #self.ngwin.logEdit.append('dn=%s,measType=%s,tag=%s,text=%s' % (dn.text[len('NE-'):], measType, child.tag, child.text))
            except Exception as e:
                self.ngwin.logEdit.append(str(e))
                return
            
