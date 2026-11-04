"""Virtual Mycroft Mark 1 faceplate: a software Arduino plus a browser GUI for OVOS."""

from ovos_virtual_mark1.arduino import VirtualArduino
from ovos_virtual_mark1.version import __version__

__all__ = ["VirtualArduino", "__version__"]
