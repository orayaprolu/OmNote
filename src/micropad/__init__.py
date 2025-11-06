import warnings
warnings.warn(
    "Package 'micropad' is deprecated; use 'omnote'. Back-compat will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)
from omnote import *  # re-export everything
