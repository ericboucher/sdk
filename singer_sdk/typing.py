"""Classes and functions to streamline JSONSchema typing.

Usage example:
----------
```py
    jsonschema = PropertiesList(
        Property("id", IntegerType, required=True),
        Property("name", StringType),
        Property("tags", ArrayType(StringType)),
        Property("ratio", NumberType),
        Property("days_active", IntegerType),
        Property("updated_on", DateTimeType),
        Property("is_deleted", BooleanType),
        Property(
            "author",
            ObjectType(
                Property("id", StringType),
                Property("name", StringType),
            )
        ),
        Property(
            "groups",
            ArrayType(
                ObjectType(
                    Property("id", StringType),
                    Property("name", StringType),
                )
            )
        ),
    ).to_dict()
```

Note:
----
- These helpers are designed to output json in the traditional Singer dialect.
- Due to the expansive set of capabilities within the JSONSchema spec, there may be
  other valid implementations which are not syntactically identical to those generated
  here.

"""
from typing import Any, Dict, Generic, List, Tuple, Type, TypeVar, Union, cast

import sqlalchemy
from jsonschema import validators

from singer_sdk.helpers._classproperty import classproperty
from singer_sdk.helpers._typing import append_type, get_datelike_property_type


def extend_validator_with_defaults(validator_class):  # noqa
    """Fill in defaults, before validating with the provided JSON Schema Validator.

    See https://python-jsonschema.readthedocs.io/en/latest/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance  # noqa
    for details.
    """
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):  # noqa
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


class JSONTypeHelper(object):
    """Type helper base class for JSONSchema types."""

    @classproperty
    def type_dict(cls) -> dict:
        """Return dict describing the type.

        Raises:
            NotImplementedError: If the derived class does not override this method.
        """
        raise NotImplementedError()

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            A JSON Schema dictionary describing the object.
        """
        return cast(dict, self.type_dict)


class DateTimeType(JSONTypeHelper):
    """DateTime type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {
            "type": ["string"],
            "format": "date-time",
        }


class DateType(JSONTypeHelper):
    """DateTime type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {
            "type": ["string"],
            "format": "date",
        }


class StringType(JSONTypeHelper):
    """String type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {"type": ["string"]}


class BooleanType(JSONTypeHelper):
    """Boolean type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {"type": ["boolean"]}


class IntegerType(JSONTypeHelper):
    """Integer type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {"type": ["integer"]}


class NumberType(JSONTypeHelper):
    """Number type."""

    @classproperty
    def type_dict(cls) -> dict:
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {"type": ["number"]}


W = TypeVar("W", bound=JSONTypeHelper)


class ArrayType(JSONTypeHelper, Generic[W]):
    """Array type."""

    def __init__(self, wrapped_type: W) -> None:
        """Initialize Array type with wrapped inner type.

        Args:
            wrapped_type: JSON Schema item type inside the array.
        """
        self.wrapped_type = wrapped_type

    @property
    def type_dict(self) -> dict:  # type: ignore  # OK: @classproperty vs @property
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return {"type": "array", "items": self.wrapped_type.type_dict}


class Property(JSONTypeHelper, Generic[W]):
    """Generic Property. Should be nested within a `PropertiesList`."""

    def __init__(
        self,
        name: str,
        wrapped: Union[W, Type[W]],
        required: bool = False,
        default: Any = None,
        description: str = None,
    ) -> None:
        """Initialize Property object.

        Args:
            name: Property name.
            wrapped: JSON Schema type of the property.
            required: Whether this is a required property.
            default: Default value in the JSON Schema.
            description: Long-text property description.
        """
        self.name = name
        self.wrapped = wrapped
        self.optional = not required
        self.default = default
        self.description = description

    @property
    def type_dict(self) -> dict:  # type: ignore  # OK: @classproperty vs @property
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return cast(dict, self.wrapped.type_dict)

    def to_dict(self) -> dict:
        """Return a dict mapping the property name to its definition.

        Returns:
            A JSON Schema dictionary describing the object.
        """
        type_dict = self.type_dict
        if self.optional:
            type_dict = append_type(type_dict, "null")
        if self.default:
            type_dict.update({"default": self.default})
        if self.description:
            type_dict.update({"description": self.description})
        return {self.name: type_dict}


class ObjectType(JSONTypeHelper):
    """Object type, which wraps one or more named properties."""

    def __init__(self, *properties: Property) -> None:
        """Initialize ObjectType from its list of properties.

        Args:
            properties: TODO
        """
        self.wrapped: List[Property] = list(properties)

    @property
    def type_dict(self) -> dict:  # type: ignore  # OK: @classproperty vs @property
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        merged_props = {}
        required = []
        for w in self.wrapped:
            merged_props.update(w.to_dict())
            if not w.optional:
                required.append(w.name)
        result = {"type": "object", "properties": merged_props}
        if required:
            result["required"] = required
        return result


