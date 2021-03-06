from tkinter import *
from tkinter import ttk, filedialog
import cv2
from time import sleep
import imutils
import os
import datetime
import numpy as np
import sys
from threading import Thread, Lock
from picamera.array import PiRGBArray
from picamera import PiCamera
from ObjectTracker import ObjectTracker
from CameraControl import CameraControl
from RemoteControl import RemoteControl
from imutils.video import VideoStream, FPS

#globals from GUI
global stage
stage = 0
global directory
directory = None
global distance
distance = 0

global displayMap
displayMap = False
global mapFrame
mapFrame = None
global initBB
initBB = None
global selectROI
selectROI = False
global lassoBB
lassoBB = None
global laserList
laserList = None
global selectLasso
selectLasso = False
global lassoReady
lassoReady = False

#GUI creation
class GUI:
    def __init__(self, app, tracking_source):

        self.app = app

        # window
        self.window = Tk()
        self.window.title("LassoCam Setup")
        self.window.geometry('250x350')

        # progress bar
        style = ttk.Style()
        style.theme_use('default')
        style.configure("black.Horizontal.TProgressbar", background='black')
        self.bar = ttk.Progressbar(self.window, length=250, style='black.Horizontal.TProgressbar')
        self.bar['value'] = 0
        self.bar.grid(column=0, row=0)

        # labels
        self.lbl1 = Label(self.window, text="LassoCam", font=("Arial Bold", 12))
        self.lbl1.grid(column=0, row=1)
        self.lbl2 = Label(self.window, text="Welcome to the LassoCam\ncamera calibration program\nclick continue to proceed", font=("Arial Italic", 12))
        self.lbl2.grid(column=0, row=2, pady=(100,0))

        # text entry
        self.txt = Entry(self.window,width=10)

        # button
        self.btn = Button(self.window, text="Continue", command=self.next_stage)
        self.btn2 = Button(self.window, text="Change Path", command=self.change_path)
        self.btn.grid(column=0, row=4, pady=(90,10))

        
        while True:
            global mapFrame
            global displayMap
            global initBB
            global lassoBB
            global selectROI
            global selectLasso
            global lassoReady

            if displayMap:
                cv2.imshow("Frame", mapFrame)
                cv2.waitKey(1) & 0xFF

            if selectROI:
                initBB = cv2.selectROI("Make a Selection", mapFrame, fromCenter=False, showCrosshair=True)
                cv2.destroyWindow("Make a Selection")
                self.app.select_presenter()
                self.app.start_tracker()
                selectROI = False

            if selectLasso:
                lassoBB = cv2.selectROI("Make a Selection", mapFrame, fromCenter=False, showCrosshair=True)
                cv2.destroyWindow("Make a Selection")
                self.app.select_lasso()
                lassoReady = True
                selectLasso = False

            self.window.update_idletasks()
            self.window.update()




        # run window
 
    #GUI mapping
    def next_stage(self):
        global directory
        global distance
        global stage 
        if stage == 2 and self.txt.get().isdigit() is False:
            print("Need an integer.")
            return

        stage = stage + 1


        if stage == 1:
            self.bar['value'] = 20 
            self.lbl1.configure(text="Setup Camera")
            self.lbl2.configure(text="Place the camera so the\nentire stage is shown,\nthen click continue")
            self.txt.grid_forget()

            # Display map camera
            self.app.start_map()
        elif stage == 2:
            self.bar['value'] = 40
            self.lbl1.configure(text="Measuring Distance")
            self.lbl2.configure(text="Enter the distance (in inches)\nfrom the camera to the stage,\nthen click continue")
            self.txt.grid(column=0, row=3)
            self.txt.focus()
            self.btn.grid(column=0, row=4, pady=(61,10))
        elif stage == 3:
            self.bar['value'] = 60
            distance = int(self.txt.get())
            self.app.camControl.calibrate(distance, 0)
            self.lbl1.configure(text="Person Selection")
            self.lbl2.configure(text="Select the torso of the\nperson you'd like to track,\n hit the enter key, \nthen click continue")
            self.btn.grid(column=0, row=4, pady=(80,10))
            self.txt.grid_forget()

            # Select Presenter
            global selectROI
            selectROI = True

        elif stage == 4:
            self.bar['value'] = 80
            self.lbl1.configure(text="Save Destination")
            self.lbl2.configure(text="Choose where to save the video\nafter it has been recorded,\nthen click continue", font=("Arial, 12"))
            self.btn2.grid(column=0, row=4, pady=(100,10))
            self.btn.grid(column=0, row=5, pady=(0,20))
            self.change_path()
            self.lbl2.configure(font=("Arial, 7"))
        elif stage == 5:
            self.btn2.grid_forget()
            self.bar['value'] = 100
            self.lbl1.configure(text="Begin Recording")
            self.lbl2.configure(text="Click the button to exit setup\nand immediately begin recording\nusing LassoCam technology", font=("Arial, 10"))
            self.btn.configure(text="Start", command=self.next_stage)
            self.btn.grid(column=0, row=4, pady=(90,10))

        elif stage == 6:
            self.app.camControl.start_recording(directory)
            self.bar['value'] = 100
            self.lbl1.configure(text="Begin Recording")
            self.lbl2.configure(text="Click the button to stop recording")
            self.btn.configure(text="Stop", command=self.next_stage)
            self.btn2.grid(column=0, row=4, pady=(100,10))
            self.btn2.configure(text="Lasso", command=self.app.select_lasso)
            self.btn.grid(column=0, row=5, pady=(0,20))

        else:
            self.app.camControl.stop_recording()
            self.app.stop_tracker()
            displayMap = False
            print(" ")
            print("--- SETUP OVER ---")
            print(directory)
            print(distance)
            print(" ")
            self.window.quit()

    def change_path(self):
        global directory
        directory = filedialog.askdirectory()
        self.lbl2.configure(text=directory)

