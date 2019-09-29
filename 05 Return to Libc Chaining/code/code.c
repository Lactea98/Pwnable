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
