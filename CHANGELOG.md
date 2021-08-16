# Changelog

## Version `0.0.2`

### Major changes
- Added `freezable` and `lockable` objects to `__init__`.
    - [\_\_init\_\_.py](src/frozen/__init__.py)
        - 001-002: `freezable` and `lockable` objects added.
    - [core.py](src/frozen/core.py)
        - 009: Class `ModuleElements` implemented.
    - [freezable.py](src/frozen/freezable.py)
        - 208: Class `ModuleElements` instantiated.
    - [lockable.py](src/frozen/lockable.py)
        - 249: Class `ModuleElements` instantiated.
- Implemented `Errors` class for error strings.
    - [core.py](src/frozen/core.py)
        - 009: Class `Errors` implemented.
    - [freezable.py](src/frozen/freezable.py)
        - 005: Class `Errors` extended.
    - [lockable.py](src/frozen/lockable.py)
        - 005: Class `Errors` extended.
- Fixed method `tailor_arguments`, so the intended class does not raise an error
    - [core.py](src/frozen/core.py)
        - 118: `input_spec` and `output_spec` changed to functions.
        - 120: New argument `has_self` was added.
        - 132: Method `tailor_arguments` now uses internal cache.
        - 153: Returns two `kwargs`'s now.
        - 264: Method is called differently and calls the wrapped_class directly from `ClassWrapper.__init__`
    - [freezable.py](src/frozen/freezable.py)
        - 073: Calling the base class `cls` was appointed to `ClassDecorator.ClassWrapper.__init__`.
    - [lockable.py](src/frozen/lockable.py)
        - 080: Ditto.
- Added `freeze` and `melt` methods to class `FreezableView`. Now attempting to freeze or melt a freezable view object
is not allowed.
    - [freezable.py](src/frozen/freezable.py)
        - 063:074: Methods `freeze` and `melt` were added.        

### Minor changes
- Improved `ObjectView` meta-class.
    - [core.py](src/frozen/core.py)
        - 163:163: The `__proxy_cache` and `__obj` attributes are now private, in order not to conflict with 
        main class elements.
    - [freezable.py](src/frozen/freezable.py)
        - `method_self._obj` changed to `method_self._ObjectView__obj`.
        

### To do
- Implement `view` method for lockable objects.
    - [lockable.py](src/frozen/lockable.py)
        - 211-214: Implement `view`.
        - 234: Handle lockable views in `lockable_wrapper` method.

## Version `0.0.1`

### Major changes
- Added `view()` method to freezable objects:
    - [core.py](src/frozen/core.py)
        - 126: Added `ClassDecorator.ObjectView` class.
        - 245: `ClassDecorator` abstract methods now raise a `NotImplementedError` exception.
    - [freezable.py](src/frozen/freezable.py)
        - 051: `FreezableView` was added as a subclass of `ClassDecorator.ObjectView`.
        - 159: `FreezableWrapper.view()` was added.
        - 181: The `freezable_wrapper` function now checks for the wrapper classes.


### Minor changes
- [core.py](src/frozen/core.py)
    - 236: Explicit class name instead of `self` to refer to `__spec` property.
- [freezable.py](src/frozen/freezable.py)
    - 181: Removed unnecessary try-except block.
- [lockable.py](src/frozen/lockable.py)
    - 230: Ditto.
- [README.md](README.md)
    - minor modifications.
- [setup.cfg](setup.cfg)
    - File added.
- [CHANGELOG.md](CHANGELOG.md)
    - File added.