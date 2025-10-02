# -*- coding: utf-8 -*-
from ..qt_compat import QtCore, QtGui, QtWidgets, pyqtSignal, qt_left_button, painter_antialiasing_hint
import sys
sys.dont_write_bytecode = True
class VolumeBar(QtWidgets.QWidget):
    volumeChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._volume = 50
        self.setMinimumHeight(60)
        self.setStyleSheet("background-color: rgba(0,0,0,0);")

    def setVolume(self, volume):
        v = max(0, min(int(volume), 100))
        if v != self._volume:
            self._volume = v
            self.update()
            self.volumeChanged.emit(self._volume)

    def getVolume(self):
        return self._volume

    def mousePressEvent(self, event):
        if event.button() == qt_left_button():
            self._set_from_pos(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & qt_left_button():
            self._set_from_pos(event.pos())

    def _set_from_pos(self, pos: QtCore.QPoint):
        rect = self.rect()
        pct = int((pos.x() / max(1, rect.width())) * 100)
        self.setVolume(pct)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(painter_antialiasing_hint())

        rect = self.rect()

        # Base capsule — warm dark cocoa
        bg = QtGui.QLinearGradient(0, 0, 0, rect.height())
        bg.setColorAt(0.0, QtGui.QColor(34, 23, 18))   # #221712
        bg.setColorAt(1.0, QtGui.QColor(20, 14, 11))   # #140e0b
        painter.setBrush(QtGui.QBrush(bg))
        painter.setPen(QtGui.QPen(QtGui.QColor(56, 40, 32), 1))  # #382820
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)

        # Bars
        bar_count = 18
        spacing = 5
        inner = rect.adjusted(12, 10, -12, -10)
        bar_w = (inner.width() - spacing * (bar_count - 1)) / bar_count
        active = int((self._volume / 100) * bar_count)

        for i in range(bar_count):
            x = int(inner.x() + i * (bar_w + spacing))
            r = QtCore.QRect(int(x), inner.y(), int(bar_w), inner.height())

            if i < active:
                # shiny walnut gradient
                g = QtGui.QLinearGradient(0, r.y(), 0, r.bottom())
                g.setColorAt(0.0, QtGui.QColor(120, 80, 56))  # top glow (#785038)
                g.setColorAt(0.5, QtGui.QColor(70, 44, 30))   # mid (#462c1e)
                g.setColorAt(1.0, QtGui.QColor(45, 28, 20))   # base (#2d1c14)
                painter.setBrush(QtGui.QBrush(g))
                painter.setPen(QtGui.QPen(QtGui.QColor(110, 80, 62), 1))  # rim light
            else:
                painter.setBrush(QtGui.QColor(33, 24, 19))                # #211813
                painter.setPen(QtGui.QPen(QtGui.QColor(52, 34, 23), 1))   # #342217

            painter.drawRoundedRect(r, 6, 6)
