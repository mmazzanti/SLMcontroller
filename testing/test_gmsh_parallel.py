from collections.abc import Callable, Iterable, Mapping
from multiprocessing import Process, Condition
from typing import Any
from multiprocessing import RLock, Event, Queue
import gmsh
import signal, os
import threading
import time
import numpy as np




# theLock = RLock()
# condition = Condition(lock = theLock)

# custom process class
class MeshingHandler(Process):
    # override the run function
    def __init__(self, generalEvent, showGUI, genMesh, parseMesh, queue, SLM_x_res, SLM_y_res, algorithm, F):
    # execute the base constructor
        print('starting process')
        Process.__init__(self)
        # Settings running thread parameter (true = running, false = not running)
        self._running = True

        # Events signals
        self.showGUI = showGUI
        self.genMeshE = genMesh
        self.generalEvent = generalEvent

        # Parse mesh is actually a condition as it needs synchronization between processes
        self.parseMeshE = parseMesh

        # List of meshing algorithms
        # TODO : Make this global such that the GUI has 100% the same order
        self.algorithms_names = ["MeshAdapt", "Automatic", "Initial mesh only", "Delaunay", "Frontal-Delaunay", "BAMG", "Frontal-Delaunay quads", "Packing paralleograms","Quasi-structured Quad"]

        # Queue for data transfer between processes
        self.queue = queue

        # Meshing parameters
        self.algorithm = algorithm
        self.F = F
        self.SLM_size_X = SLM_x_res
        self.SLM_size_Y = SLM_y_res

        self.wasINIT = False
        # Settings for multiprocessing (stop the second process once done with the optimization algorithm)
        self.Enabled = True
        
        
    def run(self):
        t1 = threading.Thread(target=self.checkParams, args=(10,))
        t1.start()
        while self.Enabled:
        #self.condition = Condition(lock = theLock)
            self.showGUI.wait()
            self.init_GMESH()
            self.mathModel = gmsh.model.mesh.field.add("MathEval")
            gmsh.fltk.run()
            gmsh.finalize()
            self.showGUI.clear()
        #Once we're done with the optimization process we can kill the settings handling process
        self._running = False


    def redomesh(self):
        # Reload new mesh variables
        self.getVariablesInQueue()
        self.reconstructMesh()
        # set new algorithm
        self.change_mesh_algo(self.algorithms[self.algorithm])
        
        #gmsh.model.mesh.unpartition()
        gmsh.model.mesh.field.setString(self.mathModel, "F", self.function)
        self.field.setAsBackgroundMesh(self.mathModel)
        #gmsh.model.mesh.setRecombine(2, self.pl)
        # To make quadrangles instead of triangles
        gmsh.model.mesh.setRecombine(2,self.pl)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.createEdges()
        gmsh.model.mesh.createFaces()
        print("redoing mesh : ", self.algorithm, self.function)

    def reconstructMesh(self):
        if self.wasINIT: 
            gmsh.model.remove_entity_name("SLM Meshing")
            gmsh.model.geo.remove([[1,self.points[0]],[1,self.points[1]],[1,self.points[2]],[1,self.points[3]]],recursive=True)
            gmsh.model.geo.remove([[1,self.lines[0]],[1,self.lines[1]],[1,self.lines[2]],[1,self.lines[3]]],recursive=True)
            #gmsh.model.geo.remove([2,self.contour])
            #gmsh.model.mesh.field.remove(self.threshold)
            gmsh.model.mesh.field.remove(self.mathModel)
            self.mathModel = None
            self.threshold=None
            gmsh.model.mesh.clear()
            self.init_GMESH()

    def init_GMESH(self):
        if not self.wasINIT:
            gmsh.initialize()
        self.wasINIT = True
        gmsh.model.add("SLM Meshing")
        lc = 0.5*max(self.SLM_x_res,self.SLM_y_res)
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0, meshSize = lc)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.SLM_x_res, 0, 0, meshSize = lc)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.SLM_x_res, self.SLM_y_res, 0, meshSize = lc)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.SLM_y_res, 0, meshSize = lc)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(1, 2, 1)
        self.lines[1] = gmsh.model.geo.addLine(3, 2, 2)
        self.lines[2] = gmsh.model.geo.addLine(3, 4, 3)
        self.lines[3] = gmsh.model.geo.addLine(4, 1, 4)

        self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([1], 1)

        gmsh.model.geo.synchronize()
        self.field = gmsh.model.mesh.field

    def parseMesh(self):
        with self.parseMesh:
            print("parsing mesh")
            self.ids_list = []
            self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
            for i in range(0,self.SLM_y_res):
                for j in range(0,self.SLM_x_res):  
                    tmp = gmsh.model.mesh.getElementsByCoordinates(j, self.SLM_y_res-i, 0,dim=2)[0]
                    self.mesh[i,j] = tmp
                    self.ids_list.append(tmp)
            self.ids_list = [*set(self.ids_list)]
            self.queue.put(self.mesh)
            self.queue.put(self.ids_list)
            print("done parsing mesh")
            self.parseMesh.notify_all()
    
        

    def getVariablesInQueue(self):
        self.SLM_size_X = self.queue.get()
        self.SLM_size_Y = self.queue.get()
        self.algorithm = self.queue.get()
        self.function = self.queue.get()

    def checkParams(self,randomarg):
        print("blah")
        while self._running:
            print("Running")
            self.generalEvent.wait()
            if self.genMeshE.is_set():
                self.genMeshE.clear()
                self.redomesh()

            if self.parseMeshE.is_set():
                self.parseMeshE.clear()
                self.parseMesh()



            print("notified")
            self.redomesh()
            self.genMeshE.clear()



