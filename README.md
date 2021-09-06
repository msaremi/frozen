# Package Frozen :snowman:

Package Frozen :snowman: is a python package that adds 
immutability, lockability, and alienatability features to python classes.

- **Immutability**: As long as an object is immutable, no changes are allowed to be made on it.
- **Lockability**: The locked members of an object are not allowed to be called. Only permitted classes and lock/unlock an object. 
- **Alienatability**: Makes class members permanently alien to other classes. Only friend classes can access those members. 

## Examples
### Immutability
Immutability is made possible through the freezable decorators.

As a simple example, we make a freezable class that can be arbitrarily frozen. 
We use the `@freezable.cls` and `@freezable.mth` decorators.

```python
from frozen import freezable


# A freezable class the can be frozen on upon desire
@freezable.cls()
class Immutable:
	def __init__(self, value=None):
		self._value = value

	@property
	def value(self):
		return self._value

	@value.setter
	# This method is freezable and can not be called on frozen objects.
	@freezable.mth()
	def value(self, value):
		self._value = value
``` 

We can make an instance of the class and set its value.

```pycon
>>> immutable = Immutable()
>>> immutable.value = "value"
>>> immutable.value
'value'
```

However, once the object is frozen, its value cannot be set further.

```pycon
>>> immutable.freeze()
>>> immutable.value = "new value"
```
```diff
- frozen.freezable.FrozenError: Calling `value` method on frozen `Immutable` objects is not possible. - 
- Try making a copy of the object before calling frozen methods. -
```
```pycon
>>> immutable.value
'value'
```
