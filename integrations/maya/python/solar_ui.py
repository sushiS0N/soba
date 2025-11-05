import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.mel as mel
from maya import OpenMayaUI as omui

from shiboken6 import wrapInstance
from PySide6 import QtUiTools, QtCore, QtGui, QtWidgets
from functools import partial  # optional, for passing args during signal function calls
import sys
import os

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from core import config

from integrations.maya.python import usd_exporter as usde
from integrations.maya.python import client


def get_selected_meshes():
    """Get full paths of selected meshes"""
    sel = om.MGlobal.getActiveSelectionList()
    if sel.length() == 0:
        raise ValueError("No meshes selected")

    meshes = []
    for i in range(sel.length()):
        try:
            dag_path = sel.getDagPath(i)
            meshes.append(dag_path.fullPathName())
        except:
            continue

    if not meshes:
        raise ValueError("No valid meshes found in selection")

    return meshes


class SolarMayaUI(QtWidgets.QWidget):
    """
    Create a default tool window.
    """

    window = None

    def __init__(self, parent=None):
        """
        Initialize class.
        """
        super(SolarMayaUI, self).__init__(parent=parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self._widgetPath = self.getWidgetPath()
        self._tempPath = self.getTempPath()

        self.widget = QtUiTools.QUiLoader().load(self._widgetPath)
        self.widget.setParent(self)
        # set initial window size
        self.minimumWidth = 650
        self.minimumHeight = 500

        self.resize(self.minimumWidth, self.minimumHeight)

        # global variables
        self.target_meshes = []
        self.context_meshes = []
        self.epw_path = None
        self.solar_params = None
        self.analysis_client = client.SolarAnalysisClient(
            server_url=(f"http://{config.SERVER_HOST}:{config.SERVER_PORT}"),
            status_callback=self.on_status_update,
        )

        # locate UI widgets
        # Buttons
        self.btn_epw = self.widget.findChild(QtWidgets.QPushButton, "btn_epw")
        self.btn_target = self.widget.findChild(QtWidgets.QPushButton, "btn_target")
        self.btn_context = self.widget.findChild(QtWidgets.QPushButton, "btn_context")
        self.btn_run = self.widget.findChild(QtWidgets.QPushButton, "btn_run")
        # TODO: self.btn_reset = self.widget.findChild(QtWidgets.QPushButton, "btn_reset")

        # Line edits
        self.le_epw = self.widget.findChild(QtWidgets.QLineEdit, "le_epw")

        self.le_monthStart = self.widget.findChild(QtWidgets.QLineEdit, "le_monthStart")
        self.le_monthEnd = self.widget.findChild(QtWidgets.QLineEdit, "le_monthEnd")
        self.le_dayStart = self.widget.findChild(QtWidgets.QLineEdit, "le_dayStart")
        self.le_dayEnd = self.widget.findChild(QtWidgets.QLineEdit, "le_dayEnd")
        self.le_hourStart = self.widget.findChild(QtWidgets.QLineEdit, "le_hourStart")
        self.le_hourEnd = self.widget.findChild(QtWidgets.QLineEdit, "le_hourEnd")
        self.le_timestep = self.widget.findChild(QtWidgets.QLineEdit, "le_timestep")

        self.le_offset = self.widget.findChild(QtWidgets.QLineEdit, "le_offset")

        self.le_target = self.widget.findChild(QtWidgets.QLineEdit, "le_target")
        self.le_context = self.widget.findChild(QtWidgets.QLineEdit, "le_context")

        # Progress bar
        self.progress_bar = self.widget.findChild(QtWidgets.QProgressBar, "progressBar")

        # assign functionality to buttons
        self.btn_epw.clicked.connect(self.loadSolarParams)
        self.btn_target.clicked.connect(self.selectTargetMeshes)
        self.btn_context.clicked.connect(self.selectContextMeshes)
        self.btn_run.clicked.connect(self.runAnalysis)

    def getWidgetPath(self):
        maya_scripts_dir = cmds.internalVar(userScriptDir=True)
        solar_path = os.path.join(maya_scripts_dir, "SolarAnalysis", "SolarUI.ui")

        return solar_path

    def getTempPath(self):
        maya_scripts_dir = cmds.internalVar(userScriptDir=True)

        temp_path = os.path.join(maya_scripts_dir, "SolarAnalysis", "temp")
        try:
            os.makedirs(temp_path, exist_ok=True)
        except OSError as e:
            print(f"Error creating temporary directory {temp_path}: {e}")

        return temp_path

    def on_status_update(self, status, progress, error_msg=None):
        """
        Handle status updates from analysis client

        Args:
            status: One of "queued", "processing", "downloading", "complete", "error"
            progress: Integer 0-100 for progress bar
            error_msg: Optional error message if status is "error"
        """
        # Update progress bar
        self.progress_bar.setValue(progress)

        # Update status label (if you have one)
        status_messages = {
            "queued": " Job queued...",
            "processing": " Processing analysis...",
            "downloading": " Downloading results...",
            "complete": " Analysis complete!",
            "error": f" Error: {error_msg}",
        }

        message = status_messages.get(status, status)

        if hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(message)

        print(f"Status: {message} ({progress}%)")

        # Optional: Disable/enable UI elements based on status
        if status in ["queued", "processing", "downloading"]:
            self.btn_run.setEnabled(False)  # Disable run button during processing
        elif status in ["complete", "error"]:
            self.btn_run.setEnabled(True)  # Re-enable when done

    def resizeEvent(self, event):
        """
        Called on automatically generated resize event
        """
        self.widget.resize(
            max(self.minimumWidth, self.width()), max(self.minimumHeight, self.height())
        )

    def loadSolarParams(self):
        """Button handler for EPW import"""
        file_filter = "Epw file (*.epw)"
        response = QtWidgets.QFileDialog.getOpenFileName(
            parent=self, caption="Select a file", filter=file_filter
        )

        # Display file path in UI
        epw = str(response[0])
        if not epw:  # User cancelled
            return

        self.le_epw.setText(epw)

        # Get solar parameters from UI
        try:
            solar_params = [
                int(self.le_monthStart.text()),
                int(self.le_monthEnd.text()),
                int(self.le_dayStart.text()),
                int(self.le_dayEnd.text()),
                int(self.le_hourStart.text()),
                int(self.le_hourEnd.text()),
                int(self.le_timestep.text()),
                float(self.le_offset.text()),
            ]
        except ValueError:
            print(
                "Error: Invalid solar parameters. Using defaults: [6, 6, 21, 21, 0, 23, 1, 0.1]"
            )
            solar_params = [6, 6, 21, 21, 0, 23, 1, 0.1]  # Defaults

        self.epw_path = epw
        self.solar_params = solar_params

        print(f"EPW loaded: {epw}")
        print(f"Solar params: {solar_params}")

    def selectTargetMeshes(self):
        try:
            self.target_meshes = get_selected_meshes()
            clean_names = [m.split("|")[-1] for m in self.target_meshes]
            self.le_target.setText(", ".join(clean_names))
            print(f"Target: {self.target_meshes}")
        except Exception as e:
            print(f"Error: {e}")

    def selectContextMeshes(self):
        try:
            self.context_meshes = get_selected_meshes()
            clean_names = [m.split("|")[-1] for m in self.context_meshes]
            self.le_context.setText(", ".join(clean_names))
            print(f"Context: {len(self.context_meshes)} meshes")
        except Exception as e:
            print(f"Error: {e}")

    def runAnalysis(self):
        """Run solar analysis via server (non-blocking)"""
        try:
            self.progress_bar.setValue(0)
            # Validate inputs
            if not self.target_meshes:
                raise ValueError("Target meshes not loaded")
            if not self.context_meshes:
                raise ValueError("Context meshes not loaded")
            if not self.epw_path:
                raise ValueError("EPW not loaded")
            if not self.solar_params:
                raise ValueError("Solar parameters not set")

            # Export USD
            target = self.target_meshes
            context = self.context_meshes

            usd_path = os.path.join(self._tempPath, "solar_analysis.usda")
            usde.export_solar_scene(
                target, context, usd_path, self.solar_params, self.epw_path
            )

            print(" Submitting job to analysis server...")

            # Submit to server (non-blocking!)
            self.analysis_client.submit_job(
                usd_path, self.epw_path, callback=self.on_analysis_complete
            )

            print(" Job submitted! Maya remains responsive while processing...")

        except Exception as e:
            print(f" Error: {e}")
            import traceback

            traceback.print_exc()

    def on_analysis_complete(self, success, result):
        """Callback when analysis finishes"""
        if success:
            print(f" Analysis complete!")
            print(f"   Result file: {result}")
            self.importResults(result)
        else:
            print(f" Analysis failed: {result}")

    def importResults(self, result_usd_path):
        """
        Import solar analysis results as new USD geometry in Maya

        Args:
            result_usd_path: Path to the results USD file with colors
        """
        try:
            print(f" Importing results from: {result_usd_path}")

            # Simple USD import - exactly like File > Import > USD
            cmds.mayaUSDImport(file=result_usd_path, primPath="/")

            print(f" Results imported successfully!")
            print(f"   Set viewport shading to 'Textured' (press 6) to see colors")

            # Refresh viewport
            cmds.refresh()

        except Exception as e:
            print(f" Error importing results: {e}")
            import traceback

            traceback.print_exc()

    def closeWindow(self):
        """
        Close window.
        """
        print("closing window")
        self.destroy()


def openWindow():
    """
    ID Maya and attach tool window.
    """
    # Maya uses this so it should always return True
    if QtWidgets.QApplication.instance():
        # Id any current instances of tool and destroy
        for win in QtWidgets.QApplication.allWindows():
            if (
                "solarMayaUI" in win.objectName()
            ):  # update this name to match name below
                win.destroy()

    # QtWidgets.QApplication(sys.argv)
    mayaMainWindowPtr = omui.MQtUtil.mainWindow()
    mayaMainWindow = wrapInstance(int(mayaMainWindowPtr), QtWidgets.QWidget)
    SolarMayaUI.window = SolarMayaUI(parent=mayaMainWindow)
    SolarMayaUI.window.setObjectName(
        "solarMayaUI"
    )  # code above uses this to ID any existing windows
    SolarMayaUI.window.setWindowTitle("Solar Analisys")
    SolarMayaUI.window.show()


openWindow()