def killGUIvisualizerProcess(queue, event):
    queue.put(False)
    event.set()


def putMeshInQueue(queue, mesh):
    queue.put(mesh)

def getMeshInQueue(queue):
    return(queue.get())

def parseMesh(condition, queue, mesh):
    # Waits for second process to finish parsing the mesh
    with condition:
        condition.wait()
    # Returns the mesh
    return(queue.get())


def putVariablesInQueue(queue, SLM_size_X, SLM_size_Y, algorithm, function, event, notify):
    # Tells the second process the type of event
    event.set()
    queue.put(SLM_size_X)
    queue.put(SLM_size_Y)
    queue.put(algorithm)
    queue.put(function)
    # Notifies the second process that data is ready
    notify.set()



if __name__ == '__main__':
    # Parse mesh has to be done in a synchronized way. The main process cannot proceed without the mesh being generated
    parseMesh = Condition()

    genMesh = Event()
    generalEvent = Event()
    genMesh = Event()
    parseMesh = Event()

    showGUI = Event()
    queue = Queue()

    process = MeshingHandler(genMesh,parseMesh,queue)
    # start the process
    #theLock.acquire()
    print('hello still going here')
    process.start()
    time.sleep(10)

    print("notifying")
    genMesh.set()
    time.sleep(2)
    print("waiting for process to remesh")

    putVariablesInQueue(queue, SLM_size_X, SLM_size_Y, algorithm, F)
    queue.put("Delanauy")
    queue.put("F(x) = x^2")
    
    genMesh.set()
    time.sleep(10)

    process.join()
    #p = Process(target=task, args=(lock))

    #p = Process(target=f, args=('bob',))
    #p.start()
    # print('hello still going here')
    # p2 = Process(target=f2, args=('bob',))
    # p2.start()
    # print('hello still going here again')

    # p.join()
    # p2.join()

