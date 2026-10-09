"""Defines how the application looks. Everything that decides on a color or a style for the UI or its graphs should
get it from here, so that the look of the application is set in one place."""

import matplotlib as mpl
from cycler import cycler

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


def getColors(dark, accent):
    """Returns a dictionary of all of the colors of a theme, as strings like '#rrggbb'. The colors that highlight
    things are worked out from the accent color passed in, which is replaced by the default if it isn't valid."""
    accentColor = QColor(accent)
    if not accentColor.isValid():
        accentColor = QColor(DEFAULT_ACCENT)
    hue, saturation, lightness, _ = accentColor.getHslF()
    themeColors = dict(NEUTRALS[dark])
    if dark:
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


def getGrayLevel(name):
    """Returns the brightness of one of the theme's colors from 0 to 255, for images that are drawn in grayscale"""
    return QColor(getColor(name)).lightness()


def getPalette():
    """Returns the palette that the application's widgets are drawn with"""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: 'window',
        QPalette.ColorRole.WindowText: 'text',
        QPalette.ColorRole.Base: 'base',
        QPalette.ColorRole.AlternateBase: 'alternateBase',
        QPalette.ColorRole.ToolTipBase: 'base',
        QPalette.ColorRole.ToolTipText: 'text',
        QPalette.ColorRole.Text: 'text',
        QPalette.ColorRole.Button: 'button',
        QPalette.ColorRole.ButtonText: 'text',
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
        'axes.labelcolor': getColor('text'),
        'axes.titlecolor': getColor('text'),
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.axisbelow': True,
        'axes.prop_cycle': cycler(color=getColor('lines')),
        'text.color': getColor('text'),
        'xtick.color': getColor('axes'),
        'ytick.color': getColor('axes'),
        'xtick.labelcolor': getColor('text'),
        'ytick.labelcolor': getColor('text'),
        'grid.color': getColor('grid'),
        'grid.linewidth': 0.7,
        'lines.linewidth': 1.6,
        'font.size': 9,
        'legend.frameon': True,
        'legend.framealpha': 0.85,
        'legend.facecolor': getColor('base'),
        'legend.edgecolor': getColor('grid'),
    }


def apply(app, theme=SYSTEM_THEME, accent=DEFAULT_ACCENT):
    """Sets up the look of the application from the name of a theme and an accent color. This has to be called
    before any of its graphs are made, as they take their colors from the theme when they are built."""
    global darkMode, colors
    if theme == SYSTEM_THEME:
        darkMode = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    else:
        darkMode = theme == DARK_THEME
    colors = getColors(darkMode, accent)
    # Fusion looks the same on every platform and takes all of its colors from the palette
    app.setStyle('fusion')
    app.setPalette(getPalette())
    mpl.rcParams.update(getGraphSettings())
