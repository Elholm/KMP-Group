#!/usr/bin/env python3

import os
import platform
import sys
import time
from tkinter import *
from tkinter.filedialog import asksaveasfilename

import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import globals
# from lib.avaspec import *  #Avantes spectrometer


import matplotlib
from GUI import TTA_GUI_win as TTA_window

matplotlib.use("Qt5Agg")
import matplotlib

matplotlib.use('agg')
from math import log10 as log
from statistics import mean

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
    sensitizer_pump = 'x'
    emitter_pump = 'x'
    solvent_pump = 'x'
    Spectrum_figure = plt.figure(dpi = 100)
    Power = 0
    spectral_measurement_simple = False

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.StartMeasBtn.setEnabled(False)
        self.StopDilutionBtn.setEnabled(False)
        self.actionHelpOxy.triggered.connect(self.show_help_oxy)
        self.log_name = "default_log.txt"

        # read com ports and print essential info
        for pinfo in serial.tools.list_ports.comports():
            print (pinfo.name, pinfo.serial_number, pinfo.vid)

        #Set calibration file
        self.CalibrationFileName.setText("532nm_2023-05-04 max119mW.txt")
        #set values
        self.min_flow_rate_box_A.setValue(1)
        self.min_flow_rate_box_B.setValue(1)
        self.Int_time_abs.setValue(0.04)
        self.avg_abs.setValue(3000)
        
        # Initialize all figures
        self.Spectrum_figure = MplCanvas() # Spectrum figure
        self.Spectrum_Layout.addWidget(self.Spectrum_figure)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Intensity")
        plt.tight_layout()
        plt.close()

        self.PLdynamics_figure = MplCanvas()
        self.PLdynamics_Layout.addWidget(self.PLdynamics_figure)
        plt.xlabel("Time [s]")
        plt.ylabel(f"PL intensity")
        plt.tight_layout()
        plt.close()
        
        self.Absorption_figure = MplCanvas()
        self.Absorption_Layout.addWidget(self.Absorption_figure)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Absorbance [OD]")
        plt.tight_layout()
        plt.close()

    @pyqtSlot() #Print time and message
    def print_to_message_box(self, text):
        t = time.localtime()
        current_time = time.strftime("%H:%M:%S", t)
        self.MsgBox.append(f"{current_time}  {text}")
        # QScrollBar *sb = ui->terminalTextBrowser()->verticalScrollBar();
        # sb->setValue(sb->maximum());
        return

