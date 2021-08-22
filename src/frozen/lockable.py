from .core import *


class LockableClass(ForwardDec, ClassDecorator):
	pass


class LockableMethod(ForwardDec, MethodDecorator):
	pass


MyClassDecorator = ClassDecorator[LockableClass, LockableMethod]
MyMethodDecorator = MethodDecorator[LockableClass, LockableMethod]


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
		return LockableClass()(cls)
	else:
		return LockableClass(lock_permissions=lock_permissions, unlock_permissions=unlock_permissions)


class LockableClass(MyClassDecorator):
	def __init__(
			self,
			lock_permissions: Dict[str, Optional[Set]] = None,
			unlock_permissions: Dict[str, Optional[Set]] = None
	):
		"""

		:param lock_permissions: Example: {"key1": {Class1, Class2}, "key2: {Class2, Class3}}
		:param unlock_permissions: Same as `lock_permissions`
		"""
		if lock_permissions is None:
			raise ValueError(Errors.NoLocksDefined.format(self._decorator_function))
		elif isinstance(lock_permissions, dict):
			lock_permissions = lock_permissions.items()

		lock_permissions = dict(
			(k, {v} if isinstance(v, type) else set(v))
			for k, v in lock_permissions if v is not None
		)

		if unlock_permissions is None:
			unlock_permissions = lock_permissions
		else:
			if isinstance(unlock_permissions, dict):
				unlock_permissions = unlock_permissions.items()

			unlock_permissions = dict(
				(k, {v} if isinstance(v, type) else set(v))
				for k, v in unlock_permissions if v is not None
			)

		self._locks = set(lock_permissions.keys() | unlock_permissions.keys())
		self._lock_permissions: Dict = defaultdict(lambda: None, lock_permissions)
		self._unlock_permissions: Dict = defaultdict(lambda: None, unlock_permissions)

	def __call__(self, cls, *_):
		super().__call__(cls)

		for spec in self._method_specs:
			self._locks.update(spec.method_decorator.keys)

		class LockableWrapper(cls, MyClassDecorator.ClassWrapper):
			def __init__(self, *args, **kwargs):
				# This will call LockableWrapper.__construct__ and then cls.__init__
				MyClassDecorator.ClassWrapper.__init__(self, LockableWrapper, cls, *args, **kwargs)

			def __construct__(self, locks: Iterable[str] = None):
				self.__locks__ = set()

				if locks is not None and locks:
					for key in locks:
						self.lock(key)

			def __locked_error__(self, key: str, method: Callable):
				"""
				Throws an error when a locked method is called
				:param key:
				:param method:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__locked_error__(key=str, method=method)
				except AttributeError:
					raise LockedError(Errors.CallingLockedMethod.format(method.__qualname__, key)) from None

			def __lock_error__(self, key: str, calling_cls):
				"""
				Throws an error when a class tries to lock this without permission
				:param key:
				:param calling_cls:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__lock_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise LockError(Errors.LockingNotAllowed.format(
						None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
					)) from None

			def __unlock_error__(self, key: str, calling_cls):
				"""
				Throws an error when a class tries to unlock this without permission.
				:param key:
				:param calling_cls:
				:return: None
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__unlock_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise UnlockError(Errors.UnlockingNotAllowed.format(
						None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
					)) from None

			def __lock_key_error__(self, key: str):
				"""
				Throws an error when a class tries to unlock this with undefined key
				:param key:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__lock_key_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise KeyError(Errors.UnrecognizedKey.format(key)) from None

			# noinspection PyMethodParameters
			@locked_in_view
			def lock(myself, key: str) -> None:
				"""
				Tries to lock the object with `key`;
				If the locker is not permitted to use the key, raises a `LockError`.
				:param key: The key to lock the object
				:return: None
				"""
				if key in self._locks:
					if self._lock_permissions[key] is None:
						myself.__locks__.add(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._lock_permissions[key]):
							if _class is not None:
								found = next(
									(True for c in self._lock_permissions[key] if issubclass(_class, c)),
									False
								)

								if calling_cls is None:
									calling_cls = _class

								if found:
									myself.__locks__.add(key)
									break

						if not found:
							myself.__lock_error__(key, calling_cls)
				else:
					myself.__lock_key_error__(key)

			# noinspection PyMethodParameters
			@locked_in_view
			def unlock(myself, key: str) -> None:
				if key in self._locks:
					if self._unlock_permissions[key] is None:
						myself.__locks__.remove(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._unlock_permissions[key]):
							if _class is not None:
								calling_cls = _class
								found = next(
									(True for c in self._unlock_permissions[key] if issubclass(_class, c)),
									False
								)

								if found:
									myself.__locks__.remove(key)
									break

						if not found:
							myself.__unlock_error__(key, calling_cls)
				else:
					myself.__lock_key_error__(key)

			# noinspection PyMethodParameters
			def locked(myself, key: str) -> bool:
				"""
				Returns true if the object is locked with `key`
				:param key:
				:return:
				"""
				if key in self._locks:
					return key in myself.__locks__
				else:
					myself.__lock_key_error__(key)

			def view(self):
				return self if isinstance(self, View) else LockableView(self)

		class LockableView(View):
			__locks__: set

			def __init__(self, obj: LockableWrapper):
				View.__init__(self, obj)
				self.__locks__ = obj.__locks__

		for lock in self._lock_permissions:
			self._lock_permissions[lock].add(cls)

		for lock in self._unlock_permissions:
			self._unlock_permissions[lock].add(cls)

		return super().__call__(cls, LockableWrapper)


def lockablemethod(*args, keys: Set = None):
	if args:
		method = args[0]
		return LockableMethod()(method)
	else:
		return LockableMethod(keys=keys)


class LockableMethod(MyMethodDecorator):
	def __init__(self, keys: Set = None):
		if keys is not None:
			self._keys = frozenset(keys)
		else:
			raise ValueError(Errors.NoKeysDefined.format(self._decorator_function.__name__))

	def __call__(self, method: Callable, *_):
		super().__call__(method)

		def lockable_wrapper(myself, *args, **kwargs):
			if isinstance(myself, View):
				# noinspection PyProtectedMember
				locks = myself.__locks__ | myself._View__obj.__locks__
			else:
				locks = myself.__locks__

			keys = self._keys.intersection(locks)

			if keys:
				myself.__locked_error__(next(iter(keys)), method)
			else:
				return method(myself, *args, **kwargs)

		return super().__call__(method, lockable_wrapper)

	@property
	def keys(self):
		return self._keys


LockableClass._decorator_function = lockableclass
LockableClass._method_decorator = LockableMethod
LockableMethod._decorator_function = lockablemethod
LockableMethod._class_decorator = LockableClass
lockable = ModuleElements(mth=lockablemethod, cls=lockableclass)
Lockable = ClassDecorator[LockableClass, LockableMethod].ClassWrapper
