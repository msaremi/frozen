import weakref
import inspect
import types
import typing
import itertools
from collections import deque


class Errors:
	"""
	List of error messages in this module. For internal use. Can be extended by other modules.
	"""
	MethodNotImplemented = \
		"`{}` method is not implemented."
	CallWithClassArg = \
		"`{}` class can only be called with class arguments."
	CallWithMethodArg = \
		"`{}` class can only be called with method arguments."
	ClassNotFinalized = \
		"`{}` class has not been finalized using a `{}` decorator."
	ViewMethodNotCallable = \
		"`{}` method on `{}` view objects is not callable."


def trace_execution(location_hint: typing.Iterable[type] = None):
	"""
	Yields the list of (method, class)'s of the current execution frame
	If the methods are not @staticmethod the algorithm finds the classes directly
	If the methods are @staticmethod the algorithm searches in `locations_hint` and their subclasses
	:param location_hint: List of candidate classes to search in
	:return: yields (method, location) frame-by-frame in execution stack
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
	:param include_methods: Yield as well the member methods
	:return: Yield list of descendent objects of the current object
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
		intended_method: typing.Callable,
		augmented_method: typing.Callable,
		has_self: bool = True,
		*args, **kwargs
):
	"""
	Tailors the argument list prepared for one function to be fit to another
	:param intended_method:
	:param augmented_method:
	:param has_self: If the functions take the 'self' argument
	:param args: List of positional arguments
	:param kwargs: Dictionary of keyword arguments
	:return: Tailored kwargs
	"""
	try:
		intended_spec = inspect.getfullargspec(intended_method)
	except KeyError:
		intended_spec = inspect.getfullargspec(intended_method)
		tailor_arguments.cache[intended_method] = intended_spec

	try:
		augmented_spec = inspect.getfullargspec(augmented_method)
	except KeyError:
		augmented_spec = inspect.getfullargspec(augmented_method)
		tailor_arguments.cache[augmented_method] = augmented_spec

	intended_kwargs = kwargs if intended_spec.varkw else dict(
		(k, kwargs[k]) for k in intended_spec.args if k in kwargs
	)
	start = 1 if has_self else 0
	kwargs.update(dict(zip(intended_spec.args[start:], args[start:])))
	augmented_kwargs = kwargs if augmented_spec.varkw else dict(
		(k, kwargs[k]) for k in augmented_spec.args if k in kwargs
	)

	return intended_kwargs, augmented_kwargs


class DecorationUsageError(Exception):
	pass


class ClassDecorator:
	class ObjectView(object):
		__proxy_cache = dict()
		__obj = None  # Necessary for the class to detect it as a member

		def __init__(self, obj):
			self.__obj = obj

		def __getattribute__(self, item):
			try:
				return object.__getattribute__(self, item)
			except AttributeError:
				value = getattr(self.__obj, item)

				# If the member of obj is a method, we'll pass the proxy to it, instead of obj
				if isinstance(value, types.MethodType):
					value = getattr(type(self.__obj), item)
					return value.__get__(self, type(self))
				# If the member is of one of the following type, return its view()
				# The view() method of ClassDecorator returns an ObjectView.
				# This makes recursive proxying possible.
				elif isinstance(value, ClassDecorator.ClassWrapper):
					return value.view()
				else:
					return value

		def __setattr__(self, key, value):
			try:
				object.__getattribute__(self, key)  # Raises error if key is not in self
				object.__setattr__(self, key, value)
			except AttributeError:
				setattr(self.__obj, key, value)

		def __delattr__(self, item):
			try:
				object.__getattribute__(self, item)
				object.__delattr__(self, item)
			except AttributeError:
				return delattr(self.__obj, item)

		@classmethod
		def _create_class_proxy(cls, object_class):
			"""
			The factory method that creates a proxy class based on class `object_class`
			:param object_class: The type based on which the proxy class will be create
			:return: The proxy class
			"""
			def make_method(method_name):
				def method(self, *args, **kw):
					return getattr(self._obj, method_name)(*args, **kw)

				return method

			# The dictionary holds python's special methods present in object_class
			special_methods = dict()

			for name in dir(object_class):
				value = getattr(object_class, name)

				if (
						not hasattr(cls, name) and  # if this cls does not have the method (we don't want to override this methods)
						isinstance(value, (types.WrapperDescriptorType, types.MethodDescriptorType))  #
						# WrapperDescriptorType == type(object.__init__), MethodDescriptorType == type(str.join)
				):
					special_methods[name] = make_method(name)

			return type(f"@{cls.__name__}.{object_class.__name__}", (cls,), special_methods)

		def __new__(cls, *args, **kwargs):
			"""
			Creates a new Proxy(type(obj)) class
			:param obj: The object for whose type the proxy is created/returned.
			:param args:
			:param kwargs:
			"""
			# Reason for improvement of the function. The previous version raises error if calling copy() after view()
			# File "...\lib\copyreg.py", line 88, in __newobj__
			#   return cls.__new__(cls, *args)
			# TypeError: __new__() missing 1 required positional argument: 'obj'

			if len(args) == 0:  # When cls is being copied
				return object.__new__(cls)
			else:  # When new cls is created based on an obj
				obj = args[0]
				main_class = type(obj)

				try:
					proxy_class = cls.__proxy_cache[main_class]
				except KeyError:
					proxy_class = cls._create_class_proxy(main_class)
					proxy_class.__qualname__ = main_class.__qualname__[:main_class.__qualname__.rfind('.')+1] + proxy_class.__name__
					cls.__proxy_cache[main_class] = proxy_class

				return object.__new__(proxy_class)

	class ClassWrapper:
		def __init__(self, calling_class, wrapped_class, *args, **kwargs):
			"""
			__init__ super-method to be overridden by ClassWrappers
			overriding
			:param calling_class:
			:param args:
			:param kwargs:
			"""
			# Find the first non-wrapped class to extract its __init__ signature
			intended_class = next(
				(cls for cls in type(self).mro() if not issubclass(cls, ClassDecorator.ClassWrapper)),
			)
			intended_kwargs, construct_kwargs = tailor_arguments(
				intended_class.__init__, calling_class.__construct__, True, self, *args, **kwargs
			)
			calling_class.__construct__(self, **construct_kwargs)
			wrapped_class.__init__(self, *args, **intended_kwargs)

		def __construct__(self, **kwargs):
			raise NotImplementedError(Errors.MethodNotImplemented.format(self.__construct__.__qualname__))

		def view(self):
			raise NotImplementedError(Errors.MethodNotImplemented.format(self.view.__qualname__))

	_decorator_function = None
	_method_decorator = None

	# noinspection PyProtectedMember
	def __call__(self, cls, wrapper=None):
		if wrapper is None:
			if not inspect.isclass(cls):
				raise TypeError(Errors.CallWithClassArg.format(type(self).__name__))

			if self._decorator_function.__name__ in MethodDecorator._current_class_decorators:
				MethodDecorator._current_class_decorators.remove(self._decorator_function.__name__)  # Reset the checker
		else:
			wrapper.__name__ = f"@{wrapper.__name__}.{cls.__name__}"
			wrapper.__qualname__ = cls.__qualname__[:cls.__qualname__.rfind('.')+1] + wrapper.__name__
			wrapper.__doc__ = cls.__doc__
			wrapper.__module__ = cls.__module__


class MethodDecorator:
	_decorator_function = None
	_class_decorator = None
	_last_decorated_method_spec = None
	_current_class_decorators = set()

	def __call__(self, method: typing.Callable, wrapper: typing.Callable = None):
		if wrapper is None:
			if not inspect.isfunction(method):  # Remember that methods are functions before they are bound to classes
				raise TypeError(Errors.CallWithMethodArg.format(type(self).__name__))

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
					Errors.ClassNotFinalized.format(
						MethodDecorator._last_decorated_method_spec['class'],
						MethodDecorator._current_class_decorators.pop()
					)
				)
		else:
			wrapper.__name__ = f"@{wrapper.__name__}.{method.__name__}"
			wrapper.__qualname__ = method.__qualname__[:method.__qualname__.rfind('.')+1] + wrapper.__name__
			wrapper.__doc__ = method.__doc__
			# noinspection PyUnresolvedReferences
			wrapper.__module__ = method.__module__
			return wrapper


class ModuleElements:
	def __init__(self, mth: typing.Callable, cls: typing.Callable):
		self._mth = mth
		self._cls = cls

	@property
	def mth(self):
		return self._mth

	@property
	def cls(self):
		return self._cls


trace_execution.cache = dict()
trace_execution.cache_max_len = 1024
tailor_arguments.cache = weakref.WeakKeyDictionary()
