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
import traceback
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
            self.tgzs = sorted([os.path.join(root, fn) for fn in files if fn.lower().endswith('tar.gz')], key=str.lower)
            for tgz in self.tgzs:
                tar = tarfile.open(tgz, 'r:gz')
                fns = tar.getnames()
                for fn in fns:
                    tar.extract(fn, self.inDir)

        #parse raw pm xml
        self.data = dict()
        self.tagsMap = dict()
        for root, dirs, files in os.walk(self.inDir):
            self.xmls = sorted([os.path.join(root, fn) for fn in files if fn.lower().endswith('xml')], key=str.lower)
            for fn in self.xmls:
                self.parseRawPmXml(fn, self.rat)

        #post-processing of raw pm
        self.aggMap = dict()
        self.gnbKpiReport = dict()
        for key1,val1 in self.data.items():
            for key2,val2 in val1.items():
                stime, interval, dn = key2.split(';')
                agg = dn.split('/')[-1].split('-')[0]

                #init gnbKpiReport: {agg, {'stime_interval_dn', {kpi_name, kpi_value}}}
                if agg not in self.gnbKpiReport:
                    self.gnbKpiReport[agg] = dict()
                if key2 not in self.gnbKpiReport[agg]:
                    self.gnbKpiReport[agg][key2] = dict()

                for key3,val3 in val2.items():
                    if key3 not in self.aggMap:
                        self.aggMap[key3] = agg

        #sort self.gnbKpiReport[agg].keys()
        for agg in self.gnbKpiReport.keys():
            keys = list(self.gnbKpiReport[agg].keys())
            keys.sort()
            val = {key:self.gnbKpiReport[agg][key] for key in keys}
            self.gnbKpiReport[agg].clear()
            self.gnbKpiReport[agg] = val

        #print self.data
        '''
        for key1,val1 in self.data.items():
            self.ngwin.logEdit.append('|-measType=%s' % key1)
            for key2,val2 in val1.items():
                self.ngwin.logEdit.append('|--tag=%s' % key2)
                for key3,val3 in val2.items():
                    self.ngwin.logEdit.append('|----key=%s,val=%s' % (key3, val3))
            qApp.processEvents()

        for key,val in self.tagsMap.items():
            self.ngwin.logEdit.append('key=%s,val=%s'%(key,val))

        for key,val in self.aggMap.items():
            self.ngwin.logEdit.append('tag=%s,agg=%s'%(key,val))
        '''

        #parse kpi definitions
        self.gnbKpis = []
        self.confDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
        for root, dirs, files in os.walk(self.confDir):
            self.kpiDefs = sorted([os.path.join(root, fn) for fn in files if (os.path.basename(fn).lower().startswith('kpi_def') or os.path.basename(fn).lower().startswith('menb_kpi_def')) and not fn.endswith('~')], key=str.lower)
            for fn in self.kpiDefs:
                self.parseKpiDef(fn)

        #post-processing of gnbKpis
        for kpi in self.gnbKpis:
            try:
                if len(kpi) != 6:
                    continue

                x = kpi[2]
                y = kpi[3]
                invalidx = False
                invalidy = False
                aggx = None
                aggy = None
                if not invalidx and x is not None:
                    tokens = x.split(';')
                    tokens = list(map(lambda z:z.strip(), tokens))
                    if len(tokens) == 1 and not(tokens[0].startswith('(') and tokens[0].endswith(')')):
                        kpi[2] = int(tokens[0])
                    else:
                        kpi[2] = []
                        for item in tokens:
                            if item.startswith('(') and item.endswith(')'):
                                a,b = item[1:-1].split(',')
                                kpi[2].append([a, int(b)])
                                #all counters involved must have the same aggregation level
                                if aggx is None:
                                    aggx = self.aggMap[a]
                                else:
                                    if self.aggMap[a] != aggx:
                                        invalidx = True
                                        break
                            else:
                                invalidx = True
                                break

                if not invalidy and y is not None:
                    tokens = y.split(';')
                    tokens = list(map(lambda z:z.strip(), tokens))
                    if len(tokens) == 1 and not(tokens[0].startswith('(') and tokens[0].endswith(')')):
                        kpi[3] = int(tokens[0])
                    else:
                        kpi[3] = []
                        for item in tokens:
                            if item.startswith('(') and item.endswith(')'):
                                a,b = item[1:-1].split(',')
                                kpi[3].append([a, int(b)])
                                #all counters involved must have the same aggregation level
                                if aggy is None:
                                    aggy = self.aggMap[a]
                                else:
                                    if self.aggMap[a] != aggy:
                                        invalidy = True
                                        break
                            else:
                                invalidy = True
                                break

                if invalidx or invalidy or aggx is None or (aggx is not None and aggy is not None and aggx != aggy):
                    self.ngwin.logEdit.append('<font color=purple>Invalid KPI definition(name=%s,aggx=%s,aggy=%s), which will be ignored!</font>' % (kpi[0], aggx if aggx is not None else 'None', aggy if aggy is not None else 'None'))
                    qApp.processEvents()
                    kpi[0] = None
                else:
                    kpi[5] = aggx
            except Exception as e:
                #self.ngwin.logEdit.append(str(e))
                #self.ngwin.logEdit.append(repr(e))
                #self.ngwin.logEdit.append(e.message)
                self.ngwin.logEdit.append('<font color=purple>Invalid KPI definition(name=%s,aggx=%s,aggy=%s), which will be ignored!</font>' % (kpi[0], aggx if aggx is not None else 'None', aggy if aggy is not None else 'None'))
                self.ngwin.logEdit.append(traceback.format_exc())
                qApp.processEvents()
                kpi[0] = None
                continue

        '''
        for kpi in self.gnbKpis:
            if kpi[0] is None:
                continue
            self.ngwin.logEdit.append('name=%s,f=%s,x=%s,y=%s,p=%s,agg=%s' % (kpi[0], kpi[1] if kpi[1] is not None else 'None', kpi[2], kpi[3] if kpi[3] is not None else 'None', kpi[4] if kpi[4] is not None else 'None', kpi[5] if kpi[5] is not None else 'None'))
            qApp.processEvents()
        '''

        #calculate kpi
        self.ngwin.logEdit.append('<font color=blue>Calculating KPIs, please wait...</font>')
        qApp.processEvents()
        #reconstruct self.data to {'stime_interval_dn', {pm_tag, pm_value}}
        data2 = dict()
        for key1,val1 in self.data.items():
            for key2,val2 in val1.items():
                if key2 not in data2:
                    data2[key2] = dict()
                for key3,val3 in val2.items():
                    if key3 not in data2[key2]:
                        data2[key2][key3] = val3

        '''
        for key1,val1 in data2.items():
            self.ngwin.logEdit.append('|key=%s'%key1)
            for key2,val2 in val1.items():
                self.ngwin.logEdit.append('|--pm_tag=%s,pm_val=%s'%(key2,val2))
        '''

        for key1,val1 in self.gnbKpiReport.items():
            agg = key1
            for key2,val2 in val1.items():
                    #calculate valid kpi for key2('stime_interval_dn')
                    for kpi in self.gnbKpis:
                        try:
                            if kpi[0] is None or kpi[5] != agg:
                                continue

                            f = kpi[1]
                            x = kpi[2]
                            y = kpi[3]
                            p = kpi[4]

                            #calculate x and y
                            if x is not None:
                                if not isinstance(x, int):
                                    xval = 0
                                    for item in x:
                                        xval = xval + int(data2[key2][item[0]]) * item[1]
                                else:
                                    xval = x

                            if y is not None:
                                if not isinstance(y, int):
                                    yval = 0
                                    for item in y:
                                        yval = yval + int(data2[key2][item[0]]) * item[1]
                                else:
                                    yval = y

                            #calculate kpi
                            if f is not None and x is not None and y is not None and p is not None:
                                if yval != 0:
                                    kpival = '{:0.{precision}f}'.format(f * xval / yval, precision=p)
                                else:
                                    kpival = 0

                            if f is None and x is not None and y is None and p is None:
                                kpival = xval

                            self.gnbKpiReport[agg][key2][kpi[0]] = kpival
                        except Exception as e:
                            self.gnbKpiReport[agg][key2][kpi[0]] = 'NA'
                            self.ngwin.logEdit.append('<font color=purple>Error when calculating KPI(=%s) for DN=%s:</font>' % (kpi[0], key2))
                            self.ngwin.logEdit.append(traceback.format_exc())
                            qApp.processEvents()
                            continue

        if self.ngwin.enableDebug:
            for key1,val1 in self.gnbKpiReport.items():
                self.ngwin.logEdit.append('|agg=%s'%key1)
                for key2,val2 in val1.items():
                    self.ngwin.logEdit.append('|--key=%s'%key2)
                    for key3,val3 in val2.items():
                        self.ngwin.logEdit.append('|----kpi_name=%s,kpi_val=%s'%(key3,val3))
                qApp.processEvents()

        #export to excel
        self.ngwin.logEdit.append('<font color=blue>Exporting to excel(engine=xlsxwriter), please wait...</font>')
        qApp.processEvents()

        workbook = xlsxwriter.Workbook(os.path.join(self.outDir, '%s_kpi_report_%s.xlsx' % (rat, time.strftime('%Y%m%d%H%M%S', time.localtime()))))
        fmtHHeader = workbook.add_format({'font_name':'Arial', 'font_size':9, 'align':'center', 'valign':'vcenter', 'text_wrap':True, 'bg_color':'yellow'})
        fmtCell = workbook.add_format({'font_name':'Arial', 'font_size':9, 'align':'left', 'valign':'vcenter'})

        for key1,val1 in self.gnbKpiReport.items():
            horizontalHeader = ['STIME', 'INTERVAL', 'DN']
            for key2,val2 in val1.items():
                if len(val2) == 0:
                    continue
                horizontalHeader.extend(val2.keys())
                break

            #skip unused agg
            if key1 in ('NRCUUP', 'SFP', 'MNLENT', 'ETHLK', 'ETHIF', 'IPIF', 'IPADDRESSV4', 'IPNO', 'LNMME', 'VLANIF', 'IPVOL', 'SMOD', 'LTAC', 'LNADJ', 'FSTSCH'):
                continue

            sheet1 = workbook.add_worksheet('KPI_%s' % key1)
            sheet1.set_zoom(90)
            sheet1.freeze_panes(1, 3)

            #write header
            sheet1.write_row(0, 0, horizontalHeader, fmtHHeader)

            count = 0
            for key2,val2 in val1.items():
                if len(val2) == 0:
                    continue

                #key = 'time;interval;dn'
                stime, interval, dn = key2.split(';')
                row = [stime, interval, dn]
                row.extend(val2.values())

                sheet1.write_row(count+1, 0, row, fmtCell)
                count = count + 1

        for measType in self.data.keys():
            horizontalHeader = ['STIME', 'INTERVAL', 'DN']
            tags = list(self.tagsMap[measType])
            tags.sort()
            horizontalHeader.extend(tags)

            sheet1 = workbook.add_worksheet(measType[:31] if len(measType) > 31 else measType)
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
                    if tag in val:
                        row.append(val[tag])
                    else:
                        row.append('NA')

                sheet1.write_row(count+1, 0, row, fmtCell)
                count = count + 1

        workbook.close()

    def parseRawPmXml(self, fn, rat):
        self.ngwin.logEdit.append('<font color=blue>Parsing raw PM:%s (rat=%s)</font>' % (fn, rat))
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

                        pmtarget = pmmoresult.find('PMTarget') if pmmoresult.find('PMTarget') is not None else pmmoresult.find('NE-WBTS_1.0')
                        measType = pmtarget.get('measurementType')
                        for child in pmtarget:
                            key = '%s;%s;%s' % (startTime, interval, dn.text[len('PLMN-PLMN/'):])
                            if measType not in self.data:
                                self.data[measType] = dict()
                            if key not in self.data[measType]:
                                self.data[measType][key] = dict()
                            self.data[measType][key][child.tag] = child.text

                            if measType not in self.tagsMap:
                                #note the difference between: a=set('hello') and a=set(['hello'])
                                self.tagsMap[measType] = set([child.tag])
                            else:
                                self.tagsMap[measType].add(child.tag)
            except Exception as e:
                #self.ngwin.logEdit.append(str(e))
                self.ngwin.logEdit.append(traceback.format_exc())
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
                            key = '%s;%s;%s' % (startTime, interval, dn.text[len('NE-'):])
                            if measType not in self.data:
                                self.data[measType] = dict()
                            if key not in self.data[measType]:
                                self.data[measType][key] = dict()
                            self.data[measType][key][child.tag] = child.text

                            if measType not in self.tagsMap:
                                #note the difference between: a=set('hello') and a=set(['hello'])
                                self.tagsMap[measType] = set([child.tag])
                            else:
                                self.tagsMap[measType].add(child.tag)
            except Exception as e:
                #self.ngwin.logEdit.append(str(e))
                self.ngwin.logEdit.append(traceback.format_exc())
                return

    def parseKpiDef(self, fn):
        try:
            with open(fn, 'r') as f:
                self.ngwin.logEdit.append('<font color=blue>Parsing KPI definition: %s</font>' % fn)
                qApp.processEvents()

                #[name, f, x, y, p, agg]
                kpi = [None, None, None, None, None, None]
                while True:
                    line = f.readline()
                    if not line:
                        #don't forget the last KPI!
                        if kpi[0] is not None and kpi[2] is not None:
                            self.gnbKpis.append(kpi)
                        break
                    if line.startswith('#') or line.strip() == '':
                        continue

                    tokens = line.split('=')
                    tokens = list(map(lambda x:x.strip(), tokens))
                    if len(tokens) == 2:
                        if tokens[0].lower() == 'kpi_name':
                            if kpi[0] is None:
                                kpi[0] = tokens[1]
                            else:
                                if kpi[0] is not None and kpi[2] is not None:
                                    self.gnbKpis.append(kpi)
                                kpi = [tokens[1], None, None, None, None, None]
                        elif tokens[0].lower() == 'kpi_f':
                            kpi[1] = int(tokens[1])
                        elif tokens[0].lower() == 'kpi_x':
                            kpi[2] = tokens[1]
                        elif tokens[0].lower() == 'kpi_y':
                            kpi[3] = tokens[1]
                        elif tokens[0].lower() == 'kpi_p':
                            kpi[4] = int(tokens[1])
                        else:
                            pass
        except Exception as e:
            #self.ngwin.logEdit.append(str(e))
            self.ngwin.logEdit.append(traceback.format_exc())
            qApp.processEvents()
