# Package Frozen :snowman:

Package Frozen :snowman: is a python package that adds 
immutability and lockability features to python classes.

## Examples
### Freezable Decorator
As a simple example, we make a freezable class that can be arbitrarily frozen. 
We use the `@freezableclass` and `@freezablemethod` decorators.

```python
from frozen import freezableclass, freezablemethod, FrozenError


@freezableclass
class Immutable:
    def __init__(self, value=None):
        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    @freezablemethod
    def value(self, value):
        self._value = value

    def __frozen_error__(self, method):
        print(
                f"`{type(self).__name__}` object is frozen; "
                f"can not set `{method.__name__}`."
        )


immutable = Immutable()

immutable.value = 10
print(f"The assigned value is {immutable.value}.")

immutable.freeze()
immutable.value = 20
print(f"The assigned value is still {immutable.value}.")
``` 

The excerpt above prints the following output:

```pycon
The assigned value is 10.
`Immutable` object is frozen; cannot set `value`.
The assigned value is still 20.
```
