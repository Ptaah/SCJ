#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import QDir
from PyQt4.QtCore import QFile
from PyQt4.QtCore import QFileInfo
from PyQt4.QtCore import QMutex
from PyQt4.QtCore import QSettings
from PyQt4.QtCore import QString
from PyQt4.QtCore import QStringList
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QThread
from PyQt4.QtCore import SIGNAL
from PyQt4.QtCore import QTranslator
from PyQt4.QtCore import QLocale
from PyQt4.QtCore import QObject
from PyQt4.QtGui import QFileDialog
from PyQt4.QtGui import QLabel
from PyQt4.QtGui import QApplication
from PyQt4.QtGui import QColor
from PyQt4.QtGui import QHBoxLayout
from PyQt4.QtGui import QVBoxLayout
from PyQt4.QtGui import QDialog
from PyQt4.QtGui import QSpacerItem
from PyQt4.QtGui import QProgressBar
from PyQt4.QtGui import QTextEdit
from PyQt4.QtGui import QPushButton
from PyQt4.QtGui import QSizePolicy
from PyQt4.QtGui import QBrush
from PyQt4.QtGui import QPalette
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

# Mutagen : manage tags on audio files
try:
    import mutagen
    from mutagen.easyid3 import EasyID3
except ImportError:
    mp3tags = False
    print >>sys.stderr, u"Warning Tags on MP3 files will not be available"
else:
    mp3tags = True


def Process( command, output = subprocess.PIPE, outputerr = subprocess.PIPE,
                stdinput = None, universal_newlines = True, bufsize = 0 ):
    """
        Fonction permettant de lancer un processus via subprocess.Popen
    """
    process = subprocess.Popen( command, shell = False, stdin = stdinput,
                                   stdout = output, stderr = outputerr,
                                   universal_newlines = universal_newlines,
                                   bufsize = bufsize)
    return process

class SCJ(QThread):
    lock = QMutex()
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
            self.command = [ u"/usr/bin/sox", u"-S", u"%s" % self.filename,
                             u"-t", u"%s" % self.format, u"%s" % self.output ]
            self.pipecmd = None
        else:
            self.command = [ u"/usr/bin/sox", u"-S", u"%s" % self.filename,
                             u"-t", u"wav", u"-" ]
            self.pipecmd = [ u"/usr/bin/ffmpeg", u"-y", u"-i", u"-",
                             u"-f", u"%s" % self.format, u"%s" % self.output ]
        self.value = 0
        self.process = None
        self.retCode = None
        self.running = False
        self.log = QString(u"")

    def setProgress(self, value):
        self.value = value
        self.emit(SIGNAL("progress(int)"), self.value)

    def mkdir(self, path):
        directory = QDir(path)
        SCJ.lock.lock()
        if not directory.exists() :
            if not directory.mkpath(path) :
                self.emit(SIGNAL("error(QString)"),
                          QString(self.trUtf8("Cannot create %s" % path)))
        SCJ.lock.unlock()

    def run(self):
        self.running = True
        self.mkdir(self.outputdir)
        self.process = Process( self.command,
                                    stdinput = None)
        if self.pipecmd :
            self.pipe = Process( self.pipecmd, stdinput = self.process.stdout)
            self.process.stdout.close()
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
                try:
                    self.process.terminate()
                    self.process.wait()
                except Exception as e:
                    self.process.kill()
            except OSError as e :
                pass
        self.running = False

    def end(self):
        if self.retCode != 0 :
            self.emit(SIGNAL("error(QString)"), self.trUtf8("Code de retour sox : %d\n%s" %
                             (self.retCode, self.log)))
        else:
            if mp3tags : self.set_tags()
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
            self.log.append(line)

    def set_tags(self):
        """
        Update audio file metadata (Id3 tags...)
        """
        if self.format != "mp3":
            return
        tags =  mutagen.File(u"%s" % self.filename, easy = True)
        audio = EasyID3(u"%s" % self.output)
        for key in tags.keys():
            # Ugly hack to have the year in the mp3 metadata
            if key == "year":
                audio["date"] = tags[key]
            else:
                if key in audio.valid_keys :
                    audio[key] = tags[key]
        audio.save()

