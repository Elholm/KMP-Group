#!/usr/bin/env python3

#imports
import os
# import platform
import sys
import time
from pathlib import Path

import scipy.optimize
from scipy.stats import chisquare
from sklearn.metrics import r2_score

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from ctypes import *
from math import log10 as log
from statistics import mean
import json

import matplotlib
import numpy as np
import pandas as pd
# import rseriesopc as rs
import scipy
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

matplotlib.use("Qt5Agg")
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from lib.windows import QYA_f_win as form_window
import flux_dict

# import globals
# import qy_window
from lib.avaspec import *

# from tqdm import tqdm
# print(__file__.split("\\")[-1].split(".")[0])
# head, tail = os.path.split(__file__)
# print(head, tail)

# time.sleep(2)

cwd = os.getcwd()

# if os.path.isfile(cwd+"/avaspecx64.dll"):
#     # print("You are in the right directory!")
#     os.add_dll_directory(cwd)
#     pass
# else:
#     print("You are not in the directory with avaspecx64.dll")
#     raise FileNotFoundError

# time.sleep(1)


# lib = cdll.LoadLibrary("C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLUP_64.dll")

class MainWindow(QMainWindow, form_window.Ui_MainWindow):
    params_list = ["analysisEndTime",
                   "analysisStartTime",
                   "analysisNumPoints",
                   "analysiswlLineEdit",
                   "manCorr",
                   "zeroLineEdit",
                   "abswlLineEdit",
                   "fluxLineEdit",
                   "fluxwlLineEdit",
                   "concLineEdit",
                   "extincLineEdit",
                   "extincwlLineEdit",
                   "pathLength",
                   "qyLineEdit",
                   "volLineEdit",
                   "kLine",
                   "simTimeLineEdit"
                   ]
    qya_params = []
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle("Quantum Yield Analysis Program")
        self.setWindowIcon(QIcon('lib/sun.png'))
