# -*- coding: utf-8 -*-
import sys
sys.dont_write_bytecode = True
USING_QT6 = False

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import QSettings, QTimer, QProcess, pyqtSignal, pyqtSlot, Qt
    USING_QT6 = True
    print("Using PyQt6")
except Exception as e:
    print("PyQt6 import failed, falling back to PyQt5:", e)
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import QSettings, QTimer, QProcess, pyqtSignal, pyqtSlot, Qt
    USING_QT6 = False
    print("Using PyQt5")

def qt_align_center():
    return Qt.AlignmentFlag.AlignCenter if USING_QT6 else Qt.AlignCenter

def qt_user_role():
    return Qt.ItemDataRole.UserRole if USING_QT6 else Qt.UserRole

def qt_left_button():
    return Qt.MouseButton.LeftButton if USING_QT6 else Qt.LeftButton

def available_geometry(widget: QtWidgets.QWidget):
    if USING_QT6:
        scr = widget.screen() or QtWidgets.QApplication.primaryScreen()
        return scr.availableGeometry()
    return QtWidgets.QDesktopWidget().availableGeometry()

def painter_antialiasing_hint():
    # PyQt6: QtGui.QPainter.RenderHint.Antialiasing; PyQt5: QtGui.QPainter.Antialiasing
    try:
        return QtGui.QPainter.RenderHint.Antialiasing  # PyQt6
    except AttributeError:
        return QtGui.QPainter.Antialiasing  # PyQt5
