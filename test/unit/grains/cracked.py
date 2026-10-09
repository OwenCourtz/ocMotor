import unittest
import motorlib.grains
import motorlib.motor
from motorlib.simResult import SimAlertLevel, SimAlertType


class CrackedGrainMethods(unittest.TestCase):

    def setUp(self):
        self.config = motorlib.motor.MotorConfig()
        self.config.setProperties({'mapDim': 500})
        self.base = motorlib.grains.BatesGrain()
        self.base.setProperties({
            'length': 0.14,
            'diameter': 0.083,
            'coreDiameter': 0.032,
            'inhibitedEnds': 'Both'
        })
        self.base.simulationSetup(self.config)

    def makeGrain(self, numCracks, depth, angle=0):
        grain = motorlib.grains.CrackedGrain(self.base)
        grain.setProperties({'numCracks': numCracks, 'crackDepth': depth, 'crackAngle': angle})
        return grain

    def test_copiesBaseProperties(self):
        grain = self.makeGrain(2, 0.01)
        self.assertEqual(grain.getProperty('length'), 0.14)
        self.assertEqual(grain.getProperty('diameter'), 0.083)
        self.assertEqual(grain.getProperty('inhibitedEnds'), 'Both')

    def test_getDetailsString(self):
        grain = self.makeGrain(2, 0.01)
        self.assertEqual(grain.getDetailsString(), 'Length: 0.14 m, Core: 0.032 m, Cracks: 2')

    def test_noCracksMatchesBase(self):
        grain = self.makeGrain(0, 0)
        grain.simulationSetup(self.config)
        for reg in (0, 0.005, 0.02):
            self.assertAlmostEqual(grain.getSurfaceAreaAtRegression(reg) / self.base.getSurfaceAreaAtRegression(reg),
                                   1, delta=0.02)
            self.assertAlmostEqual(grain.getVolumeAtRegression(reg) / self.base.getVolumeAtRegression(reg),
                                   1, delta=0.02)
        self.assertAlmostEqual(grain.getCaseExposureRegression(), self.base.wallWeb, delta=0.0005)

    def test_cracksAddArea(self):
        uncracked = self.makeGrain(0, 0)
        uncracked.simulationSetup(self.config)
        for numCracks, depth in ((1, 0.015), (4, 0.008)):
            grain = self.makeGrain(numCracks, depth)
            grain.simulationSetup(self.config)
            # Both faces of each crack burn
            expected = 2 * numCracks * depth * 0.14
            added = grain.getSurfaceAreaAtRegression(0) - uncracked.getSurfaceAreaAtRegression(0)
            self.assertAlmostEqual(added / expected, 1, delta=0.1)
            # The cracks are too thin to remove a meaningful amount of propellant
            self.assertAlmostEqual(grain.getVolumeAtRegression(0) / uncracked.getVolumeAtRegression(0), 1, delta=0.01)
            # A crack doesn't change how far the flame has to go to burn out the grain, just to reach the case
            self.assertAlmostEqual(grain.wallWeb, self.base.wallWeb, delta=0.0005)
            self.assertAlmostEqual(grain.getCaseExposureRegression(), self.base.wallWeb - depth, delta=0.0005)

    def test_cracksLoseAreaAfterReachingCase(self):
        uncracked = self.makeGrain(0, 0)
        uncracked.simulationSetup(self.config)
        grain = self.makeGrain(1, 0.015)
        grain.simulationSetup(self.config)
        self.assertGreater(grain.getSurfaceAreaAtRegression(0.005), uncracked.getSurfaceAreaAtRegression(0.005))
        self.assertLess(grain.getSurfaceAreaAtRegression(0.02), uncracked.getSurfaceAreaAtRegression(0.02))

    def test_getAvailableCrackDepth(self):
        self.assertAlmostEqual(self.makeGrain(3, 0.01).getAvailableCrackDepth(), self.base.wallWeb, delta=0.0005)
        self.assertIsNone(self.makeGrain(0, 0).getAvailableCrackDepth())

    def test_getGeometryErrors(self):
        self.assertEqual(self.makeGrain(0, 0).getGeometryErrors(), [])
        self.assertEqual(self.makeGrain(3, 0.01).getGeometryErrors(), [])
        self.assertEqual(self.makeGrain(1, self.base.wallWeb).getGeometryErrors(), [])

        errors = self.makeGrain(2, 0.04).getGeometryErrors()
        self.assertEqual(len(errors), 2)
        for error in errors:
            self.assertEqual(error.level, SimAlertLevel.ERROR)
            self.assertEqual(error.type, SimAlertType.GEOMETRY)
        self.assertIn('Crack 1 is 40.00 mm deep', errors[0].description)

        self.base.setProperties({'coreDiameter': 0})
        errors = self.makeGrain(2, 0.01).getGeometryErrors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].description, 'Core diameter must not be 0')


if __name__ == '__main__':
    unittest.main()
