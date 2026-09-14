#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void win() {
    printf("flag{pwn_basic_buffer_overflow_exploited}\\n");
    exit(0);
}

void vulnerable() {
    char buffer[64];
    printf("Enter your input: ");
    fflush(stdout);
    gets(buffer);
    printf("You entered: %s\\n", buffer);
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stdin, NULL, _IONBF, 0);
    vulnerable();
    return 0;
}