#include <stdio.h>

int main(){
	char buf[100];
	read(0,buf,200);
	printf("%s\n",buf);
}