#       self.OpenCommBtn.clicked.connect(self.on_OpenCommBtn_clicked)
#       do not use explicit connect together with the on_ notation, or you will get
#       two signals instead of one!
        self.fit_fig = MplCanvas()
        toolbar = NavigationToolbar(self.fit_fig, self)
        self.fitFigLayout.addWidget(self.fit_fig)
        self.fitFigLayout.addWidget(toolbar)
        self.spec_fig = MplCanvas()
        toolbar = NavigationToolbar(self.spec_fig, self)
        self.specFigLayout.addWidget(self.spec_fig)
        self.specFigLayout.addWidget(toolbar)
        self.res_fig = MplCanvas()
        toolbar = NavigationToolbar(self.res_fig, self)
        self.resFigLayout.addWidget(self.res_fig)
        self.resFigLayout.addWidget(toolbar)
        self.flux_dict = flux_dict.all_flux
        
        if os.path.isfile("lib/qya_params.json"):
            with open('lib/qya_params.json', 'r') as file:
                self.qya_params = json.load(file)
            for i in range(len(self.params_list)):
                if self.__dict__[f"{self.params_list[i]}"].__class__.__name__ == "QLineEdit":
                    self.__dict__[f"{self.params_list[i]}"].setText(self.qya_params[i])
                if self.__dict__[f"{self.params_list[i]}"].__class__.__name__ == "QSpinBox":
                    self.__dict__[f"{self.params_list[i]}"].setValue(int(self.qya_params[i]))
        else:
            print("No init params were found.")

    def closeEvent(self, event):

        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Warning', 
                         quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    ##############################################################################################################################
    # GENERAL UI

    @pyqtSlot()
    def on_saveParams_clicked(self):
        self.qya_params=[]
        for i in range(len(self.params_list)):
            if self.__dict__[f"{self.params_list[i]}"].__class__.__name__ == "QLineEdit":
                self.qya_params.append(self.__dict__[f"{self.params_list[i]}"].text())
            if self.__dict__[f"{self.params_list[i]}"].__class__.__name__ == "QSpinBox":
                self.qya_params.append(str(self.__dict__[f"{self.params_list[i]}"].value()))
        with open('lib/qya_params.json', 'w') as file:
            json.dump(self.qya_params, file)
            
        return


     #Print time and message
    
    def print_to_message_box(self, text):
            t = time.localtime()
            current_time = time.strftime("%H:%M:%S", t)
            self.logTextEdit.appendPlainText(f"{current_time}  {text}")
            return

    @pyqtSlot()
    def on_runCalcBtn_clicked(self):
        ### Get calculation parameters from the fields and check if they are viable
        self.check_file()
        if self.good_file == False:
            self.print_to_message_box("Analysis cancelled due to file.")
            return

        self.check_params()
        params = self.get_params()
        print(params)
        ### Run QY calculation
        qys = self.run_QY_calc(params)
        if self.fluxRadio.isChecked():
            self.print_to_message_box(f"Quantum yield at {params.fluxwl} nm: {100*qys[0]:.3f} %")
            self.print_to_message_box(f"The error of the fit is: {np.sqrt(np.diag(self.pcov)).real*100} %")    
        if self.qyRadio.isChecked():
            self.print_to_message_box(f"Photon flux at {params.fluxwl} nm: {qys[0]:.3e}")
            self.print_to_message_box(f"The error of the fit is: {np.sqrt(np.diag(self.pcov)).real*100} %")
        return qys
    
    @pyqtSlot()
    def on_runSimBtn_clicked(self):
        # Make the simulation prediction and show the plots.

        return
    
    def check_file(self):
        self.good_file = True
        try:
            check = pd.read_csv(self.fileName, sep=' ', header = None,skiprows=2)
            
        except:
            print("File could not be read.")
            self.good_file = False
            return
        if np.min(check.iloc[1,1:]) < 0:
            qm = QMessageBox
            response = qm.question(self,'', "Some values in the spectrum are below 0. Do you want to continue?", qm.Yes | qm.No)
            if response == qm.Yes:
                self.good_file = True
            elif response == qm.No:
                self.good_file = False
        return

    def check_params(self):
        self.good_params = True
        
        if self.good_params == True:
            # self.print_to_message_box("Parameters are looking good. Proceeding calculation.")
            pass
        return
    
    @pyqtSlot()
    def on_loadLEDBtn_clicked(self):
        try:
            dlg = QDialog(self)
            dlg.resize(250,300)
            dlg.setFixedSize(250,300)
            dlg.setWindowTitle("Load LED data:")
            layout = QVBoxLayout()
            cb1 = QComboBox()
            cb1.addItems(["280","308","340","365","405","430","455"])
            cb1.setCurrentIndex(1)
            cb2 = QComboBox()
            cb2.addItems([f"{x}" for x in range(100,1201,100)])
            cb2.setCurrentIndex(1)
            cb3 = QComboBox()
            cb3.addItems(["Standard 10 mm", "No cuvette", "Standard MeCN", "80 ul flowcell", "80 ul new","80ul pm","80ul pm 13nov","toluene 14nov","mecn 14nov","water14nov"])
            layout.addWidget(QLabel("Choose wavelength:"))
            layout.addWidget(cb1)
            layout.addWidget(QLabel("Choose power:"))
            layout.addWidget(cb2)
            layout.addWidget(QLabel("Choose Cuvette:"))
            layout.addWidget(cb3)
            b3 = QPushButton("Preview photon flux")
            layout.addWidget(b3)
            preview = QLabel("Preview: N/A")
            layout.addWidget(preview)
            # preview_text = self.get_flux_from_params(cb1.currentText(),cb2.currentText(),cb3.currentText)
            preview_text = f"Preview: {self.flux_dict[0]['308']['100']}"
            # preview_text = f"Preview: {self.flux_dict['um45mm3'][{str(cb1.currentText())}][str(cb2.currentText())]}"
            b3.clicked.connect(lambda: preview.setText(str(self.flux_dict[cb3.currentIndex()][cb1.currentText()][cb2.currentText()])))
            b1 = QPushButton("Load",dlg)
            b1.clicked.connect(dlg.accept)
            b2 = QPushButton("Cancel",dlg)
            b2.clicked.connect(dlg.reject)
            btn_layout = QHBoxLayout()
            btn_layout.addWidget(b1)
            btn_layout.addWidget(b2)
            layout.addLayout(btn_layout)
            dlg.setLayout(layout)
            dlg.setWindowTitle("Load photon flux")
            dlg.setWindowModality(Qt.ApplicationModal)
            path_lengths = [1,1,1,1,1,1,1,1,1,1,1]
            dlg.accepted.connect(lambda: self.set_flux(f"{float(self.flux_dict[cb3.currentIndex()][cb1.currentText()][cb2.currentText()]):.3e}",cb1.currentText(),pathlength=path_lengths[cb3.currentIndex()]))
            dlg.exec_()  
        except:
            self.print_to_message_box("Something went wrong with loading the photon flux.")
        return
    
    def set_flux(self,flux,wl,v = None,pathlength = None):
        self.fluxLineEdit.setText(str(flux))
        self.fluxwlLineEdit.setText(str(wl))
        self.abswlLineEdit.setText(str(wl))
        if v == None:
            pass
        else:
            self.volLineEdit.setText(v)
        if pathlength == None:
            pass
        else:
            self.pathLength.setText(str(pathlength))
        return

    def get_params(self):
        params = pd.Series(dtype=object)
        params.qy = float(self.qyLineEdit.text())
        params.extinc = float(self.extincLineEdit.text())
        params.extincwl = float(self.extincwlLineEdit.text())
        params.conc = float(self.concLineEdit.text())
        params.flux = float(self.fluxLineEdit.text())
        params.fluxwl = float(self.fluxwlLineEdit.text())
        params.analysiswl = float(self.analysiswlLineEdit.text())
        params.abswl = float(self.abswlLineEdit.text())
        params.volume = float(self.volLineEdit.text())
        params.zeropoint = float(self.zeroLineEdit.text())
        return params
    
    def run_QY_calc(self,params):
        try:
            calc = QY_analysis()
            if self.qyRadio.isChecked():
                calc.qy = params.qy
            else:
                calc.qy = None
            if self.extincRadio.isChecked():
                calc.extinc = params.extinc
                calc.extincwl = params.extincwl
            if self.concRadio.isChecked():
                calc.start_conc = params.conc
            if self.fluxRadio.isChecked():
                calc.flux = params.flux
            else:
                calc.flux = None
            calc.file_name = self.fileName
            calc.plot = False
            calc.zero_wl = params.zeropoint
            calc.V = params.volume
            calc.LED_current = 300
            calc.LED_wl = params.abswl
            calc.qy_wl = params.analysiswl
            calc.num_points = self.analysisNumPoints.value()
            calc.start_point = int(self.analysisStartTime.value())
            calc.end_point = int(self.analysisEndTime.value())
            calc.path_length = float(self.pathLength.text())
            if self.extincRadio.isChecked():
                qys,t_list = calc.calculate_QY(calc_conc = True)
            else:
                qys,t_list = calc.calculate_QY()
            self.pcov = calc.pcov
            if self.qyRadio.isChecked():
                y_list = calc.nbd_conc_imag(t_list,calc.qy,qys[0],calc.c_1.real,calc.c_1.imag)
                self.Plot_new_spectrum([t_list,calc.data_wl],[y_list,calc.data_i],self.fit_fig,double=True,label1="Fit",label2="Data")
                # self.Plot_new_spectrum([t_list,calc.data_wl],[calc.nbd_conc_imag(t_list,calc.qy,qys[0],calc.c_1.real,calc.c_1.imag),calc.data_i],self.fit_fig,double=True)
            elif self.fluxRadio.isChecked():
                y_list = calc.nbd_conc_imag(t_list,qys[0],calc.flux,calc.c_1.real,calc.c_1.imag)
                self.Plot_new_spectrum([t_list,calc.data_wl],[y_list,calc.data_i],self.fit_fig,double=True,label1="Fit",label2="Data")
                # self.Plot_new_spectrum([t_list,calc.data_wl],[calc.nbd_conc_imag(t_list,qys[0],calc.flux,calc.c_1.real,calc.c_1.imag),calc.data_i],self.fit_fig,double=True)
            # self.print_to_message_box([calc.data_wl.to_list(),calc.data_i])
            for i in range(len(calc.first_abs)):
                if i == 0:
                    self.Plot_new_spectrum(calc.first_wl,calc.first_abs[i],self.spec_fig,start_x=150,end_x=600,clear=True,typ="spec")
                else:
                    self.Plot_new_spectrum(calc.first_wl,calc.first_abs[i],self.spec_fig,start_x=150,end_x=600,clear=False,typ="spec")
            self.x_list = calc.data_wl.to_list()
            self.y_list = calc.data_i

            if self.prodAbsCheck.isChecked():
                qy_prod_guess = 0.5
                eps_prod = float(self.epsProdLine.text())
                up_scale = 1.02
                down_scale = 0.98
                if self.qyRadio.isChecked():
                    y,x,z = self.prod_abs_correction(calc.qy,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_prod = eps_prod, qy_prod = qy_prod_guess,b_ex = calc.b_ex)
                    init_qy = calc.qy
                if self.fluxRadio.isChecked():
                    y,x,z = self.prod_abs_correction(qys[0],calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = qy_prod_guess,b_ex = calc.b_ex)
                    init_qy = qys[0]
                # self.Plot_new_spectrum(self.x_list,z,self.fit_fig,clear=False,label1="Fit with prod absorption")
                # print(calc.data_i)
                loose_conv = False
                tight_conv = False
                opt_threshold = 1e-3
                qy_grad_up = 1
                qy_grad_prod_up = 1
                qy_grad_down = 1
                qy_grad_prod_down = 1
                current_qy = init_qy
                current_qy_prod = qy_prod_guess
                for attempt in range(100):
                    if len(z) == len(calc.data_i):
                        corr_matrix = np.corrcoef(calc.data_i,z)
                        corr = corr_matrix[0,1]
                        loose_r2 = corr**2
                        tight_r2 = r2_score(calc.data_i,z)
                        if self.qyRadio.isChecked():
                            y_up,x_up,z_up = self.prod_abs_correction(calc.qy*up_scale,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_prod = eps_prod, qy_prod = current_qy_prod,b_ex = calc.b_ex)
                            y_down,x_down,z_down = self.prod_abs_correction(calc.qy*down_scale,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_prod = eps_prod, qy_prod = current_qy_prod,b_ex = calc.b_ex)
                            y_up,x_up,z_up_prod = self.prod_abs_correction(calc.qy,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_prod = eps_prod, qy_prod = current_qy_prod*up_scale,b_ex = calc.b_ex)
                            y_down,x_down,z_down_prod = self.prod_abs_correction(calc.qy,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_prod = eps_prod, qy_prod = current_qy_prod*down_scale,b_ex = calc.b_ex)
                        if self.fluxRadio.isChecked():
                            y_up,x_up,z_up = self.prod_abs_correction(current_qy*up_scale,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = current_qy_prod,b_ex = calc.b_ex)
                            y_down,x_down,z_down = self.prod_abs_correction(current_qy*down_scale,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = current_qy_prod,b_ex = calc.b_ex)
                            y_up,x_up,z_up_prod = self.prod_abs_correction(current_qy,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = current_qy_prod*up_scale,b_ex = calc.b_ex)
                            y_down,x_down,z_down_prod = self.prod_abs_correction(current_qy,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = current_qy_prod*down_scale,b_ex = calc.b_ex)
                        
                        if loose_r2 > 0.99500:
                            loose_conv = True
                            loose_qy = current_qy
                            loose_qy_prod = current_qy_prod
                        if tight_r2 > 0.99500:
                            tight_conv = True
                            tight_qy = current_qy
                            tight_qy_prod = current_qy_prod
                        if tight_r2 > 0.9990:
                            tight_qy = current_qy
                            tight_qy_prod = current_qy_prod
                            break
                        else:
                            tight_conv = False
                        if abs(min([qy_grad_up,qy_grad_down])) < opt_threshold:
                            qy_opt_complete = True
                            opt_qy = current_qy
                        else:
                            qy_opt_complete = False
                        if abs(min([qy_grad_prod_up,qy_grad_prod_down])) < opt_threshold:
                            
                            qy_prod_opt_complete = True
                            # opt_k = current_k
                        else:
                            qy_prod_opt_complete = False
                        if tight_conv == False or qy_prod_opt_complete == False or qy_opt_complete == False:
                            ###GET GRADIENTS FOR EACH QY
                            # qy_grad =      ((r2_score(calc.data_i,z_up))-     (r2_score(calc.data_i,z_down))) /      (current_qy*up_scale-     current_qy*down_scale)
                            # qy_grad_prod = ((r2_score(calc.data_i,z_up_prod))-(r2_score(calc.data_i,z_down_prod))) / (current_qy_prod*up_scale-current_qy_prod*down_scale)

                            qy_grad_up =        (np.sum(np.square(np.subtract(calc.data_i,z_up)))       - np.sum(np.square(np.subtract(calc.data_i,z)))) / (current_qy*up_scale       -current_qy)
                            qy_grad_down =      -(np.sum(np.square(np.subtract(calc.data_i,z_down)))     - np.sum(np.square(np.subtract(calc.data_i,z)))) / (current_qy*down_scale     -current_qy)
                            qy_grad_prod_up =   (np.sum(np.square(np.subtract(calc.data_i,z_up_prod)))  - np.sum(np.square(np.subtract(calc.data_i,z)))) / (current_qy_prod*up_scale  -current_qy_prod)
                            qy_grad_prod_down = -(np.sum(np.square(np.subtract(calc.data_i,z_down_prod)))- np.sum(np.square(np.subtract(calc.data_i,z)))) / (current_qy_prod*down_scale-current_qy_prod)

                            print(f"{attempt} grad1: {min([qy_grad_up,qy_grad_down]):.5f}   !  qy1: {current_qy:.5f} ! grad2: {min([qy_grad_prod_up,qy_grad_prod_down]):.5f}  ! qy2: {current_qy_prod:.5f} ! tight r2 value is: {tight_r2:.5f}")
                            if attempt > 100:
                                factor = attempt/100
                            else:
                                factor = 1
                            if qy_grad_up <= qy_grad_down:
                                current_qy = current_qy*up_scale
                            else:
                                current_qy = current_qy*down_scale
                            if qy_grad_prod_up <= qy_grad_prod_down:
                                current_qy_prod = current_qy_prod*up_scale
                            else:
                                current_qy_prod = current_qy_prod*down_scale
                            

                            # new_qy = current_qy * (1+qy_grad/factor)
                            # if new_qy > current_qy * up_scale:
                            #     current_qy = current_qy * up_scale
                            # elif new_qy < current_qy * down_scale:
                            #     current_qy = current_qy * down_scale
                            # else:
                            #     current_qy = new_qy

                            # new_qy_prod = current_qy_prod * (1+qy_grad_prod/factor)
                            # if new_qy_prod > current_qy_prod * up_scale:
                            #     current_qy_prod = current_qy_prod * up_scale
                            # elif new_qy_prod < current_qy_prod * down_scale:
                            #     current_qy_prod = current_qy_prod * down_scale
                            # else:
                            #     current_qy_prod = new_qy_prod
                            # current_qy = current_qy * (1+qy_grad/factor)
                            # current_qy_prod = current_qy_prod * (1+qy_grad_prod/factor)
                            
                            y,x,z = self.prod_abs_correction(current_qy,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_prod = eps_prod,qy_prod = current_qy_prod,b_ex = calc.b_ex)
                        else:
                            print("Converged.")
                            break
                    else:
                        print(len(z),len(calc.data_i))
                        print("failed")
                self.Plot_new_spectrum(self.x_list,z,self.fit_fig,clear=False,label1="Fit with prod absorption optimized")
                self.Plot_new_spectrum(self.x_list,np.array(calc.data_i)-np.array(z),self.res_fig,clear = True,label1="Residuals")
                if loose_conv:
                    self.print_to_message_box(f"Loose convergence was obtained with quantum yields: {100*loose_qy:.2f} % and {100*loose_qy_prod:.2f} %")
                if tight_conv:
                    self.print_to_message_box(f"Tight convergence was obtained with quantum yields: {100*tight_qy:.2f} % and {100*tight_qy_prod:.2f} %")
                else:
                    self.print_to_message_box(f"Optimisation did not converge. Last result was: {100*current_qy:.2f} % and {100*current_qy_prod:.2f} % ")
                    self.print_to_message_box(f"b was {calc.b}")
            else:
                pass

            if self.kCheck.isChecked() and not self.prodAbsCheck.isChecked():  ## Function for fitting with thermal conversion rate
                k = float(self.kLine.text())
                up_scale = 1.02
                down_scale = 0.98
                if self.qyRadio.isChecked():
                    y,x,z = self.after_correction(calc.qy,k,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl)
                elif self.fluxRadio.isChecked():
                    y,x,z = self.after_correction(qys[0],k,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl)
                qy_grad = 1
                k_grad = 1
                opt_threshold = 2e-2
                loose_conv = False
                tight_conv = False
                qy_opt_complete = False
                k_opt_complete = False
                init_qy = qys[0]
                current_qy = init_qy
                current_k = k
                for attempt in range(100):
                    if len(z)==len(calc.data_i):
                        corr_matrix = np.corrcoef(calc.data_i, z)
                        corr = corr_matrix[0,1]
                        loose_r2 = corr**2
                        tight_r2 = r2_score(calc.data_i,z)
                        if self.qyRadio.isChecked():
                            y_up,x_up,z_up = self.after_correction(calc.qy*up_scale,k,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_ex =calc.b_ex)
                            y_down,x_down,z_down = self.after_correction(calc.qy*down_scale,k,calc.start_conc,calc.b,calc.V,calc.N_A,qys[0],calc.data_wl,b_ex =calc.b_ex)
                            
                        if self.fluxRadio.isChecked():
                            y_up,x_up,z_up = self.after_correction(current_qy*up_scale,current_k,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_ex =calc.b_ex)
                            y_down,x_down,z_down = self.after_correction(current_qy*down_scale,current_k,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_ex =calc.b_ex)
                            y_up,x_up,k_up = self.after_correction(current_qy,current_k*up_scale,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_ex =calc.b_ex)
                            y_down,x_down,k_down = self.after_correction(current_qy,current_k*down_scale,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_ex =calc.b_ex)
                        # print(f"tight r2 value is: {tight_r2:.5f}")
                        
                        if loose_r2 > 0.995000:
                            loose_conv = True
                            loose_qy = current_qy
                            loose_k = current_k
                        if tight_r2 > 0.995000:
                            tight_conv = True
                            tight_qy = current_qy
                            tight_k = current_k
                        if tight_r2 > 0.9999:
                            tight_qy = current_qy
                            break
                        else:
                            tight_conc = False
                        if abs(qy_grad) < opt_threshold:
                            qy_opt_complete = True
                            opt_qy = current_qy
                        else:
                            qy_opt_complete = False
                        if abs(k_grad) < opt_threshold:
                            k_opt_complete = True
                            opt_k = current_k
                        else:
                            k_opt_complete = False
                        if qy_opt_complete == False or k_opt_complete == False or tight_conv == False:  
                            qy_grad =      -(np.sum(np.square(np.subtract(calc.data_i,z_up)))      - np.sum(np.square(np.subtract(calc.data_i,z_down))))      / (current_qy*up_scale     -current_qy*down_scale)
                            if k != 0:
                                k_grad =       -(np.sum(np.square(np.subtract(calc.data_i,k_up)))      - np.sum(np.square(np.subtract(calc.data_i,k_down))))      / (current_k*up_scale     -current_k*down_scale)
                            else:
                                k_grad = 0
                            print(f"{attempt}: qy_grad: {qy_grad:.6f} !   qy: {current_qy:.5f} !      k_grad: {k_grad:.6f} !    k: {current_k:.5e} ! r2_squared is {tight_r2}")
                            factor = 1
                            if attempt > 50:
                                factor = attempt/50
                            new_qy = current_qy * (1+qy_grad/factor)
                            if new_qy > current_qy * up_scale:
                                current_qy = current_qy * up_scale
                            elif new_qy < current_qy * down_scale:
                                current_qy = current_qy * down_scale
                            else:
                                current_qy = new_qy
                            new_k = current_k * (1+k_grad/factor)
                            if new_k > current_k * up_scale:
                                current_k = current_k * up_scale
                            elif new_k < current_k * down_scale:
                                current_k = current_k * down_scale
                            else:
                                current_k = new_k
                            # current_k = k ## This causes the optimisation to only use the fixed value of k and not update it.
                            y,x,z = self.after_correction(current_qy,current_k,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl,b_ex =calc.b_ex)
                        else:
                            print(f"opt finished at step{attempt}")
                            break

                        """
                        if loose_r2 > 0.99000:
                            loose_conv = True
                            loose_qy = current_qy
                        if tight_r2 > 0.99000:
                            tight_conv = True
                            tight_qy = current_qy
                            break
                        if tight_conv == False:
                            #Correct the qy for a better fit
                            factor = 2
                            corr_value = ((mean(z)/mean(calc.data_i)))
                            if corr_value < 1:
                                corr_corr = 1-factor*(1-corr_value)/(attempt+1)
                            elif corr_value >= 1:
                                corr_corr = 1+factor*(corr_value-1)/(attempt+1)
                            print(f"corr_value is {corr_value}")
                            current_qy = current_qy*corr_value*corr_corr
                            y,x,z = self.after_correction(current_qy,k,calc.start_conc,calc.b,calc.V,calc.N_A,calc.flux,calc.data_wl)
                        """
                    else:
                        print("Error...")
                        print(len(z))
                        print(len(calc.data_i))
                        break
                    
                self.print_to_message_box(f"Optimized qy is: {current_qy*100:.4f} %")
                self.print_to_message_box(f"Optimized k value is: {current_k:.5f} 1/s")
                # if tight_qy:
                #     self.print_to_message_box(f"Tight QY is {tight_qy*100:.3f} %")
                if self.fluxRadio.isChecked():
                    self.Plot_new_spectrum(x,np.array(y)*calc.b,self.fit_fig,clear=False,label1="Corrected qy fit")
            else:
                pass
            if not self.kCheck.isChecked() and not self.prodAbsCheck.isChecked():
                #DO SIMPLE FUNCTION OPTIMISATION...
                
                pass
            # self.Plot_new_spectrum(calc.data_wl,np.array(calc.data_i)-calc.nbd_conc_imag(calc.data_wl,qys[0],calc.qy,calc.c_1.real,calc.c_1.imag),self.fit_fig,clear=False)
            # print([x.real for x in np.array(calc.data_i)-calc.nbd_conc_imag(calc.data_wl,qys[0],calc.qy,calc.c_1.real,calc.c_1.imag)])
            # p,cov = scipy.optimize.curve_fit(lambda: calc.nbd_conc_imag(x,calc.qy,qys[0],calc.c_1.real,calc.c_1.imag)-k*(calc.start_conc-calc.nbd_conc_imag(x,calc.qy,qys[0],calc.c_1.real,calc.c_1.imag)),t_list,y_list,)
        except:
            self.print_to_message_box("Calculation failed. Check your parameters.")
            return [1,1]
        return qys

    def led_intgrl_correction(self):

        return

    def prod_abs_correction(self,qy,start_conc,b,V,N_A,I,t_list,b_prod=0,qy_prod=0,k=0,b_ex = 1):
        # b = float(self.epsReacLine.text())
        b_analysis_reac = float(self.epsReacAnal.text())
        b_analysis_prod = float(self.epsProdAnal.text())
        
        last_time = t_list.to_list()[-1]
        time_step = 1
        time_range = np.linspace(0,last_time,int(last_time/time_step))
        c = start_conc
        c_list = [c]
        c_list_final = []
        c_list_final_prod  = []
        c_prod_list = [0]
        if self.kCheck.isChecked():
            k = float(self.kLine.text())
        else:
            k = 0
        
        for y in range(len(time_range)):
            b_trans = b_ex
            c_trans = c_list[-1]
            b_cis = b_prod
            c_cis = c-c_list[-1]
            q_0 = I
            # q_trans = (c_trans * b_trans)/(c_trans * b_trans + c_cis * b_cis) * q_0 * (1-10**(-c_trans * b_trans + c_cis * b_cis))
            # q_cis = (c_cis * b_cis)/(c_trans * b_trans + c_cis * b_cis) * q_0 * (1-10**(-c_trans * b_trans + c_cis * b_cis))
        
            c_grad = (((1/V)*(q_0/N_A)*((1-10**(-(c_trans*b_trans+c_cis*b_cis)))/(c_trans*b_trans+c_cis*b_cis)))*(qy_prod*c_cis*b_cis-qy*c_trans*b_trans)+k*c_cis)*time_step
            # c_grad = (-qy*I*(1-10**(-b*c_list[-1]))/(V*N_A) + (qy_prod*I*(1-10**(-b*(c-c_list[-1])))/(V*N_A)) + k*(c_list[0]-c_list[-1]))*time_step      #k*(c_list[0]-c_list[-1]))*time_step
            c_list.append(c_list[-1]+c_grad)
            c_prod_list.append(c_prod_list[-1]-c_grad)
            
            # if y%10 == 0:
            #     c_list_final.append(c_list[-1])
        # print(c_trans,b_trans,c_cis,b_cis)
        if abs(c_list[-1]+c_prod_list[-1]-c) > 1e-7:
            print(f"Difference in conc is {c-(c_list[-1]+c_prod_list[-1]):.2e}")
        c_list.pop(-1)
        c_prod_list.pop(-1)
        for i in t_list:
            c_list_final.append(c_list[np.argmin([abs(o-i) for o in time_range])])
            c_list_final_prod.append(c_prod_list[np.argmin([abs(o-i) for o in time_range])])

        
        
        return c_list,time_range,np.add(np.array(c_list_final)*b,np.array(c_list_final_prod)*b_analysis_prod)

    def after_correction(self,qy,k,start_conc,b,V,N_A,I,t_list,b_ex = 1):
        last_time = t_list.to_list()[-1]
        time_step = 0.2
        time_range = np.linspace(0,last_time,int(last_time/time_step))
        # time_seconds = int(self.simTimeLineEdit.text())
        
        # time_steps = int(time_seconds/time_step)
        # time_range = [x*time_step for x in range(time_steps)]
        c = start_conc
        c_list = [c]
        c_list_final = []
        for y in range(len(time_range)):
            c_grad = (-qy*I*(1-10**(-b_ex*c_list[-1]))/(V*N_A) + k*(c-c_list[-1]))*time_step
            c_list.append(c_list[-1]+c_grad)
            # if y%10 == 0:
            #     c_list_final.append(c_list[-1])
        c_list.pop(-1)
        for i in t_list:
            c_list_final.append(c_list[np.argmin([abs(o-i) for o in time_range])])
        
        return c_list,time_range,np.array(c_list_final)*b
    
    def Plot_new_spectrum_old(self, x,y,func, draw = True,start_x = 0,end_x = -1):
        func.axes.clear()
        if len(x)>1:
            func.axes.plot(x[0], y[0],label = "Fit")
            func.axes.plot(x[1], y[1],label = "Data")
        else:
            func.axes.plot(x, y,label = "Fit")

        func.axes.set_xlabel("Irradiation time (s)")
        func.axes.set_ylabel(f"Absorption  @ {self.analysiswlLineEdit.text()} nm")
        func.axes.legend()
        # self.fit_fig.axes.tight_layout()
        if draw == True:
            func.draw()
        else:
            pass
    
    def Plot_new_spectrum(self, x,y,func, draw = True,start_x = 0,end_x = -1,dots = False,double=False,clear=True,label1="Data",label2="Fit",typ="default"):
        if clear:
            func.axes.clear()
        else:
            pass
        if typ == "spec":
            func.axes.plot(x[start_x:end_x], y[start_x:end_x],label = label1,color="black",linewidth=1)
            func.axes.set_xlabel("Wavelength (nm)")
            func.axes.set_ylabel(f"Absorbance")
            func.draw()
            return
        if double:
            print("All instances were lists")
            
            if dots:
                func.axes.plot(x[1], y[1],label = label2)
                func.axes.scatter(x[0], y[0], label = label1)
            else:
                # func.axes.plot(x[0][start_x:end_x], y[0][start_x:end_x],label = label1)
                func.axes.plot(x[0], y[0],label = label1,color="red")
                func.axes.scatter(x[1], y[1],label = label2,color="black",marker="x")
            
        else:
            # func.axes.plot(x[start_x:end_x], y[start_x:end_x],label = "Data")
            if dots == True:
                func.axes.plot(x, y,label = label1)
                func.axes.scatter(x, y)
            else:
                func.axes.plot(x[start_x:end_x], y[start_x:end_x],label = label1)

        func.axes.set_xlabel("Irradiation time (s)")
        func.axes.set_ylabel(f"Absorption  @ {self.analysiswlLineEdit.text()} nm")
        func.axes.legend()
        
        # self.fit_fig.axes.tight_layout()
        if draw == True:
            func.draw()
        else:
            pass

    @pyqtSlot()
    def on_getFileBtn_clicked(self):
        self.fileName = self.openFileNameDialog("Choose file containing UV-VIS data from the QY experiment...")
        self.chosenLabel.setText("File chosen: "+ self.fileName.split("/")[-1])
        self.chosenLabel.setToolTip("File chosen: "+ self.fileName)
        self.chosenLabel.setToolTipDuration(30000)
        return 

    def openFileNameDialog(self,windowTitle):
        
        
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,windowTitle, "","All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            print(fileName)
        return fileName
    
    @pyqtSlot()
    def on_runSimBtn_clicked(self):
        ### RUN LINEAR PART FIRST?
        # conc = start_conc - (qy*I*t)/(V*N_A)
        ### THIS IS NON LINEAR PART
        sim = QY_analysis()
        self.sim_time = int(self.simTimeLineEdit.text())
        t_list = np.arange(0,self.sim_time*2)*0.5
        self.b = float(self.extincLineEdit.text())
        sim.b = self.b
        sim.b_ex = self.b
        sim.num_points = self.analysisNumPoints.value()
        s = float(self.concLineEdit.text())
        n=1
        print(self.b*s)
        self.c_1 = (np.log(1 - (np.power(10,(self.b * s)) + 0j )) + 2j * np.pi * n)/(self.b * np.log(10))
        flux = float(self.fluxLineEdit.text())
        qy = float(self.qyLineEdit.text())
        plt.plot(t_list,sim.nbd_conc_imag(t_list,qy,flux,self.c_1.real,self.c_1.imag)/self.b)
        plt.ylim(bottom=0)
        plt.show()
        return
    
    @pyqtSlot()
    def on_btnExport_clicked(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            self.print_to_message_box(f"Saving to: {fileName}")
            self.save_path = fileName
        else:
            self.print_to_message_box("No filename was selected and therefore the experiment has not started")
            return
        try:
            df = pd.DataFrame()
            df["time"] = self.x_list
            df["abs"] = self.y_list
            df.to_csv(f"{fileName}.csv",index=False)
        except:
            self.print_to_message_box("No data could be exported. Perform analysis first.")
        return

class QY_analysis:
    def __init__(self):
        print("Please setup all reaction parameters for the calculation. The parameters can be found with .help()")
        #Below is the standard data for the KMP1
        self.file_name = ""
        self.LED_wl = 365 #Wavelength of the LED for irradiation
        self.qy_wl = 340 #Wavelength for the absorption peak of NBD for analysis
        self.start_conc = 9.5426e-06 #Starting concenctration of experiments performed on 21Mar2023
        self.qy = None #0.61 is the QY calculated for KMP1
        self.flux = None #Standard flux set to None, for calibration of Flux
        self.V = 80e-6 #The volume of the flow cell
        self.LED_current = 300 #The current of the LED
        self.N_A = 6.022e+23 #Avogadros number, it's required so don't question it.
        self.corr = 0
        self.zero_wl = 400
        self.num_points = 15
        self.start_point = 0
        self.end_point = -1
        self.path_length = 1
        return
    
    def calculate_QY(self,calc_conc = False, start_x = 0, end_x = -1):
        #Some constants
        
        #First check if the necessary parameters are set
        self.get_current_params()
#         cont = input("These are the current parameters. Are you sure you want to continue? y/n: ")
        cont = "y"
        if cont.lower() != "y":
            print("Cancelling calculation.")
            return
        data = pd.read_csv(self.file_name, sep=' ', header = None,skiprows=2)
        self.zero_col = np.argmin([abs(x-self.zero_wl) for x in data.iloc[0,:]])
        print(self.zero_col)
        if self.corr != 0:
            corr = self.corr
        else:
            corr = -np.mean(data.iloc[1,self.zero_col-5:self.zero_col+5])
        # print(np.min(data.iloc[1,1:]))
        ex_col = data.iloc[0,:].round(0).to_list().index(self.LED_wl)
        wl_col = data.iloc[0,:].round(0).to_list().index(self.qy_wl)
        data_wl = data.iloc[1:,0][self.start_point:self.end_point]
        data_wl = data_wl - data.iloc[self.start_point+1,0] #correction so it always starts at 0
        self.data_wl = data_wl
        data_i = [num + corr for num in data.iloc[1:,wl_col]][self.start_point:self.end_point]
        data_i = (data.iloc[1:,wl_col]-data.iloc[1:,self.zero_col]).to_list()[self.start_point:self.end_point]
        self.data_i = data_i
        data_ex = [num + corr for num in data.iloc[1:,ex_col]][self.start_point:self.end_point]
        data_ex = (data.iloc[1:,ex_col]-data.iloc[1:,self.zero_col]).to_list()[self.start_point:self.end_point]
        data_t0 = data.iloc[1,1:][self.start_point:self.end_point]
        if calc_conc:
            extinc_col = data.iloc[0,:].round(0).to_list().index(self.extincwl)
            self.start_conc = (data.iloc[1,extinc_col] + corr)/(self.extinc*self.path_length)
            print(f"Calculated starting concentration is: {self.start_conc}")
        else:
            pass
        self.first_abs = []
        self.first_wl = data.iloc[0,2:].to_list()
        for spec_point in np.linspace(self.start_point,self.end_point,10,dtype=int):
            print(spec_point)
            self.first_abs.append(np.array(data.iloc[spec_point,2:].to_list())-data.iloc[:,self.zero_col].to_list()[spec_point])
        self.b = data_i[0] /(self.start_conc*self.path_length)
        self.b_ex = data_ex[0]/(self.start_conc*self.path_length)
        remove_qc = []
        data_c = []
        for dot in range(len(data_i)):
            diff = (1-(data_i[dot]/data_i[0]))*data_i[-1]
            remove_qc.append(diff)
            data_c.append(data_i[dot]-diff)
        data_c = data_i
        self.data_ex = data_ex
        num_points = self.num_points
        if self.flux == None:
            # for i in range(15):
                # params = self.run_qy_calc(data_wl[:i],data_c[:i],self.start_conc)
            params = self.run_qy_calc(data_wl[:num_points],data_c[:num_points],self.start_conc)
        if self.qy == None:
            # for i in range(15):
            #     params = self.run_flux_calc(data_wl[:i],data_c[:i],self.start_conc)
            params = self.run_flux_calc(data_wl[:num_points],data_c[:num_points],self.start_conc)
        x=np.linspace(0,data_wl[self.end_point],400)
        return params , x
                  
    def help(self):
        print(f"The required parameters are listed below. To see the current parameters run .get_current_params()")
        return 
    
    def get_current_params(self):
        print(f"Current parameters are:\nData file: {self.file_name}\nIrradiation wavelength: {self.LED_wl}\n"+
              f"Measurement wavelength: {self.qy_wl} nm\nStarting concenctration: {self.start_conc} M\n"+
              f"Calculated Quantum Yield: {self.qy}\nCalculated Photon Flux: {self.flux} 1/s\n"+
              f"Flow cell volume: {self.V} l\nLED current: {self.LED_current}")
        return
    
    def nbd_conc_imag(self,t,qy,I,cr,ci):
        a = (qy*I)/(self.V*self.N_A)
        return (0.434294*np.log(1-(2.71828**(2.30259*self.b_ex*complex(cr,ci)-2.30259*a*self.b_ex*t))))*(self.b/self.b_ex)
    
    def helper_qy(self,x,qy):
        return self.nbd_conc_imag(x,qy,self.flux,self.c_1.real,self.c_1.imag)
    
    def helper_flux(self,x,I):
        return self.nbd_conc_imag(x,self.qy,I,self.c_1.real,self.c_1.imag)

    def run_qy_calc(self,x_vals,y_vals,start_conc):
        old_x_vals = x_vals
        old_y_vals = y_vals
#         x_vals = old_x_vals[:10]
#         y_vals = old_y_vals[:10]
        if len(x_vals)>1:
            self.b = y_vals[0] /(start_conc*self.path_length)
            s = self.start_conc
            n = 1
            self.c_1 = (np.log(1 - (10**(self.b_ex * s) + 0j )) + 2j * np.pi * n)/(self.b_ex * np.log(10))
    #         popt,pcov = scipy.optimize.curve_fit(nbd_conc_imag,x_vals,y_vals,bounds=([0,1e12,1.1*c_1.real,0.9*c_1.imag],[1,1e16,0.9*c_1.real,c_1.imag*1.1]),p0=[0.5,6e13,c_1.real,c_1.imag],check_finite=False)
            try:
                popt,pcov = scipy.optimize.curve_fit(self.helper_flux,x_vals,y_vals,p0=[10e14],bounds=([0],[10e20]),check_finite=False)
                self.pcov = pcov
            except:
                print("Curve fit did not converge. Check your parameters.")
        
            print(f"PHOTON FLUX PREDICTED TO BE: {popt[0]/self.LED_current:.2e} 1/s @ BASED ON {len(x_vals)} DATA POINTS. b is: {self.b}")
            return popt
        return "Not enough datapoints..."
    
    def run_flux_calc(self,x_vals,y_vals,start_conc):
        old_x_vals = x_vals
        old_y_vals = y_vals
#         x_vals = old_x_vals[:10]
#         y_vals = old_y_vals[:10]
        if len(x_vals)>1:
            self.b = y_vals[0] /start_conc
            s = self.start_conc
            n = 1
            self.c_1 = (np.log(1 - (10**(self.b_ex * s) + 0j )) + 2j * np.pi * n)/(self.b_ex * np.log(10))
    #         popt,pcov = scipy.optimize.curve_fit(nbd_conc_imag,x_vals,y_vals,bounds=([0,1e12,1.1*c_1.real,0.9*c_1.imag],[1,1e16,0.9*c_1.real,c_1.imag*1.1]),p0=[0.5,6e13,c_1.real,c_1.imag],check_finite=False)
            try:
                popt,pcov = scipy.optimize.curve_fit(self.helper_qy,x_vals,y_vals,p0=[0.5],bounds=([-1],[10]),check_finite=False)
                self.pcov = pcov
            except:
                print("Curve fit did not converge. Check your parameters.")
        
            print(f"QUANTUM YIELD PREDICTED TO BE: {popt[0]:.2e} % @ BASED ON {len(x_vals)} DATA POINTS. b is: {self.b} ! b_ex is: {self.b_ex}")
            return popt
        return "Not enough datapoints..."

    def run_qy_sim(self):
        ### Get data ready for the plot
        return
    


class Worker(QObject):
    finished = pyqtSignal()
    func = None
    def run(self):
        self.func()
        self.finished.emit()
        return

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=12, height=12, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


def main():
    app = QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    app.setApplicationName("QY Calculation Program")
    form = MainWindow()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
