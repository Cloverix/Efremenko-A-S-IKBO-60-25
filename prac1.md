## Задача 2
cat protocols | awk '{print $2, $1}' | sort -r | tail -5

## Задача 3
Код bash:
#!/usr/bin/bash

```
str=$1
len=$(( ${#str} + 4 ))
for (( i = 0; i < len; i++ )); do
        if (( i == 0 || i == len - 1 )); then
                echo -n +
        else
                echo -n -
        fi
done
printf '\n| %s |\n' "$str"
for (( i = 0; i < len; i++ )); do
        if (( i == 0 || i == len - 1 )); then
                echo -n +
        else
                echo -n -
        fi
done
printf '\n'
```

Работа скрипта:
cloverix@cloverix-MDG-XX:~/test$ ./banner "Hello from RTU MIREA!"
+-----------------------+
| Hello from RTU MIREA! |
+-----------------------+
