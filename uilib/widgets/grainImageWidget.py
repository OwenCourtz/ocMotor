from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QImage
import numpy as np

from .. import theme

class GrainImageWidget(QLabel):
    def showImage(self, image):
        np.ma.set_fill_value(image, 0)
        # The images are shown in a table, so anything that isn't propellant is the color of the table's cells
        image = np.where(image.filled(), theme.getGrayLevel('propellant'), theme.getGrayLevel('base')).astype(np.uint8)
        image = np.ascontiguousarray(image)
        height, width = image.shape

        qImg = QImage(image.data, width, height, QImage.Format.Format_Grayscale8)
        pixmap = QPixmap(qImg)
        self.setPixmap(pixmap)
