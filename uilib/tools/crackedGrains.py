from threading import Thread

import numpy as np
from PyQt6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSlider
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

import motorlib
from motorlib.crackAnalysis import CrackAnalysis, getUnsupportedGrains

from ..tool import Tool
from ..logger import logger
from ..widgets.collectionEditor import CollectionEditor
from ..widgets.grainSelector import GrainSelector
from ..widgets.crackGeometryWidget import CrackGeometryWidget
from ..widgets.crackResultsDialog import CrackResultsDialog


class CrackedGrainsTool(Tool):
    SWEEP_MODE = 'Sweep area multiplier'
    SPECIFIED_MODE = 'Specify cracks'

    # Emitted from the thread that generates the preview with the number of the request it is for and a dictionary
    # of what to show
    previewReady = pyqtSignal(int, object)

    def __init__(self, manager):
        super().__init__(manager,
                         'Cracked Grains',
                         'Use this tool to see how the motor would behave if some of its grains were cracked. Cracks '
                         'run radially out from the core for the full length of the grain and are evenly spaced '
                         'around it. They can either be specified directly, or sized automatically to multiply the '
                         'initial burning area of each cracked grain by a range of values. Cracks that are too deep '
                         'to fit in a grain are shortened, and cracks are added to a grain if it needs more of them '
                         'to reach an area multiplier.',
                         {},
                         False)

        # Each mode has its own set of properties, which are swapped into the editor when the mode is changed
        self.collections = {self.SWEEP_MODE: motorlib.properties.PropertyCollection(),
                            self.SPECIFIED_MODE: motorlib.properties.PropertyCollection()}
        self.collections[self.SWEEP_MODE].props = {
            'startMultiplier': motorlib.properties.FloatProperty('Starting area multiplier', '', 1, 10),
            'endMultiplier': motorlib.properties.FloatProperty('Ending area multiplier', '', 1, 10),
            'numPoints': motorlib.properties.IntProperty('Number of points', '', 2, 50),
            'numCracks': motorlib.properties.IntProperty('Minimum cracks per grain', '', 1, 64),
            'crackAngle': motorlib.properties.FloatProperty('First crack angle', 'deg', 0, 360)
        }
        self.collections[self.SWEEP_MODE].setProperties({'endMultiplier': 1.5, 'numPoints': 6})
        self.collections[self.SPECIFIED_MODE].props = {
            'numCracks': motorlib.properties.IntProperty('Cracks per grain', '', 1, 64),
            'crackDepth': motorlib.properties.FloatProperty('Crack depth', 'm', 0,
                                                            motorlib.constants.maximumRefDiameter),
            'crackAngle': motorlib.properties.FloatProperty('First crack angle', 'deg', 0, 360)
        }
        self.shownCollection = None
        # Set while the tool is waiting on the simulation manager to finish its analysis
        self.running = False

        # The editor that the base class builds applies a change to the motor, which this tool never does
        self.layout().removeWidget(self.editor)
        self.editor.deleteLater()

        self.modeSelector = QComboBox()
        self.modeSelector.addItems(self.collections.keys())
        self.modeSelector.currentTextChanged.connect(self.modeChanged)

        self.editor = CollectionEditor(self, False)

        self.grainSelector = GrainSelector(self)
        self.grainSelector.setTitle('Cracked grains')
        self.grainSelector.checksChanged.connect(self.schedulePreview)

        # The preview is generated in another thread a moment after the last change that was made, and anything
        # that comes back from a request that isn't the latest one is ignored
        self.previewRequest = 0
        self.previewData = None
        self.previewAnalysis = None
        self.previewKey = None
        self.previewTimer = QTimer(self)
        self.previewTimer.setSingleShot(True)
        self.previewTimer.timeout.connect(self.updatePreview)
        self.previewReady.connect(self.showPreview)

        self.pointLabel = QLabel('Sweep point to preview:')
        self.pointSlider = QSlider(Qt.Orientation.Horizontal)
        self.pointSlider.setPageStep(1)
        # Starting with no range puts the slider at its end, so it moves to the last point when the range is set
        self.pointSlider.setRange(0, 0)
        self.pointSlider.valueChanged.connect(self.schedulePreview)
        self.previewWidget = CrackGeometryWidget()
        self.previewWidget.setMinimumSize(420, 260)
        # There can be a note for every grain, so they get a box that scrolls instead of crowding out the preview
        self.previewLabel = QPlainTextEdit()
        self.previewLabel.setReadOnly(True)
        self.previewLabel.setFixedHeight(80)

        inputs = QVBoxLayout()
        inputs.addWidget(self.modeSelector)
        inputs.addWidget(self.editor)
        inputs.addWidget(self.grainSelector)
        pointLayout = QHBoxLayout()
        pointLayout.addWidget(self.pointLabel)
        pointLayout.addWidget(self.pointSlider)
        preview = QVBoxLayout()
        preview.addLayout(pointLayout)
        preview.addWidget(self.previewWidget, 1)
        preview.addWidget(self.previewLabel)
        columns = QHBoxLayout()
        columns.addLayout(inputs)
        columns.addLayout(preview, 1)
        self.layout().addLayout(columns)

        self.runButton = QPushButton('Run')
        self.runButton.pressed.connect(self.runPressed)
        self.closeButton = QPushButton('Close')
        self.closeButton.pressed.connect(self.hide)
        buttons = QHBoxLayout()
        buttons.addWidget(self.runButton)
        buttons.addWidget(self.closeButton)
        self.layout().addLayout(buttons)

        self.resultsDialog = CrackResultsDialog()
        self.resultsDialog.showRequested.connect(self.manager.simulationManager.newSimulationResult.emit)
        self.manager.simulationManager.taskDone.connect(self.taskDone)

    def setPreferences(self, pref):
        super().setPreferences(pref)
        self.resultsDialog.setPreferences(pref)
        # The colormap might have changed
        self.drawPreview()

    def show(self):
        logger.log('Showing "{}" tool'.format(self.name))
        self.grainSelector.resetChecks()
        self.grainSelector.setupChecks(len(self.manager.getMotor().grains), True)
        self.loadCollection(self.collections[self.modeSelector.currentText()])
        super(Tool, self).show()
        self.updatePreview()

    def loadCollection(self, collection):
        self.shownCollection = collection
        self.editor.loadProperties(collection)
        for propEditor in self.editor.propertyEditors.values():
            propEditor.valueChanged.connect(self.schedulePreview)
        isSweep = self.modeSelector.currentText() == self.SWEEP_MODE
        self.pointLabel.setVisible(isSweep)
        self.pointSlider.setVisible(isSweep)

    def storeProperties(self):
        """Saves what has been entered into the editor so it is still there when the mode is shown again"""
        if self.shownCollection is not None:
            self.shownCollection.setProperties(self.editor.getProperties())

    def modeChanged(self, mode):
        self.storeProperties()
        self.loadCollection(self.collections[mode])
        self.schedulePreview()

    def getSupportedGrains(self, motor):
        """Returns the IDs of the grains that are selected to be cracked and are able to be"""
        grainIds = self.grainSelector.getSelectedGrains()
        unsupported = getUnsupportedGrains(motor, grainIds)
        return [gid for gid in grainIds if gid not in unsupported]

    def schedulePreview(self, *_):
        self.previewTimer.start(250)

    def updatePreview(self):
        """Starts generating a preview of the cracks that the tool would currently simulate"""
        if not self.isVisible():
            return
        self.storeProperties()
        props = self.shownCollection.getProperties()
        isSweep = self.modeSelector.currentText() == self.SWEEP_MODE
        if isSweep:
            # The deepest cracks are the ones worth checking, so the slider stays on the last point if it was there
            wasAtEnd = self.pointSlider.value() == self.pointSlider.maximum()
            self.pointSlider.blockSignals(True)
            self.pointSlider.setRange(0, props['numPoints'] - 1)
            if wasAtEnd:
                self.pointSlider.setValue(props['numPoints'] - 1)
            self.pointSlider.blockSignals(False)

        motor = self.manager.getMotor()
        grainIds = self.getSupportedGrains(motor)
        self.previewRequest += 1
        if len(grainIds) == 0:
            self.showPreview(self.previewRequest, {'text': 'Select a grain with a core to preview its cracks.'})
            return
        # Working out the area of the grains is slow, so the analysis is kept until the motor or grains change
        previewKey = (motor.getDict(), grainIds)
        if previewKey != self.previewKey:
            self.previewAnalysis = CrackAnalysis(motor, grainIds)
            self.previewKey = previewKey
        args = [self.previewRequest, self.previewAnalysis, isSweep, props, self.pointSlider.value()]
        Thread(target=self._generatePreview, args=args).start()

    def _generatePreview(self, request, analysis, isSweep, props, point):
        try:
            if isSweep:
                multiplier = np.linspace(props['startMultiplier'], props['endMultiplier'], props['numPoints'])[point]
                cracks = analysis.getCracksForAreaMultiplier(multiplier, props['numCracks'], props['crackAngle'])
                text = 'Point {} of {}, area multiplier {:.3f}.'.format(point + 1, props['numPoints'], multiplier)
            else:
                cracks = analysis.getSpecifiedCracks(props['numCracks'], props['crackDepth'], props['crackAngle'])
                text = 'Specified cracks.'
            numCracks, depths, notes = cracks
            geometry = analysis.getGeometry(numCracks, depths, props['crackAngle'])

            lengthUnit = self.preferences.getUnit('m')
            preview = {'titles': [], 'regressionData': [], 'scales': [], 'unit': lengthUnit}
            for gid in analysis.grainIds:
                if numCracks[gid] > 0 and depths[gid] > 0:
                    depth = motorlib.units.convert(depths[gid], 'm', lengthUnit)
                    cracksText = '{} crack{}\n{:.3f} {} deep'.format(numCracks[gid], 's' if numCracks[gid] > 1 else '',
                                                                     depth, lengthUnit)
                else:
                    cracksText = 'No cracks'
                preview['titles'].append('Grain {}\n{}'.format(gid + 1, cracksText))
                preview['regressionData'].append(geometry[gid][0])
                # A distance of one on a grain's regression map is its radius
                radius = analysis.motorDict['grains'][gid]['properties']['diameter'] / 2
                preview['scales'].append(motorlib.units.convert(radius, 'm', lengthUnit))
                notes += ['Grain {}: {}'.format(gid + 1, alert.description) for alert in geometry[gid][1]]
            preview['text'] = '\n'.join([text] + notes)
            self.previewReady.emit(request, preview)
        except Exception as exc:
            self.previewReady.emit(request, {'text': 'The preview could not be generated: {}'.format(exc)})

    def showPreview(self, request, preview):
        if request != self.previewRequest:
            return
        self.previewData = preview
        self.previewLabel.setPlainText(preview['text'])
        self.drawPreview()

    def drawPreview(self, *_):
        """Draws the last preview that was generated, which also happens when the preferences are changed"""
        if self.previewData is None:
            return
        self.previewWidget.showRegression(self.previewData.get('titles', []),
                                          self.previewData.get('regressionData', []),
                                          self.previewData.get('scales', []), self.previewData.get('unit', ''),
                                          self.preferences.getColormap())

    def runPressed(self):
        self.storeProperties()
        app = QApplication.instance()
        motor = self.manager.getMotor()
        grainIds = self.grainSelector.getSelectedGrains()
        if len(grainIds) == 0:
            app.outputMessage('At least one grain must be selected to be cracked.')
            return
        unsupported = getUnsupportedGrains(motor, grainIds)
        if len(unsupported) > 0:
            grainNames = ', '.join(str(gid + 1) for gid in unsupported)
            app.outputMessage('Only grains with a core can be cracked, which rules out grain(s) {}.'.format(grainNames))
            return

        props = self.shownCollection.getProperties()
        analysis = CrackAnalysis(motor, grainIds)
        if self.modeSelector.currentText() == self.SWEEP_MODE:
            if props['endMultiplier'] < props['startMultiplier']:
                app.outputMessage('The ending area multiplier must not be less than the starting area multiplier.')
                return
            multipliers = np.linspace(props['startMultiplier'], props['endMultiplier'], props['numPoints'])

            def run(callback):
                return analysis.runAreaMultiplierSweep(multipliers, props['numCracks'], props['crackAngle'], callback)
        else:
            def run(callback):
                return analysis.runSpecifiedCracks(props['numCracks'], props['crackDepth'], props['crackAngle'],
                                                   callback)

        def task(callback):
            # This runs outside of the UI thread, so anything that goes wrong is handed back to be reported there
            try:
                return run(callback)
            except Exception as exc:
                return exc

        logger.log('Running crack analysis ({}) with {} on grain(s) {}'.format(self.modeSelector.currentText(), props,
                                                                              [gid + 1 for gid in grainIds]))
        self.running = True
        self.manager.simulationManager.runTask(task)

    def taskDone(self, result):
        if not self.running:
            return
        self.running = False
        if isinstance(result, Exception):
            QApplication.instance().outputException(result, 'An error occurred while running the crack analysis:')
            return
        self.resultsDialog.showCases(result)

    def simCanceled(self):
        self.running = False
        super().simCanceled()
