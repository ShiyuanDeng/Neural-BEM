"""
Shared simulation configuration parameters for GPR forward modeling.
"""
import numpy as np

# Physical constants
C0 = 299792458.0  # Speed of light in vacuum (m/s)
MU0 = 4 * np.pi * 1e-7  # Permeability of free space (H/m)
EPS0 = 8.854187817e-12  # Permittivity of free space (F/m)

# Domain parameters
DOMAIN_WIDTH = 1.0  # m (x direction)
DOMAIN_HEIGHT = 1.0  # m (y direction)

# Material parameters
SAND_EPSR = 6.0  # Relative permittivity of sand
SAND_SIGMA = 0.0  # Conductivity of sand (S/m)

PLASTIC_EPSR = 3.0  # Relative permittivity of plastic
PLASTIC_SIGMA = 0.0  # Conductivity of plastic (S/m)

# Shared target placement
TARGET_CENTER_X = 0.5  # m
TARGET_CENTER_Y = 0.5  # m

# Antenna parameters
TX_RX_OFFSET = 0.06  # m (transmitter-receiver separation)
ANTENNA_Y = 0.0  # m (top surface reference)
SCAN_PATH = "rectangular_loop"
SCAN_RECT_LEFT = 0.24  # m
SCAN_RECT_RIGHT = 0.76  # m
SCAN_RECT_TOP = 0.32  # m
SCAN_RECT_BOTTOM = 0.68  # m
SCAN_RECT_TOP_COUNT = 60
SCAN_RECT_RIGHT_COUNT = 60
SCAN_RECT_BOTTOM_COUNT = 60
SCAN_RECT_LEFT_COUNT = 60
SCAN_GATE_START = 2.0e-9  # s

# Legacy linear scan reference kept for lightweight unit tests
SCAN_START = 0.2  # m (x position)
SCAN_END = 0.8  # m (x position)
SCAN_STEP = 0.01  # m

# Source parameters
CENTER_FREQ = 2.5e9  # Hz (2500 MHz)
TIME_WINDOW = 15e-9  # s (15 ns)
NUM_TIME_SAMPLES = 301

# Frequency domain parameters
FREQ_MIN = 0.005e9  # Hz (5 MHz, conservative high-accuracy lower cutoff)
FREQ_MAX = 8.0e9  # Hz (8 GHz, widened to retain more high-frequency pulse content)
NUM_FREQS = 385  # Conservative high-accuracy frequency sampling for the widened band
FREQUENCY_WINDOW = "none"  # "none", "hann", or "tukey"
FREQUENCY_WINDOW_ALPHA = 0.4  # Tukey taper fraction; ignored for Hann/none

# BEM discretization
NUM_BOUNDARY_ELEMENTS = 192  # Higher boundary resolution for the conservative high-accuracy run

# Absorbing boundary condition
ABC_TYPE = 'first_order'  # First-order ABC
