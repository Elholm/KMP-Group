#!/usr/bin/env python3

#imports
import os
import sys
import time
import pandas as pd
import numpy as np
import rseriesopc as rs
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from ctypes import *
from math import log10 as log
import serial
import serial.tools.list_ports
import json
import requests

from lib.windows import QYEX_f2_win as form_window

import globals
from lib.avaspec import *

cwd = os.getcwd()

if os.path.isfile(cwd+"/avaspecx64.dll"):
    # print("You are in the right directory!")
    os.add_dll_directory(cwd)
    pass
else:
    print("You are not in the directory with avaspecx64.dll")
    raise FileNotFoundError

# time.sleep(1)


lib = cdll.LoadLibrary("C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLUP_64.dll")

class MainWindow(QMainWindow, form_window.Ui_MainWindow):
    newdata = pyqtSignal()
    cancel = pyqtSignal()
    start_TBC = pyqtSignal()
    cancel_qy = pyqtSignal()
    stop_disp = pyqtSignal()
    abs_spectrum = pyqtSignal()
    stop_update = pyqtSignal()
    cancelled = False
    first = True
    use_light = False
    stop_dispersion = False
    TBC_started = False
    Spectrum_figure = plt.figure(dpi = 100)


    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle("Quantum Yield EXperiment Program")
        self.setWindowIcon(QIcon('lib/sun.png'))
        self.showMaximized()
        self.IntTimeEdt.setText("{0:.3f}".format(2))
        self.NumAvgEdt.setText("{0:d}".format(4000))
        self.NumMeasEdt.setText("{0:d}".format(0))
        self.StartMeasBtn.setEnabled(False)
        self.t0 = time.time()
        OnlyInt = QIntValidator()
        OnlyInt.setRange(1, 1000)  
        self.NumAvgEdt.setValidator(OnlyInt)
        self.NumMeasEdt.setValidator(OnlyInt)
        self.newdata.connect(self.handle_newdata)
        self.cancel.connect(self.cancel_meas)
        self.cancel_qy.connect(self.set_qy_cancel)
        self.start_TBC.connect(self.set_start_TBC)
        self.stop_update.connect(self.stop_update_func)
        self.get_abs_spectrum = False
        self.actionHelpOxy.triggered.connect(self.show_help_oxy)
        self.log_name = "default_log.txt"
        self.log_path = "logs/default_log_path.txt"
        self.time_off_end = 0
        self.time_off_total = 0
        self.qy_cancelled=False
        self.LEDlist.activated.connect(self.update_power)

        self.Spectrum_figure = MplCanvas()
        self.monitorLayout.addWidget(self.Spectrum_figure)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Intensity")
        plt.tight_layout()
        plt.close()

        self.time_figure = MplCanvas()
        self.timeLayout.addWidget(self.time_figure)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Intensity")
        plt.tight_layout()
        plt.close()

        self.abs_figure = MplCanvas()
        self.absLayout.addWidget(self.abs_figure)
        plt.xlabel("Wavelength [nm]")
        plt.ylabel("Intensity")
        plt.tight_layout()
        plt.close()

        self.on_Set_wavelength_btn_clicked()

        #connect function for continuous temperature update
        self.tempCheck.toggled.connect(self.tempCheck_func)

        #load preset samples in case of crash
        if os.path.isfile(cwd+"/Valve_Presets.json"):
            with open('Valve_Presets.json', 'r') as file:
                self.Valve_Presets = json.load(file)
            for i in range(1,17):
                self.__dict__['Sample_name_' + str(i)].setText(self.Valve_Presets[i-1])


        # read com ports and connect to SF10 pump
        self.Pump = False
        self.qpod = False

        self.on_setPowerBtn_clicked()
        
        # sf10 pump auto connect
        self.on_pumpConnect_clicked()

        #knauer sampler valve auto connect
        self.on_samplerConnect_clicked()

        #qpod1 auto connect
        self.on_qpodConnect_clicked()
        
        #shelly auto connect
        self.Shelly_IP.setText('192.168.137.85')
        self.on_shellyConnect_clicked()
       
                

        

    ##############################################################################################################################

    # GENERAL UI

    def print_to_message_box(self, text):#Print time and message
            t = time.localtime()
            current_time = time.strftime("%H:%M:%S", t)
            self.logTextEdit.append(f"{current_time}  {text}")
            return
    
    def closeEvent(self, event):

        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Warning', 
                         quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    ##############################################################################################################################

    #### PART CONTAINING TEMPERATURE CONTROL

    @pyqtSlot()
    def on_qpodConnect_clicked(self):
        for pinfo in serial.tools.list_ports.comports():
            if pinfo.serial_number == 'D30ALF5KA' and pinfo.vid == 1027: #QPOD 1 is D30ALF5KA. QPOD 3 is .
                self.qpod = serial.Serial(pinfo.device,19200,timeout=3)
                cmd = str("[F1 ID ?]")
                self.qpod.write(cmd.encode())
                print("message sent")
                response = self.qpod.read_until(expected=b"]",size=20).decode("utf-8")
                print(response)
                time.sleep(0.1)
                self.qpod.write(b"[F1 CT -]")
                time.sleep(0.1)
                self.qpod.write(b"[F1 HT -]")
                self.tempOff.setEnabled(True)
                self.tempOn.setEnabled(True)
                self.qpodDisconnect.setEnabled(True)
                self.qpodConnect.setEnabled(False)
        return

    @pyqtSlot()
    def on_qpodDisconnect_clicked(self):
        try:
            self.qpod.close()
        except:
            self.print_to_message_box("qpod could not disconnect. perhaps it was not connected properly")
        self.qpodDisconnect.setEnabled(False)
        self.tempOff.setEnabled(False)
        self.tempOn.setEnabled(False)
        self.qpodConnect.setEnabled(True)
        return

    @pyqtSlot()
    def on_tempOn_clicked(self):
        if self.qpod:
            cmd = "[F1 TC +]"
            self.qpod.write(cmd.encode())
            cmd = "[F1 TC ?]"
            self.qpod.write(cmd.encode())
            response = self.qpod.read_until(expected=b"]",size=None).decode("utf-8")
            if response == "[F1 TC +]":
                self.print_to_message_box("Temperature control turned ON.")
            else:
                self.print_to_message_box("Temperature control could not be turned on. Try again.")
        else:
            self.print_to_message_box("Could not send message. Qpod not connected.")
        return

    @pyqtSlot()
    def on_tempOff_clicked(self):
        if self.qpod:
            cmd = "[F1 TC -]"
            self.qpod.write(cmd.encode())
            cmd = "[F1 TC ?]"
            self.qpod.write(cmd.encode())
            response = self.qpod.read_until(expected=b"]",size=None).decode("utf-8")
            if response == "[F1 TC -]":
                self.print_to_message_box("Temperature control turned OFF.")
            else:
                self.print_to_message_box("Temperature control could not be turned off. Try again.")
        else:
            self.print_to_message_box("Could not send message. Qpod not connected.")
        return

    @pyqtSlot()
    def on_tempSet_clicked(self):
        dlg = QDialog(self)
        dlg.resize(200,100)
        dlg.setFixedSize(200,100)
        dlg.setWindowTitle("Set target temperature: ")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Write target temperature: "))
        temp_spin = QSpinBox()
        temp_spin.setMinimum(0)
        temp_spin.setMaximum(100)
        temp_spin.setValue(25)
        temp_spin.setFocus()
        layout.addWidget(temp_spin)
        b1 = QPushButton("Set",dlg)
        b1.clicked.connect(dlg.accept)
        b2 = QPushButton("Cancel",dlg)
        b2.clicked.connect(dlg.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(b1)
        btn_layout.addWidget(b2)
        layout.addLayout(btn_layout)
        dlg.setLayout(layout)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.accepted.connect(lambda: self.set_temp(temp_spin.value()))
        dlg.open()
        temp_spin.setFocus()
        temp_spin.selectAll()

        return
        
    def set_temp(self,TT):
        if self.qpod:
            cmd = f"[F1 TT S {TT}]"
            self.qpod.write(cmd.encode())
            cmd = "[F1 TT ?]"
            self.qpod.write(cmd.encode())
            response = self.qpod.read_until(expected=b"]",size=None).decode("utf-8")
            print(response)
            expect = f"[F1 TT {TT:.2f}]"
            if response.strip() == expect:
                self.print_to_message_box(f"Target temperature set to {TT}.")
                self.temp_label.setText(f"T (Cº): {TT}")
            else:
                self.print_to_message_box("Target temperature could not be set. Try again.")
        else:
            self.print_to_message_box("Could not send message. Qpod not connected.")

        return
    
    def temp_update(self): 
        while self.update_temp == True:
                cmd = "[F1 CT ?]"
                self.qpod.write(cmd.encode())
                response = self.qpod.read_until(expected=b"]",size=None).decode("utf-8")
                print(response)
                temp = response.split(" ")[-1].replace("]","")
                self.tempCheck.setText(f"Current temp: {temp}")
                time.sleep(5)
        return

    def tempCheck_func(self): #this is connected to the toggle of the temperature update checkbox
        if self.qpod:
            if self.tempCheck.isChecked():
                self.update_temp = True
                self.thread_temp = QThread() # this created an additional computing thread for processes, so the main window doesn't freeze
                self.worker_temp = Worker() # this is a worker that will tell when the job is done
                self.worker_temp.func = self.temp_update #here the job of the worker is defined. it should only be one function
                self.worker_temp.moveToThread(self.thread_temp) #the workers job is moved from the frontend to the thread in backend
                self.thread_temp.started.connect(self.worker_temp.run) # when the thread is started, the worker runs
                self.worker_temp.finished.connect(self.thread_temp.quit) # when the worker is finished, the the thread is quit
                self.worker_temp.finished.connect(self.worker_temp.deleteLater)
                self.thread_temp.finished.connect(self.thread_temp.deleteLater)
                self.thread_temp.start() #here the thread is actually started
                print("update started")
            elif self.tempCheck.isChecked() == False:
                self.tempCheck.setText("Current temp: ??")
                self.stop_update.emit()
                print("update stopped")# end temp update
                pass
        else:
            self.print_to_message_box("Qpod not connected.  ")    
        return
    
    def stop_update_func(self):
        self.update_temp = False

    #### MULTI SAMPLE CONTROL
    #### PART CONTAINING CONTROL OF KNAUER SELECTION VALVE AND SF10 PUMP

    @pyqtSlot()
    def on_samplerConnect_clicked(self):
        for pinfo in serial.tools.list_ports.comports():
            print (pinfo.name, pinfo.serial_number, pinfo.vid)
            if pinfo.serial_number == 'KNE01QKMA' and pinfo.vid == 1027: #Knauer valve
                self.valve = serial.Serial(pinfo.device)
                serialcmd = str(f'POSITION:{5}\r')
                self.valve.write(serialcmd.encode())
                    # serialcmd = str(f'POSITION?\r')
                    # self.valve.write(serialcmd.encode())
                    # print(self.valve.readline().strip().decode("latin-1"))
                self.valve_connected = True
        return
    
    @pyqtSlot()
    def on_Valve_Select_Button_clicked(self):
        # if self.valve_position == int(self.ValveList.currentText()):
        #     return
        self.valve_position = int(self.ValveList.currentText())
        serialcmd = str(f'POSITION:{self.valve_position}\r')
        self.valve.write(serialcmd.encode())
        self.valve.read_until(expected='\r'.encode('UTF-8'))
        time.sleep(0.5)
        serialcmd = str(f'POSITION?\r')
        self.valve.write(serialcmd.encode())
        line = self.valve.read_until(expected='\r'.encode('UTF-8')).decode("latin-1")
        self.valve_position = int(line.split('POSITION:')[1].split('\r')[0])

        self.print_to_message_box(f"Valve position set to {self.valve_position}")

    @pyqtSlot()
    def on_pumpConnect_clicked(self):
        for pinfo in serial.tools.list_ports.comports():
            print (pinfo.name, pinfo.serial_number, pinfo.vid)
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
                print("Pump connected")
                self.Pump_button.setEnabled(True)
                self.Pump = True
        return

    @pyqtSlot()
    def on_Load_Button_clicked(self):
        rate = self.Pump_flowrate.value() # flow rate in ml/min
        vol = self.Load_Volume.value() #in ml
        self.print_to_message_box(f"Loading {vol} ml at {rate} ml/min, valve {self.valve_position}")
        serialcmd = str(f'MODE DOSE\r')
        self.pump_solvent.write(serialcmd.encode())
        serialcmd = str(f'SETFLOW {rate}\r')
        self.pump_solvent.write(serialcmd.encode())
        serialcmd = str(f'SETDOSE {vol}\r')
        self.pump_solvent.write(serialcmd.encode())   
        serialcmd = str(f'SETREG 3.0\r')
        self.pump_solvent.write(serialcmd.encode())   
        serialcmd = str(f'START\r')
        self.pump_solvent.write(serialcmd.encode())
        time.sleep(60*vol/rate) #in seconds
        serialcmd = str(f'STOP\r')
        self.pump_solvent.write(serialcmd.encode())  
        return
    
    @pyqtSlot()
    def on_Clean_Button_clicked(self):
        if self.Knauer:
            self.valve_position = 16
            serialcmd = str(f'POSITION:{self.valve_position}\r')
            self.valve.write(serialcmd.encode())
        if self.SF10:
            rate = 1 # flow rate in ml/min
            vol = self.Clean_Volume.value() #in ml
            self.print_to_message_box(f"Cleaning {vol} ml at {rate} ml/min, valve {self.valve_position}")
            serialcmd = str(f'MODE DOSE\r')
            self.pump_solvent.write(serialcmd.encode())
            serialcmd = str(f'SETFLOW {rate}\r')
            self.pump_solvent.write(serialcmd.encode())
            serialcmd = str(f'SETDOSE {vol}\r')
            self.pump_solvent.write(serialcmd.encode())   
            serialcmd = str(f'SETREG 3.0\r')
            self.pump_solvent.write(serialcmd.encode())   
            serialcmd = str(f'START\r')
            self.pump_solvent.write(serialcmd.encode())
            time.sleep(60*vol/rate) #in seconds
            serialcmd = str(f'STOP\r')
            self.pump_solvent.write(serialcmd.encode())
        else:
            self.print_to_message_box("No pump connected")

    @pyqtSlot()
    def on_Save_Valve_Presets_Button_clicked(self):
        for i in range(1,17):
            self.Valve_Presets[i-1] = self.__dict__['Sample_name_' + str(i)].text()
        with open('Valve_Presets.json', 'w') as file:
            json.dump(self.Valve_Presets, file)
        
    @pyqtSlot()
    def on_Clear_Valve_Presets_Button_clicked(self):
        for i in range(1,17):
            self.__dict__['Sample_name_' + str(i)].clear()


    #### SHELLY POWER PLUG CONTROL
    @pyqtSlot()
    def on_shellyConnect_clicked(self):
        # self.Shelly_on.setEnabled(True)
        url = f'http://{self.Shelly_IP.text()}/rpc/Switch.GetStatus?id=0'
        print(url)
        try:
            # Make a GET request to the Shelly device's status URL
            response = requests.get(url,timeout=3)
            # Check for successful response
            if response.status_code == 200:
                print(response.json()) # Parse the JSON response and check for output
                if response.json().get('output'):
                    self.Shelly_off.setEnabled(True)
                else:
                    self.Shelly_on.setEnabled(True)
        except Exception as e:
            print(f"An error occurred: {e}")
        return

    @pyqtSlot()
    def on_Shelly_on_clicked(self):
        try:
            response = requests.get(f'http://{self.Shelly_IP.text()}/relay/0?turn=on',timeout=2) #turn on shelly device
            if response.json().get('ison') == True:
                self.Shelly_on.setEnabled(False)
                self.Shelly_off.setEnabled(True)
                self.plugLabel.setText("Plug status: ON")
        except:
            self.print_to_message_box("Shelly smart plug disconnected. Check if mobile hotspot is on or if IP address is correct")
    
    @pyqtSlot()
    def on_Shelly_off_clicked(self,check=True):
        if check:
            off_msg = "Are you sure you want to turn off the power supply for the lamp? You will not be able to turn it back on automatically. To turn the lamp back on, you will need to manually use the switch located on the front of the DHS lamp."
            reply = QMessageBox.question(self, 'Warning', off_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        else:
            pass       
        try:
            #turn off shelly device
            response = requests.get(f'http://{self.Shelly_IP.text()}/relay/0?turn=off',timeout=2) 
            if response.json().get('ison') == False:
                self.Shelly_on.setEnabled(True)
                self.Shelly_off.setEnabled(False)
                self.plugLabel.setText("Plug status: OFF")
        except:
            self.print_to_message_box("Shelly smart plug disconnected. Check if mobile hotspot is on or if IP address is correct")


    #### PART CONTAINING PUMP CONTROL 
    @pyqtSlot()
    def on_Pump_button_clicked(self):
        rate = 1000 # flow rate in ul/min
        vol = self.Pump_vol_Box.value() #in ul
        self.print_to_message_box(f"Pushing {vol} ul at {rate} ul/min")
        serialcmd = str(f'MODE DOSE\r')
        self.pump_solvent.write(serialcmd.encode())
        serialcmd = str(f'SETFLOW {rate/1000}\r')
        self.pump_solvent.write(serialcmd.encode())
        serialcmd = str(f'SETDOSE {vol/1000}\r')
        self.pump_solvent.write(serialcmd.encode())   
        serialcmd = str(f'SETREG 3.0\r')
        self.pump_solvent.write(serialcmd.encode())   
        serialcmd = str(f'START\r')
        self.pump_solvent.write(serialcmd.encode())
        time.sleep(60*vol/rate) #in seconds
        serialcmd = str(f'STOP\r')
        self.pump_solvent.write(serialcmd.encode())  
        return       

#### PART CONTAINING LED SWITCH AUTOMATION
    @pyqtSlot()
    def update_power(self):
        time.sleep(0.1)
        try:
            upHandle = c_long(int(self.LEDlist.currentText().split(".")[0]))
            currentSetpoint = c_double(0)
            ret = lib.TLUP_getLedOutputState(upHandle)
            # print(ret)
            if ret == 1:
                lib.TLUP_getLedCurrentSetpoint(upHandle,0, byref(currentSetpoint))
                self.LEDcurrentpower.setText(f"Current power: {currentSetpoint.value}")
        except:
            self.print_to_message_box("No LED chosen.")
        return

    @pyqtSlot()
    def on_connectLED_clicked(self):
        self.print_to_message_box("Trying to connect to LEDs.")
        deviceCount = c_uint32()
        lib.TLUP_findRsrc(0,byref(deviceCount))
        if deviceCount.value > 0:
            self.print_to_message_box("Number of upSeries devices found: " + str(deviceCount.value))
        else:
            self.print_to_message_box("No upSeries devices found.")
            return
        # print()
        modelName = create_string_buffer(256)
        serialNumber = create_string_buffer(256)
        lib.TLUP_getRsrcInfo(0, 0, modelName, serialNumber, 0, 0)
        # print("Connecting to this device:")
        self.print_to_message_box(f"Model name: {modelName.value.decode()}, Serial number: {serialNumber.value.decode()}")
        # print()
        self.upNames = [0 for i in range(deviceCount.value)]
        self.upHandles = [0 for i in range(deviceCount.value)]

        for i in range(deviceCount.value):
            # print(i)
            #Initializing the first connected upSeries device.
            self.upNames[i] = create_string_buffer(256)
            lib.TLUP_getRsrcName(0, i, self.upNames[i])
            self.upHandles[i]=c_int(0)
            res=lib.TLUP_init(self.upNames[i].value, 0, 0, byref(self.upHandles[i]))
            # print(f"uphandle is: {self.upHandles[i] , self.upHandles[i].value} for {self.upNames[i].value}")
        wls = []

        for i in self.upHandles:
            currentSetpoint = c_double()
            LEDName = create_string_buffer(256)
            LEDSerialNumber = create_string_buffer(256)
            LEDCurrentLimit = c_double()
            LEDForwardVoltage = c_double()
            LEDWavelength = c_double(0)
            lib.TLUP_getLedInfo(i, LEDName, LEDSerialNumber, byref(LEDCurrentLimit),
                        byref(LEDForwardVoltage), byref(LEDWavelength))
            wls.append(f"{i.value}. {LEDWavelength.value}")
        for l in range(self.LEDlist.count()):
            self.LEDlist.removeItem(0)
        self.LEDlist.addItem("Select LED...")
        self.LEDlist.addItems([f"{x} nm" for x in wls])
        self.connectLED.setEnabled(False)
        self.disconnectLED.setEnabled(True)
        return
    
    @pyqtSlot()
    def on_disconnectLED_clicked(self):
        try:
            for handle in self.upHandles:
                lib.TLUP_close(handle)
            self.connectLED.setEnabled(True)
            self.disconnectLED.setEnabled(False)
        except:
            self.print_to_message_box("No LEDs connected.")
        return

    @pyqtSlot()
    def on_setLED_clicked(self):
        try:
            upHandle = c_long(int(self.LEDlist.currentText().split(".")[0]))

            print(lib.TLUP_setLedUseNonThorlabsLed(upHandle, 1))
            if self.current_power < 20:
                self.current_power = 20
            if self.current_power > 1200:
                self.current_power = 1200
            
            currentSetpoint = c_double(float(self.current_power*0.001)) #in mA
            lib.TLUP_setLedCurrentSetpoint(upHandle,currentSetpoint)
            time.sleep(0.5)
            print(lib.TLUP_switchLedOutput(upHandle,1))
            print("Switch LED on.")
            self.LED_stat_text.setText(f"LED status: ON @ {float(self.LEDpower.value())}")
        except:
            print("LED not available.")
        return

    @pyqtSlot()
    def on_LEDoff_clicked(self): #turns LED OFF
        try:
            upHandle = c_long(int(self.LEDlist.currentText().split(".")[0]))
            # print(lib.TLUP_setLedUseNonThorlabsLed(upHandle, 1))
            lib.TLUP_switchLedOutput(upHandle,0)
            self.LED_stat_text.setText("LED status: OFF")
            # print("Switch LED off.")
        except:
            print("You didnt choose an LED!!!")
        return

        
    #################################################################################################################

    # SPECTROMETER CONTROL BELOW

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

    @pyqtSlot() 
    def on_OpenCommBtn_clicked(self):
        try:
            ret = AVS_Init(0)    
            # QMessageBox.information(self,"Info","AVS_Init returned:  {0:d}".format(ret))
            ret = AVS_GetNrOfDevices()
            # QMessageBox.information(self,"Info","AVS_GetNrOfDevices returned:  {0:d}".format(ret))
            req = 0
            mylist = AvsIdentityType * 1
            ret = AVS_GetList(75, req, mylist)
            serienummer = str(ret[1].SerialNumber.decode("utf-8"))
            if serienummer:
                QMessageBox.information(self,"Info","Found spectrometer with Serialnumber: " + serienummer)
            else:
                self.print_to_message_box("Could not find spectrometer. Try again.")
                return
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
            
            if globals.pixels != 0:
                self.StartMeasBtn.setEnabled(False)
                self.StopMeasBtn.setEnabled(True)
                self.OpenCommBtn.setEnabled(False)
                self.CloseCommBtn.setEnabled(True)
                self.getLightBtn.setEnabled(True)
                self.loadRefBtn.setEnabled(True)
        except:
            self.print_to_message_box("No device found.")
        
        return

    @pyqtSlot()
    def on_CloseCommBtn_clicked(self):
        callbackclass.callback(self, 0, 0)
        self.StartMeasBtn.setEnabled(False)
        self.StopMeasBtn.setEnabled(False)
        self.OpenCommBtn.setEnabled(True)
        self.CloseCommBtn.setEnabled(False)
        return

        FPGAver = bytes(VERSION_LEN)
        FWver = bytes(VERSION_LEN)
        DLLver = bytes(VERSION_LEN)
        ret = AVS_GetVersionInfo(globals.dev_handle, FPGAver, FWver, DLLver)
        FPGAver = ret[0]
        FWver = ret[1]
        DLLver = ret[2]
        QMessageBox.information(self,"Info","FPGA version: {FPGA} \nFirmware version: {FW} \nDLL version: {DLL}" \
                               .format(FPGA=FPGAver.value.decode('utf-8'), 
                                       FW=FWver.value.decode('utf-8'),  
                                       DLL=DLLver.value.decode('utf-8')))
        return

    @pyqtSlot()
    def on_StartMeasBtn_clicked_old(self):
        self.StartMeasBtn.setEnabled(False)
        ret = AVS_UseHighResAdc(globals.dev_handle, True)
        self.measconfig.m_IntegrationTime = float(self.IntTimeEdt.text()) #set exposure
        self.measconfig.m_NrAverages = int(self.NumAvgEdt.text()) #set number of averages
        ret = AVS_PrepareMeasure(globals.dev_handle, self.measconfig)
        timestamp = 0
        nummeas = int(self.NumMeasEdt.text())
        self.cancelled = False

        scans = 0

        if nummeas == 0:
            nummeas=100000
        while (scans < nummeas):
            if (self.cancelled == False):

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

                    scans = scans + 1
                    self.time_spectrum = time.time()
                    self.newdata.emit()
                    time.sleep(0.3)
                    
            else:
                break
        self.StartMeasBtn.setEnabled(True)
        return

    @pyqtSlot()
    def on_StartMeasBtn_clicked(self): #activates when the button "Start Measurement" is clicked
        self.first = False ### THIS MUST BE FALSE OTHERWISE THE START MEASUREMENT BUTTON WILL OVERWRITE THE CURRENT FILE!!!
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
        self.worker.func = self.on_StartMeasBtn_clicked_old #here the job of the worker is defined. it should only be one function
        self.worker.moveToThread(self.thread) #the workers job is moved from the frontend to the thread in backend
        self.thread.started.connect(self.worker.run) # when the thread is started, the worker runs
        self.worker.finished.connect(self.thread.quit) # when the worker is finished, then the thread is quit
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start() #here the thread is actually started
        return

    @pyqtSlot()
    def on_StopMeasBtn_clicked(self):
        self.cancel.emit()
        time.sleep(1)

        return

    @pyqtSlot()
    def cancel_meas(self):
        self.cancelled = True
        return
   
    @pyqtSlot()
    def handle_newdata(self):
        # self.label_5.setText(
        #     f"Estimated time required: {(float(self.IntTimeEdt.text())*int(self.NumAvgEdt.text())*int(self.NumMeasEdt.text())*2)/1000:0.0f} seconds")
        try:
            self.time_off_total += self.time_off_end
            self.new_time =  self.time_spectrum - self.t0 - self.time_off_total
            
            self.Spectrum_figure.axes.cla()
            self.Spectrum_figure.axes.plot(globals.wavelength,globals.spectraldata)
            self.Spectrum_figure.axes.set_xlabel("Wavelength [nm]")
            self.Spectrum_figure.axes.set_ylabel("Intensity")
            self.Spectrum_figure.draw()

            self.save_data(save_pdf=True)
        except:
            print("new data was not handled")
        return

    @pyqtSlot()
    def save_data(self,save_pdf = False):
        try:
            if self.use_light == True:
                try:
                    globals.spectral_minus_light = [log(globals.light_spectrum[x] / globals.spectraldata[x]) if globals.spectraldata[x]>0 and globals.light_spectrum[x]>0 else 0.0 for x in range(globals.pixels)]
                except:
                    globals.spectral_minus_light = np.zeros(globals.pixels)
                # globals.spectral_minus_light = [log(globals.light_spectrum[x] / globals.spectraldata[x]) if globals.spectraldata[x] != 0 else 0.0 for x in range(globals.pixels)]
                
                # globals.spectral_minus_light = [0.0 - globals.spectraldata[x] + globals.light_spectrum[x] for x in range(globals.pixels)]
                if self.first:
                    with open(self.log_path,'w') as f:
                        f.write(f"Temperature: {self.Temperature_box.value()} C, Exposure time: {float(self.IntTimeEdt.text())} ms, number of averages: {int(self.NumAvgEdt.text())}, LED: {self.LEDlist.currentText()}, Power: {self.current_power} \n")
                        f.write('light '  + 'spectrum ' + ' '.join([str(globals.light_spectrum[x]) for x in range(globals.pixels)]) + '\n') #light spectrum
                        f.write('0 '  + '0 ' + ' '.join([str(globals.wavelength[x]) for x in range(globals.pixels)]) + '\n') #wavelengths
                        f.write('0 ' +str(self.LEDpower.value())+' ' + ' '.join([str(globals.spectral_minus_light[x]) for x in range(globals.pixels)]) + '\n')
                else:
                    with open(self.log_path,'a') as f:
                        f.write(str(self.new_time)+' '+ f"{self.TBC_started}"+ ' ' + ' '.join([str(globals.spectral_minus_light[x]) for x in range(globals.pixels)]) + '\n')
                if save_pdf == True:
                    self.abs_figure.axes.cla()
                    self.abs_figure.axes.plot(globals.wavelength[:2048], [globals.spectral_minus_light[x] for x in range(globals.pixels)])
                    self.abs_figure.axes.set_xlim(left=self.Min_wl_box.value(), right=self.Max_wl_box.value())
                    self.abs_figure.axes.set_xlabel("Wavelength [nm]")
                    self.abs_figure.axes.set_ylabel("Absorbance [OD]")
                    self.abs_figure.draw()

                    # plot new dynamics
                    self.Plot_new_dynamics()
            else:
                print("you didnt choose reference light spectrum")
            self.first = False
        except:
            print("data was not saved")
        return

################################################# PLOT Values real time. From TTAUC script ############################################

    @pyqtSlot()
    def on_Set_wavelength_btn_clicked(self): #set values to plot and background value to subtract
        self.wavelengths_int = [int(eval(i)) for i in self.Wavelength_line.text().split(",")]
        self.background = int(self.Background_line.text())
        return
    
    @pyqtSlot()
    def Plot_new_dynamics(self): #also removes absorption values and can be used to calculate threshold
        try:
            pddata = pd.read_csv(self.log_path, sep=' ', header=2) #2 for two lines of metadata and light spectrum in the rows
            meta = 5 #how many places reserved for metadata in the columns
            wavelengths_pd = np.array(list(pddata)[meta:])
            wavelength_axis = np.around(wavelengths_pd.astype(float),1)
            bg_index = (np.abs(wavelength_axis - self.background)).argmin() + meta
            Data_points = len(pddata.iloc[:,0])
            Dynamics = np.zeros(Data_points)
            Time = np.zeros(Data_points)
            self.time_figure.axes.clear()
            for wl in range(len(self.wavelengths_int)): # pl vs time plot
                wl_index = (np.abs(wavelength_axis - self.wavelengths_int[wl])).argmin() + meta
                for i in range(Data_points):
                    Time[i] = np.array(pddata.iloc[i,0])
                    Dynamics[i] = pddata.iloc[i,wl_index] - pddata.iloc[i,bg_index]
                Time_axis = np.around(Time.astype(float),2)
                # self.time_figure.axes.cla()
                self.time_figure.axes.plot(Time_axis,Dynamics,label=wavelength_axis[wl_index-meta])

            self.time_figure.axes.legend()
            self.time_figure.axes.set_xlabel("Time [s]")
            self.time_figure.axes.set_ylabel("Absorbance")
            self.time_figure.draw()
        except:
            print("no dynamics plotted")
            return
        return

################################################################################################################

    @pyqtSlot()
    def on_setPowerBtn_clicked(self): #sets the power that the LED will use when turned on
        try:
            self.current_power = float(self.LEDpower.value())
            self.LEDcurrentpower.setText(f"Current power: {self.current_power}")
        except:
            self.print_to_message_box("Could not set power.")
        return
    
    @pyqtSlot()
    def on_showRefBtn_clicked(self): #shows the reference spectum in the raw spectrum plot
        self.Spectrum_figure.axes.cla()
        self.Spectrum_figure.axes.plot(globals.wavelength[0:2048],globals.light_spectrum[0:2048],label="Light")
        self.Spectrum_figure.axes.set_xlabel("Wavelength [nm]")
        self.Spectrum_figure.axes.set_ylabel("Intensity")
        self.Spectrum_figure.figure.tight_layout()
        self.Spectrum_figure.draw()
        return
    
    @pyqtSlot()
    def on_saveRefBtn_clicked(self): #saves the reference spectrum
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","Text Files (*.txt)", options=options)
        if fileName:
            self.print_to_message_box(f"Saving reference spectrum to: {fileName}")
        else:
            self.print_to_message_box("No filename was selected and therefore the reference spectrum has not been saved.")
            return
        with open(fileName,"w") as f:
            f.write(' '.join([str(x) for x in globals.wavelength[0:2048]])+'\n'+' '.join(str(x) for x in globals.light_spectrum[0:2048]))

        return

    @pyqtSlot()
    def on_loadRefBtn_clicked(self): #loads a reference spectrum previously saved
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getSaveFileName()","","Text Files (*.txt)", options=options)
        
        if fileName:
            self.print_to_message_box(f"Loading reference spectrum from: {fileName}")
        else:
            self.print_to_message_box("No filename was selected and therefore the reference spectrum has not been loaded.")
            return
        try:
            pddata_ref = pd.read_csv(fileName, sep=' ', header=0)
            globals.light_spectrum = np.array(pddata_ref.iloc[0,:])
            self.use_light = True
        except:
            self.print_to_message_box("The reference spectrum could not be loaded...")
            return
        self.showRefBtn.setEnabled(True)
        self.saveRefBtn.setEnabled(True)
        self.StartMeasBtn.setEnabled(True)
        return

    @pyqtSlot()
    def on_getLightBtn_clicked(self):
        self.StartMeasBtn.setEnabled(False)
        try:
            self.on_lampOnBtn_clicked()
            time.sleep(0.5)
        except:
            print("Lamp is not connected...")
        ret = AVS_UseHighResAdc(globals.dev_handle, True)
        measconfig = MeasConfigType
        measconfig.m_StartPixel = 0
        measconfig.m_StopPixel = globals.pixels - 1
        measconfig.m_IntegrationTime = float(self.IntTimeEdt.text())
        measconfig.m_IntegrationDelay = 0
        measconfig.m_NrAverages = int(1000/float(self.IntTimeEdt.text()))
        measconfig.m_CorDynDark_m_Enable = 1  # nesting of types does NOT work!!
        measconfig.m_CorDynDark_m_ForgetPercentage = 0
        measconfig.m_Smoothing_m_SmoothPix = 0
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
        ret = AVS_PrepareMeasure(globals.dev_handle, measconfig)
        nummeas = int(self.NumMeasEdt.text())
        self.cancelled = False
        timestamp = 0
        ret = AVS_Measure(globals.dev_handle, 0, 1)
        dataready = False
        while (dataready == False):
            dataready = (AVS_PollScan(globals.dev_handle) == True)
            time.sleep(0.001)
        if dataready == True:
            ret = AVS_GetScopeData(globals.dev_handle, timestamp, globals.spectraldata )
            wl = AVS_GetLambda(globals.dev_handle, globals.wavelength)
            timestamp = ret[0]
            x = 0
            while (x < globals.pixels): # 0 through 2047
                globals.spectraldata[x] = ret[1][x]
                x += 1
        
        light = [globals.spectraldata[x] for x in range(globals.pixels)]
        globals.light_spectrum = light

        self.use_light = True
        try:
            time.sleep(0.5)
            self.on_lampOffBtn_clicked()
        except:
            print("Lamp is still not connected...")
        self.StartMeasBtn.setEnabled(True)
        self.saveRefBtn.setEnabled(True)
        self.showRefBtn.setEnabled(True)

        self.on_showRefBtn_clicked() #show ref spectrum

        return    

    @pyqtSlot()
    def on_laserOnBtn_clicked(self):
        try:
            ret = AVS_SetDigOut(globals.dev_handle, 7, 1) #OPENS CHANNEL 1 WHICH CORRESPONDS TO DO8
            self.channel1_text.setText("Laser status: On")
        except:
            self.channel1_text.setText("ERROR")
        return

    @pyqtSlot()
    def on_laserOffBtn_clicked(self):
        try:
            ret = AVS_SetDigOut(globals.dev_handle, 7, 0) #CLOSES CHANNEL 1 WHICH CORRESPONDS TO DO8
            self.channel1_text.setText("Laser status: Off")
        except:
            self.channel1_text.setText("ERROR")
        return

    @pyqtSlot()
    def on_lampOnBtn_clicked(self):
        try:
            ret = AVS_SetDigOut(globals.dev_handle, 3, 1) #OPENS CHANNEL 2 WHICH CORRESPONDS TO DO5
            self.channel2_text.setText("Lamp status: On")
            # self.print_to_message_box("Lamp shutter opened.")
        except:
            self.channel2_text.setText("ERROR")
        return

    @pyqtSlot()
    def on_lampOffBtn_clicked(self):
        try:
            ret = AVS_SetDigOut(globals.dev_handle, 3, 0) #CLOSES CHANNEL 2 WHICH CORRESPONDS TO DO5
            self.channel2_text.setText("Lamp status: Off")
            # self.print_to_message_box("Lamp shutter closed.")
        except:
            self.channel2_text.setText("ERROR")
        return

    @pyqtSlot()
    def runQY(self):
        self.startQYBtn.setEnabled(False)
        self.qyRunning.setText("Experiment running...")
        if self.NumMeasEdt.text() != "1":
            self.NumMeasEdt.setText("1")
        self.t0 = time.time()
        self.time_off_total = 0
        self.time_off_start = 0
        self.time_off_end = 0
        self.time_spectrum = 0
        meas_interval = int(self.intervalLine.text())
        TBC_interval = int(self.TBC_interval_box.value())
        blank_measurements = self.Blank_meas_num.value()
        self.qy_cancelled = False
        self.TBC_started = False
        if self.qyPointsSpinBox.value() > 0:
            num_points = self.qyPointsSpinBox.value()
        else:
            num_points = 100000
        for i in range(num_points):
            if self.qy_cancelled == True: #Cancel if Stop button was pressed
                self.qyRunning.setText("Experiment not running.")
                self.on_lampOffBtn_clicked()
                self.on_LEDoff_clicked()
                self.startQYBtn.setEnabled(True)
                self.print_to_message_box("QY experiment stopped (manual).")
                return
            
            elif self.TBC_started == True: #Begin backconversion if button was pressed
                self.time_off_start = time.time()
                self.on_lampOnBtn_clicked()
                time.sleep(0.1)
                self.on_StartMeasBtn_clicked_old(scans=1)
                time.sleep(0.2)
                self.on_lampOffBtn_clicked()
                time.sleep(0.1)
                # self.time_off_end = time.time()-self.time_off_start
                
                self.time_off_end = 0 # This has to be 0 to obtain the proper time of the back conversion. Otherwise the time to take the spectrum will be subtracted from the total back conversion time.
                try:
                    TBC_interval_new = int(self.TBC_interval_box.value())
                except:
                    TBC_interval_new = TBC_interval
                    pass
                for b in range(int(TBC_interval_new)):
                    time.sleep(1)
                    if self.qy_cancelled == True:
                        break
            
            else: #continue with isomerisation measurement
                self.time_off_start = time.time()
                time.sleep(0.1)
                self.on_lampOnBtn_clicked()
                time.sleep(0.1)
                self.on_StartMeasBtn_clicked_old(scans=1)
                time.sleep(0.1)
                self.on_lampOffBtn_clicked()
                time.sleep(0.1)
                if i > blank_measurements: #dont turn on LED for initial set of measurements
                    self.on_setLED_clicked()
                self.time_off_end = time.time()-self.time_off_start
                print(f"Time off is: {self.time_off_end}")
                try:
                    meas_interval_new = int(self.intervalLine.text())
                except:
                    meas_interval_new = meas_interval
                    pass
                lamp_warm_time = self.lampWarmSpin.value()
                if self.lampToggleCheck.isChecked():
                    self.on_Shelly_off_clicked(check=False)
                    print("Shelly off")
                for b in range(int(meas_interval_new)):
                    time.sleep(1)
                    if self.qy_cancelled == True:
                        break
                    if b == int(meas_interval_new-lamp_warm_time):
                        if self.lampToggleCheck.isChecked():
                            self.on_Shelly_on_clicked()
                            print("Shelly on")
                self.on_LEDoff_clicked()



        
        self.on_lampOffBtn_clicked()
        self.on_LEDoff_clicked()
        self.qyRunning.setText("Experiment not running.")
        self.startQYBtn.setEnabled(True)
        self.print_to_message_box("QY experiment finished succesfully.")
        return

    @pyqtSlot()
    def on_TBC_start_clicked(self):
        self.start_TBC.emit()
        self.print_to_message_box("Thermal back-conversion experiment started")
        return

    @pyqtSlot()
    def set_start_TBC(self):
        self.TBC_started = True
        return

    @pyqtSlot()
    def set_qy_cancel(self):
        self.qy_cancelled = True
        return

    @pyqtSlot()
    def on_stopQYBtn_clicked(self):
        self.cancel_qy.emit()
        self.print_to_message_box("QY experiment end requested. Shutting down.")
        return

    @pyqtSlot()
    def on_startQYBtn_clicked(self):

        #This is where you select the log file name
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            self.print_to_message_box(f"Saving to: {fileName}")
            self.log_path = fileName
        else:
            self.print_to_message_box("No filename was selected and therefore the experiment has not started")
            self.startQYBtn.setEnabled(True)
            return
        
        self.print_to_message_box("QY experiment started.")
        self.first = True
        meas_interval = self.intervalLine.text()
        self.get_abs_spectrum = True
        # self.ratio_t0 = time.time()
        self.t0 = time.time()

        try:
            if self.thread_qy.isRunning():
                print("Shutting down running thread.")
                self.thread_qy.terminate()
                time.sleep(1)
            else:
                print("No thread was running.")
        except:
            print("Didn't find thread.")
        self.thread_qy = QThread() # this created an additional computing thread for processes, so the main window doesn't freeze
        self.worker_qy = Worker() # this is a worker that will tell when the job is done
        self.worker_qy.func = self.runQY #here the job of the worker is defined. it should only be one function
        self.worker_qy.moveToThread(self.thread_qy) #the workers job is moved from the frontend to the thread in backend
        self.thread_qy.started.connect(self.worker_qy.run) # when the thread is started, the worker runs
        self.worker_qy.finished.connect(self.thread_qy.quit) # when the worker is finished, the the thread is quit
        self.worker_qy.finished.connect(self.worker_qy.deleteLater)
        self.thread_qy.finished.connect(self.thread_qy.deleteLater)
        self.thread_qy.start() #here the thread is actually started
        return

    ############################################################################################################################
    ### ALL BELOW IS VAPOURTEC
    @pyqtSlot()
    def on_OpenCommBtn_vap_clicked(self):
        if self.checkA.isChecked() == False and self.checkB.isChecked() == False and self.checkC.isChecked() == False and self.checkD.isChecked() == False:
            print("Remember to pick which pumps you want to connect to")
            return
        print("This button should connect to the Vapourtec")
        self.client = rs.RSeriesClient('opc.tcp://localhost:43344')
        self.conState = self.client.connect()
        # print(conState)
        self.rseries = self.client.getRSeries()
        self.manualControl = self.rseries.getManualControl()
        # self.reactor = self.manualControl.getR4I().getReactors()['3']
        print(f"Pumps available are {self.manualControl.getR2Secondary().getPumps()}")
        # print(f"Pump selected is {self.pump_name.currentText()}")
        if self.checkA.isChecked():
            self.pumpA = self.manualControl.getR2Primary()._getPump(f"A")
        if self.checkB.isChecked():
            self.pumpB = self.manualControl.getR2Primary()._getPump(f"B")
        if self.checkC.isChecked():
            self.pumpC = self.manualControl.getR2Secondary()._getPump(f"A")
        if self.checkD.isChecked():
            self.pumpD = self.manualControl.getR2Secondary()._getPump(f"B")
        # self.pump = self.manualControl.getR2Secondary()._getPump(f"{self.pump_name.currentText()}") # In primary, A=A and B=B but in secondary A=C and B=D.
        # self.temperature = self.reactor.getTemperature()
        if self.pumpD.getValveSRState():
            self.switchSRBtn_D.setText(f"Switch SR. Current: R")
        else:
            self.switchSRBtn_D.setText("Switch SR. Current: S")
        time.sleep(1)
        # self.pump.setValveSRState(True)
        self.StartFlowBtn_D.setEnabled(True)
        self.StopFlowBtn_D.setEnabled(True)
        self.StartFlowBtn_C.setEnabled(True)
        self.StopFlowBtn_C.setEnabled(True)
        self.CloseCommBtn_vap.setEnabled(True)
        self.switchSRBtn_D.setEnabled(True)
        self.switchSRBtn_C.setEnabled(True)
        self.getFlow.setEnabled(True)
        return

    @pyqtSlot()
    def on_CloseCommBtn_vap_clicked(self):
        print("This should close the connection to Vapourtec")
        print('stopping manual control')
        self.manualControl.stopAll()
        print('turn off pump and reactor')  
        self.pumpD.setFlowRate(0)
        # self.temperature.setTemperature(25) #This is turned off for testing
    
        if self.conState:
            self.client.disconnect()
        return

    @pyqtSlot()
    def show_help_oxy(self):
        QMessageBox.information(self, "Info", "Setup for Oxygen level experiment.\
             \nSet Integration time to 500 ms\nSet Number of averages to 5\nSet Number of measurements to 0 (infinite)\nSet the wavelengths for fluorescence measurement (645 for PtTFPP) \
             \nThe Pump chosen should be B, becuase pump D is apparently called B on the Secondary R2 series. \
             \nFor now you can change the flow rate manually by selecting the flow rate and clicking Start Flow.")
        return

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
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
    app.setApplicationName("Quantum Yield Program")
    form = MainWindow()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
