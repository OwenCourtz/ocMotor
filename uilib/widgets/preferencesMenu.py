from PyQt6.QtWidgets import QDialog, QApplication, QColorDialog
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from ..views.Preferences_ui import Ui_PreferencesDialog


class PreferencesMenu(QDialog):

    preferencesApplied = pyqtSignal(dict)

    def __init__(self):
        QDialog.__init__(self)

        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QApplication.instance().icon)

        self.ui.buttonBox.accepted.connect(self.apply)
        self.ui.buttonBox.rejected.connect(self.cancel)
        self.ui.pushButtonAccent.pressed.connect(self.chooseAccent)

    def load(self, pref):
        self.ui.settingsEditorGeneral.setPreferences(pref)
        self.ui.settingsEditorGeneral.loadProperties(pref.general)
        self.ui.settingsEditorUnits.loadProperties(pref.units)
        self.ui.settingsEditorAppearance.loadProperties(pref.appearance)

    def chooseAccent(self):
        # The accent is a property that holds the name of a color, which this fills in from a color picker
        accentEditor = self.ui.settingsEditorAppearance.propertyEditors['accent'].editor
        color = QColorDialog.getColor(QColor(accentEditor.text()), self, 'Accent Color')
        if color.isValid():
            accentEditor.setText(color.name())

    def apply(self):
        self.preferencesApplied.emit({'general': self.ui.settingsEditorGeneral.getProperties(),
                                      'units': self.ui.settingsEditorUnits.getProperties(),
                                      'appearance': self.ui.settingsEditorAppearance.getProperties()})
        self.hide()

    def cancel(self):
        self.hide()
