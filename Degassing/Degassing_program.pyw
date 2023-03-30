#!/usr/bin/env python3

from tkinter import *
from tkinter.filedialog import asksaveasfilename
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib import pyplot as plt
import os
import platform
import sys
import time
import numpy as np
# sys.path.append("")
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from avaspec import *
import globals
import TTA_window
import rseriesopc as rs
import matplotlib
matplotlib.use("Qt5Agg")
from statistics import mean
from math import log10 as log
from tqdm import tqdm

# time.sleep(2)

cwd = os.getcwd()
if os.path.isfile(cwd+"/avaspecx64.dll"):
    print("You are in the right directory!")
    pass
else:
    print("You are not in the directory with avaspecx64.dll")
    raise FileNotFoundError

# time.sleep(1)

os.add_dll_directory(os.getcwd())

class MainWindow(QMainWindow, TTA_window.Ui_MainWindow):
    newdata = pyqtSignal()
    cancel = pyqtSignal()
    cancelled = False
    cancelled_dilution = False
    first = True
    use_dark = False
    use_light = False
    stop_dispersion = False
    PumpsConnected = False
    ConcentrationCalculated = False
    SpectrometerConnected = False
    start = False
    sensitizer_pump = {}
    emitter_pump = {}
    solvent_pump = {}
    Spectrum_figure = plt.figure(dpi = 100)
    

    measconfig = MeasConfigType
    measconfig.m_StartPixel = 0
    measconfig.m_StopPixel = globals.pixels - 1
    measconfig.m_IntegrationTime = 0
    measconfig.m_IntegrationDelay = 0
    measconfig.m_NrAverages = 0
    measconfig.m_CorDynDark_m_Enable = 1  # nesting of types does NOT work!!
    measconfig.m_CorDynDark_m_ForgetPercentage = 100
    measconfig.m_Smoothing_m_SmoothPix = 2
    measconfig.m_Smoothing_m_SmoothModel = 0
    measconfig.m_SaturationDetection = 0
    measconfig.m_Trigger_m_Mode = 0
    measconfig.m_Trigger_m_Source = 0
    measconfig.m_Trigger_m_SourceType = 0
    measconfig.m_Control_m_StrobeControl = 0
    measconfig.m_Control_m_LaserDelay = 0
    measconfig.m_Control_m_LaserWidth = 0
    measconfig.m_Control_m_LaserWaveLength = 0.0
    measconfig.m_Control_m_StoreToRam = 0

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        # self.IntTimeEdt.setText("{:3.1f}".format(500))
        self.NumAvgEdt.setText("{0:d}".format(2))
        # self.NumMeasEdt.setText("{0:d}".format(10))
        self.StartMeasBtn.setEnabled(False)
        self.StopDilutionBtn.setEnabled(False)
        self.wl_low_label.setValue(582)
        self.wl_high_label.setValue(644)
        OnlyInt = QIntValidator()
        OnlyInt.setRange(1, 1000)  
        self.NumAvgEdt.setValidator(OnlyInt)
        # self.IntTimeEdt.setValidator(QDoubleValidator(1.00,10000.00,1))
        # self.NumMeasEdt.setValidator(OnlyInt)
#       self.OpenCommBtn.clicked.connect(self.on_OpenCommBtn_clicked)
#       do not use explicit connect together with the on_ notation, or you will get
#       two signals instead of one!
        self.cancel.connect(self.cancel_meas)
        self.actionHelpOxy.triggered.connect(self.show_help_oxy)
        self.log_name = "default_log.txt"

    @pyqtSlot()
    
    def on_log_file_btn_clicked(self):
        text, ok = QInputDialog().getText(self, "QInputDialog().getText()",
                                     "Log to:", QLineEdit.Normal,
                                     "Filename")
        if ok and text:
            self.log_name = text
            self.log_name_label.setText("Saving to: "+text)
        #something about open dialog
        return

    @pyqtSlot() # no idea why you have to use this command, but it works haha
