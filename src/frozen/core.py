import inspect
import typing
import itertools
from collections import deque


def trace_execution(location_hint: typing.Iterable[type] = None):
	"""
	Yields the list of (method, class)'s of the current execution frame
	:param location_hint: List of candidate locations classes to search in
	:return:
	"""
	# Search in all candidate classes for the object
	def search_locations(search_in: typing.Iterable[type]):
		for loc in search_in:
			for mth_name, mth in inspect.getmembers(  # Get all methods and functions of loc
					loc,
					lambda x: inspect.ismethod(x) or inspect.isfunction(x)
			):
				if code.co_name == mth_name:
					if code == mth.__code__:  # If code equals the method's __code__ then the method is found
						return mth, loc
					else:  # However, for static methods, if the code and function names are the same, we also search all subclasses
						mth, loc = search_locations(loc.__subclasses__())

						if (mth, loc) != (None, None):
							return mth, loc

		return None, None

	frame = inspect.currentframe().f_back

	while frame:
		code = frame.f_code
		cache_key = id(code)

		try:  # using cache makes it apx. 50 times faster. Note that WeakValueDicts are not as fast
			method, location = trace_execution.cache[cache_key]
		except KeyError:
			if code.co_argcount > 0:  # if code has at least one positional argument
				args = inspect.getargs(code).args  # get the arguments of the method: looking for 'self' or 'cls'
				first_arg = inspect.getargvalues(frame).locals[args[0]]  # first arg is either 'self' or 'cls' or neither
				cls = first_arg if inspect.isclass(first_arg) else type(first_arg)  # get the 'cls' object
			else:
				cls = None

			method, location = search_locations(itertools.chain(
				[] if cls is None else [cls],
				[] if location_hint is None else location_hint
			))

			if len(trace_execution.cache) > trace_execution.cache_max_len:
				key = next(iter(trace_execution.cache.keys()))
				del trace_execution.cache[key]

			trace_execution.cache[cache_key] = method, location

		yield method, location
		frame = frame.f_back


def get_object_descendents(
		obj: object,
		include_methods: bool = False
):
	"""
	Yields descendents of an object
	:param obj: The object to be inspected
	:param include_methods:  Yield also the member methods
	:return:
	"""
	queue: typing.Deque[object] = deque({obj})
	visited: typing.Set[int] = {id(obj)}

	while queue:
		obj = queue.popleft()

		yield obj

		members = inspect.getmembers(
			obj,
			lambda x:
				not inspect.isbuiltin(x) and  # filters build-in members
				not isinstance(x, type) and  # filters type objects
				not id(x) in visited and (  # filters visited members to avoid infinite cycles
						include_methods or not (
								inspect.ismethod(x) or  # filters object methods, class methods, lambdas, and method attributes
								inspect.isfunction(x)  # filters static methods
							)
					)
			)

		for name, obj in members:
			if not name.startswith('__'):  # filters private members
				visited.add(id(obj))
				queue.append(obj)


def tailor_arguments(
		input_spec: inspect.FullArgSpec,
		output_spec: inspect.FullArgSpec,
		*args, **kwargs
):
	"""
	Tailors the argument list prepared for one function to be fit to another
	:param input_spec:
	:param output_spec:
	:param args:
	:param kwargs:
	:return: Tailored kwargs
	"""
	kwargs.update(dict(zip(input_spec.args[1:], args)))

	if not output_spec.varkw:
		kwargs = dict((k, kwargs[k]) for k in output_spec.args if k in kwargs)

	return kwargs


class DecorationUsageError(Exception):
	pass


class ClassDecorator:
	class ClassWrapper:
		__specs = dict()

		def __init_subclass__(cls, **kwargs):
			parent = cls.__mro__[1]
			cls.__name__ = parent.__name__
			cls.__qualname__ = parent.__qualname__
			cls.__doc__ = parent.__doc__
			cls.__module__ = parent.__module__
			pass

		def __init__(self, calling_class, *args, **kwargs):
			"""
			__init__ super-method to be overridden by ClassWrappers
			overriding
			:param calling_class:
			:param args:
			:param kwargs:
			"""
			if calling_class not in self.__specs:
				wrapped_class = type(self)

				# Find the first non-wrapped class to extract its __init__ signature
				for wrapped_class in wrapped_class.mro():
					if not issubclass(wrapped_class, ClassDecorator.ClassWrapper):
						break

				self.__specs[calling_class] = (
					inspect.getfullargspec(wrapped_class.__init__),
					inspect.getfullargspec(calling_class.__construct__)
				)

			kwargs = tailor_arguments(*self.__specs[calling_class], *args, **kwargs)
			calling_class.__construct__(self, **kwargs)

		def __construct__(self, **kwargs):
			pass

	_decorator_function = None
	_method_decorator = None

	# noinspection PyProtectedMember
	def __call__(self, cls):
		if not inspect.isclass(cls):
			raise TypeError(f"Class {type(self).__name__} can only be called with class arguments.")

		if self._decorator_function.__name__ in MethodDecorator._current_class_decorators:
			MethodDecorator._current_class_decorators.remove(self._decorator_function.__name__)  # Reset the checker


class MethodDecorator:
	_decorator_function = None
	_class_decorator = None
	_last_decorated_method_spec = None
	_current_class_decorators = set()

	def __call__(self, method: typing.Callable, wrapper: typing.Callable = None):
		if wrapper is None:
			if not inspect.isfunction(method):  # Remember that methods are functions before they are bound to classes
				raise TypeError(f"Class {type(self).__name__} can only be called with method arguments.")

			method_spec = {
				'module': inspect.getmodule(method),
				'class': method.__qualname__[:method.__qualname__.rfind('.')]
			}

			if (
					MethodDecorator._last_decorated_method_spec is None or
					MethodDecorator._last_decorated_method_spec == method_spec or
					len(MethodDecorator._current_class_decorators) == 0
			):
				MethodDecorator._last_decorated_method_spec = method_spec
				# noinspection PyProtectedMember
				decorator_name = self._class_decorator._decorator_function.__name__
				MethodDecorator._current_class_decorators.add(decorator_name)
			else:
				raise DecorationUsageError(
					f"Class `{MethodDecorator._last_decorated_method_spec['class']}` has not been "
					f"finalized using a `@{MethodDecorator._current_class_decorators.pop()}` decorator. "
				)
		else:
			wrapper.__name__ = method.__name__
			wrapper.__qualname__ = method.__qualname__
			wrapper.__doc__ = method.__doc__
			# noinspection PyUnresolvedReferences
			wrapper.__module__ = method.__module__
			return wrapper


trace_execution.cache = dict()
trace_execution.cache_max_len = 1024
