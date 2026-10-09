import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .. import theme

class CrackGeometryWidget(FigureCanvas):
    """Shows the cross sections of a number of grains side by side. They can either be colored by how far each part
    of them has to regress before it burns, or drawn as they are at any regression depth."""

    def __init__(self):
        super().__init__(Figure(layout='constrained'))
        self.setMinimumHeight(180)
        self.images = []
        self.regressionMaps = []

    def colorize(self, propellant):
        """Takes an array that is true where there is propellant and returns an image of it to draw"""
        # Anything that isn't propellant is the color of what is behind the graph, so only the propellant stands out
        return theme.getImage(np.ma.filled(propellant, False), 'propellant', 'window')

    def setupPlots(self, titles, regressionData):
        """Clears the figure and adds a plot to it for each of the titles passed in. Returns a list of tuples of the
        plots that have geometry to show and the regression map to show on them."""
        self.figure.clear()
        self.images = []
        self.regressionMaps = []
        if len(titles) == 0:
            return []

        plots = []
        for plot, title, data in zip(self.figure.subplots(1, len(titles), squeeze=False)[0], titles, regressionData):
            plot.axis('off')
            plot.set_title(title, fontsize=9)
            if data is None or data[1] is None:
                plot.text(0.5, 0.5, 'No geometry', ha='center', va='center', transform=plot.transAxes)
                self.regressionMaps.append(None)
            else:
                self.regressionMaps.append(data[1])
                plots.append((plot, data[1]))
        return plots

    def showGrains(self, titles, regressionData):
        """Draws a grain as it is before it burns for each of the titles passed in from the corresponding entry in
        regressionData, which is what its getRegressionData method returned when it was called with coreBlack set to
        false. An entry can be None for a grain that has no geometry to show."""
        plots = self.setupPlots(titles, regressionData)
        # There is an entry for every grain so the images line up with the regression that they are set to
        for regressionMap in self.regressionMaps:
            if regressionMap is None:
                self.images.append(None)
            else:
                plot, _ = plots.pop(0)
                self.images.append(plot.imshow(self.colorize(regressionMap > 0)))
        self.draw()

    def showRegression(self, titles, regressionData, scales, unit, colormap):
        """Draws a grain for each of the titles passed in like showGrains does, but with its propellant colored by
        how far it has to regress before it burns. The scale of a grain is the distance in the unit passed in that a
        distance of one on its regression map is equal to, and the colormap is the name of the one to use."""
        plots = self.setupPlots(titles, regressionData)
        if len(plots) == 0:
            self.draw()
            return
        scales = [scale for scale, regMap in zip(scales, self.regressionMaps) if regMap is not None]
        depths = [np.ma.masked_less_equal(regMap * scale, 0) for (_, regMap), scale in zip(plots, scales)]
        # The grains share a scale so the same color is the same depth in all of them
        maxDepth = max(depth.max() for depth in depths)
        for (plot, _), depth in zip(plots, depths):
            image = plot.imshow(depth, cmap=colormap, vmin=0, vmax=maxDepth)
        colorbar = self.figure.colorbar(image, ax=[plot for plot, _ in plots], orientation='horizontal', shrink=0.7,
                                        pad=0.03)
        colorbar.set_label('Regression Depth - {}'.format(unit))
        self.draw()

    def setRegression(self, mapDists):
        """Redraws the grains that were drawn by showGrains as they are after regressing by the distances passed in,
        which are in the units of the grains' regression maps. A distance of None shows a grain as burned out."""
        for image, regressionMap, mapDist in zip(self.images, self.regressionMaps, mapDists):
            if image is None:
                continue
            if mapDist is None:
                image.set_data(self.colorize(np.zeros(regressionMap.shape, dtype=bool)))
            else:
                image.set_data(self.colorize(regressionMap > mapDist))
        self.draw_idle()
