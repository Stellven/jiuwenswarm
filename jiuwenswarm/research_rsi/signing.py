"""Ed25519 over a pinned canonical signing profile, separate from artifact hashes."""
import base64
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat


SIGNING_PROFILE='ai4r-ed25519-json:1'


def signing_bytes(record):
    return json.dumps({k:v for k,v in record.items() if k!='signature'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def verify(record,public_key,key_id):
    if record.get('signer_key_id')!=key_id:raise ValueError('untrusted signature identity')
    try:
        text=record['signature']
        if not isinstance(text,str) or len(text)!=86 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in text):raise ValueError('invalid signature encoding')
        signature=base64.urlsafe_b64decode(text+'==')
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature,signing_bytes(record))
    except Exception:raise ValueError('invalid evidence signature') from None


class Signer:
    def __init__(self,key,key_id):self.key,self.key_id=key,key_id
    @classmethod
    def generate(cls,key_id):return cls(Ed25519PrivateKey.generate(),key_id)
    def public_bytes(self):return self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    def sign(self,record):
        value={**record,'signer_key_id':self.key_id};value.pop('signature',None)
        value['signature']=base64.urlsafe_b64encode(self.key.sign(signing_bytes(value))).decode('ascii').rstrip('=')
        return value