#   if you leave out the @pyqtSlot() line, you will also get an extra signal!
#   so you might even get three!
    def on_OpenCommBtn_clicked(self):
        
        ret = AVS_Init(0)    
        # QMessageBox.information(self,"Info","AVS_Init returned:  {0:d}".format(ret))
        ret = AVS_GetNrOfDevices()
        # QMessageBox.information(self,"Info","AVS_GetNrOfDevices returned:  {0:d}".format(ret))
        req = 0
        mylist = AvsIdentityType * 1
        ret = AVS_GetList(75, req, mylist)
        serienummer = str(ret[1].SerialNumber.decode("utf-8"))
        QMessageBox.information(self,"Info","Found Serialnumber: " + serienummer)
        globals.dev_handle = AVS_Activate(ret[1])
        # QMessageBox.information(self,"Info","AVS_Activate returned:  {0:d}".format(globals.dev_handle))
        devcon = DeviceConfigType
        reqsize = 0
        ret = AVS_GetParameter(globals.dev_handle, 63484, reqsize, devcon)
        globals.pixels = ret[1].m_Detector_m_NrPixels
        print(f'len of globals pixels in: {globals.pixels}')
        ret = AVS_GetLambda(globals.dev_handle,globals.wavelength)
        x = 0
        globals.wavelength = ret[:globals.pixels]

        self.StartMeasBtn.setEnabled(False)
        self.StopMeasBtn.setEnabled(True)
        self.OpenCommBtn.setEnabled(False)
        self.CloseCommBtn.setEnabled(True)
        self.getDarkBtn.setEnabled(True)
        self.getLightBtn.setEnabled(True)

        # Create figure and assign to layout in GUI
        self.Spectrum_figure = MplCanvas()
        toolbar = NavigationToolbar(self.Spectrum_figure, self)
        self.SpectrumVLayout.addWidget(self.Spectrum_figure)
        self.SpectrumVLayout.addWidget(toolbar)
        self.Plot_new_spectrum(0,0)

        self.SpectrometerConnected = True
        return

    @pyqtSlot()
    def Plot_new_spectrum(self, x,y):
        self.Spectrum_figure.axes.clear()
        self.Spectrum_figure.axes.plot(x, y)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Intensity")
        plt.tight_layout()
        self.Spectrum_figure.draw()
   

    @pyqtSlot()
    def on_CloseCommBtn_clicked(self):
        callbackclass.callback(self, 0, 0)
        self.StartMeasBtn.setEnabled(False)
        self.StopMeasBtn.setEnabled(False)
        self.OpenCommBtn.setEnabled(True)
        self.CloseCommBtn.setEnabled(False)
        return


#function for recording a spectrum
    @pyqtSlot() 
    def Record_Spectrum(self,avg):
        ret = AVS_UseHighResAdc(globals.dev_handle, True)
        self.measconfig.m_IntegrationTime = float(self.IntTimeEdt.text())
        self.measconfig.m_NrAverages = avg * int(self.NumAvgEdt.text())
        ret = AVS_PrepareMeasure(globals.dev_handle, self.measconfig)
        # nummeas = int(self.NumMeasEdt.text())
        self.cancelled = False
        timestamp = 0
        ret = AVS_Measure(globals.dev_handle, 0, 1)
        dataready = False
        while (dataready == False):
            dataready = (AVS_PollScan(globals.dev_handle) == True)
            time.sleep(0.001)
        if dataready == True:
            ret = AVS_GetScopeData(globals.dev_handle, timestamp, globals.spectraldata )
            timestamp = ret[0]
            x = 0
            while (x < globals.pixels): # 0 through 2047
                globals.spectraldata[x] = ret[1][x]
                x += 1
        return
        


    @pyqtSlot()
    def on_StartMeasBtn_clicked(self): #activates when the button "Start Measurement" is clicked
        self.first = True
        try:
            if self.thread.isRunning():
                print("Shutting down running thread.")
                self.thread.terminate()
                time.sleep(1)
            else:
                print("No thread was running.")
        except:
            print("Didn't find thread.")
        self.thread = QThread() # this created an additional computing thread for processes, so the main window doesn't freeze
        self.worker = Worker() # this is a worker that will tell when the job is done
        self.worker.func = self.on_StartMeasBtn_clicked_function #here the job of the worker is defined. it should only be one function
        self.worker.moveToThread(self.thread) #the workers job is moved from the frontend to the thread in backend
        self.thread.started.connect(self.worker.run) # when the thread is started, the worker runs
        self.worker.finished.connect(self.thread.quit) # when the worker is finished, the the thread is quit
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start() #here the thread is actually started

        return
    

    @pyqtSlot()
    def on_StopMeasBtn_clicked(self):
        self.cancel.emit()
        # ret = AVS_StopMeasure(globals.dev_handle)
        time.sleep(1)
        # self.worker.finished.emit()
        # self.thread.quit()
        # self.worker.deleteLater
        # self.thread.deleteLater
        return

    @pyqtSlot()
    def cancel_meas(self):
        self.cancelled = True
        return

    #def nativeEvent(self, eventType, message):
    #    msg = ctypes.wintypes.MSG.from_address(message.__int__())
    #    if eventType == "windows_generic_MSG":
    #        if msg.message == WM_MEAS_READY:
    #            # print("Message Received!")
    #            self.newdata.emit()
    #    return False, 0


