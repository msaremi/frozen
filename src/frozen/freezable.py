from .core import *
import copy


class Errors(Errors):
	InconsistentCopyMethod = \
		"`{}` class has a `copy` method with inconsistent signature. " \
		"It needs a positional 'self' parameter and a 'deep' parameter."
	CallingFrozenMethod = \
		"Calling `{}` method on frozen `{}` objects is not possible. " \
		"Try making a copy of the object before calling frozen methods."
	MethodNotCallable = \
		"`{}` method on `{}` objects is not callable."


class FrozenError(PermissionError):
	pass


def freezableclass(*args, let_freeze: bool = True, let_melt: bool = False):
	if args:
		cls = args[0]
		return FreezableClass()(cls)
	else:
		return FreezableClass(let_freeze=let_freeze, let_melt=let_melt)


class FreezableClass(ClassDecorator):
	def __init__(self, let_freeze: bool = True, let_melt: bool = False):
		"""
		:param let_freeze: Let the object call the freeze method in cases other than `__init__` or `copy`
		:param let_melt: Same as `let_freeze`
		"""
		self._let_freeze = let_freeze
		self._let_melt = let_melt

	def __call__(self, cls, *_):
		"""
		Sanitize the class cls and returns a wrapper
		:param cls:
		:return:
		"""
		super().__call__(cls)

		try:  # if cls.copy does not exist it will set is_copy_callable to False
			is_copy_callable = isinstance(cls.copy, typing.Callable)
		except AttributeError:
			is_copy_callable = False

		if is_copy_callable:
			spec = inspect.getfullargspec(cls.copy)

			if (
					(len(spec.args) == 0 and spec.varargs is None) or  # check if the method has a 'self' parameter
					('deep' not in spec.args and spec.varkw is None)  # check if 'deep' exists as a parameter
			):
				raise ValueError(Errors.InconsistentCopyMethod.format(cls.__qualname__))

		class FreezableView(ClassDecorator.ObjectView):
			def __init__(self, obj):
				ClassDecorator.ObjectView.__init__(self, obj)

			# noinspection PyMethodMayBeStatic, PyUnusedLocal
			def freeze(self, deep: bool = True):
				raise PermissionError(
					Errors.ViewMethodNotCallable.format(FreezableView.freeze.__name__, cls.__qualname__)
				)

			# noinspection PyMethodMayBeStatic, PyUnusedLocal
			def melt(self, deep: bool = True):
				raise PermissionError(
					Errors.ViewMethodNotCallable.format(FreezableView.melt.__name__, cls.__qualname__)
				)

		class FreezableWrapper(cls, ClassDecorator.ClassWrapper):
			def __init__(self, *args, **kwargs):
				# This will call FreezableWrapper.__construct__ and then cls.__init__
				self.__view = None
				ClassDecorator.ClassWrapper.__init__(self, FreezableWrapper, cls, *args, **kwargs)

			def __construct__(self, frozen: bool = False):
				self.__frozen__ = frozen

				if self.__frozen__:
					self.__freeze(deep=False)

			def __frozen_error__(self, method: typing.Callable):
				"""
				Throws an error when a frozen method is called
				:param method:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__frozen_error__(method=method)
				except AttributeError:
					raise FrozenError(
						Errors.CallingFrozenMethod.format(method.__name__, type(self).__qualname__)
					) from None

			def __freeze(self, deep: bool = True):
				if deep:
					for obj in get_object_descendents(self):
						try:
							obj.__frozen__ = True
						except AttributeError:
							continue
				else:
					self.__frozen__ = True

			def __melt(self, deep: bool = True):
				if deep:
					for obj in get_object_descendents(self):
						try:
							obj.__frozen__ = False
						except AttributeError:
							continue
				else:
					self.__frozen__ = False

			@property
			def frozen(self) -> bool:
				"""
				Returns a value indicating if the object is frozen
				:return: the frozen value
				"""
				return self.__frozen__

			# noinspection PyMethodParameters
			def freeze(myself, deep: bool = True):
				if self._let_freeze:
					return myself.__freeze(deep=deep)
				else:
					raise PermissionError(
						Errors.MethodNotCallable.format(FreezableWrapper.freeze.__name__, cls.__qualname__)
					)

			# noinspection PyMethodParameters
			def melt(myself, deep: bool = True):
				"""
				Unfreezes the object
				:param deep:
				:return:
				"""
				if self._let_melt:
					return myself.__melt(deep=deep)
				else:
					raise PermissionError(
						Errors.MethodNotCallable.format(FreezableWrapper.melt.__name__, cls.__qualname__)
					)

			def copy(self, deep: bool = True, frozen: bool = None):
				"""
				Makes of copy of the object, which may or may not be frozen
				:param deep:
				:param frozen:
				:return:
				"""
				# Note that the following will always return an object
				# of type FreezableClass.__call__.<locals>.FreezableWrapper
				try:  # call super().copy(...) if it exists
					# noinspection PyUnresolvedReferences
					new_obj = super().copy(deep=deep)
				except AttributeError:
					new_obj = copy.deepcopy(self) if deep else copy.copy(self)

				if frozen is not None:
					if frozen:
						new_obj.__freeze(deep)
					else:
						new_obj.__melt(deep)

				return new_obj

			def view(self):
				if self.__view is None:
					self.__view = FreezableView(self)

				return self.__view

		super().__call__(cls, FreezableWrapper)
		return FreezableWrapper


def freezablemethod(*args):
	if args:
		method = args[0]
		return FreezableMethod()(method)
	else:
		return FreezableMethod()


class FreezableMethod(MethodDecorator):
	def __call__(self, method: typing.Callable, *_):
		super().__call__(method)
		
		def freezable_wrapper(myself, *args, **kwargs):
			if isinstance(myself, ClassDecorator.ObjectView):
				# noinspection PyProtectedMember
				myself._ObjectView__obj.__frozen_error__(method)
			elif myself.__frozen__:
				myself.__frozen_error__(method)
			else:
				return method(myself, *args, **kwargs)

		return super().__call__(method, freezable_wrapper)


FreezableClass._decorator_function = freezableclass
FreezableClass._method_decorator = FreezableMethod
FreezableMethod._decorator_function = freezablemethod
FreezableMethod._class_decorator = FreezableClass
freezable = ModuleElements(mth=freezablemethod, cls=freezableclass)
