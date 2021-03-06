import base64
from typing import Dict, Tuple, Optional

from benji.aes_keywrap import aes_wrap_key, aes_unwrap_key

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from benji.transform.base import TransformBase
from benji.utils import derive_key
from benji.config import Config, ConfigDict


class Transform(TransformBase):

    def __init__(self, *, config: Config, name: str, module_configuration: ConfigDict) -> None:
        super().__init__(config=config, name=name, module_configuration=module_configuration)

        master_key: Optional[bytes] = Config.get_from_dict(module_configuration, 'masterKey', None, types=bytes)
        if master_key is not None:
            if len(master_key) != 32:
                raise ValueError('Key masterKey has the wrong length. It must be 32 bytes long.')

            self._master_key = master_key
        else:
            kdf_salt: bytes = Config.get_from_dict(module_configuration, 'kdfSalt', types=bytes)
            kdf_iterations: int = Config.get_from_dict(module_configuration, 'kdfIterations', types=int)
            password: str = Config.get_from_dict(module_configuration, 'password', types=str)

            self._master_key = derive_key(salt=kdf_salt, iterations=kdf_iterations, key_length=32, password=password)

    def encapsulate(self, *, data: bytes) -> Tuple[Optional[bytes], Optional[Dict]]:
        envelope_key = get_random_bytes(32)
        envelope_iv = get_random_bytes(16)
        encryptor = AES.new(envelope_key, AES.MODE_GCM, nonce=envelope_iv)

        envelope_key = aes_wrap_key(self._master_key, envelope_key)

        materials = {
            'envelope_key': base64.b64encode(envelope_key).decode('ascii'),
            'iv': base64.b64encode(envelope_iv).decode('ascii'),
        }

        return encryptor.encrypt(data), materials

    def decapsulate(self, *, data: bytes, materials: Dict) -> bytes:
        for key in ['envelope_key', 'iv']:
            if key not in materials:
                raise KeyError('Encryption materials are missing required key {}.'.format(key))

        envelope_key = materials['envelope_key']
        iv = materials['iv']

        envelope_key = base64.b64decode(envelope_key)
        iv = base64.b64decode(iv)

        if len(iv) != 16:
            raise ValueError('Encryption materials IV iv has wrong length of {}. It must be 16 bytes long.'.format(
                len(iv)))

        envelope_key = aes_unwrap_key(self._master_key, envelope_key)
        if len(envelope_key) != 32:
            raise ValueError(
                'Encryption materials key envelope_key has wrong length of {}. It must be 32 bytes long.'.format(
                    len(envelope_key)))

        decryptor = AES.new(envelope_key, AES.MODE_GCM, nonce=iv)
        return decryptor.decrypt(data)
