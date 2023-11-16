#!/usr/bin/env python
# -*- coding: utf-8 -*-
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, QSize, QWaitCondition
from PyQt6.QtWidgets import QMessageBox, QLabel, QGridLayout, QWidget, QPushButton, QToolBar, QApplication, QHBoxLayout, QSpinBox, QVBoxLayout, QFileDialog, QLabel, QErrorMessage, QTabWidget
from PyQt6.QtGui import QPixmap, QImage, QAction, QScreen

import numpy as np
import sys
import src.settings as settings
import src.camera.camera as camera
import src.Phase_pattern as Phase_pattern
import src.OpticalElement as opticalElement
import src.Lens as Lens
import src.Grating as Grating
import src.FourierWavefrontOptim as FourierWavefrontOptim
import src.WavefrontOptim as WavefrontOptim
import src.FlatnessCorrection as FlatnessCorrection
import src.Meshing_process as Meshing_process
import src.Remote_control as Remote_control

from multiprocessing import RLock, Event, Queue, Process, Condition, freeze_support
import threading

SLM_size_X = 600
SLM_size_Y = 500


class ImageWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)

    def hasHeightForWidth(self):
        return self.pixmap() is not None

    def heightForWidth(self, w):
        if self.pixmap():
            try:
                return int(w * (self.pixmap().height() / self.pixmap().width()))
            except ZeroDivisionError:
                return 0

class SLMWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self,resX,resY,window):
        super().__init__(parent=None)
        layout = QVBoxLayout()
        self.setLayout(layout)
        #self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.Change_window(window)
        #monitors = QScreen.virtualSiblings(self.screen())
        # If the user selected a monitor that doesn't exist, use the primary monitor
        #monitor = monitors[window].availableGeometry()

        self.setWindowFlags(Qt.WindowType.BypassWindowManagerHint | Qt.WindowType.X11BypassWindowManagerHint | QtCore.Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(QSize(resX,resY))
        self.pattern_image = ImageWidget()
        self.lbl = QLabel(self)
        self.lbl.move(0, 0)
        self.setStyleSheet("background-color: black;")

    # Resize pattern window size
    def Change_window(self,window):
        monitors = QScreen.virtualSiblings(self.screen())
        # If the user selected a monitor that doesn't exist, use the primary monitor
        if len(monitors) <= window:
            window = 0
        monitor = monitors[window].availableGeometry()
        self.move(monitor.left(), monitor.top())

    def ResizeWindow(self,resX,resY):
        self.setFixedSize(QSize(resX,resY))

    def UpdatePattern(self,pixmap):
        self.lbl.setPixmap(pixmap)
        self.lbl.resize(pixmap.width(), pixmap.height())
        self.update()

class HologramsManager():
    def __init__(self, SLMwindow, settings_manager, pattern_generator,tabwidget):
        self.optical_elements = {}
        self.SLMWindow = SLMwindow
        self.settings_manager = settings_manager
        self.pattern_generator = pattern_generator
        self.tabwidget = tabwidget
        self.pattern = None
        self.wasexec = False

    def addElementToList(self, id, elem):
        self.optical_elements[id] = elem

    def getElementsList(self):
        return self.optical_elements

    def isListEmpty(self):
        return len(self.optical_elements) == 0

    def removeAll(self):
        todelete = []
        for el in self.optical_elements:
            if el is not None:
                todelete.append(el)
        for el in todelete:
            self.optical_elements[el].__del__()

    def removeElementFromList(self, id):
        del self.optical_elements[id]


    def closeSLMWindow(self):
        pass #Hide SLM window

    def __del__(self):
        self.SLMWindow = None
        self.optical_elements = None

    # This function is used to render a pattern generated from an algorithm, 
    # bypassing the active optical elements
    def renderAlgorithmPattern(self, pattern, others):
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern = np.copy(pattern)
        #if not self.wasexec:
        if others == True:
            self.getPatterns()
        #    self.wasexec = True
        self.renderPattern()

    #This part corrects for the non-linearities of the SLM
    #For each wavelenght the maximum phase value is given by the company
    #e.g. at 760nm 255 ---> 226
    #So we need to renormalize the hologram such that value%226
    def RenormalizePattern(self):
        # Wrapped pattern = Total phase (sum of various optical elements) % 256
        # Displayed pattern = Wrapped pattern * (2pi_correction/255)
        self.pattern = ((self.pattern%256)*(self.settings_manager.get_phase_correction())/255).astype(np.uint8)

    # This function gets all the patterns from the active elements and sums them up
    def getPatterns(self):
         for el in self.optical_elements:
            if el is not None:
                if self.optical_elements[el].is_active():
                    pattern_from_el = self.optical_elements[el].get_pattern()
                    if (pattern_from_el.shape[1] != self.settings_manager.get_X_res()) or (pattern_from_el.shape[0] != self.settings_manager.get_Y_res()) :
                        dlg = QMessageBox(self.tabwidget)
                        dlg.setIcon(QMessageBox.Icon.Warning)
                        dlg.setWindowTitle("WARNING!")
                        dlg.setText("One of the optical elements don't match with the SLM resolution. Please check the settings.")
                        button = dlg.exec()
                        if button == QMessageBox.StandardButton.Ok:
                            return	4444
                    self.pattern += pattern_from_el

    # This function does the actual render of the phase pattern. Updates the QPixmap used on the SLM window
    def renderPattern(self):
        self.RenormalizePattern()
        q_img = QImage(self.pattern, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(), self.settings_manager.get_X_res(), QImage.Format.Format_Grayscale8)
#        label = QLabel(self)
        pixmap = QPixmap(q_img)
        self.SLMWindow.ResizeWindow(self.settings_manager.get_X_win_size(),self.settings_manager.get_Y_win_size())
        self.SLMWindow.UpdatePattern(pixmap)

    # Function to update the SLM window when a new pattern is generated
    def updateSLMWindow(self):
        self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.getPatterns()
        self.renderPattern()
        


class First(QtWidgets.QMainWindow):
    def __init__(self, mesh_process, parent=None):
        super(First, self).__init__(parent)
        self.setMinimumSize(QSize(400, 700))
        #centerPoint = QGuiApplication.primaryScreen().availableGeometry()
        self.setWindowTitle("SLM hologram control")
        self.settings_manager = settings.SettingsManager()
        self.pattern_generator = Phase_pattern.Patter_generator()
        self.pattern = None
        self.tabwidget = QTabWidget()
        self.tabwidget.setTabsClosable(True)
        self.cameraWindow = None
        self.tabwidget.tabCloseRequested.connect(self.closeTab)
        self.mesh_process = mesh_process

        self.w = SLMWindow(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(),self.settings_manager.get_SLM_window())
        self.holograms_manager = HologramsManager(self.w, self.settings_manager, self.pattern_generator,self.tabwidget)

        
        self.possible_optical_elements = ["Lens", "Grating", "Flatness correction", "Zernike", "LUT", "Spot optimization", "Spot optimization (ext)"]
        self.tabs_constructors = [self.lens_tab, self.grating_tab, self.flatness_correction_tab, self.zernike_tab, self.LUT_tab, self.Spot_optim, self.Spot_optim_ext]

        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)

        buttons = {}
        self.InitButtons(buttons)

        menu = self.menuBar()
        toolbar = QToolBar("Quick actions")
        grid = QGridLayout()

        self.InitMenu(menu,buttons)
        self.InitToolbar(toolbar,buttons)
        self.addToolBar(toolbar)
        self.InitLayout(grid,buttons)


        wid.setLayout(grid)
        self.show()

    def closeTab(self,index):
        widget = self.tabwidget.widget(index)
        if widget is not None:
            widget.deleteLater()
        self.tabwidget.removeTab(index)
        self.holograms_manager.removeElementFromList(id(widget))

    def lens_tab(self):
        tab = Lens.LensTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Lens")
        self.holograms_manager.addElementToList(id(tab), tab)

    def grating_tab(self):
        tab = Grating.GratingTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Grating")
        self.holograms_manager.addElementToList(id(tab), tab)

    def flatness_correction_tab(self):
        tab = FlatnessCorrection.FlatnessCorrectionTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Flatness Correction")
        self.holograms_manager.addElementToList(id(tab), tab)

    def zernike_tab(self):
        pass
    def LUT_tab(self):
        pass
    def Spot_optim(self):
        if self.cameraWindow is None:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Initialize camera first!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        tab = FourierWavefrontOptim.SpotOptimTab(self.pattern_generator, self.settings_manager, self.holograms_manager,self.cameraWindow)
        self.tabwidget.addTab(tab,"Optimizer (camera)")
        self.holograms_manager.addElementToList(id(tab), tab)

    def Spot_optim_ext(self):
        tab = WavefrontOptim.SpotOptimTab_ext(self.pattern_generator, self.settings_manager, self.holograms_manager, self.mesh_process)
        tab.setEventsHandlers(eventsDict, conditionsDict, queue)
        self.tabwidget.addTab(tab,"Optimizer (ext)")
        self.holograms_manager.addElementToList(id(tab), tab)
        flask_thread = threading.Thread(target=lambda: app.run(host=self.settings_manager.get_IPclient(), port=self.settings_manager.get_Portclient(), debug=True, use_reloader=False))
        flask_thread.daemon = True
        flask_thread.start()
        self.add_endpoint_connections(tab)

    def edit_SLM_settings(self):
        dlg = settings.SettingsDialog(self.settings_manager, self)
        dlg.exec()
        # Update where the SLM window is (TODO: IS IT GOOD TO DO THIS HERE ??)
        self.w.Change_window(self.settings_manager.get_SLM_window())
        # TODO: ADD HERE RESIZING OF SLM PATTERN TO MATCH RESOLUTION
    
    def start_camera(self):
        self.cameraWindow = camera.CameraWindow()
        self.cameraWindow.show()

    def closeEvent(self, event):
        self.holograms_manager.removeAll()
        print("Closing Hologram window")
        QApplication.instance().quit()
    
    def add_endpoint_connections(self,tab):
        app.add_endpoint('/nextStep', 'nextStep', tab.triggerNextStep, methods=['GET'])
        app.add_endpoint('/refzone', 'refzone', tab.getRefZone, methods=['GET'])
        app.add_endpoint('/refzone/<refzone>', 'refzone/<refzone>', tab.setRefZone, methods=['GET'])
        app.add_endpoint('/probzone/<probzone>', 'probzone/<probzone>', tab.setProbZone, methods=['GET'])

    def on_pushButton_clicked(self):
        self.w.show()
        #self.pattern = self.pattern_generator.GenerateLens(100, 800, self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        # Initialize empty pattern. WARNING! Resolution of SLM must be already defined!!
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.update_pattern()

    def InitLayout(self,grid,buttons):
        grid.addWidget(buttons["SLM_hologram_window"], 1, 0)
        grid.addWidget(buttons["Add_optical_elem"], 2, 0)
        grid.addWidget(self.tabwidget,0,0)

    def AddOpticalElement(self):
        if self.holograms_manager.isListEmpty() and self.tabwidget== None:
            # If the user still didn't choose any optical element generate the tabs layout ?
            pass
        inputter = opticalElement.opticalElement(self.possible_optical_elements, self)
        if inputter.exec():
            self.tabs_constructors[inputter.get_selected()]()

    def InitButtons(self,buttons):
        button_exit = QAction("Exit", self)
        button_exit.setStatusTip("Exit")
        button_exit.triggered.connect(QApplication.instance().quit)
        button_exit.setCheckable(True)
        buttons["Exit"] = button_exit


        button_camera = QAction("Start Camera", self)
        button_camera.triggered.connect(self.start_camera)
        buttons["Start Camera"] = button_camera

        button_settings = QAction("Settings", self)
        button_settings.triggered.connect(self.edit_SLM_settings)
        buttons["Settings"] = button_settings

        SLM_hologram_window = QPushButton("Show Hologram/Update")
        SLM_hologram_window.clicked.connect(self.on_pushButton_clicked)
        buttons["SLM_hologram_window"] = SLM_hologram_window

        AddOpticalElement = QPushButton("Add new optical element")
        AddOpticalElement.clicked.connect(self.AddOpticalElement)
        buttons["Add_optical_elem"] = AddOpticalElement

    def InitToolbar(self,toolbar,buttons):
        toolbar.setIconSize(QSize(16, 16))
        toolbar.addSeparator()
        toolbar.addAction(buttons["Settings"])
        toolbar.addAction(buttons["Start Camera"])
        toolbar.addAction(buttons["Exit"])

    def InitMenu(self,menu,buttons):
        file_menu = menu.addMenu("&File")
        file_menu.addAction(buttons["Settings"])
        file_menu.addAction(buttons["Exit"])

    def update_pattern(self):
        self.holograms_manager.updateSLMWindow()

