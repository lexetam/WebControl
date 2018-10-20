from DataStructures.makesmithInitFuncs import MakesmithInitFuncs
from scipy.spatial                      import distance as dist
from imutils                            import perspective, contours
#from imutils.video                      import VideoStream
#from background.webcamVideoStream       import WebcamVideoStream
#from imutils.video			import WebcamVideoStream
import numpy                            as np
import imutils
import cv2
import time
import re
import sys
import math


class OpticalCalibration(MakesmithInitFuncs):

    camera = None
    time.sleep(2.0)
    gaussianBlurValue = 5
    cannyLowValue = 50
    cannyHighValue = 100
    opticalCenter = (None,None)

    def removeOutliersAndAverage(self, data):
        mean = np.mean(data)
        sd = np.std(data)
        tArray = [x for x in data if ( (x >= mean-2.0*sd) and (x<=mean+2.0*sd))]
        return np.average(tArray), np.std(tArray)

    def simplifyContour(self,c,sides=4):
        tolerance = 0.01
        while True:
            _c = cv2.approxPolyDP(c, tolerance*cv2.arcLength(c,True), True)
            if len(_c)<=sides or tolerance>0.5:
                break
            tolerance += 0.01
        if len(_c)<sides: # went too small.. now lower the tolerance until four points or more are reached
            while True:
                tolerance -= 0.01
                _c = cv2.approxPolyDP(c, tolerance*cv2.arcLength(c,True), True)
                if len(_c)>=sides or tolerance <= 0.1:
                    break
        return _c

    def setCalibraitonSettings(self,args):
        self.markerX = args['markerX']
        self.markerY = args['markerY']
        self.centerX = args['centerX']
        self.centerY = args['centerY']
        self.scaleX = args['scaleX']
        self.scaleY = args['scaleY']
        self.tlX = args['tlX']
        self.tlY = args['tlY']
        self.brX = args['brX']
        self.brY = args['brY']

    def on_Start(self,args):
        self.setCalibrationSettings(args)
        self.camera = cv2.VideoCapture(0)
        self.on_CenterOnSquare()
        self.camera.release()
        return True

    def on_Calibrate(self, args):
        self.setCalibrationSettings(args)
        self.camera = cv2.VideoCapture(0)
        self.on_CenterOnSquare(self, False)
        self.camera.release()
        return True

    def translatePoint(self, xB, yB, xA, yA, angle):
        cosa = math.cos((angle)*3.141592/180.0)
        sina = math.sin((angle)*3.141592/180.0)
        xB -= xA
        yB -= yA
        _xB = xB*cosa - yB*sina
        _yB = xB*sina + yB*cosa
        xB = _xB+xA
        yB = _yB+yA
        return xB, yB

    def on_CenterOnSquare(self, findCenter=False):

        dxList = np.zeros(shape=(10))  # [-9999.9 for x in range(10)]
        dyList = np.zeros(shape=(10))  # [-9999.9 for x in range(10)]
        diList = np.zeros(shape=(10))  # [-9999.9 for x in range(10)]
        xBList = np.zeros(shape=(10))
        yBList = np.zeros(shape=(10))
        x = 0
        falseCounter = 0

        while True:
            print("geting image")
            (grabbed, image) = self.camera.read()
            print("got image")
            #cv2.imwrite("image"+str(x)+".png",image)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (self.gaussianBlurValue, self.gaussianBlurValue), 0)
            edged = cv2.Canny(gray, self.cannyLowValue, self.cannyHighValue)
            edged = cv2.dilate(edged, None, iterations=1)
            edged = cv2.erode(edged, None, iterations=1)
            cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if imutils.is_cv2() else cnts[1]
            (cnts, _) = contours.sort_contours(cnts)
            #print(cnts)
            colors = ((0, 0, 255), (240, 0, 159), (0, 165, 255), (255, 255, 0), (255, 0, 255))
            refObj = None
            height, width, channels = image.shape

            if self.opticalCenter[0] is None or self.opticalCenter[1] is None:
                xA = int(width / 2)
                yA = int(height / 2)
            else:
                xA, yA = self.opticalCenter

            maxArea = 0

            for cTest in cnts:
                if (cv2.contourArea(cTest)>maxArea):
                    maxArea = cv2.contourArea(cTest)
                    c = cTest
            #cv2.imwrite("edged.png",edged)
            print(cv2.contourArea(c))
            if cv2.contourArea(c)>1000:
                orig = image.copy()
                #approximate to a square (i.e., four contour segments)
                cv2.drawContours(orig, [c.astype("int")], -1, (255, 255, 0), 2)
                #simplify the contour to get it as square as possible (i.e., remove the noise from the edges)
                if (findCenter):
                    sides = 20
                else:
                    sides = 4
                c=self.simplifyContour(c,sides)
                cv2.drawContours(orig, [c.astype("int")], -1, (255, 0, 0), 2)
                box = cv2.minAreaRect(c)
                angle = box[-1]
                if (abs(angle+90)<30):
                    _angle = angle+90
                else:
                    _angle = angle
                box = cv2.cv.BoxPoints(box) if imutils.is_cv2() else cv2.boxPoints(box)
                box = np.array(box, dtype="int")
                box = perspective.order_points(box)
                cv2.drawContours(orig, [box.astype("int")], -1, (0, 255, 0), 2)
                cv2.imwrite('image-out'+str(x)+".png",orig)
                if findCenter == False:
                    M = cv2.getRotationMatrix2D((xA,yA),_angle,1)
                    orig = cv2.warpAffine(orig,M,(width,height))
                xB = np.average(box[:, 0])
                yB = np.average(box[:, 1])

                (tl, tr, br, bl) = box
                (tlblX, tlblY) = self.midpoint(tl, bl)
                (trbrX, trbrY) = self.midpoint(tr, br)
                (tltrX, tltrY) = self.midpoint(tl, tr)
                (blbrX, blbrY) = self.midpoint(bl, br)

                xD = dist.euclidean((tlblX,tlblY),(trbrX,trbrY))/self.markerX
                yD = dist.euclidean((tltrX,tltrY),(blbrX,blbrY))/self.markerY
                if xD == 0:  #doing this to catch bad calibrations and stop crashing
                    xD = 1.0
                if yD == 0:
                    yD = 1.0


                cos = math.cos(angle*3.141592/180.0)
                sin = math.sin(angle*3.141592/180.0)
                if (_angle<30):
                    _angle = _angle *-1.0
                if findCenter == False:
                    xB,yB = self.translatePoint(xB,yB,xA,yA,_angle)
                print("here7")

                Dx = dist.euclidean((xA,0), (xB,0))/xD
                if (xA>xB):
                    Dx *= -1
                Dy = dist.euclidean((0,yA), (0,yB))/yD
                if (yA<yB):
                    Dy *= -1
                Dist = math.sqrt(Dx**2.0 + Dy**2.0 )
                dxList[x] = Dx
                dyList[x] = Dy
                diList[x] = Dist
                xBList[x] = xB
                yBList[x] = yB
                x +=1
                print("Processed Image "+str(x))
                if (x==10):
                    break
            else:
                falseCounter += 1
                if (falseCounter == 10):
                    break
        print("Got 10 images processed, " + str(falseCounter) + " images were bad")
        if dxList.ndim != 0:
            avgDx, stdDx = self.removeOutliersAndAverage(dxList)
            avgDy, stdDy = self.removeOutliersAndAverage(dyList)
            avgDi, stdDi = self.removeOutliersAndAverage(diList)
            avgxB, stdxB = self.removeOutliersAndAverage(xBList)
            avgyB, stdyB = self.removeOutliersAndAverage(yBList)
            print("avgDx, stdDx:" + str(avgDx) + ", " + str(stdDx))
            print("avgDy, stdDy:" + str(avgDy) + ", " + str(stdDy))
            print("avgDy, stdDy:" + str(avgDy) + ", " + str(stdDy))
            print("avgxB, stdxB:" + str(avgxB) + ", " + str(stdxB))
            print("avgyB, stdyB:" + str(avgyB) + ", " + str(stdyB))
            return True
        return False


