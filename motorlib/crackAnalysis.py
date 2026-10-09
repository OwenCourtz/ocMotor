"""Contains the tools used to find out how a motor behaves when some of its grains are cracked."""

import numpy as np

from .grain import PerforatedGrain
from .grains import CrackedGrain
from .motor import Motor
from .simResult import SimAlertLevel


class CrackCase:
    """The outcome of simulating a motor with a set of cracks in it. Along with the simulation result, it records the
    cracks that were simulated as dictionaries of grain ID to the number of cracks in that grain and their depth,
    along with notes on anything about them that was changed from what was asked for. It also holds the factor that
    the cracks multiplied the initial burning area of the cracked grains by, and the time at which the flame first
    reached the casting tube of a cracked grain. The requested multiplier is None unless the cracks were sized to
    reach a specific area multiplier, and the exposure time is None if the simulation did not get that far."""

    def __init__(self, simRes, numCracks, depths, areaMultiplier, requestedMultiplier, caseExposureTime, notes=None):
        self.simRes = simRes
        self.numCracks = numCracks
        self.depths = depths
        self.areaMultiplier = areaMultiplier
        self.requestedMultiplier = requestedMultiplier
        self.caseExposureTime = caseExposureTime
        self.notes = notes if notes is not None else []

    def isCracked(self, gid=None):
        """Returns if the grain with the ID passed in has cracks, or if any grain does when it is left out"""
        if gid is None:
            return any(self.isCracked(gid) for gid in self.numCracks)
        return self.numCracks.get(gid, 0) > 0 and self.depths.get(gid, 0) > 0


def getUnsupportedGrains(motor, grainIds):
    """Returns the IDs from the list passed in that belong to grains that cannot be cracked because they do not have
    a core for the cracks to start from."""
    return [gid for gid in grainIds if not isinstance(motor.grains[gid], PerforatedGrain)]


