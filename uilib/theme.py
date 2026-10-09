"""Defines how the application looks. Everything that decides on a color or a style for the UI or its graphs should
get it from here, so that the look of the application is set in one place."""

import matplotlib as mpl
from cycler import cycler

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

# The color that the application's highlights are based around
ACCENT = '#701033'

# The colors of the UI, by whether dark mode is in use. The window color is what sits behind everything, and the base
# color is what is behind anything that is edited or drawn on, like a text box or the axes of a graph.
COLORS = {
    False: {
        'window': '#f0f0f0',
        'base': '#ffffff',
        'alternateBase': '#f6f6f6',
        'button': '#f0f0f0',
        'text': '#1f1f1f',
        'disabledText': '#a0a0a0',
        'highlight': ACCENT,
        'highlightedText': '#ffffff',
        'link': ACCENT,
        'grid': '#d9d9d9',
        'axes': '#8c8c8c',
        # The accent is first so anything with a single line on it is drawn in it
        'lines': [ACCENT, '#1f6f8b', '#c9892b', '#3a7d44', '#5b4b8a', '#7a7a7a', '#b5524a', '#2a9d8f'],
        'propellant': '#2d2d2d',
    },
    True: {
        'window': '#2b2b2b',
        'base': '#1e1e1e',
        'alternateBase': '#252525',
        'button': '#353535',
        'text': '#e6e6e6',
        'disabledText': '#7a7a7a',
        # The accent itself is too dark to see against a dark background, so lighter versions of it stand in
        'highlight': '#8a1a45',
        'highlightedText': '#ffffff',
        'link': '#d0668f',
        'grid': '#3d3d3d',
        'axes': '#8c8c8c',
        'lines': ['#d0668f', '#5fb3ce', '#e3b05a', '#7cc48a', '#a493d6', '#b0b0b0', '#e08b84', '#63cdbf'],
        'propellant': '#c0c0c0',
    }
}

darkMode = False


def getColor(name):
    """Returns one of the colors of the theme that is in use, as a string like '#rrggbb'"""
    return COLORS[darkMode][name]


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


def apply(app):
    """Sets up the look of the application. This has to be called before any of its widgets or graphs are made."""
    global darkMode
    darkMode = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    # Fusion looks the same on every platform and takes all of its colors from the palette
    app.setStyle('fusion')
    app.setPalette(getPalette())
    mpl.rcParams.update(getGraphSettings())
