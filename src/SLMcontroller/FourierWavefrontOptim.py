#!/usr/bin/env python

"""FourierWavefrontOptim.py: Uses the camera to correct for aberrations using a Fourier-based algorithm. The algorithm is based on: https://www.frontiersin.org/articles/10.3389/fnano.2022.998656/full """

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QMessageBox, QLineEdit, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt, QThread

import os
import SLMcontroller.utils as utils
import gmsh
import numpy as np
import time

#!/usr/bin/env python

"""OpticalElement.py: Generates a dialog used to load an optical element."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

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
        self.visualizer = utils.MeshVisualizer(self)
        
        # Mesh data matrix

        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        self.ids_list = []
        self.frequencies = []
        self.theOptimizer = OptimizerAlgorithmFourier(self.hologram_manager,self.cameraWindow)


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
        self.sampling = 1
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
        #self.theOptimizer.initPattern()
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
        
class OptimizerAlgorithmFourier(QThread):

    def __init__(self,hologram_manager,cameraWindow):
        QThread.__init__(self)
        self.pattern = None
        self.frequencies = None
        self.cameraWindow = cameraWindow
        self.times = None
        self.mesh = None
        self.freqs = None
        self.SLM_x_res = None
        self.SLM_y_res = None
        self.ids_list = None
        self.hologram_manager = hologram_manager
        self._active = False
        self.isPhaseReady = False

    def __del__(self):
        self.wait()

    def run(self):
        self.initPattern()
        print("Done with init ...")
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
        print("Initializating ... ")
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res))
        self.freqs = np.zeros((self.SLM_y_res,self.SLM_x_res))
        self.random_phases = np.rint(np.random.rand(len(self.ids_list))*255)
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):
                tmp = self.ids_list.index(self.mesh[i,j])
                self.pattern[i,j] = self.random_phases[tmp]
                self.freqs[i,j] = self.frequencies[tmp]
        print("... done")


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
        print("generating new phases ... ")
        self.pattern += (self.freqs*self.times[time]*256)%256
        print("... done")
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         self.pattern[i,j] += (self.frequencies[self.ids_list.index(self.mesh[i,j])]*self.times[time]*(2*np.pi)*256)%256

