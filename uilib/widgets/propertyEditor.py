import math

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QCheckBox
from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox, QComboBox, QColorDialog
from PyQt6.QtCore import pyqtSignal, Qt, QRectF
from PyQt6.QtGui import QColor, QConicalGradient, QIcon, QPainter, QPixmap

import motorlib

from .. import theme
from .polygonEditor import PolygonEditor
from .tabularEditor import TabularEditor

class FloatEditor(QDoubleSpinBox):
    """A spin box that only shows the digits of its value that matter. It still holds its value to the full number of
    decimal places, and the value is only changed by what is shown if it is edited."""
    maxDecimals = 8
    significantDigits = 6

    def __init__(self):
        super().__init__()
        self.setDecimals(self.maxDecimals)

    def textFromValue(self, value):
        if value == 0:
            decimals = 0
        else:
            decimals = self.significantDigits - 1 - math.floor(math.log10(abs(value)))
            decimals = min(max(decimals, 0), self.maxDecimals)
        text = super().textFromValue(round(value, decimals))
        decimalPoint = self.locale().decimalPoint()
        if decimalPoint in text:
            text = text.rstrip('0').rstrip(decimalPoint)
        return text

    def valueFromText(self, text):
        # The spin box reads its value back from its text whenever it is done being edited, which would round the
        # value off to what is shown if nothing had been typed
        shown = text.removeprefix(self.prefix()).removesuffix(self.suffix()).strip()
        if shown == self.textFromValue(self.value()):
            return self.value()
        return super().valueFromText(text)


class ColorEditor(QLineEdit):
    """A text box for the hex code of a color, with a button at its end that opens a color picker"""
    iconSize = 64

    def __init__(self):
        super().__init__()
        self.pickAction = self.addAction(self.makeIcon(), QLineEdit.ActionPosition.TrailingPosition)
        self.pickAction.setToolTip('Pick a color')
        self.pickAction.triggered.connect(self.pickColor)
        self.textChanged.connect(lambda: self.pickAction.setIcon(self.makeIcon()))

    def makeIcon(self):
        """Returns the icon for the color picker button, which is a color wheel around the color that is entered"""
        pixmap = QPixmap(self.iconSize, self.iconSize)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        wheel = QConicalGradient(self.iconSize / 2, self.iconSize / 2, 0)
        for step in range(7):
            wheel.setColorAt(step / 6, QColor.fromHsvF((step / 6) % 1, 0.85, 0.95))
        painter.setBrush(wheel)
        painter.drawEllipse(QRectF(2, 2, self.iconSize - 4, self.iconSize - 4))
        # The middle shows the color that is entered, or what is behind the text box if there isn't one
        color = theme.parseColor(self.text())
        painter.setBrush(color if color.isValid() else self.palette().base())
        inset = self.iconSize * 0.24
        painter.drawEllipse(QRectF(inset, inset, self.iconSize - 2 * inset, self.iconSize - 2 * inset))
        painter.end()
        return QIcon(pixmap)

    def pickColor(self):
        current = theme.parseColor(self.text())
        color = QColorDialog.getColor(current if current.isValid() else QColor(theme.getColor('window')), self,
                                      'Pick a Color')
        if color.isValid():
            self.setText(color.name())


class PropertyEditor(QWidget):

    valueChanged = pyqtSignal()

    def __init__(self, parent, prop, preferences):
        super(PropertyEditor, self).__init__(QWidget(parent))
        self.preferences = preferences
        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(5, 5, 5, 5)
        self.prop = prop

        if self.preferences is not None:
            self.dispUnit = self.preferences.getUnit(self.prop.unit)
        else:
            self.dispUnit = self.prop.unit

        if isinstance(prop, motorlib.properties.FloatProperty):
            self.editor = FloatEditor()

            self.editor.setSuffix(' {}'.format(self.dispUnit))

            convMin = motorlib.units.convert(self.prop.min, self.prop.unit, self.dispUnit)
            convMax = motorlib.units.convert(self.prop.max, self.prop.unit, self.dispUnit)
            self.editor.setRange(convMin, convMax)

            self.editor.setSingleStep(10 ** (int(math.log(convMax, 10) - 4)))

            self.editor.setValue(motorlib.units.convert(self.prop.getValue(), prop.unit, self.dispUnit))
            self.editor.valueChanged.connect(self.valueChanged.emit)
            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.IntProperty):
            self.editor = QSpinBox()

            convMin = motorlib.units.convert(self.prop.min, self.prop.unit, self.dispUnit)
            convMax = motorlib.units.convert(self.prop.max, self.prop.unit, self.dispUnit)
            self.editor.setRange(convMin, convMax)

            self.editor.setValue(self.prop.getValue())
            self.editor.valueChanged.connect(self.valueChanged.emit)
            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.ColorProperty):
            self.editor = ColorEditor()
            self.editor.setText(self.prop.getValue())
            self.editor.setPlaceholderText('Theme default')
            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.StringProperty):
            self.editor = QLineEdit()
            self.editor.setText(self.prop.getValue())
            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.BooleanProperty):
            self.editor = QCheckBox()
            self.editor.setCheckState(Qt.CheckState.Checked if self.prop.getValue() else Qt.CheckState.Unchecked)
            self.editor.stateChanged.connect(self.valueChanged.emit)
            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.EnumProperty):
            self.editor = QComboBox()

            self.editor.addItems(self.prop.values)
            self.editor.setCurrentText(self.prop.value)
            self.editor.currentTextChanged.connect(self.valueChanged.emit)

            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.PolygonProperty):
            self.editor = PolygonEditor(self)

            self.editor.pointsChanged.connect(self.valueChanged.emit)
            self.editor.points = self.prop.getValue()
            self.editor.preferences = self.preferences

            self.layout().addWidget(self.editor)

        elif isinstance(prop, motorlib.properties.TabularProperty):
            self.editor = TabularEditor()

            self.editor.setPreferences(self.preferences)
            for tab in prop.tabs:
                self.editor.addTab(tab)
            self.editor.updated.connect(self.valueChanged.emit)

            self.layout().addWidget(self.editor)

    def getValue(self):
        if isinstance(self.prop, motorlib.properties.FloatProperty):
            return motorlib.units.convert(self.editor.value(), self.dispUnit, self.prop.unit)

        if isinstance(self.prop, motorlib.properties.IntProperty):
            return motorlib.units.convert(self.editor.value(), self.dispUnit, self.prop.unit)

        if isinstance(self.prop, motorlib.properties.StringProperty):
            return self.editor.text()

        if isinstance(self.prop, motorlib.properties.BooleanProperty):
            return self.editor.isChecked()

        if isinstance(self.prop, motorlib.properties.EnumProperty):
            return self.editor.currentText()

        if isinstance(self.prop, motorlib.properties.PolygonProperty):
            return self.editor.points

        if isinstance(self.prop, motorlib.properties.TabularProperty):
            return self.editor.getTabs()

        return None
