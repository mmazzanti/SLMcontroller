#!/usr/bin/env python

"""CameraFunctions.py: Contains the functions and classes needed to control the camera acquisition."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

import time
import numpy as np
import os

from PIL import Image
from io import BytesIO

import cv2, queue, threading
from PyQt6.QtCore import Qt, QThread,pyqtSignal
from PyQt6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QGroupBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget, QSlider,QLabel,QGridLayout,QDoubleSpinBox)
from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot

from flask import jsonify, send_file, abort

class RenderingThread(QThread):
    updateFrame = Signal(QImage)

    def __init__(self, name, parent=None):
        QThread.__init__(self, parent)
        #self.trained_file = None
        self.cap = cv2.VideoCapture(name)
        self.q = queue.Queue()

        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.5)
        self.cap.set(cv2.CAP_PROP_FPS, 30.0)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, 10)
        # Hardcoded max resolution (TODO : try to get the max resolution from the camera)
        cols, rows = 2592,1944,
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cols)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rows)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1);
        


        self.video = True
        self.active = True
        self.zoomed = False
        self.X = 100 #1280
        self.Y = 100 #720
        self.r = 100

    # makes a live feed of the camera 

    def start(self):
        if self.active :
            t = threading.Thread(target=self._reader)
            t.daemon = True
            t.start()

    def _reader(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.q.empty():
                try:
                    self.q.get_nowait()   # discard previous (unprocessed) frame
                except queue.Empty:
                    pass
            self.q.put(frame)
            if self.video:
                pos_ori = (self.X, self.Y)
                pos_end = (self.X+self.r, self.Y+self.r)
                color = (0, 255, 0)
                if self.zoomed:
                    frame = frame[self.Y:(self.Y + self.r), self.X:(self.X + self.r)]            
                else:
                    cv2.rectangle(frame, pos_ori, pos_end, color, 2)

                # zooms in into the square, needs to be after rectangle is made otherwise it will see the frame as a different size

                self.update_image(frame)
        self.active=False


    def read(self):
        return self.q.get()
    
    def start_video(self):
        self.video = True

    def stop_video(self):
        self.video = False

    def die(self):
        self.active = False
        self.cap.release()

    def update_image(self,frame):
        color_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Creating and scaling QImage
        h, w, ch = color_frame.shape
        img = QImage(color_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        scaled_img = img.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)

        # Emit signal
        self.updateFrame.emit(scaled_img)


    def save_picture(self,frame):
        print("saving")
        if  not os.path.exists("Img"):
            os.makedirs("Img")
        self.update_image(frame)
        timestamp = time.strftime("%d-%b-%Y-%H_%M_%S")
        img_name = "Img/frame_{}".format(timestamp)
        np.array(frame)
        cv2.imwrite(img_name+".png", frame)
        np.save(img_name,frame)        

    def take_picture(self):
        self.video = False
        frame = self.read()
        if self.zoomed:
            frame = frame[self.Y:(self.Y + self.r), self.X:(self.X + self.r)]
        return frame

    # moves the square position as a function of the slides 
    def move_square(self, x,y,r):
        self.X = x
        self.Y = y
        self.r = r

    def photo(self):
        self.pictureCounter = 1

    # if zoom button is pushed -> counter = 1 -> zoom into the square
    def zoom_video(self):
        self.zoomed = True

    # if zoom OUT button is pushed -> counter = 0 -> zoom out to full image 
    def zoom_out_video(self):
        self.zoomed = False



class CameraWindow(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)

        self.camera_resX = 2592
        self.camera_resY = 1944

        # Title and dimensions
        self.setWindowTitle("Camera")
        if self.camera_resX > 640:
            scaling = self.camera_resX/640
            self.setGeometry(0, 0, int(self.camera_resX/scaling), int(0.78*self.camera_resX/scaling))
        else :
            self.setGeometry(0, 0, 640, 500)
        camera_NUM = 0
        # slides for square, X position
        self.slider_layout = QVBoxLayout()
        self.pos_sliderX = QSlider(Qt.Orientation.Horizontal, self)
        self.pos_sliderX.setGeometry(500,50, 200, 50)
        self.pos_sliderX.setMinimum(0)
        self.pos_sliderX.setMaximum(2048)
        self.pos_sliderX.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pos_sliderX.setTickInterval(5000)
        self.pos_sliderX.setValue(100)
        
        # Y position
        self.pos_sliderY = QSlider(Qt.Orientation.Horizontal, self)
        #self.pos_slider.setGeometry(50,50, 200, 50)
        self.pos_sliderY.setMinimum(0)
        self.pos_sliderY.setMaximum(1536)
        self.pos_sliderY.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pos_sliderY.setTickInterval(5000)
        self.pos_sliderY.setValue(100)
        
        # Size of the square 
        self.pos_slider_r = QSlider(Qt.Orientation.Horizontal, self)
        #self.pos_slider.setGeometry(50,50, 200, 50)
        self.pos_slider_r.setMinimum(0)
        self.pos_slider_r.setMaximum(2048)
        self.pos_slider_r.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pos_slider_r.setTickInterval(5000)
        self.pos_slider_r.setValue(100)

        # connect the slider to the update which will change the Move square function coordinates
        self.pos_sliderX.valueChanged.connect(self.update)
        self.pos_sliderY.valueChanged.connect(self.update)
        self.pos_slider_r.valueChanged.connect(self.update)

        self.slider_layout.addWidget(self.pos_sliderX)
        self.slider_layout.addWidget(self.pos_sliderY)
        self.slider_layout.addWidget(self.pos_slider_r)
        self.layout = QGridLayout()

        # Main menu bar
        self.menu = self.menuBar()
        self.menu_file = self.menu.addMenu("File")
        #exit = QAction("Exit", self, triggered=QApplication.quit)
        #self.menu_file.addAction(exit)

        # Create a label for the display camera
        self.label = QLabel(self)
        self.label.setFixedSize(640, 480)

        # Thread in charge of updating the image
        #self.th.finished.connect(self.close)
        self.th = RenderingThread(camera_NUM)
        self.th.updateFrame.connect(self.setImage)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        self.button1 = QPushButton("Start")
        self.button2 = QPushButton("Stop/Close")
        self.button_frame = QPushButton('Acquire Frame')
        self.zoom_button = QPushButton('Zoom')
        self.unzoom_button = QPushButton('Zoom Out')

        buttons_layout.addWidget(self.button2)
        buttons_layout.addWidget(self.button1)
        buttons_layout.addWidget(self.button_frame)
        buttons_layout.addWidget(self.zoom_button)
        buttons_layout.addWidget(self.unzoom_button)


        right_layout = QHBoxLayout()
        right_layout.addLayout(buttons_layout, 1)

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addLayout(right_layout)
        layout.addLayout(self.slider_layout)

        # Central widget
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        # Connections
        self.button1.clicked.connect(self.start)
        self.button2.clicked.connect(self.kill_thread)
        self.button2.setEnabled(False)

        self.button_frame.clicked.connect(self.click_photo)
        self.zoom_button.clicked.connect(self.zoom)
        self.unzoom_button.clicked.connect(self.unzoom)



    def closeEvent(self, event):
        self.th.die()
        del self.th


    def take_picture(self):
        return self.th.take_picture()

    def getCameraIMG(self):
        img = Image.fromarray(self.take_picture())
        # create file-object in memory
        file_object = BytesIO()
        # write PNG in file-object
        img.save(file_object, 'PNG')
        # move to beginning of file so `send_file()` it will read from start 
        file_object.seek(0)
        return send_file(file_object,mimetype='image/PNG',as_attachment=False,download_name='pattern.png')
    

    @Slot()
    # sends a message to the zoom function if the "Zoom" button is pushed
    def zoom(self):
        self.th.zoom_video()
        print("zoom is pushed")

    @Slot()
     # sends a message to the zoom OUT function if the "Zoom Out" button is pushed
    def unzoom(self):
        self.th.zoom_out_video()
        print("zoom out is pushed")

    @Slot()
    # updates the position of the squares with the slider values
    def update(self):
        self.th.move_square(self.pos_sliderX.value(),self.pos_sliderY.value(), self.pos_slider_r.value() )
        

    @Slot()
    def kill_thread(self):
        print("Finishing...")
        self.button2.setEnabled(False)
        self.button1.setEnabled(True)
        #self.th.cap.release()
        self.th.stop_video()
        #cv2.destroyAllWindows()
        #self.th.terminate()
        # Give time for the thread to finish
        time.sleep(1)

    @Slot()
    def start(self):
        print("Starting...")
        self.th.start()
        self.button2.setEnabled(True)
        self.button1.setEnabled(False)
        self.th.start_video()

    @Slot(QImage)
    def setImage(self, image):
        self.label.setPixmap(QPixmap.fromImage(image))
    
    @Slot()
    # takes a photo of the square
    def click_photo(self):
        #self.th.photo()        
        self.th.save_picture(self.th.take_picture())
        print("Finishing...")
        self.button2.setEnabled(False)
        self.button1.setEnabled(True)

    def setCameraRes(self,resX, resY):
        self.camera_resX = resX
        self.camera_resY = resY