############ SPECTROMETER CONTROL AND SPECTRAL MEASUREMENTS ##################################################
    @pyqtSlot() 
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
        # print(f'length of globals pixels in: {globals.pixels}')
        ret = AVS_GetLambda(globals.dev_handle,globals.wavelength)
        x = 0
        self.wavelength = np.array(ret[:globals.pixels])
        np_round_to_tenths = np.around(self.wavelength, 1)
        globals.wavelength = list(np_round_to_tenths)

        self.measconfig = MeasConfigType
        self.measconfig.m_StartPixel = 0
        self.measconfig.m_StopPixel = globals.pixels - 1
        self.measconfig.m_IntegrationTime = 0
        self.measconfig.m_IntegrationDelay = 0
        self.measconfig.m_NrAverages = 0
        self.measconfig.m_CorDynDark_m_Enable = 1  # nesting of types does NOT work!!
        self.measconfig.m_CorDynDark_m_ForgetPercentage = 100
        self.measconfig.m_Smoothing_m_SmoothPix = 2
        self.measconfig.m_Smoothing_m_SmoothModel = 0
        self.measconfig.m_SaturationDetection = 0
        self.measconfig.m_Trigger_m_Mode = 0
        self.measconfig.m_Trigger_m_Source = 0
        self.measconfig.m_Trigger_m_SourceType = 0
        self.measconfig.m_Control_m_StrobeControl = 0
        self.measconfig.m_Control_m_LaserDelay = 0
        self.measconfig.m_Control_m_LaserWidth = 0
        self.measconfig.m_Control_m_LaserWaveLength = 0.0
        self.measconfig.m_Control_m_StoreToRam = 0

        self.StartMeasBtn.setEnabled(False)
        self.StopMeasBtn.setEnabled(True)
        self.OpenCommBtn.setEnabled(False)
        self.CloseCommBtn.setEnabled(True)
        self.getDarkBtn.setEnabled(True)
        self.getLightBtn.setEnabled(True)
        self.Absorbance_reference_button.setEnabled(True)

        self.SpectrometerConnected = True

        self.on_Set_wavelength_btn_clicked()
        self.on_Set_wavelength_abs_btn_clicked()

        return

    @pyqtSlot()
    def on_CloseCommBtn_clicked(self):
        callbackclass.callback(self, 0, 0)
        self.StartMeasBtn.setEnabled(False)
        self.StopMeasBtn.setEnabled(False)
        self.OpenCommBtn.setEnabled(True)
        self.CloseCommBtn.setEnabled(False)
        self.Absorbance_reference_button.setEnabled(False)
        return

    @pyqtSlot()
    def Plot_new_spectrum(self, x,y):
        self.Spectrum_figure.axes.cla()
        self.Spectrum_figure.axes.plot(x, y)
        self.Spectrum_figure.axes.set_xlabel("Wavelength [nm]")
        self.Spectrum_figure.axes.set_ylabel("Intensity")
        self.Spectrum_figure.draw()

    @pyqtSlot()
    def on_Set_wavelength_btn_clicked(self):
        self.wavelengths_int = [int(eval(i)) for i in self.Wavelength_line.text().split(",")]
        self.background = int(self.Background_line.text())
        return
    
    @pyqtSlot()
    def on_Set_wavelength_abs_btn_clicked(self):
        self.wavelengths_int_abs = [int(eval(i)) for i in self.Wavelength_line_abs.text().split(",")]
        self.background_abs = int(self.Background_line_abs.text())
        return

    @pyqtSlot()
    def Plot_new_PLdynamics(self): #also removes absorption values and can be used to calculate threshold

        meta = 10 #how many places reserved for flow rates and other metadata in the file
        try:
            pddata = pd.read_csv(self.log_name, sep='\t', header=3)
        except:
            return
        p_index = [] #number of pl measures
        n_index = [] #number of abs measures
        na_index = [] #number of abs after measures
        p=0
        n=0
        na=0

        for x in range(len(pddata.iloc[:,0])): # find number of powers and total measurements
            if pddata.iloc[x,1] == f"Abs{n}":
                n += 1
                n_index.append(x) 
                continue
            elif pddata.iloc[x,1] == f"Absa{na+1}":
                na += 1
                na_index.append(x) 
                continue
            else:
                p += 1
                p_index.append(x) 

        print(n, na, p)
        wavelengths_pd = np.array(list(pddata)[meta:])
        wavelength_axis = np.around(wavelengths_pd.astype(float),1)
        bg_index = (np.abs(wavelength_axis - self.background)).argmin() + meta
        Dynamics = np.zeros(p)
        # Time = np.zeros(len(p_index))
        self.PLdynamics_figure.axes.clear()

        for wl in range(len(self.wavelengths_int)): # pl vs time plot
            wl_index = (np.abs(wavelength_axis - self.wavelengths_int[wl])).argmin() + meta
            i=0
            for p in p_index:
                # Time[i] = np.array(pddata.iloc[p,0])
                Dynamics[i] = pddata.iloc[p,wl_index] - pddata.iloc[p,bg_index]
                i+=1
            
            # Time_axis = np.around(Time.astype(float),2)
            Time_axis = range(i)
            self.PLdynamics_figure.axes.plot(Time_axis,Dynamics,label=wavelength_axis[wl_index-meta])
        self.PLdynamics_figure.axes.legend()
        self.PLdynamics_figure.axes.set_xlabel("Measurement #")
        self.PLdynamics_figure.axes.set_ylabel("Intensity")
        self.PLdynamics_figure.axes.set_yscale("log")
        self.PLdynamics_figure.draw()

        
        if self.AbsConc_checkBox.isChecked() == True: # absorbance vs time plot
            if self.spectral_measurement_simple == True:
                return
            Reference_abs = np.array(pddata.iloc[n_index[0],meta:])
            Signal_abs = np.array(pddata.iloc[n_index[-1],meta:]) #plot absorption last spectrum
            try:
                Absorbance = [log(Reference_abs[x] / Signal_abs[x]) if Signal_abs[x]>0 and Reference_abs[x]>0 else 0.0 for x in range(len(wavelength_axis))]
            except:
                return
            self.Absorption_figure.axes.clear()
            self.Absorption_figure.axes.plot(wavelength_axis,Absorbance,label=len(n_index))
            if len(n_index)>2:    
                Signal_abs = np.array(pddata.iloc[n_index[-2],meta:]) #plot absorption second-to-last spectrum
                try:
                    Absorbance = [log(Reference_abs[x] / Signal_abs[x]) if Signal_abs[x]>0 and Reference_abs[x]>0 else 0.0 for x in range(len(wavelength_axis))]
                except:
                    return
                self.Absorption_figure.axes.plot(wavelength_axis,Absorbance,'k--', label=len(n_index)-1)
            self.Absorption_figure.axes.legend()
            self.Absorption_figure.axes.set_xlabel("Wavelength [nm]")
            self.Absorption_figure.axes.set_ylabel("Absorbance [OD]")
        self.Absorption_figure.draw()

            # # self.PLdynamics_figure.axes[0].clear()
            # Dynamics_abs = np.zeros(len(n_index))
            # Time_abs = np.zeros(len(n_index))
            # bg_index_abs = (np.abs(wavelength_axis - self.background_abs)).argmin() + meta
            # for wl in range(len(self.wavelengths_int_abs)):
            #     wl_index = (np.abs(wavelength_axis - self.wavelengths_int_abs[wl])).argmin() + meta
            #     i=0
            #     for n in n_index:
            #         Time_abs[i] = np.array(pddata.iloc[n,0])
            #         Dynamics_abs[i] = log(Reference_abs[wl_index] / pddata.iloc[n,wl_index]) - log(Reference_abs[bg_index_abs] / pddata.iloc[n,bg_index_abs])
            #         i+=1
            #     Time_axis_abs = np.around(Time_abs.astype(float),2)
                
            #     self.PLdynamics_figure.axes.plot(Time_axis_abs,Dynamics_abs,label=wavelength_axis[wl_index-meta])
        return
        
    @pyqtSlot() #function for recording a spectrum.Exposure in miliseconds
    def Record_Spectrum(self,exp,avg): 
        ret = AVS_UseHighResAdc(globals.dev_handle, True)
        self.measconfig.m_IntegrationTime = exp
        self.measconfig.m_NrAverages = avg
        ret = AVS_PrepareMeasure(globals.dev_handle, self.measconfig)
        # nummeas = int(self.NumMeasEdt.text())
        timestamp = 0
        ret = AVS_Measure(globals.dev_handle, 0, 1)
        dataready = False
        while (dataready == False):
            dataready = (AVS_PollScan(globals.dev_handle) == True)
            time.sleep(0.001)
        if dataready == True:
            ret = AVS_GetScopeData(globals.dev_handle, timestamp, globals.spectraldata)
            timestamp = ret[0]
            x = 0
            for x in range(globals.pixels): # 0 through 2047
                globals.spectraldata[x] = int(ret[1][x])
            globals.spectraldata = [globals.spectraldata[x] for x in range(globals.pixels)]
        return
        
    @pyqtSlot()
    def on_StartMeasBtn_clicked(self): #activates when the button "Start Measurement" is clicked
        self.spectral_measurement_simple = True
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
        self.cancelled = True
        time.sleep(1)
        return

    @pyqtSlot()
    def on_StartMeasBtn_clicked_function(self):
        
        self.StartMeasBtn.setEnabled(False)
        self.getDarkBtn.setEnabled(False)
        self.getLightBtn.setEnabled(False)
        self.start = False
        self.cancelled = False
        nummeas = 0
        scans = 0
        # globals.ratio = []
        # globals.ratio_time = []

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
                    f.write(f"Exposure time: {float(self.IntTimeEdt.text())} ms, number of averages: {int(self.NumAvgEdt.text())}\n")
                    f.write(f"Total flow rate: {self.total_flow_rate_box.value()} ul/min, system volume: {self.SysVolBox.value()} ul, volume interval: {self.volume_interval_box.value()} ul\n")
                    f.write(f"Sensitizer {self.sample_name_A.text()} concentration: {self.prep_conc_box_A.value()} mM, emitter {self.sample_name_B.text()} concentration: {self.prep_conc_box_B.value()} mM, solvent {self.sample_name_C.text()}\n")
                    f.write('time(s)\tPower(mW)\tA\tB\tC\t'+'\t'.join(str(globals.wavelength[x]) for x in range(globals.pixels))+'\n')

        self.start = True

        exp = float(self.IntTimeEdt.text())
        avg = int(self.NumAvgEdt.text()) 
        if nummeas == 0:
            nummeas=100000
        while (scans < nummeas) and self.cancelled == False:
            self.Record_Spectrum(exp,avg)
            print(scans)
            scans = scans + 1
            temp_time = time.time() - t0
            self.new_time = str("{:.2f}".format(temp_time))
            

            if self.use_dark == True:
                globals.spectral_minus_dark = [globals.spectraldata[x] - globals.dark_spectrum[x] for x in range(globals.pixels)]
                self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)       
                with open(self.log_name,"a") as f:
                    f.write(str(self.new_time)+'\t'+str(self.Power*1000)+'\t')
                    f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                    f.write('\t'.join(str(globals.spectral_minus_dark[x]) for x in range(globals.pixels))+"\n")
                   
            
            elif self.use_light == True:
                globals.spectral_minus_light = [log(globals.light_spectrum[x] / globals.spectraldata[x]) if globals.spectraldata[x] != 0 else 0.0 for x in range(globals.pixels)]
                self.Plot_new_spectrum(globals.wavelength[:2048], globals.spectral_minus_light[:2048])
                # globals.spectral_minus_light = [0.0 - globals.spectraldata[x] + globals.light_spectrum[x] for x in range(globals.pixels)]
                with open(self.log_name,'a') as f:
                    f.write(str(self.new_time)+'\t'+str(self.Power*1000)+'\t')
                    f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                    f.write('\t'.join(str(globals.spectral_minus_light[x]) for x in range(globals.pixels))+"\n")

            else:
                self.print_to_message_box("you didnt choose dark or light spectrum wth")
            
            self.first = False
        
            self.Plot_new_PLdynamics()

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
        exp = float(self.IntTimeEdt.text())
        avg = int(self.NumAvgEdt.text()) 
        self.Record_Spectrum(exp,avg*3)
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
        exp = float(self.IntTimeEdt.text())
        avg = int(self.NumAvgEdt.text()) 
        self.Record_Spectrum(exp,avg*3)
        globals.light_spectrum = [globals.spectraldata[x] for x in range(globals.pixels)]
        self.print_to_message_box("Light spectrum measured")
        self.use_dark = False
        self.use_light = True
        self.StartMeasBtn.setEnabled(True)
        self.Plot_new_spectrum(globals.wavelength[:2048], globals.light_spectrum)
        return    

