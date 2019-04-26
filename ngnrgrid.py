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
from PyQt5.QtWidgets import qApp
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
        self.error = False
        if not self.init():
            self.error = True
            return

    def init(self):
        self.ngwin.logEdit.append('---->inside init')
        qApp.processEvents()

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
        if self.nrDuplexMode == 'TDD':
            if not self.initTddUlDlConfig():
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

        self.nrIniDlBwpId = int(self.args['iniDlBwp']['bwpId'])
        self.nrIniDlBwpScs = int(self.args['iniDlBwp']['scs'][:-3])
        self.nrIniDlBwpCp = self.args['iniDlBwp']['cp']
        self.nrIniDlBwpLocAndBw = int(self.args['iniDlBwp']['locAndBw'])
        self.nrIniDlBwpStartRb = int(self.args['iniDlBwp']['startRb'])
        self.nrIniDlBwpNumRbs = int(self.args['iniDlBwp']['numRbs'])

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
        qApp.processEvents()

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
        self.reservedPdcchSib1 = dict()
        self.reservedSib1 = dict()
        self.ssbFirstSc = self.nrSsbNCrbSsb * self.nrScPerPrb + self.nrSsbKssb * (self.nrMibCommonScs // self.baseScsFd if self.nrFreqRange == 'FR2' else 1) + self.nrIniDlBwpStartRb * self.nrScPerPrb * (self.nrIniDlBwpScs // self.baseScsFd)
        self.ssbScsInBaseScsFd = {self.ssbFirstSc+k for k in range(20 * self.nrScPerPrb * (self.nrSsbScs // self.baseScsFd))}

        ssbFirstSymbSetStr = []
        for i in range(len(self.ssbSet)):
            ssbFirstSymbSetStr.append(str(self.ssbFirstSymbSet[i]) if self.ssbSet[i] == '1' else '-')
        self.ngwin.logEdit.append('ssb first symbols: "%s"' % ','.join(ssbFirstSymbSetStr))
        qApp.processEvents()

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
            qApp.processEvents()
            return False

        #self.coreset0FirstSc = self.ssbFirstSc - self.nrCoreset0Offset * self.nrScPerPrb * (self.nrMibCommonScs // self.baseScsFd)
        self.coreset0FirstSc = self.nrSsbNCrbSsb * self.nrScPerPrb - self.nrCoreset0Offset * self.nrScPerPrb * (self.nrMibCommonScs // self.baseScsFd) + self.nrIniDlBwpStartRb * self.nrScPerPrb * (self.nrIniDlBwpScs // self.baseScsFd)
        #CORESET0 CCE-to-REG mapping
        self.coreset0RegBundles, self.coreset0Cces = self.coresetCce2RegMapping(coreset='coreset0', numRbs=self.nrCoreset0NumRbs, numSymbs=self.nrCoreset0NumSymbs, interleaved=True, L=6, R=2, nShift=self.nrPci)

        self.coreset0Occasions = dict()

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

        self.nrMsg2Rnti = int(self.args['dci10Msg2']['rnti'], 16)
        self.nrMsg2MuPdcch = int(self.args['dci10Msg2']['muPdcch'])
        self.nrMsg2MuPdsch = int(self.args['dci10Msg2']['muPdsch'])
        self.nrMsg2TdRa = self.args['dci10Msg2']['tdRa']
        self.nrMsg2TdMappingType = self.args['dci10Msg2']['tdMappingType']
        self.nrMsg2TdK0 = int(self.args['dci10Msg2']['tdK0'])
        self.nrMsg2TdSliv = int(self.args['dci10Msg2']['tdSliv'])
        self.nrMsg2TdStartSymb = int(self.args['dci10Msg2']['tdStartSymb'])
        self.nrMsg2TdNumSymbs = int(self.args['dci10Msg2']['tdNumSymbs'])
        self.nrMsg2FdRaType = self.args['dci10Msg2']['fdRaType']
        self.nrMsg2FdRa = self.args['dci10Msg2']['fdRa']
        self.nrMsg2FdStartRb = int(self.args['dci10Msg2']['fdStartRb'])
        self.nrMsg2FdNumRbs = int(self.args['dci10Msg2']['fdNumRbs'])
        self.nrMsg2FdVrbPrbMappingType = self.args['dci10Msg2']['fdVrbPrbMappingType']
        self.nrMsg2FdBundleSize = int(self.args['dci10Msg2']['fdBundleSize'][1:])

        self.nrMsg2DmrsType = self.args['dmrsMsg2']['dmrsType']
        self.nrMsg2DmrsAddPos = self.args['dmrsMsg2']['dmrsAddPos']
        self.nrMsg2DmrsMaxLen = self.args['dmrsMsg2']['maxLength']
        self.nrMsg2DmrsPorts = self.args['dmrsMsg2']['dmrsPorts']
        self.nrMsg2DmrsCdmGroupsWoData = int(self.args['dmrsMsg2']['cdmGroupsWoData'])
        self.nrMsg2DmrsNumFrontLoadSymbs = int(self.args['dmrsMsg2']['numFrontLoadSymbs'])
        self.nrMsg2DmrsTdL = self.args['dmrsMsg2']['tdL']
        self.nrMsg2DmrsFdK = self.args['dmrsMsg2']['fdK']

        #DCI 1_0 with CSS interleaved VRB-to-PRB mapping
        if self.nrSib1FdVrbPrbMappingType == 'interleaved':
            self.dci10CssPrbs = self.dci10CssVrb2PrbMapping(coreset0Size=self.nrCoreset0NumRbs, iniDlBwpStart=0, coreset0Start=0, L=self.nrSib1FdBundleSize)

        self.nrIniUlBwpId = int(self.args['iniUlBwp']['bwpId'])
        self.nrIniUlBwpScs = int(self.args['iniUlBwp']['scs'][:-3])
        self.nrIniUlBwpCp = self.args['iniUlBwp']['cp']
        self.nrIniUlBwpLocAndBw = int(self.args['iniUlBwp']['locAndBw'])
        self.nrIniUlBwpStartRb = int(self.args['iniUlBwp']['startRb'])
        self.nrIniUlBwpNumRbs = int(self.args['iniUlBwp']['numRbs'])

        self.nrRachCfgId = int(self.args['rach']['prachConfId'])
        self.nrRachCfgFormat = self.args['rach']['raFormat']
        self.nrRachCfgPeriodx = self.args['rach']['raX']
        self.nrRachCfgOffsety = self.args['rach']['raY']
        self.nrRachCfgSubfNumFr1SlotNumFr2 = self.args['rach']['raSubfNumFr1SlotNumFr2']
        self.nrRachCfgStartSymb = int(self.args['rach']['raStartingSymb'])
        self.nrRachCfgNumSlotsPerSubfFr1Per60KSlotFR2 = int(self.args['rach']['raNumSlotsPerSubfFr1Per60KSlotFr2'])
        self.nrRachCfgNumOccasionsPerSlot = int(self.args['rach']['raNumOccasionsPerSlot'])
        self.nrRachCfgDuration = int(self.args['rach']['raDuration'])
        if self.nrRachCfgFormat in ('0', '1', '2', '3'):
            self.nrRachCfgDuration = {'0':14, '1':42, '2':49, '3':14}[self.nrRachCfgFormat]
        self.nrRachScs = self.args['rach']['scs'][:-3] #value range: {'1.25', '5', '15', '30', '60', '120'}
        self.prachScs = 15 if self.nrRachScs in ('1.25', '5') else int(self.nrRachScs)
        self.nrRachMsg1Fdm = int(self.args['rach']['msg1Fdm'])
        self.nrRachMsg1FreqStart = int(self.args['rach']['msg1FreqStart'])
        self.nrRachRaRespWin = int(self.args['rach']['raRespWin'][2:])
        self.nrRachTotNumPreambs = int(self.args['rach']['totNumPreambs'])
        ssbPerRachOccasionMap = {'oneEighth':1, 'oneFourth':2, 'oneHalf':4, 'one':8, 'two':16, 'four':32, 'eight':64, 'sixteen':128}
        self.nrRachSsbPerRachOccasionM8 = ssbPerRachOccasionMap[self.args['rach']['ssbPerRachOccasion']]
        self.nrRachCbPreambsPerSsb = int(self.args['rach']['cbPreambsPerSsb'])
        self.nrRachContResTimer = int(self.args['rach']['contResTimer'][2:])
        self.nrRachMsg3Tp = self.args['rach']['msg3Tp']
        self.nrRachPreambLen = self.args['rach']['raLen']
        self.nrRachNumRbs = self.args['rach']['raNumRbs']
        self.nrRachKBar = self.args['rach']['raKBar']

        self.numTxSsb = len([c for c in self.ssbSet if c == '1'])
        self.minNumValidPrachOccasionPerAssociationPeriod = math.ceil(self.numTxSsb / self.nrRachSsbPerRachOccasionM8 * 8)

        self.nrMsg3MuPusch = int(self.args['msg3Pusch']['muPusch'])
        self.nrMsg3TdRa = int(self.args['msg3Pusch']['tdRa'])
        self.nrMsg3TdMappingType = self.args['msg3Pusch']['tdMappingType']
        self.nrMsg3TdK2 = int(self.args['msg3Pusch']['tdK2'])
        self.nrMsg3TdDelta = int(self.args['msg3Pusch']['tdDelta'])
        self.nrMsg3TdSliv = int(self.args['msg3Pusch']['tdSliv'])
        self.nrMsg3TdStartSymb = int(self.args['msg3Pusch']['tdStartSymb'])
        self.nrMsg3TdNumSymbs = int(self.args['msg3Pusch']['tdNumSymbs'])
        self.nrMsg3FdRaType = self.args['msg3Pusch']['fdRaType']
        self.nrMsg3FdFreqHop = self.args['msg3Pusch']['fdFreqHop']
        self.nrMsg3FdRa = self.args['msg3Pusch']['fdRa']
        self.nrMsg3FdStartRb = int(self.args['msg3Pusch']['fdStartRb'])
        self.nrMsg3FdNumRbs = int(self.args['msg3Pusch']['fdNumRbs'])
        if self.nrMsg3FdFreqHop == 'enabled':
            self.nrMsg3FdSecondHopFreqOff = int(self.args['msg3Pusch']['fdSecondHopFreqOff'])
        else:
            self.nrMsg3FdSecondHopFreqOff = None

        self.nrMsg3DmrsType = self.args['dmrsMsg3']['dmrsType']
        self.nrMsg3DmrsAddPos = self.args['dmrsMsg3']['dmrsAddPos']
        self.nrMsg3DmrsMaxLen = self.args['dmrsMsg3']['maxLength']
        self.nrMsg3DmrsPorts = self.args['dmrsMsg3']['dmrsPorts']
        self.nrMsg3DmrsCdmGroupsWoData = int(self.args['dmrsMsg3']['cdmGroupsWoData'])
        self.nrMsg3DmrsNumFrontLoadSymbs = int(self.args['dmrsMsg3']['numFrontLoadSymbs'])
        self.nrMsg3DmrsTdL = self.args['dmrsMsg3']['tdL']
        self.nrMsg3DmrsFdK = self.args['dmrsMsg3']['fdK']

        self.nrMsg4Rnti = int(self.args['dci10Msg4']['rnti'], 16)
        self.nrMsg4MuPdcch = int(self.args['dci10Msg4']['muPdcch'])
        self.nrMsg4MuPdsch = int(self.args['dci10Msg4']['muPdsch'])
        self.nrMsg4TdRa = self.args['dci10Msg4']['tdRa']
        self.nrMsg4TdMappingType = self.args['dci10Msg4']['tdMappingType']
        self.nrMsg4TdK0 = int(self.args['dci10Msg4']['tdK0'])
        self.nrMsg4TdSliv = int(self.args['dci10Msg4']['tdSliv'])
        self.nrMsg4TdStartSymb = int(self.args['dci10Msg4']['tdStartSymb'])
        self.nrMsg4TdNumSymbs = int(self.args['dci10Msg4']['tdNumSymbs'])
        self.nrMsg4FdRaType = self.args['dci10Msg4']['fdRaType']
        self.nrMsg4FdRa = self.args['dci10Msg4']['fdRa']
        self.nrMsg4FdStartRb = int(self.args['dci10Msg4']['fdStartRb'])
        self.nrMsg4FdNumRbs = int(self.args['dci10Msg4']['fdNumRbs'])
        self.nrMsg4FdVrbPrbMappingType = self.args['dci10Msg4']['fdVrbPrbMappingType']
        self.nrMsg4FdBundleSize = int(self.args['dci10Msg4']['fdBundleSize'][1:])
        self.nrMsg4DeltaPri = int(self.args['dci10Msg4']['deltaPri'])
        self.nrMsg4TdK1 = int(self.args['dci10Msg4']['tdK1'])

        self.nrMsg4DmrsType = self.args['dmrsMsg4']['dmrsType']
        self.nrMsg4DmrsAddPos = self.args['dmrsMsg4']['dmrsAddPos']
        self.nrMsg4DmrsMaxLen = self.args['dmrsMsg4']['maxLength']
        self.nrMsg4DmrsPorts = self.args['dmrsMsg4']['dmrsPorts']
        self.nrMsg4DmrsCdmGroupsWoData = int(self.args['dmrsMsg4']['cdmGroupsWoData'])
        self.nrMsg4DmrsNumFrontLoadSymbs = int(self.args['dmrsMsg4']['numFrontLoadSymbs'])
        self.nrMsg4DmrsTdL = self.args['dmrsMsg4']['tdL']
        self.nrMsg4DmrsFdK = self.args['dmrsMsg4']['fdK']

        #whether dedicated ul/dl bwp is received through MSG4?
        self.msg4Recved = False

        self.nrDedDlBwpId = int(self.args['dedDlBwp']['bwpId'])
        self.nrDedDlBwpScs = int(self.args['dedDlBwp']['scs'][:-3])
        self.nrDedDlBwpCp = self.args['dedDlBwp']['cp']
        self.nrDedDlBwpLocAndBw = int(self.args['dedDlBwp']['locAndBw'])
        self.nrDedDlBwpStartRb = int(self.args['dedDlBwp']['startRb'])
        self.nrDedDlBwpNumRbs = int(self.args['dedDlBwp']['numRbs'])

        self.nrNzpCsiRsResSetId = int(self.args['nzpCsiRs']['resSetId'])
        self.nrNzpCsiRsTrsInfo = self.args['nzpCsiRs']['trsInfo']
        self.nrNzpCsiRsResId = int(self.args['nzpCsiRs']['resId'])
        self.nrNzpCsiRsNumPorts = int(self.args['nzpCsiRs']['numPorts'][1:])
        self.nrNzpCsiRsCdmType = self.args['nzpCsiRs']['cdmType']
        self.nrNzpCsiRsDensity = self.args['nzpCsiRs']['density']
        self.nrNzpCsiRsFreqAlloc = self.args['nzpCsiRs']['freqAlloc']
        self.nrNzpCsiRsFirstSymb = int(self.args['nzpCsiRs']['firstSymb']) if self.args['nzpCsiRs']['firstSymb'] else None
        self.nrNzpCsiRsFirstSymb2 = int(self.args['nzpCsiRs']['firstSymb2']) if self.args['nzpCsiRs']['firstSymb2'] else None
        self.nrNzpCsiRsStartRb = int(self.args['nzpCsiRs']['startRb'])
        self.nrNzpCsiRsNumRbs = int(self.args['nzpCsiRs']['numRbs'])
        self.nrNzpCsiRsPeriod = int(self.args['nzpCsiRs']['period'][5:])
        self.nrNzpCsiRsOffset = int(self.args['nzpCsiRs']['offset'])
        self.nrNzpCsiRsRow = self.args['nzpCsiRs']['row']
        self.nrNzpCsiRsKBarLBar = self.args['nzpCsiRs']['kBarLBar']
        self.nrNzpCsiRsKi = self.args['nzpCsiRs']['ki']
        self.nrNzpCsiRsLi = self.args['nzpCsiRs']['li']
        self.nrNzpCsiRsCdmGrpIndj = self.args['nzpCsiRs']['cdmGrpIndj']
        self.nrNzpCsiRsKap = self.args['nzpCsiRs']['kap']
        self.nrNzpCsiRsLap = self.args['nzpCsiRs']['lap']

        self.nrTrsResSetId = int(self.args['trs']['resSetId'])
        self.nrTrsTrsInfo = self.args['trs']['trsInfo']
        startResId, endResId = self.args['trs']['resId'].split('-')
        self.nrTrsResIdList = list(range(int(startResId), int(endResId)+1))
        self.nrTrsNumPorts = int(self.args['trs']['numPorts'][1:])
        self.nrTrsCdmType = self.args['trs']['cdmType']
        self.nrTrsDensity = self.args['trs']['density']
        self.nrTrsFreqAlloc = self.args['trs']['freqAlloc']
        self.nrTrsFirstSymbList = [int(k) for k in self.args['trs']['firstSymb'].split(',')]
        self.nrTrsStartRb = int(self.args['trs']['startRb'])
        self.nrTrsNumRbs = int(self.args['trs']['numRbs'])
        self.nrTrsPeriod = int(self.args['trs']['period'][5:])
        self.nrTrsOffsetList = [int(k) for k in self.args['trs']['offset'].split(',')]
        self.nrTrsRow = self.args['trs']['row']
        self.nrTrsKBarLBar = self.args['trs']['kBarLBar']
        self.nrTrsKi = self.args['trs']['ki']
        self.nrTrsLi = self.args['trs']['li']
        self.nrTrsCdmGrpIndj = self.args['trs']['cdmGrpIndj']
        self.nrTrsKap = self.args['trs']['kap']
        self.nrTrsLap = self.args['trs']['lap']

        self.nrCsiImResSetId = int(self.args['csiIm']['resSetId'])
        self.nrCsiImResId = int(self.args['csiIm']['resId'])
        self.nrCsiImRePattern = self.args['csiIm']['rePattern']
        self.nrCsiImScLoc = int(self.args['csiIm']['scLoc'][1:])
        self.nrCsiImSymbLoc = int(self.args['csiIm']['symbLoc'])
        self.nrCsiImStartRb = int(self.args['csiIm']['startRb'])
        self.nrCsiImNumRbs = int(self.args['csiIm']['numRbs'])
        self.nrCsiImPeriod = int(self.args['csiIm']['period'][5:])
        self.nrCsiImOffset = int(self.args['csiIm']['offset'])

        self.nrNzpCsiRsResCfgId = int(self.args['nzpCsiRsResCfg']['resCfgId'])
        self.nrNzpCsiRsResCfgResSetId = int(self.args['nzpCsiRsResCfg']['resSetId'])
        self.nrNzpCsiRsResCfgBwpId = int(self.args['nzpCsiRsResCfg']['bwpId'])
        self.nrNzpCsiRsResCfgResType = self.args['nzpCsiRsResCfg']['resType']

        self.nrTrsResCfgId = int(self.args['trsResCfg']['resCfgId'])
        self.nrTrsResCfgResSetId = int(self.args['trsResCfg']['resSetId'])
        self.nrTrsResCfgBwpId = int(self.args['trsResCfg']['bwpId'])
        self.nrTrsResCfgResType = self.args['trsResCfg']['resType']

        self.nrCsiImResCfgId = int(self.args['csiImResCfg']['resCfgId'])
        self.nrCsiImResCfgResSetId = int(self.args['csiImResCfg']['resSetId'])
        self.nrCsiImResCfgBwpId = int(self.args['csiImResCfg']['bwpId'])
        self.nrCsiImResCfgResType = self.args['csiImResCfg']['resType']

        self.nrCsiRepCfgId = int(self.args['csiRepCfg']['repCfgId'])
        self.nrCsiRepCfgResCfgIdChnMeas = int(self.args['csiRepCfg']['resCfgIdChnMeas'])
        self.nrCsiRepCfgResCfgIdCsiImIntf = int(self.args['csiRepCfg']['resCfgIdCsiImIntf'])
        self.nrCsiRepCfgRepType = self.args['csiRepCfg']['repType']
        self.nrCsiRepCfgPeriod = int(self.args['csiRepCfg']['period'][5:])
        self.nrCsiRepCfgOffset = int(self.args['csiRepCfg']['offset'])
        self.nrCsiRepCfgUlBwpId = int(self.args['csiRepCfg']['ulBwpId'])
        self.nrCsiRepCfgPucchRes = int(self.args['csiRepCfg']['pucchRes'])
        self.nrCsiRepCfgQuantity = self.args['csiRepCfg']['quantity']

        self.nrDedUlBwpId = int(self.args['dedUlBwp']['bwpId'])
        self.nrDedUlBwpScs = int(self.args['dedUlBwp']['scs'][:-3])
        self.nrDedUlBwpCp = self.args['dedUlBwp']['cp']
        self.nrDedUlBwpLocAndBw = int(self.args['dedUlBwp']['locAndBw'])
        self.nrDedUlBwpStartRb = int(self.args['dedUlBwp']['startRb'])
        self.nrDedUlBwpNumRbs = int(self.args['dedUlBwp']['numRbs'])

        self.nrSrsRes = dict()
        for i in range(4):
            self.nrSrsRes[i] = dict()
            self.nrSrsRes[i]['resId'] = int(self.args['srsRes%d' % i]['resId'])
            self.nrSrsRes[i]['numPorts'] = int(self.args['srsRes%d' % i]['numPorts'][-1:])
            self.nrSrsRes[i]['nonCbPtrsPort'] = int(self.args['srsRes%d' % i]['nonCbPtrsPort'][1:])
            self.nrSrsRes[i]['numCombs'] = int(self.args['srsRes%d' % i]['numCombs'][1:])
            self.nrSrsRes[i]['combOff'] = int(self.args['srsRes%d' % i]['combOff'])
            self.nrSrsRes[i]['startPos'] = int(self.args['srsRes%d' % i]['startPos'])
            self.nrSrsRes[i]['numSymbs'] = int(self.args['srsRes%d' % i]['numSymbs'][1:])
            self.nrSrsRes[i]['repetition'] = int(self.args['srsRes%d' % i]['repetition'][1:])
            self.nrSrsRes[i]['freqPos'] = int(self.args['srsRes%d' % i]['freqPos'])
            self.nrSrsRes[i]['freqShift'] = int(self.args['srsRes%d' % i]['freqShift'])
            self.nrSrsRes[i]['cSrs'] = int(self.args['srsRes%d' % i]['cSrs'])
            self.nrSrsRes[i]['bSrs'] = int(self.args['srsRes%d' % i]['bSrs'])
            self.nrSrsRes[i]['bHop'] = int(self.args['srsRes%d' % i]['bHop'])
            self.nrSrsRes[i]['type'] = self.args['srsRes%d' % i]['type']
            self.nrSrsRes[i]['period'] = int(self.args['srsRes%d' % i]['period'][2:])
            self.nrSrsRes[i]['offset'] = int(self.args['srsRes%d' % i]['offset'])
            self.nrSrsRes[i]['mSRSb'] = self.args['srsRes%d' % i]['mSRSb']
            self.nrSrsRes[i]['Nb'] = self.args['srsRes%d' % i]['Nb']

        self.nrSrsResSet0Id = int(self.args['srsResSet0']['resSetId'])
        self.nrSrsResSet0ResList = [int(k) for k in self.args['srsResSet0']['resIdList'].split(',')]
        self.nrSrsResSet0Type = self.args['srsResSet0']['type']
        self.nrSrsResSet0Usage = self.args['srsResSet0']['usage']

        self.nrSrsResSet1Id = int(self.args['srsResSet1']['resSetId'])
        self.nrSrsResSet1ResList = [int(k) for k in self.args['srsResSet1']['resIdList'].split(',')]
        self.nrSrsResSet1Type = self.args['srsResSet1']['type']
        self.nrSrsResSet1Usage = self.args['srsResSet1']['usage']

        self.nrPucchFmt134NumSlots = int(self.args['pucchFmtCfg']['numSlots'][1:])
        self.nrPucchFmt134InterSlotFreqHop = self.args['pucchFmtCfg']['interSlotFreqHop']
        self.nrPucchFmt34AddDmrs = self.args['pucchFmtCfg']['addDmrs']
        self.nrPucchFmt234SimulAckCsi = self.args['pucchFmtCfg']['simulAckCsi']

        self.nrPucchRes = dict()
        for i in range(5):
            self.nrPucchRes[i] = dict()
            self.nrPucchRes[i]['resId'] = int(self.args['pucchRes%d' % i]['resId'])
            self.nrPucchRes[i]['format'] = int(self.args['pucchRes%d' % i]['format'][-1:])
            self.nrPucchRes[i]['resSetId'] = int(self.args['pucchRes%d' % i]['resSetId'])
            self.nrPucchRes[i]['startRb'] = int(self.args['pucchRes%d' % i]['startRb'])
            self.nrPucchRes[i]['intraSlotFreqHop'] = self.args['pucchRes%d' % i]['intraSlotFreqHop']
            if self.nrPucchRes[i]['intraSlotFreqHop'] == 'enabled' or (self.nrPucchFmt134NumSlots > 1 and self.nrPucchFmt134InterSlotFreqHop == 'enabled'):
                self.nrPucchRes[i]['secondHopPrb'] = int(self.args['pucchRes%d' % i]['secondHopPrb'])
            else:
                self.nrPucchRes[i]['secondHopPrb'] = None
            self.nrPucchRes[i]['numRbs'] = int(self.args['pucchRes%d' % i]['numRbs'])
            self.nrPucchRes[i]['startSymb'] = int(self.args['pucchRes%d' % i]['startSymb'])
            self.nrPucchRes[i]['numSymbs'] = int(self.args['pucchRes%d' % i]['numSymbs'])

        self.nrDsrRes = dict()
        for i in range(2):
            self.nrDsrRes[i] = dict()
            self.nrDsrRes[i]['resId'] = int(self.args['dsrRes%d' % i]['resId'])
            self.nrDsrRes[i]['pucchRes'] = int(self.args['dsrRes%d' % i]['pucchRes'])
            self.nrDsrRes[i]['period'] = self.args['dsrRes%d' % i]['period']
            self.nrDsrRes[i]['offset'] = int(self.args['dsrRes%d' % i]['offset'])

        #advanced settings
        try:
            self.nrAdvBestSsb = int(self.args['advanced']['bestSsb'])
        except Exception as e:
            self.nrAdvBestSsb = None

        try:
            self.nrAdvSib1PdcchSlot = [int(k) for k in self.args['advanced']['sib1PdcchSlot']]
        except Exception as e:
            self.nrAdvSib1PdcchSlot = None

        try:
            self.nrAdvPrachOccasion = int(self.args['advanced']['prachOccasion'])
        except Exception as e:
            self.nrAdvPrachOccasion = None

        try:
            self.nrAdvMsg2PdcchOccasion = int(self.args['advanced']['msg2PdcchOcc'])
        except Exception as e:
            self.nrAdvMsg2PdcchOccasion = None

        try:
            self.nrAdvMsg4PdcchOccasion = int(self.args['advanced']['msg4PdcchOcc'])
        except Exception as e:
            self.nrAdvMsg4PdcchOccasion = None

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
            qApp.processEvents()
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
                qApp.processEvents()
                return False
            self.pat2NumSlotsPerPeriod = self.tddCfgRefScsPeriod[key]
            self.nrTddCfgPat2NumDlSlots = int(self.args['tddCfg']['pat2NumDlSlots'])
            self.nrTddCfgPat2NumDlSymbs = int(self.args['tddCfg']['pat2NumDlSymbs'])
            self.nrTddCfgPat2NumUlSymbs = int(self.args['tddCfg']['pat2NumUlSymbs'])
            self.nrTddCfgPat2NumUlSlots = int(self.args['tddCfg']['pat2NumUlSlots'])

            period = self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']] + self.tddCfgPeriod2Int[self.args['tddCfg']['pat2Period']]
            if 160 % period != 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid TDD-UL-DL-Config periodicity(=%.3fms) with p=%.3fms and p2=%.3fms, which should divide 20ms!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), period/8, self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']]/8, self.tddCfgPeriod2Int[self.args['tddCfg']['pat2Period']]/8))
                qApp.processEvents()
                return False
        else:
            self.pat2NumSlotsPerPeriod = None
            period = self.tddCfgPeriod2Int[self.args['tddCfg']['pat1Period']]
            if 160 % period != 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid TDD-UL-DL-Config periodicity(=%.3fms), which should divide 20ms!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), period/8))
                qApp.processEvents()
                return False

        self.periodsPer20ms = 160 // period

        pattern = []
        pattern.extend(['D'] * self.nrTddCfgPat1NumDlSlots * self.nrSymbPerSlotNormCp)
        pattern.extend(['D'] * self.nrTddCfgPat1NumDlSymbs)
        pattern.extend(['F'] * ((self.pat1NumSlotsPerPeriod - self.nrTddCfgPat1NumDlSlots - self.nrTddCfgPat1NumUlSlots) * self.nrSymbPerSlotNormCp - self.nrTddCfgPat1NumDlSymbs - self.nrTddCfgPat1NumUlSymbs))
        pattern.extend(['U'] * self.nrTddCfgPat1NumUlSymbs)
        pattern.extend(['U'] * self.nrTddCfgPat1NumUlSlots * self.nrSymbPerSlotNormCp)

        if self.pat2NumSlotsPerPeriod is not None:
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
        qApp.processEvents()

        return True

    def initTddGrid(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside initTddGrid(hsfn=%d, sfn=%d)' % (hsfn, sfn))
        qApp.processEvents()

        dn = '%s_%s' % (hsfn, sfn)
        if not dn in self.gridNrTdd:
            #report error
            return

        tddCfgMap = {'D':NrResType.NR_RES_D.value, 'F':NrResType.NR_RES_F.value, 'U':NrResType.NR_RES_U.value}
        scaleTd = self.baseScsTd // self.nrTddCfgRefScs
        self.ngwin.logEdit.append('scaleTd=%d where baseScsTd=%dKHz and tddCfgRefScs=%dKHz' % (scaleTd, self.baseScsTd, self.nrTddCfgRefScs))
        qApp.processEvents()
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
        self.ngwin.logEdit.append('---->exporting to excel(engine=xlsxwriter), please wait...')
        qApp.processEvents()
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
                        #horizontalHeader.append('sfn%s\nslot%d\nsymb%d' % (sfn, i, j))
                        horizontalHeader.append('%s-%d-%d' % (sfn, i, j))

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
            #sheet1.freeze_panes(1, 1)
            sheet1.freeze_panes(self.nrScGb+1, 1)
            for row in range(2, self.nrScGb):
                sheet1.set_row(row, None, None, {'hidden':True})

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
            #sheet1.freeze_panes(1, 1)
            sheet1.freeze_panes(self.nrScGb+1, 1)
            for row in range(2, self.nrScGb):
                sheet1.set_row(row, None, None, {'hidden':True})

            sheet2 = workbook.add_worksheet('FDD DL Grid')
            sheet2.set_zoom(80)
            #sheet2.freeze_panes(1, 1)
            sheet2.freeze_panes(self.nrScGb+1, 1)
            for row in range(2, self.nrScGb):
                sheet2.set_row(row, None, None, {'hidden':True})

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

    def monitorPdcch(self, hsfn, sfn, slot, dci=None, rnti=None):
        if self.error:
            return (None, None, None)

        if dci is None or rnti is None:
            return (None, None, None)

        if not dci in ('dci01', 'dci10', 'dci11'):
            return (None, None, None)

        if not rnti in ('ra-rnti', 'tc-rnti', 'c-rnti'):
            return (None, None, None)

        self.ngwin.logEdit.append('---->inside monitorPdcch(hsfn=%d, sfn=%d, slot=%d, dci="%s",rnti="%s", scaleTdSsb=%d, scaleTdRmsiScs=%d)' % (hsfn, sfn, slot, dci, rnti, self.baseScsTd // self.nrSsbScs, self.baseScsTd // self.nrMibCommonScs))
        qApp.processEvents()

        if dci == 'dci10' and rnti == 'ra-rnti':
            #convert 'slot'+'msg1LastSymb' which based on prachScs into commonScs
            tmpStr = 'converting from prachScs(=%dKHz) to commonScs(=%dKHz): [hsfn=%d, sfn=%d, slot=%d, msg1LastSymb=%d] --> ' % (self.prachScs, self.nrMibCommonScs, hsfn, sfn,  slot, self.msg1LastSymb)

            scaleTd = self.nrMibCommonScs / self.prachScs
            firstSlotMonitoring = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg1LastSymb + 1) * scaleTd - 1) // self.nrSymbPerSlotNormCp)
            if firstSlotMonitoring >= self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]:
                firstSlotMonitoring = firstSlotMonitoring % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                #self.recvSsb(hsfn, sfn)
                self.alwaysOnTr(hsfn, sfn)
            firstSymbMonitoring = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg1LastSymb + 1) * scaleTd - 1) % self.nrSymbPerSlotNormCp)

            tmpStr = tmpStr + '[hsfn=%d, sfn=%d, slot=%d, symb=%d]' % (hsfn, sfn, firstSlotMonitoring, firstSymbMonitoring)
            self.ngwin.logEdit.append(tmpStr)
            qApp.processEvents()

            oldHsfn, oldSfn = hsfn, sfn

            #refer to 3GPP 38.213 vf40 8.2
            #The window starts at the first symbol of the earliest CORESET the UE is configured to receive PDCCH for Type1-PDCCH CSS set, as defined in Subclause 10.1, that is at least one symbol, after the last symbol of the PRACH occasion corresponding to the PRACH transmission, where the symbol duration corresponds to the SCS for Type1-PDCCH CSS set as defined in Subclause 10.1.
            firstSymbMonitoring = firstSymbMonitoring + 1
            if firstSymbMonitoring >= self.nrSymbPerSlotNormCp:
                firstSymbMonitoring = firstSymbMonitoring % self.nrSymbPerSlotNormCp
                firstSlotMonitoring = firstSlotMonitoring + 1
                if firstSlotMonitoring >= self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]:
                    firstSlotMonitoring = firstSlotMonitoring % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                    hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                    #self.recvSsb(hsfn, sfn)
                    self.alwaysOnTr(hsfn, sfn)

            self.ngwin.logEdit.append('start monitoring CSS0 for DCI 1_0 scheduling RAR: hsfn=%d, sfn=%d, firstSlotMonitoring=%d, firstSymbMonitoring=%d' % (hsfn, sfn, firstSlotMonitoring, firstSymbMonitoring))
            qApp.processEvents()

            symbInd = ((1024 * hsfn + sfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + firstSlotMonitoring) * self.nrSymbPerSlotNormCp + firstSymbMonitoring
            css0Msg2 = []
            maxTry = math.ceil(self.nrSsbPeriod / 10) + 1
            count=0
            while count < maxTry:
                ret = self.detCss0(hsfn, sfn)
                if not ret:
                    if self.ngwin.enableDebug:
                        self.ngwin.logEdit.append('<font color=red>detCss0 failed, hsfn=%s,sfn=%s</font>' % (hsfn, sfn))
                        qApp.processEvents()
                else:
                    key1 = '%s_%s' % (hsfn, sfn)
                    for i in range(len(self.ssbFirstSymbInBaseScsTd[key1])):
                        if self.ssbFirstSymbInBaseScsTd[key1][i] is None:
                            #self.coreset0Occasions.append(None)
                            continue
                        key2 = '%s_%s' % (key1, i)
                        oc, firstSymb, valid = self.coreset0Occasions[key2]
                        for j in range(len(valid)):
                            if valid[j] == 'NOK':
                                continue
                            ocHsfn, ocSfn, ocSlot = oc[j]
                            symbInd2 = ((1024 * ocHsfn + ocSfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + ocSlot) * self.nrSymbPerSlotNormCp + firstSymb
                            if symbInd2 >= symbInd:
                                numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
                                for k in range(numCandidates):
                                    cand = [ocHsfn, ocSfn, ocSlot, firstSymb, k]
                                    if cand not in self.reservedPdcchSib1.values() and cand not in css0Msg2:
                                        css0Msg2.append(cand)

                if len(css0Msg2) > 0:
                    break

                count = count + 1
                hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                #self.recvSsb(hsfn, sfn)
                self.alwaysOnTr(hsfn, sfn)

            if len(css0Msg2) == 0:
                self.ngwin.logEdit.append('<font color=red>Error: css0Msg2 is empty after maxTry=%d frames!</font>' % maxTry)
                qApp.processEvents()
                self.error = True
                return (None, None, None)

            startHsfn, startSfn, startSlot, startFirstSymb,startPdcchCandidate = css0Msg2[0]
            raRespWinStart = ((1024 * startHsfn + startSfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + startSlot) * self.nrSymbPerSlotNormCp + startFirstSymb
            raRespWinEnd = ((1024 * startHsfn + startSfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + startSlot + self.nrRachRaRespWin) * self.nrSymbPerSlotNormCp + startFirstSymb - self.nrCoreset0NumSymbs
            validCss0Msg2 = [css0Msg2[0]]
            for i in range(1, len(css0Msg2)):
                ocHsfn, ocSfn, ocSlot, ocFirstSymb, ocPdcchCandidate = css0Msg2[i]
                symbInd2 = ((1024 * ocHsfn + ocSfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + ocSlot) * self.nrSymbPerSlotNormCp + ocFirstSymb
                if symbInd2 >= raRespWinStart and symbInd2 < raRespWinEnd:
                    validCss0Msg2.append(css0Msg2[i])

            self.ngwin.logEdit.append('contents of css0Msg2:')
            for i in range(len(css0Msg2)):
                self.ngwin.logEdit.append('PDCCH occasion #%d: %s' % (i, css0Msg2[i]))
            self.ngwin.logEdit.append('contents of validCss0Msg2(raRespWin=%d slots):' % self.nrRachRaRespWin)
            for i in range(len(validCss0Msg2)):
                self.ngwin.logEdit.append('PDCCH occasion #%d: %s' % (i, validCss0Msg2[i]))
            qApp.processEvents()

            #remove 'not-used' HSFN+SFN from gridNrTdd/gridNrFddUl/gridNrFddDl
            validHsfnSfn = []
            validHsfnSfn.append([oldHsfn, oldSfn])
            for i in range(len(validCss0Msg2)):
                _hsfn, _sfn, _slot, _symb, _cand = validCss0Msg2[i]
                if [_hsfn, _sfn] not in validHsfnSfn:
                    validHsfnSfn.append([_hsfn, _sfn])

            if self.nrDuplexMode == 'TDD':
                keys = list(self.gridNrTdd.keys())
                for key in keys:
                    _hsfn, _sfn = [int(k) for k in key.split('_')]
                    if (_hsfn > oldHsfn or (_hsfn == oldHsfn and _sfn >= oldSfn)) and [_hsfn, _sfn] not in validHsfnSfn:
                        if self.ngwin.enableDebug:
                            self.ngwin.logEdit.append('unused [hsfn=%d,sfn=%d] removed' % (_hsfn, _sfn))
                            qApp.processEvents()
                        self.gridNrTdd.pop('%s_%s' % (_hsfn, _sfn))
            else:
                keys = list(self.gridNrFddDl.keys())
                for key in keys:
                    _hsfn, _sfn = [int(k) for k in key.split('_')]
                    if (_hsfn > oldHsfn or (_hsfn == oldHsfn and _sfn >= oldSfn)) and [_hsfn, _sfn] not in validHsfnSfn:
                        if self.ngwin.enableDebug:
                            self.ngwin.logEdit.append('unused [hsfn=%d,sfn=%d] removed' % (_hsfn, _sfn))
                            qApp.processEvents()
                        self.gridNrFddUl.pop('%s_%s' % (_hsfn, _sfn))
                        self.gridNrFddDl.pop('%s_%s' % (_hsfn, _sfn))

            #randomly select from validCss0Msg2 pdcch occasion for msg2 scheduling
            pdcchOccasion = np.random.randint(0, len(validCss0Msg2)) if self.nrAdvMsg2PdcchOccasion is None else self.nrAdvMsg2PdcchOccasion
            hsfn, sfn, slot, firstSymb, pdcchCandidate = validCss0Msg2[pdcchOccasion]

            #numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
            #pdcchCandidate = np.random.randint(0, numCandidates) if self.nrAdvMsg2PdcchCand is None else self.nrAdvMsg2PdcchCand

            self.ngwin.logEdit.append('<font color=purple>Select PDCCH scheduling Msg2(RAR): [%s]</font>' % validCss0Msg2[pdcchOccasion])
            qApp.processEvents()

            scaleTd = self.baseScsTd // self.nrMibCommonScs
            scaleFd = self.nrMibCommonScs // self.baseScsFd
            dn2 = '%s_%s' % (hsfn, sfn)
            firstSymbInBaseScsTd = (slot * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
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

            return (hsfn, sfn, slot)
        elif dci == 'dci10' and rnti == 'tc-rnti':
            #convert 'slot'+'msg3LastSymb' which based on puschScs(initial ul bwp) into commonScs
            tmpStr = 'converting from puschScs(=%dKHz) to commonScs(=%dKHz): [hsfn=%d, sfn=%d, slot=%d, msg3LastSymb=%d] --> ' % (self.nrIniUlBwpScs, self.nrMibCommonScs, hsfn, sfn,  slot, self.msg3LastSymb)

            scaleTd = self.nrMibCommonScs / self.nrIniUlBwpScs
            firstSlotMonitoring = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg3LastSymb + 1) * scaleTd - 1) // self.nrSymbPerSlotNormCp)
            if firstSlotMonitoring >= self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]:
                firstSlotMonitoring = firstSlotMonitoring % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                #self.recvSsb(hsfn, sfn)
                self.alwaysOnTr(hsfn, sfn)
            firstSymbMonitoring = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg3LastSymb + 1) * scaleTd - 1) % self.nrSymbPerSlotNormCp)

            tmpStr = tmpStr + '[hsfn=%d, sfn=%d, slot=%d, symb=%d]' % (hsfn, sfn, firstSlotMonitoring, firstSymbMonitoring)
            self.ngwin.logEdit.append(tmpStr)
            qApp.processEvents()

            oldHsfn, oldSfn = hsfn, sfn
            #start pdcch monitoring for msg4 scheduling
            firstSymbMonitoring = firstSymbMonitoring + 1
            if firstSymbMonitoring >= self.nrSymbPerSlotNormCp:
                firstSymbMonitoring = firstSymbMonitoring % self.nrSymbPerSlotNormCp
                firstSlotMonitoring = firstSlotMonitoring + 1
                if firstSlotMonitoring >= self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]:
                    firstSlotMonitoring = firstSlotMonitoring % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                    hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                    #self.recvSsb(hsfn, sfn)
                    self.alwaysOnTr(hsfn, sfn)

            self.ngwin.logEdit.append('start monitoring CSS0 for DCI 1_0 scheduling Msg4: hsfn=%d, sfn=%d, firstSlotMonitoring=%d, firstSymbMonitoring=%d' % (hsfn, sfn, firstSlotMonitoring, firstSymbMonitoring))
            qApp.processEvents()

            #refer to 3GPP 38.321 vf40 5.1.5
            #Once Msg3 is transmitted, the MAC entity shall:
            #1>	start the ra-ContentionResolutionTimer and restart the ra-ContentionResolutionTimer at each HARQ retransmission in the first symbol after the end of the Msg3 transmission;
            raContResStart = ((1024 * hsfn + sfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + firstSlotMonitoring) * self.nrSymbPerSlotNormCp + firstSymbMonitoring
            raContResEnd = ((1024 * hsfn + sfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + firstSlotMonitoring + self.nrRachContResTimer * self.nrSlotPerSubf[self.nrScs2Mu[self.nrMibCommonScs]]) * self.nrSymbPerSlotNormCp + firstSymbMonitoring - self.nrCoreset0NumSymbs

            css0Msg4 = []
            raContResTimerExpired = False
            while not raContResTimerExpired:
                ret = self.detCss0(hsfn, sfn)
                if not ret:
                    if self.ngwin.enableDebug:
                        self.ngwin.logEdit.append('<font color=red>detCss0 failed, hsfn=%s,sfn=%s</font>' % (hsfn, sfn))
                        qApp.processEvents()

                else:
                    key1 = '%s_%s' % (hsfn, sfn)
                    for i in range(len(self.ssbFirstSymbInBaseScsTd[key1])):
                        if self.ssbFirstSymbInBaseScsTd[key1][i] is None:
                            #self.coreset0Occasions.append(None)
                            continue
                        key2 = '%s_%s' % (key1, i)
                        oc, firstSymb, valid = self.coreset0Occasions[key2]
                        for j in range(len(valid)):
                            if valid[j] == 'NOK':
                                continue
                            ocHsfn, ocSfn, ocSlot = oc[j]
                            symbInd = ((1024 * ocHsfn + ocSfn) * self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] + ocSlot) * self.nrSymbPerSlotNormCp + firstSymb
                            if symbInd >= raContResStart and symbInd < raContResEnd and [ocHsfn, ocSfn, ocSlot, firstSymb] not in css0Msg4:
                                numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
                                for k in range(numCandidates):
                                    cand = [ocHsfn, ocSfn, ocSlot, firstSymb, k]
                                    if cand not in self.reservedPdcchSib1.values() and cand not in css0Msg4:
                                        css0Msg4.append(cand)

                            if symbInd > raContResEnd:
                                raContResTimerExpired = True
                                break

                hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                #self.recvSsb(hsfn, sfn)
                self.alwaysOnTr(hsfn, sfn)

            if len(css0Msg4) == 0:
                self.ngwin.logEdit.append('<font color=red>Error: css0Msg4 is empty when ra-ContentionResolutionTimer(=%s subframes) expired!</font>' % self.nrRachContResTimer)
                qApp.processEvents()
                self.error = True
                return (None, None, None)

            self.ngwin.logEdit.append('contents of valid css0Msg4(raContResTimer=%d subframes):' % self.nrRachContResTimer)
            for i in range(len(css0Msg4)):
                self.ngwin.logEdit.append('PDCCH occasion #%d: %s' % (i, css0Msg4[i]))
            qApp.processEvents()

            #remove 'not-used' HSFN+SFN from gridNrTdd/gridNrFddUl/gridNrFddDl
            validHsfnSfn = []
            validHsfnSfn.append([oldHsfn, oldSfn])
            for i in range(len(css0Msg4)):
                _hsfn, _sfn, _slot, _symb, _cand = css0Msg4[i]
                if [_hsfn, _sfn] not in validHsfnSfn:
                    validHsfnSfn.append([_hsfn, _sfn])

            if self.nrDuplexMode == 'TDD':
                keys = list(self.gridNrTdd.keys())
                for key in keys:
                    _hsfn, _sfn = [int(k) for k in key.split('_')]
                    if (_hsfn > oldHsfn or (_hsfn == oldHsfn and _sfn >= oldSfn)) and [_hsfn, _sfn] not in validHsfnSfn:
                        if self.ngwin.enableDebug:
                            self.ngwin.logEdit.append('unused [hsfn=%d,sfn=%d] removed' % (_hsfn, _sfn))
                            qApp.processEvents()
                        self.gridNrTdd.pop('%s_%s' % (_hsfn, _sfn))
            else:
                keys = list(self.gridNrFddDl.keys())
                for key in keys:
                    _hsfn, _sfn = [int(k) for k in key.split('_')]
                    if (_hsfn > oldHsfn or (_hsfn == oldHsfn and _sfn >= oldSfn)) and [_hsfn, _sfn] not in validHsfnSfn:
                        if self.ngwin.enableDebug:
                            self.ngwin.logEdit.append('unused [hsfn=%d,sfn=%d] removed' % (_hsfn, _sfn))
                            qApp.processEvents()
                        self.gridNrFddUl.pop('%s_%s' % (_hsfn, _sfn))
                        self.gridNrFddDl.pop('%s_%s' % (_hsfn, _sfn))

            #randomly select from css0Msg4 the pdcch occasion for msg4 scheduling
            pdcchOccasion = np.random.randint(0, len(css0Msg4)) if self.nrAdvMsg4PdcchOccasion is None else self.nrAdvMsg4PdcchOccasion
            hsfn, sfn, slot, firstSymb, pdcchCandidate = css0Msg4[pdcchOccasion]

            #numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
            #pdcchCandidate = np.random.randint(0, numCandidates) if self.nrAdvMsg4PdcchCand is None else self.nrAdvMsg4PdcchCand

            self.ngwin.logEdit.append('<font color=purple>Select PDCCH scheduling Msg4: [%s]</font>' % css0Msg4[pdcchOccasion])
            qApp.processEvents()

            scaleTd = self.baseScsTd // self.nrMibCommonScs
            scaleFd = self.nrMibCommonScs // self.baseScsFd
            dn2 = '%s_%s' % (hsfn, sfn)
            firstSymbInBaseScsTd = (slot * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
            cceSet = [pdcchCandidate * self.nrCss0AggLevel + k for k in range(self.nrCss0AggLevel)]
            self.msg4Cce0 = cceSet[0]
            self.ngwin.logEdit.append('cceSet=%s, msg4Cce0=%d' % (cceSet, self.msg4Cce0))
            qApp.processEvents()
            for i in range(self.coreset0Cces.shape[0]):
                for j in range(self.coreset0Cces.shape[1]):
                    if self.coreset0Cces[i, j] in cceSet:
                        if self.nrDuplexMode == 'TDD':
                            self.gridNrTdd[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                            self.gridNrTdd[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value
                        else:
                            self.gridNrFddDl[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                            self.gridNrFddDl[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value

            return (hsfn, sfn, slot)
        else:
            return (hsfn, sfn, slot)


    def detCss0(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside detCss0(hsfn=%d, sfn=%d)' % (hsfn, sfn))
        qApp.processEvents()

        oldHsfn, oldSfn = hsfn, sfn
        #self.coreset0Occasions = []
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
                qApp.processEvents()
                self.error = True
                return False
            else:
                O2, numSetsPerSlot, M2, firstSymbSet = css0OccasionsPat1Fr1[self.nrRmsiCss0] if self.nrFreqRange == 'FR1' else css0OccasionsPat1Fr2[self.nrRmsiCss0]

            dn = '%s_%s' % (hsfn, sfn)
            if not dn in self.ssbFirstSymbInBaseScsTd:
                return False

            for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                    #self.coreset0Occasions.append(None)
                    continue

                key = '%s_%s' % (dn, i)
                if key in self.coreset0Occasions:
                    return True

                issb = i % self.nrSsbMaxL
                #determine pdcch monitoring occasion (sfnc + nc) for ssb with index issb
                val = (O2 * 2 ** self.nrScs2Mu[self.nrMibCommonScs]) // 2 + math.floor(issb * M2 / 2)
                valSfnc = math.floor(val / self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]])
                if (valSfnc % 2 == 0 and sfn % 2 == 0) or (valSfnc % 2 == 1 and sfn % 2 == 1):
                    sfnc = sfn
                else:
                    hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                    #self.recvSsb(hsfn, sfn)
                    self.alwaysOnTr(hsfn, sfn)
                    sfnc = sfn

                n0 = val % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                if n0 == self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]] - 1:
                    oc = [(hsfn, sfnc, n0)]
                    hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                    #self.recvSsb(hsfn, sfn)
                    self.alwaysOnTr(hsfn, sfn)
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

                #self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK', 'OK']])
                self.coreset0Occasions[key] = [oc, firstSymbCoreset0, ['OK', 'OK']]
        elif self.nrCoreset0MultiplexingPat == 2:
            dn = '%s_%s' % (hsfn, sfn)
            if not dn in self.ssbFirstSymbInBaseScsTd:
                return False

            for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                    #self.coreset0Occasions.append(None)
                    continue

                key = '%s_%s' % (dn, i)
                if key in self.coreset0Occasions:
                    return True

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
                    qApp.processEvents()
                    self.error = True
                    return False

                oc = [(hsfn, sfnc, i) for i in nc]
                #self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK']])
                self.coreset0Occasions[key] = [oc, firstSymbCoreset0, ['OK']]
        else:
            dn = '%s_%s' % (hsfn, sfn)
            if not dn in self.ssbFirstSymbInBaseScsTd:
                return False

            for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
                if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                    #self.coreset0Occasions.append(None)
                    continue

                key = '%s_%s' % (dn, i)
                if key in self.coreset0Occasions:
                    return True

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
                    qApp.processEvents()
                    self.error = True
                    return False

                oc = [(hsfn, sfnc, i) for i in nc]
                #self.coreset0Occasions.append([oc, firstSymbCoreset0, ['OK']])
                self.coreset0Occasions[key] = [oc, firstSymbCoreset0, ['OK']]

        #validate pdcch occasions
        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd
        #for i in range(len(self.coreset0Occasions)):
        #    if self.coreset0Occasions[i] is None:
        #        continue
        for i in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
            if self.ssbFirstSymbInBaseScsTd[dn][i] is None:
                #self.coreset0Occasions.append(None)
                continue

            key = '%s_%s' % (dn, i)
            oc, firstSymb, valid = self.coreset0Occasions[key]
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
                        qApp.processEvents()
                        self.error = True
                        return False

                #refer to 3GPP 38.213 vf30
                #11.1 Slot configuration
                '''
                For a set of symbols of a slot indicated to a UE by pdcch-ConfigSIB1 in MIB for a CORESET for Type0-PDCCH CSS set, the UE does not expect the set of symbols to be indicated as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated.
                '''
                if self.nrDuplexMode == 'TDD':
                    for k in coreset0SymbsInBaseScsTd:
                        if self.gridNrTdd[dn2][self.ssbFirstSc, k] in (NrResType.NR_RES_U.value, NrResType.NR_RES_F.value):
                            valid[j] = 'NOK'
                            break

                #set CORESET0 for each PDCCH occasions
                if valid[j] == 'OK':
                    for k in coreset0SymbsInBaseScsTd:
                        if self.nrDuplexMode == 'TDD':
                            for m in range(self.nrCoreset0NumRbs*self.nrScPerPrb*scaleFd):
                                #avoid overwriting 'CORESET0/PDCCH'
                                if self.gridNrTdd[dn2][self.coreset0FirstSc+m, k] == NrResType.NR_RES_D.value:
                                    self.gridNrTdd[dn2][self.coreset0FirstSc+m, k] = NrResType.NR_RES_CORESET0.value
                        else:
                            for m in range(self.nrCoreset0NumRbs*self.nrScPerPrb*scaleFd):
                                #avoid overwriting 'CORESET0/PDCCH'
                                if self.gridNrFddDl[dn2][self.coreset0FirstSc+m, k] == NrResType.NR_RES_D.value:
                                    self.gridNrFddDl[dn2][self.coreset0FirstSc+m, k] = NrResType.NR_RES_CORESET0.value

            self.coreset0Occasions[key][2] = valid
            if (len(valid) == 1 and valid[0] == 'NOK') or (len(valid) == 2 and valid[0] == 'NOK' and valid[1] == 'NOK'):
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid PDCCH occasion: i=%d(issb=%d,hrf=%d), occasion=%s.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), i, i % self.nrSsbMaxL, self.nrMibHrf if self.nrSsbPeriod >= 10 else i // self.nrSsbMaxL, self.coreset0Occasions[key]))
                qApp.processEvents()
                self.error = True
                return False

            self.ngwin.logEdit.append('[Type-0 CSS]PDCCH monitoring occasion for SSB [%s](hrf=%d, issb=%d): %s' % (key, self.nrMibHrf if self.nrSsbPeriod >= 10 else i // self.nrSsbMaxL, i % self.nrSsbMaxL, self.coreset0Occasions[key]))
            qApp.processEvents()

        return True

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
        qApp.processEvents()

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
        qApp.processEvents()

        return (regBundles, cces)

    def recvSib1(self, hsfn, sfn):
        if self.error:
            return (None, None, None)

        self.ngwin.logEdit.append('contents of reservedSib1(key=[hsfn,sfn,issb],val=[hsfn,sfn,slotSib1]):')
        for key,val in self.reservedSib1.items():
            self.ngwin.logEdit.append('key=%s,val=%s' % (key, val))
            qApp.processEvents()

        dn = '%s_%s' % (hsfn, sfn)
        if self.nrAdvBestSsb is None:
            if self.ngwin.enableDebug:
                self.ngwin.logEdit.append('<font color=blue>WARNING: first while True for SSB selection, which may hang up!</font>')
                qApp.processEvents()
            while True:
                bestSsb = np.random.randint(0, len(self.ssbFirstSymbInBaseScsTd[dn]))
                if self.ssbFirstSymbInBaseScsTd[dn][bestSsb] is not None:
                    break
        else:
            bestSsb = self.nrAdvBestSsb

        #save bestSsb index for later ssb-prach mapping
        issb = bestSsb % self.nrSsbMaxL
        hrf = self.nrMibHrf if self.nrSsbPeriod >= 10 else bestSsb // self.nrSsbMaxL
        self.bestSsbInd = issb
        self.ngwin.logEdit.append('<font color=purple>bestSsb=%d(hrf=%d,issb=%d)</font>' % (bestSsb, hrf, issb))
        qApp.processEvents()

        key = '%s_%s_%s' % (hsfn, sfn, bestSsb)
        if key in self.reservedSib1:
            return self.reservedSib1[key]
        else:
            return (None, None, None)

    def dci10CssVrb2PrbMapping(self, coreset0Size=48, iniDlBwpStart=0, coreset0Start=0, L=2):
        #FIXME The UE is not expected to be configured with Li=2 simultaneously with a PRG size of 4 as defined in [6, TS 38.214].

        self.ngwin.logEdit.append('calling dci10CssVrb2PrbMapping: coreset0Size=%d,iniDlBwpStart=%d,coreset0Start=%d,L=%d' % (coreset0Size, iniDlBwpStart, coreset0Start, L))
        qApp.processEvents()

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
        qApp.processEvents()

        return prbs

    def sendMsg1(self, hsfn, sfn, slot):
        if self.error:
            return (None, None, None)

        self.ngwin.logEdit.append('---->inside sendMsg1(hsfn=%s,sfn=%s,slot=%s)' % (hsfn, sfn, slot))
        qApp.processEvents()

        #rachSsbMapStartSfn = sfn if sfn % self.prachAssociationPeriod == 0 else self.prachAssociationPeriod * math.floor(sfn / self.prachAssociationPeriod)
        rachSsbMapStartSfn = sfn if sfn % 16 == 0 else 16 * math.floor(sfn / 16)
        if rachSsbMapStartSfn >= 1024:
            rachSsbMapStartSfn = rachSsbMapStartSfn % 1024
            curHsfn = hsfn + 1
        else:
            curHsfn = hsfn

        #find all valid PRACH occasions within a PRACH association period which is at most 160ms
        validPrachOccasionsPerAssociationPeriod = []
        invalidPrachOccasionsPerAssociationPeriod = []
        isfn = 0
        while isfn < 16 and len(validPrachOccasionsPerAssociationPeriod) < self.minNumValidPrachOccasionPerAssociationPeriod:
            curSfn = rachSsbMapStartSfn + isfn
            if curSfn < sfn:
                isfn = isfn + 1
                continue

            if curSfn % self.nrRachCfgPeriodx in self.nrRachCfgOffsety:
                raSlots = []
                if self.nrRachScs in ('30', '120'):
                    if self.nrRachCfgNumSlotsPerSubfFr1Per60KSlotFR2 == 1:
                        for m in self.nrRachCfgSubfNumFr1SlotNumFr2:
                            raSlots.append(2*m+1)
                    else:
                        for m in self.nrRachCfgSubfNumFr1SlotNumFr2:
                            raSlots.extend([2*m, 2*m+1])
                else:
                    raSlots.extend(self.nrRachCfgSubfNumFr1SlotNumFr2)

                #'slot' from args are based on commonScs, while PRACH slot based on prachScs
                if curSfn == sfn:
                    if self.prachScs > self.nrMibCommonScs:
                        scaleTd = self.prachScs // self.nrMibCommonScs
                        firstSlotAfterSib1 = (slot + 1) * scaleTd
                    else:
                        scaleTd = self.nrMibCommonScs // self.prachScs
                        firstSlotAfterSib1 = slot // scaleTd + 1

                    while True:
                        if len(raSlots) > 0 and raSlots[0] < firstSlotAfterSib1:
                            raSlots.pop(0)
                        else:
                            break

                #init current frame for TDD
                if self.nrDuplexMode == 'TDD':
                    tdGrid = np.full(self.nrSymbPerRfNormCp, 'F')
                    scaleTd = self.baseScsTd // self.nrTddCfgRefScs
                    if curSfn % 2 == 0:
                        for i in range(len(self.tddPatEvenRf)):
                            for j in range(scaleTd):
                                tdGrid[i*scaleTd+j] = self.tddPatEvenRf[i]
                    else:
                        for i in range(len(self.tddPatOddRf)):
                            for j in range(scaleTd):
                                tdGrid[i*scaleTd+j] = self.tddPatOddRf[i]

                    #init ssb in current frame
                    if self.nrSsbPeriod >= 10 and self.deltaSfn(self.hsfn, self.nrMibSfn, curHsfn, curSfn) % (self.nrSsbPeriod // 10) != 0:
                        pass
                    else:
                        ssbHrfSet = [0, 1] if self.nrSsbPeriod < 10 else [self.nrMibHrf]
                        for hrf in ssbHrfSet:
                            for issb in range(self.nrSsbMaxL):
                                if self.ssbSet[issb] == '0':
                                    continue
                                scaleTd = self.baseScsTd // self.nrSsbScs
                                ssbFirstSymb = hrf * (self.nrSymbPerRfNormCp // 2) + self.ssbFirstSymbSet[issb] * scaleTd
                                for k in range(4*scaleTd):
                                    tdGrid[ssbFirstSymb+k] = 'SSB'

                    #init sib1 if any
                    if curHsfn == hsfn and curSfn == sfn:
                        scaleTd = self.baseScsTd // self.nrMibCommonScs
                        firstSymbSib1InBaseScsTd = (slot * self.nrSymbPerSlotNormCp + self.nrSib1TdStartSymb) * scaleTd
                        for k in range(self.nrSib1TdNumSymbs*scaleTd):
                            tdGrid[firstSymbSib1InBaseScsTd+k] = 'SIB1'

                #refer to 3GPP 38.213 vf40 8.1
                #For paired spectrum all PRACH occasions are valid.
                #If a UE is provided TDD-UL-DL-ConfigurationCommon, a PRACH occasion in a PRACH slot is valid if
                #-	it is within UL symbols, or
                #-	it does not precede a SS/PBCH block in the PRACH slot and starts at least N_gap symbols after a last downlink symbol and at least N_gap symbols after a last SS/PBCH block transmission symbol, where N_gap is provided in Table 8.1-2.
                for s in raSlots:
                    for t in range(self.nrRachCfgNumOccasionsPerSlot):
                        if self.nrDuplexMode == 'FDD':
                            for f in range(self.nrRachMsg1Fdm):
                                validPrachOccasionsPerAssociationPeriod.append([[curHsfn, curSfn, s], t, f])
                        else:
                            scaleTd = self.baseScsTd // self.prachScs
                            rachFirstSymbInBaseScsTd = (s * self.nrSymbPerSlotNormCp + self.nrRachCfgStartSymb + t * self.nrRachCfgDuration) * scaleTd
                            rachSymbsInbaseScsTd = [rachFirstSymbInBaseScsTd+k for k in range(self.nrRachCfgDuration*scaleTd)]

                            nGapInBaseScsTd = 0 if self.nrRachScs in ('1.25', '5') or self.nrRachCfgFormat == 'B4' else 2*(self.baseScsTd//self.prachScs)

                            valid = True
                            for k in rachSymbsInbaseScsTd:
                                if tdGrid[k] != 'U':
                                    valid = False
                                    break

                            for k in range(rachFirstSymbInBaseScsTd, (s+1)*self.nrSymbPerSlotNormCp):
                                if tdGrid[k] == 'SSB':
                                    valid = False
                                    break

                            for k in range(max(0, rachFirstSymbInBaseScsTd - nGapInBaseScsTd), rachFirstSymbInBaseScsTd):
                                if tdGrid[k] in ('SSB', 'SIB1'):
                                    valid = False
                                    break

                            if valid:
                                for f in range(self.nrRachMsg1Fdm):
                                    validPrachOccasionsPerAssociationPeriod.append([[curHsfn, curSfn, s], t, f])
                            else:
                                for f in range(self.nrRachMsg1Fdm):
                                    invalidPrachOccasionsPerAssociationPeriod.append([[curHsfn, curSfn, s], t, f])

            isfn = isfn + 1

        self.ngwin.logEdit.append('contents of validPrachOccasionsPerAssociationPeriod(size=%d,minSize=%d):' % (len(validPrachOccasionsPerAssociationPeriod), self.minNumValidPrachOccasionPerAssociationPeriod))
        self.ngwin.logEdit.append(','.join([str(occ) for occ in validPrachOccasionsPerAssociationPeriod]))

        self.ngwin.logEdit.append('contents of invalidPrachOccasionsPerAssociationPeriod(size=%d):' % len(invalidPrachOccasionsPerAssociationPeriod))
        self.ngwin.logEdit.append(','.join([str(occ) for occ in invalidPrachOccasionsPerAssociationPeriod]))
        qApp.processEvents()

        if isfn >= 16 and len(validPrachOccasionsPerAssociationPeriod) < self.minNumValidPrachOccasionPerAssociationPeriod:
            self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: Invalid PRACH configuration(numTxSsb=%d,ssbPerOccasionM8=%d,x=%d,y=%s,subfFr1SlotFr2=%s,#prachSlots=%d,#prachOccasion=%d,msg1Fdm=%d): PRACH association period is at most 160ms!' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), self.numTxSsb, self.nrRachSsbPerRachOccasionM8,  self.nrRachCfgPeriodx, self.nrRachCfgOffsety, self.nrRachCfgSubfNumFr1SlotNumFr2, self.nrRachCfgNumSlotsPerSubfFr1Per60KSlotFR2, self.nrRachCfgNumOccasionsPerSlot, self.nrRachMsg1Fdm))
            qApp.processEvents()
            self.error = True
            return (None, None, None)

        #SSB and PRACH occasion mapping
        ssb2RachOccasionMap = dict()
        if self.nrRachSsbPerRachOccasionM8 < 8:
            numRachOccasionPerSsb = 8 // self.nrRachSsbPerRachOccasionM8
            count = 0
            for issb in range(len(self.ssbSet)):
                if self.ssbSet[issb] == '1':
                    rachOccasions = [validPrachOccasionsPerAssociationPeriod[numRachOccasionPerSsb*count+k] for k in range(numRachOccasionPerSsb)]
                    cbPreambs = list(range(0, self.nrRachCbPreambsPerSsb))
                    ssb2RachOccasionMap[issb] = [rachOccasions, cbPreambs]
                    count = count + 1
        else:
            numSsbPerRachOccasion = self.nrRachSsbPerRachOccasionM8 // 8
            availCbPreambsPerSsb = self.nrRachTotNumPreambs // numSsbPerRachOccasion
            count = 0
            for issb in range(len(self.ssbSet)):
                if self.ssbSet[issb] == '1':
                    rachOccasions = [validPrachOccasionsPerAssociationPeriod[count // numSsbPerRachOccasion]]
                    cbPreambs = [availCbPreambsPerSsb*(count%numSsbPerRachOccasion)+k for k in range(self.nrRachCbPreambsPerSsb)]
                    ssb2RachOccasionMap[issb] = [rachOccasions, cbPreambs]
                    count = count + 1

        self.ngwin.logEdit.append('contents of ssb2RachOccasionMap:')
        for key,val in ssb2RachOccasionMap.items():
            self.ngwin.logEdit.append('issb=%d: rachOccasion=%s, cbPreambs=%s' % (key, val[0], val[1]))
        qApp.processEvents()

        #assume valid prach occasion is randomly selected
        bestSsbRachOccasion = ssb2RachOccasionMap[self.bestSsbInd][0][np.random.randint(0, len(ssb2RachOccasionMap[self.bestSsbInd][0])) if self.nrAdvPrachOccasion is None else self.nrAdvPrachOccasion]
        self.ngwin.logEdit.append('<font color=purple>selecting prach occasion(=%s) with cbPreambs=%s corresponding to best SSB(with issb=%d)</font>' % (bestSsbRachOccasion, ssb2RachOccasionMap[self.bestSsbInd][1], self.bestSsbInd))
        qApp.processEvents()

        #PRACH time/freq domain RE mapping
        msg1Hsfn, msg1Sfn, msg1Slot = bestSsbRachOccasion[0]
        msg1OccasionInd = bestSsbRachOccasion[1]
        msg1FdmInd = bestSsbRachOccasion[2]

        dn = '%s_%s' % (msg1Hsfn, msg1Sfn)
        if (self.nrDuplexMode == 'TDD' and not dn in self.gridNrTdd) or (self.nrDuplexMode == 'FDD' and not dn in self.gridNrFddUl):
            #self.recvSsb(msg1Hsfn, msg1Sfn)
            self.alwaysOnTr(msg1Hsfn, msg1Sfn)

        scaleTd = self.baseScsTd // self.prachScs
        #last symbol of PRACH occasion, starting from msg1Slot
        self.msg1LastSymb = self.nrRachCfgStartSymb + msg1OccasionInd * self.nrRachCfgDuration + self.nrRachCfgDuration - 1
        msg1FirstSymbInBaseScsTd = (msg1Slot * self.nrSymbPerSlotNormCp + self.nrRachCfgStartSymb + msg1OccasionInd * self.nrRachCfgDuration) * scaleTd
        msg1SymbsInBaseScsTd = [msg1FirstSymbInBaseScsTd+k for k in range(self.nrRachCfgDuration*scaleTd)]

        #determine freq-domain
        scaleFd = self.nrIniUlBwpScs // self.baseScsFd
        msg1FirstScInBaseScsFd = self.nrCarrierMinGuardBand * self.nrScPerPrb * (self.nrCarrierScs // self.baseScsFd) + self.nrIniUlBwpStartRb * self.nrScPerPrb * scaleFd + (self.nrRachMsg1FreqStart + msg1FdmInd * self.nrRachNumRbs) * self.nrScPerPrb * scaleFd
        msg1ScsInBaseScsFd = [msg1FirstScInBaseScsFd+k for k in range(self.nrRachNumRbs*self.nrScPerPrb*scaleFd)]

        if self.nrDuplexMode == 'TDD':
            for fd in msg1ScsInBaseScsFd:
                for td in msg1SymbsInBaseScsTd:
                    self.gridNrTdd[dn][fd, td] = NrResType.NR_RES_PRACH.value
        else:
            for fd in msg1ScsInBaseScsFd:
                for td in msg1SymbsInBaseScsTd:
                    self.gridNrFddUl[dn][fd, td] = NrResType.NR_RES_PRACH.value

        #refer to 3GPP 38.321 5.1.3
        #RA-RNTI= 1 + s_id + 14*t_id + 14*80*f_id + 14*80*8*ul_carrier_id
        #where s_id is the index of the first OFDM symbol of the PRACH occasion (0 ≤ s_id < 14), t_id is the index of the first slot of the PRACH occasion in a system frame (0 ≤ t_id < 80), f_id is the index of the PRACH occasion in the frequency domain (0 ≤ f_id < 8), and ul_carrier_id is the UL carrier used for Random Access Preamble transmission (0 for NUL carrier, and 1 for SUL carrier).
        self.raRnti = 1 + (self.nrRachCfgStartSymb + msg1OccasionInd * self.nrRachCfgDuration) + 14 * msg1Slot + 14 * 80 * msg1FdmInd
        self.ngwin.logEdit.append('Associated RA-RNTI = 0x{:04X}'.format(self.raRnti))
        qApp.processEvents()

        return (msg1Hsfn, msg1Sfn, msg1Slot)
        #return (hsfn, sfn, slot)

    def recvMsg2(self, hsfn, sfn, slot):
        if self.error:
            return (None, None, None)

        self.ngwin.logEdit.append('---->inside recvMsg2(hsfn=%d,sfn=%d,dci slot=%d)' % (hsfn, sfn, slot))
        qApp.processEvents()

        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd

        slotMsg2 = math.floor(slot * 2 ** (self.nrMsg2MuPdsch - self.nrMsg2MuPdcch)) + self.nrMsg2TdK0
        self.msg2LastSymb = self.nrMsg2TdStartSymb + self.nrMsg2TdNumSymbs - 1
        firstSymbMsg2InBaseScsTd = (slotMsg2 * self.nrSymbPerSlotNormCp + self.nrMsg2TdStartSymb) * scaleTd
        msg2SymbsInBaseScsTd = [firstSymbMsg2InBaseScsTd+k for k in range(self.nrMsg2TdNumSymbs*scaleTd)]

        msg2DmrsSymbs = []
        for i in self.nrMsg2DmrsTdL:
            if self.nrMsg2TdMappingType == 'Type A':
                #for PDSCH mapping type A, tdL is defined relative to the start of the slot
                msg2DmrsSymbs.append(i - self.nrMsg2TdStartSymb)
            else:
                #for PDSCH mapping type B, tdL is defined relative to the start of the scheduled PDSCH resources
                msg2DmrsSymbs.append(i)
        self.ngwin.logEdit.append('contents of msg2DmrsSymbs(w.r.t to slivS): %s' % msg2DmrsSymbs)
        qApp.processEvents()

        if self.nrMsg2FdVrbPrbMappingType == 'nonInterleaved':
            firstScMsg2InBaseScsFd = self.coreset0FirstSc + self.nrMsg2FdStartRb * self.nrScPerPrb * scaleFd
            msg2ScsInBaseScsFd = [firstScMsg2InBaseScsFd+k for k in range(self.nrMsg2FdNumRbs*self.nrScPerPrb*scaleFd)]
        else:
            msg2ScsInBaseScsFd = []
            for k in range(self.nrMsg2FdNumRbs):
                vrb = self.nrMsg2FdStartRb + k
                prb = self.dci10CssPrbs[vrb]
                msg2ScsInBaseScsFd.extend([self.coreset0FirstSc+prb*self.nrScPerPrb*scaleFd+k for k in range(self.nrScPerPrb*scaleFd)])

        #validate Msg2 time-frequency allocation
        dn = '%s_%s' % (hsfn, sfn)
        if dn in self.ssbFirstSymbInBaseScsTd:
            #refer to 3GPP 38.314 vf40
            #5.1.4	PDSCH resource mapping
            '''
            When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 1, RA-RNTI, P-RNTI or TC-RNTI, the UE assumes SS/PBCH block transmission according to ssb-PositionsInBurst, and if the PDSCH resource allocation overlaps with PRBs containing SS/PBCH block transmission resources the UE shall assume that the PRBs containing SS/PBCH block transmission resources are not available for PDSCH in the OFDM symbols where SS/PBCH block is transmitted.
            '''
            tdOverlapped = self.ssbSymbsInBaseScsTd[dn].intersection(set(msg2SymbsInBaseScsTd))
            fdOverlapped = self.ssbScsInBaseScsFd.intersection(set(msg2ScsInBaseScsFd))
            if len(tdOverlapped) > 0 and len(fdOverlapped) > 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 1, RA-RNTI, P-RNTI or TC-RNTI, the UE assumes SS/PBCH block transmission according to ssb-PositionsInBurst, and if the PDSCH resource allocation overlaps with PRBs containing SS/PBCH block transmission resources the UE shall assume that the PRBs containing SS/PBCH block transmission resources are not available for PDSCH in the OFDM symbols where SS/PBCH block is transmitted.\ntdOverlapped=%s\nfdOverlapped=%s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), tdOverlapped, fdOverlapped))
                qApp.processEvents()
                self.error = True
                return (None, None, None)

        #refer to 3GPP 38.213 vf40 11.1
        #For a set of symbols of a slot that are indicated to a UE as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not receive PDCCH, PDSCH, or CSI-RS in the set of symbols of the slot.
        if self.nrDuplexMode == 'TDD':
            invalidSymbs = []
            for symb in msg2SymbsInBaseScsTd:
                if self.gridNrTdd[dn][msg2ScsInBaseScsFd[0], symb] in (NrResType.NR_RES_U.value, NrResType.NR_RES_F.value):
                    invalidSymbs.append(symb)

            if len(invalidSymbs) > 0:
                self.ngwin.logEdit.append('<font color=red>Error: UE does not receive PDSCH, PDCCH, or CSI-RS in symbols which are indicated as uplink or flexible!</font>')
                self.ngwin.logEdit.append('contents of invalidSymbs(scaleTd=%d,firstSymb=%d): %s' % (scaleTd, firstSymbMsg2InBaseScsTd, invalidSymbs))
                qApp.processEvents()
                self.error = True
                return False

        for i in range(self.nrMsg2TdNumSymbs):
            if self.nrDuplexMode == 'TDD':
                self.gridNrTdd[dn][msg2ScsInBaseScsFd, firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG2.value
                if i in msg2DmrsSymbs:
                    for j in range(self.nrMsg2FdNumRbs):
                        for k in range(self.nrScPerPrb):
                            if self.nrMsg2DmrsFdK[k] == 1:
                                self.gridNrTdd[dn][msg2ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG2.value
                            else:
                                if not (self.nrMsg2TdMappingType == 'Type B' and self.nrMsg2TdNumSymbs == 2):
                                    self.gridNrTdd[dn][msg2ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
            else:
                self.gridNrFddDl[dn][msg2ScsInBaseScsFd, firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG2.value
                if i in msg2DmrsSymbs:
                    for j in range(self.nrMsg2FdNumRbs):
                        for k in range(self.nrScPerPrb):
                            if self.nrMsg2DmrsFdK[k] == 1:
                                self.gridNrFddDl[dn][msg2ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG2.value
                            else:
                                if not (self.nrMsg2TdMappingType == 'Type B' and self.nrMsg2TdNumSymbs == 2):
                                    self.gridNrFddDl[dn][msg2ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg2InBaseScsTd+i*scaleTd:firstSymbMsg2InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value

        return (hsfn, sfn, slotMsg2)

    def sendMsg3(self, hsfn, sfn, slot):
        self.ngwin.logEdit.append('---->inside sendMsg3(hsfn=%s,sfn=%s,slot=%s)' % (hsfn, sfn, slot))

        #convert 'slot'+'msg2LastSymb' which based on commonScs into puschScs(initial ul bwp)
        tmpStr = 'converting from commonScs(=%dKHz) to puschScs(=%dKHz): [hsfn=%d, sfn=%d, slot=%d, msg2LastSymb=%d] --> ' % (self.nrMibCommonScs, self.nrIniUlBwpScs, hsfn, sfn,  slot, self.msg2LastSymb)
        scaleTd = self.nrIniUlBwpScs / self.nrMibCommonScs
        slotInPuschScs = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg2LastSymb + 1) * scaleTd - 1) // self.nrSymbPerSlotNormCp)
        tmpStr = tmpStr + '[hsfn=%d, sfn=%d, slot=%d]' % (hsfn, sfn, slotInPuschScs)
        self.ngwin.logEdit.append(tmpStr)
        qApp.processEvents()

        dn = '%s_%s' % (hsfn, sfn)

        scaleTd = self.baseScsTd // self.nrIniUlBwpScs
        scaleFd = self.nrIniUlBwpScs // self.baseScsFd

        slotMsg3 = slotInPuschScs + self.nrMsg3TdK2 + self.nrMsg3TdDelta
        self.msg3LastSymb = self.nrMsg3TdStartSymb + self.nrMsg3TdNumSymbs - 1
        self.ngwin.logEdit.append('<font color=purple>slotMsg3=%d with K2=%d and delta=%d</font>' % (slotMsg3, self.nrMsg3TdK2, self.nrMsg3TdDelta))
        qApp.processEvents()

        if self.nrMsg3FdFreqHop == 'enabled':
            #intra-slot frequency hopping
            numSymbsPerHop = [math.floor(self.nrMsg3TdNumSymbs / 2), self.nrMsg3TdNumSymbs - math.floor(self.nrMsg3TdNumSymbs / 2)]
            startRbPerHop = [self.nrMsg3FdStartRb, (self.nrMsg3FdStartRb + self.nrMsg3FdSecondHopFreqOff) % self.nrIniUlBwpNumRbs]
            self.ngwin.logEdit.append('intra-slot freq hop settings: 1st hop=[numSymbs=%d,startRb=%d], 2nd hop=[numSymbs=%d,startRb=%d]' % (numSymbsPerHop[0], startRbPerHop[0], numSymbsPerHop[1], startRbPerHop[1]))
            qApp.processEvents()

            for hop in range(2):
                msg3TdStartSymb = self.nrMsg3TdStartSymb + (0 if hop == 0 else numSymbsPerHop[0])
                firstSymbMsg3InBaseScsTd = (slotMsg3 * self.nrSymbPerSlotNormCp + msg3TdStartSymb) * scaleTd
                msg3SymbsInBaseScsTd = [firstSymbMsg3InBaseScsTd+k for k in range(numSymbsPerHop[hop]*scaleTd)]

                msg3DmrsSymbs = []
                for i in self.nrMsg3DmrsTdL[hop]:
                    #for both PUSCH mapping type A/B, tdL is defined relative to the start of each hop in case frequency hopping is enabled
                    msg3DmrsSymbs.append(i)
                self.ngwin.logEdit.append('contents of msg3DmrsSymbs(w.r.t to the start of hop%d): %s' % (hop, msg3DmrsSymbs))
                qApp.processEvents()

                firstScMsg3InBaseScsFd = self.nrCarrierMinGuardBand * self.nrScPerPrb * (self.nrCarrierScs // self.baseScsFd) + self.nrIniUlBwpStartRb * self.nrScPerPrb * scaleFd + startRbPerHop[hop] * self.nrScPerPrb * scaleFd
                msg3ScsInBaseScsFd = [firstScMsg3InBaseScsFd+k for k in range(self.nrMsg3FdNumRbs*self.nrScPerPrb*scaleFd)]

                #validate against tdd-ul-dl-config
                #refer to 3GPP 38.213 vf40 11.1
                #For a set of symbols of a slot that are indicated to a UE as downlink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not transmit PUSCH, PUCCH, PRACH, or SRS in the set of symbols of the slot.
                #For a set of symbols of a slot that are indicated to a UE as flexible by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not expect to receive both dedicated configuring transmission from the UE in the set of symbols of the slot and dedicated configuring reception by the UE in the set of symbols of the slot.
                if self.nrDuplexMode == 'TDD':
                    invalidSymbs = []
                    for symb in msg3SymbsInBaseScsTd:
                        if self.gridNrTdd[dn][firstScMsg3InBaseScsFd, symb] in (NrResType.NR_RES_D.value, NrResType.NR_RES_F.value):
                            invalidSymbs.append(symb)

                    if len(invalidSymbs) > 0:
                        self.ngwin.logEdit.append('<font color=red>Error: UE does not transmit PUSCH, PUCCH, PRACH or SRS in symbols which are indicated as downlink or flexible!</font>')
                        self.ngwin.logEdit.append('contents of invalidSymbs(hop=%d,scaleTd=%d,firstSymb=%d): %s' % (hop, scaleTd, firstSymbMsg3InBaseScsTd, invalidSymbs))
                        qApp.processEvents()
                        self.error = True
                        return (None, None, None)

                for i in range(numSymbsPerHop[hop]):
                    if self.nrDuplexMode == 'TDD':
                        self.gridNrTdd[dn][msg3ScsInBaseScsFd, firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG3.value
                        if i in msg3DmrsSymbs:
                            for j in range(self.nrMsg3FdNumRbs):
                                for k in range(self.nrScPerPrb):
                                    if self.nrMsg3DmrsFdK[k] == 1:
                                        self.gridNrTdd[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG3.value
                                    else:
                                        if not (self.nrRachMsg3Tp == 'disabled' and self.nrMsg3TdNumSymbs <= 2):
                                            self.gridNrTdd[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
                    else:
                        self.gridNrFddUl[dn][msg3ScsInBaseScsFd, firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG3.value
                        if i in msg3DmrsSymbs:
                            for j in range(self.nrMsg3FdNumRbs):
                                for k in range(self.nrScPerPrb):
                                    if self.nrMsg3DmrsFdK[k] == 1:
                                        self.gridNrFddUl[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG3.value
                                    else:
                                        if not (self.nrRachMsg3Tp == 'disabled' and self.nrMsg3TdNumSymbs <= 2):
                                            self.gridNrFddUl[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
        else:
            firstSymbMsg3InBaseScsTd = (slotMsg3 * self.nrSymbPerSlotNormCp + self.nrMsg3TdStartSymb) * scaleTd
            msg3SymbsInBaseScsTd = [firstSymbMsg3InBaseScsTd+k for k in range(self.nrMsg3TdNumSymbs*scaleTd)]

            msg3DmrsSymbs = []
            for i in self.nrMsg3DmrsTdL:
                if self.nrMsg3TdMappingType == 'Type A':
                    #for PUSCH mapping type A, tdL is defined relative to the start of the slot if frequency hopping is disabled
                    msg3DmrsSymbs.append(i - self.nrMsg3TdStartSymb)
                else:
                    #for PUSCH mapping type B, tdL is defined relative to the start of the scheduled PUSCH resources if frequency hopping is disabled
                    msg3DmrsSymbs.append(i)
            self.ngwin.logEdit.append('contents of msg3DmrsSymbs(w.r.t to slivS): %s' % msg3DmrsSymbs)
            qApp.processEvents()

            firstScMsg3InBaseScsFd = self.nrCarrierMinGuardBand * self.nrScPerPrb * (self.nrCarrierScs // self.baseScsFd) + self.nrMsg3FdStartRb * self.nrScPerPrb * scaleFd
            msg3ScsInBaseScsFd = [firstScMsg3InBaseScsFd+k for k in range(self.nrMsg3FdNumRbs*self.nrScPerPrb*scaleFd)]

            #validate against tdd-ul-dl-config
            #refer to 3GPP 38.213 vf40 11.1
            #For a set of symbols of a slot that are indicated to a UE as downlink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not transmit PUSCH, PUCCH, PRACH, or SRS in the set of symbols of the slot.
            #For a set of symbols of a slot that are indicated to a UE as flexible by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not expect to receive both dedicated configuring transmission from the UE in the set of symbols of the slot and dedicated configuring reception by the UE in the set of symbols of the slot.
            if self.nrDuplexMode == 'TDD':
                    invalidSymbs = []
                    for symb in msg3SymbsInBaseScsTd:
                        if self.gridNrTdd[dn][firstScMsg3InBaseScsFd, symb] in (NrResType.NR_RES_D.value, NrResType.NR_RES_F.value):
                            invalidSymbs.append(symb)

                    if len(invalidSymbs) > 0:
                        self.ngwin.logEdit.append('<font color=red>Error: UE does not transmit PUSCH, PUCCH, PRACH or SRS in symbols which are indicated as downlink or flexible!</font>')
                        self.ngwin.logEdit.append('contents of invalidSymbs(hop=%d,scaleTd=%d,firstSymb=%d): %s' % (hop, scaleTd, firstSymbMsg3InBaseScsTd, invalidSymbs))
                        qApp.processEvents()
                        self.error = True
                        return (None, None, None)

            for i in range(self.nrMsg3TdNumSymbs):
                if self.nrDuplexMode == 'TDD':
                    self.gridNrTdd[dn][msg3ScsInBaseScsFd, firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG3.value
                    if i in msg3DmrsSymbs:
                        for j in range(self.nrMsg3FdNumRbs):
                            for k in range(self.nrScPerPrb):
                                if self.nrMsg3DmrsFdK[k] == 1:
                                    self.gridNrTdd[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG3.value
                                else:
                                    if not (self.nrRachMsg3Tp == 'disabled' and self.nrMsg3TdNumSymbs <= 2):
                                        self.gridNrTdd[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
                else:
                    self.gridNrFddUl[dn][msg3ScsInBaseScsFd, firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG3.value
                    if i in msg3DmrsSymbs:
                        for j in range(self.nrMsg3FdNumRbs):
                            for k in range(self.nrScPerPrb):
                                if self.nrMsg3DmrsFdK[k] == 1:
                                    self.gridNrFddUl[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG3.value
                                else:
                                    if not (self.nrRachMsg3Tp == 'disabled' and self.nrMsg3TdNumSymbs <= 2):
                                        self.gridNrFddUl[dn][msg3ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg3InBaseScsTd+i*scaleTd:firstSymbMsg3InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value

        return (hsfn, sfn, slotMsg3)

    def recvMsg4(self, hsfn, sfn, slot):
        if self.error:
            return (None, None, None)

        self.ngwin.logEdit.append('---->inside recvMsg4(hsfn=%d,sfn=%d,dci slot=%d)' % (hsfn, sfn, slot))
        qApp.processEvents()

        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd

        slotMsg4 = math.floor(slot * 2 ** (self.nrMsg4MuPdsch - self.nrMsg4MuPdcch)) + self.nrMsg4TdK0
        self.msg4LastSymb = self.nrMsg4TdStartSymb + self.nrMsg4TdNumSymbs - 1
        firstSymbMsg4InBaseScsTd = (slotMsg4 * self.nrSymbPerSlotNormCp + self.nrMsg4TdStartSymb) * scaleTd
        msg4SymbsInBaseScsTd = [firstSymbMsg4InBaseScsTd+k for k in range(self.nrMsg4TdNumSymbs*scaleTd)]

        msg4DmrsSymbs = []
        for i in self.nrMsg4DmrsTdL:
            if self.nrMsg4TdMappingType == 'Type A':
                #for PDSCH mapping type A, tdL is defined relative to the start of the slot
                msg4DmrsSymbs.append(i - self.nrMsg4TdStartSymb)
            else:
                #for PDSCH mapping type B, tdL is defined relative to the start of the scheduled PDSCH resources
                msg4DmrsSymbs.append(i)
        self.ngwin.logEdit.append('contents of msg4DmrsSymbs(w.r.t to slivS): %s' % msg4DmrsSymbs)
        qApp.processEvents()

        if self.nrMsg4FdVrbPrbMappingType == 'nonInterleaved':
            firstScMsg4InBaseScsFd = self.coreset0FirstSc + self.nrMsg4FdStartRb * self.nrScPerPrb * scaleFd
            msg4ScsInBaseScsFd = [firstScMsg4InBaseScsFd+k for k in range(self.nrMsg4FdNumRbs*self.nrScPerPrb*scaleFd)]
        else:
            msg4ScsInBaseScsFd = []
            for k in range(self.nrMsg4FdNumRbs):
                vrb = self.nrMsg4FdStartRb + k
                prb = self.dci10CssPrbs[vrb]
                msg4ScsInBaseScsFd.extend([self.coreset0FirstSc+prb*self.nrScPerPrb*scaleFd+k for k in range(self.nrScPerPrb*scaleFd)])

        #validate Msg4 time-frequency allocation
        dn = '%s_%s' % (hsfn, sfn)
        if dn in self.ssbFirstSymbInBaseScsTd:
            #refer to 3GPP 38.314 vf40
            #5.1.4	PDSCH resource mapping
            '''
            When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 1, RA-RNTI, P-RNTI or TC-RNTI, the UE assumes SS/PBCH block transmission according to ssb-PositionsInBurst, and if the PDSCH resource allocation overlaps with PRBs containing SS/PBCH block transmission resources the UE shall assume that the PRBs containing SS/PBCH block transmission resources are not available for PDSCH in the OFDM symbols where SS/PBCH block is transmitted.
            '''
            tdOverlapped = self.ssbSymbsInBaseScsTd[dn].intersection(set(msg4SymbsInBaseScsTd))
            fdOverlapped = self.ssbScsInBaseScsFd.intersection(set(msg4ScsInBaseScsFd))
            if len(tdOverlapped) > 0 and len(fdOverlapped) > 0:
                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 1, RA-RNTI, P-RNTI or TC-RNTI, the UE assumes SS/PBCH block transmission according to ssb-PositionsInBurst, and if the PDSCH resource allocation overlaps with PRBs containing SS/PBCH block transmission resources the UE shall assume that the PRBs containing SS/PBCH block transmission resources are not available for PDSCH in the OFDM symbols where SS/PBCH block is transmitted.\ntdOverlapped=%s\nfdOverlapped=%s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), tdOverlapped, fdOverlapped))
                qApp.processEvents()
                self.error = True
                return (None, None, None)

        #refer to 3GPP 38.213 vf40 11.1
        #For a set of symbols of a slot that are indicated to a UE as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not receive PDCCH, PDSCH, or CSI-RS in the set of symbols of the slot.
        if self.nrDuplexMode == 'TDD':
            invalidSymbs = []
            for symb in msg4SymbsInBaseScsTd:
                if self.gridNrTdd[dn][msg4ScsInBaseScsFd[0], symb] in (NrResType.NR_RES_U.value, NrResType.NR_RES_F.value):
                    invalidSymbs.append(symb)

            if len(invalidSymbs) > 0:
                self.ngwin.logEdit.append('<font color=red>Error: UE does not receive PDSCH, PDCCH, or CSI-RS in symbols which are indicated as uplink or flexible!</font>')
                self.ngwin.logEdit.append('contents of invalidSymbs(scaleTd=%d,firstSymb=%d): %s' % (scaleTd, firstSymbMsg4InBaseScsTd, invalidSymbs))
                qApp.processEvents()
                self.error = True
                return False

        for i in range(self.nrMsg4TdNumSymbs):
            if self.nrDuplexMode == 'TDD':
                self.gridNrTdd[dn][msg4ScsInBaseScsFd, firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG4.value
                if i in msg4DmrsSymbs:
                    for j in range(self.nrMsg4FdNumRbs):
                        for k in range(self.nrScPerPrb):
                            if self.nrMsg4DmrsFdK[k] == 1:
                                self.gridNrTdd[dn][msg4ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG4.value
                            else:
                                if not (self.nrMsg4TdMappingType == 'Type B' and self.nrMsg4TdNumSymbs == 2):
                                    self.gridNrTdd[dn][msg4ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
            else:
                self.gridNrFddDl[dn][msg4ScsInBaseScsFd, firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_MSG4.value
                if i in msg4DmrsSymbs:
                    for j in range(self.nrMsg4FdNumRbs):
                        for k in range(self.nrScPerPrb):
                            if self.nrMsg4DmrsFdK[k] == 1:
                                self.gridNrFddDl[dn][msg4ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_MSG4.value
                            else:
                                if not (self.nrMsg4TdMappingType == 'Type B' and self.nrMsg4TdNumSymbs == 2):
                                    self.gridNrFddDl[dn][msg4ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbMsg4InBaseScsTd+i*scaleTd:firstSymbMsg4InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value

        self.msg4Recved = True
        return (hsfn, sfn, slotMsg4)

    def sendPucch(self, hsfn, sfn, slot, harq=True, sr=False, csi=False, pucchResSet='common'):
        self.ngwin.logEdit.append('---->inside sendPucch(hsfn=%s,sfn=%s,slot=%s,harq=%s,sr=%s,csi=%s,pucchResSet="%s")' % (hsfn, sfn, slot, harq, sr, csi, pucchResSet))

        if pucchResSet == 'common':
            if not (harq and not sr and not csi):
                self.error = True
                return (None, None, None)

            #convert 'slot'+'msg4LastSymb' which based on commonScs into puschScs(initial ul bwp)
            tmpStr = 'converting from commonScs(=%dKHz) to puschScs(=%dKHz): [hsfn=%d, sfn=%d, slot=%d, msg4LastSymb=%d] --> ' % (self.nrMibCommonScs, self.nrIniUlBwpScs, hsfn, sfn,  slot, self.msg4LastSymb)
            scaleTd = self.nrIniUlBwpScs / self.nrMibCommonScs
            slotInPuschScs = math.ceil(((slot * self.nrSymbPerSlotNormCp + self.msg4LastSymb + 1) * scaleTd - 1) // self.nrSymbPerSlotNormCp)
            tmpStr = tmpStr + '[hsfn=%d, sfn=%d, slot=%d]' % (hsfn, sfn, slotInPuschScs)
            self.ngwin.logEdit.append(tmpStr)
            qApp.processEvents()

            #refer to 3GPP 38.213 vf40 9.2.1
            #determine PUCCH index r_PUCCH
            rPucch = math.floor(2 * self.msg4Cce0 / self.coreset0NumCces) + 2 * self.nrMsg4DeltaPri

            #refer to 3GPP 38.213 vf30
            #Table 9.2.1-1: PUCCH resource sets before dedicated PUCCH resource configuration
            commonPucchResSets = {
                0 : (0,12,2,0,(0, 3)),
                1 : (0,12,2,0,(0, 4, 8)),
                2 : (0,12,2,3,(0, 4, 8)),
                3 : (1,10,4,0,(0, 6)),
                4 : (1,10,4,0,(0, 3, 6, 9)),
                5 : (1,10,4,2,(0, 3, 6, 9)),
                6 : (1,10,4,4,(0, 3, 6, 9)),
                7 : (1,4,10,0,(0, 6)),
                8 : (1,4,10,0,(0, 3, 6, 9)),
                9 : (1,4,10,2,(0, 3, 6, 9)),
                10 : (1,4,10,4,(0, 3, 6, 9)),
                11 : (1,0,14,0,(0, 6)),
                12 : (1,0,14,0,(0, 3, 6, 9)),
                13 : (1,0,14,2,(0, 3, 6, 9)),
                14 : (1,0,14,4,(0, 3, 6, 9)),
                #Note: for pucch resource index 15, 'PRB offset' is floor(N_BWP_size/4)
                15 : (1,0,14,None,(0, 3, 6, 9)),
                }

            pucchFmt, firstSymb, numSymbs, prbOffset, initialCsSet = commonPucchResSets[rPucch]
            if rPucch == 15:
                prbOffset = math.floor(self.nrIniUlBwpNumRbs / 4)
            numCs = len(initialCsSet)

            #the PRB index of the PUCCH transmission per hop
            prbPerHop = []
            if math.floor(rPucch / 8) == 0:
                prbPerHop.append(prbOffset + math.floor(rPucch / numCs))
                prbPerHop.append(self.nrIniUlBwpNumRbs - 1 - prbOffset - math.floor(rPucch / numCs))
            else:
                prbPerHop.append(self.nrIniUlBwpNumRbs - 1 - prbOffset - math.floor((rPucch - 8) / numCs))
                prbPerHop.append(prbOffset + math.floor((rPucch - 8) / numCs))

            #refer to 3GPP 38.213 vf40 9.2.3
            #For DCI format 1_0, the PDSCH-to-HARQ-timing-indicator field values map to {1, 2, 3, 4, 5, 6, 7, 8}.
            #With reference to slots for PUCCH transmissions, if the UE detects a DCI format 1_0 or a DCI format 1_1 scheduling a PDSCH reception ending in slot n or if the UE detects a DCI format 1_0 indicating a SPS PDSCH release through a PDCCH reception ending in slot n, the UE provides corresponding HARQ-ACK information in a PUCCH transmission within slot n+k, where k is a number of slots and is indicated by the PDSCH-to-HARQ-timing-indicator field in the DCI format, if present, or provided by dl-DataToUL-ACK.
            k1 = [1,2,3,4,5,6,7,8][self.nrMsg4TdK1]

            slotMsg4Harq = slotInPuschScs + k1
            if slotMsg4Harq >= self.nrSlotPerRf[self.nrScs2Mu[self.nrIniUlBwpScs]]:
                slotMsg4Harq = slotMsg4Harq % self.nrSlotPerRf[self.nrScs2Mu[self.nrIniUlBwpScs]]
                hsfn, sfn = self.incSfn(hsfn, sfn, 1)
                self.alwaysOnTr(hsfn, sfn)

            dn = '%s_%s' % (hsfn, sfn)
            self.ngwin.logEdit.append('deltaPri=%d, rPucch=%d(format=%d,firstSymb=%d,numSymbs=%d,prbOffset=%d,initialCsSet=%s), prbPerHop=%s, K1=%s, slotMsg4Harq=[%s,%s,%s]' % (self.nrMsg4DeltaPri, rPucch, pucchFmt, firstSymb, numSymbs, prbOffset, initialCsSet, prbPerHop, k1, hsfn, sfn, slotMsg4Harq))
            qApp.processEvents()

            scaleTd = self.baseScsTd // self.nrIniUlBwpScs
            scaleFd = self.nrIniUlBwpScs // self.baseScsFd
            firstSymbPucchInBaseScsTd = (slotMsg4Harq * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
            pucchSymbsInBaseScsTd = [firstSymbPucchInBaseScsTd+k for k in range(numSymbs*scaleTd)]
            pucchDmrsSymbs = []
            if pucchFmt == 1:
                for i in range(numSymbs):
                    if i % 2 == 0:
                        pucchDmrsSymbs.append(i)
                self.ngwin.logEdit.append('contents of pucchDmrsSymbs(w.r.t to firstSymb(=%d) of PUCCH): %s' % (firstSymb, pucchDmrsSymbs))
                qApp.processEvents()

            for hop in range(2):
                firstScPucchInBaseScsFd = self.nrCarrierMinGuardBand * self.nrScPerPrb * (self.nrCarrierScs // self.baseScsFd) + self.nrIniUlBwpStartRb * self.nrScPerPrb * scaleFd + prbPerHop[hop] * self.nrScPerPrb * scaleFd
                pucchScsInBaseScsFd = [firstScPucchInBaseScsFd+k for k in range(1*self.nrScPerPrb*scaleFd)]

                #validate against tdd-ul-dl-config
                #refer to 3GPP 38.213 vf40 11.1
                #For a set of symbols of a slot that are indicated to a UE as downlink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not transmit PUSCH, PUCCH, PRACH, or SRS in the set of symbols of the slot.
                #For a set of symbols of a slot that are indicated to a UE as flexible by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not expect to receive both dedicated configuring transmission from the UE in the set of symbols of the slot and dedicated configuring reception by the UE in the set of symbols of the slot.
                if self.nrDuplexMode == 'TDD':
                    invalidSymbs = []
                    for symb in pucchSymbsInBaseScsTd:
                        if self.gridNrTdd[dn][firstScPucchInBaseScsFd, symb] in (NrResType.NR_RES_D.value, NrResType.NR_RES_F.value):
                            invalidSymbs.append(symb)

                    if len(invalidSymbs) > 0:
                        self.ngwin.logEdit.append('<font color=red>Error: UE does not transmit PUSCH, PUCCH, PRACH or SRS in symbols which are indicated as downlink or flexible!</font>')
                        self.ngwin.logEdit.append('contents of invalidSymbs(hop=%d,scaleTd=%d,firstSymb=%d): %s' % (hop, scaleTd, firstSymbPucchInBaseScsTd, invalidSymbs))
                        qApp.processEvents()
                        self.error = True
                        return (None, None, None)

                for i in range(numSymbs):
                    if self.nrDuplexMode == 'TDD':
                        if pucchFmt == 1 and i in pucchDmrsSymbs:
                            self.gridNrTdd[dn][pucchScsInBaseScsFd, firstSymbPucchInBaseScsTd+i*scaleTd:firstSymbPucchInBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_PUCCH.value
                        else:
                            self.gridNrTdd[dn][pucchScsInBaseScsFd, firstSymbPucchInBaseScsTd+i*scaleTd:firstSymbPucchInBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_PUCCH.value
                    else:
                        if pucchFmt == 1 and i in pucchDmrsSymbs:
                            self.gridNrFddUl[dn][pucchScsInBaseScsFd, firstSymbPucchInBaseScsTd+i*scaleTd:firstSymbPucchInBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_PUCCH.value
                        else:
                            self.gridNrFddUl[dn][pucchScsInBaseScsFd, firstSymbPucchInBaseScsTd+i*scaleTd:firstSymbPucchInBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_PUCCH.value

            return (hsfn, sfn, slotMsg4Harq)
        else:
            pass

        return (hsfn, sfn, slot)

    def sendPusch(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside sendPusch')
        return (hsfn, sfn)

    def recvPdsch(self, hsfn, sfn):
        self.ngwin.logEdit.append('---->inside recvPdsch')
        return (hsfn, sfn)

    def alwaysOnTr(self, hsfn, sfn):
        if self.error:
            return

        self.ngwin.logEdit.append('---->inside alwaysOnTr(hsfn=%s,sfn=%s)' % (hsfn, sfn))

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

        if self.aotSsb(hsfn, sfn):
            if not self.error:
                self.aotPdcchSib1(hsfn, sfn)
            if not self.error:
                self.aotSib1(hsfn, sfn)

    def aotSsb(self, hsfn, sfn):
        if self.error:
            return False

        if self.nrSsbPeriod >= 10 and self.deltaSfn(self.hsfn, self.nrMibSfn, hsfn, sfn) % (self.nrSsbPeriod // 10) != 0:
            self.ngwin.logEdit.append('<font color=purple>no SSB transmission in current frame(hsfn=%d,sfn=%d)</font>' % (hsfn, sfn))
            qApp.processEvents()
            return False

        dn = '%s_%s' % (hsfn, sfn)
        if dn in self.ssbFirstSymbInBaseScsTd:
            return False
        else:
            self.ssbFirstSymbInBaseScsTd[dn] = []
            self.ssbSymbsInBaseScsTd[dn] = set()

        self.ngwin.logEdit.append('---->inside aotSsb(hsfn=%d,sfn=%d, scaleTd=%d, scaleFd=%d)' % (hsfn, sfn, self.baseScsTd // self.nrSsbScs, self.nrSsbScs // self.baseScsFd))
        qApp.processEvents()

        ssbHrfSet = [0, 1] if self.nrSsbPeriod < 10 else [self.nrMibHrf]
        scaleTd = self.baseScsTd // self.nrSsbScs
        scaleFd = self.nrSsbScs // self.baseScsFd
        v = self.nrPci % 4

        for hrf in ssbHrfSet:
            for issb in range(self.nrSsbMaxL):
                if self.ssbSet[issb] == '0':
                    self.ssbFirstSymbInBaseScsTd[dn].append(None)
                    continue

                #SSB time domain
                ssbFirstSymb = hrf * (self.nrSymbPerRfNormCp // 2) + self.ssbFirstSymbSet[issb] * scaleTd
                self.ngwin.logEdit.append('<font color=purple>[AOT @ hsfn=%d, sfn=%d]issb=%d, ssbFirstSc=%d, v=%d, ssbFirstSymb=%d</font>' % (hsfn, sfn, issb, self.ssbFirstSc, v, ssbFirstSymb))
                qApp.processEvents()

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
                            if self.gridNrTdd[dn][self.ssbFirstSc, ssbFirstSymb+i*scaleTd+j] in (NrResType.NR_RES_U.value, NrResType.NR_RES_F.value):
                                self.ngwin.logEdit.append('<font color=red><b>[%s]Error</font>: The UE does not expect the set of symbols of the slot which are used for SSB transmission(ssb index=%d, first symbol=%d) to be indicated as uplink by TDD-UL-DL-ConfigurationCommon.' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), issb, ssbFirstSymb))
                                qApp.processEvents()
                                self.error = True
                                return False

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

        return True

    def aotPdcchSib1(self, hsfn, sfn, dci='dci10', rnti='si-rnti'):
        if self.error:
            return False

        if not (dci == 'dci10' and rnti == 'si-rnti'):
            self.error = True
            return False

        self.ngwin.logEdit.append('---->inside aotPdcchSib1(hsfn=%d, sfn=%d, dci="%s",rnti="%s", scaleTdSsb=%d, scaleTdRmsiScs=%d)' % (hsfn, sfn, dci, rnti, self.baseScsTd // self.nrSsbScs, self.baseScsTd // self.nrMibCommonScs))
        qApp.processEvents()

        ret = self.detCss0(hsfn, sfn)
        if not ret:
            self.error = True
            return False

        dn = '%s_%s' % (hsfn, sfn)
        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd

        for _issb in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
            if self.ssbFirstSymbInBaseScsTd[dn][_issb] is None:
                continue

            issb = _issb % self.nrSsbMaxL
            hrf = self.nrMibHrf if self.nrSsbPeriod >= 10 else _issb // self.nrSsbMaxL
            oc, firstSymb, valid = self.coreset0Occasions['%s_%s' %(dn, _issb)]

            allPdcchCands = []
            numCandidates = min(self.nrCss0MaxNumCandidates, self.coreset0NumCces // self.nrCss0AggLevel)
            for i in range(len(valid)):
                if valid[i] == 'NOK' or (self.nrAdvSib1PdcchSlot is not None and self.nrAdvSib1PdcchSlot[issb] != i):
                    continue

                hsfnc, sfnc, nc = oc[i]
                for j in range(numCandidates):
                    allPdcchCands.append([hsfnc, sfnc, nc, firstSymb, j])

            aotStatus = False
            #for pdcchSlot in range(len(valid)):
            for cand in allPdcchCands:
                if aotStatus:
                    break

                if cand in self.reservedPdcchSib1.values():
                    continue

                self.ngwin.logEdit.append('<font color=purple>[AOT @ hsfn=%d, sfn=%d]PDCCH scheduling SIB1 for issb=%d(hrf=%d): [%s]</font>' % (hsfn, sfn, issb, hrf, cand))
                qApp.processEvents()

                hsfnc, sfnc, nc, firstSymb, pdcchCandidate = cand
                self.alwaysOnTr(hsfnc, sfnc)

                firstSymbInBaseScsTd = (nc * self.nrSymbPerSlotNormCp + firstSymb) * scaleTd
                cceSet = [pdcchCandidate * self.nrCss0AggLevel + k for k in range(self.nrCss0AggLevel)]
                dn2 = '%s_%s' % (hsfnc, sfnc)
                for i in range(self.coreset0Cces.shape[0]):
                    for j in range(self.coreset0Cces.shape[1]):
                        if self.coreset0Cces[i, j] in cceSet:
                            if self.nrDuplexMode == 'TDD':
                                self.gridNrTdd[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                                self.gridNrTdd[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value
                            else:
                                self.gridNrFddDl[dn2][self.coreset0FirstSc+i*self.nrScPerPrb*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_PDCCH.value
                                self.gridNrFddDl[dn2][self.coreset0FirstSc+(i*self.nrScPerPrb+1)*scaleFd:self.coreset0FirstSc+(i+1)*self.nrScPerPrb*scaleFd:4, firstSymbInBaseScsTd+j*scaleTd:firstSymbInBaseScsTd+(j+1)*scaleTd] = NrResType.NR_RES_DMRS_PDCCH.value

                key = '%s_%s_%s' % (hsfn, sfn, _issb)
                self.reservedPdcchSib1[key] = cand
                aotStatus = True

            if not aotStatus:
                self.ngwin.logEdit.append('<font color=purple>[AOT @ hsfn=%d, sfn=%d]no valid pdcch slot/candidate for issb=%d(hrf=%d)</font>' % (hsfn, sfn, issb, self.nrMibHrf if self.nrSsbPeriod >= 10 else issb // self.nrSsbMaxL))
                qApp.processEvents()
                self.error = True

        return not self.error

    def aotSib1(self, hsfn, sfn):
        if self.error:
            return False

        self.ngwin.logEdit.append('---->inside aotSib1(hsfn=%d,sfn=%d)' % (hsfn, sfn))
        qApp.processEvents()

        dn = '%s_%s' % (hsfn, sfn)
        scaleTd = self.baseScsTd // self.nrMibCommonScs
        scaleFd = self.nrMibCommonScs // self.baseScsFd

        self.ngwin.logEdit.append('contents of reservedPdcchSib1(key=[hsfn,sfn,issb],val=[hsfn,sfn,slot,firstSymb,pdcchCandidate]):')
        for key,val in self.reservedPdcchSib1.items():
            self.ngwin.logEdit.append('key=%s,val=%s' % (key, val))
            qApp.processEvents()

        for _issb in range(len(self.ssbFirstSymbInBaseScsTd[dn])):
            if self.ssbFirstSymbInBaseScsTd[dn][_issb] is None:
                continue

            issb = _issb % self.nrSsbMaxL
            hrf = self.nrMibHrf if self.nrSsbPeriod >= 10 else _issb // self.nrSsbMaxL
            self.ngwin.logEdit.append('<font color=purple>[AOT @ hsfn=%d, sfn=%d]SIB1 corresponding to SSB#%s(hrf=%s)</font>' % (hsfn, sfn, issb, hrf))
            qApp.processEvents()

            key = '%s_%s_%s' % (hsfn, sfn, _issb)
            hsfnc, sfnc, nc, firstSymb, pdcchCandidate = self.reservedPdcchSib1[key]

            slotSib1 = math.floor(nc * 2 ** (self.nrSib1MuPdsch - self.nrSib1MuPdcch)) + self.nrSib1TdK0
            if slotSib1 >= self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]:
                slotSib1 = slotSib1 % self.nrSlotPerRf[self.nrScs2Mu[self.nrMibCommonScs]]
                hsfnc, sfnc = self.incSfn(hsfnc, sfnc, 1)
                self.alwaysOnTr(hsfnc, sfnc)

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
            qApp.processEvents()

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
            dn2 = '%s_%s' % (hsfnc, sfnc)
            if dn2 in self.ssbFirstSymbInBaseScsTd:
                #refer to 3GPP 38.314 vf40
                #5.1.4	PDSCH resource mapping
                '''
                When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 0, the UE shall assume that no SS/PBCH block is transmitted in REs used by the UE for a reception of the PDSCH.
                '''
                tdOverlapped = self.ssbSymbsInBaseScsTd[dn2].intersection(set(sib1SymbsInBaseScsTd))
                fdOverlapped = self.ssbScsInBaseScsFd.intersection(set(sib1ScsInBaseScsFd))
                if len(tdOverlapped) > 0 and len(fdOverlapped) > 0:
                    self.ngwin.logEdit.append('<font color=red><b>[%s]Error[hrf=%d,issb=%d,slotSib1=%d]</font>:When receiving the PDSCH scheduled with SI-RNTI and the system information indicator in DCI is set to 0, the UE shall assume that no SS/PBCH block is transmitted in REs used by the UE for a reception of the PDSCH.\ntdOverlapped=%s\nfdOverlapped=%s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), hrf, issb, slotSib1, tdOverlapped, fdOverlapped))
                    qApp.processEvents()
                    self.error = True
                    return False

            #refer to 3GPP 38.213 vf40 11.1
            #For a set of symbols of a slot that are indicated to a UE as uplink by TDD-UL-DL-ConfigurationCommon, or TDD-UL-DL-ConfigDedicated, the UE does not receive PDCCH, PDSCH, or CSI-RS in the set of symbols of the slot.
            if self.nrDuplexMode == 'TDD':
                invalidSymbs = []
                for symb in sib1SymbsInBaseScsTd:
                    if self.gridNrTdd[dn][sib1ScsInBaseScsFd[0], symb] in (NrResType.NR_RES_U.value, NrResType.NR_RES_F.value):
                        invalidSymbs.append(symb)

                if len(invalidSymbs) > 0:
                    self.ngwin.logEdit.append('<font color=red>Error: UE does not receive PDSCH, PDCCH, or CSI-RS in symbols which are indicated as uplink or flexible!</font>')
                    self.ngwin.logEdit.append('contents of invalidSymbs(scaleTd=%d,firstSymb=%d): %s' % (scaleTd, firstSymbSib1InBaseScsTd, invalidSymbs))
                    qApp.processEvents()
                    self.error = True
                    return False

            self.reservedSib1[key] = [hsfnc, sfnc, slotSib1]

            for i in range(self.nrSib1TdNumSymbs):
                if self.nrDuplexMode == 'TDD':
                    self.gridNrTdd[dn2][sib1ScsInBaseScsFd, firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_SIB1.value
                    if i in sib1DmrsSymbs:
                        for j in range(self.nrSib1FdNumRbs):
                            for k in range(self.nrScPerPrb):
                                if self.nrSib1DmrsFdK[k] == 1:
                                    self.gridNrTdd[dn2][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_SIB1.value
                                else:
                                    if not (self.nrSib1TdMappingType == 'Type B' and self.nrSib1TdNumSymbs == 2):
                                        self.gridNrTdd[dn2][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value
                else:
                    self.gridNrFddDl[dn2][sib1ScsInBaseScsFd, firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_SIB1.value
                    if i in sib1DmrsSymbs:
                        for j in range(self.nrSib1FdNumRbs):
                            for k in range(self.nrScPerPrb):
                                if self.nrSib1DmrsFdK[k] == 1:
                                    self.gridNrFddDl[dn2][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DMRS_SIB1.value
                                else:
                                    if not (self.nrSib1TdMappingType == 'Type B' and self.nrSib1TdNumSymbs == 2):
                                        self.gridNrFddDl[dn2][sib1ScsInBaseScsFd[(j*self.nrScPerPrb+k)*scaleFd:(j*self.nrScPerPrb+k+1)*scaleFd], firstSymbSib1InBaseScsTd+i*scaleTd:firstSymbSib1InBaseScsTd+(i+1)*scaleTd] = NrResType.NR_RES_DTX.value

        return True
