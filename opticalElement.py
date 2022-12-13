# This Python file uses the following encoding: utf-8
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QMessageBox, QLineEdit, QGridLayout, QGroupBox, QComboBox, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSlider, QCheckBox, QSpinBox , QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QPoint
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QImage, QPainter


import numpy as np
import gmsh
import Phase_pattern
import time
import cv2
import os
import threading

class opticalElement(QDialog):
    def __init__(self, elements_map, parent = None):
        super().__init__(parent)
        self.set_attributes()
        self.generate_selection_window(elements_map)
    def __del__(self):
        pass

    def set_attributes(self):
        """
        Set attributes to the settings dialog.
        """
        self.setWindowTitle("Choose optical element")

    def generate_selection_window(self,elements_map):
        """Create groups of radio buttons as settings elements."""
        grid = QGridLayout()
        groupBox = QGroupBox("Which element you want to add ?")
        self.opt_elem_list = QComboBox()
        slayout = QVBoxLayout()
        for el in elements_map:
            self.opt_elem_list.addItem(el)

        slayout.addWidget(self.opt_elem_list)
        _buttons = QDialogButtonBox.StandardButton
        self.button_box = QDialogButtonBox(_buttons.Ok | _buttons.Cancel)

        slayout.addWidget(self.button_box)
        self.setLayout(slayout)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.accepted.connect(self.return_element)

    def return_element(self):
        self.choosen = self.opt_elem_list.currentIndex()

    def get_selected(self):
        return self.choosen

class LensTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.minfocus = 2
        self.maxfocus = 2000
        self.focus = self.minfocus

        self.init_GUI()
    def __del__(self):
        pass
    def init_GUI(self):
        self.slider_layout = QVBoxLayout()
        self.general_controls_layout = QVBoxLayout()

        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating : ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.general_controls_layout.addWidget(self.isactive)
        self.general_controls_layout.addWidget(self.liveupdate)

        self.spin_focus = QDoubleSpinBox(text="Focus ")
        self.spin_focus.setSuffix(' mm')
        self.spin_focus.setKeyboardTracking(False)
        self.spin_focus.setSingleStep(0.1)
        self.spin_focus.setMaximum(self.maxfocus)
        self.spin_focus.setMinimum(self.minfocus)
        self.spin_focus.valueChanged.connect(self.update_lens)

        self.focus_slider = DoubleSlider()
        self.focus_slider.setGeometry(50,50, 200, 50)
        self.focus_slider.setMinimum(0)
        self.focus_slider.setMaximum(2000)
        self.focus_slider.setMinimum(self.minfocus)
        self.focus_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.focus_slider.setTickInterval(10)
        self.focus_slider.valueChanged.connect(self.update_lens)

        self.slider_layout.addWidget(self.spin_focus)
        self.slider_layout.addWidget(self.focus_slider)

        self.make_image_preview()

        self.layout = QGridLayout()
        self.layout.addLayout(self.slider_layout,0,0)
        self.layout.addLayout(self.image_preview_layout,1,0)
        self.layout.addLayout(self.general_controls_layout,2,0)
        self.patten = None
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    # def removeme(self):
    #     self.hologram_manager.removeElementFromList(id(self), self)
    #     pass

    def make_image_preview(self):
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)

    def update_lens(self):
        self.focus = self.sender().value()
        self.focus_slider.setValue(self.focus)
        self.spin_focus.setValue(self.focus)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_pattern(self):
        self.pattern = self.pattern_generator.GenerateLens(self.focus, self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern_image.setImage(self.pattern)
        self.lastvals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
    
    def needs_updates(self):
        news_vals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
        for i in range(len(self.lastvals)):
            self.lastvals[i] != news_vals[i]
            return True
        return False

    def get_pattern(self):
        if self.pattern is None or self.needs_updates():
            self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()


class OptimizerAlgorithm(QThread):

    def __init__(self,hologram_manager,cameraWindow):
        QThread.__init__(self)
        self.pattern = None
        self.frequencies = None
        self.cameraWindow = cameraWindow
        self.times = None
        self.mesh = None
        self.SLM_x_res = None
        self.SLM_y_res = None
        self.ids_list = None
        self.hologram_manager = hologram_manager
        self._active = True
        self.isPhaseReady = False

    def __del__(self):
        self.wait()

    def run(self):
        self.initPattern()
        self.SaveData()
        print("Times : ", self.times, " len ", len(self.times))
        print("IDs : ", self.ids_list , " len ", len(self.ids_list))
        for t,real_time in enumerate(self.times):
            self.isPhaseReady = False
            self.GeneratePhases(t)
            self.hologram_manager.renderAlgorithmPattern(self.pattern, True)
            print("Time: ", t)
            time.sleep(2)
            frame = self.cameraWindow.take_picture()
            self.SaveImg(frame,t)
            ## Check if thread is active
            if not self._active:
                break
            self.isPhaseReady = True
    
    def isPhaseReady(self):
        return self.isPhaseReady
    # Checks that everything was properly initialized before running
    def isThreadReady(self):
        return self.times is not None or self.frequencies is not None or self.mesh is not None or self.SLM_x_res is not None or self.SLM_y_res is not None or self.ids_list is not None
    def stop(self):
        self._active = False
    def activate(self):
        self._active = True
    def setFrequencies(self, frequencies):
        self.frequencies = frequencies
    def setTimes(self, times):
        self.times = times
    def setMesh(self, mesh):
        self.mesh = mesh
    def setSLMsizes(self, SLM_x_res, SLM_y_res):
        self.SLM_x_res = SLM_x_res
        self.SLM_y_res = SLM_y_res
    def setIdsList(self, ids_list):
        self.ids_list = ids_list
    def initPattern(self):
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res), dtype=np.uint8)
        self.random_phases = np.rint(np.random.rand(len(self.ids_list))*255)
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):
                self.pattern[i,j] = self.random_phases[self.ids_list.index(self.mesh[i,j])]


    def SaveImg(self,frame,time):
        np.save(self.mypath+"/Frames/frame_" + str(time) , np.array(frame))
        np.save(self.mypath+"/Intensities/intensity_" + str(time) , np.array(frame.sum(axis=(0,1,2))) )

    def SaveData(self):
        counter = 0
        self.mypath = 'Data/Optimizer_'+(str(counter)) +'/'
        while os.path.exists(self.mypath):   
            counter += 1
            self.mypath = 'Data/Optimizer_'+(str(counter)) +'/'
            print(self.mypath)
        os.makedirs(self.mypath)
        os.makedirs(self.mypath+"Frames")
        os.makedirs(self.mypath+"Intensities")
        np.save(self.mypath+"starting_phases", self.random_phases)
        np.save(self.mypath+"mesh_data", self.mesh)
        np.save(self.mypath+"frequencies", self.frequencies)
        np.save(self.mypath+"times", self.times)
        np.save(self.mypath+"IDs", self.ids_list)



    def GeneratePhases(self,time):
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):
                self.pattern[i,j] += (self.frequencies[self.ids_list.index(self.mesh[i,j])]*self.times[time]*(2*np.pi)*256)%256



class FlatnessCorrectionTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.image_data = None
        self.loaded_file = "none"
        self.scale = 10
        self.script_folder = os.path.realpath(__file__)
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.Init_GUI()

    def __del__(self):
        pass

    def Init_GUI(self):
        self.layout = QGridLayout()
        
        self.image_loading_layout = QVBoxLayout()
        self.image_preview_layout = QVBoxLayout()
        self.general_controls = QHBoxLayout()
        
        self.image_path = QLineEdit("deformation_correction_pattern/CAL_LSH0802160_760nm.bmp")
        self.loadimage = QPushButton("Load Flatness Correction Image")
        self.loadimage.clicked.connect(self.update_pattern)

        self.pattern_image = ImageWidget()
        
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.image_loading_layout.addWidget(self.image_path)
        self.image_loading_layout.addWidget(self.loadimage)
        self.layout.addLayout(self.image_loading_layout,0,0)

        self.image_preview_layout.addWidget(self.pattern_image)
        self.layout.addLayout(self.image_preview_layout,1,0)

        self.general_controls.addWidget(self.isactive)
        self.layout.addLayout(self.general_controls,2,0)

        #self.mesh_layout.addLayout(self.showmesh_layout)
        self.setLayout(self.layout)



    def update_pattern(self):
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        if self.loaded_file != self.image_path.text():
            img = cv2.imread(self.image_path.text(), -1)
            if img is None:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Wrong path to image")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return
            self.pattern = np.array(img)
            print(self.pattern.shape)
            if len(self.pattern.shape) != 2:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Your image does not use a 8 bits color scheme, check the image and retry")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            if (self.pattern.shape[1] != self.SLM_x_res) or (self.pattern.shape[0] != self.SLM_y_res) :
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Image dimensions don't match with SLM size")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            self.loaded_file = self.image_path.text()
            self.pattern_image.setImage(self.pattern)

    def get_pattern(self):
        self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()


