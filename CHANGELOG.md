# Changelog

## Version `0.0.6`

###Major changes
- The alienatable module was added. This makes some methods only callable by friend classes.
- Changes in `ModuleElements` to make the decorators easier to use by increasing clarity.
  - Now, `lockable/freezable/alienatable.cls/mth` require a parenthesis.


##Minor changes
- Method `is_calling_class_valid` moved to core
  - [`frozen.core.is_calling_class_valid`](src/frozen/core.py): Method added.
  - [`frozen.lockable.Lockable._is_calling_class_valid`](src/frozen/lockable.py): Method removed.
- `Lockable`'s and `Freezable`'s `__init__` removed as they had the same signature as the parent class.
- Bug in `LockableClassDecoratorData` fixed.
  - [`frozen.lockable.LockableClassDecoratorData.__init__`](src/frozen/lockable.py): wrapper retrieval corrected.

## Version `0.0.5`

### Major changes:
- (Re-)implemented `view()`, finally.
  - `view()` returns the most restricted object compared to the current object.
  If `obj` is a freezable object, `obj.view()` will always be frozen; if `obj` is a lockable object, `obj.view()`
  will always be locked with the current locks, even when `obj` is unlocked. Also, `obj` can 
  be both freezable and lockable.
  - The `frozen.core.MultiView` class creates new MultiView types upon request. Current 
  MultiView types are `MultiView[Freezable.View]`, `MultiView[Lockable.View]`, and `MultiView[Freezable.View, Lockable.View]`.
    - [`frozen.core.MultiView`](src/frozen/core.py): Class added.
    - [`frozen.core.ClassWrapperBase.view(...)`](src/frozen/core.py): Method added.
- A bug fixed related to the class decorators, that caused inheritance in the decorators buggy.
  - The `frozen.lockable.Lockable` and `frozen.freezable.Freezable` are not bipartite! Part of them is
  implemented in the decorator `__call__` method. This part stores the data relevant to the decorator.
- Now, `MultiView` supports `view()` without relying on `View`. This is an improved version that makes it possible
  for the `view()` methods to also take arguments.
  - [`frozen.core.MultiView.<locals>.view()`](src/frozen/core.py): Method added.
  - [`frozen.core.View.view()`](src/frozen/core.py): Method removed.

### Minor changes:
- `get_object_descendents(...)` method re-named to `get_descendents(...)`.
  - [`frozen.core.get_descendents`](src/frozen/core.py): Method renamed.
- A bug in `tailor_arguments` fixed that caused duplicate values in the intended method.
  - [`frozen.core.tailor_arguments`](src/frozen/core.py): Added `kwargs` to `kwargs.copy()` so that the `intended_kwargs` will not be affected.
- Introduced `ClassDecoratorData` types that hold the data of `ClassDecorator` objects.
  - [`frozen.core.ClassDecoratorDataType`](src/frozen/core.py): Generic type added.
  - [`frozen.freezable.FreezableMethodDecorator`](src/frozen/freezable.py): Class added.
  - [`frozen.lockable.LockableClassDecoratorData`](src/frozen/lockable.py): Class added.
- The shared part of the `Lockable.lock` and `Lockable.unlock` methods is now in a new method `_is_calling_class_valid`.
  - [`frozen.lockable.Lockable.is_calling_class_valid`](src/frozen/lockable.py): Method added.
  - [`frozen.lockable.Lockable.lock`](src/frozen/lockable.py): Method changed.
  - [`frozen.lockable.Lockable.unlock`](src/frozen/lockable.py): Method changed.
- Added `__frozen__ = True` to `Freezable.View`
  - [`frozen.freezable.Freezable.View.__frozen__`](src/frozen/freezable.py): Attribute added.
- A bug fixed in `Lockable.View` that made it possible to unlock lockable views by unlocking the objects.
- A bug fixed in `Lockable.unlock` that raised an error when the object has not previously been locked with a key before unlocking.
- A bug fixed in `View` that made it impossible to cpy special methods. Another bug that caused conflicting arguments with `self` was fixed.
  - [`frozen.core.View._create_class_proxy`](src/frozen/core.py): `self._obj` changed to `args[0].__obj`.



## Version `0.0.4`

### Major changes:
- Three new types added to the package: `View`, `Freezable`, `Lockable`
- Improved caching for functions. Now, I don't use dictionaries explicitly; Instead, I use `functools.lru_cache`.
  - [`core.trace_execution`](src/frozen/core.py): The function caches the traces of functions/methods.
  - [`core.tailor_arguments`](src/frozen/core.py): The full arg specs are now cached.
