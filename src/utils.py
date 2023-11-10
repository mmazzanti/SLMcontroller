
from PyQt6.QtWidgets import QSlider, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QThread, QRunnable, pyqtSlot
from PyQt6.QtGui import QImage, QPainter

import cv2
import numpy as np
import gmsh


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

class DoubleSlider(QSlider):
    doubleValueChanged = pyqtSignal(float)
    def __init__(self, decimals=3, *args, **kargs):
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


class MeshVisualizer(QRunnable):
    def __init__(self, *args, **kwargs):
        super(MeshVisualizer, self).__init__()
        gmsh.fltk.initialize()
        self._active = True
    # def __init__(self,parent=None):
    #     QThread.__init__(self, parent)


    # def showMesh(self):
    #     gmsh.fltk.initialize()
    #     while(self._active):
    #         gmsh.fltk.wait()
    #         #gmsh.fltk.update()
    #         #gmsh.fltk.awake("update")
    #         print("running")
    #         self._active = gmsh.fltk.isAvailable()
    #     gmsh.fltk.finalize()
        
    def run(self):
        #t = threading.Thread(target=self.showMesh)
        #gmsh.fltk.initialize()
        #gmsh.fltk.run()
        while self._active:
            gmsh.fltk.wait()
            #self.wait()
        # t.daemon = True
        # t.start()
        
    def highlight_zone(self,probe_zone,reference_zone):
        #gmsh.fltk.select_elements([])
        #gmsh.model.mesh.get_element
        pass
        #select_elements([probe_zone,reference_zone])

    # def __del__(self):
    #     self.wait()
        
    def stop(self):
        gmsh.fltk.finalize()
        self.wait(2)
        self._active = False
        self.exit(0)