'''
    def run(self):
        # block for a moment
        gmsh.initialize()
        # display a message
        lc = 0.5*max(self.SLM_x_res,self.SLM_y_res)
        self.scaling_x = self.SLM_x_res
        self.scaling_y = self.SLM_y_res
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0, meshSize = lc)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.scaling_x, 0, 0, meshSize = lc)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.scaling_x, self.scaling_y, 0, meshSize = lc)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.scaling_y, 0, meshSize = lc)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(1, 2, 1)
        self.lines[1] = gmsh.model.geo.addLine(3, 2, 2)
        self.lines[2] = gmsh.model.geo.addLine(3, 4, 3)
        self.lines[3] = gmsh.model.geo.addLine(4, 1, 4)

        self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([1], 1)
        print('Init GMSH')













def f(name):
        # Initialize gmsh:
    gmsh.initialize()
    
    # cube points:
    lc = 1e-2
    point1 = gmsh.model.geo.add_point(0, 0, 0, lc)
    point2 = gmsh.model.geo.add_point(1, 0, 0, lc)
    point3 = gmsh.model.geo.add_point(1, 1, 0, lc)
    point4 = gmsh.model.geo.add_point(0, 1, 0, lc)
    point5 = gmsh.model.geo.add_point(0, 1, 1, lc)
    point6 = gmsh.model.geo.add_point(0, 0, 1, lc)
    point7 = gmsh.model.geo.add_point(1, 0, 1, lc)
    point8 = gmsh.model.geo.add_point(1, 1, 1, lc)
    
    # Create the relevant Gmsh data structures 
    # from Gmsh model.
    gmsh.model.geo.synchronize()
    
    # Generate mesh:
    gmsh.model.mesh.generate()
    
    # Write mesh data:
    #gmsh.write("GFG.msh")
    
    # Creates  graphical user interface

    gmsh.fltk.run()
    
    # It finalize the Gmsh API
    gmsh.finalize()
    print('hello', name)

def f2(name):
    gmsh.initialize()
 
    # cube points:
    lc = 1e-2
    point1 = gmsh.model.geo.add_point(0, 0, 0, lc)
    point2 = gmsh.model.geo.add_point(1, 0, 0, lc)
    point3 = gmsh.model.geo.add_point(1, 1, 0, lc)
    point4 = gmsh.model.geo.add_point(0, 1, 0, lc)
    point5 = gmsh.model.geo.add_point(0, 1, 1, lc)
    point6 = gmsh.model.geo.add_point(0, 0, 1, lc)
    point7 = gmsh.model.geo.add_point(1, 0, 1, lc)
    point8 = gmsh.model.geo.add_point(1, 1, 1, lc)
    
    # Edge of cube:
    line1 = gmsh.model.geo.add_line(point1, point2)
    line2 = gmsh.model.geo.add_line(point2, point3)
    line3 = gmsh.model.geo.add_line(point3, point4)
    line4 = gmsh.model.geo.add_line(point4, point1)
    line5 = gmsh.model.geo.add_line(point5, point6)
    line6 = gmsh.model.geo.add_line(point6, point7)
    line7 = gmsh.model.geo.add_line(point7, point8)
    line8 = gmsh.model.geo.add_line(point8, point5)
    line9 = gmsh.model.geo.add_line(point4, point5)
    line10 = gmsh.model.geo.add_line(point6, point1)
    line11 = gmsh.model.geo.add_line(point7, point2)
    line12 = gmsh.model.geo.add_line(point3, point8)
    
    # faces of cube:
    face1 = gmsh.model.geo.add_curve_loop([line1, line2, line3, line4])
    face2 = gmsh.model.geo.add_curve_loop([line5, line6, line7, line8])
    face3 = gmsh.model.geo.add_curve_loop([line9, line5, line10, -line4])
    face4 = gmsh.model.geo.add_curve_loop([line9, -line8, -line12, line3])
    face5 = gmsh.model.geo.add_curve_loop([line6, line11, -line1, -line10])
    face6 = gmsh.model.geo.add_curve_loop([line11, line2, line12, -line7])
    
    # surfaces of cube:
    gmsh.model.geo.add_plane_surface([face1])
    gmsh.model.geo.add_plane_surface([face2])
    gmsh.model.geo.add_plane_surface([face3])
    gmsh.model.geo.add_plane_surface([face4])
    gmsh.model.geo.add_plane_surface([face5])
    gmsh.model.geo.add_plane_surface([face6])
    
    # Create the relevant Gmsh data structures 
    # from Gmsh model.
    gmsh.model.geo.synchronize()
    
    # Generate mesh:
    gmsh.model.mesh.generate()
    
    # Write mesh data:
    gmsh.write("GFG.msh")
    
    # Creates  graphical user interface

    gmsh.fltk.run()
    
    # It finalize the Gmsh API
    gmsh.finalize()


'''