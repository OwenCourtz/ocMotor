"""Defines how the application looks. Everything that decides on a color or a style for the UI or its graphs should
get it from here, so that the look of the application is set in one place."""

import matplotlib as mpl
import numpy as np
from cycler import cycler
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.colors import to_hex

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

# The color that the application's highlights are based around unless the user picks another
DEFAULT_ACCENT = '#701033'

# The themes that the user can choose from. The system theme is light or dark to match the operating system.
SYSTEM_THEME, LIGHT_THEME, DARK_THEME = 'System', 'Light', 'Dark'
THEMES = [SYSTEM_THEME, LIGHT_THEME, DARK_THEME]

# The colors of the UI that don't depend on the accent, by whether dark mode is in use. The window color is what sits
# behind everything, and the base color is what is behind anything that is edited or drawn on, like a text box or the
# axes of a graph.
NEUTRALS = {
    False: {
        'window': '#f0f0f0',
        'base': '#ffffff',
        'alternateBase': '#f6f6f6',
        'button': '#f0f0f0',
        'text': '#1f1f1f',
        'mutedText': '#5c5c5c',
        'disabledText': '#a0a0a0',
        'grid': '#d9d9d9',
        'axes': '#8c8c8c',
        'lines': ['#1f6f8b', '#c9892b', '#3a7d44', '#5b4b8a', '#7a7a7a', '#b5524a', '#2a9d8f'],
        'propellant': '#2d2d2d',
    },
    True: {
        'window': '#2b2b2b',
        'base': '#1e1e1e',
        'alternateBase': '#252525',
        'button': '#353535',
        'text': '#e6e6e6',
        'mutedText': '#a8a8a8',
        'disabledText': '#7a7a7a',
        'grid': '#3d3d3d',
        'axes': '#8c8c8c',
        'lines': ['#5fb3ce', '#e3b05a', '#7cc48a', '#a493d6', '#b0b0b0', '#e08b84', '#63cdbf'],
        'propellant': '#c0c0c0',
    }
}

darkMode = False
colors = dict(NEUTRALS[False])


def parseColor(name):
    """Returns the color that a string like '#rrggbb' describes, with or without the '#'. The color is not valid if
    the string is empty or doesn't describe a color, which can be checked with its isValid method."""
    name = (name or '').strip()
    if len(name) in (3, 6) and all(char in '0123456789abcdefABCDEF' for char in name):
        name = '#' + name
    return QColor(name) if name != '' else QColor()


