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
    
    NR_RES_CORESET0 = 70
    NR_RES_CORESET1 = 71
    
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
        
        self.nrFreqRange = self.args['freqBand']['freqRange']
        self.baseScsFd = 15 if self.nrFreqRange == 'FR1' else 60 
        self.baseScsTd = 60 if self.nrFreqRange == 'FR1' else 240 
        
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
        self.ssbSymbsInBaseScsTd = dict()
        self.ssbFirstSc = self.nrSsbNCrbSsb * self.nrScPerPrb + self.nrSsbKssb * (self.nrMibCommonScs // self.baseScsFd if self.nrFreqRange == 'FR2' else 1)
        self.ssbScsInBaseScsFd = {self.ssbFirstSc+k for k in range(20 * self.nrScPerPrb * (self.nrSsbScs // self.baseScsFd))}
        
        ssbFirstSymbSetStr = [] 
        for i in range(len(self.ssbSet)):
            ssbFirstSymbSetStr.append(str(self.ssbFirstSymbSet[i]) if self.ssbSet[i] == '1' else '-')
        self.ngwin.logEdit.append('ssb first symbols: "%s"' % ','.join(ssbFirstSymbSetStr))
        
        self.nrCoreset0MultiplexingPat = self.args['mib']['coreset0MultiplexingPat']
        self.nrCoreset0NumRbs = self.args['mib']['coreset0NumRbs']
        self.nrCoreset0NumSymbs = self.args['mib']['coreset0NumSymbs']
        self.nrCoreset0Offset = self.args['mib']['coreset0Offset']
        self.nrCoreset0StartRb = self.args['mib']['coreset0StartRb']
        self.nrRmsiCss0 = int(self.args['mib']['rmsiCss0'])
        self.nrCss0AggLevel = int(self.args['css0']['aggLevel'])
        self.nrCss0MaxNumCandidates = int(self.args['css0']['numCandidates'][1:])
        
        self.coreset0NumCces = self.nrCoreset0NumRbs * self.nrCoreset0NumSymbs // 6
        if self.nrCss0AggLevel > self.coreset0NumCces:
            self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid configurations of CSS0/CORESET0: aggregation level=%d while total number of CCEs=%d!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), self.nrCss0AggLevel, self.coreset0NumCces))
            return False
        
        #self.coreset0FirstSc = self.ssbFirstSc - self.nrCoreset0Offset * self.nrScPerPrb * (self.nrMibCommonScs // self.baseScsFd)
        self.coreset0FirstSc = self.nrSsbNCrbSsb * self.nrScPerPrb - self.nrCoreset0Offset * self.nrScPerPrb * (self.nrMibCommonScs // self.baseScsFd)
        #CORESET0 CCE-to-REG mapping
        self.coreset0RegBundles, self.coreset0Cces = self.coresetCce2RegMapping(coreset='coreset0', numRbs=self.nrCoreset0NumRbs, numSymbs=self.nrCoreset0NumSymbs, interleaved=True, L=6, R=2, nShift=self.nrPci)
        
        self.nrSib1Rnti = int(self.args['dci10Sib1']['rnti'], 16)
        self.nrSib1MuPdcch = int(self.args['dci10Sib1']['muPdcch'])
        self.nrSib1MuPdsch = int(self.args['dci10Sib1']['muPdsch'])
        self.nrSib1TdRa = self.args['dci10Sib1']['tdRa']
        self.nrSib1TdMappingType = self.args['dci10Sib1']['tdMappingType']
        self.nrSib1TdK0 = int(self.args['dci10Sib1']['tdK0'])
        self.nrSib1TdSliv = int(self.args['dci10Sib1']['tdSliv'])
        self.nrSib1TdStartSymb = int(self.args['dci10Sib1']['tdStartSymb'])
        self.nrSib1TdNumSymbs = int(self.args['dci10Sib1']['tdNumSymbs'])
        self.nrSib1FdRaType = self.args['dci10Sib1']['fdRaType']
        self.nrSib1FdRa = self.args['dci10Sib1']['fdRa']
        self.nrSib1FdStartRb = int(self.args['dci10Sib1']['fdStartRb'])
        self.nrSib1FdNumRbs = int(self.args['dci10Sib1']['fdNumRbs'])
        self.nrSib1FdVrbPrbMappingType = self.args['dci10Sib1']['fdVrbPrbMappingType']
        self.nrSib1FdBundleSize = int(self.args['dci10Sib1']['fdBundleSize'][1:])
        
        self.nrSib1DmrsType = self.args['dmrsSib1']['dmrsType']
        self.nrSib1DmrsAddPos = self.args['dmrsSib1']['dmrsAddPos']
        self.nrSib1DmrsMaxLen = self.args['dmrsSib1']['maxLength']
        self.nrSib1DmrsPorts = self.args['dmrsSib1']['dmrsPorts']
        self.nrSib1DmrsCdmGroupsWoData = int(self.args['dmrsSib1']['cdmGroupsWoData'])
        self.nrSib1DmrsNumFrontLoadSymbs = int(self.args['dmrsSib1']['numFrontLoadSymbs'])
        self.nrSib1DmrsTdL = self.args['dmrsSib1']['tdL']
        self.nrSib1DmrsFdK = self.args['dmrsSib1']['fdK']
        
        #DCI 1_0 with CSS interleaved VRB-to-PRB mapping
        if self.nrSib1FdVrbPrbMappingType == 'interleaved':
            self.dci10CssPrbs = self.dci10CssVrb2PrbMapping(coreset0Size=self.nrCoreset0NumRbs, iniDlBwpStart=0, coreset0Start=0, L=self.nrSib1FdBundleSize)
        
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
        self.ngwin.logEdit.append('---->inside initTddGrid(hsfn=%d, sfn=%d)' % (hsfn, sfn))
        
        dn = '%s_%s' % (hsfn, sfn)
        if not dn in self.gridNrTdd:
            #report error
            return
        
        tddCfgMap = {'D':NrResType.NR_RES_D.value, 'F':NrResType.NR_RES_F.value, 'U':NrResType.NR_RES_U.value}
        scaleTd = self.baseScsTd // self.nrTddCfgRefScs
        self.ngwin.logEdit.append('scaleTd=%d where baseScsTd=%dKHz and tddCfgRefScs=%dKHz' % (scaleTd, self.baseScsTd, self.nrTddCfgRefScs))
        if sfn % 2 == 0:
            for i in range(len(self.tddPatEvenRf)):
                for j in range(scaleTd):
                    self.gridNrTdd[dn][self.nrScGb:,i*scaleTd+j] = tddCfgMap[self.tddPatEvenRf[i]] 
        else:
            for i in range(len(self.tddPatOddRf)):
                for j in range(scaleTd):
                    self.gridNrTdd[dn][self.nrScGb:,i*scaleTd+j] = tddCfgMap[self.tddPatOddRf[i]] 
        
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
        resMap[NrResType.NR_RES_PDCCH.value] = ('PDCCH', '#000000', '#FF00FF')
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
        
        resMap[NrResType.NR_RES_CORESET0.value] = ('CORESET0', '#000000', '#00FFFF')
        resMap[NrResType.NR_RES_CORESET1.value] = ('CORESET1', '#000000', '#00FFFF')
        
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
        if self.error:
            return 
        
        self.ngwin.logEdit.append('---->inside recvSsb(hsfn=%d,sfn=%d, scaleFd=%d, scaleTd=%d)' % (hsfn, sfn, self.nrSsbScs // self.baseScsFd, self.baseScsTd // self.nrSsbScs))
        
        dn = '%s_%s' % (hsfn, sfn)
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
        
        if not dn in self.ssbFirstSymbInBaseScsTd:
            self.ssbFirstSymbInBaseScsTd[dn] = []
            self.ssbSymbsInBaseScsTd[dn] = set()
            
        ssbHrfSet = [0, 1] if self.nrSsbPeriod < 10 else [self.nrMibHrf]
        
        #SSB frequency domain
        scaleFd = self.nrSsbScs // self.baseScsFd
        v = self.nrPci % 4
        
        for hrf in ssbHrfSet:
            for issb in range(self.nrSsbMaxL):
                if self.ssbSet[issb] == '0':
                    self.ssbFirstSymbInBaseScsTd[dn].append(None)
                    continue
                
                #SSB time domain
                scaleTd = self.baseScsTd // self.nrSsbScs
                ssbFirstSymb = hrf * (self.nrSymbPerRfNormCp // 2) + self.ssbFirstSymbSet[issb] * scaleTd
                self.ngwin.logEdit.append('issb=%d, ssbFirstSc=%d, v=%d, ssbFirstSymb=%d' % (issb, self.ssbFirstSc, v, ssbFirstSymb))
                
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
                            if self.gridNrTdd[dn][self.ssbFirstSc, ssbFirstSymb+i*scaleTd+j] == NrResType.NR_RES_U.value:
                                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: The UE does not expect the set of symbols of the slot which are used for SSB transmission(ssb index=%d, first symbol=%d) to be indicated as uplink by TDD-UL-DL-ConfigurationCommon.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), issb, ssbFirstSymb))
                                self.error = True
                                return 
                            
                    for i in range(scaleTd):
                        #symbol 0 of SSB, PSS
                        self.gridNrTdd[dn][self.ssbFirstSc:self.ssbFirstSc+56*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][self.ssbFirstSc+56*scaleFd:self.ssbFirstSc+183*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_PSS.value
                        self.gridNrTdd[dn][self.ssbFirstSc+183*scaleFd:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        #symbol 1/3 of SSB, PBCH
                        self.gridNrTdd[dn][self.ssbFirstSc:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrTdd[dn][self.ssbFirstSc:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        #symbol 2 of SSB, PBCH and SSS 
                        self.gridNrTdd[dn][self.ssbFirstSc:self.ssbFirstSc+48*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+45)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrTdd[dn][self.ssbFirstSc+48*scaleFd:self.ssbFirstSc+56*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][self.ssbFirstSc+56*scaleFd:self.ssbFirstSc+183*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_SSS.value
                        self.gridNrTdd[dn][self.ssbFirstSc+183*scaleFd:self.ssbFirstSc+192*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrTdd[dn][self.ssbFirstSc+192*scaleFd:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+(v+192)*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrTdd[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                else:
                    for i in range(scaleTd):
                        #symbol 0 of SSB, PSS
                        self.gridNrFddDl[dn][self.ssbFirstSc:self.ssbFirstSc+56*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+56*scaleFd:self.ssbFirstSc+183*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_PSS.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+183*scaleFd:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+i] = NrResType.NR_RES_DTX.value
                        #symbol 1/3 of SSB, PBCH
                        self.gridNrFddDl[dn][self.ssbFirstSc:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrFddDl[dn][self.ssbFirstSc:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+3*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        #symbol 2 of SSB, PBCH and SSS 
                        self.gridNrFddDl[dn][self.ssbFirstSc:self.ssbFirstSc+48*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+v*scaleFd, self.ssbFirstSc+(v+45)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+48*scaleFd:self.ssbFirstSc+56*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+56*scaleFd:self.ssbFirstSc+183*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_SSS.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+183*scaleFd:self.ssbFirstSc+192*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DTX.value
                        self.gridNrFddDl[dn][self.ssbFirstSc+192*scaleFd:self.ssbFirstSc+240*scaleFd, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_PBCH.value
                        for j in range(self.ssbFirstSc+(v+192)*scaleFd, self.ssbFirstSc+(v+237)*scaleFd, 4*scaleFd):
                            for k in range(scaleFd):
                                self.gridNrFddDl[dn][j+k, ssbFirstSymb+2*scaleTd+i] = NrResType.NR_RES_DMRS_PBCH.value
                                
                self.ssbFirstSymbInBaseScsTd[dn].append(ssbFirstSymb)
                self.ssbSymbsInBaseScsTd[dn].update([ssbFirstSymb+k for k in range(4*scaleTd)])
    
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
        if self.error:
            return (None, None, None)
        
        if dci is None or rnti is None:
            return (None, None, None)
        
        if not dci in ('dci01', 'dci10', 'dci11'):
            return (None, None, None)
        
        if not rnti in ('si-rnti', 'ra-rnti', 'tc-rnti', 'c-rnti'):
            return (None, None, None)
        
        self.ngwin.logEdit.append('---->inside recvPdcch(hsfn=%d, sfn=%d, dci="%s",rnti="%s", scaleTdSsb=%d, scaleTdRmsiScs=%d)' % (hsfn, sfn, dci, rnti, self.baseScsTd // self.nrSsbScs, self.baseScsTd // self.nrMibCommonScs))
        
        if dci == 'dci10' and rnti == 'si-rnti':
            self.coreset0Occasions = []                
            if self.nrCoreset0MultiplexingPat == 1:
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
            
                if css0OccasionsPat1Fr2[self.nrRmsiCss0] is None:
                    self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid key(=%d) when referring css0OccasionsPat1Fr2.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), self.nrRmsiCss0))
                    self.error = True
                    return (None, None, None)
                else:
                    O2, numSetsPerSlot, M2, firstSymbSet = css0OccasionsPat1Fr1[self.nrRmsiCss0] if self.nrFreqRange == 'FR1' else css0OccasionsPat1Fr2[self.nrRmsiCss0] 
                
                dn = '%s_%s' % (hsfn, sfn)
                if not dn in self.ssbFirstSymbInBaseScsTd:
                    return (None, None, None)
                
                for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                    if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                        self.coreset0Occasions.append(None)
                        continue
                    
                    issb = i % self.nrSsbMaxL
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
                    if n0 == self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] - 1:
                        oc = [(hsfn, sfnc, n0)]
                        hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                        self.recvSsb(hsfn, sfn)
                        sfnc = sfn
                        oc.append((hsfn, sfnc, 0))
                    else:
                        nc = [n0, n0+1]
                        oc = [(hsfn, sfnc, i) for i in nc]
                    
                    #determine first symbol of coreset0
                    if len(firstSymbSet) == 2:
                        firstSymbCoreset0 = firstSymbSet[0] if issb % 2 == 0 else firstSymbSet[1]
                    else:
                        firstSymbCoreset0 = firstSymbSet[0]
                    
                    self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK', 'OK']])
            
            elif self.nrCoreset0MultiplexingPat == 2:
                dn = '%s_%s' % (hsfn, sfn)
                if not dn in self.ssbFirstSymbInBaseScsTd:
                    return (None, None, None)
                
                for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                    if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                        self.coreset0Occasions.append(None)
                        continue
                    
                    issb = i % self.nrSsbMaxL
                    #determine sfnSsb and nSsb which are based on commonScs 
                    sfnSsb = sfn
                    scaleTd = self.baseScsTd // self.nrMibCommonScs
                    nSsb = math.floor(self.ssbFirstSymbInBaseScsTd[dn][i] / (self.nrSymbPerSlotNormCp * scaleTd))
                    
                    #Table 13-13: PDCCH monitoring occasions for Type0-PDCCH CSS set - SS/PBCH block and CORESET multiplexing pattern 2 and {SS/PBCH block, PDCCH} SCS {120, 60} kHz
                    #Table 13-14: PDCCH monitoring occasions for Type0-PDCCH CSS set - SS/PBCH block and CORESET multiplexing pattern 2 and {SS/PBCH block, PDCCH} SCS {240, 120} kHz
                    if self.nrSsbScs == 120 and self.nrMibCommonScs == 60:
                        sfnc = sfnSsb
                        nc = [nSsb,]
                        firstSymbCoreset0 = (0, 1, 6, 7)[issb % 4]
                    elif self.nrSsbScs == 240 and self.nrMibCommonScs == 120:
                        issbMod8Set1 = (0, 1, 2, 3, 6, 7)
                        issbMod8Set2 = (4, 5)
                        if issb % 8 in issbMod8Set2:
                            sfnc = sfnSsb
                            nc = [nSsb - 1,]
                            firstSymbCoreset0 = (12, 13)[issbMod8Set2.index(issb % 8)]
                        else:
                            sfnc = sfnSsb
                            nc = [nSsb,]
                            firstSymbCoreset0 = (0, 1, 2, 3, 0, 1)[issbMod8Set1.index(issb % 8)]
                    else:
                        self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid combination of ssbScs(=%d) and mibCommonScs(=%d) for FR2.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), self.nrSsbScs, self.nrMibCommonScs))
                        self.error = True
                        return (None, None, None)
                    
                    oc = [(hsfn, sfnc, i) for i in nc]
                    self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK']])
            else:
                dn = '%s_%s' % (hsfn, sfn)
                if not dn in self.ssbFirstSymbInBaseScsTd:
                    return (None, None, None)
                
                for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                    if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                        self.coreset0Occasions.append(None)
                        continue
                    
                    issb = i % self.nrSsbMaxL
                    #determine sfnSsb and nSsb which are based on commonScs 
                    sfnSsb = sfn
                    scaleTd = self.baseScsTd // self.nrMibCommonScs
                    nSsb = math.floor(self.ssbFirstSymbInBaseScsTd[dn][i] / (self.nrSymbPerSlotNormCp * scaleTd))
                    
                    #Table 13-15: PDCCH monitoring occasions for Type0-PDCCH CSS set - SS/PBCH block and CORESET multiplexing pattern 3 and {SS/PBCH block, PDCCH} SCS {120, 120} kHz
                    if self.nrSsbScs == 120 and self.nrMibCommonScs == 120:
                        sfnc = sfnSsb
                        nc = [nSsb,]
                        firstSymbCoreset0 = (4, 8, 2, 6)[issb % 4]
                    else:
                        self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid combination of ssbScs(=%d) and mibCommonScs(=%d) for FR2.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), self.nrSsbScs, self.nrMibCommonScs))
                        self.error = True
                        return (None, None, None)
                    
                    oc = [(hsfn, sfnc, i) for i in nc]
                    self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK']])
                    
            
            #validate pdcch occasions
            scaleTd = self.baseScsTd // self.nrMibCommonScs
            scaleFd = self.nrMibCommonScs // self.baseScsFd
            for i in range(len(self.coreset0Occasions)):
                if self.coreset0Occasions[i] is None:
                    continue
                
                oc, firstSymb, valid = self.coreset0Occasions[i]
                for j in range(len(oc)):
                    hsfn, sfnc, nc = oc[j]
                    
                    dn2 = '%s_%s' % (hsfn, sfnc)
                    firstSymbInBaseScsTd = (nc * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
                    coreset0SymbsInBaseScsTd = [firstSymbInBaseScsTd+k for k in range(self.nrCoreset0NumSymbs * scaleTd)]
                    #self.ngwin.logEdit.append('---->coreset0SymbsInBaseScsTd[issb=%d,nc=%d]=%s' % (i % self.nrSsbMaxL, nc, coreset0SymbsInBaseScsTd))
                    
                    #refer to 3GPP 38.213 vf30
                    #10 UE procedure for receiving control information 
                    '''
                    If the UE monitors the PDCCH candidate for a Type0-PDCCH CSS set on the serving cell according to the procedure described in Subclause 13, the UE may assume that no SS/PBCH block is transmitted in REs used for monitoring the PDCCH candidate on the serving cell.
                    '''
                    if dn2 in self.ssbFirstSymbInBaseScsTd:
                        #multiplexing pattern 1 uses TDM only, and pattern 2 uses FDM/TDM, pattern 3 uses FDM only
                        #coreset0 and ssb dosn't overlap in freq-domain when:
                        #(1) if offset>0, offset >= #RB_CORESET0
                        #(2) if offset<0, offset <= -1 * #RB_SSB * (ssbScs / commonScs)
                        tdOverlapped = True if len(self.ssbSymbsInBaseScsTd[dn2].intersection(set(coreset0SymbsInBaseScsTd))) > 0 else False
                        fdOverlapped = True if not (self.nrCoreset0Offset >= self.nrCoreset0NumRbs or self.nrCoreset0Offset <= -20*(self.nrSsbScs//self.nrMibCommonScs)) else False
                        if tdOverlapped and fdOverlapped:
                            valid[j] = 'NOK' 
                            self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: If the UE monitors the PDCCH candidate for a Type0-PDCCH CSS set on the serving cell, the UE may assume that no SS/PBCH block is transmitted in REs used for monitoring the PDCCH candidate on the serving cell. Victim PDCCH occasion is: i=%d(issb=%d,hrf=%d), oc=%s, firstSymb=%s.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), i, i % self.nrSsbMaxL, self.nrMibHrf if self.nrSsbPeriod >= 10 else i // self.nrSsbMaxL, oc[j], firstSymb))
                            self.error = True
                            return (None, None, None)
                                    
                    #refer to 3GPP 38.213 vf30
                    #11.1 Slot configuration
                    '''
                    For a set of symbols of a slot indicated to a UE by pdcch-ConfigSIB1 in MIB for a CORESET for Type0-PDCCH CSS set, the UE does not expect the set of symbols to be indicated as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated.
                    '''                
                    if self.nrDuplexMode == 'TDD':                
                        for k in coreset0SymbsInBaseScsTd:
                            if self.gridNrTdd[dn2][self.ssbFirstSc, k] == NrResType.NR_RES_U.value:
                                valid[j] = 'NOK'
                                break
                            
                    #set CORESET0 for each PDCCH occasions
                    if valid[j] == 'OK':
                        for k in coreset0SymbsInBaseScsTd:
                            if self.nrDuplexMode == 'TDD':
                                self.gridNrTdd[dn2][self.coreset0FirstSc:self.coreset0FirstSc+self.nrCoreset0NumRbs*self.nrScPerPrb*scaleFd, k] = NrResType.NR_RES_CORESET0.value
                            else:
                                self.gridNrFddDl[dn2][self.coreset0FirstSc:self.coreset0FirstSc+self.nrCoreset0NumRbs*self.nrScPerPrb*scaleFd, k] = NrResType.NR_RES_CORESET0.value
                        
                self.coreset0Occasions[i][2] = valid
                if (len(valid) == 1 and valid[0] == 'NOK') or (len(valid) == 2 and valid[0] == 'NOK' and valid[1] == 'NOK'):
                    self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid PDCCH occasion: i=%d(issb=%d,hrf=%d), occasion=%s.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), i, i % self.nrSsbMaxL, self.nrMibHrf if self.nrSsbPeriod >= 10 else i // self.nrSsbMaxL, self.coreset0Occasions[i]))
                    self.error = True
                    return (None, None, None)
                
                self.ngwin.logEdit.append('PDCCH monitoring occasion for SSB index=%d(hrf=%d): %s' % (i % self.nrSsbMaxL, self.nrMibHrf if self.nrSsbPeriod >= 10 else i // self.nrSsbMaxL, self.coreset0Occasions[i]))
            
            #for simplicity, assume SSB index is randomly selected!
            while True:
                bestSsb = np.random.randint(0, len(self.ssbFirstSymbInBaseScsTd[dn]))
                if self.ssbFirstSymbInBaseScsTd[dn][bestSsb] is not None:
                    break
            
            #determine pdcch candidate randomly
            oc, firstSymb, valid = self.coreset0Occasions[bestSsb]
            if len(valid) == 2 and valid[0] == 'OK' and valid[1] == 'OK':
                pdcchSlot = np.random.randint(0, 2)
            else:
                if len(valid) == 1:
                    pdcchSlot = 0
                else:
                    pdcchSlot = 0 if valid[0] == 'OK' else 1
                    
            numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
            pdcchCandidate = np.random.randint(0, numCandidates)
            
            self.ngwin.logEdit.append('randomly selecting pdcch candidate: bestSsb=%d(hrf=%d,issb=%d), pdcchSlot=%d, pdcchCandidate=%d' % (bestSsb, self.nrMibHrf if self.nrSsbPeriod >= 10 else bestSsb // self.nrSsbMaxL, bestSsb % self.nrSsbMaxL, pdcchSlot, pdcchCandidate)) 
            
            hsfn, sfnc, nc = oc[pdcchSlot]
            dn2 = '%s_%s' % (hsfn, sfnc)
            firstSymbInBaseScsTd = (nc * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
            cceSet = [pdcchCandidate * self.nrCss0AggLevel + k for k in range(self.nrCss0AggLevel)]
            for i in range(self.coreset0Cces.shape[0]):
                for j in range(self.coreset0Cces.shape[1]):
                    if self.coreset0Cces[i, j] in cceSet:
                        if self.nrDuplexMode == 'TDD':
                            self.gridNrTdd[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                            self.gridNrTdd[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value
                        else:
                            self.gridNrFddDl[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                            self.gridNrFddDl[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value
            
            return (hsfn, sfnc, nc)
        else:
            #TODO
            return (hsfn, sfn, 0)
        
    
    def coresetCce2RegMapping(self, coreset='coreset0', numRbs=6, numSymbs=1, interleaved=False, L=6, R=None, nShift=None):
        if not coreset in ('coreset0', 'coreset1'):
            return (None, None)
        
        if not interleaved and L != 6:
            return (None, None)
        
        if interleaved:
            if (numSymbs == 1 and not L in (2, 6)) or (numSymbs in (2, 3) and not L in (numSymbs, 6)):
                return (None, None)
            if R is None:
                return (None, None)
            if (numRbs * numSymbs) % (L * R) != 0:
                return (None, None)
            if nShift is None:
                return (None, None)
        
        self.ngwin.logEdit.append('calling coresetCce2RegMapping for %s: numRbs=%d,numSymbs=%d,interleaved=%s,L=%d,R=%s,nShift=%s' % (coreset, numRbs, numSymbs, interleaved, L, R, nShift))
        
        #indexing REGs
        #refer to 3GPP 38.211 vf30
        #7.3.2.2	Control-resource set (CORESET)
        #Resource-element groups within a control-resource set are numbered in increasing order in a time-first manner, starting with 0 for the first OFDM symbol and the lowest-numbered resource block in the control resource set.
        numRegs = numRbs * numSymbs
        regBundles = np.full((numRbs, numSymbs), 0)
        count = 0
        for i in range(regBundles.shape[0]):
            for j in range(regBundles.shape[1]):
                regBundles[i, j] = count
                count += 1
        
        #indexing REG bundles
        numRegBundles = numRegs // L
        for i in range(regBundles.shape[0]):
            for j in range(regBundles.shape[1]):
                regBundles[i, j] = regBundles[i, j] // L
                
        #indexing CCEs
        numCces = numRegs // 6
        numRegBundlesPerCce = 6 // L
        cces = np.full((numRbs, numSymbs), 0)
        for i in range(numCces):
            regBundlesSet = [numRegBundlesPerCce * i + j for j in range(numRegBundlesPerCce)]
            if interleaved:
                C = numRegs // (L * R)
                for k in range(len(regBundlesSet)):
                    x = regBundlesSet[k]
                    c = x // R
                    r = x % R
                    regBundlesSet[k] = (r * C + c + nShift) % numRegBundles
            
            for j in range(cces.shape[0]):
                for k in range(cces.shape[1]):
                    if regBundles[j, k] in regBundlesSet:
                        cces[j, k] = i
        
        #print info
        regBundlesStr = []
        ccesStr = []
        for isymb in range(regBundles.shape[1]):
            for irb in range(regBundles.shape[0]): 
                if irb == 0:
                    regBundlesStr.append(str(regBundles[irb, isymb]))
                    ccesStr.append(str(cces[irb, isymb]))
                else:
                    regBundlesStr.append(','+str(regBundles[irb, isymb]))
                    ccesStr.append(','+str(cces[irb, isymb]))
            if isymb != regBundles.shape[1]-1:
                regBundlesStr.append('\n')
                ccesStr.append('\n')
        self.ngwin.logEdit.append('contents of regBundles:\n%s' % ''.join(regBundlesStr))
        self.ngwin.logEdit.append('contents of cces:\n%s' % ''.join(ccesStr))
                
        return (regBundles, cces)
    
    def recvSib1(self, hsfn, sfn, slot):
        self.ngwin.logEdit.append('---->inside recvSib1(hsfn=%d,sfn=%d,dci slot=%d)' % (hsfn, sfn, slot))
        
        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd
        
        slotSib1 = math.floor(slot * 2 ** (self.nrSib1MuPdsch - self.nrSib1MuPdcch)) + self.nrSib1TdK0
        firstSymbSib1InBaseScsTd = (slotSib1 * self.nrSymbPerSlotNormCp + self.nrSib1TdStartSymb) * scaleTd
        sib1SymbsInBaseScsTd = [firstSymbSib1InBaseScsTd+k for k in range(self.nrSib1TdNumSymbs*scaleTd)]
        
        sib1DmrsSymbs = []
        for i in self.nrSib1DmrsTdL:
            if self.nrSib1TdMappingType == 'Type A':
                #for PDSCH mapping type A, tdL is defined relative to the start of the slot
                sib1DmrsSymbs.append(i - self.nrSib1TdStartSymb)
            else:
                #for PDSCH mapping type B, tdL is defined relative to the start of the scheduled PDSCH resources
                sib1DmrsSymbs.append(i)
        self.ngwin.logEdit.append('contents of sib1DmrsSymbs(w.r.t to slivS): %s' % sib1DmrsSymbs)
        
        if self.nrSib1FdVrbPrbMappingType == 'nonInterleaved':
            firstScSib1InBaseScsFd = self.coreset0FirstSc + self.nrSib1FdStartRb * self.nrScPerPrb * scaleFd
            sib1ScsInBaseScsFd = [firstScSib1InBaseScsFd+k for k in range(self.nrSib1FdNumRbs*self.nrScPerPrb*scaleFd)]
        else:
            sib1ScsInBaseScsFd = []
            for k in range(self.nrSib1FdNumRbs):
                vrb = self.nrSib1FdStartRb + k
                prb = self.dci10CssPrbs[vrb]
                sib1ScsInBaseScsFd.extend([self.coreset0FirstSc+prb*self.nrScPerPrb*scaleFd+k for k in range(self.nrScPerPrb*scaleFd)])
        
        #validate SIB1 time-frequency allocation
        dn = '%s_%s' % (hsfn, sfn)
        if dn in self.ssbFirstSymbInBaseScsTd:
            #refer to 3GPP 38.314 vf40
            #5.1.4	PDSCH resource mapping
            '''
            When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 0, the UE shall assume that no SS/PBCH block is transmitted in REs used by the UE for a reception of the PDSCH.
            '''
            tdOverlapped = self.ssbSymbsInBaseScsTd[dn].intersection(set(sib1SymbsInBaseScsTd))
            fdOverlapped = self.ssbScsInBaseScsFd.intersection(set(sib1ScsInBaseScsFd))
            if len(tdOverlapped) > 0 and len(fdOverlapped) > 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 0, the UE shall assume that no SS/PBCH block is transmitted in REs used by the UE for a reception of the PDSCH.\ntdOverlapped=%s\nfdOverlapped=%s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), tdOverlapped, fdOverlapped))
                self.error = True
                return
        
        for i in range(self.nrSib1TdNumSymbs):
            if self.nrDuplexMode == 'TDD' and self.gridNrTdd[dn][self.coreset0FirstSc, firstSymbSib1InBaseScsTd+i*scaleTd] == NrResType.NR_RES_U.value:
                continue
            
            if self.nrDuplexMode == 'TDD':
                self.gridNrTdd[dn][sib1ScsInBaseScsFd, firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_SIB1.value
                if i in sib1DmrsSymbs:
                    for j in range(self.nrSib1FdNumRbs):
                        for k in range(self.nrScPerPrb):
                            if self.nrSib1DmrsFdK[k] == 1:
                                self.gridNrTdd[dn][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_SIB1.value
                            else:
                                if not (self.nrSib1TdMappingType == 'Type B' and self.nrSib1TdNumSymbs == 2):
                                    self.gridNrTdd[dn][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
            else:
                self.gridNrFddDl[dn][sib1ScsInBaseScsFd, firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_SIB1.value
    
    def dci10CssVrb2PrbMapping(self, coreset0Size=48, iniDlBwpStart=0, coreset0Start=0, L=2):
        #FIXME The UE is not expected to be configured with Li=2 simultaneously with a PRG size of 4 as defined in [6, TS 38.214].
        
        self.ngwin.logEdit.append('calling dci10CssVrb2PrbMapping: coreset0Size=%d,iniDlBwpStart=%d,coreset0Start=%d,L=%d' % (coreset0Size, iniDlBwpStart, coreset0Start, L))
        
        numBundles = math.ceil((coreset0Size + (iniDlBwpStart + coreset0Start) % L) / L)
        rbBundleSize = []
        for i in range(numBundles):
            if i == 0:
                rbBundleSize.append(L - (iniDlBwpStart + coreset0Start) % L)
            elif i == numBundles - 1:
                rbBundleSize.append((coreset0Size + iniDlBwpStart + coreset0Start) % L if (coreset0Size + iniDlBwpStart + coreset0Start) % L > 0 else L)
            else:
                rbBundleSize.append(L)
                
        vrbBundles = list(range(numBundles))
        prbBundles = []
        for j in range(numBundles):
            if j == numBundles - 1:
                prbBundles.append(j)
            else:
                R = 2
                C = math.floor(numBundles / R)
                c = j // R
                r = j % R
                fj = r * C + c
                prbBundles.append(fj)
        
        #indexing vrbs and prbs
        prbs = []
        for j in range(numBundles):
            for k in range(rbBundleSize[j]):
                prbs.append(sum(rbBundleSize[:prbBundles[j]]) + k)
                
        #print info
        self.ngwin.logEdit.append('contents of rbBundleSize: %s' % rbBundleSize)
        self.ngwin.logEdit.append('contents of vrbBundles: %s' % vrbBundles)
        self.ngwin.logEdit.append('contents of prbBundles: %s' % prbBundles)
        self.ngwin.logEdit.append('contents of prbs: %s' % prbs)
        
        return prbs
    
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
