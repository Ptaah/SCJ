#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import QDir
from PyQt4.QtCore import QFile
from PyQt4.QtCore import QFileInfo
from PyQt4.QtCore import QObject
from PyQt4.QtCore import QRegExp
from PyQt4.QtCore import QSize
from PyQt4.QtCore import QString
from PyQt4.QtCore import QStringList
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QThread
from PyQt4.QtCore import QVariant
from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QFileDialog, QLabel, QImage, QApplication
from PyQt4.QtGui import QDialog, QVBoxLayout, QHBoxLayout, QColor
from PyQt4.QtGui import QSpacerItem, QProgressBar, QTextEdit
from PyQt4.QtGui import QBrush, QSizePolicy, QPushButton, QPalette
from PyQt4.QtGui import QScrollArea
from PyQt4.QtGui import QIcon
from PyQt4.QtGui import QComboBox
from PyQt4.QtGui import QFrame
from PyQt4.QtGui import QMessageBox
from PyQt4.QtGui import QLayout
import os
import sys
import subprocess
import signal
import re



def Process( command, output = subprocess.PIPE, outputerr = subprocess.PIPE,
                stdinput = None, universal_newlines = True, bufsize = 0 ):
    """
        Fonction permettant de lancer un processus via subprocess.Popen
    """
    # Adaptation du code pour la version Win créée avec py2exe
    if os.name == 'nt' :
        if stdinput == None :
            stdinput =  file('nul','a')
        if output == None :
            output =  file('nul','a')
        if outputerr == None :
            outputerr =  file('nul','a')

    try:
        process = subprocess.Popen( command, shell = True, stdin = stdinput,
                                    stdout = output, stderr = outputerr,
                                    universal_newlines = universal_newlines,
                                    bufsize = bufsize,
                                    preexec_fn = os.setsid)
    except AttributeError :
        process = subprocess.Popen( command, shell = True, stdin = stdinput,
                                    stdout = output, stderr = outputerr,
                                    universal_newlines = universal_newlines,
                                    bufsize = bufsize)
    return process

class SCJ(QThread):
    def __init__(self, file=None, format=None, createDir=False):
        super(SCJ, self).__init__()
        self.format = format
        self.filename = file
        self.file = QFileInfo(self.filename)
        self.file.makeAbsolute()
        self.suffix = self.file.suffix()
        if createDir:
            self.outputdir = u"%s-%s" % (self.file.path(), self.format)
        else:
            self.outputdir = self.file.path()
        self.output = u"%s%c%s.%s" % ( self.outputdir,
                                       QDir.separator().unicode(),
                                       self.file.completeBaseName(),
                                       self.format)
        if self.format != "mp3":
            self.command = u"sox -S %s -t %s %s" % (self.filename,
                                             self.format,
                                             self.output)
        else:
            self.command = u"sox -S %s -t wav - | ffmpeg -y -i - -f %s %s" % \
                                        (self.filename,
                                         self.format,
                                         self.output)
        self.value = 0
        self.process = None
        self.retCode = None
        self.running = False
        self.log = u""

    def setProgress(self, value):
        self.value = value
        self.emit(SIGNAL("progress(int)"), self.value)

    def mkdir(self, path):
        directory = QDir()
        if not directory.mkpath(path) :
            self.emit(SIGNAL("error(QString)"),
                      QString(u"Cannot create %s" % path))

    def run(self):
        self.running = True
        self.mkdir(self.outputdir)
        self.process = Process( self.command,
                                    stdinput = None)
        self.emit(SIGNAL("void started()"))
        while self.retCode == None :
            try:
                self.progression()
            except IOError as e:
                pass

            self.retCode = self.process.poll()
            self.usleep(10)
        self.running = False
        self.end()

    def resume(self):
        if self.process :
            try :
                self.process.send_signal(signal.SIGCONT)
            except OSError :
                pass

    def stop(self):
        if self.process :
            try :
                self.process.send_signal(signal.SIGSTOP)
            except OSError :
                pass

    def cancel(self):
        if self.process :
            try :
                self.process.send_signal(signal.SIGCONT)
                self.process.terminate()
            except OSError :
                pass
        self.running = False

    def end(self):
        if self.retCode != 0 :
            self.emit(SIGNAL("error(QString)"), u"Code de retour sox : %d\n%s" %
                             (self.retCode, self.log))
        else:
            self.setProgress(100)
        self.emit(SIGNAL("finished()"))

    def progression(self):
        """
        Recupération de la progression du process en cours
        """
        line = self.process.stderr.readline()
        if re.match(u'^In:.*', line):
            val = re.findall(u"[\.\d]+%", line)[0]
            self.setProgress(float(val[:-1]))
        else :
            self.log += line

