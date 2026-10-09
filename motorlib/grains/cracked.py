"""Cracked grain submodule"""

import numpy as np

from ..grain import FmmGrain
from ..properties import FloatProperty, IntProperty
from ..simResult import SimAlert, SimAlertLevel, SimAlertType
from ..constants import maximumRefDiameter

class CrackedGrain(FmmGrain):
    """A cracked grain wraps another perforated grain and adds a number of evenly spaced radial cracks that start at
    the surface of its core and run the full length of the grain. The cracks are drawn onto the core map of the grain
    it wraps as slits that are as thin as the map allows, so they burn the same way as any other part of the core. It
    is not included in the grain type lookup table because it is only built to analyze a motor and is never saved."""
    geomName = 'Cracked'
    # Half of the width of the slit drawn for a crack in pixels, which is the least that always leaves a connected line
    crackHalfWidth = 0.75
    # The cracks can be checked for errors without the detail that simulation needs
    errorCheckMapDim = 501

    def __init__(self, baseGrain):
        super().__init__()
        self.baseGrain = baseGrain
        for prop in ('diameter', 'length', 'inhibitedEnds'):
            self.props[prop].setValue(baseGrain.props[prop].getValue())
        self.props['numCracks'] = IntProperty('Number of cracks', '', 0, 64)
        self.props['crackDepth'] = FloatProperty('Crack depth', 'm', 0, maximumRefDiameter)
        self.props['crackAngle'] = FloatProperty('First crack angle', 'deg', 0, 360)

    def getCrackPaths(self, coreMap):
        """Finds where each crack starts on a core map. The cracks follow rays cast from the centroid of the port, and
        each one starts where its ray first passes from the port into propellant. Returns a list with an entry for
        each crack, which is None if its ray never does this and otherwise a tuple of the point the crack starts at,
        the unit vector it extends along and the depth of the propellant along it, all in map coordinates."""
        mapDim = coreMap.shape[0]
        pitch = 2 / (mapDim - 1)
        mapX, mapY = np.meshgrid(np.linspace(-1, 1, mapDim), np.linspace(-1, 1, mapDim))
        mask = mapX**2 + mapY**2 > 1
        port = np.logical_and(coreMap == 0, np.logical_not(mask))
        numCracks = self.props['numCracks'].getValue()
        if not np.any(port):
            return [None] * numCracks
        origin = np.array([np.mean(mapX[port]), np.mean(mapY[port])])

        paths = []
        dists = np.arange(0, 2, pitch / 2)
        for i in range(numCracks):
            theta = np.radians(self.props['crackAngle'].getValue()) + (2 * np.pi * i / numCracks)
            direction = np.array([np.cos(theta), np.sin(theta)])
            # Sample the map along the ray, stopping where it leaves the grain
            cols = np.rint((origin[0] + dists * direction[0] + 1) / pitch).astype(int)
            rows = np.rint((origin[1] + dists * direction[1] + 1) / pitch).astype(int)
            inMap = (cols >= 0) & (cols < mapDim) & (rows >= 0) & (rows < mapDim)
            inGrain = np.zeros_like(inMap)
            inGrain[inMap] = np.logical_not(mask[rows[inMap], cols[inMap]])
            numSamples = len(dists) if np.all(inGrain) else np.argmin(inGrain)
            isPropellant = coreMap[rows[:numSamples], cols[:numSamples]] != 0
            starts = np.flatnonzero(np.logical_and(np.logical_not(isPropellant[:-1]), isPropellant[1:]))
            if len(starts) == 0:
                paths.append(None)
                continue
            start = starts[0]
            # The crack can be as deep as the unbroken run of propellant that follows the core surface
            pastStart = isPropellant[start + 1:]
            runLength = len(pastStart) if np.all(pastStart) else np.argmin(pastStart)
            paths.append((origin + dists[start] * direction, direction, dists[start + runLength] - dists[start]))
        return paths

    def getAvailableCrackDepth(self, coreMap=None):
        """Returns the depth of the shallowest web that any of the grain's cracks run into, which is the deepest that
        the cracks can be. Returns None if the grain has no cracks or any of them do not start on the surface of the
        core. The core map of the grain that is being cracked can be passed in to save generating it."""
        if coreMap is None:
            coreMap = np.ma.getdata(self.baseGrain.getFaceImage(self.errorCheckMapDim))
        paths = self.getCrackPaths(coreMap)
        if len(paths) == 0 or any(path is None for path in paths):
            return None
        return min(self.unNormalize(available) for _, _, available in paths)

    def generateCoreMap(self):
        self.coreMap = np.array(np.ma.getdata(self.baseGrain.getFaceImage(self.mapDim)), dtype=float)
        depth = self.normalize(self.props['crackDepth'].getValue())
        if depth == 0:
            return
        halfWidth = self.crackHalfWidth * 2 / (self.mapDim - 1)
        for path in self.getCrackPaths(self.coreMap):
            if path is None:
                continue
            start, direction, available = path
            # The slit begins inside of the port to make sure it is connected to it and has a rounded tip, which is
            # allowed for so the crack ends at the right depth
            begin = start - 2 * halfWidth * direction
            slitLength = max(min(depth, available) - halfWidth, 0) + 2 * halfWidth
            offX, offY = self.mapX - begin[0], self.mapY - begin[1]
            along = np.clip(offX * direction[0] + offY * direction[1], 0, slitLength)
            distSquared = (offX - along * direction[0])**2 + (offY - along * direction[1])**2
            self.coreMap[distSquared < halfWidth**2] = 0

    def getCorePerimeter(self, regDist):
        # The contour at the surface of the core follows the edges of pixels, which overstates its length by enough
        # to hide the effect of a small crack. The first few pixels of regression are instead extrapolated from
        # contours that are far enough from the surface to be smooth.
        near, far = 4 / self.mapDim, 8 / self.mapDim
        mapDist = self.normalize(regDist)
        if mapDist >= near:
            return super().getCorePerimeter(regDist)
        nearPerimeter = super().getCorePerimeter(self.unNormalize(near))
        farPerimeter = super().getCorePerimeter(self.unNormalize(far))
        return nearPerimeter + (mapDist - near) * (farPerimeter - nearPerimeter) / (far - near)

    def getCaseExposureRegression(self):
        """Returns the regression depth at which the burning surface first reaches the casting tube. The grain must
        have been set up for simulation before this is called."""
        pitch = 2 / (self.mapDim - 1)
        atWall = np.logical_and(self.mapX**2 + self.mapY**2 > (1 - 1.5 * pitch)**2, np.logical_not(self.mask))
        return self.unNormalize(np.amin(self.regressionMap[atWall]))

    def getDetailsString(self, lengthUnit='m'):
        return '{}, Cracks: {}'.format(self.baseGrain.getDetailsString(lengthUnit), self.props['numCracks'].getValue())

    def getGeometryErrors(self):
        errors = self.baseGrain.getGeometryErrors()
        numCracks = self.props['numCracks'].getValue()
        depth = self.props['crackDepth'].getValue()
        if numCracks == 0 or depth == 0 or SimAlertLevel.ERROR in [error.level for error in errors]:
            return errors

        face = self.baseGrain.getFaceImage(self.errorCheckMapDim)
        pitch = self.props['diameter'].getValue() / (self.errorCheckMapDim - 1)
        for crackId, path in enumerate(self.getCrackPaths(np.ma.getdata(face))):
            if path is None:
                aText = 'Crack {} does not pass from the core into propellant, try a different crack angle'
                aText = aText.format(crackId + 1)
                errors.append(SimAlert(SimAlertLevel.ERROR, SimAlertType.GEOMETRY, aText))
                continue
            available = self.unNormalize(path[2])
            if depth > available + pitch:
                aText = 'Crack {} is {:.2f} mm deep, but there is only {:.2f} mm of propellant along it'
                aText = aText.format(crackId + 1, depth * 1000, available * 1000)
                errors.append(SimAlert(SimAlertLevel.ERROR, SimAlertType.GEOMETRY, aText))
        return errors
