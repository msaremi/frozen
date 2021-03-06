"""
This module adds the freezability feature to classes
"""

from __future__ import annotations
from frozen.core import *
import copy


class Errors(Errors):
	"""
	List of error messages in this module.
	:cvar CallingFrozenMethod: Error message for when a frozen method is called.
	:cvar MethodNotCallable: Error message for when a `freeze` or `melt` is not allowed to be called.
	"""
	CallingFrozenMethod = \
		"Calling `{}` method on frozen `{}` objects is not possible. " \
		"Try making a copy of the object before calling frozen methods."
	MethodNotCallable = \
		"`{}` method on `{}` objects is not callable."


class FrozenError(PermissionError):
	"""
	Raised when a frozen method is called on a frozen object.
	"""
	pass


class Freezable(ClassWrapperBase['FreezableClassDecoratorData']):
	def __load__(self, frozen: bool = False):
		self.__frozen__ = frozen

		if self.__frozen__:
			self._set_frozen_state(frozen=True, deep=False)

	def __frozen_error__(self, method: Callable) -> None:
		"""
		Raises an error when a frozen method is called. Can be overridden. \n
		:param method: The frozen method that was called.
		:raises FrozenError: Always raises an error.
		"""
		raise FrozenError(
			Errors.CallingFrozenMethod.format(method.__name__, type(self).__qualname__)
		)

	def _set_frozen_state(self, frozen: bool, deep: bool) -> None:
		# Visits only the children of freezable objects. Therefore,
		# only the directly-accessible frozen members will be frozen/melted.
		# The underlying rule is every object is responsible for the behavior of its own children.
		self.__frozen__ = frozen

		if deep:
			is_freezable: bool

			for obj in get_descendents(self, visit_children=lambda: is_freezable):
				is_freezable = isinstance(obj, Freezable)

				if is_freezable:
					obj.__frozen__ = frozen

	@property
	def frozen(self) -> bool:
		"""
		Returns a value indicating whether the object is frozen.\n
		:return: The boolean value which is `True` is the object is frozen.
		"""
		return self.__frozen__

	def freeze(self, deep: bool = True) -> None:
		"""
		Freeze a Freezable object. If `deep` is `True`, also freeze its transitive Freezable descendents.\n
		:param deep: Determine whether to freeze the descendents or not.
		:raises PermissionError: If the object can not be frozen, i.e. `let_freeze` is `False`.
		"""
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.freeze.__qualname__))

	def melt(self, deep: bool = True) -> None:
		"""
		Unfreeze a Freezable object. If `deep` is `True`, also unfreeze its transitive Freezable descendents.\n
		:param deep: Determine whether to unfreeze the descendents or not.
		:raises PermissionError: If the object can not be unfrozen, i.e. `let_melt` is `False`.
		"""
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.melt.__qualname__))

	def copy(self, deep: bool = True, frozen: bool = None):
		"""
		Makes of copy of the object, and make the copy frozen or unfrozen.
		:param deep: If `True`, the copy will be deep; otherwise, it will be shallow.
		:param frozen: If `None`, the copy will inherit the object's frozen state;
		otherwise, its frozen state will be set accordingly.
		:return: The copy of the object.
		"""
		new_obj = copy.deepcopy(self) if deep else copy.copy(self)

		if frozen is not None:
			new_obj._set_frozen_state(frozen=frozen, deep=deep)

		return new_obj

	class View(View):
		"""
		The view base class of frozen, which is always frozen.
		"""
		__frozen__ = True