# Maybe move ratio to separate function to update every time wavelength values are changed
    @pyqtSlot()
    def get_ratio(self):
        self.wl_low = int(self.wl_low_label.text())
        self.wl_high = int(self.wl_high_label.text())
        self.index_low = [int(x) for x in globals.wavelength].index(self.wl_low)
        self.index_high = [int(x) for x in globals.wavelength].index(self.wl_high)
        if self.use_dark == True:
            intensity_low = (globals.spectral_minus_dark[self.index_low] + globals.spectral_minus_dark[self.index_low-1] + globals.spectral_minus_dark[self.index_low-2] + globals.spectral_minus_dark[self.index_low-3] + globals.spectral_minus_dark[self.index_low+1] + globals.spectral_minus_dark[self.index_low+2] +globals.spectral_minus_dark[self.index_low+3])/7
            intensity_high = (globals.spectral_minus_dark[self.index_high] + globals.spectral_minus_dark[self.index_high-1] + globals.spectral_minus_dark[self.index_high-2] + globals.spectral_minus_dark[self.index_high-3] + globals.spectral_minus_dark[self.index_high+1] + globals.spectral_minus_dark[self.index_high+2] + globals.spectral_minus_dark[self.index_high+3])/7
        elif self.use_light == True:
            intensity_low = mean(globals.spectral_minus_light[self.index_low - 3 : self.index_low + 3])
            intensity_high = mean(globals.spectral_minus_light[self.index_high - 3 : self.index_high + 3])
        if intensity_high != 0 and intensity_low != 0:
            ratio = - intensity_high + intensity_low
        else:
            ratio = 0
        # print(ratio)
        return ratio


    @pyqtSlot()
    def on_StartMeasBtn_clicked_function(self):
        
        self.StartMeasBtn.setEnabled(False)
        self.getDarkBtn.setEnabled(False)
        self.getLightBtn.setEnabled(False)
        self.start = False
        self.cancelled = False
        nummeas = 0
        scans = 0
        globals.ratio = []
        globals.ratio_time = []

        root = Tk()
        root.withdraw()
        self.log_name = asksaveasfilename(initialdir="logs/",initialfile=self.log_name,defaultextension=".txt")
        root.destroy()
        if not self.log_name:
            self.StartMeasBtn.setEnabled(True)
            self.getDarkBtn.setEnabled(True)
            self.getLightBtn.setEnabled(True)
            return
        

        

        self.print_to_message_box("Spectral measurements started")
        t0 = time.time()

        with open(self.log_name,"w") as f:
                if self.first:
                    f.write(f"Exposure time: {float(self.IntTimeEdt.text())} ms\n")
                    f.write(f"Number of averages: {int(self.NumAvgEdt.text())}\n")
                    f.write('time(s)  A   B   C   D   S   '+'   '.join(str(globals.wavelength[x]) for x in range(globals.pixels))+'\n')

        self.start = True

        if nummeas == 0:
            nummeas=100000
        while (scans < nummeas) and self.cancelled == False:
            self.Record_Spectrum(1)
            scans = scans + 1
            temp_time = time.time() - t0
            self.new_time = str("{:.2f}".format(temp_time))
            

            if self.use_dark == True:
                globals.spectral_minus_dark = [globals.spectraldata[x] - globals.dark_spectrum[x] for x in range(globals.pixels)]
                self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)       
                with open(self.log_name,"a") as f:
                    f.write(str(self.new_time)+'    '+self.flow_rate_box_A.text()+' '+self.flow_rate_box_B.text()+' '+self.flow_rate_box_C.text()+' '+self.flow_rate_box_D.text()+' '+self.flow_rate_box_S.text()+' ')
                    f.write('   '.join(str(globals.spectral_minus_dark[x]) for x in range(globals.pixels))+"\n")
                   
            
            elif self.use_light == True:
                globals.spectral_minus_light = [log(globals.light_spectrum[x] / globals.spectraldata[x]) if globals.spectraldata[x] != 0 else 0.0 for x in range(globals.pixels)]
                self.Plot_new_spectrum(globals.wavelength[:2048], globals.spectral_minus_light[:2048])
                # globals.spectral_minus_light = [0.0 - globals.spectraldata[x] + globals.light_spectrum[x] for x in range(globals.pixels)]
                with open(self.log_name,'a') as f:
                    f.write(str(self.new_time)+'    '+self.flow_rate_box_A.text()+' '+self.flow_rate_box_B.text()+' '+self.flow_rate_box_C.text()+' '+self.flow_rate_box_D.text()+' '+self.flow_rate_box_S.text()+' ')
                    f.write('   '.join(str(globals.spectral_minus_light[x]) for x in range(globals.pixels))+"\n")

            else:
                self.print_to_message_box("you didnt choose dark or light spectrum wth")
            
            self.first = False
        
            globals.ratio_time.append(temp_time)
            globals.ratio.append(self.get_ratio())
            plt.figure(dpi=60)
            plt.plot(globals.ratio_time,globals.ratio)
            plt.xlabel("Time [s]")
            plt.ylabel(f"Ratio from wl {self.wl_low} and wl {self.wl_high}")
            plt.savefig("ratio_fig.png")
            plt.close()
            self.uv_spectrum_label.setPixmap(QPixmap("ratio_fig.png"))

            first = True

            self.meas_num.setText(f"Measurement: {scans}")
            self.time_elapsed.setText(f"Time: {self.new_time} s")
            time.sleep(float(self.Time_interval_Edt.text()))
        
        self.print_to_message_box("Spectral measurements ended")
        self.StartMeasBtn.setEnabled(True)
        self.getDarkBtn.setEnabled(True)
        self.getLightBtn.setEnabled(True)
        return

    @pyqtSlot()
    def on_getDarkBtn_clicked(self):
        self.StartMeasBtn.setEnabled(False)
        self.Record_Spectrum(3)
        globals.dark_spectrum = [globals.spectraldata[x] for x in range(globals.pixels)]
        self.print_to_message_box("Dark spectrum measured")
        self.use_dark = True
        self.use_light = False
        self.StartMeasBtn.setEnabled(True)
        self.Plot_new_spectrum(globals.wavelength, globals.dark_spectrum)

        return


    @pyqtSlot()
    def on_getLightBtn_clicked(self):
        self.StartMeasBtn.setEnabled(False)
        self.Record_Spectrum(3)
        globals.light_spectrum = [globals.spectraldata[x] for x in range(globals.pixels)]
        self.print_to_message_box("Light spectrum measured")
        self.use_dark = False
        self.use_light = True
        self.StartMeasBtn.setEnabled(True)
        self.Plot_new_spectrum(globals.wavelength[:2048], globals.light_spectrum)
        return    

    @pyqtSlot() #Print time and message
    def print_to_message_box(self, text):
            t = time.localtime()
            current_time = time.strftime("%H:%M:%S", t)
            self.MsgBox.append(f"{current_time}  {text}")
            # QScrollBar *sb = ui->terminalTextBrowser()->verticalScrollBar();
            # sb->setValue(sb->maximum());
            return

    @pyqtSlot()
    def on_ConnectPumpsBtn_clicked(self):
        if self.checkA.isChecked() == False and self.checkB.isChecked() == False and self.checkC.isChecked() == False and self.checkD.isChecked() == False and self.checkS.isChecked() == False:
            self.print_to_message_box("Remember to pick which pumps you want to connect to")
            return
        self.print_to_message_box("Connecting to pumps")
        self.client = rs.RSeriesClient('opc.tcp://localhost:43344')
        self.conState = self.client.connect()
        self.rseries = self.client.getRSeries()
        self.manualControl = self.rseries.getManualControl()
        # self.print_to_message_box(f"Pumps available are {self.manualControl.getR2Secondary().getPumps()}")

        if self.checkA.isChecked(): #conncent pumpA
            self.pumpA = self.manualControl.getR2Primary()._getPump(f"A")
            if self.pumpA.getValveSRState():
                self.switchSRBtn_A.setText(f"R")
            else:
                self.switchSRBtn_A.setText(f"S")
            self.StartFlowBtn_A.setEnabled(True)
            self.switchSRBtn_A.setEnabled(True)
            self.StopFlowBtn_A.setEnabled(True)

        if self.checkB.isChecked(): #conncent pumpB
            self.pumpB = self.manualControl.getR2Primary()._getPump(f"B")
            if self.pumpB.getValveSRState():
                self.switchSRBtn_B.setText(f"R")
            else:
                self.switchSRBtn_B.setText(f"S")
            self.StartFlowBtn_B.setEnabled(True)
            self.switchSRBtn_B.setEnabled(True)
            self.StopFlowBtn_B.setEnabled(True)

        if self.checkC.isChecked(): #conncent pumpC
            self.pumpC = self.manualControl.getR2Secondary()._getPump(f"A")
            if self.pumpC.getValveSRState():
                self.switchSRBtn_C.setText(f"R")
            else:
                self.switchSRBtn_C.setText(f"S")
            self.StartFlowBtn_C.setEnabled(True)
            self.switchSRBtn_C.setEnabled(True)
            self.StopFlowBtn_C.setEnabled(True)

        if self.checkD.isChecked(): #conncent pumpD
            self.pumpD = self.manualControl.getR2Secondary()._getPump(f"B")
            if self.pumpD.getValveSRState():
                self.switchSRBtn_D.setText(f"R")
            else:
                self.switchSRBtn_D.setText(f"S")
            self.StartFlowBtn_D.setEnabled(True)
            self.switchSRBtn_D.setEnabled(True)
            self.StopFlowBtn_D.setEnabled(True)

        # if self.checkS.isChecked(): #Connect syrringe pump
        # self.pump = self.manualControl.getR2Secondary()._getPump(f"{self.pump_name.currentText()}") # In primary, A=A and B=B but in secondary A=C and B=D.
        self.CloseCommBtn.setEnabled(True)
        self.PumpsConnected = True
        return

    @pyqtSlot()
    def on_CloseCommBtn_vap_clicked(self):
        self.PumpsConnected == False
        self.print_to_message_box('Disconnecting from all pumps')
        self.pumpA.setFlowRate(0)
        self.pumpB.setFlowRate(0)
        self.pumpC.setFlowRate(0)
        self.pumpD.setFlowRate(0)
        # self.pumpS.setFlowRate(0)
        self.manualControl.stopAll()
        # self.print_to_message_box('turn off pump and reactor')  
        # self.temperature.setTemperature(25) #This is turned off for testing
        if self.conState:
            self.client.disconnect()
        return

    # Pump A controls
    @pyqtSlot()
    def on_StartFlowBtn_A_clicked(self):
            self.manualControl.startManualControl()
            self.pumpA.setFlowRate(int(self.flow_rate_box_A.text()))
            self.print_to_message_box(f"Pump A flow rate: {int(self.flow_rate_box_A.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_A_clicked(self):
        self.pumpA.setFlowRate(0)
        self.flow_rate_box_A.setValue(int(0))
        self.print_to_message_box(f"Pump A flow rate stopped")

    @pyqtSlot()
    def on_switchSRBtn_A_clicked(self):
        SR = self.pumpA.getValveSRState()
        if SR == False:
            self.pumpA.setValveSRState(True)
            self.switchSRBtn_A.setText("R")
            self.print_to_message_box(f"Pump A switched S/R to: Reactant")
            return
        else:
            self.pumpA.setValveSRState(False)
            self.switchSRBtn_A.setText("S")
            self.print_to_message_box(f"Pump A switched S/R to: Solvent")
            return

    # Pump B controls
    @pyqtSlot()
    def on_StartFlowBtn_B_clicked(self):
            self.manualControl.startManualControl()
            self.pumpB.setFlowRate(int(self.flow_rate_box_B.text()))
            self.print_to_message_box(f"Pump B flow rate: {int(self.flow_rate_box_B.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_B_clicked(self):
        self.pumpB.setFlowRate(0)
        self.flow_rate_box_B.setValue(int(0))
        self.print_to_message_box(f"Pump B flow rate stopped")

    @pyqtSlot()
    def on_switchSRBtn_B_clicked(self):
        SR = self.pumpB.getValveSRState()
        if SR == False:
            self.pumpB.setValveSRState(True)
            self.switchSRBtn_B.setText("R")
            self.print_to_message_box(f"Pump B switched S/R to: Reactant")
            return
        else:
            self.pumpB.setValveSRState(False)
            self.switchSRBtn_B.setText("S")
            self.print_to_message_box(f"Pump B switched S/R to: Solvent")
            return
    
    # Pump C controls
    @pyqtSlot()
    def on_StartFlowBtn_C_clicked(self):
            self.manualControl.startManualControl()
            self.pumpC.setFlowRate(int(self.flow_rate_box_C.text()))
            self.print_to_message_box(f"Pump C flow rate: {int(self.flow_rate_box_C.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_C_clicked(self):
        self.pumpC.setFlowRate(0)
        self.flow_rate_box_C.setValue(int(0))
        self.print_to_message_box(f"Pump C flow rate stopped")

    @pyqtSlot()
    def on_switchSRBtn_C_clicked(self):
        SR = self.pumpC.getValveSRState()
        if SR == False:
            self.pumpC.setValveSRState(True)
            self.switchSRBtn_C.setText("R")
            self.print_to_message_box(f"Pump C switched S/R to: Reactant")
            return
        else:
            self.pumpC.setValveSRState(False)
            self.switchSRBtn_C.setText("S")
            self.print_to_message_box(f"Pump C switched S/R to: Solvent")
            return
        
    # Pump D controls
    @pyqtSlot()
    def on_StartFlowBtn_D_clicked(self):
            self.manualControl.startManualControl()
            self.pumpD.setFlowRate(int(self.flow_rate_box_D.text()))
            self.print_to_message_box(f"Pump D flow rate: {int(self.flow_rate_box_D.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_D_clicked(self):
        self.pumpD.setFlowRate(0)
        self.flow_rate_box_D.setValue(int(0))
        self.print_to_message_box(f"Pump D flow rate stopped")

    @pyqtSlot()
    def on_switchSRBtn_D_clicked(self):
        SR = self.pumpD.getValveSRState()
        if SR == False:
            self.pumpD.setValveSRState(True)
            self.switchSRBtn_D.setText("R")
            self.print_to_message_box(f"Pump D switched S/R to: Reactant")
            return
        else:
            self.pumpD.setValveSRState(False)
            self.switchSRBtn_D.setText("S")
            self.print_to_message_box(f"Pump D switched S/R to: Solvent")
            return    

# Syringe pump controls to be coded

# Get flow rate button
    # @pyqtSlot()
    # def on_getFlow_clicked(self):
    #     self.getFlow.setText(f"Get Flow rate. Current: {self.pumpD.getFlowRate()}")
    #     return

    @pyqtSlot()
    def show_help_oxy(self):
        QMessageBox.information(self, "Info", "Setup for Oxygen level experiment.\
             \nSet Integration time to 500 ms\nSet Number of averages to 5\nSet Number of measurements to 0 (infinite)\nSet the wavelengths for fluorescence measurement (645 for PtTFPP) \
             \nThe Pump chosen should be B, becuase pump D is apparently called B on the Secondary R2 series. \
             \nFor now you can change the flow rate manually by selecting the flow rate and clicking Start Flow.")
        return

    # @pyqtSlot()
    # def on_RunDegas_clicked(self):

    #     maximum_found = False
    #     current_maximum = 0
    #     while maximum_found == False:
    #     start spectroscopy
    #     start flow
    #     while maximum_found == False:
    #     if last 10 points at 645 nm are within +- 5% == plateau reached
    #         save plateau as highest yet
    #         switch flow rate in + direction
    #     # self.runDegas_btn.setEnabled(False)
    #     flow_rate_list = [200,300,400,500,600,700,800,900,1000]
    #     return


    @pyqtSlot()
    def on_CalcBtn_clicked(self): # Calculates flow rates and fills the table
    
        # find sensitizer and emitter pump and use parameters to calculate concentrations. fill the table with values
        pump = ["A","B","C","D","S"]
        number_of_concentrations = 10
        sensitizer_conc = np.full(shape=number_of_concentrations, fill_value=1, dtype=float)
        emitter_conc = np.full(shape=number_of_concentrations, fill_value=1, dtype=float)
        sensitizer_prep_conc = 1
        emitter_prep_conc = 1
        sensitizer_min_flowrate = 50
        emitter_min_flowrate = 50
        solvent_min_flowrate = 50

        SensitizerSelected = False
        EmitterSelected = False
        SolventSelected = False
 
        for x in pump:
            if self.__dict__['comboBox_' + x].currentIndex() == 1 : # number 1 corresponds to sensitizer in combobox
                SensitizerSelected = True
                self.sensitizer_pump = x
                Factor_sens = float(self.total_flow_rate_box.value()) / float(self.__dict__['min_flow_rate_box_' + x].value())
                self.__dict__['prep_conc_box_' + x].setValue(float(self.__dict__['init_conc_box_' + x].value() * Factor_sens)) #set sensitizer concentration to prepare value
                sensitizer_prep_conc = float(self.__dict__['prep_conc_box_' + x].value())
                sensitizer_min_flowrate = int(self.__dict__['min_flow_rate_box_' + x].value())
                sensitizer_conc[0] = float(self.__dict__['prep_conc_box_' + x].value()) / Factor_sens
                for i in range(number_of_concentrations-1):
                   sensitizer_conc[i+1] = sensitizer_conc[i] * float(self.__dict__['Incr_factor_box_' + x].value()) #sensitizer concentrations
                globals.sensitizer_concentrations = sensitizer_conc

            if self.__dict__['comboBox_' + x].currentIndex() == 2 : # number 2 corresponds to emitter in combobox
                EmitterSelected = True
                self.emitter_pump = x
                Factor_emit = float(self.total_flow_rate_box.value()) / float(self.__dict__['min_flow_rate_box_' + x].value())
                self.__dict__['prep_conc_box_' + x].setValue(float(self.__dict__['init_conc_box_' + x].value() * Factor_emit)) #set sensitizer concentration to prepare value
                emitter_prep_conc = float(self.__dict__['prep_conc_box_' + x].value())
                emitter_min_flowrate = int(self.__dict__['min_flow_rate_box_' + x].value())
                emitter_conc[0] = float(self.__dict__['prep_conc_box_' + x].value()) / Factor_emit
                for i in range(number_of_concentrations-1):
                    emitter_conc[i+1] = emitter_conc[i] *  float(self.__dict__['Incr_factor_box_' + x].value())  #emitter concentrations
                globals.emitter_concentrations = emitter_conc
            
            if self.__dict__['comboBox_' + x].currentIndex() == 3 : # number 3 corresponds to solvent in combobox
                SolventSelected = True
                self.solvent_pump = x
                solvent_min_flowrate = int(self.__dict__['min_flow_rate_box_' + x].value())

        #Create table and set headers
        self.concentration_table.setRowCount(len(emitter_conc))
        self.concentration_table.setColumnCount(len(sensitizer_conc))
        self.concentration_table.setHorizontalHeaderLabels(list(map("{:.3f}".format,sensitizer_conc)))
        self.concentration_table.setVerticalHeaderLabels(list(map("{:.3f}".format,emitter_conc)))
        self.concentration_table.resizeColumnsToContents()
        self.concentration_table.resizeRowsToContents()
        self.concentration_table.show()

        # calculate array of values for C based on max flow rate and sensitizer and emitter lists
        Solvent_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=self.total_flow_rate_box.value(), dtype=int)
        Sensitizer_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=0, dtype=int)
        Emitter_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=0, dtype=int)
        globals.solv_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=self.total_flow_rate_box.value(), dtype=int)
        globals.sens_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=0, dtype=int)
        globals.emit_flowrates = np.full([len(sensitizer_conc),len(emitter_conc)], fill_value=0, dtype=int)
        Exp_time = 0


        if sensitizer_prep_conc == 0 or emitter_prep_conc == 0:
            self.print_to_message_box("Sensitizer or emitter concnetration cannot be 0")
            return
        
        for n in range(len(globals.emitter_concentrations)):
            for m in range(len(globals.sensitizer_concentrations)):
                Sensitizer_flowrates[n,m] = int(sensitizer_conc[m] / sensitizer_prep_conc  * float(self.total_flow_rate_box.value()))
                Emitter_flowrates[n,m] = emitter_conc[n] / emitter_prep_conc * float(self.total_flow_rate_box.value())
                Solvent_flowrates[n,m] = Solvent_flowrates[n,m] - Sensitizer_flowrates[n,m] - Emitter_flowrates[n,m]
                self.concentration_table.setItem(n,m,QTableWidgetItem(str(Solvent_flowrates[n,m])))
                globals.sens_flowrates[n,m] = Sensitizer_flowrates[n,m]
                globals.emit_flowrates[n,m] = Emitter_flowrates[n,m]
                globals.solv_flowrates[n,m] = Solvent_flowrates[n,m]
                if Solvent_flowrates[n,m] < solvent_min_flowrate or Sensitizer_flowrates[n,m] < sensitizer_min_flowrate or Emitter_flowrates[n,m] < emitter_min_flowrate:
                # if Sensitizer_flowrates[n,m] < sensitizer_min_flowrate or Emitter_flowrates[n,m] < emitter_min_flowrate:
                    self.concentration_table.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    globals.sens_flowrates[n,m] = 0
                    globals.emit_flowrates[n,m] = 0
                    globals.solv_flowrates[n,m] = 0
                if Solvent_flowrates[n,m] < 0 or Solvent_flowrates[n,m] < 0.5*solvent_min_flowrate or Sensitizer_flowrates[n,m] < 0.5*sensitizer_min_flowrate or Emitter_flowrates[n,m] < 0.5*emitter_min_flowrate:
                    self.concentration_table.item(n,m).setBackground(QColor(255, 0, 0, 100))
                else: 
                    Exp_time = Exp_time + float(self.volume_interval_box.value()) / float(self.total_flow_rate_box.value())


        #estimate experiment time
        Exp_time = Exp_time + float(self.Initial_volume_box.value()) / float(self.total_flow_rate_box.value())
        self.print_to_message_box(f"Estimated experiment runtime: {int(Exp_time)} minutes")

        if SensitizerSelected == True and EmitterSelected == True and SolventSelected == True:
            self.ConcentrationCalculated = True
        else:
            self.ConcentrationCalculated = False

        return


    @pyqtSlot()
    def on_RunDilutionBtn_clicked(self): #activates when the button "Start Measurement" is clicked
        
        if self.ConcentrationCalculated == False:
            self.print_to_message_box("Concentrations must be calculated first (Select pumps)")
            return
        if self.PumpsConnected == False:
            self.print_to_message_box("Pumps for Sensitizer, Emitter and Solvent must be connected")
            return
        if self.SpectrometerConnected == False:
            self.print_to_message_box("Connect spectrometer and set parameters")
            return

        self.stop_dispersion = False
        try:
            if self.thread_disp.isRunning():
                print("Shutting down running thread.")
                self.thread_disp.terminate()
                time.sleep(1)
            else:
                print("No thread was running.")
        except:
            print("Didn't find thread.")
        self.thread_disp = QThread() # this created an additional computing thread for processes, so the main window doesn't freeze
        self.worker_disp = Worker() # this is a worker that will tell when the job is done
        self.worker_disp.func = self.on_RunDilutionBtn_clicked_function #here the job of the worker is defined. it should only be one function
        self.worker_disp.moveToThread(self.thread_disp) #the workers job is moved from the frontend to the thread in backend
        self.thread_disp.started.connect(self.worker_disp.run) # when the thread is started, the worker runs
        self.worker_disp.finished.connect(self.thread_disp.quit) # when the worker is finished, the the thread is quit
        self.worker_disp.finished.connect(self.worker_disp.deleteLater)
        self.thread_disp.finished.connect(self.thread_disp.deleteLater)
        self.thread_disp.start() #here the thread is actually started
        return

    @pyqtSlot()
    def on_RunDilutionBtn_clicked_function(self, test=False):
        
        self.cancelled_dilution = False

        self.RunDilutionBtn.setEnabled(False)
        self.StopDilutionBtn.setEnabled(True)
        self.manualControl.startManualControl()

        initial_volume = int(self.Initial_volume_box.text())
        system_volume = int(self.SysVolBox.text()) + 200 #in ul
        interval_volume = int(self.volume_interval_box.text())
        total_FR = int(self.total_flow_rate_box.text())

        #Create shortcuts for pumps and flow rate boxes
        pump_sens = self.__dict__['pump' + self.sensitizer_pump]
        pump_emit = self.__dict__['pump' + self.emitter_pump]
        pump_solv = self.__dict__['pump' + self.solvent_pump]
        flowrate_sens = self.__dict__['flow_rate_box_' + self.sensitizer_pump]
        flowrate_emit = self.__dict__['flow_rate_box_' + self.emitter_pump]
        flowrate_solv = self.__dict__['flow_rate_box_' + self.solvent_pump]

         # Set flow rates to 0
        pump_sens.setFlowRate(0)
        pump_emit.setFlowRate(0)
        pump_solv.setFlowRate(0)

        # Set pumps to reactant
        pump_sens.setValveSRState(True)
        self.__dict__['switchSRBtn_' + self.sensitizer_pump].setText("R")
        pump_emit.setValveSRState(True)
        self.__dict__['switchSRBtn_' + self.emitter_pump].setText("R")
        pump_solv.setValveSRState(True)
        self.__dict__['switchSRBtn_' + self.solvent_pump].setText("R")

        time.sleep(1)

        # Flush solvent first to measure dark or light spectra 
        self.print_to_message_box("Solvent being flushed")
        pump_solv.setFlowRate(total_FR)
        flowrate_solv.setValue(total_FR)
        time_to_flush = system_volume / total_FR * 60 #in seconds
        time.sleep(time_to_flush)
        pump_solv.setFlowRate(0)
        flowrate_solv.setValue(0)
        self.print_to_message_box("Solvent flushing finished, prepare for dark measurement")

        # askmeasure light or dark spectrum

        if self.EmissionBtn.isChecked() == True:
            self.on_getDarkBtn_clicked()
        
        if self.AbsorbanceBtn.isChecked() == True:
            self.on_getLightBtn_clicked()
        
        time.sleep(5)

        # initiate spectral measurements and wait until saveass
        if self.cancelled_dilution == False:
            self.on_StartMeasBtn_clicked()
            while self.start == False:
                if not self.log_name:
                    self.start = False
                    self.RunDilutionBtn.setEnabled(True)
                    return
                time.sleep(1)

        time_to_push_initial = initial_volume / total_FR * 60 #in seconds
        time_to_push = interval_volume / total_FR * 60 #in seconds     

        # Scan concentrations in zig-zags
        for n in range(len(globals.emitter_concentrations)):
            for m in range(len(globals.sensitizer_concentrations)):
                if globals.sens_flowrates[n,m] != 0 and globals.emit_flowrates[n,m] != 0 and globals.solv_flowrates[n,m] != 0 and self.cancelled_dilution == False:
                    self.print_to_message_box(f"Sensitizer: {int(globals.sens_flowrates[n,m])} ul/min. Emitter: {int(globals.emit_flowrates[n,m])} ul/min. Solvent: {int(globals.solv_flowrates[n,m])} ul/min.")
                    pump_sens.setFlowRate(globals.sens_flowrates[n,m])
                    flowrate_sens.setValue(int(globals.sens_flowrates[n,m]))
                    pump_emit.setFlowRate(globals.emit_flowrates[n,m])
                    flowrate_emit.setValue(int(globals.emit_flowrates[n,m]))
                    pump_solv.setFlowRate(globals.solv_flowrates[n,m])
                    flowrate_solv.setValue(int(globals.solv_flowrates[n,m]))
                    
                    if n == 0 and m == 0:
                        time.sleep(time_to_push_initial)
                    else:
                        time.sleep(time_to_push)

            #     # wait for the amount of volume then shift to other
            # else:
            #     # stop for loop and shift to next m value, check if new flow rates are non-zero, if yes, shift to lower n value
            #     return

                # Sensitizer max conc
        
        pump_sens.setFlowRate(0)
        flowrate_sens.setValue(0)
        pump_emit.setFlowRate(0)
        flowrate_emit.setValue(0)
        pump_solv.setFlowRate(0)
        flowrate_solv.setValue(0)
        
        # introduce full concentrations of sensitizer and emitter
        if self.cancelled_dilution == False:
            pump_sens.setFlowRate(total_FR)
            flowrate_sens.setValue(total_FR)
            self.print_to_message_box(f"Sensitizer: {int(flowrate_sens.text())} ul/min. Emitter: {int(flowrate_emit.text())} ul/min. Solvent: {int(flowrate_solv.text())} ul/min.")
            time.sleep(time_to_push_initial)
            pump_sens.setFlowRate(0)
            flowrate_sens.setValue(0)
            pump_emit.setFlowRate(total_FR)
            flowrate_emit.setValue(total_FR)
            self.print_to_message_box(f"Sensitizer: {int(flowrate_sens.text())} ul/min. Emitter: {int(flowrate_emit.text())} ul/min. Solvent: {int(flowrate_solv.text())} ul/min.")
            time.sleep(time_to_push_initial)

        pump_sens.setFlowRate(0)
        flowrate_sens.setValue(0)
        pump_emit.setFlowRate(0)
        flowrate_emit.setValue(0)
        
        self.print_to_message_box("System is cleaning")
        pump_solv.setFlowRate(total_FR)
        flowrate_solv.setValue(total_FR)

        time.sleep(time_to_flush+30)

        pump_solv.setFlowRate(0)
        flowrate_solv.setValue(0)
        self.cancelled = True

        self.print_to_message_box("End of dilution")

        self.start = False
        self.RunDilutionBtn.setEnabled(True)

    @pyqtSlot()
    def on_StopDilutionBtn_clicked(self):
        self.cancelled_dilution = True
        
        self.RunDilutionBtn.setEnabled(True)
        self.StopDilutionBtn.setEnabled(False)
        return
    

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=4, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class Worker(QObject):
    finished = pyqtSignal()
    func = None
    def run(self):
        self.func()
        self.finished.emit()
        return

def main():
    app = QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    app.setApplicationName("PyQt5 simple demo")
    form = MainWindow()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