class CustomType(JSONTypeHelper):
    """Accepts an arbitrary JSON Schema dictionary."""

    def __init__(self, jsonschema_type_dict: dict) -> None:
        """Initialize JSONTypeHelper by importing an existing JSON Schema type.

        Args:
            jsonschema_type_dict: TODO
        """
        self._jsonschema_type_dict = jsonschema_type_dict

    @property
    def type_dict(self) -> dict:  # type: ignore  # OK: @classproperty vs @property
        """Get type dictionary.

        Returns:
            A dictionary describing the type.
        """
        return self._jsonschema_type_dict


class PropertiesList(ObjectType):
    """Properties list. A convenience wrapper around the ObjectType class."""

    def items(self) -> List[Tuple[str, Property]]:
        """Get wrapped properties.

        Returns:
            List of (name, property) tuples.
        """
        return [(p.name, p) for p in self.wrapped]

    def append(self, property: Property) -> None:
        """Append a property to the property list.

        Args:
            property: Property to add
        """
        self.wrapped.append(property)


def to_jsonschema_type(
    from_type: Union[
        str, sqlalchemy.types.TypeEngine, Type[sqlalchemy.types.TypeEngine]
    ]
) -> dict:
    """Return the JSON Schema dict that describes the sql type.

    Args:
        from_type: The SQL type as a string or as a TypeEngine. If a TypeEngine is
            provided, it may be provided as a class or a specific object instance.

    Raises:
        ValueError: If the `from_type` value is not of type `str` or `TypeEngine`.

    Returns:
        A compatible JSON Schema type definition.
    """
    sqltype_lookup: Dict[str, dict] = {
        # NOTE: This is an ordered mapping, with earlier mappings taking precedence.
        #       If the SQL-provided type contains the type name on the left, the mapping
        #       will return the respective singer type.
        "timestamp": DateTimeType.type_dict,
        "datetime": DateTimeType.type_dict,
        "date": DateType.type_dict,
        "int": IntegerType.type_dict,
        "number": NumberType.type_dict,
        "decimal": NumberType.type_dict,
        "double": NumberType.type_dict,
        "float": NumberType.type_dict,
        "string": StringType.type_dict,
        "text": StringType.type_dict,
        "char": StringType.type_dict,
        "bool": BooleanType.type_dict,
        "variant": StringType.type_dict,
    }
    if isinstance(from_type, str):
        type_name = from_type
    elif isinstance(from_type, sqlalchemy.types.TypeEngine):
        type_name = type(from_type).__name__
    elif isinstance(from_type, type) and issubclass(
        from_type, sqlalchemy.types.TypeEngine
    ):
        type_name = from_type.__name__
    else:
        raise ValueError("Expected `str` or a SQLAlchemy `TypeEngine` object or type.")

    # Look for the type name within the known SQL type names:
    for sqltype, jsonschema_type in sqltype_lookup.items():
        if sqltype.lower() in type_name.lower():
            return jsonschema_type

    return sqltype_lookup["string"]  # safe failover to str


def _jsonschema_type_check(jsonschema_type: dict, type_check: Tuple[str]) -> bool:
    """Return True if the jsonschema_type supports the provided type.

    Args:
        jsonschema_type: The type dict.
        type_check: A tuple of type strings to look for.

    Returns:
        True if the schema suports the type.
    """
    if "type" in jsonschema_type:
        if isinstance(jsonschema_type["type"], (list, tuple)):
            for t in jsonschema_type["type"]:
                if t in type_check:
                    return True
        else:
            if jsonschema_type.get("type") in type_check:
                return True

    if any((t in type_check for t in jsonschema_type.get("anyOf", ()))):
        return True

    return False


def to_sql_type(jsonschema_type: dict) -> Type[sqlalchemy.types.TypeEngine]:
    """Convert JSON Schema type to a SQL type.

    Args:
        jsonschema_type: The JSON Schema object.

    Returns:
        The SQL type.
    """
    if _jsonschema_type_check(jsonschema_type, ("string",)):
        datelike_type = get_datelike_property_type(jsonschema_type)
        if datelike_type:
            if datelike_type == "date-time":
                return sqlalchemy.types.DATETIME
            if datelike_type in "time":
                return sqlalchemy.types.TIME
            if datelike_type == "date":
                return sqlalchemy.types.DATE

        return sqlalchemy.types.VARCHAR

    if _jsonschema_type_check(jsonschema_type, ("integer",)):
        return sqlalchemy.types.INTEGER
    if _jsonschema_type_check(jsonschema_type, ("number",)):
        return sqlalchemy.types.DECIMAL
    if _jsonschema_type_check(jsonschema_type, ("boolean",)):
        return sqlalchemy.types.BOOLEAN

    if _jsonschema_type_check(jsonschema_type, ("object",)):
        return sqlalchemy.types.VARCHAR

    if _jsonschema_type_check(jsonschema_type, ("array",)):
        return sqlalchemy.types.VARCHAR

    return sqlalchemy.types.VARCHAR
