#!/usr/bin/env python

"""Meshing_process.py: Meshing process class. Used to handle gmesh GUI on OS that do not allow to run gmsh in a separate thread"""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from multiprocessing import Process, freeze_support
import threading

import tkinter as tk
from tkinter import ttk

import time
import gmsh
import numpy as np



class MeshingHandler(Process):
    """Meshing process class. Used to handle gmesh GUI on OS that do not allow to run gmsh in a separate thread.
    This takes care of initializing gmsh and generating the mesh according to the user parameters.
    Given a mesh it parses it in a np.array structure where each element has associated its meshID and returns it to the main thread.

    Attributes:
        eventsDict (dict): Dictionary containing all the events used to communicate with the main thread.
        conditionsDict (dict): Dictionary containing all the conditions used to communicate with the main thread.
        queue (multiprocessing.Queue): Queue used to communicate with the main thread.
        SLM_x_res (int): SLM horizontal resolution.
        SLM_y_res (int): SLM vertical resolution.
        algorithm (int): Meshing algorithm to use.
        F (float): Meshing parameter (equation for meshing, see gmsh guide).
        algorithms (list): List of available meshing algorithms.
        algorithms_names (list): List of available meshing algorithms names.
        isMeshed (bool): True if the meshing process was already done, False otherwise.
        wasINIT (bool): True if gmsh was already initialized, False otherwise.
        Enabled (bool): True if the process should keep running, False otherwise.
    """
    def __init__(self, eventsDict, conditionsDict, queue, SLM_x_res, SLM_y_res, algorithm, F):
        """Constructor for the MeshingHandler class. 
        Initializes SLM parameters and sets the events and conditions used for communication with the main thread and the queue used for data transfer.

        Args:
            eventsDict (dict): Dictionary containing all the events used to communicate with the main thread.
            conditionsDict (dict): Dictionary containing all the conditions used to communicate with the main thread.
            queue (queue): Queue used to communicate with the main thread.
            SLM_x_res (int): SLM resolution in the horizontal direction.
            SLM_y_res (int): SLM resolution in the vertical direction.
            algorithm (int): Meshing algorithm to use.
            F (string): Meshing parameter (equation for meshing, see gmsh guide).
        """
        # freeze support is needed for compiling the executable
        freeze_support()
        Process.__init__(self)
        # Settings running thread parameter (true = running, false = not running)
        self._running = True
        
        self.points = [0,0,0,0] # 4 points array where to store the points tags
        self.lines = [0,0,0,0] # 4 points array where to store the lines tags
        self.mathModel = None
        # Events signals
        self.eventsDict = eventsDict
        self.conditionsDict = conditionsDict

        # Queue for data transfer between processes
        self.queue = queue
        self.loopGUI = False

        # List of meshing algorithms
        # TODO : Make this global such that the GUI has 100% the same order
        self.algorithms = [1,2,3,5,6,7,8,9,11]
        self.algorithms_names = ["MeshAdapt", "Automatic", "Initial mesh only", "Delaunay", "Frontal-Delaunay", "BAMG", "Frontal-Delaunay quads", "Packing paralleograms","Quasi-structured Quad"]

        # Meshing parameters
        self.algorithm = algorithm
        self.F = F
        self.SLM_x_res = SLM_x_res
        self.SLM_y_res = SLM_y_res

        self.fltkInit = False
        self.isMeshed = False

        self.wasINIT = False
        # Settings for multiprocessing (stop the second process once done with the optimization algorithm)
        self.Enabled = True
        
    def checkUserMeshing(self):
        """Checks if the user requested a meshing operation (remesh, closeGUI etc.) and performs it.
        """
        if self.eventsDict['genMesh'].is_set():
            print("generating mesh")
            self.redomesh()
            self.eventsDict['genMesh'].clear()    

        if self.eventsDict['parseMesh'].is_set():
            self.eventsDict['parseMesh'].clear()
            print("parsing mesh")
            self.parseMesh()
            # Once done parsing notify the main thread
            with self.conditionsDict['parsingCond']:
                self.conditionsDict['parsingCond'].notify_all()

        if self.eventsDict['closeGUI'].is_set():
            self.eventsDict['showGUI'].clear()
            self.eventsDict['closeGUI'].clear()
            gmsh.fltk.finalize()
            self.fltkInit=False

        if self.eventsDict['savefile'].is_set():
            self.eventsDict['savefile'].clear()
            self.saveMeshToFile()
            # Once done parsing notify the main thread
            with self.conditionsDict['savefile']:
                self.conditionsDict['savefile'].notify_all()

        if self.eventsDict['loadfile'].is_set():
            self.eventsDict['loadfile'].clear()
            self.loadMeshFromFile()
            # Once done parsing notify the main thread
            with self.conditionsDict['loadfile']:
                self.conditionsDict['loadfile'].notify_all()

        if self.eventsDict['terminate'].is_set():
            self.Enabled = False
            self._running = False




    def run(self):
        """Main function of the MeshingHandler class.
        """
        # Stay dormant till invoked for a new task
        # Wait for waking up event
        self.eventsDict['generalEvent'].wait()
        self.checkUserMeshing()
        # Start thread having the task of checking for new params
        self.eventsDict['generalEvent'].clear()
        while self.Enabled:
            if not self.wasINIT:
                self.init_GMESH()
            # Check if the process should terminate (user closed the interface)
            self.eventsDict['generalEvent'].wait()
            self.checkUserMeshing()
            if self.eventsDict['showGUI'].is_set():
                if not self.fltkInit:
                    gmsh.fltk.initialize()
                    #gmsh.fltk.setCurrentWindow()
                    self.fltkInit = True
                if(gmsh.fltk.isAvailable()):
                    gmsh.fltk.wait(0.01)
                else:
                    # GUI was closed through other means (X)
                    self.eventsDict['closeGUI'].set()
                    self.eventsDict['generalEvent'].clear()
                # Check user requested events (remesh, closeGUI etc.)
            else:
                # Just woke up to check user requested events (remesh, closeGUI etc.)
                # Go back to sleep
                self.eventsDict['generalEvent'].clear()
        # Prepare to terminate
        if gmsh.isInitialized():
            if(gmsh.fltk.isAvailable):
                gmsh.fltk.finalize()
    
    def updatebar(self):
        """Updates the loading bar.
        The loading bar is extremely unnecessary. I had to add it as otherwise gmsh would not appear on top of the main GUI.
        This trick allows the gmsh GUI to appear on top of the main GUI and immediately visible to the user.
        """
        while self.p['value'] < 100:
            self.p['value'] += 10
            # Sleeping time, used to give an impression of loading
            time.sleep(0.05)
        self.root.withdraw()
        self.root.quit()
        return 
    
    def loadMeshFromFile(self):
        """Loads a mesh from a file.
        """
        self.filename = self.queue.get()
        self.getVariablesInQueue()
        # If Gmsh wasn't initialized, do it
        if not self.wasINIT:
            self.showMeshGUI()
            gmsh.initialize()
            self.wasINIT = True
        try:
            # Remove previous model
            # If we have plenty of models in memory, remove them and load the new one
            while not gmsh.model.list() == ['']:
                gmsh.model.remove()
            print(self.filename)
            gmsh.open(self.filename)
            # Set the new model as the active one
            gmsh.model.setCurrent(gmsh.model.list()[0])
            print(gmsh.model.list())
            #self.checkLoadedMeshSize()
            self.queue.put(True)
        except:
            self.queue.put(False)
            return
    
    # TODO: This part should check that the mesh actually would fit the slm sizes
    def checkLoadedMeshSize(self):
        """Checks if the loaded mesh fits the SLM size.
        
        Todo:
            * This function is a work in progress, I did not find an elegant way of getting the size of a gmsh mesh (and check that is actually 2D). For now it assumes that the user knows what they're doing...
        """
        entities = gmsh.model.getEntities()
        for e in entities:
            boundary = gmsh.model.getBoundary([e])
            elemTypes, elemTags, elemNodeTags = gmsh.model.mesh.getElements(e[0], e[1])
            print(" - boundary entities " + str(boundary))
            for t in elemTypes:
                name, dim, order, numv, parv, _ = gmsh.model.mesh.getElementProperties(t)
                print(" - Element type: " + name + ", order " + str(order) + " (" +str(numv) + " nodes in param coord: " + str(parv) + ")")



    def saveMeshToFile(self):
        """Saves the mesh to a file.
        """
        self.filename = self.queue.get()
        if self.isMeshed:
            try:
                print("saving mesh")
                print(self.filename)
                gmsh.write(self.filename)
                self.queue.put(True)
            except:
                print("something went wrong")
                self.queue.put(False)
        else:
            print("wasn't meshed")
            self.queue.put(False)
    
    def showMeshGUI(self):
        """Shows the loading GUI. This is not necessary, but it allows the gmsh GUI to appear on top of the main GUI.
        """
        # Loading bar size
        w = 200 # width for the Tk root
        h = 20 # height for the Tk root

        # Make it appear at the center of the screen 
        self.root = tk.Tk()
        self.root.title("Loading GMESH")

        ws = self.root.winfo_screenwidth() # width of the screen
        hs = self.root.winfo_screenheight() # height of the screen

        # calculate x and y coordinates for the Tk root window
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.p = ttk.Progressbar(self.root, orient="horizontal", length=200, mode="determinate",
                    takefocus=True, maximum=100)
        self.p['value'] = 0
        self.p.pack()
        self.t1 = threading.Thread(target=self.updatebar)#, args=(self,))
        self.t1.start()
        self.root.mainloop()
        # Join process
        self.t1.join()
        


    def redomesh(self):
        """Redoes the meshing operation.
        """
        # Reload new mesh variables
        self.getVariablesInQueue()
        self.reconstructMesh()
        # set new algorithm
        gmsh.option.setNumber("Mesh.Algorithm", self.algorithms[self.algorithm])
        #self.change_mesh_algo()
        
        #gmsh.model.mesh.unpartition()
        gmsh.model.mesh.field.setString(self.mathModel, "F", self.function)
        self.field.setAsBackgroundMesh(self.mathModel) 
        #gmsh.model.mesh.setRecombine(2, self.pl)
        # To make quadrangles instead of triangles
        gmsh.model.mesh.setRecombine(2,self.pl)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.createEdges()
        gmsh.model.mesh.createFaces()
        # Tells the saving function we actually have a Mesh to save
        self.isMeshed = True

    def reconstructMesh(self):
        """Deletes anre reconstructs the mesh + geometry.
        """
        if self.wasINIT: 
            #gmsh.model.remove_entity_name("SLM Meshing")
            if self.mathModel is not None:
                gmsh.model.mesh.field.remove(self.mathModel)
            gmsh.model.geo.remove([[1,self.points[0]],[1,self.points[1]],[1,self.points[2]],[1,self.points[3]]],recursive=True)
            gmsh.model.geo.remove([[1,self.lines[0]],[1,self.lines[1]],[1,self.lines[2]],[1,self.lines[3]]],recursive=True)
            self.mathModel = None
            self.threshold=None
            gmsh.model.remove()
            gmsh.model.mesh.clear()
        self.init_GMESH()

    def init_GMESH(self):
        """Initializes gmsh + creates basic geometry for the meshing.
        """
        if not self.wasINIT:
            self.showMeshGUI()
            gmsh.initialize()
        self.wasINIT = True
        gmsh.model.add("SLM Meshing")
        lc = 0.5*max(self.SLM_x_res,self.SLM_y_res)
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0, meshSize = lc)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.SLM_x_res, 0, 0, meshSize = lc)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.SLM_x_res, self.SLM_y_res, 0, meshSize = lc)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.SLM_y_res, 0, meshSize = lc)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(self.points[0], self.points[1])
        self.lines[1] = gmsh.model.geo.addLine(self.points[1], self.points[2])
        self.lines[2] = gmsh.model.geo.addLine(self.points[2], self.points[3])
        self.lines[3] = gmsh.model.geo.addLine(self.points[3], self.points[0])

        self.contour = gmsh.model.geo.addCurveLoop([self.lines[0], self.lines[1],self.lines[2],self.lines[3]])
        #self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([self.contour])
        gmsh.model.geo.synchronize()
        self.field = gmsh.model.mesh.field
        self.mathModel = gmsh.model.mesh.field.add("MathEval")

    def parseMesh(self):
        """Parses the mesh and returns it to the main thread.
        Converts from a gmsh to a numpy array where each element has associated its meshID.
        """

        print("parsing mesh")
        self.ids_list = []
        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        print("getting nodes")
        print(gmsh.model.mesh.getNodes())
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):  
                tmp = gmsh.model.mesh.getElementsByCoordinates(j, self.SLM_y_res-i, 0,dim=2)[0]
                self.mesh[i,j] = tmp
                self.ids_list.append(tmp)
        self.ids_list = [*set(self.ids_list)]
        self.queue.put(self.mesh)
        self.queue.put(self.ids_list)
        print("done parsing mesh")
    
        

    def getVariablesInQueue(self):
        """Loads parameters from the queue (from the main thread).
        """
        self.SLM_x_res = self.queue.get()
        self.SLM_y_res = self.queue.get()
        self.algorithm = self.queue.get()
        self.function = self.queue.get()