class SCJProgress(QHBoxLayout):
    def __init__(self, parent=None, file=None, format=None, createDir=False ):
        super(SCJProgress, self).__init__(parent)
        self.format = format
        self.filename = file
        self.createDir = createDir
        self.process = SCJ(self.filename, self.format, createDir)
        self.output = self.process.output
        self.command = self.process.output
        self.log = QStringList()

        self.label = QLabel(self.output)
        self.label.setToolTip(u"Destination: %s" % self.output)
        self.bar = QProgressBar(parent)
        self.bar.setToolTip(u"Source: %s" % self.filename)
        self.bar.setValue(0)
        self.startbtn = QPushButton(parent) 
        self.stopbtn = QPushButton(parent)
        self.cancelbtn = QPushButton(parent)
        self.logbtn = QPushButton(parent)
        self.cancelbtn.setMinimumSize(32,32)
        self.cancelbtn.setFlat(True)
        self.startbtn.setMinimumSize(32,32)
        self.startbtn.setFlat(True)
        self.stopbtn.setMinimumSize(32,32)
        self.stopbtn.setFlat(True)
        self.label.setMinimumSize(200,32)
        self.bar.setMinimumSize(100,16)
        self.bar.setMaximumHeight(16)

        self.addWidget(self.logbtn)
        self.logbtn.hide()
        self.addWidget(self.label)
        self.addWidget(self.bar)
        self.addWidget(self.startbtn)
        self.addWidget(self.stopbtn)
        self.addWidget(self.cancelbtn)
        self.retranslateUi()

        self.connect(self.startbtn, SIGNAL("clicked()"), self.start)
        self.connect(self.stopbtn, SIGNAL("clicked()"),  self.stop)
        self.connect(self.cancelbtn, SIGNAL("clicked()"), self.remove)
        self.connect(self.logbtn, SIGNAL('clicked()'), self.showLog)
        self.connect(self.process, SIGNAL('progress(int)'), self.bar.setValue)
        self.connect(self.process, SIGNAL('error(QString)'), self.addLog)
        self.connect(self.process, SIGNAL('finished()'), self.enable)

    def retranslateUi(self):
        self.startbtn.setIcon(QIcon(u"images/play.png"))
        self.startbtn.setToolTip(u"Démarrer")
        self.stopbtn.setIcon(QIcon(u"images/stop.png"))
        self.stopbtn.setToolTip(u"Stopper")
        self.cancelbtn.setIcon(QIcon(u"images/remove.png"))
        self.cancelbtn.setToolTip(u"Annuler")
        self.logbtn.setIcon(QIcon(u"images/log.png"))
        self.logbtn.setToolTip(u"Voir les détails")

    def start(self):
        self.log.clear()
        self.logbtn.hide()
        self.disable()
        self.process.start()
        self.process.resume()

    def stop(self):
        self.process.cancel()
        self.process.terminate()
        self.enable()

    def remove(self):
        self.removeWidget(self.label)
        self.removeWidget(self.bar)
        self.removeWidget(self.startbtn)
        self.removeWidget(self.stopbtn)
        self.removeWidget(self.cancelbtn)
        self.removeWidget(self.logbtn)
        self.label.hide()
        self.bar.hide()
        self.startbtn.hide()
        self.stopbtn.hide()
        self.cancelbtn.hide()
        self.logbtn.hide()
        self.emit(SIGNAL("void removed(QString)"), self.output)

    def showLog(self):
        QMessageBox.critical(None, u"Ooops", self.log.join("\n"))

    def addLog(self, log):
        self.log.append(log)
        self.logbtn.show()
        palette = QPalette()
        brush = QBrush(QColor(240, 100, 100))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Normal, QPalette.Background, brush)
        self.label.setPalette(palette)
        self.label.setAutoFillBackground(True)

    def enable(self):
        self.process = SCJ(self.filename, self.format, self.createDir)
        self.output = self.process.output
        self.command = self.process.output
        self.connect(self.process, SIGNAL('progress(int)'), self.bar.setValue)
        self.connect(self.process, SIGNAL('error(QString)'), self.addLog)
        self.connect(self.process, SIGNAL('finished()'), self.enable)
        self.cancelbtn.setEnabled(True)
        self.startbtn.setEnabled(True)

    def disable(self):
        self.cancelbtn.setEnabled(False)
        self.startbtn.setEnabled(False)
        self.label.setAutoFillBackground(False)


