# Pwn Basic Challenge

## Description
A simple buffer overflow challenge.

## Files
- `vuln.c` - Vulnerable source code
- `vuln` - Compiled binary (64-bit, no PIE, no canary)

## Flag Format
`flag{.*}`

## Hints
1. Check buffer size vs input size
2. Look for win function
3. Use GDB to analyze