def closeSecondProcess():
    eventsDict['terminate'].set()
    eventsDict['generalEvent'].set()

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('macos')
    main = First(mesh_process)

    main.show()
    retval = app.exec()
    # Close Gmsh process
    closeSecondProcess()
    
    sys.exit(retval)

# Events list for :
# 0 - Mesh generation request
# 1 - General event to check user request
# 2 - Parse mesh request
# 3 - Parsing condition (this is a condition, process has to wait till parsing is done)
# 4 - Show GUI event (opens GMSH GUI)
# 5 - Close GUI event (closes GMSH GUI)
# 6 - Terminate meshing handler process
eventsDict = {"genMesh":Event(),"generalEvent":Event(),"parseMesh":Event(),"showGUI":Event(),"closeGUI":Event(),"terminate":Event(), "savefile":Event(), "loadfile":Event()}
conditionsDict = {"parsingCond":Condition(), "savefile":Condition(), "loadfile":Condition()}

#genMesh, generalEvent, parseMesh, parsingCond, showGUI, closeGUI, terminate = Event(), Event() , Event(), Condition(), Event(), Event(), Event()

# Flask app for remote control
flask_app = Remote_control.Flask(__name__)
app = Remote_control.NetworkManager(flask_app)

if __name__ == '__main__':
    #ctx = get_context('spawn')
    queue = Queue()
    # Start meshing process, this will be needed to show GMESH GUI in another process
    mesh_process = Meshing_process.MeshingHandler(eventsDict, conditionsDict, queue, 0, 0, 0 , "")
    mesh_process.start()
    main()

