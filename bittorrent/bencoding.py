from collections import OrderedDict

TOKEN_INTEGER = b'i'

TOKEN_LIST = b'l'

TOKEN_DICT = b'd'

TOKEN_END = b'e'

TOKEN_STRING_SEPARATOR = b':'

class Decoder:
    """
    A class to decode bencoded data
    """
    
    def __init__(self, data: bytes):
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        self._data = data
        self._index = 0
        
    def decode(self):
        """
        Decode the data
        
        :return python object representation of the data
        """
        c = self._peek()
        if c is None:
            raise EOFError("Unexpected end of data")
        elif c == TOKEN_INTEGER:
            self._consume()
            return self._decode_int()
        elif c == TOKEN_LIST:
            self._consume()
            return self._decode_list()
        elif c == TOKEN_DICT:
            self._consume()
            return self._decode_dict()
        elif c == TOKEN_END:
            return None
        elif c in b'01234567899':
            return self._decode_string()
        else:
            raise ValueError(f"Unexpected token {c} {str(self._index)}")
        
    def _peek(self):
        """
        Peek the next byte in the data
        
        :return the next byte in the data or None
        """
        if self._index + 1 >= len(self._data):
            return None
        return self._data[self._index: self._index + 1]
    
    def _consume(self):
        """
        Consume the next byte in the data
        """
        self._index += 1
        
    def _read(self, length: int) -> bytes:
        """
        Read the next length bytes in the data
        
        :param length: the number of bytes to read
        :return the bytes read
        """
        if self._index + length > len(self._data):
            raise IndexError('Cannot read {0} bytes from current position {1}'
                             .format(str(length), str(self._index)))
        res = self._data[self._index:self._index+length]
        self._index += length
        return res
    
    def _read_until(self, token: bytes) -> bytes:
        """
        Read until the token is found in the data
        
        :param token: the token to look for
        :return the bytes read
        """
        try:
            index = self._data.index(token, self._index)
            result = self._data[self._index:index]
            self._index = index + 1
            return result
        except ValueError:
            raise RuntimeError(f"Token {token} not found")
    
    def _decode_int(self) -> int:
        """
        Decode an integer
        
        :return the integer
        """
        return int(self._read_until(TOKEN_END))
    
    def _decode_list(self) -> list:
        """
        Decode a list
        
        :return the list
        """
        res = []
        while self._data[self._index: self._index + 1] != TOKEN_END:
            res.append(self.decode())
        self._consume()
        return res
    
    def _decode_dict(self):
        """
        Decode a dist
        
        :return the dict
        """
        res = OrderedDict()
        while self._data[self._index: self._index + 1] != TOKEN_END:
            key = self.decode()
            value = self.decode()
            res[key] = value
        self._consume()
        return res
    
    def _decode_string(self):
        bytes_to_read = int(self._read_until(TOKEN_STRING_SEPARATOR))
        data = self._read(bytes_to_read)
        return data
    
class Encoder:
    """
    A class to encode python objects to bencoded data
    
    Supported python types are:
    - str
    - int
    - list
    - dict
    - bytes
    
    Any other type will be ignored
    """
    
    def __init__(self, data):
        self._data = data
        
    def encode(self) -> bytes:
        """Encode python objects to bencoded data

        Returns:
            bytes: Bencoded binary data
        """
        return self.encode_next(self._data)
    
    def encode_next(self, data):
        if type(data) == str:
            return self._encode_string(data)
        elif type(data) == int:
            return self._encode_int(data)
        elif type(data) == list:
            return self._encode_list(data)
        elif type(data) == dict or type(data) == OrderedDict:
            return self._encode_dict(data)
        elif type(data) == bytes:
            return self._encode_bytes(data)
        else:
            return None

    def _encode_int(self, value):
        return str.encode('i' + str(value) + 'e')

    def _encode_string(self, value: str):
        res = str(len(value)) + ':' + value
        return str.encode(res)

    def _encode_bytes(self, value: str):
        result = bytearray()
        result += str.encode(str(len(value)))
        result += b':'
        result += value
        return result

    def _encode_list(self, data):
        result = bytearray('l', 'utf-8')
        result += b''.join([self.encode_next(item) for item in data])
        result += b'e'
        return result

    def _encode_dict(self, data: dict) -> bytes:
        result = bytearray('d', 'utf-8')
        for k, v in data.items():
            key = self.encode_next(k)
            value = self.encode_next(v)
            if key and value:
                result += key
                result += value
            else:
                raise RuntimeError('Bad dict')
        result += b'e'
        return result