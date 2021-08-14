# Changelog

## Major changes


- Added `view()` method to freezable objects:
    - [core.py](src/frozen/core.py)
        - 126: Added `ClassDecorator.ObjectView` class.
        - 245: `ClassDecorator` abstract methods now raise a `NotImplementedError` exception.
    - [freezable.py](src/frozen/freezable.py)
        - 051: `FreezableView` was added as a subclass of `ClassDecorator.ObjectView`.
        - 159: `FreezableWrapper.view()` was added.
        - 181: The `freezable_wrapper` function now checks for the wrapper classes.


##Minor changes
- [core.py](src/frozen/core.py)
    - 236: Explicit class name instead of `self` to refer to `__spec` property.
- [freezable.py](src/frozen/freezable.py)
    - 181: Removed unnecessary try-except block.
- [lockable.py](src/frozen/lockable.py)
    - 230: Ditto.
- [README.md](README.md)
    - minor modifications.
- [setup.cfg](setup.cfg)
- [CHANGELOG.md](CHANGELOG.md)
    - File added.