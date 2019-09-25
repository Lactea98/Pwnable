#include <stdio.h>

void callme(int a){
	int b = a;
	printf("%d\n",b);
}

int main(){
	callme(1);	
}
