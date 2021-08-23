from __future__ import annotations

from .core import *
import copy


class Errors(Errors):
	"""
	List of error messages in this module.
	:cvar InconsistentCopyMethod: Error message for when the decorated class has an inconsistent signature.
	:cvar CallingFrozenMethod: Error message for when a frozen method is called.
	:cvar MethodNotCallable: Error message for when a `freeze` or `melt` is not allowed to be called.
	"""
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
		return FreezableClassDecorator()(cls)
	else:
		return FreezableClassDecorator(let_freeze=let_freeze, let_melt=let_melt)


class Freezable(ClassWrapperBase):
	def __init__(self, args, kwargs, wrapper_cls: Type[Freezable], decorator: FreezableClassDecorator):
		self.__decorator = decorator
		self.__view = None
		ClassWrapperBase.__init__(self, args=args, kwargs=kwargs, wrapper_cls=wrapper_cls)

	def __load__(self, frozen: bool = False):
		self.__frozen__ = frozen

		if self.__frozen__:
			self.__set_frozen_state(frozen=True, deep=False)

	def __frozen_error__(self, method: Callable) -> None:
		"""
		Raises an error when a frozen method is called. Can be overridden. \n
		:param method: The frozen method that was called.
		:raises FrozenError: Always raises an error.
		"""
		raise FrozenError(
			Errors.CallingFrozenMethod.format(method.__name__, type(self).__qualname__)
		) from None

	def __set_frozen_state(self, frozen: bool, deep: bool) -> None:
		self.__frozen__ = frozen

		if deep:
			visit_children: bool

			for obj in get_object_descendents(self, visit_children=lambda: visit_children):
				visit_children = isinstance(obj, Freezable)

				if visit_children:
					obj.__frozen__ = frozen

	@property
	def frozen(self) -> bool:
		"""
		Returns a value indicating whether the object is frozen.\n
		:return: The boolean value which is `True` is the object is frozen.
		"""
		return self.__frozen__

	@locked_in_view
	def freeze(self, deep: bool = True) -> None:
		"""
		Freeze a Freezable object. If `deep` is `True`, also freeze its transitive Freezable descendents.\n
		:param deep: Determine whether to freeze the descendents or not.
		:raises PermissionError: If the object can not be frozen, i.e. `let_freeze` is `False`.
		"""
		if self.__decorator.let_freeze:
			return self.__set_frozen_state(frozen=True, deep=deep)
		else:
			raise PermissionError(
				Errors.MethodNotCallable.format(Freezable.freeze.__name__, type(self).__qualname__)
			)

	@locked_in_view
	def melt(self, deep: bool = True):
		"""
		Unfreeze a Freezable object. If `deep` is `True`, also unfreeze its transitive Freezable descendents.\n
		:param deep: Determine whether to unfreeze the descendents or not.
		:raises PermissionError: If the object can not be unfrozen, i.e. `let_melt` is `False`.
		"""
		if self.__decorator.let_melt:
			return self.__set_frozen_state(frozen=False, deep=deep)
		else:
			raise PermissionError(
				Errors.MethodNotCallable.format(Freezable.melt.__name__, type(self).__qualname__)
			)

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
			new_obj.__set_frozen_state(frozen=frozen, deep=deep)

		return new_obj

	def view(self):
		if self.__view is None:
			self.__view = FreezableView(self)

		return self.__view


class FreezableView(View):
	def __init__(self, obj: Freezable):
		View.__init__(self, obj)


class FreezableClassDecorator(ClassDecorator[b'FreezableClassDecorator', b'FreezableMethodDecorator']):
	def __init__(self, let_freeze: bool = True, let_melt: bool = False):
		"""
		:param let_freeze: Let the object call the freeze method in cases other than `__init__` or `copy`
		:param let_melt: Same as `let_freeze`
		"""
		self._let_freeze = let_freeze
		self._let_melt = let_melt

	@property
	def let_freeze(self):
		return self._let_freeze

	@property
	def let_melt(self):
		return self._let_melt

	def __call__(self, cls, *_):
		"""
		Sanitize the class cls and returns a wrapper
		:param cls:
		:return:
		"""
		super().__call__(cls)

		# try:  # if cls.copy does not exist it will set is_copy_callable to False
		# 	is_copy_callable = isinstance(cls.copy, Callable)
		# except AttributeError:
		# 	is_copy_callable = False
		#
		# if is_copy_callable:
		# 	cls_spec = inspect.getfullargspec(cls.copy)
		# 	self_spec = inspect.getfullargspec(self.copy)
		#
		# 	if (
		# 			(len(cls_spec.args) == 0 and cls_spec.varargs is None) or  # check if the method has a 'self' parameter
		# 			(self_spec.args[1] not in cls_spec.args and cls_spec.varkw is None)  # check if 'deep' exists as a parameter
		# 	):
		# 		raise ValueError(Errors.InconsistentCopyMethod.format(cls.__qualname__))

		class FreezableWrapper(cls, Freezable):
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
					decorator=self,
				)

		return super().__call__(cls, FreezableWrapper)


def freezablemethod(*args):
	if args:
		method = args[0]
		return FreezableMethodDecorator()(method)
	else:
		return FreezableMethodDecorator()


class FreezableMethodDecorator(MethodDecorator[b'FreezableClassDecorator', b'FreezableMethodDecorator']):
	def __call__(self, method: Callable, *_):
		super().__call__(method)
		
		def freezable_wrapper(myself, *args, **kwargs):
			if isinstance(myself, View):
				# noinspection PyProtectedMember
				myself._View__obj.__frozen_error__(method)
			elif myself.__frozen__:
				myself.__frozen_error__(method)
			else:
				return method(myself, *args, **kwargs)

		return super().__call__(method, freezable_wrapper)


FreezableClassDecorator._decorator_function = freezableclass
FreezableClassDecorator._method_decorator = FreezableMethodDecorator
FreezableMethodDecorator._decorator_function = freezablemethod
FreezableMethodDecorator._class_decorator = FreezableClassDecorator
freezable = ModuleElements(mth=freezablemethod, cls=freezableclass)