################ PUMP CONTROL ###################################################################
    @pyqtSlot()
    def on_Connect_Pumps_Button_clicked(self):
        self.PumpsConnected = False
        A_pump = False
        B_pump = False
        C_pump = False

        for pinfo in serial.tools.list_ports.comports():
            if pinfo.serial_number == '1107697' and pinfo.vid == 8169: #sensitizer syringe pump
                self.pump_sensitizer = serial.Serial(pinfo.device)
                self.print_to_message_box("sensitizer pump connected")
                self.StartFlowBtn_A.setEnabled(True)
                self.StopFlowBtn_A.setEnabled(True)
                A_pump = True
                continue
            if pinfo.serial_number == '1120394' and pinfo.vid == 8169: #emitter syringe pump
                self.pump_emitter = serial.Serial(pinfo.device)
                self.print_to_message_box("emitter pump connected")
                self.StartFlowBtn_B.setEnabled(True)
                self.StopFlowBtn_B.setEnabled(True)
                B_pump = True
                continue
            if pinfo.serial_number == '6' and pinfo.vid == 1027: #SF10 pump
                self.pump_solvent = serial.Serial(pinfo.device)
                serialcmd = str(f'GV\r')
                self.pump_solvent.write(serialcmd.encode())
                print(self.pump_solvent.readline().strip().decode("latin-1"))
                serialcmd = str(f'REMOTEEN vap9 1\r')
                self.pump_solvent.write(serialcmd.encode())
                print(self.pump_solvent.readline().strip().decode("latin-1"))
                serialcmd = str(f'MODE DOSE\r')
                self.pump_solvent.write(serialcmd.encode())
                serialcmd = str(f'START\r')
                self.pump_solvent.write(serialcmd.encode())
                serialcmd = str(f'STOP\r')
                self.pump_solvent.write(serialcmd.encode())
                print(self.pump_solvent.readline().strip().decode("latin-1"))
                self.print_to_message_box("solvent pump connected")
                self.StartFlowBtn_C.setEnabled(True)
                self.StopFlowBtn_C.setEnabled(True)
                C_pump = True
                continue
        
        if A_pump and B_pump and C_pump:
            self.PumpsConnected = True

    @pyqtSlot() #Simplified pump control function. See if there is no problem if 2 pumps get called at once
    def Pump(self,pump,rate,vol): #controls any pump with inputs
        if pump == 'A':
            serialcmd = str(f'irate {rate} u/m\r')
            self.pump_sensitizer.write(serialcmd.encode())
            serialcmd = str(f'civolume\r')
            self.pump_sensitizer.write(serialcmd.encode())
            serialcmd = str(f'tvolume {vol} ul\r')
            self.pump_sensitizer.write(serialcmd.encode())
            serialcmd = str(f'irun\r')
            self.pump_sensitizer.write(serialcmd.encode())
            return
        if pump == 'B':
            serialcmd = str(f'irate {rate} u/m\r')
            self.pump_emitter.write(serialcmd.encode())
            serialcmd = str(f'civolume\r')
            self.pump_emitter.write(serialcmd.encode())
            serialcmd = str(f'tvolume {vol} ul\r')
            self.pump_emitter.write(serialcmd.encode())
            serialcmd = str(f'irun\r')
            self.pump_emitter.write(serialcmd.encode())
            return
        if pump == 'C':
            # serialcmd = str(f'MODE DOSE\r')
            serialcmd = str(f'MODE FLOW\r')
            self.pump_solvent.write(serialcmd.encode())
            serialcmd = str(f'SETFLOW {rate/1000}\r')
            # self.pump_solvent.write(serialcmd.encode())
            # serialcmd = str(f'SETDOSE {vol/1000}\r')
            self.pump_solvent.write(serialcmd.encode())   
            serialcmd = str(f'SETREG 3.0\r')
            self.pump_solvent.write(serialcmd.encode())   
            serialcmd = str(f'START\r')
            self.pump_solvent.write(serialcmd.encode())            
            return
        else:
            return

    @pyqtSlot() # Pump A syringe pump for sensitizer
    def on_StartFlowBtn_A_clicked(self):
        rate = int(self.flow_rate_box_A.value() * (1 + self.Calib_pumpA.value()/100))
        self.Pump('A',rate,100)
        self.print_to_message_box(f"Pump sensitizer flow rate: {int(self.flow_rate_box_A.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_A_clicked(self):
        serialcmd = str(f'stop\r')
        self.pump_sensitizer.write(serialcmd.encode())
        # self.flow_rate_box_A.setValue(0)
        return
 
    @pyqtSlot() # Pump A syringe pump for emitter
    def on_StartFlowBtn_B_clicked(self):
        rate = int(self.flow_rate_box_B.value() * (1 + self.Calib_pumpB.value()/100))
        self.Pump('B',rate,100)
        self.print_to_message_box(f"Pump sensitizer flow rate: {int(self.flow_rate_box_B.text())} ul/min")

    @pyqtSlot()
    def on_StopFlowBtn_B_clicked(self):
        serialcmd = str(f'stop\r')
        self.pump_emitter.write(serialcmd.encode())
        # self.flow_rate_box_B.setValue(0)
        return

    @pyqtSlot() # Pump C SF10 pump for solvent
    def on_StartFlowBtn_C_clicked(self):
        rate = int(self.flow_rate_box_C.value() * (1 + self.Calib_pumpC.value()/100))
        self.Pump('C',rate,100)
        self.print_to_message_box(f"Pump solvent flow rate: {int(self.flow_rate_box_C.text())} ul/min")
        return

    @pyqtSlot()
    def on_StopFlowBtn_C_clicked(self):
        serialcmd = str(f'STOP\r')
        self.pump_solvent.write(serialcmd.encode())
        # self.flow_rate_box_C.setValue(0)
        return

############## DILUTION EXPERIMENT SETUP #################################

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
        
        # Depending on which dilution type is selected run will run different functions
        if self.Continuous_measurement.isChecked():
            self.worker_disp.func = self.Run_Dilution_continuous_function #here the job of the worker is defined. it should only be one function
        if self.Sequential_measurement.isChecked():
            self.worker_disp.func = self.Run_Dilution_Sequential_function

        self.worker_disp.moveToThread(self.thread_disp) #the workers job is moved from the frontend to the thread in backend
        self.thread_disp.started.connect(self.worker_disp.run) # when the thread is started, the worker runs
        self.worker_disp.finished.connect(self.thread_disp.quit) # when the worker is finished, the the thread is quit
        self.worker_disp.finished.connect(self.worker_disp.deleteLater)
        self.thread_disp.finished.connect(self.thread_disp.deleteLater)
        self.thread_disp.start() #here the thread is actually started
        return

    # @pyqtSlot()
    # def Run_Dilution_continuous_function(self, test=False): #Runs continuous experiment

        # if self.AbsConc_checkBox.isChecked() == True: # absorbance vs time plot
        #     #create subplot
        #     self.PLdynamics_figure = MplCanvas()
        #     self.PLdynamics_Layout.addWidget(self.PLdynamics_figure)
        #     self.PLdynamics_figure.axes.set_ylabel("Absorbance [OD]")
        #     self.PLdynamics_figure.axes.set_xlabel("Time [s]")
        #     plt.tight_layout()
        
        self.cancelled_dilution = False
        self.RunDilutionBtn.setEnabled(False)
        self.StopDilutionBtn.setEnabled(True)

        system_volume = int(self.SysVolBox.text())
        interval_volume = int(self.volume_interval_box.text())
        total_FR = int(self.total_flow_rate_box.text())

       
        #Create shortcuts for pumps and flow rate boxes
        # pump_sens = self.__dict__['pump' + self.sensitizer_pump]
        # pump_emit = self.__dict__['pump' + self.emitter_pump]
        # pump_solv = self.__dict__['pump' + self.solvent_pump]
        flowrate_sens = self.flow_rate_box_A
        flowrate_emit = self.flow_rate_box_B
        flowrate_solv = self.flow_rate_box_C
        calib_sens = self.Calib_pumpA
        calib_emit = self.Calib_pumpB
        calib_solv = self.Calib_pumpC

        # Flush solvent first to measure dark or light spectra 
        self.print_to_message_box("Solvent being flushed")
        rate = int(total_FR*(1+calib_solv.value()/100)*2)
        vol = int(system_volume+100)
        self.Pump('C',rate,vol)
        flowrate_solv.setValue(total_FR)
        time_to_flush = (system_volume+20) / total_FR * 60 #in seconds
        time_to_push = interval_volume / total_FR * 60 #in seconds     
        time.sleep(time_to_flush/2)
        self.Pump('C',0,vol) #solvent pump does not have a volume limiter
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
            self.on_StartPowerBtn_clicked()
            while self.start == False:
                if not self.log_name:
                    self.start = False
                    self.RunDilutionBtn.setEnabled(True)
                    return
                time.sleep(1)

        # # Scan concentrations in two cycles
        # for n in range(len(globals.emitter_concentrations)):
        #     for m in range(len(globals.sensitizer_concentrations)):
        #         if globals.sens_flowrates[n,m] != 0 and globals.emit_flowrates[n,m] != 0 and globals.solv_flowrates[n,m] != 0 and self.cancelled_dilution == False:
        #             self.print_to_message_box(f"Sensitizer: {int(globals.sens_flowrates[n,m])} ul/min. Emitter: {int(globals.emit_flowrates[n,m])} ul/min. Solvent: {int(globals.solv_flowrates[n,m])} ul/min.")
        #             pump_sens.setFlowRate(globals.sens_flowrates[n,m])
        #             flowrate_sens.setValue(int(globals.sens_flowrates[n,m]))
        #             pump_emit.setFlowRate(globals.emit_flowrates[n,m])
        #             flowrate_emit.setValue(int(globals.emit_flowrates[n,m]))
        #             pump_solv.setFlowRate(globals.solv_flowrates[n,m])
        #             flowrate_solv.setValue(int(globals.solv_flowrates[n,m]))
                    
        #             if n == 0 and m == 0:
        #                 time.sleep(time_to_push_initial)
        #             else:
        #                 time.sleep(time_to_push)


        # Scan concentrations in zig-zags
        direction = 1 #left to right
        n = 0 #emitter conc.
        m = 0 #sensitizer conc.
        iteration = 0 #itterations to set table color
        system_iteration = system_volume/interval_volume
        coordinates = []
        while self.cancelled_dilution == False:
            
            # if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0: #check if any of current flow rates are 0
            #     break

            self.concentration_table_solvent.item(n,m).setBackground(QColor(125,255,0,100)) #set light green color for current
            coordinates.append([n,m])
            if int(iteration-system_iteration) >= 0:
                c = []
                c = coordinates[int(iteration-system_iteration)]
                self.concentration_table_solvent.item(c[0],c[1]).setBackground(QColor(34,139,34,100)) #set dark green color for measured
                # self.concentration_table_solvent.refresh()
            iteration +=1
            QAbstractItemView.reset(self.concentration_table_solvent) #reset to see changes
                
            # self.print_to_message_box(f"Sensitizer: {int(globals.sens_flowrates[n,m])} ul/min. Emitter: {int(globals.emit_flowrates[n,m])} ul/min. Solvent: {int(globals.solv_flowrates[n,m])} ul/min.")
            rate = globals.sens_flowrates[n,m]*(1+calib_sens.value()/100) #Set sensitizer flow rate
            vol = int(rate * interval_volume / total_FR)
            self.Pump('A',rate,vol)
            flowrate_sens.setValue(rate)

            rate = globals.emit_flowrates[n,m]*(1+calib_emit.value()/100) #Set emitter flow rate
            vol = int(rate * interval_volume / total_FR)
            self.Pump('B',rate,vol)
            flowrate_emit.setValue(rate)

            rate = globals.solv_flowrates[n,m]*(1+calib_solv.value()/100) #Set solvent flow rate
            vol = int(rate * interval_volume / total_FR)
            self.Pump('C',rate,vol)
            flowrate_solv.setValue(rate)

            time.sleep(time_to_push)
            
            if direction == 1:
                if  m+1 == len(globals.sensitizer_concentrations) or globals.sens_flowrates[n,m+1] == 0 or globals.emit_flowrates[n,m+1] == 0 or globals.solv_flowrates[n,m+1] == 0: #check to the right if any of the flow rates is 0
                        n += 1
                        direction = 0
                        if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                            m -= 1
                else:
                    m += 1
                # End concentration cycle when there is nowhere to go below. Restore n and m to last working values
                if n+1 == len(globals.emitter_concentrations) or globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0: 
                    m += 1 
                    n -= 1
                    break
                continue
            
            if direction == 0:
                if m == 0: 
                    n += 1
                    direction = 1
                    # End concentration cycle when there is nowhere to go below. Restore n and m to last working values
                    if n+1 == len(globals.emitter_concentrations) or globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0: 
                        n -= 1
                        break
                else:
                    m -= 1
                continue
            # end of concentration change cycle

        
        self.Pump('C',0,vol) #solvent pump does not have a volume limiter
        flowrate_solv.setValue(0)
        flowrate_emit.setValue(0)
        flowrate_sens.setValue(0)
        
        self.print_to_message_box("System is cleaning") #clean system with solvent
        self.Pump('C',total_FR,vol) 
        flowrate_solv.setValue(total_FR)
        time.sleep(time_to_flush+20)
        self.Pump('C',0,vol) 
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

    @pyqtSlot()
    def Run_Dilution_Sequential_function(self): #Runs sequential mix-degas-stop-measure experiment
        # Load first sequences without measuremnent
        # wait 1 s after setting power before measurement

        self.cancelled_dilution = False
        self.RunDilutionBtn.setEnabled(False)
        self.StopDilutionBtn.setEnabled(True)

        system_volume = int(self.SysVolBox.text())
        interval_volume = int(self.volume_interval_box.text())
        total_FR = int(self.total_flow_rate_box.text())
        flowrate_sens = self.flow_rate_box_A
        flowrate_emit = self.flow_rate_box_B
        flowrate_solv = self.flow_rate_box_C
        calib_sens = self.Calib_pumpA
        calib_emit = self.Calib_pumpB
        calib_solv = self.Calib_pumpC

        # setup for power measurements
        if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
            # create array of power values
            P_min = self.minP_box.value()/1000
            P_max = self.maxP_box.value()/1000
            P_off = 10/1000000
            points = int(self.PowerNumber_box.value())
            Filename = self.CalibrationFileName.text()
            Power_calibration = pd.read_csv(f'VOA calibration/{Filename}',sep='\s+', header=1)
            P_array = np.asarray(Power_calibration.iloc[:,1])
            # find the existing min and max values before 
            Pmin_index = (np.abs(P_array - P_min)).argmin()
            P_min = Power_calibration.iloc[Pmin_index,1]
            Pmax_index = (np.abs(P_array - P_max)).argmin()
            P_max = Power_calibration.iloc[Pmax_index,1]
            Poff_index = (np.abs(P_array - P_off)).argmin()           
            # Power_arr = np.linspace(P_min, P_max, points)
            Power_arr = np.geomspace(P_min, P_max, num=points)
            Power_maximum = np.max(Power_arr) #maximum power for reverse powe scan divider calculations
            # print(Power_arr)
            # print(Power_maximum)
            # send att to beginning
            Att_value = Power_calibration.iloc[Poff_index,0]
            serialcmd = str(f'S{int(Att_value)}\r')
            self.Attenuator.write(serialcmd.encode())
            Att_read = "lol"
            while Att_read != "Done":
                Att_read = self.Attenuator.readline().strip().decode("latin-1")
                time.sleep(0.1)
        else:
            self.print_to_message_box("Attenuator not used, current laser power")
        
        t0 = time.time()

        #ask to save file and insert metadata 
        root = Tk()
        root.withdraw()
        t = time.localtime()
        current_time = time.strftime("%Y-%m-%d", t)
        filename = str(f'TTAUC_{current_time}.txt')
        self.log_name = asksaveasfilename(initialdir="logs/",initialfile=filename, defaultextension=".txt")
        root.destroy()
        if not self.log_name:
            self.StartPowerBtn.setEnabled(True)
            return
        with open(self.log_name,"w") as f:
            f.write(f"Exposure time: {float(self.IntTimeEdt.text())} ms, number of averages: {int(self.NumAvgEdt.text())}\n")
            f.write(f"Total flow rate: {self.total_flow_rate_box.value()} ul/min, system volume: {self.SysVolBox.value()} ul, volume interval: {self.volume_interval_box.value()} ul\n")
            f.write(f"Sensitizer {self.sample_name_A.text()} concentration: {self.prep_conc_box_A.value()} mM, emitter {self.sample_name_B.text()} concentration: {self.prep_conc_box_B.value()} mM, solvent {self.sample_name_C.text()}\n")
            f.write('time(s)\tPower(mW)\tExposure(ms)\tA\tB\tC\t'+'\t'.join(str(globals.wavelength[x]) for x in range(globals.pixels))+'\n')

        time.sleep(5)
        # Flush solvent first to measure dark or light spectra 
        # self.print_to_message_box("Solvent being flushed")
        # rate = int(total_FR*(1+calib_solv.value()/100) * 2)
        # vol = int(system_volume+100)
        # self.Pump('C',rate,vol)
        # flowrate_solv.setValue(total_FR)
        # time_to_flush = int((system_volume+20) / total_FR * 60) #in seconds
        # time_to_push = int(interval_volume / total_FR * 60) #in seconds     
        # time.sleep(time_to_flush/2)
        # self.Pump('C',0,vol) #solvent pump does not have a volume limiter
        # flowrate_solv.setValue(0)
        # self.print_to_message_box("Solvent flushing finished, prepare for dark measurement")
        time_to_push = int(interval_volume / total_FR * 60) #in seconds     

        
        # Initiate spectral measurements and create file
        self.spectral_measurement_simple = False
        self.StartPowerBtn.setEnabled(False)

        # Measure reference absorbance spectra [Abs0] if not measured already 
        if self.AbsConc_checkBox.isChecked() == True: # open lamp shutter, measure transmitted light, close shutter. Use constant exposure        
            
            if self.Abs_ref_done.checkState() == False: # for Abs0 use reference spectra measured before:
                self.on_Absorbance_reference_button_clicked()      
            
            new_time = round(time.time()-t0,2)
            Abs = f'Abs0'
            with open(self.log_name,"a") as f:
                f.write(str(new_time)+'\t'+str(Abs)+'\t'+str(self.Int_time_abs.value())+'\t')
                f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                f.write('\t'.join(str(self.Abs_ref_spectrum[x]) for x in range(globals.pixels))+"\n")
            time.sleep(3)

        # Initiate mixing and recording.........................................................................

        # Scan concentrations in zig-zags
        direction = 1 #left to right
        n = 0 #emitter conc.
        m = 0 #sensitizer conc.
        iteration = 0 #itterations to set table color
        iteration_end = 0 #itterations to measure several more cycles at the end of conc table
        system_iteration = system_volume/interval_volume
        coordinates = []
        # PL recording parameters
        exc_wl = float(self.Exc_wl_box.value())
        exc_wl_index = (np.abs(self.wavelength - exc_wl)).argmin()
        exp_init = float(self.IntTimeEdt.text())
        avg_init = int(self.NumAvgEdt.text())
        div = 1
        meas = 1
        extra = 2
        
        while self.cancelled_dilution == False and iteration_end < system_iteration + extra: # stop only after all samples are pushed out degasser.
            print(f"iteration {iteration}, end iteration {iteration_end}, direction {direction}, sensitizer conc #{m}, emitter conc #{n}")

            # pump only solvent and measure for several more cycles to get last concentrations            
            if 0 < iteration_end < system_iteration + extra:
                rate = int(total_FR*(1+calib_solv.value()/100)) #Set solvent flow rate
                vol = int(interval_volume)
                self.Pump('C',rate,vol)
                flowrate_solv.setValue(rate)
                time.sleep(time_to_push)
                iteration_end += 1
                
                #continue dark green coloring
                try:
                    c = []
                    c = coordinates[int(iteration-system_iteration)]
                    self.concentration_table_solvent.item(c[0],c[1]).setBackground(QColor(34,139,34,100)) #set dark green color for measured
                    iteration +=1
                    QAbstractItemView.reset(self.concentration_table_solvent) #reset to see changes
                except:
                    print('end of predicted dilution')
            
            # Mix components from concentration table
            else:
                #set light green color for current
                self.concentration_table_solvent.item(n,m).setBackground(QColor(125,255,0,100))
                coordinates.append([n,m])
                if int(iteration-system_iteration) >= 0:
                    c = []
                    c = coordinates[int(iteration-system_iteration)]
                    self.concentration_table_solvent.item(c[0],c[1]).setBackground(QColor(34,139,34,100)) #set dark green color for measured
                    # self.concentration_table_solvent.refresh()
                iteration +=1
                QAbstractItemView.reset(self.concentration_table_solvent) #reset to see changes

                rate = int(globals.sens_flowrates[n,m]*(1+calib_sens.value()/100)) #Set sensitizer flow rate
                vol = int(rate * interval_volume / total_FR)
                self.Pump('A',rate,vol)
                flowrate_sens.setValue(rate)

                rate = int(globals.emit_flowrates[n,m]*(1+calib_emit.value()/100)) #Set emitter flow rate
                vol = int(rate * interval_volume / total_FR)
                self.Pump('B',rate,vol)
                flowrate_emit.setValue(rate)

                rate = int(globals.solv_flowrates[n,m]*(1+calib_solv.value()/100)) #Set solvent flow rate
                # rate = int(total_FR)
                vol = int(rate * interval_volume / total_FR)
                self.Pump('C',rate,vol)
                flowrate_solv.setValue(rate)

                # # For constant flow rate only from one pump
                # rate = int(total_FR) #Set solvent flow rate
                # vol = int(interval_volume)
                # self.Pump('C',rate,vol)
                # flowrate_solv.setValue(rate)

                time.sleep(time_to_push)

                # Determine direction for next measurement
                if direction == 1:
                    if m+1 == len(globals.sensitizer_concentrations) or globals.sens_flowrates[n,m+1] == 0 or globals.emit_flowrates[n,m+1] == 0 or globals.solv_flowrates[n,m+1] == 0: #check to the right if any of the flow rates is 0
                            n += 1
                            direction = 0
                            if n == len(globals.emitter_concentrations): #End if limit is reached
                                iteration_end += 1
                            else:
                                if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                    m -= 1
                                    if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                        m -= 1
                                        if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                            m -= 1
                                            if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                                m -= 1
                                                if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                                    m -= 1
                                                    if globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0:
                                                        m -= 1
                    else:
                        m += 1
                    
                    # Double chech if lines bellow have meaning
                    # # End concentration cycle when there is nowhere to go below. Restore n and m to last working values
                    # if n == len(globals.emitter_concentrations) or globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0: 
                    #     iteration_end += 1
                    #     m += 1 
                    #     n -= 1
                
                else: # direction == 0
                    if m == 0: 
                        n += 1
                        direction = 1
                    else:
                        m -= 1
                    # End concentration cycle when there is nowhere to go below. Restore n and m to last working values
                    if n == len(globals.emitter_concentrations) or globals.sens_flowrates[n,m] == 0 or globals.emit_flowrates[n,m] == 0 or globals.solv_flowrates[n,m] == 0: 
                        iteration_end += 1
                        n -= 1

            # Stop all pumps before measurement
            self.on_StopFlowBtn_A_clicked()
            self.on_StopFlowBtn_B_clicked()
            self.on_StopFlowBtn_C_clicked()

            # Set 2mW laser power for oxygen scavenging capacity
            if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
                Power_index = (np.abs(P_array - 2/1000)).argmin()
                Att_value = Power_calibration.iloc[Power_index,0]
                # Set power in attenuator
                serialcmd = str(f'S{int(Att_value)}\r')
                self.Attenuator.write(serialcmd.encode())     # Go to value
                Att_read = "lol"
                while Att_read != "Done":
                    Att_read = self.Attenuator.readline().strip().decode("latin-1")
                    time.sleep(0.01)

            time.sleep(8) # wait some time to disperse in the flow cell and oxygen scavenging
           
            # Measure absorbance before. open lamp shutter, measure transmitted light, close shutter. Use constant exposure
            if self.AbsConc_checkBox.isChecked() == True: 
                AVS_SetDigOut(globals.dev_handle, 3, 1) #Lamp shutter open. OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                time.sleep(0.5)
                self.Record_Spectrum(self.Int_time_abs.value(),self.avg_abs.value())
                new_time = round(time.time()-t0,2)
                Abs = f'Abs{meas}'
                # self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)       
                with open(self.log_name,"a") as f:
                    f.write(str(new_time)+'\t'+str(Abs)+'\t'+str(self.Int_time_abs.value())+'\t')
                    f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                    f.write('\t'.join(str(globals.spectraldata[x]) for x in range(globals.pixels))+"\n")
                AVS_SetDigOut(globals.dev_handle, 3, 0) #Lamp shutter close. OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                time.sleep(0.1)

            # Measure Emission vs power.............................................................................................................
            if iteration > 0: #int(0.5*system_iteration): # Begin measurement only after some itterations have passed

                if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
                    for Power in Power_arr:
                        # Find attenuator value for power in calibration table
                        Power_index = (np.abs(P_array - Power)).argmin()
                        self.Power = Power_calibration.iloc[Power_index,1] #read real power
                        Att_value = Power_calibration.iloc[Power_index,0]
                        # Set power in attenuator
                        serialcmd = str(f'S{int(Att_value)}\r')
                        self.Attenuator.write(serialcmd.encode())     # Go to value
                        Att_read = "lol"
                        while Att_read != "Done":
                            Att_read = self.Attenuator.readline().strip().decode("latin-1")
                            time.sleep(0.01)
                        
                        # Wait some time before measurement
                        time.sleep(3) 
                        Power = round(1000*self.Power,4)

                        # Record spectrum with dynamic parameters to avoid emission signal saturation
                        remeasure = True
                        while remeasure == True:
                            exp = exp_init * Power_maximum / self.Power / div #think how to limit changes at low power range to keep total exposure time low
                            avg = int(avg_init / Power_maximum * self.Power * div)
                            if exp > 7000:
                                exp = 7000
                                avg = 1
                            if avg < 1:
                                avg = 1
                            self.Record_Spectrum(exp,avg)
                            # time.sleep(exp*avg/1000)
                            time.sleep(0.2)

                            # dynamically set exposure time divider based on last measured spectrum. 
                            # if self.Scatter_checkBox.isChecked() == False: 
                            intensity_minus_excitation_wavelength = globals.spectraldata[:exc_wl_index-10] + globals.spectraldata[exc_wl_index+10:] #Exclude excitation wl for scattering
                            max_intensity = np.max(intensity_minus_excitation_wavelength)
                            print(f"scan: {meas}, power: {Power}mW, divider: {div}, max intensity: {max_intensity}")

                            if max_intensity > 60000: #increase divider for strong signals
                                div = div * 2
                            else:
                                remeasure = False
                                break

                        new_time = round(time.time()-t0,2)
                        
                        with open(self.log_name,"a") as f:
                            f.write(str(new_time)+'\t'+str(Power)+'\t'+str(exp)+'\t')
                            f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                            f.write('\t'.join(str(globals.spectraldata[x]/exp) for x in range(globals.pixels))+"\n")
                        
                        if self.Power == Power_maximum: #print only maximum spectrum
                            self.P_max_spectrum = globals.spectraldata
                            self.Plot_new_spectrum(globals.wavelength, self.P_max_spectrum)
                            print("spectrum plotted")

                    # # send to zero before absorption measurement, wait 1s
                    # Att_value = Power_calibration.iloc[Poff_index,0]
                    # serialcmd = str(f'S{int(Att_value)}\r')
                    # self.Attenuator.write(serialcmd.encode())
                    # Att_read = "lol"
                    # while Att_read != "Done":
                    #     Att_read = self.Attenuator.readline().strip().decode("latin-1")
                    #     time.sleep(0.2)
                    # time.sleep(1)
    
                
                if 1000 < max_intensity < 15000: #reduce divider for weak signals, but only after all powers were measured not to infinitely increase no emission divider
                    div = div / 2
                    
                
                self.Plot_new_PLdynamics() #replot pl dynamics only after full power cycle
                self.meas_num.setText(f"Measurement: {meas}")
                self.time_elapsed.setText(f"Time: {new_time} s")
                print("dynamics plotted")
        
            # Measure absorbance after PL measurement
            if self.AbsConc_checkBox.isChecked() == True: 
                AVS_SetDigOut(globals.dev_handle, 3, 1) #Lamp shutter open. OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                time.sleep(0.5)
                self.Record_Spectrum(self.Int_time_abs.value(),self.avg_abs.value())
                new_time = round(time.time()-t0,2)
                Abs = f'Absa{meas}'
                # self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)       
                with open(self.log_name,"a") as f:
                    f.write(str(new_time)+'\t'+str(Abs)+'\t'+str(self.Int_time_abs.value())+'\t')
                    f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                    f.write('\t'.join(str(globals.spectraldata[x]) for x in range(globals.pixels))+"\n")
                AVS_SetDigOut(globals.dev_handle, 3, 0) #Lamp shutter close. OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                time.sleep(0.1)
            
            meas += 1

        #Stop all pumps
        self.on_StopFlowBtn_A_clicked()
        self.on_StopFlowBtn_B_clicked()
        self.on_StopFlowBtn_C_clicked()
        
        # self.print_to_message_box("System is cleaning") #clean system with solvent
        # self.Pump('C',total_FR*2,vol) 
        # flowrate_solv.setValue(total_FR*2)
        # time.sleep(time_to_flush/2+20)
        # self.on_StopFlowBtn_C_clicked()

        self.print_to_message_box("End of dilution")

        self.start = False
        self.RunDilutionBtn.setEnabled(True)



############### ATTENUATOR AND POWER MEASUREMENT SETUP #########################################
    @pyqtSlot()
    def on_Absorbance_reference_button_clicked(self):
        AVS_SetDigOut(globals.dev_handle, 3, 1) #OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
        time.sleep(0.2)
        self.Record_Spectrum(self.Int_time_abs.value(),self.avg_abs.value())
        self.Abs_ref_spectrum = globals.spectraldata
        AVS_SetDigOut(globals.dev_handle, 3, 0) #OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
        self.Abs_ref_done.setCheckState(True)
        self.Plot_new_spectrum(globals.wavelength, globals.spectraldata)

    @pyqtSlot() 
    def on_ConnAtten_clicked(self):
        
        for pinfo in serial.tools.list_ports.comports():
            if pinfo.serial_number == '7' and pinfo.vid == 1027:  #attenuator connection
                self.Attenuator = serial.Serial(pinfo.device)
                self.Attenuator.close()
                self.Attenuator.open()
                self.Attenuator.write(b'H')     # Go home attenuator
                Att_read = "not"
                while Att_read != "Done":
                    Att_read = self.Attenuator.readline().strip().decode("latin-1")
                serialcmd = str(f'S{10000}\r')
                self.Attenuator.write(serialcmd.encode())
                while Att_read != "Done":
                    Att_read = self.Attenuator.readline().strip().decode("latin-1")
                time.sleep(1)
            
                self.AttenuatorConnected = True
                self.print_to_message_box("Attenuator connected and sent home")
                self.SetAtten.setEnabled(True)
                self.StartPowerBtn.setEnabled(True)
                self.StopPowerBtn.setEnabled(True)

    @pyqtSlot() 
    def on_SetAtten_clicked(self):

        if self.AttenuatorConnected == True:
            #  Find attenuator value for power
            Power = self.PowerValue_box.value()/1000 #convert to watts
            Filename = self.CalibrationFileName.text()
            Power_calibration = pd.read_csv(f'Calibration files/{Filename}',sep='\s+', header=1)
            P_array = np.asarray(Power_calibration.iloc[:,1])
            Power_index = (np.abs(P_array - Power)).argmin()
            self.Power = Power_calibration.iloc[Power_index,1] #read real power
            Att_value = Power_calibration.iloc[Power_index,0]
            # Set power in attenuator
            serialcmd = str(f'S{int(Att_value)}\r')
            self.Attenuator.write(serialcmd.encode())     # Go to value
            Att_read = "lol"
            while Att_read != "Done":
                Att_read = self.Attenuator.readline().strip().decode("latin-1")
                time.sleep(0.05)
            self.print_to_message_box(f"Attenuator set to: {round(1000*self.Power,6)} mW")
        else:
            self.print_to_message_box("Attenuator not connected")

    @pyqtSlot()
    def on_StartPowerBtn_clicked(self):
        try:
            if self.thread_pwr.isRunning():
                print("Shutting down running thread.")
                self.thread_prw.terminate()
                time.sleep(1)
            else:
                print("No thread was running.")
        except:
            print("Didn't find thread.")
        self.thread_pwr = QThread() # this created an additional computing thread for processes, so the main window doesn't freeze
        self.worker_pwr = Worker() # this is a worker that will tell when the job is done
        self.worker_pwr.func = self.on_StartPowerBtn_function #here the job of the worker is defined. it should only be one function
        self.worker_pwr.moveToThread(self.thread_pwr) #the workers job is moved from the frontend to the thread in backend
        self.thread_pwr.started.connect(self.worker_pwr.run) # when the thread is started, the worker runs
        self.worker_pwr.finished.connect(self.thread_pwr.quit) # when the worker is finished, the the thread is quit
        self.worker_pwr.finished.connect(self.worker_pwr.deleteLater)
        self.thread_pwr.finished.connect(self.thread_pwr.deleteLater)
        self.thread_pwr.start() #here the thread is actually started
        return
    
    @pyqtSlot() 
    def on_StopPowerBtn_clicked(self):
        self.cancelled = True
        self.StartPowerBtn.setEnabled(True)
        self.StopPowerBtn.setEnabled(False)
        time.sleep(1)
        return

    @pyqtSlot() 
    def on_StartPowerBtn_function(self): # starts power measurements of luminescence
        
        self.spectral_measurement_simple = False
        self.StartPowerBtn.setEnabled(False)
        self.start = False
        self.cancelled = False
        
        #ask to save file and insert metadata send self.start signal
        root = Tk()
        root.withdraw()
        t = time.localtime()
        current_time = time.strftime("%Y-%m-%d", t)
        filename = str(f'TTAUC_{current_time}.txt')
        self.log_name = asksaveasfilename(initialdir="logs/",initialfile=filename, defaultextension=".txt")
        root.destroy()
        if not self.log_name:
            self.StartPowerBtn.setEnabled(True)
            return
        with open(self.log_name,"w") as f:
            f.write(f"Exposure time: {float(self.IntTimeEdt.text())} ms, number of averages: {int(self.NumAvgEdt.text())}\n")
            f.write(f"Total flow rate: {self.total_flow_rate_box.value()} ul/min, system volume: {self.SysVolBox.value()} ul, volume interval: {self.volume_interval_box.value()} ul\n")
            f.write(f"Sensitizer {self.sample_name_A.text()} concentration: {self.prep_conc_box_A.value()} mM, emitter {self.sample_name_B.text()} concentration: {self.prep_conc_box_B.value()} mM, solvent {self.sample_name_C.text()}\n")
            f.write('time(s)\tPower(mW)\tExposure(ms)\tA\tB\tC\t'+'\t'.join(str(globals.wavelength[x]) for x in range(globals.pixels))+'\n')
        self.start = True

        # Setup power attenuator values
        if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
            # create array of power values
            P_min = self.minP_box.value()/1000
            P_max = self.maxP_box.value()/1000
            points = int(self.PowerNumber_box.value())
            Filename = self.CalibrationFileName.text()
            Power_calibration = pd.read_csv(f'Calibration files/{Filename}',sep='\s+', header=1)
            P_array = np.asarray(Power_calibration.iloc[:,1])
            # find the existing min and max values before 
            Pmin_index = (np.abs(P_array - P_min)).argmin()
            P_min = Power_calibration.iloc[Pmin_index,1]
            Pmax_index = (np.abs(P_array - P_max)).argmin()
            P_max = Power_calibration.iloc[Pmax_index,1]
            # Power_arr = np.linspace(P_min, P_max, points)
            Power_arr = np.geomspace(P_min, P_max, num=points)
            # send att to beginning
            Att_value = Power_calibration.iloc[Pmin_index,0]
            serialcmd = str(f'S{int(Att_value)}\r')
            self.Attenuator.write(serialcmd.encode())
            Att_read = "lol"
            while Att_read != "Done":
                Att_read = self.Attenuator.readline().strip().decode("latin-1")
                time.sleep(0.1)
            t0 = time.time()
        else:
            self.print_to_message_box("Attenuator not used, maximum laser power")

        div = 1
        exc_wl = float(self.Exc_wl_box.value())
        exc_wl_index = (np.abs(self.wavelength - exc_wl)).argmin()
        print(exc_wl_index)
        exp_init = float(self.IntTimeEdt.text())
        avg_init = int(self.NumAvgEdt.text())
        x=0

        while self.cancelled == False:
            if self.cancelled == True:
                break
            
            # Measure absorbance. open lamp shutter, measure transmitted light, close shutter. Use constant exposure
            if self.AbsConc_checkBox.isChecked() == True: 
                
                if x == 0 and self.Abs_ref_done.isChecked() == True: # for Abs0 use reference spectra measured before
                    new_time = round(time.time()-t0,2)
                    Abs = f'Abs{x}'
                    with open(self.log_name,"a") as f:
                        f.write(str(new_time)+'\t'+str(Abs)+'\t'+str(self.Int_time_abs.value())+'\t')
                        f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                        f.write('\t'.join(str(self.Abs_ref_spectrum) for x in range(globals.pixels))+"\n")
                else:
                    AVS_SetDigOut(globals.dev_handle, 3, 1) #OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                    time.sleep(0.1)
                    self.Record_Spectrum(self.Int_time_abs.value(),self.avg_abs.value())
                    new_time = round(time.time()-t0,2)
                    Abs = f'Abs{x}'
                    # self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)       
                    with open(self.log_name,"a") as f:
                        f.write(str(new_time)+'\t'+str(Abs)+'\t'+str(self.Int_time_abs.value())+'\t')
                        f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                        f.write('\t'.join(str(globals.spectraldata[x]) for x in range(globals.pixels))+"\n")
                    AVS_SetDigOut(globals.dev_handle, 3, 0) #OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
                time.sleep(0.1)

            # Measure PL at different excitation powers
            if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
                
                for Power in Power_arr:
                    # Find attenuator value for power in calibration table
                    Power_index = (np.abs(P_array - Power)).argmin()
                    self.Power = Power_calibration.iloc[Power_index,1] #read real power
                    Att_value = Power_calibration.iloc[Power_index,0]
                    # Set power in attenuator
                    serialcmd = str(f'S{int(Att_value)}\r')
                    self.Attenuator.write(serialcmd.encode())     # Go to value
                    Att_read = "lol"
                    while Att_read != "Done":
                        Att_read = self.Attenuator.readline().strip().decode("latin-1")
                        time.sleep(0.01)
                    time.sleep(0.8)
                    Power = round(1000*self.Power,4)
                    
                    # Record spectrum with dynamic parameters
                    exp = exp_init * P_max / self.Power / div #think how to limit changes at low power range to keep total exposure time low
                    avg = int(avg_init / P_max * self.Power * div)
                    if exp > 5000:
                        exp = 5000
                        avg = 1
                    if avg < 1:
                        avg = 1
                    self.Record_Spectrum(exp,avg)

                    new_time = round(time.time()-t0,2)
                    globals.spectral_minus_dark = [(globals.spectraldata[x]-globals.dark_spectrum[x]) for x in range(globals.pixels)]
                     
                    with open(self.log_name,"a") as f:
                        f.write(str(new_time)+'\t'+str(Power)+'\t'+str(exp)+'\t')
                        f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
                        f.write('\t'.join(str(globals.spectral_minus_dark[x]/exp) for x in range(globals.pixels))+"\n")
                    
                    # if Power == Power_arr[0] or Power == Power_arr[-1]: #print only first and last spectrum
                self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)
  
            # Dynamically set exposure time divider based on last measured spectrum, but only for non scattering sample. Exclude excitation wl
            print(f"scan {x} divider {div}")
            if self.Scatter_checkBox.isChecked() == False:
                intensity_minus_excitation_wavelength = globals.spectral_minus_dark[:exc_wl_index-10] + globals.spectral_minus_dark[exc_wl_index+10:]
                max_intensity = np.max(intensity_minus_excitation_wavelength)
                print(max_intensity)

                if max_intensity > 63000:
                    div = div * 4
                if 63000 > max_intensity > 40000:
                    div = div * 2
                if 1000 < max_intensity < 20000: #dont reduce divider for weak signals
                    div = div / 2
            
            # else: #record spectrum without power modulation
            #     exp = exp_init / div #think how to limit changes at low power range to keep total exposure time low
            #     avg = int(avg_init * div)
            #     if exp > 1000:
            #         exp = 1000
            #         avg = 1
            #     if avg < 1:
            #         avg = 1
            #     self.Record_Spectrum(exp,avg)
            #     new_time = round(time.time()-t0,2)
            #     globals.spectral_minus_dark = [(globals.spectraldata[x]-globals.dark_spectrum[x])/exp for x in range(globals.pixels)]
            #     self.Plot_new_spectrum(globals.wavelength, globals.spectral_minus_dark)
            #     with open(self.log_name,"a") as f:
            #         f.write(str(new_time)+'\t'+str(self.Power*1000)+'\t')
            #         f.write(self.flow_rate_box_A.text()+'\t'+self.flow_rate_box_B.text()+'\t'+self.flow_rate_box_C.text()+'\t')
            #         f.write('\t'.join(str(globals.spectral_minus_dark[x]) for x in range(globals.pixels))+"\n")

            # Attenuator send to zero before absorption measurement, wait 1s
            if self.PwrMod_checkBox.isChecked() == True and self.AttenuatorConnected == True:
                Att_value = Power_calibration.iloc[Pmin_index,0]
                serialcmd = str(f'S{int(Att_value)}\r')
                self.Attenuator.write(serialcmd.encode())
                Att_read = "lol"
                while Att_read != "Done":
                    Att_read = self.Attenuator.readline().strip().decode("latin-1")
                    time.sleep(0.2)
            
            self.Plot_new_PLdynamics() #replot pl dynamics only after full power cycle
            self.meas_num.setText(f"Measurement: {x}")
            self.time_elapsed.setText(f"Time: {new_time} s")
            x += 1

        self.StartPowerBtn.setEnabled(True)
        self.print_to_message_box("Measurement completed")