class FreezableClassDecorator(ClassDecorator['FreezableClassDecorator', 'FreezableMethodDecorator']):
	def __init__(self, let_freeze: bool = True, let_melt: bool = False):
		"""
		:param let_freeze: Let the object call the freeze method in cases other than `__init__` or `copy`
		:param let_melt: Same as `let_freeze`
		"""
		self.let_freeze = let_freeze
		self.let_melt = let_melt

	def __call__(self, cls, *_):
		"""
		Sanitize the class cls and returns a wrapper
		:param cls:
		:return:
		"""
		super().__call__(cls)

		class FreezableWrapper(cls, Freezable):
			__decorator__ = FreezableClassDecoratorData(self)

			def __init__(*args, **kwargs):
				# The reason why I do not use `self`:
				# We do not know the name of the `self` argument in `cls.__init__`;
				# All we know is it will be the first argument, i.e. args[0].
				# To avoid name conflict between `self` and `**kwargs`, I do not use `self`.
				Freezable.__init__(
					self=args[0],
					args=args[1:],
					kwargs=kwargs,
					wrapper_cls=FreezableWrapper,
				)

			@locked_in_view
			def freeze(self, deep: bool = True) -> None:
				if FreezableWrapper.__decorator__.let_freeze:
					return self._set_frozen_state(frozen=True, deep=deep)
				else:
					raise PermissionError(
						Errors.MethodNotCallable.format(FreezableWrapper.freeze.__name__, type(self).__qualname__)
					)

			@locked_in_view
			def melt(self, deep: bool = True) -> None:
				if FreezableWrapper.__decorator__.let_melt:
					return self._set_frozen_state(frozen=False, deep=deep)
				else:
					raise PermissionError(
						Errors.MethodNotCallable.format(FreezableWrapper.melt.__name__, type(self).__qualname__)
					)

		super().__call__(cls, FreezableWrapper)
		return FreezableWrapper


class FreezableClassDecoratorData(ClassDecoratorData):
	let_freeze: bool
	let_melt: bool

	def __init__(
			self,
			decorator: FreezableClassDecorator
	):
		self.let_freeze = decorator.let_freeze
		self.let_melt = decorator.let_melt


class FreezableMethodDecorator(MethodDecorator['FreezableClassDecorator', 'FreezableMethodDecorator']):
	def __call__(self, method: Callable, *_):
		super().__call__(method)
		
		def freezable_wrapper(*args, **kwargs):
			obj = args[0]

			if isinstance(obj, Freezable) or isinstance(obj, View):
				if obj.__frozen__:
					obj.__frozen_error__(method)
				else:
					return method(*args, **kwargs)
			else:
				raise DecorationUsageError(
					Errors.ClassNotFinalized.format(
						obj.__class__.__qualname__,
						freezableclass.__name__
					)
				)

		return super().__call__(method, freezable_wrapper)


def freezableclass(*args, let_freeze: bool = True, let_melt: bool = False):
	"""Fancy alternative to `freezable`, requires no parenthesis"""
	if args:
		cls = args[0]
		return freezable()(cls)
	else:
		return freezable(let_freeze=let_freeze, let_melt=let_melt)


def freezablemethod(*args):
	"""Fancy alternative to `freezable.method`, requires no parenthesis"""
	if args:
		method = args[0]
		return freezable.method()(method)
	else:
		return freezable.method()


class ModuleElements(ModuleElements):
	def __call__(self, let_freeze: bool = True, let_melt: bool = False) -> FreezableClassDecorator:
		"""
		Decorates a class to be freezable
		:param let_freeze: Let the user freeze the freezable object at will.
		If false, the `freeze()` method can not be called.
		:param let_melt: Let the user melt the freezable object at will. If false, the `melt()` method can not be called.
		:return: The class decorator.
		"""
		return FreezableClassDecorator(let_freeze=let_freeze, let_melt=let_melt)

	@staticmethod
	def method() -> FreezableMethodDecorator:
		return FreezableMethodDecorator()


FreezableClassDecorator._decorator_function = freezableclass
FreezableClassDecorator._class_wrapper_base = Freezable
FreezableClassDecorator._method_decorator = FreezableMethodDecorator
FreezableMethodDecorator._decorator_function = freezablemethod
FreezableMethodDecorator._class_decorator = FreezableClassDecorator
freezable = ModuleElements()