class CamFeed:
    def __init__(self):
        # Open the video source
        self.cap = cv2.VideoCapture(1)
        (self.grabbed, self.frame) = self.cap.read()
        self.read_lock = Lock()

        self.stopped = False
        self.t = Thread(target=self.update_frame, name="camUpdate", args=())
        self.t.daemon = True
        self.t.start()

    def get_frame(self):

        self.read_lock.acquire()
        output = self.frame.copy()
        self.read_lock.release()
        output = imutils.resize(output, width=500)
        return output

    def update_frame(self):
        while self.stopped is False:
            (grabbed, frame) = self.cap.read()
            self.read_lock.acquire()
            self.grabbed, self.frame = grabbed, frame
            self.read_lock.release()

    def stop(self):
        self.stopped = True
        self.t.join()

    def __del__(self):
        self.stopped = True
        self.cap.release()


class App:

    def __init__(self):
        self.stopMap = False 
        self.stopTrack = False
        self.laserBB = None
        self.trackingLaser = False
        self.trackingPresenter = False
        self.net = cv2.dnn.readNet('../resources/yolo.cfg', '../resources/yolo.weights')

        # Create Webcam Feed
        self.webCam = CamFeed()
        frame = self.webCam.get_frame()
        (self.fH, self.fW) = frame.shape[:2]

        # Create Object Tracker
        self.objectTracker = ObjectTracker("kcf")
        # print("Object Tracker Created")
        self.laserTracker = ObjectTracker("kcf")

        # Create Camera Controller
        self.camControl = CameraControl()
        self.camControl.set_size(self.fH, self.fW)

        # Create Remote Controller
        self.remoteControl = RemoteControl("/dev/rfcomm1")
        self.start_remote()

        # Create GUI
        self.gui = GUI(self, 0)