class CrackAnalysis:
    """Simulates a motor with radial cracks added to the grains with the IDs in grainIds, which must all be perforated
    grains. The motor that is passed in is not changed. Every simulation is run with the grains in question wrapped in
    CrackedGrains, even when they have no cracks, so results are compared without differences in how the geometry is
    calculated getting in the way. Wherever cracks are described, it is with a dictionary of grain ID to the number of
    cracks in that grain and another of grain ID to their depth."""

    # The most cracks that will be put into a grain to reach an area multiplier
    maxCracks = 64

    def __init__(self, motor, grainIds):
        self.motorDict = motor.getDict()
        self.grainIds = list(grainIds)
        # The initial burning area of each grain, which is found the first time it is needed as it requires
        # generating the grain's geometry
        self.referenceAreas = None

    def makeMotor(self, numCracks, depths, angle):
        """Returns a copy of the motor with the specified cracks in the grains being analyzed."""
        motor = Motor(self.motorDict)
        for gid in self.grainIds:
            motor.grains[gid] = CrackedGrain(motor.grains[gid])
            motor.grains[gid].setProperties({'numCracks': numCracks[gid], 'crackDepth': depths[gid],
                                             'crackAngle': angle})
        return motor

    def getNoCracks(self):
        """Returns the number of cracks and depths that describe a motor without any cracks in it"""
        return {gid: 0 for gid in self.grainIds}, {gid: 0 for gid in self.grainIds}

    def getReferenceAreas(self):
        """Returns a dictionary of grain ID to the initial burning area of that grain when it has no cracks in it.
        The area of a grain that can't be simulated is None."""
        if self.referenceAreas is None:
            referenceAreas = {}
            motor = self.makeMotor(*self.getNoCracks(), 0)
            for gid in self.grainIds:
                grain = motor.grains[gid]
                if SimAlertLevel.ERROR in [alert.level for alert in grain.getGeometryErrors()]:
                    referenceAreas[gid] = None
                    continue
                grain.simulationSetup(motor.config)
                referenceAreas[gid] = grain.getSurfaceAreaAtRegression(0)
            # Only stored once it is complete because previews can ask for it from more than one thread
            self.referenceAreas = referenceAreas
        return self.referenceAreas

    def limitDepths(self, numCracks, depths, angle=0):
        """Shortens any cracks that are deeper than the propellant that they run through, so that they end at the
        casting tube instead. Returns the depths with this done and a list of notes that describe what was changed.
        Cracks that don't start on the surface of the core are left as they are for the simulation to report."""
        motor = self.makeMotor(numCracks, depths, angle)
        limited = dict(depths)
        notes = []
        for gid in self.grainIds:
            grain = motor.grains[gid]
            if SimAlertLevel.ERROR in [alert.level for alert in grain.baseGrain.getGeometryErrors()]:
                continue
            if numCracks[gid] == 0 or depths[gid] == 0:
                continue
            available = grain.getAvailableCrackDepth()
            if available is not None and depths[gid] > available:
                limited[gid] = available
                note = 'Grain {}: Crack depth reduced from {:.2f} mm to the {:.2f} mm of propellant available'
                notes.append(note.format(gid + 1, depths[gid] * 1000, available * 1000))
        return limited, notes

    def getCracksForAreaMultiplier(self, areaMultiplier, minCracks, angle=0):
        """Works out the cracks that multiply the initial burning area of each grain by areaMultiplier. Both faces of
        a crack burn, so each one adds twice its depth times the length of the grain. Each grain is given minCracks
        cracks unless they would have to be deeper than the propellant they run through, in which case it is given
        as many as it takes for them to fit. Returns the number of cracks, their depths and a list of notes that
        describe anything that differs from what was asked for."""
        motor = Motor(self.motorDict)
        numCracks, depths = self.getNoCracks()
        notes = []
        for gid, area in self.getReferenceAreas().items():
            length = self.motorDict['grains'][gid]['properties']['length']
            if area is None or length == 0 or minCracks == 0 or areaMultiplier <= 1:
                continue
            # The depth of all of the grain's cracks added together
            totalDepth = (areaMultiplier - 1) * area / (2 * length)
            grain = CrackedGrain(motor.grains[gid])
            face = np.ma.getdata(motor.grains[gid].getFaceImage(CrackedGrain.errorCheckMapDim))
            # If no number of cracks fits, the one that gets the closest to the area is used
            mostDepth = 0
            numCracks[gid] = minCracks
            for candidate in range(minCracks, self.maxCracks + 1):
                grain.setProperties({'numCracks': candidate, 'crackAngle': angle})
                available = grain.getAvailableCrackDepth(face)
                if available is None:
                    continue
                if totalDepth / candidate <= available:
                    numCracks[gid] = candidate
                    break
                if candidate * available > mostDepth:
                    mostDepth = candidate * available
                    numCracks[gid] = candidate
            depths[gid] = totalDepth / numCracks[gid]
            if numCracks[gid] > minCracks:
                note = 'Grain {}: {} cracks used because {} would have to be deeper than the propellant available'
                notes.append(note.format(gid + 1, numCracks[gid], minCracks))
        depths, limitNotes = self.limitDepths(numCracks, depths, angle)
        return numCracks, depths, notes + limitNotes

    def getSpecifiedCracks(self, numCracks, depth, angle=0):
        """Works out the cracks that put numCracks cracks of the depth passed in into every grain, apart from where
        they are deeper than the propellant they run through and have to be shortened. Returns the number of cracks,
        their depths and a list of notes that describe anything that differs from what was asked for."""
        numCracks = {gid: numCracks for gid in self.grainIds}
        depths, notes = self.limitDepths(numCracks, {gid: depth for gid in self.grainIds}, angle)
        return numCracks, depths, notes

    def getGeometry(self, numCracks, depths, angle=0, mapDim=300):
        """Returns a dictionary of grain ID to the geometry of that grain with the specified cracks in it, as a tuple
        of what its getRegressionData method returns and a list of its geometry alerts. The regression data is None
        for a grain that has errors that aren't caused by its cracks, as it has no geometry to show."""
        motor = self.makeMotor(numCracks, depths, angle)
        geometry = {}
        for gid in self.grainIds:
            grain = motor.grains[gid]
            alerts = grain.getGeometryErrors()
            if SimAlertLevel.ERROR in [alert.level for alert in grain.baseGrain.getGeometryErrors()]:
                geometry[gid] = (None, alerts)
            else:
                geometry[gid] = (grain.getRegressionData(mapDim, numContours=8, coreBlack=False), alerts)
        return geometry

    def run(self, numCracks, depths, angle=0, requestedMultiplier=None, callback=None, notes=None):
        """Simulates the motor with the specified cracks and returns a CrackCase. The callback is passed on to the
        simulation."""
        motor = self.makeMotor(numCracks, depths, angle)
        simRes = motor.runSimulation(callback)

        areaMultiplier, caseExposureTime = None, None
        referenceAreas = self.getReferenceAreas()
        # The grains only have their geometry if the simulation got past checking for errors
        if len(simRes.channels['time'].getData()) > 0 and None not in referenceAreas.values():
            crackedArea = sum(motor.grains[gid].getSurfaceAreaAtRegression(0) for gid in self.grainIds)
            areaMultiplier = crackedArea / sum(referenceAreas.values())
            # A grain stops regressing when it is within the burnout threshold of burning out, so the casting tube
            # is considered exposed when the flame is that close to it
            burnoutThres = motor.config.getProperty('burnoutWebThres')
            exposureRegs = {gid: motor.grains[gid].getCaseExposureRegression() - burnoutThres for gid in self.grainIds}
            for regression, time in zip(simRes.channels['regression'].getData(), simRes.channels['time'].getData()):
                if any(regression[gid] >= exposureRegs[gid] for gid in self.grainIds):
                    caseExposureTime = time
                    break

        return CrackCase(simRes, numCracks, depths, areaMultiplier, requestedMultiplier, caseExposureTime, notes)

    def runSpecifiedCracks(self, numCracks, depth, angle=0, callback=None):
        """Simulates the motor without cracks and then with numCracks cracks of the specified depth in each of the
        grains being analyzed, and returns a CrackCase for each. Cracks that are deeper than the propellant they run
        through are shortened to fit. The callback is called with the progress through both simulations, and they
        are abandoned if it returns True."""
        specs = [(*self.getNoCracks(), [], None), (*self.getSpecifiedCracks(numCracks, depth, angle), None)]
        return self._runAll(specs, angle, callback)

    def runAreaMultiplierSweep(self, areaMultipliers, minCracks, angle=0, callback=None):
        """Simulates the motor once for each of the area multipliers passed in, with cracks in each of the grains
        being analyzed that are just deep enough to multiply its initial burning area by that amount. Each grain has
        at least minCracks cracks, and more if that is what it takes to reach the area. Returns a CrackCase for each
        multiplier. The callback is called with the progress through all of the simulations, and they are abandoned
        if it returns True."""
        specs = [(*self.getCracksForAreaMultiplier(multiplier, minCracks, angle), multiplier)
                 for multiplier in areaMultipliers]
        return self._runAll(specs, angle, callback)

    def _runAll(self, specs, angle, callback):
        cases = []
        canceled = False

        for caseId, (numCracks, depths, notes, multiplier) in enumerate(specs):
            def caseCallback(progress, caseId=caseId):
                nonlocal canceled
                if callback is not None:
                    canceled = bool(callback((caseId + progress) / len(specs))) or canceled
                return canceled

            cases.append(self.run(numCracks, depths, angle, multiplier, caseCallback, notes))
            if canceled:
                break
        return cases


def getAreaMultiplierAtPressure(cases, pressure):
    """Estimates the area multiplier at which the peak chamber pressure of a cracked motor reaches the pressure passed
    in by interpolating between the cases supplied. Returns None if the cases do not straddle the pressure."""
    points = [(case.areaMultiplier, case.simRes.getMaxPressure()) for case in cases
              if case.simRes.success and case.areaMultiplier is not None]
    points.sort()
    for (lowMult, lowPres), (highMult, highPres) in zip(points[:-1], points[1:]):
        if lowPres <= pressure < highPres:
            return lowMult + (highMult - lowMult) * (pressure - lowPres) / (highPres - lowPres)
    return None
