#!/usr/bin/python3
# -*- encoding: utf-8 -*-

'''
File:
    ngnrgrid.py
Description:
    Implementation of 5GNR resource grid.
Change History:
    2018-12-28  v0.1    created.    github/zhenggao2
'''

import math
import os
import time
from enum import Enum
from collections import OrderedDict
import numpy as np
#from openpyxl import Workbook
import xlsxwriter
import ngmainwin

class NrResType(Enum):
    NR_RES_PSS = 0
    NR_RES_SSS = 1
    NR_RES_PBCH = 2
    NR_RES_SIB1 = 3
    NR_RES_PDCCH = 4
    NR_RES_PDSCH = 5
    NR_RES_CSI_RS = 6
    NR_RES_MSG2 = 7
    NR_RES_MSG4 = 8
    
    NR_RES_PRACH = 10
    NR_RES_PUCCH = 11
    NR_RES_PUSCH = 12
    NR_RES_SRS = 13
    NR_RES_MSG3 = 14 
    
    NR_RES_DMRS_PBCH = 20
    NR_RES_DMRS_SIB1 = 21
    NR_RES_DMRS_PDCCH = 22 
    NR_RES_DMRS_PDSCH = 23
    NR_RES_DMRS_MSG2 = 24
    NR_RES_DMRS_MSG4 = 25
    
    NR_RES_DMRS_PUCCH = 30 
    NR_RES_DMRS_PUSCH = 31 
    NR_RES_DMRS_MSG3 = 32 
    
    NR_RES_PTRS_PDSCH = 40 
    NR_RES_PTRS_PUSCH = 41 
    
    NR_RES_DTX = 50 
    
    NR_RES_D = 60 
    NR_RES_F = 61 
    NR_RES_U = 62 
    NR_RES_GB = 63
    
    NR_RES_BUTT = 99