def getColors(dark, accent, window='', base=''):
    """Returns a dictionary of all of the colors of a theme, as strings like '#rrggbb'. The colors that highlight
    things are worked out from the accent color passed in, which is replaced by the default if it isn't valid. The
    window and base colors of the theme are replaced by the ones passed in if they are valid colors, and the colors
    that go with them are worked out again to suit."""
    accentColor = parseColor(accent)
    if not accentColor.isValid():
        accentColor = QColor(DEFAULT_ACCENT)
    hue, saturation, lightness, _ = accentColor.getHslF()
    themeColors = dict(NEUTRALS[dark])

    windowColor, baseColor = parseColor(window), parseColor(base)
    if windowColor.isValid():
        themeColors['window'] = windowColor.name()
        # Buttons have to stand out a little from a dark window, but look right matching a light one
        isDark = windowColor.lightnessF() < 0.5
        themeColors['button'] = windowColor.lighter(125).name() if isDark else windowColor.name()
    if baseColor.isValid():
        themeColors['base'] = baseColor.name()
        if baseColor.lightnessF() < 0.5:
            themeColors['alternateBase'] = baseColor.lighter(120).name()
            themeColors['grid'] = baseColor.lighter(190).name()
        else:
            themeColors['alternateBase'] = baseColor.darker(104).name()
            themeColors['grid'] = baseColor.darker(118).name()
    # Whatever is drawn on top of a background is taken from whichever of the light and dark themes has a background
    # like it, so it can still be seen if the background was replaced with one that doesn't match the theme
    windowIsDark = QColor(themeColors['window']).lightnessF() < 0.5
    baseIsDark = QColor(themeColors['base']).lightnessF() < 0.5
    themeColors['windowText'] = NEUTRALS[windowIsDark]['text']
    themeColors['mutedText'] = NEUTRALS[windowIsDark]['mutedText']
    themeColors['propellant'] = NEUTRALS[windowIsDark]['propellant']
    themeColors['buttonText'] = NEUTRALS[QColor(themeColors['button']).lightnessF() < 0.5]['text']
    themeColors['baseText'] = NEUTRALS[baseIsDark]['text']
    themeColors['lines'] = NEUTRALS[baseIsDark]['lines']
    if baseIsDark:
        # A dark accent can't be seen against a dark background, so lighter versions of it stand in where needed
        highlight = QColor.fromHslF(hue, saturation, max(lightness, 0.32))
        line = QColor.fromHslF(hue, min(saturation, 0.55), max(lightness, 0.61))
    else:
        highlight = accentColor
        line = QColor.fromHslF(hue, saturation, min(lightness, 0.45))
    themeColors['highlight'] = highlight.name()
    # Whichever of black and white is easier to read on top of the highlight
    themeColors['highlightedText'] = '#ffffff' if highlight.lightnessF() < 0.6 else '#000000'
    themeColors['link'] = line.name()
    # The accent is first so anything with a single line on it is drawn in it
    themeColors['lines'] = [line.name()] + themeColors['lines']
    return themeColors


def getColor(name):
    """Returns one of the colors of the theme that is in use, as a string like '#rrggbb'"""
    return colors[name]


def getRGB(name):
    """Returns one of the colors of the theme that is in use as a tuple of its red, green and blue from 0 to 255,
    which is what is needed to build an image out of it"""
    color = QColor(getColor(name))
    return color.red(), color.green(), color.blue()


def getImage(mask, trueColor, falseColor):
    """Returns an RGB image that has one of the theme's colors wherever the array passed in is true and another
    wherever it is false"""
    image = np.empty(mask.shape + (3, ), dtype=np.uint8)
    image[...] = getRGB(falseColor)
    image[mask] = getRGB(trueColor)
    return image


def getPalette():
    """Returns the palette that the application's widgets are drawn with"""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: 'window',
        QPalette.ColorRole.WindowText: 'windowText',
        QPalette.ColorRole.Base: 'base',
        QPalette.ColorRole.AlternateBase: 'alternateBase',
        QPalette.ColorRole.ToolTipBase: 'base',
        QPalette.ColorRole.ToolTipText: 'baseText',
        QPalette.ColorRole.Text: 'baseText',
        QPalette.ColorRole.Button: 'button',
        QPalette.ColorRole.ButtonText: 'buttonText',
        QPalette.ColorRole.BrightText: 'highlightedText',
        QPalette.ColorRole.Highlight: 'highlight',
        QPalette.ColorRole.HighlightedText: 'highlightedText',
        QPalette.ColorRole.Link: 'link',
        QPalette.ColorRole.PlaceholderText: 'disabledText',
    }
    for role, name in roles.items():
        palette.setColor(role, QColor(getColor(name)))
    # The shades that frames and separators are drawn with, which would otherwise stay the ones for a light theme
    window = QColor(getColor('window'))
    palette.setColor(QPalette.ColorRole.Light, window.lighter(150))
    palette.setColor(QPalette.ColorRole.Midlight, window.lighter(125))
    palette.setColor(QPalette.ColorRole.Mid, window.darker(130))
    palette.setColor(QPalette.ColorRole.Dark, window.darker(160))
    palette.setColor(QPalette.ColorRole.Shadow, window.darker(300))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(getColor('disabledText')))
    return palette


