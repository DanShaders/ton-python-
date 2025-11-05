import json
import pprint
import sys

from tl.tl_gen.lite_api.types.tonNode import TonNodeBlockIdExt
from tl.tl_gen.ton_api.types.pk import PkAes
from tl.tl_gen.ton_api.types.pub import PubUnenc
from tl.tl_gen.ton_api.types.id import IdConfigLocal
from tl.tl_gen.ton_api.types.catchain import CatchainConfigGlobal
from tl.tl_gen.ton_api.types.engine import EngineAdnl, EngineValidatorElectionBid, EngineValidatorConfig


with open('config.json') as f:
    config = json.load(f)

vc = EngineValidatorConfig.from_dict(config)
print(vc)
print(vc.to_json(indent=4))

a = EngineAdnl(id_=b'\x01\x02'*16, category_=3)
print(a.to_dict())
print(a.to_json())
print(a.from_dict(a.to_dict()))

v = EngineValidatorElectionBid(1, b'1234', b'1234', b'1234')
print(v.to_dict())
print(v.to_json())


block = TonNodeBlockIdExt(workchain_=-1, shard_=0, seqno_=123456, root_hash_=b'\x01'*32, file_hash_=b'\x02'*32)

print(block)
print(block.to_dict())
block2 = TonNodeBlockIdExt.from_dict(block.to_dict())

assert block == block2

pk = PkAes(key_=b'\x01'*32)

c = IdConfigLocal(id_=pk)
print(c)
print(c.to_dict())
c2 = IdConfigLocal.from_dict({'@type': 'id.config.local', 'id': {'@type': 'pk.aes', 'key': b'\x01'*32}})
print(c2)

assert c == c2

pubk = PubUnenc(data_=b'\x12'*32)


cg = CatchainConfigGlobal(tag_=b'123', nodes_=[pubk, pubk])
print(cg)
print(cg.to_dict())
cg2 = CatchainConfigGlobal.from_dict(cg.to_dict())
print(cg2)

assert cg == cg2


from tl.tl_gen.lite_api.functions.liteServer import LiteServerGetBlockHeaderRequest

req = LiteServerGetBlockHeaderRequest(id_=block, mode_=2)
print(req)
print(req.to_dict())
req2 = LiteServerGetBlockHeaderRequest.from_dict(req.to_dict())
print(req2)
assert req == req2


from tl.tl_gen.ton_api.types.adnl import AdnlPacketContents

pc = AdnlPacketContents(rand1_=b'\x01\x01', flags_=1, rand2_=b'\x01\x01', from__=pubk)
print(pc)
print(pc.to_dict())
pc2 = AdnlPacketContents.from_dict(pc.to_dict())
print(pc2)
assert pc == pc2

from tl.binary_reader import BinaryReader
from tl.tl_gen.lite_api.alltlobjects import tlobjects
reader = BinaryReader(block.to_bytes()[4:], tl_objects=tlobjects)  # skip tag
blk2 = TonNodeBlockIdExt.from_reader(reader)
print(blk2, block)
assert blk2 == block
