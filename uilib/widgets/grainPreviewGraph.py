from itertools import cycle
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .. import theme

class GrainPreviewGraph(FigureCanvas):
    def __init__(self):
        super(GrainPreviewGraph, self).__init__(Figure())
        self.setParent(None)
        self.preferences = None

        self.image = None
        self.colorbar = None
        self.numContours = 0

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.figure.tight_layout()

        self.plot = self.figure.add_subplot(111)

    def setPreferences(self, pref):
        self.preferences = pref

    def setupImagePlot(self):
        self.figure.subplots_adjust(bottom=0.01, top=0.99, hspace=0)

        self.plot.xaxis.set_visible(False)
        self.plot.yaxis.set_visible(False)
        self.plot.axis('off')

    def setupGraphPlot(self):
        self.plot.set_xticklabels([])
        self.plot.set_yticklabels([])

    def cleanup(self):
        if self.colorbar is not None:
            self.colorbar.remove()
            self.colorbar = None
        if self.image is not None:
            self.image.remove()
            self.image = None
        if self.numContours > 0:
            for _ in range(0, self.numContours):
                self.plot.lines[0].remove()
            self.numContours = 0
        self.draw()

    def showImage(self, image):
        # Image is an array core is 0, any other value is propellant
        # Cast it to a bool so core is 0, propellant is 1
        np.ma.set_fill_value(image, 0)
        image = image.filled().astype(bool)

        # The core is the color of what is behind the graph so only the propellant stands out
        self.image = self.plot.imshow(theme.getImage(image, 'propellant', 'window'))

        self.draw()

    def showRegression(self, regressionMap, scale, unit, colormap):
        # Colors the propellant by how far it has to regress before it burns. The scale is the distance in the unit
        # passed in that a distance of one on the regression map is equal to.
        depth = np.ma.masked_less_equal(regressionMap * scale, 0)
        self.image = self.plot.imshow(depth, cmap=colormap, vmin=0)
        self.colorbar = self.figure.colorbar(self.image, ax=self.plot, fraction=0.046, pad=0.04)
        # There isn't room beside the colorbar for a label, so its unit goes above it
        self.colorbar.ax.set_title(unit, fontsize=8)
        self.colorbar.ax.tick_params(labelsize=8)
        self.draw()

    def showContours(self, contours):
        colorCycle = cycle(['r', 'g', 'b', 'y'])
        for contourSet in contours:
            color = next(colorCycle)
            for contour in contourSet:
                self.plot.plot(contour[:, 1], contour[:, 0], linewidth=1, c=color)
                self.numContours += 1
        self.draw()

    def showGraph(self, points):
        self.plot.plot(points[0], points[1])
        self.numContours += 1
        self.draw()

    def resetGraphBounds(self):
        self.plot.clear()
        self.setupGraphPlot()