############## CALCULATE FLOW RATES FOR DILUTION EXPERIMENT #########################

    @pyqtSlot()
    def on_CalcBtn_clicked(self): # Calculates flow rates and fills the table
    
        # find sensitizer and emitter pump and use parameters to calculate concentrations. fill the table with values
        sensitizer_conc = np.full(shape=self.Number_box_A.value(), fill_value=1, dtype=float)
        emitter_conc = np.full(shape=self.Number_box_B.value(), fill_value=1, dtype=float)
        Total_FR = self.total_flow_rate_box.value()

        SensitizerSelected = False
        EmitterSelected = False
        SolventSelected = False
 
        #setup sensitizer
        SensitizerSelected = True
        Volume_interval = self.volume_interval_box.value()
        sensitizer_min_flowrate = self.min_flow_rate_box_A.value()
        sensitizer_init_conc = self.init_conc_box_A.value()
        Factor_sens = Total_FR / sensitizer_min_flowrate  
        sensitizer_prep_conc = self.init_conc_box_A.value() * Factor_sens
        self.prep_conc_box_A.setValue(sensitizer_prep_conc)
        if self.Number_box_A.value() == 1: #when only one concentration is scanned
            Incr_factor_sens = 1
        else:
            Incr_factor_sens = (0.95*Factor_sens)**(1./int(-1+self.Number_box_A.value())) # calclate increase factor 
        self.Incr_factor_box_A.setValue(Incr_factor_sens)
        for i in range(self.Number_box_A.value()):
            sensitizer_conc[i] = sensitizer_init_conc * (Incr_factor_sens)**i #sensitizer concentrations
        globals.sensitizer_concentrations = sensitizer_conc

        # setup emitter
        EmitterSelected = True
        emitter_min_flowrate = self.min_flow_rate_box_B.value()
        emitter_init_conc = self.init_conc_box_B.value()
        Factor_emit = Total_FR / emitter_min_flowrate  
        emitter_prep_conc = self.init_conc_box_B.value() * Factor_emit
        self.prep_conc_box_B.setValue(emitter_prep_conc)
        if self.Number_box_B.value() == 1: #when only one concentration is scanned
            Incr_factor_emit = 1
        else:
            Incr_factor_emit = (0.95*Factor_emit)**(1./int(-1+self.Number_box_B.value())) # calclate increase factor 
        self.Incr_factor_box_B.setValue(Incr_factor_emit)
        for i in range(self.Number_box_B.value()):
            emitter_conc[i] = emitter_init_conc * (Incr_factor_emit)**i #emitter concentrations
        globals.emitter_concentrations = emitter_conc

        #setup solvent
        SolventSelected = True
        solvent_min_flowrate = int(self.min_flow_rate_box_C.value())

        #Create table and set headers for solvent
        self.concentration_table_solvent.setRowCount(len(emitter_conc))
        self.concentration_table_solvent.setColumnCount(len(sensitizer_conc))
        self.concentration_table_solvent.setHorizontalHeaderLabels(list(map("{:.3f}".format,sensitizer_conc)))
        self.concentration_table_solvent.setVerticalHeaderLabels(list(map("{:.3f}".format,emitter_conc)))
        self.concentration_table_solvent.resizeColumnsToContents()
        self.concentration_table_solvent.resizeRowsToContents()
        self.concentration_table_solvent.show()
                #Create table and set headers for sensitizer
        self.concentration_table_sensitizer.setRowCount(len(emitter_conc))
        self.concentration_table_sensitizer.setColumnCount(len(sensitizer_conc))
        self.concentration_table_sensitizer.setHorizontalHeaderLabels(list(map("{:.3f}".format,sensitizer_conc)))
        self.concentration_table_sensitizer.setVerticalHeaderLabels(list(map("{:.3f}".format,emitter_conc)))
        self.concentration_table_sensitizer.resizeColumnsToContents()
        self.concentration_table_sensitizer.resizeRowsToContents()
        self.concentration_table_sensitizer.show()
                #Create table and set headers for emitter
        self.concentration_table_emitter.setRowCount(len(emitter_conc))
        self.concentration_table_emitter.setColumnCount(len(sensitizer_conc))
        self.concentration_table_emitter.setHorizontalHeaderLabels(list(map("{:.3f}".format,sensitizer_conc)))
        self.concentration_table_emitter.setVerticalHeaderLabels(list(map("{:.3f}".format,emitter_conc)))
        self.concentration_table_emitter.resizeColumnsToContents()
        self.concentration_table_emitter.resizeRowsToContents()
        self.concentration_table_emitter.show()

        # calculate array of values for C based on max flow rate and sensitizer and emitter lists
        globals.solv_flowrates = np.full([len(emitter_conc),len(sensitizer_conc)], fill_value=Total_FR, dtype=int)
        globals.sens_flowrates = np.full([len(emitter_conc),len(sensitizer_conc)], fill_value=0, dtype=int)
        globals.emit_flowrates = np.full([len(emitter_conc),len(sensitizer_conc)], fill_value=0, dtype=int)
        Exp_time = 0
        Volume_sens = 0
        Volume_emit = 0
        Volume_solv = 0


        if sensitizer_prep_conc == 0 or emitter_prep_conc == 0:
            self.print_to_message_box("Sensitizer or emitter concnetration cannot be 0")
            return
        
        for n in range(len(globals.emitter_concentrations)):
            for m in range(len(globals.sensitizer_concentrations)):
                globals.sens_flowrates[n,m] = int(sensitizer_conc[m] / sensitizer_prep_conc  * Total_FR)
                globals.emit_flowrates[n,m] = int(emitter_conc[n] / emitter_prep_conc * Total_FR)
                globals.solv_flowrates[n,m] = int(globals.solv_flowrates[n,m] - globals.sens_flowrates[n,m] - globals.emit_flowrates[n,m])
                self.concentration_table_solvent.setItem(n,m,QTableWidgetItem(str(globals.solv_flowrates[n,m])))
                self.concentration_table_sensitizer.setItem(n,m,QTableWidgetItem(str(globals.sens_flowrates[n,m])))
                self.concentration_table_emitter.setItem(n,m,QTableWidgetItem(str(globals.emit_flowrates[n,m])))
                
                if globals.solv_flowrates[n,m] < 0:
                    globals.solv_flowrates[n,m] = 0
                    self.concentration_table_solvent.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_sensitizer.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_emitter.item(n,m).setBackground(QColor(255, 200, 0, 100))
                elif globals.sens_flowrates[n,m] < 0:
                    globals.sens_flowrates[n,m] = 0
                    self.concentration_table_solvent.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_sensitizer.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_emitter.item(n,m).setBackground(QColor(255, 200, 0, 100))
                elif globals.emit_flowrates[n,m] < 0:
                    globals.emit_flowrates[n,m] = 0
                    self.concentration_table_solvent.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_sensitizer.item(n,m).setBackground(QColor(255, 200, 0, 100))
                    self.concentration_table_emitter.item(n,m).setBackground(QColor(255, 200, 0, 100))
                # if globals.solv_flowrates[n,m] < 0 or globals.solv_flowrates[n,m] < 0.5*solvent_min_flowrate or Sensitizer_flowrates[n,m] < 0.5*sensitizer_min_flowrate or Emitter_flowrates[n,m] < 0.5*emitter_min_flowrate:
                #     self.concentration_table_solvent.item(n,m).setBackground(QColor(255, 0, 0, 100))
                else: 
                    if self.Continuous_measurement.isChecked():
                        Exp_time += Volume_interval / Total_FR
                    if self.Sequential_measurement.isChecked():
                        Exp_time += Volume_interval / Total_FR + self.PowerNumber_box.value()*3/60

                    Volume_sens += globals.sens_flowrates[n,m] * Volume_interval / Total_FR
                    Volume_emit += globals.emit_flowrates[n,m] * Volume_interval / Total_FR
                    Volume_solv += globals.solv_flowrates[n,m] * Volume_interval / Total_FR


        #estimate experiment time and volume
        Exp_time += 2*(float(self.SysVolBox.value()) / Total_FR)
        Volume_solv += 2*(float(self.SysVolBox.value()))

        self.print_to_message_box(f"Estimated experiment runtime: {int(Exp_time)} minutes, sensitizer volume: {int(Volume_sens)/1000} ml, emitter volume: {int(Volume_emit)/1000} ml, solvent volume: {int(Volume_solv)/1000} ml")

        if SensitizerSelected == True and EmitterSelected == True and SolventSelected == True:
            self.ConcentrationCalculated = True
        else:
            self.ConcentrationCalculated = False

        return

    @pyqtSlot()
    def show_help_oxy(self):
        QMessageBox.information(self, "Info", "Setup for Oxygen level experiment.\
             \nSet Integration time to 500 ms\nSet Number of averages to 5\nSet Number of measurements to 0 (infinite)\nSet the wavelengths for fluorescence measurement (645 for PtTFPP) \
             \nThe Pump chosen should be B, becuase pump D is apparently called B on the Secondary R2 series. \
             \nFor now you can change the flow rate manually by selecting the flow rate and clicking Start Flow.")
        return

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=4, height=3, dpi=100):
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