class ImageWidget(QWidget):
    def __init__(self, parent=None):
        super(ImageWidget, self).__init__(parent)
        self.image = None
        self.image_data = None
        self.scale = 1

    def setImage(self, image):
        self.image_data = image.astype(np.uint8)
        self.scale = self.image_data.shape[1]/self.frameGeometry().width()
        disp_size = int(self.image_data.shape[1]//self.scale), int(self.image_data.shape[0]//self.scale)
        img = cv2.resize(self.image_data, disp_size, interpolation=cv2.INTER_CUBIC)
        self.image = QImage(img.data, disp_size[0], disp_size[1], disp_size[0], QImage.Format.Format_Grayscale8)
        self.update()

    def resizeEvent(self,event):
        if self.image is not None:
            self.setImage(self.image_data)

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        if self.image:
            qp.drawImage(QPoint(0, 0), self.image)
        qp.end()


class MeshVisualizer(QThread):
    def __init__(self,parent=None):
        QThread.__init__(self, parent)
        self._active = True


    def showMesh(self):
        while(self._active):
            gmsh.fltk.wait()
            self._active = gmsh.fltk.isAvailable()


    def run(self):
        self._active = True
        t = threading.Thread(target=self.showMesh)
        gmsh.fltk.initialize()
        t.daemon = True
        t.start()
        

    def __del__(self):
        self.wait()
        
    def stop(self):
        self._active = False
        gmsh.fltk.finalize()

class SpotOptimTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager,cameraWindow):
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.cameraWindow = cameraWindow
        self.algorithms = [1,2,3,5,6,7,8,9,11]
        self.algorithms_names = ["MeshAdapt", "Automatic", "Initial mesh only", "Delaunay", "Frontal-Delaunay", "BAMG", "Frontal-Delaunay quads", "Packing paralleograms","Quasi-structured Quad"]
        self.openmeshvisualizer = True
        self.wasINIT = False
        self.th_active = True
        self.points = [0,0,0,0] # 4 points array where to store the points tags
        self.lines = [0,0,0,0] # 4 points array where to store the lines tags
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.scaling_x = 0
        self.scaling_y = 0

        self.init_GMESH()
        self.init_GUI()
        self.visualizer = MeshVisualizer(self)
        
        # Mesh data matrix

        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        self.ids_list = []
        self.frequencies = []
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.cameraWindow)


    def __del__(self):
        self.close_mesh()
        
    def redo_GMESH(self):
        if self.wasINIT: 
            self.SLM_x_res = self.settings_manager.get_X_res()
            self.SLM_y_res = self.settings_manager.get_Y_res()
            gmsh.model.remove_entity_name("SLM Meshing")
            gmsh.model.geo.remove([[1,self.points[0]],[1,self.points[1]],[1,self.points[2]],[1,self.points[3]]],recursive=True)
            gmsh.model.geo.remove([[1,self.lines[0]],[1,self.lines[1]],[1,self.lines[2]],[1,self.lines[3]]],recursive=True)
            #gmsh.model.geo.remove([2,self.contour])
            self.init_GMESH()
            # gmsh.model.geo.remove([2,self.pl])
            #gmsh.model.geo.remove([2,self.contour])

        
    def init_GMESH(self):
        if not self.wasINIT:
            gmsh.initialize()
        self.wasINIT = True
        gmsh.model.add("SLM Meshing")
        lc = 0.1
        self.scaling_x = self.SLM_x_res
        self.scaling_y = self.SLM_y_res
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0,)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.scaling_x, 0, 0,)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.scaling_x, self.scaling_y, 0,)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.scaling_y, 0,)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(1, 2, 1)
        self.lines[1] = gmsh.model.geo.addLine(3, 2, 2)
        self.lines[2] = gmsh.model.geo.addLine(3, 4, 3)
        self.lines[3] = gmsh.model.geo.addLine(4, 1, 4)

        self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([1], 1)

        gmsh.model.geo.synchronize()

        self.field = gmsh.model.mesh.field
        gmsh.model.mesh.field.add("Threshold", 2)
        gmsh.model.mesh.field.setNumber(2, "InField", 1)
        gmsh.model.mesh.field.setNumber(2, "SizeMin", lc / 30)
        gmsh.model.mesh.field.setNumber(2, "SizeMax", lc)
        gmsh.model.mesh.field.setNumber(2, "DistMin", 0.15)
        gmsh.model.mesh.field.setNumber(2, "DistMax", 0.5)

        gmsh.model.mesh.field.add("MathEval", 3)
        
    def change_mesh_algo(self,algorithm):
        gmsh.option.setNumber("Mesh.Algorithm", algorithm)

    def generate_mesh(self,F):
        self.redo_GMESH()
        self.change_mesh_algo(self.algorithms[self.list_algorithms.currentIndex()])
        gmsh.model.mesh.clear()
        gmsh.model.mesh.unpartition()
        gmsh.model.geo.synchronize()
        gmsh.model.mesh.field.setString(3, "F", F)
        self.field.setAsBackgroundMesh(3)
        gmsh.model.mesh.setRecombine(2, self.pl)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.createEdges()
        gmsh.model.mesh.createFaces()


    def load_mesh_ids(self):
        self.ids_list = []
        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):
                tmp = gmsh.model.mesh.getElementsByCoordinates(j, i, 0)[0]
                self.mesh[i,j] = tmp
                self.ids_list.append(tmp)
        self.fixed = gmsh.model.mesh.getElementsByCoordinates(self.SLM_x_res/2, self.SLM_y_res/2, 0)[0]
        self.ids_list = [*set(self.ids_list)]
        self.frequencies = np.zeros(len(self.ids_list))
        freq = 1
        for (i,id) in enumerate(self.ids_list):
            if id == self.fixed:
                self.frequencies[i] = 0
            else:
                self.frequencies[i] = freq 
                freq += 2
        self.fmax = max(self.frequencies)
        self.sampling = 5
        self.deltaT = 1/self.fmax/self.sampling
        self.times = np.arange(0, 1, self.deltaT)

        self.theOptimizer.setIdsList(self.ids_list)
        self.theOptimizer.setFrequencies(self.frequencies)
        self.theOptimizer.setMesh(self.mesh)
        self.theOptimizer.setTimes(self.times)
        self.theOptimizer.setSLMsizes(self.SLM_x_res, self.SLM_y_res)

    def StopOptimization(self):
        self.theOptimizer.stop()

    def RunOptimization(self):
        if not self.theOptimizer.isThreadReady():
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Mesh is not ready!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        self.theOptimizer.initPattern()
        self.theOptimizer.activate()
        self.theOptimizer.start()

        
    def init_GUI(self):
        self.mesh_layout = QVBoxLayout()
        self.showmesh_layout = QHBoxLayout()
        self.meshparams_layout = QHBoxLayout()
        self.algo_controls_layout = QHBoxLayout()

        self.showmeshbutton = QPushButton("Show Mesh")
        self.generatemeshbutton = QPushButton("Generate Mesh")
        self.closemeshbutton = QPushButton("Close Mesh")

        self.parseMeshButton = QPushButton("Parse phases from mesh (slow)")
        self.parseMeshButton.clicked.connect(self.load_mesh_ids)

        self.runAlgorithmButton = QPushButton("Run Algorithm")
        self.runAlgorithmButton.clicked.connect(self.RunOptimization)

        self.stopAlgorithmButton = QPushButton("Stop Algorithm")
        self.stopAlgorithmButton.clicked.connect(self.StopOptimization)

        self.list_algorithms = QComboBox()
        for elem in self.algorithms_names:
            self.list_algorithms.addItem(elem)

        self.showmeshbutton.clicked.connect(self.show_mesh)
        self.meshF = QLineEdit("2.5*((x-0.5)*(x-0.5)+(y-0.5)*(y-0.5))+ 10")

        self.generatemeshbutton.clicked.connect(lambda: self.generate_mesh(self.meshF.text()))
        self.closemeshbutton.clicked.connect(self.close_mesh)

        
        self.meshparams_layout.addWidget(self.meshF)
        self.meshparams_layout.addWidget(self.list_algorithms)
        self.mesh_layout.addLayout(self.meshparams_layout)

        self.mesh_layout.addWidget(self.generatemeshbutton)

        self.showmesh_layout.addWidget(self.showmeshbutton)
        self.showmesh_layout.addWidget(self.closemeshbutton)

        self.algo_controls_layout.addWidget(self.runAlgorithmButton)
        self.algo_controls_layout.addWidget(self.stopAlgorithmButton)

        self.mesh_layout.addLayout(self.showmesh_layout)
        self.mesh_layout.addWidget(self.parseMeshButton)
        self.mesh_layout.addLayout(self.algo_controls_layout)

        self.setLayout(self.mesh_layout)

    def is_active(self):
        return False

    def show_mesh(self):
        # self.th_active = True
        # self.vis_th = threading.Thread(target=self.thread_gmsh_visualizer, args=())
        # self.vis_th.start()
        self.visualizer.run()
        
    def close_mesh(self):
        self.visualizer.stop()
        # self.th_active = False
        # time.sleep(2)
        

class GratingTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.minlmm = 0
        self.maxlmm = 1e-3/(2*self.settings_manager.get_pixel_pitch()*1e-6)
        self.lmm = 0.
        self.angle = 0.
        self.init_GUI()
    def __del__(self):
        pass

    def init_GUI(self):
        self.general_controls_layout = QVBoxLayout()
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating : ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.general_controls_layout.addWidget(self.isactive)
        self.general_controls_layout.addWidget(self.liveupdate)

        self.make_lmm_slider()
        self.make_angle_slider()

        self.make_image_preview()

        self.layout = QGridLayout()
        self.layout.addLayout(self.lmm_layout,0,0)
        self.layout.addLayout(self.angle_layout,1,0)
        self.layout.addLayout(self.image_preview_layout,2,0)
        self.layout.addLayout(self.general_controls_layout,3,0)
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    def needs_updates(self):
        new_vals = [self.angle,self.lmm,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
        for i in range(len(self.lastvals)):
            self.lastvals[i] != new_vals[i]
            return True
        return False

    def make_image_preview(self):
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)

    def make_lmm_slider(self):
        self.lmm_layout = QVBoxLayout()

        self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        self.spin_lmm.setSuffix(' l/mm')
        self.spin_lmm.valueChanged.connect(self.update_lmm)
        self.spin_lmm.setKeyboardTracking(False)
        self.spin_lmm.setSingleStep(0.1)
        self.spin_lmm.setMaximum(self.maxlmm)
        self.spin_lmm.setMinimum(self.minlmm)

        self.lmm_slider = DoubleSlider()
        self.lmm_slider.setGeometry(50,50, 200, 50)
        self.lmm_slider.setMinimum(0)
        self.lmm_slider.setMaximum(self.maxlmm)
        self.lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lmm_slider.setTickInterval(10)
        self.lmm_slider.valueChanged.connect(self.update_lmm)

        self.lmm_layout.addWidget(self.spin_lmm)
        self.lmm_layout.addWidget(self.lmm_slider)

    def make_angle_slider(self):
        self.angle_layout = QVBoxLayout()

        self.spin_angle = QDoubleSpinBox(text="Grating angle")
        self.spin_angle.setSuffix(' π')
        self.spin_angle.valueChanged.connect(self.update_angle)
        self.spin_angle.setKeyboardTracking(False)
        self.spin_angle.setSingleStep(0.1)

        self.angle_slider = DoubleSlider()
        self.angle_slider.setGeometry(50,50, 200, 50)
        self.angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        self.angle_slider.setMaximum(2.)
        self.angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.angle_slider.valueChanged.connect(self.update_angle)

        self.angle_layout.addWidget(self.spin_angle)
        self.angle_layout.addWidget(self.angle_slider)

    def update_lmm(self):
        self.lmm = self.sender().value()
        self.lmm_slider.setValue(self.lmm)
        self.spin_lmm.setValue(self.lmm)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_angle(self):
        self.angle = self.sender().value()
        self.angle_slider.setValue(self.angle)
        self.spin_angle.setValue(self.angle)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()


    def update_pattern(self):
        self.pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.lmm, self.angle*np.pi, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern_image.setImage(self.pattern)
        self.lastvals = [self.angle,self.lmm,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]

    def get_pattern(self):
        if self.pattern is None or self.needs_updates():
            self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()

class DoubleSlider(QSlider):
    doubleValueChanged = pyqtSignal(float)
    def __init__(self, decimals=2, *args, **kargs):
        super(DoubleSlider, self).__init__(Qt.Orientation.Horizontal,*args, **kargs)
        self._multi = 10 ** decimals

        self.valueChanged.connect(self.emitDoubleValueChanged)

    def emitDoubleValueChanged(self):
        value = float(super(DoubleSlider, self).value())/self._multi
        self.doubleValueChanged.emit(value)

    def value(self):
        return float(super(DoubleSlider, self).value()) / self._multi

    def setMinimum(self, value):
        return super(DoubleSlider, self).setMinimum(value * self._multi)

    def setMaximum(self, value):
        return super(DoubleSlider, self).setMaximum(int(value * self._multi))

    def setSingleStep(self, value):
        return super(DoubleSlider, self).setSingleStep(value * self._multi)

    def singleStep(self):
        return float(super(DoubleSlider, self).singleStep()) / self._multi

    def setValue(self, value):
        super(DoubleSlider, self).setValue(int(value * self._multi))
