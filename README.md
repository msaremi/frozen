# Package Frozen :snowman:

Package Frozen :snowman: is a python package that adds 
immutability, lockability, and alienatability features to python classes.

- **Immutability**: As long as an object is immutable, no changes are allowed to be made on it.
- **Lockability**: The locked members of an object are not allowed to be called. Only permitted classes and lock/unlock an object. 
- **Alienatability**: Makes class members permanently alien to other classes. Only friend classes can access those members. 

## Examples
### Freezable Decorator
As a simple example, we make a freezable class that can be arbitrarily frozen. 
We use the `@freezableclass` and `@freezablemethod` decorators.

```python
from frozen import freezableclass, freezablemethod


# A freezable class the can be frozen on upon desire
@freezableclass
class Immutable:
	def __init__(self, value=None):
		self._value = value

	@property
	def value(self):
		return self._value

	@value.setter
	# This method is freezable and can not be called on frozen objects.
	@freezablemethod
	def value(self, value):
		self._value = value
``` 

We can make an instance of the class and set its value.

```pycon
>>> from test import Immutable
>>> immutable = Immutable()
>>> immutable.value = "value"
>>> immutable.value
'value'
```

However, once the object is frozen, its value cannot be set further.

```pycon
>>> immutable.freeze()
>>> try:
... 	immutable.value = "new value"
... except:
... 	print("Cannot assign frozen attribute.")
Cannot assign frozen attribute.
>>> immutable.value
'value'
```