- Getting members of an object is now optimized. The`get_members` function is now customized. I no longer use `inspect.getmembers` because it 
  iterates over the whole members before returning anything. The customized version yields the values
  and avoids unnecessary sorting.
  - [`core.get_members`](src/frozen/core.py): Method added.
- Wrapper naming strategy have been changed. Now a `__realname__` attribute is added to the wrappers and 
  all other fields are copied.
  - [`core.wraps`](src/frozen/core.py): Method added, which unifies all wrapper naming code blocks.
- View is now coded differently. Methods that can not be called in views are decorated using `locked_in_view`.
  - [`core.locked_in_view`](src/frozen/core.py): Decorates method to raise error when called in a view.
- The message-passing relation between method and class decorator has been improved. Now, I use explicit `MethodSpec`'s
  to transfer messages between the two decorators.
  - [`core.MethodSpec(Generic[...])`](src/frozen/core.py): Class added.


### Minor changes:
- Typing module imports `*` to save key-strokes.
- Class `core.Error` annotation completed.
- Many type hints have been added.
- A bug in `core.tailor_argumets` fixed, which resulted in bugs when decorated classes did not define `__init__`.
- A `ForwardDec` class was implemented, which helps classes to forward declare themselves.
  - [`core.ForwardDec`](src/frozen/core.py): Abstract class added. I extend this class to forward-declare my classes.
  - [`core.forward_declarable`](src/frozen/core.py): Helps the `core` classes template types to be forward declarable.
- I changed `ClassDecorator.ClassWrapper.__init__` to be slightly faster. Previously it iterated over 
  `self.__mro__`; Now, it iterates over `calling_class.__mro__`. Plus, it does not pass `intended_kwargs` if `wrapped_class` is 
  an object of `ClassDecorator`; in this case, `wrapped_class` will handle the arguments itself.
- Property `_method_specs` added to `ClassDecorator.ClassWrapper`. This method returns the set of specs of the 
  decorated methods of the subclass decorator. 
  - [`core.ClassDecorator.ClassWrapper._method_specs`](src/frozen/core.py): Method added.
- Class decorator `lockable.cls` now accepts classes, in addition to set of classes for `lock_permissions`.

### Known issues:
- Deep-freezing freezes every freezable objects. I should freeze only those object that
  are transitively accessible from the main object. The reason is, other descendents that own
  freezable objects should handle the freezable objects themselves (This is questionable at this stage).
- Views are still problematic. Especially, `view()` returns the view of only the topmost wrapper.
  Plus, `view().view()`, shows inconsistent behaviour.

## Version `0.0.3`

### Major changes
- Implemented `view()` for `lockable` objects.
  - [lockable.py](src/frozen/lockable.py)
  - 088: Class `LockableView` implemented.
  - 077: Method `lockable_wrapper` updated to incorporate "view" objects.
- A class can now lock/unlock itself.
  - [lockable.py](src/frozen/lockable.py)
  - 251-257: Add `cls` to list of lock/unlock permissions.
- Improved `lockable.cls` input permission data types.
  - [lockable.py](src/frozen/lockable.py)
  - 056, 063: Change values to typing.Dict[str, typing.Set[type]].
- Fixed a problem of re-naming the dunders of child classes of wrappers.
  - [core.py](src/frozen/core.py)
  - 258: Removed `__init_subclass__`, which was called for every sub-class, not only wrappers.
  - 286: Reimplemented `__call__` to rename the wrapper class dunders; 
  now the wrapper classes call `ClassDecorator.__call__` twice.
- Changed the renaming strategy of class and method wrapper dunder re-naming.
  - [core.py](src/frozen/core.py)
  - 293: New naming strategy. Now a "@{wrapper.__name__}" is added before the wrapped class.
  - 228, 252: Same naming strategy for view wrappers.
  - 333: Same naming strategy for methods.
- Fixed a bug that made objects with views non-copiable.
  - [core.py](src/frozen/core.py)
  - 237-253: When copying, the `obj` parameter was empty, which raised an error. 
  Now, `*args` is used instead: When instantiating `args[0]` holds he object to be wrapped; 
  when copying, `args[0]` is not assignd.
  The error was: "TypeError: \_\_new\_\_() missing 1 required positional argument: 'obj'" in "\lib\copyreg.py".
  

### Minor changes
- Changed inner self's to `myself`.
  - [freezable.py](src/frozen/freezable.py)
  - [lockable.py](src/frozen/lockable.py)
  - (Various locations)
- Changed the error string of inaccessible methods on view objects.
  - [core.py](src/frozen/core.py)
  - 021: New member was added to `Errors`.
  - [freezable.py](src/frozen/freezable.py)
  - 066, 072: Changed the error string.
  - [lockable.py](src/frozen/lockable.py)
  - 097, 102: Proper error string was used.

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