def getGraphSettings():
    """Returns the matplotlib settings that all of the application's graphs are drawn with"""
    return {
        'figure.facecolor': getColor('window'),
        'savefig.facecolor': getColor('base'),
        'axes.facecolor': getColor('base'),
        'axes.edgecolor': getColor('axes'),
        'axes.labelcolor': getColor('windowText'),
        'axes.titlecolor': getColor('windowText'),
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.axisbelow': True,
        'axes.prop_cycle': cycler(color=getColor('lines')),
        'text.color': getColor('windowText'),
        'xtick.color': getColor('axes'),
        'ytick.color': getColor('axes'),
        'xtick.labelcolor': getColor('windowText'),
        'ytick.labelcolor': getColor('windowText'),
        'grid.color': getColor('grid'),
        'grid.linewidth': 0.7,
        'lines.linewidth': 1.6,
        'font.size': 9,
        'legend.frameon': True,
        'legend.framealpha': 0.85,
        'legend.facecolor': getColor('base'),
        'legend.labelcolor': getColor('baseText'),
        'legend.edgecolor': getColor('grid'),
    }


def restyleFigure(figure, previous):
    """Changes a figure that was drawn with the theme colors in the dictionary passed in so that it uses the ones
    of the theme that is in use now. Anything in it that isn't in one of the theme's colors is left as it is."""
    lineColors = dict(zip(previous['lines'], getColor('lines')))
    imageColors = [(QColor(previous[name]).getRgb()[:3], getRGB(name)) for name in ('propellant', 'window')]
    figure.set_facecolor(getColor('window'))
    for axes in figure.axes:
        axes.set_facecolor(getColor('base'))
        for spine in axes.spines.values():
            spine.set_edgecolor(getColor('axes'))
        axes.tick_params(which='both', colors=getColor('axes'), labelcolor=getColor('windowText'))
        for text in [axes.xaxis.label, axes.yaxis.label, axes.title] + list(axes.texts):
            text.set_color(getColor('windowText'))
        for gridline in axes.get_xgridlines() + axes.get_ygridlines():
            gridline.set_color(getColor('grid'))
        lines = list(axes.lines)
        legend = axes.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(getColor('base'))
            legend.get_frame().set_edgecolor(getColor('grid'))
            for text in legend.get_texts():
                text.set_color(getColor('baseText'))
            lines += legend.get_lines()
        for line in lines:
            # Lines that were given a color of their own instead of one of the theme's keep it
            color = to_hex(line.get_color())
            if color in lineColors:
                line.set_color(lineColors[color])
        for image in axes.get_images():
            # Images of grains are made of two of the theme's colors, which are swapped for the new ones
            pixels = np.asarray(image.get_array())
            if pixels.ndim == 3 and pixels.dtype == np.uint8:
                masks = [np.all(pixels[..., :3] == old, axis=-1) for old, _ in imageColors]
                pixels = pixels.copy()
                for mask, (_, new) in zip(masks, imageColors):
                    pixels[mask] = new
                image.set_data(pixels)


def restyle(app, previous):
    """Updates every graph in the application from the theme colors in the dictionary passed in to the ones of the
    theme that is in use now."""
    for widget in app.allWidgets():
        if isinstance(widget, FigureCanvasQTAgg):
            restyleFigure(widget.figure, previous)
            widget.draw_idle()


def apply(app, theme=SYSTEM_THEME, accent=DEFAULT_ACCENT, window='', base=''):
    """Sets up the look of the application from the name of a theme and an accent color, along with colors to use
    in place of the theme's window and base colors if they are wanted. It can be called again to change the look of
    the application while it is running."""
    global darkMode, colors
    previous = colors
    if theme == SYSTEM_THEME:
        darkMode = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    else:
        darkMode = theme == DARK_THEME
    colors = getColors(darkMode, accent, window, base)
    # Fusion looks the same on every platform and takes all of its colors from the palette
    app.setStyle('fusion')
    app.setPalette(getPalette())
    mpl.rcParams.update(getGraphSettings())
    # Graphs that already exist took their colors from the theme when they were made
    restyle(app, previous)