class QtSCJ(QDialog) :
    """
    QtSCJ est une boite de dialogue contenant l'état de la progression de 
    chaque processus
    """

    def __init__(self, parent=None):
        super(QtSCJ, self).__init__(parent)
        self.dir = None
        self.jobs = { }
        self.log = [ ]
        self.mode = "ogg"
        self.filter = "*.mp3 *.ogg *.wav"
        self.modes = [ "ogg", "mp3", "wav" ]

        self.setupUi()
        self.retranslateUi()
        self.fermer.setEnabled(True)
        
        self.connect(self.fermer,SIGNAL("clicked()"),self.close)
        self.connect(self.convertDir,SIGNAL("clicked()"),self.getDir)
        self.connect(self.convertFile,SIGNAL("clicked()"),self.getFiles)
        self.connect(self.startallbtn,SIGNAL("clicked()"),self.startAll)
        self.connect(self.output,SIGNAL("currentIndexChanged(const QString)"),
                     self.setMode)

    def addText(self, text):
        self.infoText.append(QString(text))

    def setMode(self, mode):
        self.mode = mode

    def setupUi(self):
        self.setObjectName("qtsox")
        self.resize(500, 300)
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setObjectName("verticalLayout")
        self.infoText = QTextEdit(self)
        palette = QPalette()
        brush = QBrush(QColor(255, 255, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Text, brush)
        brush = QBrush(QColor(0, 0, 0))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Base, brush)
        brush = QBrush(QColor(255, 255, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Inactive, QPalette.Text, brush)
        brush = QBrush(QColor(0, 0, 0))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Inactive, QPalette.Base, brush)
        brush = QBrush(QColor(126, 125, 124))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.Text, brush)
        brush = QBrush(QColor(255, 255, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.Base, brush)
        self.infoText.setPalette(palette)
        self.infoText.setObjectName("infoText")
        self.infoText.setReadOnly(True)
        self.verticalLayout.addWidget(self.infoText)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding,
                                 QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        ## Format de sortie
        self.outlabel = QLabel(u"Choix du format de destination")
        self.horizontalLayout.addWidget(self.outlabel)
        self.output = QComboBox()
        self.output.addItems(self.modes)
        self.horizontalLayout.addWidget(self.output)
        # Buttons
        self.fermer = QPushButton(self)
        self.fermer.setObjectName("fermer")
        self.horizontalLayout.addWidget(self.fermer)
        self.convertDir = QPushButton(self)
        self.convertDir.setObjectName("convertDir")
        self.horizontalLayout.addWidget(self.convertDir)
        self.convertFile = QPushButton(self)
        self.convertFile.setObjectName("convertFile")
        self.horizontalLayout.addWidget(self.convertFile)
        self.verticalLayout.addLayout(self.horizontalLayout)

        # Add startAll bouton
        self.startallbtn = QPushButton(self)
        self.verticalLayout.addWidget(self.startallbtn)
        self.startallbtn.hide()
        # Mode avec scroll
        self.frame = QFrame()
        self.frame.setMinimumSize(520,250)
        self.frame.setMaximumWidth(520)
        self.scroll = QScrollArea()
        self.jobsLayout = QVBoxLayout(self.frame)
        self.jobsLayout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        #self.jobsLayout.setSizeConstraint(QLayout.SetMinimumSize)
        #self.jobsLayout.setSizeConstraint(QLayout.SetMaximumSize)
        self.scroll.setWidget(self.frame)
        self.scroll.setWidgetResizable(False)
        self.verticalLayout.addWidget(self.scroll)
        self.scroll.hide()

        # Mode sans scroll
        #self.jobsLayout = QVBoxLayout()
        #self.verticalLayout.addLayout(self.jobsLayout)


    def retranslateUi(self):
        self.setWindowTitle(u"SCJ")
        self.infoText.setToolTip(u"Messages")
        self.fermer.setToolTip(u"Fermer la fenêtre")
        self.fermer.setText(u"Fermer")
        self.startallbtn.setToolTip(u"Démarrer toutes les tâches")
        self.startallbtn.setText(u"Tout démarrer")
        self.convertDir.setToolTip(u"Convertir un répertoire")
        self.convertDir.setText(u"Répertoire")
        self.convertFile.setToolTip(u"Convertir un fichier")
        self.convertFile.setText(u"Fichier(s)")
        self.addText(
                u"<h1>            BIENVENUE SUR SCJ           </h1>\
                \nSCJ permet de convertir un ou plusieurs fichiers son vers\
                \ndifférents formats.<br/><br/>\
                \nIl gère également les répertoires en convertissant\
                \nl'ensemble des fichiers sons présents vers le format voulu.<br/>\
                \nCliquez sur Fichier(s) ou Répertoire en fonction de ve que\
                \nvous voulez convertir."
                )

    def addFile(self, file, createDir=False):
        file.makeAbsolute()
        if (file.suffix() != self.mode):
            job = SCJProgress( parent=None,
                                     file=file.filePath(),
                                     format=self.mode,
                                     createDir=createDir)
            if not self.jobs.get(job.output):
                self.jobs[job.output] = job
                self.jobsLayout.addLayout(self.jobs[job.output])
                self.connect(self.jobs[job.output], SIGNAL("void removed(QString)"), self.delFile)
        self.addStartAll()

    def delFile(self, job):
        self.jobs.pop(job)
        self.addStartAll()

    def getDir(self):
        self.dir = QFileDialog.getExistingDirectory(
                                parent = self,
                                caption = u"Choix du répertoire",
					            directory = QDir.homePath(),
		                        options = QFileDialog.ShowDirsOnly |
                                QFileDialog.DontResolveSymlinks)
        directory = QDir(self.dir, self.filter)
        for file in directory.entryInfoList():
            self.addFile(file, createDir=True)

    def getFiles(self):
        files = QFileDialog.getOpenFileNames(
                                parent = self,
                                caption = u"Choix des fichiers",
                                directory = QDir.homePath(),
                                filter = "Sons (%s)" % self.filter) 
        for file in files:
            self.addFile(QFileInfo(file), createDir=False)

    def addStartAll(self):
        self.startallbtn.setVisible((len(self.jobs) > 0 ))
        self.scroll.setVisible((len(self.jobs) > 0 ))

    def startAll(self):
        for (key, job) in self.jobs.items():
            job.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    #app.setStyle(QStyleFactory.create(EkdConfig.get("general", "qtstyle")))
    main = QtSCJ()
    main.show()
    sys.exit(app.exec_())

# vim: expandtab:ts=4:sw=4