class NgNrGrid(object):
    def __init__(self, ngwin, args):
        self.ngwin = ngwin
        self.args = args
        if not self.init():
            return
        self.error = False
    
    def init(self):
        self.ngwin.logEdit.append('---->inside init')
        
        #HSFN not exit in NR specs, but used in 5GNR resource grid for convenience
        self.hsfn = 0
        
        self.nrSubfPerRf = 10
        self.nrSlotPerSubf = [2 ** mu for mu in range(5)]
        self.nrSlotPerRf = [self.nrSubfPerRf * 2 ** mu for mu in range(5)]
        self.nrScs2Mu = {15:0, 30:1, 60:2, 120:3, 240:4}
        self.nrSymbPerSlotNormCp = 14
        self.nrSymbPerSlotExtCp = 12
        self.nrScPerPrb = 12
        
        self.baseScsFd = 15 if self.args['freqBand']['freqRange'] == 'FR1' else 60 
        self.baseScsTd = 60 if self.args['freqBand']['freqRange'] == 'FR1' else 240 
        
        self.nrCarrierScs = int(self.args['carrierGrid']['scs'][:-3])
        self.nrCarrierMinGuardBand = int(self.args['carrierGrid']['minGuardBand'])
        self.nrCarrierNumRbs = int(self.args['carrierGrid']['numRbs'])
        
        self.nrScTot = self.nrScPerPrb * (self.nrCarrierMinGuardBand + self.nrCarrierNumRbs) * (self.nrCarrierScs // self.baseScsFd)
        self.nrScGb = self.nrScPerPrb * self.nrCarrierMinGuardBand * (self.nrCarrierScs // self.baseScsFd)
        self.nrSymbPerRfNormCp = self.nrSymbPerSlotNormCp * self.nrSlotPerRf[self.nrScs2Mu[self.baseScsTd]]
        
        self.nrDuplexMode = self.args['freqBand']['duplexMode']
        self.nrMibSfn = int(self.args['mib']['sfn'])
        
        self.gridNrTdd = OrderedDict()
        self.gridNrFddDl = OrderedDict()
        self.gridNrFddUl = OrderedDict()
        dn = '%s_%s' % (self.hsfn, self.nrMibSfn)
        if self.nrDuplexMode == 'TDD':
            self.gridNrTdd[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_GB.value)
            if not self.initTddUlDlConfig():
                return False
            self.initTddGrid(self.hsfn, self.nrMibSfn)
        elif self.nrDuplexMode == 'FDD':
            self.gridNrFddDl[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_D.value)
            self.gridNrFddUl[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_U.value)
            #init 'min guard band'
            self.gridNrFddDl[dn][:self.nrScGb, :] = NrResType.NR_RES_GB.value
            self.gridNrFddUl[dn][:self.nrScGb, :] = NrResType.NR_RES_GB.value
        else:
            return False
        
        self.outDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        if not os.path.exists(self.outDir):
            os.mkdir(self.outDir)
            
        self.nrSsbPeriod = int(self.args['ssbBurst']['period'][:-2])
        self.nrMibHrf = int(self.args['mib']['hrf'])
        self.nrSsbScs = int(self.args['ssbGrid']['scs'][:-3])
        self.nrSsbPattern = self.args['ssbGrid']['pattern']
        self.nrSsbMinGuardBand240k = int(self.args['ssbGrid']['minGuardBand240k']) if self.nrSsbScs == 240 else None
        self.nrSsbKssb = int(self.args['ssbGrid']['kSsb'])
        self.nrSsbNCrbSsb = int(self.args['ssbGrid']['nCrbSsb'])
        self.nrSsbMaxL = int(self.args['ssbBurst']['maxL'])
        self.nrSsbInOneGroup = self.args['ssbBurst']['inOneGroup']
        self.nrSsbGroupPresence = self.args['ssbBurst']['groupPresence'] if self.nrSsbMaxL == 64 else None
        self.nrMibCommonScs = int(self.args['mib']['commonScs'][:-3])
        self.nrPci = int(self.args['pci'])
        
        if self.nrSsbMaxL == 64:
            self.ssbSet = ''
            for group in self.nrSsbGroupPresence:
                if group == '1':
                    self.ssbSet += self.nrSsbInOneGroup
                else:
                    self.ssbSet += '00000000'
        else:
            self.ssbSet = self.nrSsbInOneGroup[:self.nrSsbMaxL]
        
        self.ngwin.logEdit.append('ssbSet="%s"' % self.ssbSet)
        
        if self.nrSsbPattern == 'Case A' and self.nrSsbScs == 15:
            ssb1 = [2, 8]
            ssb2 = 14
            ssb3 = [0, 1] if self.nrSsbMaxL == 4 else [0, 1, 2, 3]
        elif self.nrSsbPattern == 'Case B' and self.nrSsbScs == 30:
            ssb1 = [4, 8, 16, 20]
            ssb2 = 28 
            ssb3 = [0,] if self.nrSsbMaxL == 4 else [0, 1]
        elif self.nrSsbPattern == 'Case C' and self.nrSsbScs == 30:
            ssb1 = [2, 8]
            ssb2 = 14 
            ssb3 = [0, 1] if self.nrSsbMaxL == 4 else [0, 1, 2, 3]
        elif self.nrSsbPattern == 'Case D' and self.nrSsbScs == 120:
            ssb1 = [4, 8, 16, 20]
            ssb2 = 28 
            ssb3 = [0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18]
        elif self.nrSsbPattern == 'Case E' and self.nrSsbScs == 240:
            ssb1 = [8, 12, 16, 20, 32, 36, 40, 44]
            ssb2 = 56 
            ssb3 = [0, 1, 2, 3, 5, 6, 7, 8]
        else:
            return False
        
        self.ssbFirstSymbSet = []
        for i in ssb1:
            for j in ssb3:
                self.ssbFirstSymbSet.append(i + ssb2 * j)
        self.ssbFirstSymbSet.sort()
        
        self.ssbFirstSymbInBaseScsTd = dict()
        
        ssbFirstSymbSetStr = [] 
        for i in range(len(self.ssbSet)):
            ssbFirstSymbSetStr.append(str(self.ssbFirstSymbSet[i]) if self.ssbSet[i] == '1' else '-')
        self.ngwin.logEdit.append('ssb first symbols: "%s"' % ','.join(ssbFirstSymbSetStr))
        
        self.nrCoreset0MultiplexingPat = self.args['mib']['coreset0MultiplexingPat']
        self.nrCoreset0NumRbs = self.args['mib']['coreset0NumRbs']
        self.nrCoreset0NumSymbs = self.args['mib']['coreset0NumSymbs']
        self.nrCoreset0Offset = self.args['mib']['coreset0Offset']
        self.nrRmsiCss0 = int(self.args['mib']['rmsiCss0'])
        self.nrCss0AggLevel = int(self.args['css0']['aggLevel'])
        self.nrCss0NumCandidates = int(self.args['css0']['numCandidates'][1:])
        
        return True
        
    def initTddUlDlConfig(self):
        #refer to 3GPP 38.213 vf30
        #11.1	Slot configuration
        self.tddCfgRefScsPeriod = {
            '0.5ms_0' : None,
            '0.5ms_1' : 1,
            '0.5ms_2' : 2,
            '0.5ms_3' : 4,
            '0.625ms_0' : None,
            '0.625ms_1' : None,
            '0.625ms_2' : None,
            '0.625ms_3' : 5,
            '1ms_0' : 1,
            '1ms_1' : 2,
            '1ms_2' : 4,
            '1ms_3' : 8,
            '1.25ms_0' : None,
            '1.25ms_1' : None,
            '1.25ms_2' : 5,
            '1.25ms_3' : 10,
            '2ms_0' : 2,
            '2ms_1' : 4,
            '2ms_2' : 8,
            '2ms_3' : 16,
            '2.5ms_0' : None,
            '2.5ms_1' : 5,
            '2.5ms_2' : 10,
            '2.5ms_3' : 20,
            '3ms_0' : 3,
            '3ms_1' : 6,
            '3ms_2' : 12,
            '3ms_3' : 24,
            '4ms_0' : 4,
            '4ms_1' : 8,
            '4ms_2' : 16,
            '4ms_3' : 32,
            '5ms_0' : 5,
            '5ms_1' : 10,
            '5ms_2' : 20,
            '5ms_3' : 40,
            '10ms_0' : 10,
            '10ms_1' : 20,
            '10ms_2' : 40,
            '10ms_3' : 80,
            }
        #period is x8 of actual value
        self.tddCfgPeriod2Int = {'0.5ms':4, '0.625ms':5, '1ms':8, '1.25ms':10, '2ms':16, '2.5ms':20, '3ms':24, '4ms':32, '5ms':40, '10ms':80}
        
        self.nrTddCfgRefScs = int(self.args['tddCfg']['refScs'][:-3])
        key = '%s_%s' % (self.args['tddCfg']['pat1Period'], self.nrScs2Mu[self.nrTddCfgRefScs])
        if not key in self.tddCfgRefScsPeriod or self.tddCfgRefScsPeriod[key] is None:
            self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid key(="%s") when referring tddCfgRefScsPeriod!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), key))
            return False
        self.pat1NumSlotsPerPeriod = self.tddCfgRefScsPeriod[key]
        self.nrTddCfgPat1NumDlSlots = int(self.args['tddCfg']['pat1NumDlSlots'])
        self.nrTddCfgPat1NumDlSymbs = int(self.args['tddCfg']['pat1NumDlSymbs'])
        self.nrTddCfgPat1NumUlSymbs = int(self.args['tddCfg']['pat1NumUlSymbs'])
        self.nrTddCfgPat1NumUlSlots = int(self.args['tddCfg']['pat1NumUlSlots'])
        
        if self.args['tddCfg']['pat2Period'] != 'not used':
            key = '%s_%s' % (self.args['tddCfg']['pat2Period'], self.nrScs2Mu[self.nrTddCfgRefScs])
            if not key in self.tddCfgRefScsPeriod or self.tddCfgRefScsPeriod[key] is None:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid key(="%s") when referring tddCfgRefScsPeriod!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), key))
                return False
            self.pat2NumSlotsPerPeriod = self.tddCfgRefScsPeriod[key]
            self.nrTddCfgPat2NumDlSlots = int(self.args['tddCfg']['pat2NumDlSlots'])
            self.nrTddCfgPat2NumDlSymbs = int(self.args['tddCfg']['pat2NumDlSymbs'])
            self.nrTddCfgPat2NumUlSymbs = int(self.args['tddCfg']['pat2NumUlSymbs'])
            self.nrTddCfgPat2NumUlSlots = int(self.args['tddCfg']['pat2NumUlSlots'])
            
            period = self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']] + self.tddCfgPeriod2Int[self.args['tddCfg']['pat2Period']] 
            if 160 % period != 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid TDD-UL-DL-Config periodicity(=%.3fms) with p=%.3fms and p2=%.3fms, which should divide 20ms!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), period/8, self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']]/8, self.tddCfgPeriod2Int[self.args['tddCfg']['pat2Period']]/8))
                return False
        else:
            self.pat2NumSlotsPerPeriod = None
            period = self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']]
            if 160 % period != 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid TDD-UL-DL-Config periodicity(=%.3fms), which should divide 20ms!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), period/8))
                return False
            
        self.periodsPer20ms = 160 // period
        
        pattern = []
        pattern.extend(['D'] * self.nrTddCfgPat1NumDlSlots * self.nrSymbPerSlotNormCp)
        pattern.extend(['D'] * self.nrTddCfgPat1NumDlSymbs)
        pattern.extend(['F'] * ((self.pat1NumSlotsPerPeriod - self.nrTddCfgPat1NumDlSlots - self.nrTddCfgPat1NumUlSlots) * self.nrSymbPerSlotNormCp - self.nrTddCfgPat1NumDlSymbs - self.nrTddCfgPat1NumUlSymbs))
        pattern.extend(['U'] * self.nrTddCfgPat1NumUlSymbs)
        pattern.extend(['U'] * self.nrTddCfgPat1NumUlSlots * self.nrSymbPerSlotNormCp)
        
        if self.pat2NumSlotsPerPeriod is None:
            numSlotsPerPeriod = self.pat1NumSlotsPerPeriod
        else:
            numSlotsPerPeriod = self.pat1NumSlotsPerPeriod + self.pat2NumSlotsPerPeriod
            
            pattern.extend(['D'] * self.nrTddCfgPat2NumDlSlots * self.nrSymbPerSlotNormCp)
            pattern.extend(['D'] * self.nrTddCfgPat2NumDlSymbs)
            pattern.extend(['F'] * ((self.pat2NumSlotsPerPeriod - self.nrTddCfgPat2NumDlSlots - self.nrTddCfgPat2NumUlSlots) * self.nrSymbPerSlotNormCp - self.nrTddCfgPat2NumDlSymbs - self.nrTddCfgPat2NumUlSymbs))
            pattern.extend(['U'] * self.nrTddCfgPat2NumUlSymbs)
            pattern.extend(['U'] * self.nrTddCfgPat2NumUlSlots * self.nrSymbPerSlotNormCp)
        
        pattern = pattern * self.periodsPer20ms
        self.tddPatEvenRf = pattern[:self.nrSlotPerRf[self.nrScs2Mu[self.nrTddCfgRefScs]] * self.nrSymbPerSlotNormCp]
        self.tddPatOddRf = pattern[self.nrSlotPerRf[self.nrScs2Mu[self.nrTddCfgRefScs]] * self.nrSymbPerSlotNormCp:]
        
        self.ngwin.logEdit.append('pattern of even frame:')
        for i in range(len(self.tddPatEvenRf)):
            if (i+1) % self.nrSymbPerSlotNormCp == 0:
                self.ngwin.logEdit.append('-->slot%d: %s' % (i // self.nrSymbPerSlotNormCp, ''.join(self.tddPatEvenRf[i-13:i+1])))
        self.ngwin.logEdit.append('pattern of odd frame:')
        for i in range(len(self.tddPatOddRf)):
            if (i+1) % self.nrSymbPerSlotNormCp == 0:
                self.ngwin.logEdit.append('-->slot%d: %s' % (i // self.nrSymbPerSlotNormCp, ''.join(self.tddPatOddRf[i-13:i+1])))
        
        return True
    
    def initTddGrid(self, hsfn, sfn):
        dn = '%s_%s' % (hsfn, sfn)
        if not dn in self.gridNrTdd:
            #report error
            return
        
        tddCfgMap = {'D':NrResType.NR_RES_D.value, 'F':NrResType.NR_RES_F.value, 'U':NrResType.NR_RES_U.value}
        scale = self.baseScsTd // self.nrTddCfgRefScs
        self.ngwin.logEdit.append('scaleTd=%d where baseScsTd=%dKHz and tddCfgRefScs=%dKHz' % (scale, self.baseScsTd, self.nrTddCfgRefScs))
        if sfn % 2 == 0:
            for i in range(len(self.tddPatEvenRf)):
                for j in range(scale):
                    self.gridNrTdd[dn][self.nrScGb:,i*scale+j] = tddCfgMap[self.tddPatEvenRf[i]] 
        else:
            for i in range(len(self.tddPatOddRf)):
                for j in range(scale):
                    self.gridNrTdd[dn][self.nrScGb:,i*scale+j] = tddCfgMap[self.tddPatOddRf[i]] 
        
        '''
        rows, cols = self.gridNrTdd[dn].shape
        for i in range(rows):
            self.ngwin.logEdit.append(','.join([str(self.gridNrTdd[dn][i,j]) for j in range(cols)]))
        '''
        
    def exportToExcel(self):
        self.ngwin.logEdit.append('---->exporting to excel(engine=xlsxwriter)...')
        verticalHeader = []
        for i in range(self.nrScTot):
            verticalHeader.append('crb%dsc%d' % (i // self.nrScPerPrb, i % self.nrScPerPrb))
        
        horizontalHeader = ['k/l']
        if self.nrDuplexMode == 'TDD':
            for key in self.gridNrTdd.keys():
                hsfn, sfn = key.split('_')
                for i in range(self.nrSymbPerRfNormCp//self.nrSymbPerSlotNormCp):
                    for j in range(self.nrSymbPerSlotNormCp):
                        #horizontalHeader.append('sfn%s\nslot%d\nsymb%d' % (sfn, i, j))
                        horizontalHeader.append('%s-%d-%d' % (sfn, i, j))
        else:
            for key in self.gridNrFddDl.keys():
                hsfn, sfn = key.split('_')
                for i in range(self.nrSymbPerRfNormCp//self.nrSymbPerSlotNormCp):
                    for j in range(self.nrSymbPerSlotNormCp):
                        horizontalHeader.append('sfn%s\nslot%d\nsymb%d' % (sfn, i, j))
        
        workbook = xlsxwriter.Workbook(os.path.join(self.outDir, '5gnr_grid_%s.xlsx' % (time.strftime('%Y%m%d%H%M%S', time.localtime()))))
        fmtHHeader = workbook.add_format({'font_name':'Arial', 'font_size':8, 'align':'center', 'valign':'vcenter', 'text_wrap':True, 'bg_color':'yellow', 'border':1})
        fmtVHeader = workbook.add_format({'font_name':'Arial', 'font_size':8, 'align':'center', 'valign':'vcenter', 'bg_color':'yellow', 'border':1})
        
        #key=NrResType, val=(name, font_color, bg_color)
        resMap = dict()
        resMap[NrResType.NR_RES_PSS.value] = ('PSS', '#000000', '#00FF00')
        resMap[NrResType.NR_RES_SSS.value] = ('SSS', '#000000', '#FFFF00')
        resMap[NrResType.NR_RES_PBCH.value] = ('PBCH', '#000000', '#80FFFF')
        resMap[NrResType.NR_RES_SIB1.value] = ('SIB1', '#0000FF', '#FFFFFF')
        resMap[NrResType.NR_RES_PDCCH.value] = ('PDCCH', '#000000', '#00FFFF')
        resMap[NrResType.NR_RES_PDSCH.value] = ('PDSCH', '#000000', '#FFFFFF')
        resMap[NrResType.NR_RES_CSI_RS.value] = ('CSIRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_MSG2.value] = ('MSG2', '#000000', '#FF00FF')
        resMap[NrResType.NR_RES_MSG4.value] = ('MSG4', '#000000', '#FF00FF')
        
        resMap[NrResType.NR_RES_PRACH.value] = ('PRACH', '#000000', '#80FFFF')
        resMap[NrResType.NR_RES_PUCCH.value] = ('PUCCH', '#FFFFFF', '#0000FF')
        resMap[NrResType.NR_RES_PUSCH.value] = ('PUSCH', '#000000', '#FFFFFF')
        resMap[NrResType.NR_RES_SRS.value] = ('SRS', '#000000', '#FFFF00')
        resMap[NrResType.NR_RES_MSG3.value] = ('MSG3', '#000000', '#FF00FF')
        
        resMap[NrResType.NR_RES_DMRS_PBCH.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_SIB1.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_PDCCH.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_PDSCH.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_MSG2.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_MSG4.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_PUCCH.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_PUSCH.value] = ('DMRS', '#000000', '#FF0000')
        resMap[NrResType.NR_RES_DMRS_MSG3.value] = ('DMRS', '#000000', '#FF0000')
        
        resMap[NrResType.NR_RES_PTRS_PDSCH.value] = ('PTRS', '#000000', '#FF00FF')
        resMap[NrResType.NR_RES_PTRS_PUSCH.value] = ('PTRS', '#000000', '#FF00FF')
        
        resMap[NrResType.NR_RES_DTX.value] = ('DTX', '#FFFFFF', '#000000')
        
        resMap[NrResType.NR_RES_D.value] = ('D', '#FFFFFF', '#808080')
        resMap[NrResType.NR_RES_F.value] = ('F', '#FFFFFF', '#808080')
        resMap[NrResType.NR_RES_U.value] = ('U', '#FFFFFF', '#808080')
        resMap[NrResType.NR_RES_GB.value] = ('GB', '#808080', '#000000')
        
        formatMap = dict()
        for key, val in resMap.items():
            name, fg, bg = val
            formatMap[key] = workbook.add_format({'font_name':'Arial', 'font_size':8, 'align':'center', 'valign':'vcenter', 'font_color':fg, 'bg_color':bg, 'border':1})
            
        if self.nrDuplexMode == 'TDD':
            sheet1 = workbook.add_worksheet('TDD Grid')
            sheet1.set_zoom(80)
            sheet1.freeze_panes(1, 1)
            
            #write header
            sheet1.write_row(0, 0, horizontalHeader, fmtHHeader)
            sheet1.write_column(1, 0, verticalHeader, fmtVHeader)
            
            count = 0
            for key,val in self.gridNrTdd.items():
                for row in range(val.shape[0]):
                    for col in range(val.shape[1]):
                        name, fg, bg = resMap[val[row, col]]
                        sheet1.write(row+1, col+1+count*val.shape[1], name, formatMap[val[row, col]])
                count += 1
            
            sheet1.set_column(1, len(self.gridNrTdd) * self.nrSymbPerRfNormCp, 5)
        else:
            sheet1 = workbook.add_worksheet('FDD UL Grid')
            sheet1.set_zoom(80)
            sheet1.freeze_panes(1, 1)
            sheet2 = workbook.add_worksheet('FDD DL Grid')
            sheet2.set_zoom(80)
            sheet2.freeze_panes(1, 1)
            
            #write header
            sheet1.write_row(0, 0, horizontalHeader, fmtHHeader)
            sheet1.write_column(1, 0, verticalHeader, fmtVHeader)
            sheet2.write_row(0, 0, horizontalHeader, fmtHHeader)
            sheet2.write_column(1, 0, verticalHeader, fmtVHeader)
         
            count = 0
            for key,val in self.gridNrFddUl.items():
                for row in range(val.shape[0]):
                    for col in range(val.shape[1]):
                        name, fg, bg = resMap[val[row, col]]
                        sheet1.write(row+1, col+1+count*val.shape[1], name, formatMap[val[row, col]])
                count += 1
            
            count = 0
            for key,val in self.gridNrFddDl.items():
                for row in range(val.shape[0]):
                    for col in range(val.shape[1]):
                        name, fg, bg = resMap[val[row, col]]
                        sheet2.write(row+1, col+1+count*val.shape[1], name, formatMap[val[row, col]])
                count += 1
                
            sheet1.set_column(1, len(self.gridNrFddDl) * self.nrSymbPerRfNormCp, 5)
            sheet2.set_column(1, len(self.gridNrFddUl) * self.nrSymbPerRfNormCp, 5)
        
        workbook.close()
    
    def recvSsb(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvSsb(hsfn=%d,sfn=%d)' % (hsfn, sfn))
        
        #init gridNrTdd or gridNrFddDl/gridNrFddUl if necessary
        if self.nrDuplexMode == 'TDD'and not dn in self.gridNrTdd:
            self.gridNrTdd[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_GB.value)
            self.initTddGrid(hsfn, sfn)
        elif self.nrDuplexMode == 'FDD' and not dn in self.gridNrFddDl:
            self.gridNrFddDl[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_D.value)
            self.gridNrFddUl[dn] = np.full((self.nrScTot, self.nrSymbPerRfNormCp), NrResType.NR_RES_U.value)
            #init 'min guard band'
            self.gridNrFddDl[dn][:self.nrScGb, :] = NrResType.NR_RES_GB.value
            self.gridNrFddUl[dn][:self.nrScGb, :] = NrResType.NR_RES_GB.value
        else:
            pass
        
        if self.nrSsbPeriod >= 10 and self.deltaSfn(self.hsfn, self.nrMibSfn, hsfn, sfn) % (self.nrSsbPeriod // 10) != 0:
            return
        
        dn = '%s_%s' % (hsfn, sfn)
        if not dn in self.ssbFirstSymbInBaseScsTd:
            self.ssbFirstSymbInBaseScsTd[dn] = []
            
        ssbHrfSet = [0, 1] if self.nrSsbPeriod < 10 else [self.nrMibHrf]
        
        #SSB frequency domain
        scaleFd = self.nrSsbScs // self.baseScsFd
        ssbFirstSc = self.nrSsbNCrbSsb * self.nrScPerPrb + self.nrSsbKssb * (self.nrMibCommonScs // self.baseScsFd if self.args['freqBand']['freqRange'] == 'FR2' else 1)
        v = self.nrPci % 4
        
        for hrf in ssbHrfSet:
            for issb in range(self.nrSsbMaxL):
                if self.ssbSet[issb] == '0':
                    self.ssbFirstSymbInBaseScsTd[dn].append(None)
                    continue
                
                #SSB time domain
                scaleTd = self.baseScsTd // self.nrSsbScs
                ssbFirstSymb = hrf * (self.nrSymbPerRfNormCp // 2) + self.ssbFirstSymbSet[issb] * scaleTd
                self.ssbFirstSymbInBaseScsTd[dn].append(ssbFirstSymb)
                self.ngwin.logEdit.append('ssbFirstSc=%d, v=%d, ssbFirstSymb=%d with scaleFd=%d(baseScsFd=%d,ssbScs=%d) and scaleTd=%d(baseScsTd=%d,ssbScs=%d)' % (ssbFirstSc, v, ssbFirstSymb, scaleFd, self.baseScsFd, self.nrSsbScs, scaleTd, self.baseScsTd, self.nrSsbScs))
                
                #refer to 3GPP 38.211 vf30
                #Table 7.4.3.1-1: Resources within an SS/PBCH block for PSS, SSS, PBCH, and DM-RS for PBCH.
                if self.nrDuplexMode == 'TDD':
                    #check ul/dl config
                    #refer to 3GPP 38.213 vf30
                    #11.1 Slot configurations
                    '''
                    For a set of symbols of a slot that are indicated to a UE by ssb-PositionsInBurst in SystemInformationBlockType1 or ssb-PositionsInBurst in ServingCellConfigCommon, when provided to the UE, for reception of SS/PBCH blocks, the UE does not transmit PUSCH, PUCCH, PRACH in the slot if a transmission would overlap with any symbol from the set of symbols and the UE does not transmit SRS in the set of symbols of the slot. The UE does not expect the set of symbols of the slot to be indicated as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, when provided to the UE.
                    '''
                    for i in range(4):
                        for j in range(scaleTd):
                            if self.gridNrTdd[dn][ssbFirstSc, ssbFirstSymb+i*scaleTd+j] == NrResType.NR_RES_U.value:
                                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: The UE does not expect the set of symbols of the slot which are used for SSB transmission(ssb index=%d, first symbol=%d) to be indicated as uplink by TDD-UL-DL-ConfigurationCommon.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), issb, ssbFirstSymb))
                                self.error = True
                                return (hsfn, sfn)
                    
                    for i in range(scaleTd):
                        #symbol 0 of SSB, PSS
                        self.gridNrTdd[dn][ssbFirstSc:ssbFirstSc+56*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][ssbFirstSc+56*scaleFd:ssbFirstSc+183*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_PSS.value
                        self.gridNrTdd[dn][ssbFirstSc+183*scaleFd:ssbFirstSc+240*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        #symbol 1/3 of SSB, PBCH
                        self.gridNrTdd[dn][ssbFirstSc:ssbFirstSc+240*scaleFd, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrTdd[dn][ssbFirstSc:ssbFirstSc+240*scaleFd, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        #symbol 2 of SSB, PBCH and SSS 
                        self.gridNrTdd[dn][ssbFirstSc:ssbFirstSc+48*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+45)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrTdd[dn][ssbFirstSc+48*scaleFd:ssbFirstSc+56*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][ssbFirstSc+56*scaleFd:ssbFirstSc+183*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_SSS.value
                        self.gridNrTdd[dn][ssbFirstSc+183*scaleFd:ssbFirstSc+192*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][ssbFirstSc+192*scaleFd:ssbFirstSc+240*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+(v+192)*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                else:
                    for i in range(scaleTd):
                        #symbol 0 of SSB, PSS
                        self.gridNrFddDl[dn][ssbFirstSc:ssbFirstSc+56*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][ssbFirstSc+56*scaleFd:ssbFirstSc+183*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_PSS.value
                        self.gridNrFddDl[dn][ssbFirstSc+183*scaleFd:ssbFirstSc+240*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        #symbol 1/3 of SSB, PBCH
                        self.gridNrFddDl[dn][ssbFirstSc:ssbFirstSc+240*scaleFd, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrFddDl[dn][ssbFirstSc:ssbFirstSc+240*scaleFd, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        #symbol 2 of SSB, PBCH and SSS 
                        self.gridNrFddDl[dn][ssbFirstSc:ssbFirstSc+48*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+v*scaleFd, ssbFirstSc+(v+45)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrFddDl[dn][ssbFirstSc+48*scaleFd:ssbFirstSc+56*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][ssbFirstSc+56*scaleFd:ssbFirstSc+183*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_SSS.value
                        self.gridNrFddDl[dn][ssbFirstSc+183*scaleFd:ssbFirstSc+192*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][ssbFirstSc+192*scaleFd:ssbFirstSc+240*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(ssbFirstSc+(v+192)*scaleFd, ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        
        
        return (hsfn, sfn)
    
    def deltaSfn(self, hsfn0, sfn0, hsfn1, sfn1):
        return (1024 * hsfn1 + sfn1) - (1024 * hsfn0 + sfn0)
    
    def incSfn(self, hsfn, sfn, n):
        if n <= 0:
            return (hsfn, sfn)
    
        sfn = sfn + n
        if sfn >= 1024:
            sfn = sfn % 1024
            hsfn = hsfn + 1
            if hsfn >= 1024:
                hsfn = hsfn % 1024
                
        return (hsfn, sfn)
    
    def monitorPdcch(self, hsfn, sfn, dci=None, rnti=None):
        if dci is None or rnti is None:
            return (hsfn, sfn)
        
        if not dci in ('dci01', 'dci10', 'dci11'):
            return (hsfn, sfn)
        
        if not rnti in ('si-rnti', 'ra-rnti', 'tc-rnti', 'c-rnti'):
            return (hsfn, sfn)
        
        self.ngwin.logEdit.append('---->inside recvPdcch(hsfn=%d, sfn=%d, dci="%s",rnti="%s")' % (hsfn, sfn, dci, rnti))
        
        if dci == 'dci10' and rnti == 'si-rnti':
            #refer to 3GPP 38.213 vf30
            #Table 13-11: Parameters for PDCCH monitoring occasions for Type0-PDCCH CSS set - SS/PBCH block and CORESET multiplexing pattern 1 and FR1
            #Table 13-12: Parameters for PDCCH monitoring occasions for Type0-PDCCH CSS set - SS/PBCH block and CORESET multiplexing pattern 1 and FR2
            css0OccasionsPat1Fr1 = {
                0 : (0,1,2,(0,)),
                1 : (0,2,1,(0, self.nrCoreset0NumSymbs)),
                2 : (4,1,2,(0,)),
                3 : (4,2,1,(0, self.nrCoreset0NumSymbs)),
                4 : (10,1,2,(0,)),
                5 : (10,2,1,(0, self.nrCoreset0NumSymbs)),
                6 : (14,1,2,(0,)),
                7 : (14,2,1,(0, self.nrCoreset0NumSymbs)),
                8 : (0,1,4,(0,)),
                9 : (10,1,4,(0,)),
                10 : (0,1,2,(1,)),
                11 : (0,1,2,(2,)),
                12 : (4,1,2,(1,)),
                13 : (4,1,2,(2,)),
                14 : (10,1,2,(1,)),
                15 : (10,1,2,(2,)),
                }
            css0OccasionsPat1Fr2 = {
                0 : (0,1,2,(0,)),
                1 : (0,2,1,(0,7),),
                2 : (5,1,2,(0,)),
                3 : (5,2,1,(0,7),),
                4 : (10,1,2,(0,)),
                5 : (10,2,1,(0,7),),
                6 : (0,2,1,(0, self.nrCoreset0NumSymbs)),
                7 : (5,2,1,(0, self.nrCoreset0NumSymbs)),
                8 : (10,2,1,(0, self.nrCoreset0NumSymbs)),
                9 : (15,1,2,(0,)),
                10 : (15,2,1,(0,7),),
                11 : (15,2,1,(0, self.nrCoreset0NumSymbs)),
                12 : (0,1,4,(0,)),
                13 : (10,1,4,(0,)),
                14 : None,
                15 : None,
                }
            
            self.coreset0Occasions = []                
            if self.nrCoreset0MultiplexingPat == 1:
                O2, numSetsPerSlot, M2, firstSymbSet = css0OccasionsPat1Fr1[self.nrRmsiCss0] if self.args['freqBand']['freqRange'] == 'FR1' else css0OccasionsPat1Fr2[self.nrRmsiCss0] 
                
                for issb in range(self.nrSsbMaxL):
                    if self.ssbSet[issb] == '0':
                        self.coreset0Occasions.append(None)
                        continue
                    
                    #determine pdcch monitoring occasion (sfnc + nc) for ssb with index issb
                    val = (O2 * 2 ** self.nrScs2Mu[self.nrMibCommonScs]) // 2 + math.floor(issb * M2 / 2)
                    valSfnc = math.floor(val / self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]])
                    if (valSfnc % 2 == 0 and sfn % 2 == 0) or (valSfnc % 2 == 1 and sfn % 2 == 1):
                        sfnc = sfn
                    else:
                        hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                        self.recvSsb(hsfn, sfn)
                        sfnc = sfn
                    
                    n0 = val % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] 
                    nc = [n0, n0+1]
                    
                    #determine first symbol of coreset0
                    if len(firstSymbSet) == 2:
                        firstSymbCoreset0 = firstSymbSet[0] if issb % 2 == 0 else firstSymbSet[1]
                    else:
                        firstSymbCoreset0 = firstSymbSet[0]
                    
                    self.coreset0Occasions.append([hsfn, sfnc, nc, firstSymbCoreset0, [True, True]])
                    
                #FIXME pdcch monitoring occasions may overlap with SSB
                dn = '%s_%s' % (hsfn, sfn)
                scaleTd = self.baseScsTd // self.nrMibCommonScs
                for issb in range(self.nrSsbMaxL):
                    #refer to 3GPP 38.213 vf30
                    #10 UE procedure for receiving control information 
                    '''
                    If the UE monitors the PDCCH candidate for a Type0-PDCCH CSS set on the serving cell according to the procedure described in Subclause 13, the UE may assume that no SS/PBCH block is transmitted in REs used for monitoring the PDCCH candidate on the serving cell.
                    '''
                    if dn in self.ssbFirstSymbInBaseScsTd:
                        hsfn, sfnc, nc, firstSymb, valid = self.coreset0Occasions[issb]
                        for i in range(2):
                            firstSymbInBaseScsTd = (nc[i] * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
                            coreset0SymbsInBaseScsTd = [firstSymbInBaseScsTd+j for j in range(self.nrCoreset0NumSymbs * scaleTd)]
                            for k in self.ssbFirstSymbInBaseScsTd[dn]:
                                if k in coreset0SymbsInBaseScsTd:
                                    valid[i] = False
                        self.coreset0Occasions[issb][4] = valid
                        
                    self.ngwin.logEdit.append('PDCCH monitoring occasion for SSB index=%d: %s, with scaleTd=%d(baseScsTd=%d,commonScs=%d)' % (issb, self.coreset0Occasions[issb], scaleTd, self.baseScsTd, self.nrMibCommonScs))
            elif self.nrCoreset0MultiplexingPat == 2:
                for issb in range(self.nrSsbMaxL):
                    sfnc = sfn
                    #TODO
                pass
            else:
                pass
            
            #for simplicity, assume SSB index is randomly selected!
            #issb = np.random.randint(0, self.nrSsbMaxL)
            
            #TODO determine pdcch candidate
            
            pass
        else:
            pass
        
        return (hsfn, sfn)
        
    
    def recvSib1(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvSib1')
        
        #TODO determine sib1(pdsch) and its dmrs
        return (hsfn, sfn)
    
    def sendMsg1(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside sendMsg1')
        return (hsfn, sfn)
    
    def recvMsg2(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvMsg2')
        return (hsfn, sfn)
    
    def sendMsg3(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside sendMsg3')
        return (hsfn, sfn)
    
    def recvMsg4(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvMsg4')
        return (hsfn, sfn)
    
    def sendPucch(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside sendPucch')
        return (hsfn, sfn)
    
    def sendPusch(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside sendPusch')
        return (hsfn, sfn)
    
    def recvPdsch(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvPdsch')
        return (hsfn, sfn)
    
    def normalOps(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside normalOps')
        return (hsfn, sfn)
