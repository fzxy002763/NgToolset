#!/usr/bin/python3
# -*- encoding: utf-8 -*-

'''
File:
    ngsshsftp.py
Description:
    SSH and SFTP implementation using paramiko library.
Change History:
    2019-3-21   v0.1    created.    github/zhenggao2
'''

import os
import time
import traceback
import paramiko
import ngmainwin
from PyQt5.QtWidgets import qApp

class NgSshSftp(object):
    def __init__(self, ngwin):
        self.ngwin = ngwin
        self.bbuip = []
        #dataDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.confDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
        try:
            with open(os.path.join(self.confDir, 'bbuip.txt'), 'r') as f:
                self.ngwin.logEdit.append('Parsing bbuip.txt...')
                qApp.processEvents()

                while True:
                    line = f.readline()
                    if not line:
                        break
                    if line.startswith('#') or line.strip() == '':
                        continue

                    tokens = line.split(',')
                    tokens = list(map(lambda x:x.strip(), tokens))
                    if len(tokens) != 3:
                        self.ngwin.logEdit.append('Format for each line of bbuip.txt must be: bts_id,bts_ip,bts_name!')
                    else:
                        self.bbuip.append(tokens)
        except Exception as e:
            #self.ngwin.logEdit.append(str(e))
            self.ngwin.logEdit.append(traceback.format_exc())

        for bts in self.bbuip:
            btsId, btsIp, btsName = bts
            self.ngwin.logEdit.append('Connecting to bts(id=%s,ip=%s,name=%s)' % (btsId, btsIp, btsName))
            qApp.processEvents()

            try:
                t = paramiko.Transport((btsIp, 22))
                t.connect(username='toor4nsn', password='oZPS0POrRieRtu')

                #SSHClient
                ssh = paramiko.SSHClient()
                ssh._transport = t
                #ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                #ssh.connect(hostname='10.140.7.4', port=22, username='toor4nsn', password='oZPS0POrRieRtu')
                self.ngwin.logEdit.append('>pwd:')
                stdin, stdout, stderr = ssh.exec_command('pwd')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>ls -al /:')
                stdin, stdout, stderr = ssh.exec_command('ls -al /')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>ls -al /ffs:')
                stdin, stdout, stderr = ssh.exec_command('ls -al /ffs')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>cd /ffs/run && ls -al' )
                stdin, stdout, stderr = ssh.exec_command('cd /ffs/run && ls -al')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>ls -al /ffs/run/config:')
                stdin, stdout, stderr = ssh.exec_command('ls -al /ffs/run/config')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>ls -al /tmp:')
                stdin, stdout, stderr = ssh.exec_command('ls -al /tmp')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>find / -iname "SBTS_SCF.xml" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "SBTS_SCF.xml" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>find / -iname "Vendor_DU.xml" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "Vendor_DU.xml" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>find / -iname "swconfig.txt" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "swconfig.txt" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                self.ngwin.logEdit.append('>find / -iname "FrequencyHistory.xml" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "FrequencyHistory.xml" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                #5G raw pm: MRBTS-53775_PM_20190321_070030_SRAN.xml
                self.ngwin.logEdit.append('>find / -iname "MRBTS*PM*.xml" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "MRBTS*PM*.xml" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                '''
                #4G raw pm: PM.BTS-833144.20160916.150000.LTE.xml.xz, PM.BTS-833144.20160916.151500.LTE.raw.xz
                self.ngwin.logEdit.append('>find / -iname "MRBTS*PM*.xml" -print:')
                stdin, stdout, stderr = ssh.exec_command('find / -iname "MRBTS*PM*.xml" -print')
                self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))
                '''

                #parse path configuration
                try:
                    with open(os.path.join(self.confDir, 'sftp_path_config.txt'), 'r') as f:
                        self.ngwin.logEdit.append('Parsing SFTP path configuation: %s' % f.name)
                        qApp.processEvents()

                        while True:
                            line = f.readline()
                            if not line:
                                break
                            if line.startswith('#') or line.strip() == '':
                                continue

                            tokens = line.split('=')
                            tokens = list(map(lambda x:x.strip(), tokens))
                            if len(tokens) == 2:
                                if tokens[0].lower() == 'scf_path':
                                    self.scfPath = tokens[1]
                                elif tokens[0].lower() == 'vendor_path':
                                    self.vendorPath = tokens[1]
                                elif tokens[0].lower() == 'swconfig_path':
                                    self.swconfigPath = tokens[1]
                                elif tokens[0].lower() == 'freq_history_path':
                                    self.freqHistPath = tokens[1]
                                elif tokens[0].lower() == 'raw_pm_path':
                                    self.rawPmPath = tokens[1]
                                else:
                                    pass
                except Exception as e:
                    #self.ngwin.logEdit.append(str(e))
                    self.ngwin.logEdit.append(traceback.format_exc())


                #SFTPClient
                curDir = os.path.dirname(os.path.abspath(__file__))
                if not os.path.exists(os.path.join(curDir, 'output')):
                    os.mkdir(os.path.join(curDir, 'output'))

                sftp = paramiko.SFTPClient.from_transport(t)
                #remotePath = '/ffs/run/config/node_0xe000/siteoam/config/SBTS_SCF.xml'
                remotePath = self.scfPath
                localPath = './output/scf_%s.xml' % '_'.join(bts)
                sftp.get(remotePath, localPath)

                #remotePath = '/ffs/run/config/node_0xe000/config/Vendor_DU.xml'
                remotePath = self.vendorPath
                localPath = './output/vendor_%s.xml' % '_'.join(bts)
                sftp.get(remotePath, localPath)

                #remotePath = '/ffs/run/swconfig.txt'
                remotePath = self.swconfigPath
                localPath = './output/swconfig_%s.txt' % '_'.join(bts)
                sftp.get(remotePath, localPath)

                #remotePath = '/tmp/FrequencyHistory.xml'
                remotePath = self.freqHistPath
                localPath = './output/FrequencyHistory_%s.xml' % '_'.join(bts)
                sftp.get(remotePath, localPath)

                self.ngwin.logEdit.append('>cd %s && ls -al:' % self.rawPmPath)
                stdin, stdout, stderr = ssh.exec_command('cd %s && ls -al' % self.rawPmPath)
                stdout = str(stdout.read(), encoding='utf-8')
                self.ngwin.logEdit.append(stdout)
                numXmls = int(stdout.split('\n')[0].split(' ')[1])
                if numXmls > 0:
                    if not os.path.exists(os.path.join(curDir, 'data/raw_pm')):
                        os.mkdir(os.path.join(curDir, 'data/raw_pm'))

                    self.ngwin.logEdit.append('>tar -czf /tmp/PM.tar.gz *.xml:')
                    stdin, stdout, stderr = ssh.exec_command('tar -czf /tmp/PM.tar.gz *.xml')
                    self.ngwin.logEdit.append(str(stdout.read(), encoding='utf-8'))

                    remotePath = '/tmp/PM.tar.gz'
                    localPath = './data/raw_pm/PM_%s_%s.tar.gz' % ('_'.join(bts), time.strftime('%Y%m%d%H%M%S', time.localtime()))
                    sftp.get(remotePath, localPath)

                t.close()
            except Exception as e:
                #self.ngwin.logEdit.append(str(e))
                self.ngwin.logEdit.append(traceback.format_exc())
                continue
