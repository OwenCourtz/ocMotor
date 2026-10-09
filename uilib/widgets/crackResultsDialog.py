import copy
import csv

import numpy as np

from PyQt6.QtWidgets import QDialog, QApplication, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QFileDialog, QHeaderView, QSlider
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import motorlib
from motorlib.crackAnalysis import getAreaMultiplierAtPressure
from motorlib.grain import PerforatedGrain

from ..logger import logger
from .crackGeometryWidget import CrackGeometryWidget

class CrackResultsDialog(QDialog):
    """Shows the cases produced by a crack analysis as a table with a row per case and a graph that overlays them.
    The grains of the case that is selected are drawn beside the graph, with a slider to step them through its
    simulation."""

    # Emitted with the simulation result of a case when the user asks to see it in the main window
    showRequested = pyqtSignal(object)

    # The values shown for a case that was simulated successfully, as a title, unit, format and a function that gets
    # the value from the case's simulation result. The limit is the name of the config property that the value
    # should not exceed, if there is one.
    resultColumns = [
        ('Initial Kn', '', '{:.2f}', lambda simRes: simRes.getInitialKN(), None),
        ('Peak Kn', '', '{:.2f}', lambda simRes: simRes.getPeakKN(), None),
        ('Peak Pressure', 'Pa', '{:.2f}', lambda simRes: simRes.getMaxPressure(), 'maxPressure'),
        ('Average Pressure', 'Pa', '{:.2f}', lambda simRes: simRes.getAveragePressure(), None),
        ('Burn Time', 's', '{:.2f}', lambda simRes: simRes.getBurnTime(), None),
        ('Impulse', 'Ns', '{:.2f}', lambda simRes: simRes.getImpulse(), None),
        ('ISP', 's', '{:.2f}', lambda simRes: simRes.getISP(), None),
        ('Peak Mass Flux', 'kg/(m^2*s)', '{:.2f}', lambda simRes: simRes.getPeakMassFlux(), 'maxMassFlux'),
        ('Peak Mach Number', '', '{:.3f}', lambda simRes: simRes.getPeakMachNumber(), 'maxMachNumber'),
    ]
    plotChannels = ['pressure', 'force', 'kn']
    # The dimension of the maps that the grains are drawn from
    geometryMapDim = 300
    # How far past the end of the longest burn the time slider goes, so every case can be seen with nothing left
    timeSliderMargin = 1
    # Tooltips for the columns that aren't also shown for a normal simulation, by the index of the column
    columnTips = {
        0: 'The initial burning area of the cracked grains divided by what it is without the cracks',
        2: 'How far each crack extends into the propellant from the surface of the core',
        12: 'The time at which the flame first reaches the casting tube of a cracked grain'
    }

    def __init__(self):
        super().__init__()
        self.preferences = None
        self.cases = []
        # The regression data of the grains in each case that has been selected, by the row of the case
        self.geometryCache = {}
        # The IDs of the grains that are currently drawn
        self.geometryGrains = []
        self.timeMarker = None
        # The time that a step of the time slider is equal to
        self.timeStep = 1

        self.setWindowTitle('Cracked Grain Analysis')
        self.setWindowIcon(QApplication.instance().icon)
        self.resize(1300, 800)
        self.setLayout(QVBoxLayout())

        self.summaryLabel = QLabel()
        self.summaryLabel.setWordWrap(True)
        self.layout().addWidget(self.summaryLabel)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.selectionChanged)
        self.table.cellDoubleClicked.connect(self.showSelected)
        self.layout().addWidget(self.table, 2)

        self.channelSelector = QComboBox()
        self.channelSelector.currentIndexChanged.connect(self.drawGraph)
        channelLayout = QHBoxLayout()
        channelLayout.addWidget(QLabel('Graph:'))
        channelLayout.addWidget(self.channelSelector)
        channelLayout.addStretch()
        self.layout().addLayout(channelLayout)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.plot = self.figure.add_subplot(111)

        self.geometryWidget = CrackGeometryWidget()
        self.timeSlider = QSlider(Qt.Orientation.Horizontal)
        self.timeSlider.valueChanged.connect(self.timeChanged)
        self.timeLabel = QLabel('-')
        timeLayout = QHBoxLayout()
        timeLayout.addWidget(QLabel('Time:'))
        timeLayout.addWidget(self.timeSlider)
        timeLayout.addWidget(self.timeLabel)
        geometryLayout = QVBoxLayout()
        geometryLayout.addWidget(self.geometryWidget, 1)
        geometryLayout.addLayout(timeLayout)
        graphLayout = QHBoxLayout()
        graphLayout.addWidget(self.canvas, 3)
        graphLayout.addLayout(geometryLayout, 2)
        self.layout().addLayout(graphLayout, 3)

        self.showButton = QPushButton('Show Selected Case in Main Window')
        self.showButton.pressed.connect(self.showSelected)
        self.exportButton = QPushButton('Export Table')
        self.exportButton.pressed.connect(self.exportTable)
        self.closeButton = QPushButton('Close')
        self.closeButton.pressed.connect(self.hide)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.showButton)
        buttonLayout.addWidget(self.exportButton)
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.closeButton)
        self.layout().addLayout(buttonLayout)

    def setPreferences(self, pref):
        self.preferences = pref

    def formatValue(self, value, unit, form='{:.2f}'):
        return form.format(motorlib.units.convert(value, unit, self.preferences.getUnit(unit)))

    def formatTitle(self, title, unit):
        dispUnit = self.preferences.getUnit(unit)
        return title if dispUnit == '' else '{} ({})'.format(title, dispUnit)

    def getCaseName(self, case):
        """Returns a short name for a case that can be used to pick it out in the graph's legend"""
        if not case.isCracked():
            return 'No cracks'
        if case.requestedMultiplier is None:
            return 'Cracked'
        return '{:.3f}x area'.format(case.areaMultiplier)

    def showCases(self, cases):
        """Fills the dialog out from a list of crack cases and shows it."""
        self.cases = cases
        self.geometryCache = {}

        titles = ['Area Multiplier', 'Cracks Per Grain', self.formatTitle('Crack Depth', 'm')]
        titles += [self.formatTitle(title, unit) for title, unit, _, _, _ in self.resultColumns]
        titles += [self.formatTitle('Case Exposed', 's'), 'Designation', 'Alerts']
        self.table.clear()
        self.table.setColumnCount(len(titles))
        self.table.setHorizontalHeaderLabels(titles)
        for col, tip in self.columnTips.items():
            self.table.horizontalHeaderItem(col).setToolTip(tip)
        self.table.setRowCount(len(cases))

        for row, case in enumerate(cases):
            simRes = case.simRes
            config = simRes.motor.config
            # Cases that failed don't have an area of their own, so they fall back to the one that was asked for
            multiplier = case.areaMultiplier if case.areaMultiplier is not None else case.requestedMultiplier
            # Grains can have different cracks from each other, in which case the range is shown
            numCracks = sorted(set(case.numCracks.values()))
            depths = sorted(set(case.depths.values()))
            texts = ['{:.3f}'.format(multiplier) if multiplier is not None else '-',
                     ' - '.join(str(num) for num in numCracks),
                     ' - '.join(self.formatValue(depth, 'm', '{:.3f}') for depth in depths)]
            overLimit = []
            for _, unit, form, getter, limit in self.resultColumns:
                if not simRes.success:
                    texts.append('-')
                    continue
                value = getter(simRes)
                if limit is not None and value > config.getProperty(limit):
                    overLimit.append(len(texts))
                texts.append(self.formatValue(value, unit, form))
            if simRes.success and case.caseExposureTime is not None:
                texts.append('{:.2f}'.format(case.caseExposureTime))
            else:
                texts.append('-')
            texts.append(simRes.getDesignation() if simRes.success else '-')
            texts.append('; '.join(case.notes + [self.describeAlert(alert) for alert in simRes.alerts]))

            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if col in overLimit:
                    item.setBackground(QColor(255, 0, 0, 90))
                    item.setToolTip('Exceeds the limit set in the motor\'s configuration')
                self.table.setItem(row, col, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        self.channelSelector.blockSignals(True)
        self.channelSelector.clear()
        if len(cases) > 0:
            self.channelSelector.addItems([cases[0].simRes.channels[channel].name for channel in self.plotChannels])
        self.channelSelector.blockSignals(False)

        self.summaryLabel.setText(self.getSummary())
        self.setupTimeSlider()
        # The case with the most severe cracks is the one that is most likely to be of interest
        succeeded = [row for row, case in enumerate(cases) if case.simRes.success]
        if len(succeeded) > 0:
            self.table.selectRow(succeeded[-1])
        self.selectionChanged()
        self.show()
        self.raise_()

    def describeAlert(self, alert):
        if alert.location is None:
            return alert.description
        return '{}: {}'.format(alert.location, alert.description)

    def getSummary(self):
        """Returns a few sentences that describe the outcome of the analysis as a whole."""
        succeeded = [case for case in self.cases if case.simRes.success]
        failed = len(self.cases) - len(succeeded)
        summary = []
        if len(succeeded) > 0:
            maxPressure = succeeded[0].simRes.motor.config.getProperty('maxPressure')
            dispUnit = self.preferences.getUnit('Pa')
            limit = '{} {}'.format(self.formatValue(maxPressure, 'Pa'), dispUnit)
            peaks = [case.simRes.getMaxPressure() for case in succeeded]
            # An area multiplier can only be interpolated when the cases were spread over a range of them
            crossing = None
            if None not in [case.requestedMultiplier for case in succeeded]:
                crossing = getAreaMultiplierAtPressure(succeeded, maxPressure)
            if crossing is not None:
                text = 'Peak chamber pressure reaches the maximum allowed pressure of {} at an area multiplier of '
                text += 'about {:.2f}.'
                summary.append(text.format(limit, crossing))
            elif max(peaks) <= maxPressure:
                text = 'Peak chamber pressure stays below the maximum allowed pressure of {} in every case.'
                summary.append(text.format(limit))
            elif min(peaks) > maxPressure:
                text = 'Peak chamber pressure is above the maximum allowed pressure of {} in every case.'
                summary.append(text.format(limit))
            else:
                text = 'Peak chamber pressure is above the maximum allowed pressure of {} in {} of the {} cases '
                text += 'simulated.'
                summary.append(text.format(limit, len([peak for peak in peaks if peak > maxPressure]), len(peaks)))
        if failed > 0:
            text = '{} of the {} cases could not be simulated, which their alerts give the reason for.'
            summary.append(text.format(failed, len(self.cases)))
        summary.append('Select a case to step through how its grains burn, or double click it to see its full '
                       'results in the main window.')
        return ' '.join(summary)

    def getSelectedCase(self):
        rows = self.table.selectionModel().selectedRows()
        if len(rows) == 0:
            return None
        return self.cases[rows[0].row()]

    def selectionChanged(self):
        case = self.getSelectedCase()
        self.showButton.setEnabled(case is not None and case.simRes.success)
        self.loadGeometry()
        self.drawGraph()

    def getEndTime(self):
        """Returns the time that the slider ends at, which is a little after the longest burn of any case"""
        burnTimes = [case.simRes.getBurnTime() for case in self.cases if case.simRes.success]
        return max(burnTimes, default=0) + self.timeSliderMargin

    def setupTimeSlider(self):
        """Sets the time slider up to cover all of the cases, so it means the same time whichever is selected"""
        succeeded = [case for case in self.cases if case.simRes.success]
        self.timeSlider.blockSignals(True)
        self.timeSlider.setValue(0)
        if len(succeeded) > 0:
            self.timeStep = succeeded[0].simRes.motor.config.getProperty('timestep')
            self.timeSlider.setMaximum(int(np.ceil(self.getEndTime() / self.timeStep)))
        self.timeSlider.blockSignals(False)

    def loadGeometry(self):
        """Draws the grains of the selected case and sets the time slider up to step through its simulation"""
        case = self.getSelectedCase()
        self.geometryGrains = []
        if case is None or not case.simRes.success:
            self.timeSlider.setEnabled(False)
            self.timeLabel.setText('-')
            self.geometryWidget.showGrains([], [])
            return
        self.timeSlider.setEnabled(True)

        grains = case.simRes.motor.grains
        self.geometryGrains = [gid for gid, grain in enumerate(grains) if isinstance(grain, PerforatedGrain)]
        row = self.cases.index(case)
        if row not in self.geometryCache:
            # Generating the regression data of a grain replaces the geometry that it was simulated with, which the
            # main window still needs if the case is shown there, so it is generated from a copy
            self.geometryCache[row] = [copy.deepcopy(grains[gid]).getRegressionData(self.geometryMapDim,
                                                                                    coreBlack=False)
                                       for gid in self.geometryGrains]
        titles = []
        for gid in self.geometryGrains:
            titles.append('Grain {}{}'.format(gid + 1, ' (cracked)' if case.isCracked(gid) else ''))
        self.geometryWidget.showGrains(titles, self.geometryCache[row])
        self.timeChanged()

    def timeChanged(self, *_):
        """Redraws the grains of the selected case as they are at the time that the slider is set to"""
        case = self.getSelectedCase()
        if case is None or not case.simRes.success:
            return
        simRes = case.simRes
        time = self.timeSlider.value() * self.timeStep
        numPoints = len(simRes.channels['time'].getData())
        index = min(round(time / simRes.motor.config.getProperty('timestep')), numPoints - 1)
        # Nothing is left of any of the grains once the slider is past the end of the case's burn
        burnedOut = time > simRes.getBurnTime()
        burnoutThres = simRes.motor.config.getProperty('burnoutWebThres')
        mapDists = []
        for gid in self.geometryGrains:
            if not burnedOut and simRes.channels['web'].getPoint(index)[gid] > burnoutThres:
                radius = 0.5 * simRes.motor.grains[gid].props['diameter'].getValue()
                mapDists.append(simRes.channels['regression'].getPoint(index)[gid] / radius)
            else:
                mapDists.append(None)
        self.geometryWidget.setRegression(mapDists)

        self.timeLabel.setText('{:.2f} s'.format(time))
        if self.timeMarker is not None:
            self.timeMarker.set_xdata([time, time])
            self.canvas.draw_idle()

    def showSelected(self, *_):
        case = self.getSelectedCase()
        if case is not None and case.simRes.success:
            logger.log('Showing crack analysis case in main window')
            self.showRequested.emit(case.simRes)

    def drawGraph(self, *_):
        self.plot.clear()
        self.timeMarker = None
        succeeded = [case for case in self.cases if case.simRes.success]
        if len(succeeded) == 0 or self.channelSelector.currentIndex() == -1:
            self.canvas.draw()
            return

        channelName = self.plotChannels[self.channelSelector.currentIndex()]
        selected = self.getSelectedCase()
        for case in succeeded:
            channel = case.simRes.channels[channelName]
            dispUnit = self.preferences.getUnit(channel.unit)
            self.plot.plot(case.simRes.channels['time'].getData(), channel.getData(dispUnit),
                           label=self.getCaseName(case), linewidth=3 if case is selected else 1.5)
        if channelName == 'pressure':
            maxPressure = succeeded[0].simRes.motor.config.getProperty('maxPressure')
            self.plot.axhline(motorlib.units.convert(maxPressure, 'Pa', dispUnit), linestyle='--', color='red',
                              label='Maximum allowed')
        self.plot.legend()
        if selected is not None and selected.simRes.success:
            self.timeMarker = self.plot.axvline(self.timeSlider.value() * self.timeStep, linestyle=':', color='gray')
        # The time slider goes past the end of the data, and its marker has to stay on the graph when it does
        self.plot.set_xlim(right=self.timeSlider.maximum() * self.timeStep)
        self.plot.set_xlabel('Time - s')
        self.plot.set_ylabel(channel.name if dispUnit == '' else '{} - {}'.format(channel.name, dispUnit))
        self.plot.grid(True)
        self.figure.tight_layout()
        self.canvas.draw()

    def exportTable(self):
        path = QFileDialog.getSaveFileName(self, 'Export Crack Analysis', '', 'Comma separated value file (*.csv)')[0]
        if path == '' or path is None:
            return
        if not path.endswith('.csv'):
            path += '.csv'
        logger.log('Exporting crack analysis to "{}"'.format(path))
        with open(path, 'w', newline='') as outFile:
            writer = csv.writer(outFile)
            numCols = self.table.columnCount()
            writer.writerow([self.table.horizontalHeaderItem(col).text() for col in range(numCols)])
            for row in range(self.table.rowCount()):
                writer.writerow([self.table.item(row, col).text() for col in range(numCols)])
