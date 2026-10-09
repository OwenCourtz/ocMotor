import sys
from threading import Thread

from PyQt6.QtWidgets import QMainWindow, QTableWidgetItem, QHeaderView, QDockWidget, QWidget, QVBoxLayout, QMenu
from PyQt6.QtWidgets import QSizePolicy, QComboBox
from PyQt6.QtGui import QKeySequence, QPalette, QColor
from PyQt6.QtCore import Qt

import motorlib
import uilib.widgets.aboutDialog
from uilib import theme
from uilib.views.MainWindow_ui import Ui_MainWindow

class Window(QMainWindow):
    # How wide the sidebar is when the window opens
    sidebarWidth = 360

    def __init__(self, app):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.app = app

        self.setWindowIcon(self.app.icon)

        self.appVersion = uilib.fileIO.appVersion
        self.appVersionStr = uilib.fileIO.appVersionStr

        self.app.preferencesManager.preferencesChanged.connect(self.applyPreferences)

        self.app.propellantManager.updated.connect(self.propListChanged)

        self.motorStatLabels = [self.ui.labelMotorDesignation, self.ui.labelImpulse, self.ui.labelDeliveredISP, self.ui.labelBurnTime,  self.ui.labelVolumeLoading,
                                self.ui.labelAveragePressure, self.ui.labelPeakPressure, self.ui.labelInitialKN, self.ui.labelPeakKN, self.ui.labelIdealThrustCoefficient,
                                self.ui.labelPropellantMass, self.ui.labelPropellantDimensions, self.ui.labelPortThroatRatio, self.ui.labelPeakMassFlux, self.ui.labelDeliveredThrustCoefficient
                               ]

        self.app.fileManager.fileNameChanged.connect(self.updateWindowTitle)
        self.app.fileManager.newMotor.connect(lambda _: self.resetOutput(True))
        self.app.fileManager.newMotor.connect(self.getQuickResults)
        self.app.fileManager.recentFileLoaded.connect(self.motorImported)

        self.app.importExportManager.motorImported.connect(self.motorImported)

        self.app.simulationManager.newSimulationResult.connect(self.updateMotorStats)
        self.app.simulationManager.newSimulationResult.connect(self.ui.resultsWidget.showData)

        self.aboutDialog = uilib.widgets.aboutDialog.AboutDialog(self.appVersionStr)

        self.app.toolManager.setupMenu(self.ui.menuTools)
        self.app.toolManager.changeApplied.connect(self.postLoadUpdate)

        self.setupSidebar()
        self.layoutMotorStats()
        self.setupMotorStats()
        self.setupMotorEditor()
        self.setupGrainAddition()
        self.setupMenu()
        self.setupPropSelector()
        self.setupGrainTable()
        self.setupGraph()

    def updateWindowTitle(self, name, saved):
        if not name and saved:
            self.setWindowTitle('ocMotor')
            return
        unsavedStr = '*' if not saved else ''
        displayName = name if name is not None else ''
        self.setWindowTitle('ocMotor - {}{}'.format(displayName, unsavedStr))

    def setupSidebar(self):
        # The propellant selector and the list of the motor's parts live in a panel at the side of the window, which
        # can be hidden or pulled out into a window of its own
        panel = QWidget()
        panelLayout = QVBoxLayout(panel)
        column = self.ui.verticalLayoutMotorEditor
        for layout in (self.ui.horizontalLayoutPropellant, self.ui.horizontalLayoutEditButtons,
                       self.ui.horizontalLayoutAddGrain):
            column.removeItem(layout)
            layout.setParent(None)
        column.removeWidget(self.ui.tableWidgetGrainList)
        panelLayout.addLayout(self.ui.horizontalLayoutPropellant)
        panelLayout.addWidget(self.ui.tableWidgetGrainList)
        panelLayout.addLayout(self.ui.horizontalLayoutEditButtons)
        panelLayout.addLayout(self.ui.horizontalLayoutAddGrain)
        # The list and propellant selector were limited to the size of the space they used to have
        self.ui.tableWidgetGrainList.setMaximumSize(16777215, 16777215)
        self.ui.tableWidgetGrainList.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.comboBoxPropellant.setMaximumWidth(16777215)
        # A long propellant name shouldn't decide how narrow the sidebar can be made
        self.ui.comboBoxPropellant.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.ui.comboBoxPropellant.setMinimumContentsLength(12)
        self.ui.line.hide()

        self.sidebar = QDockWidget('Motor', self)
        self.sidebar.setObjectName('sidebarMotor')
        self.sidebar.setWidget(panel)
        self.sidebar.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
        self.resizeDocks([self.sidebar], [self.sidebarWidth], Qt.Orientation.Horizontal)

        menuView = QMenu('View', self.ui.menubar)
        self.ui.menubar.insertMenu(self.ui.menuSimulate.menuAction(), menuView)
        toggleSidebar = self.sidebar.toggleViewAction()
        toggleSidebar.setText('Motor Sidebar')
        toggleSidebar.setShortcut(QKeySequence('Ctrl+B'))
        menuView.addAction(toggleSidebar)

        # With the list in the sidebar, the column it was in only holds the editor, which is hidden until
        # something is being edited so it doesn't leave a gap
        self.setEditorVisible(False)
        self.ui.motorEditor.closed.connect(lambda: self.setEditorVisible(False))

    def setEditorVisible(self, visible):
        self.ui.motorEditor.setVisible(visible)
        self.ui.line_2.setVisible(visible)

    def editObject(self, obj):
        self.setEditorVisible(True)
        self.ui.motorEditor.loadObject(obj)

    def layoutMotorStats(self):
        # The form puts the name and value of each statistic in a layout of their own, which leaves the values
        # wherever the names happen to end. Giving them a column each lines them up.
        grid = self.ui.gridLayout
        cells = [(grid.getItemPosition(index), grid.itemAt(index).layout()) for index in range(grid.count())]
        namePalette = QPalette(self.palette())
        namePalette.setColor(QPalette.ColorRole.WindowText, QColor(theme.getColor('mutedText')))
        for (row, column, _, _), cell in cells:
            grid.removeItem(cell)
            name, value = cell.itemAt(0).widget(), cell.itemAt(1).widget()
            grid.addWidget(name, row, column * 2)
            grid.addWidget(value, row, column * 2 + 1)
            # The values are what gets read, so they are the part that stands out
            name.setPalette(namePalette)
            valueFont = value.font()
            valueFont.setBold(True)
            value.setFont(valueFont)
            grid.setColumnStretch(column * 2 + 1, 1)
        grid.setHorizontalSpacing(12)

    def setupMotorStats(self):
        for label in self.motorStatLabels:
            label.setText("-")

    def doubleClickGrainSelector(self):
        self.editGrain()

    def setupMotorEditor(self):
        self.ui.motorEditor.setPreferences(self.app.preferencesManager.preferences)
        self.ui.pushButtonEditGrain.pressed.connect(self.editGrain)
        self.ui.motorEditor.changeApplied.connect(self.applyChange)
        # Enables only buttons for actions possible given the selected grain
        self.ui.motorEditor.closed.connect(self.checkGrainSelection)

    def setupGrainAddition(self):
        self.ui.comboBoxGrainGeometry.addItems(motorlib.grains.grainTypes.keys())
        self.ui.pushButtonAddGrain.pressed.connect(self.addGrain)

    def setupMenu(self):
        # File menu
        self.ui.actionNew.triggered.connect(self.newMotor)
        self.ui.actionSave.triggered.connect(self.app.fileManager.save)
        self.ui.actionSaveAs.triggered.connect(self.app.fileManager.saveAs)
        # Lambda because the signal passes in an argument
        self.ui.actionOpen.triggered.connect(lambda x: self.loadMotor(None))

        self.app.importExportManager.createMenus(self.ui.menuImport, self.ui.menuExport)
        self.app.fileManager.createRecentlyOpenedMenu(self.ui.menuOpen_Recent)

        self.ui.actionQuit.triggered.connect(self.closeEvent)

        # Edit menu
        self.ui.actionUndo.triggered.connect(self.undo)
        self.ui.actionRedo.triggered.connect(self.redo)
        self.ui.actionPreferences.triggered.connect(self.app.preferencesManager.showMenu)
        self.ui.actionPropellantEditor.triggered.connect(self.app.propellantManager.showMenu)

        # Sim
        self.ui.actionRunSimulation.triggered.connect(self.runSimulation)

        # Help
        self.ui.actionAboutOpenMotor.triggered.connect(self.aboutDialog.show)

    def setupPropSelector(self):
        self.ui.pushButtonPropEditor.pressed.connect(self.app.propellantManager.showMenu)
        self.populatePropSelector()
        self.ui.comboBoxPropellant.currentIndexChanged.connect(self.propChooserChanged)
        self.updatePropBoxSelection()

    def populatePropSelector(self):
        self.ui.comboBoxPropellant.clear()
        self.ui.comboBoxPropellant.addItem('-')
        self.ui.comboBoxPropellant.addItems(self.app.propellantManager.getNames())

    def disablePropSelector(self):
        self.ui.comboBoxPropellant.blockSignals(True)

    def enablePropSelector(self):
        self.ui.comboBoxPropellant.blockSignals(False)

    def updatePropBoxSelection(self):
        self.disablePropSelector()
        cm = self.app.fileManager.getCurrentMotor()
        prop = self.app.fileManager.getCurrentMotor().propellant
        if prop is None:
            self.ui.comboBoxPropellant.setCurrentText('-')
        else:
            self.ui.comboBoxPropellant.setCurrentText(prop.getProperty("name"))
        self.enablePropSelector()

    def setupGrainTable(self):
        self.ui.tableWidgetGrainList.clearContents()

        header = self.ui.tableWidgetGrainList.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.updateGrainTable()

        self.ui.pushButtonMoveGrainUp.pressed.connect(lambda: self.moveGrain(-1))
        self.ui.pushButtonMoveGrainDown.pressed.connect(lambda: self.moveGrain(1))
        self.ui.pushButtonDeleteGrain.pressed.connect(self.deleteGrain)
        self.ui.pushButtonCopyGrain.pressed.connect(self.copyGrain)

        self.ui.tableWidgetGrainList.itemSelectionChanged.connect(self.checkGrainSelection)
        self.checkGrainSelection()
        
        self.ui.tableWidgetGrainList.doubleClicked.connect(self.doubleClickGrainSelector)

    def setupGraph(self):
        self.ui.resultsWidget.resetPlot()
        self.ui.resultsWidget.setPreferences(self.app.preferencesManager.preferences)

    def applyChange(self, propDict):
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        cm = self.app.fileManager.getCurrentMotor()
        if len(ind) > 0:
            gid = ind[0].row()
            if gid < len(cm.grains):
                cm.grains[gid].setProperties(propDict)
            elif gid == len(cm.grains):
                cm.nozzle.setProperties(propDict)
            else:
                cm.config.setProperties(propDict)
        self.app.fileManager.addNewMotorHistory(cm)
        self.updateGrainTable()

    def propListChanged(self):
        self.resetOutput()
        self.disablePropSelector()
        self.populatePropSelector()
        self.updatePropBoxSelection()
        self.enablePropSelector()

    def propChooserChanged(self):
        cm = self.app.fileManager.getCurrentMotor()
        if self.ui.comboBoxPropellant.currentIndex() == 0:
            cm.propellant = None
        else:
            cm.propellant = self.app.propellantManager.propellants[self.ui.comboBoxPropellant.currentIndex() - 1]
        self.app.fileManager.addNewMotorHistory(cm)

    def updateGrainTable(self):
        cm = self.app.fileManager.getCurrentMotor()
        self.ui.tableWidgetGrainList.setRowCount(len(cm.grains) + 2)
        lengthUnit = self.app.preferencesManager.preferences.units.getProperty('m')
        for gid, grain in enumerate(cm.grains):
            self.ui.tableWidgetGrainList.setItem(gid, 0, QTableWidgetItem(grain.geomName))
            self.ui.tableWidgetGrainList.setItem(gid, 1, QTableWidgetItem(grain.getDetailsString(lengthUnit)))

        self.ui.tableWidgetGrainList.setItem(len(cm.grains), 0, QTableWidgetItem('Nozzle'))
        self.ui.tableWidgetGrainList.setItem(len(cm.grains), 1, QTableWidgetItem(cm.nozzle.getDetailsString(lengthUnit)))

        self.ui.tableWidgetGrainList.setItem(len(cm.grains) + 1, 0, QTableWidgetItem('Config'))
        self.ui.tableWidgetGrainList.setItem(len(cm.grains) + 1, 1, QTableWidgetItem('-'))

    def toggleGrainEditButtons(self, state, grainTable=True):
        if grainTable:
            self.ui.tableWidgetGrainList.setEnabled(state)
        self.ui.pushButtonDeleteGrain.setEnabled(state)
        self.ui.pushButtonEditGrain.setEnabled(state)
        self.ui.pushButtonCopyGrain.setEnabled(state)
        self.ui.pushButtonMoveGrainDown.setEnabled(state)
        self.ui.pushButtonMoveGrainUp.setEnabled(state)

    def toggleGrainButtons(self, state):
        self.toggleGrainEditButtons(state)
        self.ui.comboBoxPropellant.setEnabled(state)
        self.ui.comboBoxGrainGeometry.setEnabled(state)
        self.ui.pushButtonAddGrain.setEnabled(state)

    def checkGrainSelection(self):
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        cm = self.app.fileManager.getCurrentMotor()
        if len(ind) > 0:
            gid = ind[0].row()
            self.toggleGrainButtons(True)
            if gid == 0: # Top grain selected
                self.ui.pushButtonMoveGrainUp.setEnabled(False)
            if gid == len(cm.grains) - 1: # Bottom grain selected
                self.ui.pushButtonMoveGrainDown.setEnabled(False)
            if gid >= len(cm.grains): # Nozzle or config selected
                self.ui.pushButtonMoveGrainUp.setEnabled(False)
                self.ui.pushButtonMoveGrainDown.setEnabled(False)
                self.ui.pushButtonDeleteGrain.setEnabled(False)
                self.ui.pushButtonCopyGrain.setEnabled(False)
        else:
            self.toggleGrainEditButtons(False, False)

    def moveGrain(self, offset):
        cm = self.app.fileManager.getCurrentMotor()
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        if len(ind) > 0:
            gid = ind[0].row()
            if gid < len(cm.grains) and gid + offset < len(cm.grains) and gid + offset >= 0:
                cm.grains[gid + offset], cm.grains[gid] = cm.grains[gid], cm.grains[gid + offset]
                self.ui.tableWidgetGrainList.selectRow(gid + offset)
                self.app.fileManager.addNewMotorHistory(cm)
                self.updateGrainTable()

    def editGrain(self):
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        cm = self.app.fileManager.getCurrentMotor()
        if len(ind) > 0:
            gid = ind[0].row()
            if gid < len(cm.grains):
                self.editObject(cm.grains[gid])
            elif gid == len(cm.grains):
                self.editObject(cm.nozzle)
            else:
                self.editObject(cm.config)
            self.toggleGrainButtons(False)

    def copyGrain(self):
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        cm = self.app.fileManager.getCurrentMotor()
        if len(ind) > 0:
            gid = ind[0].row()
            if gid < len(cm.grains):
                cm.grains.append(cm.grains[gid])
                self.app.fileManager.addNewMotorHistory(cm)
                self.updateGrainTable()
                self.checkGrainSelection()

    def deleteGrain(self):
        ind = self.ui.tableWidgetGrainList.selectionModel().selectedRows()
        cm = self.app.fileManager.getCurrentMotor()
        if len(ind) > 0:
            gid = ind[0].row()
            if gid < len(cm.grains):
                del cm.grains[gid]
                self.app.fileManager.addNewMotorHistory(cm)
                self.updateGrainTable()
                self.checkGrainSelection()

    def addGrain(self):
        cm = self.app.fileManager.getCurrentMotor()
        newGrain = motorlib.grains.grainTypes[self.ui.comboBoxGrainGeometry.currentText()]()
        if len(cm.grains) != 0:
            newGrain.setProperty('diameter', cm.grains[-1].getProperty('diameter'))
        cm.grains.append(newGrain)
        self.app.fileManager.addNewMotorHistory(cm)
        self.updateGrainTable()
        self.ui.tableWidgetGrainList.selectRow(len(cm.grains) - 1)
        self.editObject(cm.grains[-1])
        self.checkGrainSelection()
        self.toggleGrainButtons(False)

    def formatMotorStat(self, quantity, inUnit):
        convUnit = self.app.preferencesManager.preferences.getUnit(inUnit)
        return '{:.2f} {}'.format(motorlib.units.convert(quantity, inUnit, convUnit), convUnit)

    def updateMotorStats(self, simResult):
        self.ui.labelMotorDesignation.setText('{} ({:.0%})'.format(simResult.getDesignation(), simResult.getImpulseClassPercentage()))
        self.ui.labelImpulse.setText(self.formatMotorStat(simResult.getImpulse(), 'Ns'))
        self.ui.labelDeliveredISP.setText(self.formatMotorStat(simResult.getISP(), 's'))
        self.ui.labelBurnTime.setText(self.formatMotorStat(simResult.getBurnTime(), 's'))
        self.ui.labelVolumeLoading.setText('{:.2f}%'.format(simResult.getVolumeLoading()))

        self.ui.labelAveragePressure.setText(self.formatMotorStat(simResult.getAveragePressure(), 'Pa'))
        self.ui.labelPeakPressure.setText(self.formatMotorStat(simResult.getMaxPressure(), 'Pa'))
        self.ui.labelInitialKN.setText(self.formatMotorStat(simResult.getInitialKN(), ''))
        self.ui.labelPeakKN.setText(self.formatMotorStat(simResult.getPeakKN(), ''))
        self.ui.labelIdealThrustCoefficient.setText(self.formatMotorStat(simResult.getIdealThrustCoefficient(), ''))

        self.ui.labelPropellantMass.setText(self.formatMotorStat(simResult.getPropellantMass(), 'kg'))
        propellantDimensionString = '⌀ {} x {}'.format(
            self.formatMotorStat(simResult.getMaxPropellantDiameter(), 'm'),
            self.formatMotorStat(simResult.getPropellantLength(), 'm')
        )
        self.ui.labelPropellantDimensions.setText(propellantDimensionString)

        # These only make sense for grains with cores, so blank them out for endburners
        if simResult.getPortRatio() is not None:
            self.ui.labelPortThroatRatio.setText(self.formatMotorStat(simResult.getPortRatio(), ''))
            peakMassFluxQuantity = self.formatMotorStat(simResult.getPeakMassFlux(), 'kg/(m^2*s)')
            peakMassFluxGrain = simResult.getPeakMassFluxLocation() + 1
            self.ui.labelPeakMassFlux.setText('{} (G: {})'.format(peakMassFluxQuantity, peakMassFluxGrain))

        else:
            self.ui.labelPortThroatRatio.setText('-')
            self.ui.labelPeakMassFlux.setText('-')
        self.ui.labelDeliveredThrustCoefficient.setText(self.formatMotorStat(simResult.getAdjustedThrustCoefficient(), ''))

    def getQuickResults(self, motor):
        thread = lambda: self.showQuickResults(motor.getQuickResults())

        dataThread = Thread(target=thread)
        dataThread.start()

    def showQuickResults(self, results):
        self.ui.labelVolumeLoading.setText('{:.2f}%'.format(results['volumeLoading']))
        self.ui.labelInitialKN.setText(self.formatMotorStat(results['initialKn'], ''))
        propellantDimensionString = '⌀ {} x {}'.format(
            self.formatMotorStat(results['diameter'], 'm'),
            self.formatMotorStat(results['length'], 'm')
        )
        self.ui.labelPropellantDimensions.setText(propellantDimensionString)
        self.ui.labelPropellantMass.setText(self.formatMotorStat(results['propellantMass'], 'kg'))
        self.ui.labelPortThroatRatio.setText(self.formatMotorStat(results['portRatio'], ''))

    def runSimulation(self):
        self.resetOutput()
        cm = self.app.fileManager.getCurrentMotor()
        self.app.simulationManager.runSimulation(cm)

    def resetOutput(self, keepGrainChecks = True):
        self.setupMotorStats()
        self.ui.resultsWidget.resetPlot()
        self.updateGrainTable()
        self.ui.resultsWidget.setupGrainChecks(len(self.app.fileManager.getCurrentMotor().grains), keepGrainChecks)

    def undo(self):
        self.app.fileManager.undo()
        self.updateGrainTable()
        self.checkGrainSelection()
        self.updatePropBoxSelection()
        self.ui.motorEditor.close()

    def redo(self):
        self.app.fileManager.redo()
        self.updateGrainTable()
        self.checkGrainSelection()
        self.updatePropBoxSelection()
        self.ui.motorEditor.close()

    def newMotor(self):
        self.app.fileManager.newFile()
        self.updatePropBoxSelection()
        self.resetOutput()
        self.ui.motorEditor.close()

    def motorImported(self):
        self.ui.motorEditor.close()
        self.postLoadUpdate()
        self.getQuickResults(self.app.fileManager.getCurrentMotor())

    def loadMotor(self, path=None):
        self.disablePropSelector()
        if self.app.fileManager.load(path):
            self.postLoadUpdate()
             # Needed because postLoadUpdate clears results
            self.getQuickResults(self.app.fileManager.getCurrentMotor())
        self.enablePropSelector()
        self.ui.motorEditor.close()

    # Clear out all info related to old motor/sim in the interface
    def postLoadUpdate(self):
        self.disablePropSelector() # It is enabled again at the end of updatePropBoxSelection
        self.resetOutput(False)
        self.updateGrainTable()
        self.populatePropSelector()
        self.updatePropBoxSelection()

    def closeEvent(self, event=None):
        if self.app.fileManager.unsavedCheck():
            sys.exit()
            return
        if event is None or isinstance(event, bool):
            return
        event.ignore()

    def applyPreferences(self, prefDict):
        self.updateGrainTable()
        self.setupMotorStats()
        self.setupGraph()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            if len(self.ui.tableWidgetGrainList.selectedItems()) != 0:
                self.deleteGrain()
