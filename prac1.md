## Задача 2
`cat protocols | awk '{print $2, $1}' | sort -r | tail -5`

## Задача 3
Код bash:

```
#!/usr/bin/bash

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
```
cloverix@cloverix-MDG-XX:~/test$ ./banner "Hello from RTU MIREA!"
+-----------------------+
| Hello from RTU MIREA! |
+-----------------------+
```

## Задача 4
код bash:
```
#!/usr/bin/bash

file=$1
grep -o -E '[a-zA-Z\_]+' < $file | sort --unique | xargs
```

тестовый файл test.txt:
```
#include <stdio.h>

int main(void) {
    printf("Hello, World!\n");
    return 0;
}

World
int_count
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./idens test.txt
h Hello include int int_count main n printf return stdio void World
```

## Задача 5
код bash:
```
#!/usr/bin/bash

chmod +x "$1" && sudo cp "$1" /usr/local/bin/"$1"
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./reg idens
cloverix@cloverix-MDG-XX:~/test$ ls /usr/local/bin
idens
```

## Задача 6
код bash:
```
#!/usr/bin/bash

path=$1
c_js_files=()
py_files=()
for file in `find $1 -type f`; do
        read -r line < "$file"

        if [[ "$file" == *".c" || "$file" == *".js" ]]; then

                if [[ $line == "//"* || $line == "/*"*"*/" ]]; then
                        c_js_files+=("$file")
                fi

        elif [[ "$file" == *".py" ]]; then

                if [[ $line == "#"* || $line == "\"\"\""* || $line == "'''"* ]]; then
                        py_files+=("$file")
                fi

        fi
done

echo "Файлы c и js с комментариями:"
echo "${c_js_files[*]}"

echo "Файлы py с комментариями:"
echo "${py_files[*]}"
```

тестовые файлы:
```
cloverix@cloverix-MDG-XX:~/test/testdir$ ls
f.c  f.js  f.py  f2.js  f2.py
cloverix@cloverix-MDG-XX:~/test/testdir$ ls | xargs cat
//Это комментарий
Это не комментарий
"""Комм"""
/*Это опять комментарий*/
\# И это комментарий
```

работа скрипта:
```
cloverix@cloverix-MDG-XX:~/test$ ./sfc testdir
Файлы c и js с комментариями:
testdir/f.c testdir/f2.js
Файлы py с комментариями:
testdir/f.py testdir/f2.py
```