##################################################
############ MAP FUNCTIONS #######################
##################################################

    def start_map(self):

        # Create thread for map display
        tmap = Thread(target = self.update_map, name = "MapFeed Display", args=())
        tmap.daemon = True
        self.stopMap = False

        # Start thread
        tmap.start()

        sleep(0.5)

        global displayMap
        displayMap = True

        return self

    def update_map(self):
        global mapFrame
        while self.stopMap is False:
            # Grab frame, show it
            mapFrame = self.webCam.get_frame()
            sleep(0.016)

    def stop_map(self):
        self.stopMap = True

##################################################
############ TRACKER FUNCTIONS ###################
##################################################

    def select_presenter(self):
        global initBB
        global mapFrame
        self.objectTracker.set_presenter(mapFrame, initBB)
        self.objectTracker.update_presenter(mapFrame)

    def start_tracker(self):
        # Create thread for tracking
        self.trackingPresenter = True
        tTrack = Thread(target = self.update_tracker, name = "Tracker Thread", args=())
        tTrack.daemon = True

        # Start thread
        tTrack.start()

        return self

    def stop_tracker(self):
        self.trackingPresenter = False

##################################################
############## LASER FUNCTIONS ###################
##################################################

    def detect(self):
        global mapFrame
        while trackingLaser is False:
            print("Detecting laser")
            #DNN stuff
            netImage = cv2.resize(mapFrame, (128, 128))
            blob = cv2.dnn.blobFromImage(netImage, size=(128, 128), swapRB=True, crop=False)
            net.setInput(blob)
            output = net.forward()

            for detection in output[0, 0, :, :]:
                if detection[2] > 0.5:
                    class_id = detection[1]
                    class_name = id_class_name(class_id, classNames)
                    x = detection[3] * self.fW/128
                    y = detection[4] * self.fH/128
                    self.laserBB = (x, y)
                    self.trackingLaser = True

        tDetector = Thread(target = self.update_laser, name = "Detector Thread", args=())
        tDetector.daemon = True

        # Start thread
        tDetector.start()

        return self

    def select_lasso(self):
        global selectLasso
        global lassoBB
        global lassoReady
        selectLasso = True

    def update_tracker(self):
        global mapFrame, selectLasso, lassoBB, lassoReady
        while self.trackingPresenter:
            self.objectTracker.update_presenter(mapFrame)
            pBB = self.objectTracker.get_presenter()
            #print("updated to: " + str(xCoord) + ", " + str(yCoord))
            if lassoReady:
                self.camControl.set_angle(lassoBB[0], lassoBB[1], lassoBB[2], lassoBB[3])
            else:
                self.camControl.set_angle(pBB[0], pBB[1], pBB[2], pBB[3])

    def update_laser(self):
        global laserList

        while trackingLaser:
            self.laserBB = laserTracker.get_presenter()
            laserList.append(tuple((self.laserBB[0], self.laserBB[1])))

        # Do math here
        laserL = laserB = sys.maxint
        laserR = laserT = 0

        for i in laserList:
            if i[0] > laserR:
                laserR = i[0]

            if i[0] < laserL:
                laserL = i[0]

            if i[1] > laserT:
                laserT = i[1]

            if i[1] < laserB:
                laserB = i[1]

        self.camControl.lassozoom(laserT, laserR, laserB, laserL)

##################################################
############## REMOTE FUNCTIONS ##################
##################################################

    def start_remote(self):
        # Create thread for map display
        tRemote = Thread(target = self.monitor_remote, name = "MapFeed Display", args=())
        tRemote.daemon = True

        # Start thread
        tRemote.start()

        sleep(0.5)

        return self

    def monitor_remote(self):
        global lassoReady, stage, selectLasso

        while True:
            if self.remoteControl.hasWaiting():
                readIn = self.remoteControl.read()

                if readIn == 1:
                    if stage == 6 and selectLasso is False:
                        print("Lasso signal received.")
                        self.select_lasso()

                if readIn == 2:
                    print("Return to presenter.")
                    lassoReady = False

                if readIn == 3:
                    print("Lasso end received.")

        sleep(0.2)


# Open application
App()
print("Past app")


