from __future__ import annotations
from .core import *


class Errors(Errors):
	NoLocksDefined = \
		"No keys have been defined for `{}`. " \
		"Use `lock_permissions` parameter to define the locks."
	NoKeysDefined = \
		"No keys have been defined for `{}`. " \
		"Use `keys` parameter to define the keys."
	CallingLockedMethod = \
		"`{}` method is locked with key '{}'."
	LockingNotAllowed = \
		"`{}` objects are not allowed to lock `{}` objects using '{}' key."
	UnlockingNotAllowed = \
		"`{}` objects are not allowed to unlock `{}` objects using '{}' key."
	UnrecognizedKey = \
		"Unrecognized key '{}'."


class LockedError(PermissionError):
	pass


class UnlockError(PermissionError):
	pass


class LockError(PermissionError):
	pass


def lockableclass(
		*args,
		lock_permissions: Dict[str, Optional[Set]] = None,
		unlock_permissions: Dict[str, Optional[Set]] = None
):
	if args:
		cls = args[0]
		return LockableClassDecorator()(cls)
	else:
		return LockableClassDecorator(lock_permissions=lock_permissions, unlock_permissions=unlock_permissions)


class Lockable(ClassWrapperBase['LockableClassDecoratorData']):
	def __init__(self, args: tuple, kwargs: dict, wrapper_cls: Type[Lockable]):
		self.__view = None
		ClassWrapperBase.__init__(self, args=args, kwargs=kwargs, wrapper_cls=wrapper_cls)

	def __load__(self, locks: Iterable[str] = None) -> None:
		self.__locks__ = set()

		if locks is not None and locks:
			for key in locks:
				self.lock(key)

	@staticmethod
	def _is_calling_class_valid(allowed_classes: Set[type] | None) -> Tuple[bool, List[type | None]]:
		calling_classes = []
		found = False

		for _, cls in trace_execution(allowed_classes):
			if cls is not None:
				found = next(
					(True for c in allowed_classes if issubclass(cls, c)),
					False
				)

				calling_classes.append(cls)

			if found:
				break

		calling_classes.append(None)
		return found, calling_classes

	def lock(self, key: str) -> None:
		"""
		Tries to lock the object with `key`;
		If the locker is not permitted to use the key, raises a `LockError`.\n
		:param key: The key to lock the object
		:return: None
		"""
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.lock.__qualname__))

	def unlock(self, key: str) -> None:
		"""
		Tries to unlock the object with `key`;
		If the locker is not permitted to use the key, raises a `LockError`.\n
		:param key: The key to unlock the object
		:return: None
		"""
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.unlock.__qualname__))

	def locked(self, key: str) -> bool:
		"""
		Returns true if the object is locked with `key`.\n
		:param key: The key to check
		:return: `True` if locked with `key`; `False`, otherwise.
		"""
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.locked.__qualname__))

	def __locked_error__(self, key: str, method: Callable) -> None:
		"""
		Throws an error when a locked method is called.\n
		:param key: The key that the method is locked with.
		:param method: The called method.
		:return:
		"""
		raise LockedError(Errors.CallingLockedMethod.format(method.__qualname__, key))

	def __lock_error__(self, key: str, calling_cls: type) -> None:
		"""
		Throws an error when a class tries to lock this without permission.\n
		:param key:
		:param calling_cls:
		:return:
		"""
		raise LockError(Errors.LockingNotAllowed.format(
			None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
		))

	def __unlock_error__(self, key: str, calling_cls: type) -> None:
		"""
		Throws an error when a class tries to unlock this without permission.
		:param key:
		:param calling_cls:
		:return: None
		"""
		raise UnlockError(Errors.UnlockingNotAllowed.format(
			None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
		))

	def __lock_key_error__(self, key: str):
		"""
		Throws an error when a class tries to unlock this with undefined key
		:param key:
		:return:
		"""
		raise KeyError(Errors.UnrecognizedKey.format(key))

	class View(View):
		__view_locks__: set = None

		def __init__(self, obj: Lockable):
			self.__view_locks__ = obj.__locks__.copy()

		@property
		def __locks__(self):
			return self.__view_locks__ | self._View__obj.__locks__


