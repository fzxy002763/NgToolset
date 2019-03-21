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
import paramiko
import ngmainwin
from PyQt5.QtWidgets import qApp

class NgSshSftp(object):
    def __init__(self, ngwin):
        self.ngwin = ngwin
        self.bbuip = []
        dataDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        try:
            with open(os.path.join(dataDir, 'bbuip.txt'), 'r') as f:
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
            #self.ngwin.logEdit.append('%s' % e.args)
            self.ngwin.logEdit.append(str(e))
            
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
                
                #SFTPClient
                curDir = os.path.dirname(os.path.abspath(__file__))
                if not os.path.exists(os.path.join(curDir, 'output')):
                    os.mkdir(os.path.join(curDir, 'output'))
                            
                sftp = paramiko.SFTPClient.from_transport(t)
                remotePath = '/ffs/run/config/node_0xe000/siteoam/config/SBTS_SCF.xml'
                localPath = './output/scf_%s.xml' % '_'.join(bts)
                sftp.get(remotePath, localPath)
                
                remotePath = '/ffs/run/config/node_0xe000/config/Vendor_DU.xml'
                localPath = './output/vendor_%s.xml' % '_'.join(bts)
                sftp.get(remotePath, localPath)
                
                remotePath = '/ffs/run/swconfig.txt'
                localPath = './output/swconfig_%s.txt' % '_'.join(bts)
                sftp.get(remotePath, localPath)
                
                remotePath = '/tmp/FrequencyHistory.xml'
                localPath = './output/FrequencyHistory_%s.xml' % '_'.join(bts) 
                sftp.get(remotePath, localPath)
                
                self.ngwin.logEdit.append('>cd /tmp/node_0xe000/tmp/pm/reports && ls -al:')
                stdin, stdout, stderr = ssh.exec_command('cd /tmp/node_0xe000/tmp/pm/reports && ls -al')
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
                #self.ngwin.logEdit.append('%s' % e.args)
                self.ngwin.logEdit.append(str(e))
                continue