class SCJProgress(QHBoxLayout):
    def __init__(self, parent=None, file=None, format=None, createDir=False ):
        super(SCJProgress, self).__init__(parent)
        self.format = format
        self.filename = file
        self.createDir = createDir
        self.process = SCJ(self.filename, self.format, createDir)
        self.output = QString(self.process.output)
        self.command = QStringList(self.process.command)
        self.log = QStringList()

        self.label = QLabel(self.output)
        self.label.setToolTip(self.trUtf8("Destination: %s" % self.output))
        self.bar = QProgressBar(parent)
        self.bar.setToolTip(self.trUtf8("Source: %s" % self.filename))
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
        self.startbtn.setToolTip(self.trUtf8("Demarrer"))
        self.stopbtn.setIcon(QIcon(u"images/stop.png"))
        self.stopbtn.setToolTip(self.trUtf8("Stopper"))
        self.cancelbtn.setIcon(QIcon(u"images/remove.png"))
        self.cancelbtn.setToolTip(self.trUtf8("Annuler"))
        self.logbtn.setIcon(QIcon(u"images/log.png"))
        self.logbtn.setToolTip(self.trUtf8("Voir les details"))

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
        self.output = QString(self.process.output)
        self.command = QStringList(self.process.output)
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

        self.readSettings()

        self.setupUi()
        self.retranslateUi()
        self.fermer.setEnabled(True)
        
        self.connect(self.fermer,SIGNAL("clicked()"),self.close)
        self.connect(self.convertDir,SIGNAL("clicked()"),self.getDir)
        self.connect(self.convertFile,SIGNAL("clicked()"),self.getFiles)
        self.connect(self.startallbtn,SIGNAL("clicked()"),self.startAll)
        self.connect(self.delallbtn,SIGNAL("clicked()"),self.delAll)
        self.connect(self.output,SIGNAL("currentIndexChanged(const QString)"),
                     self.setMode)

    def setMode(self, mode):
        self.mode = mode
        self.writeSettings()

    def writeSettings(self):
        settings = QSettings("scj", "scj")
        settings.setValue("mode", self.mode)

    def readSettings(self):
        settings = QSettings("scj", "scj")
        self.mode = settings.value("mode", "ogg").toString()

    def setupUi(self):
        self.setObjectName("SCJ")
        self.setFixedSize(600,260)
        #self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setObjectName("verticalLayout")
        #self.infoText = QTextEdit(self)
        self.infoText = QLabel(self)
        palette = QPalette()
        brush = QBrush(QColor(245, 245, 245))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Normal, QPalette.Background, brush)
        self.infoText.setPalette(palette)
        self.infoText.setAutoFillBackground(True)
        self.infoText.setFixedHeight(200)
        self.infoText.setObjectName("infoText")
        #self.infoText.setReadOnly(True)
        self.infoText.setWordWrap(True)
        self.verticalLayout.addWidget(self.infoText)
        # Manage Actions buttons
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding,
                                 QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        ## Format de sortie
        self.outlabel = QLabel(self.trUtf8("Choix du format de destination"))
        self.horizontalLayout.addWidget(self.outlabel)
        self.output = QComboBox()
        self.output.addItems(self.modes)
        self.output.setCurrentIndex(self.output.findText(self.mode))
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

        # Layout for allButtons
        self.allLayout = QHBoxLayout()
        # Add startAll bouton
        self.startallbtn = QPushButton(self)
        self.allLayout.addWidget(self.startallbtn)
        self.startallbtn.hide()
        self.verticalLayout.addLayout(self.allLayout)
        # Add delAll bouton
        self.delallbtn = QPushButton(self)
        self.allLayout.addWidget(self.delallbtn)
        self.delallbtn.hide()
        # Mode avec scroll
        self.frame = QFrame()
        self.frame.setMinimumSize(520,250)
        self.frame.setMaximumWidth(520)
        self.scroll = QScrollArea()
        self.scroll.setMinimumHeight(180)
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

        # Add a strech to the bottom of the window
        self.verticalLayout.insertStretch(-1)

    def retranslateUi(self):
        self.setWindowTitle(u"SCJ")
        self.infoText.setToolTip(self.trUtf8("Messages"))
        self.fermer.setToolTip(self.trUtf8("Fermer la fenetre"))
        self.fermer.setText(self.trUtf8("Fermer"))
        self.startallbtn.setToolTip(self.trUtf8("Demarrer toutes les taches"))
        self.startallbtn.setText(self.trUtf8("Tout demarrer"))
        self.delallbtn.setToolTip(self.trUtf8("Supprimmer toutes les taches"))
        self.delallbtn.setText(self.trUtf8("Tout supprimer"))
        self.convertDir.setToolTip(self.trUtf8("Convertir un repertoire"))
        self.convertDir.setText(self.trUtf8("Repertoire"))
        self.convertFile.setToolTip(self.trUtf8("Convertir un fichier"))
        self.convertFile.setText(self.trUtf8("Fichier(s)"))
        self.infoText.setText(u"<h1>%s</h1>\
                                \n%s<br/>\
                                \n%s\
                                \n<ul><li>%s</li>\
                                \n    <li>%s</li>\
                                \n    <li><b>%s</b></li>\
                                \n</ul>" %
                (self.trUtf8("BIENVENUE SUR SCJ"),
                 self.trUtf8("SCJ permet de convertir un ou plusieurs fichiers"+
                              " son vers differents formats."),
                 self.trUtf8("Il gere egalement les repertoires en convertissant"+
                              " l'ensemble des fichiers sons presents vers le"+
                              " format voulu."),
                 self.trUtf8("Choisissez le format de destination"),
                 self.trUtf8("Cliquez sur Fichier(s) ou Repertoire en fonction"+
                             " de ve que vous voulez convertir."),
                 self.trUtf8("Demarrez la conversion !")
                ))

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
        j = self.jobs.pop(job)
        self.addStartAll()
        self.jobsLayout.removeItem(j)

    def getDir(self):
        self.dir = QFileDialog.getExistingDirectory(
                                parent = self,
                                caption = self.trUtf8("Choix du repertoire"),
					            directory = QDir.homePath(),
		                        options = QFileDialog.ShowDirsOnly |
                                QFileDialog.DontResolveSymlinks)
        if self.dir :
            directory = QDir(self.dir, self.filter)
            for file in directory.entryInfoList():
                self.addFile(file, createDir=True)

    def getFiles(self):
        files = QFileDialog.getOpenFileNames(
                                parent = self,
                                caption = self.trUtf8("Choix des fichiers"),
                                directory = QDir.homePath(),
                                filter = u"%s (%s)" % (self.trUtf8("Sons"),
                                                       self.filter))
        for file in files:
            self.addFile(QFileInfo(file), createDir=False)

    def addStartAll(self):
        if (len(self.jobs) > 0 ):
            self.startallbtn.setVisible(True)
            self.delallbtn.setVisible(True)
            self.scroll.setVisible(True)
            self.setFixedSize(600, 480)
        else:
            self.startallbtn.setVisible(False)
            self.delallbtn.setVisible(False)
            self.scroll.setVisible(False)
            self.setFixedSize(600, 260)
        self.updateGeometry()

    def startAll(self):
        for (key, job) in self.jobs.items():
            job.start()

    def delAll(self):
        for (key, job) in self.jobs.items():
            job.stop()
            self.delFile(key)

    def close(self):
        print u"%s" % self.trUtf8("We are stopping running jobs"),
        for (key, job) in self.jobs.items():
            job.stop()
            print ".",
        print u"%s" % self.trUtf8("Done")
        super(QtSCJ, self).close()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Init the translation mecanism
    lang = str(QLocale.system().name())
    print u"Language: %s" % lang
    translator = QTranslator()
    translator.load(u"locale/scj_%s.qm" % lang)
    app.installTranslator(translator)

    #app.setStyle(QStyleFactory.create(EkdConfig.get("general", "qtstyle")))
    main = QtSCJ()
    main.show()
    sys.exit(app.exec_())

# vim: expandtab:ts=4:sw=4