class LockableClassDecorator(ClassDecorator['LockableClassDecorator', 'LockableMethodDecorator']):
	def __init__(
			self,
			lock_permissions: Dict[str, Optional[Set]] = None,
			unlock_permissions: Dict[str, Optional[Set]] = None
	):
		"""
		Lockable decorator.\n
		:param lock_permissions: Example: {"key1": {Class1, Class2}, "key2: {Class2, Class3}}
		:param unlock_permissions: Same as `lock_permissions`
		"""
		if lock_permissions is None:
			raise ValueError(Errors.NoLocksDefined.format(self._decorator_function.__name__))
		elif isinstance(lock_permissions, dict):
			lock_permissions = lock_permissions.items()

		locks = set(k for k, v in lock_permissions)

		lock_permissions = dict(
			(k, {v} if isinstance(v, type) else set(v))
			for k, v in lock_permissions if v is not None
		)

		if unlock_permissions is None:
			unlock_permissions = lock_permissions
		else:
			if isinstance(unlock_permissions, dict):
				unlock_permissions = unlock_permissions.items()

			locks.update(k for k, v in unlock_permissions)

			unlock_permissions = dict(
				(k, {v} if isinstance(v, type) else set(v))
				for k, v in unlock_permissions if v is not None
			)

		self.locks: Set[str] = locks
		self.lock_permissions: DefaultDict[str, Optional[Set]] = defaultdict(lambda: None, lock_permissions)
		self.unlock_permissions: DefaultDict[str, Optional[Set]] = defaultdict(lambda: None, unlock_permissions)

	def __call__(self, cls, *_):
		super().__call__(cls)

		class LockableWrapper(cls, Lockable):
			__decorator__ = LockableClassDecoratorData(self, cls)

			def __init__(*args, **kwargs):
				# The reason why I do not use `self`:
				# We do not know the name of the `self` argument in `cls.__init__`;
				# All we know is it will be the first argument, i.e. args[0].
				# To avoid name conflict between `self` and `**kwargs`, I do not use `self`.
				Lockable.__init__(
					self=args[0],
					args=args[1:],
					kwargs=kwargs,
					wrapper_cls=LockableWrapper,
				)

			@locked_in_view
			def lock(self, key: str) -> None:
				if key in LockableWrapper.__decorator__.locks:
					if LockableWrapper.__decorator__.lock_permissions[key] is None:
						self.__locks__.add(key)
					else:
						found, calling_classes = self._is_calling_class_valid(
							LockableWrapper.__decorator__.lock_permissions[key]
						)

						if found:
							self.__locks__.add(key)
						if not found:
							self.__lock_error__(key, calling_classes[0])
				else:
					self.__lock_key_error__(key)

			@locked_in_view
			def unlock(self, key: str) -> None:
				if key in LockableWrapper.__decorator__.locks:
					if LockableWrapper.__decorator__.unlock_permissions[key] is None:
						self.__locks__.remove(key)
					else:
						found, calling_classes = self._is_calling_class_valid(
							LockableWrapper.__decorator__.unlock_permissions[key]
						)

						if found:
							try:
								self.__locks__.remove(key)
							except KeyError:
								pass
						else:
							self.__unlock_error__(key, calling_classes[0])
				else:
					self.__lock_key_error__(key)

			def locked(self, key: str) -> bool:
				if key in LockableWrapper.__decorator__.locks:
					return key in self.__locks__
				else:
					self.__lock_key_error__(key)

		return super().__call__(cls, LockableWrapper)


class LockableClassDecoratorData(ClassDecoratorData):
	locks: Set[str]
	lock_permissions: DefaultDict[str, Optional[Set]]
	unlock_permissions: DefaultDict[str, Optional[Set]]

	def __init__(
			self,
			decorator: LockableClassDecorator,
			cls: type
	):
		self.locks = decorator.locks
		self.lock_permissions = decorator.lock_permissions
		self.unlock_permissions = decorator.unlock_permissions

		for spec in decorator.method_specs:
			self.locks.update(spec.method_decorator.keys)

		for lock in self.lock_permissions:
			self.lock_permissions[lock].add(cls)

		for lock in self.unlock_permissions:
			self.unlock_permissions[lock].add(cls)

		if issubclass(cls, Lockable):
			for lock, cls_set in cls.__decorator__.lock_permissions.items():
				if lock not in self.lock_permissions:
					self.lock_permissions[lock] = cls_set

			for lock, cls_set in cls.__decorator__.unlock_permissions.items():
				if lock not in self.unlock_permissions:
					self.unlock_permissions[lock] = cls_set

			self.locks.update(cls.__decorator__.locks)


def lockablemethod(*args, keys: Iterable[str] = None):
	if args:
		method = args[0]
		return LockableMethodDecorator()(method)
	else:
		return LockableMethodDecorator(keys=keys)


class LockableMethodDecorator(MethodDecorator['LockableClassDecorator', 'LockableMethodDecorator']):
	def __init__(self, keys: Iterable[str] = None):
		if keys is not None:
			self._keys = frozenset(keys)
		else:
			raise ValueError(Errors.NoKeysDefined.format(self._decorator_function.__name__))

	def __call__(self, method: Callable, *_):
		super().__call__(method)

		def lockable_wrapper(*args, **kwargs):
			obj = args[0]

			if isinstance(obj, Lockable) or isinstance(obj, View):
				keys = self._keys.intersection(obj.__locks__)

				if keys:
					obj.__locked_error__(next(iter(keys)), method)
				else:
					return method(*args, **kwargs)
			else:
				raise DecorationUsageError(
					Errors.ClassNotFinalized.format(
						obj.__class__.__qualname__,
						lockableclass.__name__
					)
				)

		return super().__call__(method, lockable_wrapper)

	@property
	def keys(self):
		return self._keys


LockableClassDecorator._decorator_function = lockableclass
LockableClassDecorator._method_decorator = LockableMethodDecorator
LockableMethodDecorator._decorator_function = lockablemethod
LockableMethodDecorator._class_decorator = LockableClassDecorator
lockable = ModuleElements(mth=lockablemethod, cls=lockableclass)
