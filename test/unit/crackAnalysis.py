import unittest
import motorlib.grains
import motorlib.motor
from motorlib.crackAnalysis import CrackAnalysis, CrackCase, getAreaMultiplierAtPressure, getUnsupportedGrains


def makeMotor():
    grain = {
        'type': 'BATES',
        'properties': {'diameter': 0.083, 'length': 0.14, 'coreDiameter': 0.032, 'inhibitedEnds': 'Neither'}
    }
    return motorlib.motor.Motor({
        'nozzle': {'throat': 0.014, 'exit': 0.035, 'efficiency': 0.9, 'divAngle': 15, 'convAngle': 65,
                   'throatLength': 0.004, 'slagCoeff': 0, 'erosionCoeff': 0},
        'propellant': {
            'name': 'Cherry Limeade',
            'density': 1680,
            'tabs': [{'minPressure': 0, 'maxPressure': 2e7, 'a': 3.517e-05, 'n': 0.3273, 't': 3500, 'm': 23.67,
                      'k': 1.21}]
        },
        'grains': [grain, grain],
        'config': {'maxPressure': 1e7, 'maxMassFlux': 1400, 'maxMachNumber': 0.7, 'minPortThroat': 2,
                   'flowSeparationWarnPercent': 0.05, 'burnoutWebThres': 0.00025, 'burnoutThrustThres': 0.1,
                   'timestep': 0.03, 'ambPressure': 101325, 'mapDim': 400, 'sepPressureRatio': 0.4}
    })


# The distance from the core of the grains in the motor to their casting tubes
WEB = (0.083 - 0.032) / 2


class FakeSimRes:
    def __init__(self, maxPressure, success=True):
        self.maxPressure = maxPressure
        self.success = success

    def getMaxPressure(self):
        return self.maxPressure


