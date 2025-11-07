import re

from typing_extensions import override

from ....generator.utils import get_class_name


class TLArg:
    def __init__(self, name: str, arg_type: str, generic_definition: bool):
        """
        Initializes a new .tl argument
        :param name: The name of the .tl argument
        :param arg_type: The type of the .tl argument
        :param generic_definition: Is the argument a generic definition?
                                   (i.e. {X:Type})
        """
        self.name: str
        if name == 'self':
            self.name = 'is_self'
        elif name == 'from':
            self.name = 'from_'
        else:
            self.name = name

        # Default values
        self.is_vector: bool = False
        self.flag: str | None = None  # name of the flag to check if self is present
        self.skip_constructor_id: bool = False
        self.flag_index: int = -1  # bit index of the flag to check if self is present
        # self.cls: list[ParsedTLObject] | None = None

        # The type can be an indicator that other arguments will be flags
        self.flag_indicator: bool
        self.type: str
        self.is_generic: bool
        if arg_type == '#':
            self.flag_indicator = True
            self.type = 'int'
            self.is_generic = False
        else:
            self.flag_indicator = False
            self.is_generic = arg_type.startswith('!')
            # Strip the exclamation mark always to have only the name
            self.type = arg_type.lstrip('!')

            # The type may be a flag (FLAGS.IDX?REAL_TYPE)
            # FLAGS can be any name, but it should have appeared previously.
            flag_match = re.match(r'(\w+).(\d+)\?([\w<>.]+)', self.type)
            if flag_match:
                self.flag = flag_match.group(1)
                self.flag_index = int(flag_match.group(2))
                # Update the type to match the exact type, not the "flagged" one
                self.type = flag_match.group(3)

            # Then check if the type is a Vector<REAL_TYPE>
            vector_match = re.match(r'[Vv]ector<([\w\d.]+)>', self.type)
            if vector_match:
                self.is_vector = True

                # If the type's first letter is not uppercase, then
                # it is a constructor and we use (read/write) its ID
                self.use_vector_id: bool = self.type[0] == 'V'

                # Update the type to match the one inside the vector
                self.type = vector_match.group(1)

            # See use_vector_id. An example of such case is ipPort in
            # help.configSpecial
            if self.type.split('.')[-1][0].islower():
                self.skip_constructor_id = True
        # if self.type in ('Int128' or 'Int256'):
        #     self.type = 'bytes'

        self.generic_definition: bool = generic_definition

    def get_type_class_name(self):
        return get_class_name(self.type)

    def type_hint(self):
        cls = self.type
        # if '.' in cls:
        #     cls = snake_to_camel_case('_'.join(cls.split('.')))
        result = {
            'int': 'int',
            'long': 'int',
            'int64': 'int',
            'int32': 'int',
            'int53': 'int',
            'int128': 'bytes | str',
            'int256': 'bytes | str',
            'double': 'float',
            'string': 'str',
            'bytes': 'bytes | str',
            'Bool': 'bool',
            'true': 'bool',
        }.get(cls)
        if result is None:
            cls = self.get_type_class_name()
            if self.skip_constructor_id:
                result = f"'{cls} | None'"
            else:
                result = f"'Type{cls} | None'"
        if self.is_vector:
            result = f'list[{result}]'
            if self.flag:
                result = f'{result} | None'
        else:
            if self.flag:
                result = f"""'{result.replace("'", "")} | None'"""  # avoid 'T | None' | None

        return result

    def get_init_arg(self, value: str) -> str:
        if self.type in ('int128', 'int256', 'bytes'):
            if not self.is_vector:
                t = 'bytes' if not self.flag else 'bytes | None'
                return f'self.{self.name}: {t} = base64.b64decode({value}) if isinstance({value}, str) else {value}'
            else:
                t = 'list[bytes]' if not self.flag else 'list[bytes] | None'
                return f'self.{self.name}: {t} = [base64.b64decode(x) if isinstance(x, str) else x for x in {value}]'
        else:
            return f'self.{self.name}: {self.type_hint()} = {value}'

    def default_value(self):
        if self.flag:
            return "None"
        if self.is_vector:
            return "[]"
        elif self.type in ('int', 'long', 'int64', 'int32', 'int53'):
            return "0"
        elif self.type in ('bytes', 'int128', 'int256'):
            return "b''"
        elif self.type == 'string':
            return "''"
        elif self.type == 'double':
            return "0.0"
        elif self.type == 'Bool':
            return "False"
        elif self.type == 'true':
            return "True"
        else:
            return "None"

    def real_type(self):
        # Find the real type representation by updating it as required
        real_type = self.type
        if self.flag_indicator:
            real_type = '#'

        if self.is_vector:
            if self.use_vector_id:
                real_type = 'Vector<{}>'.format(real_type)
            else:
                real_type = 'vector<{}>'.format(real_type)

        if self.is_generic:
            real_type = '!{}'.format(real_type)

        if self.flag:
            real_type = '{}.{}?{}'.format(self.flag, self.flag_index, real_type)

        return real_type

    @override
    def __str__(self):
        name = self.orig_name()
        if self.generic_definition:
            return '{{{}:{}}}'.format(name, self.real_type())
        else:
            return '{}:{}'.format(name, self.real_type())

    @override
    def __repr__(self):
        return str(self)

    def orig_name(self):
        return self.name.replace('is_self', 'self').strip('_')

    def to_dict(self):
        return {
            'name': self.orig_name(),
            'type': self.real_type(),
        }
