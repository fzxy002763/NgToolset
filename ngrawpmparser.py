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
import time
from datetime import datetime
import tarfile
import xml.etree.ElementTree as ET
import ngmainwin
import xlsxwriter
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
        self.tagsMap = dict()
        for root, dirs, files in os.walk(self.inDir):
            self.xmls = sorted([os.path.join(root, fn) for fn in files if fn.endswith('xml')], key=str.lower) 
            for fn in self.xmls:
                self.parseRawPmXml(fn, self.rat)
        
        #print self.data
        '''
        for key1,val1 in self.data.items():
            self.ngwin.logEdit.append('|-measType=%s' % key1)
            for key2,val2 in val1.items():
                self.ngwin.logEdit.append('|--tag=%s' % key2)
                for key3,val3 in val2.items():
                    self.ngwin.logEdit.append('|----key=%s,val=%s' % (key3, val3))
            qApp.processEvents()
        '''
        
        #calculate kpi
        #TODO
        
        
        #export to excel
        self.ngwin.logEdit.append('Exporting to excel(engine=xlsxwriter), please wait...')
        qApp.processEvents()
        
        workbook = xlsxwriter.Workbook(os.path.join(self.outDir, '%s_kpi_report_%s.xlsx' % (rat, time.strftime('%Y%m%d%H%M%S', time.localtime()))))
        fmtHHeader = workbook.add_format({'font_name':'Arial', 'font_size':9, 'align':'center', 'valign':'vcenter', 'text_wrap':True, 'bg_color':'yellow'})
        fmtCell = workbook.add_format({'font_name':'Arial', 'font_size':9, 'align':'left', 'valign':'vcenter'})
        
        for measType in self.data.keys():
            horizontalHeader = ['STIME', 'INTERVAL', 'DN']
            tags = self.tagsMap[measType]
            tags.sort()
            horizontalHeader.extend(tags)
            
            sheet1 = workbook.add_worksheet(measType)
            sheet1.set_zoom(90)
            sheet1.freeze_panes(1, 3)

            #write header
            sheet1.write_row(0, 0, horizontalHeader, fmtHHeader)

            count = 0
            for key,val in self.data[measType].items():
                #key = 'time;interval;dn'
                #val = {tag:text}
                stime, interval, dn = key.split(';')
                row = [stime, interval, dn]
                for tag in tags:
                    row.append(val[tag])
                    
                sheet1.write_row(count+1, 0, row, fmtCell)
                count = count + 1
                    
        workbook.close()
    
    def parseRawPmXml(self, fn, rat):
        self.ngwin.logEdit.append('Parsing raw PM:%s (rat=%s)' % (fn, rat))
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
                            key = '%s;%s;%s' % (startTime, interval, dn.text[len('PLMN-PLMN/'):])
                            if measType not in self.data:
                                self.data[measType] = dict()
                            if key not in self.data[measType]:
                                self.data[measType][key] = dict()
                            self.data[measType][key][child.tag] = child.text
                            
                            if measType not in self.tagsMap:
                                self.tagsMap[measType] = [child.tag]
                            else:
                                self.tagsMap[measType].append(child.tag)
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
                            key = '%s;%s;%s' % (startTime, interval, dn.text[len('PLMN-PLMN/'):])
                            if measType not in self.data:
                                self.data[measType] = dict()
                            if key not in self.data[measType]:
                                self.data[measType][key] = dict()
                            self.data[measType][key][child.tag] = child.text
                            
                            if measType not in self.tagsMap:
                                self.tagsMap[measType] = [child.tag]
                            else:
                                self.tagsMap[measType].append(child.tag)
            except Exception as e:
                self.ngwin.logEdit.append(str(e))
                return
            