class TestCrackAnalysis(unittest.TestCase):

    def test_getUnsupportedGrains(self):
        motor = makeMotor()
        motor.grains.append(motorlib.grains.EndBurningGrain())
        motor.grains.append(motorlib.grains.Finocyl())
        self.assertEqual(getUnsupportedGrains(motor, [0, 1, 2, 3]), [2])
        self.assertEqual(getUnsupportedGrains(motor, [0, 3]), [])

    def test_isCracked(self):
        case = CrackCase(None, {0: 2, 1: 0, 2: 3}, {0: 0.01, 1: 0, 2: 0}, None, None, None)
        self.assertTrue(case.isCracked())
        self.assertTrue(case.isCracked(0))
        self.assertFalse(case.isCracked(1))
        self.assertFalse(case.isCracked(2))
        self.assertFalse(case.isCracked(3))
        self.assertFalse(CrackCase(None, {0: 0}, {0: 0}, None, None, None).isCracked())

    def test_getCracksForAreaMultiplier(self):
        analysis = CrackAnalysis(makeMotor(), [1])
        area = analysis.getReferenceAreas()[1]
        self.assertAlmostEqual(area / makeMotor().grains[1].getSurfaceAreaAtRegression(0), 1, delta=0.02)

        self.assertEqual(analysis.getCracksForAreaMultiplier(1, 2), ({1: 0}, {1: 0}, []))

        numCracks, depths, notes = analysis.getCracksForAreaMultiplier(1.2, 2)
        self.assertEqual(numCracks, {1: 2})
        self.assertAlmostEqual(depths[1], 0.2 * area / (2 * 2 * 0.14))
        self.assertEqual(notes, [])

        numCracks, depths, notes = analysis.getCracksForAreaMultiplier(1.2, 4)
        self.assertEqual(numCracks, {1: 4})
        self.assertAlmostEqual(depths[1], 0.2 * area / (2 * 4 * 0.14))

    def test_getCracksForAreaMultiplierAddsCracks(self):
        analysis = CrackAnalysis(makeMotor(), [0, 1])
        area = analysis.getReferenceAreas()[0]
        # The depth of all of the cracks in a grain put together that it takes to double its burning area
        totalDepth = area / (2 * 0.14)
        self.assertGreater(totalDepth / 2, WEB)

        numCracks, depths, notes = analysis.getCracksForAreaMultiplier(2, 2)
        self.assertEqual(numCracks[0], numCracks[1])
        self.assertGreater(numCracks[0], 2)
        # It should be the fewest cracks that fit, not just any number of them that does
        self.assertLessEqual(totalDepth / numCracks[0], WEB + 0.0005)
        self.assertGreater(totalDepth / (numCracks[0] - 1), WEB - 0.0005)
        self.assertAlmostEqual(depths[0], totalDepth / numCracks[0])
        self.assertEqual(len(notes), 2)
        self.assertIn('Grain 1: {} cracks used'.format(numCracks[0]), notes[0])
        self.assertEqual(analysis.makeMotor(numCracks, depths, 0).grains[0].getGeometryErrors(), [])

    def test_getCracksForAreaMultiplierTooLarge(self):
        analysis = CrackAnalysis(makeMotor(), [0])
        # No number of cracks can add this much area, so the most that fit are used
        numCracks, depths, notes = analysis.getCracksForAreaMultiplier(100, 1)
        self.assertEqual(numCracks, {0: CrackAnalysis.maxCracks})
        self.assertAlmostEqual(depths[0], WEB, delta=0.0005)
        self.assertIn('Crack depth reduced', notes[-1])

    def test_getSpecifiedCracks(self):
        analysis = CrackAnalysis(makeMotor(), [0, 1])
        self.assertEqual(analysis.getSpecifiedCracks(3, 0.01), ({0: 3, 1: 3}, {0: 0.01, 1: 0.01}, []))

        numCracks, depths, notes = analysis.getSpecifiedCracks(3, 0.05)
        self.assertEqual(numCracks, {0: 3, 1: 3})
        for gid in (0, 1):
            self.assertAlmostEqual(depths[gid], WEB, delta=0.0005)
        self.assertEqual(len(notes), 2)
        self.assertIn('Grain 2: Crack depth reduced from 50.00 mm', notes[1])
        self.assertEqual(analysis.makeMotor(numCracks, depths, 0).grains[0].getGeometryErrors(), [])

    def test_getGeometry(self):
        analysis = CrackAnalysis(makeMotor(), [1])
        (face, regressionMap, contours, _), alerts = analysis.getGeometry({1: 2}, {1: 0.01})[1]
        self.assertEqual(alerts, [])
        self.assertEqual(face.shape, (300, 300))
        self.assertEqual(regressionMap.shape, (300, 300))
        self.assertEqual(len(contours), 8)
        # The cracks are part of the core, so there is less propellant in the face than there is without them
        uncracked = analysis.getGeometry(*analysis.getNoCracks())[1][0][0]
        self.assertLess(face.sum(), uncracked.sum())

        _, alerts = analysis.getGeometry({1: 2}, {1: 0.04})[1]
        self.assertEqual(len(alerts), 2)

        motor = makeMotor()
        motor.grains[1].setProperties({'coreDiameter': 0})
        regressionData, alerts = CrackAnalysis(motor, [1]).getGeometry({1: 2}, {1: 0.01})[1]
        self.assertIsNone(regressionData)
        self.assertEqual(len(alerts), 1)

    def test_runAreaMultiplierSweep(self):
        motor = makeMotor()
        baseline, cracked, moreCracks = CrackAnalysis(motor, [0, 1]).runAreaMultiplierSweep([1, 1.2, 2], 2)
        # The motor being analyzed must be left alone
        self.assertIsInstance(motor.grains[0], motorlib.grains.BatesGrain)

        self.assertTrue(baseline.simRes.success)
        self.assertFalse(baseline.isCracked())
        self.assertEqual(baseline.requestedMultiplier, 1)
        self.assertAlmostEqual(baseline.areaMultiplier, 1)
        # Without cracks, the results should line up with a normal simulation of the motor
        normal = motor.runSimulation()
        self.assertAlmostEqual(baseline.simRes.getMaxPressure() / normal.getMaxPressure(), 1, delta=0.02)
        self.assertAlmostEqual(baseline.simRes.getImpulse() / normal.getImpulse(), 1, delta=0.02)

        self.assertTrue(cracked.simRes.success)
        self.assertEqual(cracked.numCracks, {0: 2, 1: 2})
        self.assertEqual(cracked.notes, [])
        self.assertAlmostEqual(cracked.areaMultiplier, 1.2, delta=0.02)
        self.assertAlmostEqual(cracked.simRes.getInitialKN() / baseline.simRes.getInitialKN(), 1.2, delta=0.02)
        self.assertGreater(cracked.simRes.getMaxPressure(), 1.1 * baseline.simRes.getMaxPressure())
        # Cracks change when the propellant burns, not how much of it there is
        self.assertAlmostEqual(cracked.simRes.getImpulse() / baseline.simRes.getImpulse(), 1, delta=0.02)
        self.assertAlmostEqual(cracked.simRes.getPropellantMass() / baseline.simRes.getPropellantMass(), 1, delta=0.01)
        self.assertLess(cracked.caseExposureTime, 0.8 * baseline.caseExposureTime)

        # Two cracks can't double the burning area of the grains, so more of them are used to get there
        self.assertTrue(moreCracks.simRes.success)
        self.assertGreater(moreCracks.numCracks[0], 2)
        self.assertEqual(len(moreCracks.notes), 2)
        self.assertEqual(moreCracks.requestedMultiplier, 2)
        self.assertAlmostEqual(moreCracks.areaMultiplier, 2, delta=0.05)

    def test_runSpecifiedCracks(self):
        baseline, cracked = CrackAnalysis(makeMotor(), [1]).runSpecifiedCracks(3, 0.01, 30)
        self.assertFalse(baseline.isCracked())
        self.assertEqual(cracked.numCracks, {1: 3})
        self.assertEqual(cracked.depths, {1: 0.01})
        self.assertEqual(cracked.notes, [])
        self.assertIsNone(cracked.requestedMultiplier)
        self.assertIsInstance(cracked.simRes.motor.grains[0], motorlib.grains.BatesGrain)
        self.assertIsInstance(cracked.simRes.motor.grains[1], motorlib.grains.CrackedGrain)
        self.assertGreater(cracked.areaMultiplier, 1.3)
        self.assertGreater(cracked.simRes.getMaxPressure(), baseline.simRes.getMaxPressure())

    def test_runSpecifiedCracksTooDeep(self):
        _, cracked = CrackAnalysis(makeMotor(), [1]).runSpecifiedCracks(1, 0.05)
        # The crack is shortened to end at the casting tube, which the flame then reaches straight away
        self.assertTrue(cracked.simRes.success)
        self.assertAlmostEqual(cracked.depths[1], WEB, delta=0.0005)
        self.assertEqual(len(cracked.notes), 1)
        self.assertLess(cracked.caseExposureTime, 0.1)

    def test_cancel(self):
        progress = []

        def callback(prog):
            progress.append(prog)
            return prog > 0.25

        cases = CrackAnalysis(makeMotor(), [0]).runSpecifiedCracks(1, 0.01, callback=callback)
        self.assertEqual(len(cases), 1)
        self.assertFalse(cases[0].simRes.success)
        self.assertLess(max(progress), 0.5)

    def test_getAreaMultiplierAtPressure(self):
        cases = [CrackCase(FakeSimRes(pressure, success), {}, {}, multiplier, multiplier, None)
                 for multiplier, pressure, success in ((1.4, 8e6, True), (1, 4e6, True), (1.2, 6e6, True),
                                                       (1.1, 9e6, False))]
        self.assertAlmostEqual(getAreaMultiplierAtPressure(cases, 5e6), 1.1)
        self.assertAlmostEqual(getAreaMultiplierAtPressure(cases, 7.5e6), 1.35)
        self.assertIsNone(getAreaMultiplierAtPressure(cases, 3e6))
        self.assertIsNone(getAreaMultiplierAtPressure(cases, 9e6))


if __name__ == '__main__':
    unittest.main()
