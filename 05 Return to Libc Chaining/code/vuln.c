#include <stdio.h>

int main(){
	char buf[50];
	read(0,buf,100);
	printf("%s\n",buf);
}
